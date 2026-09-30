"""`sb digest` — what changed in the knowledge base over a period (spec §27).

Built only from ``log.md`` (what the agent and `sb` recorded) plus the current
review queue and pending sources, so the digest never claims anything that was
not logged.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import StoreConfig
from .models import CompileStatus
from .store import SourceRepository
from .vault import load_pages

ENTRY_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.*)$")
EFFECTS = ("strengthen", "narrow", "extend", "contradict", "replace", "unchanged")
EFFECT_RE = re.compile(
    r"^effect:\s*(\S+?):\s*(" + "|".join(EFFECTS) + r")\b\s*(?:[—\-:]\s*(.*))?$", re.IGNORECASE
)
LINK_TARGET_RE = re.compile(r"\[\[([^\]|#]+)")


@dataclass
class LogEntry:
    day: date
    kind: str
    title: str
    bullets: list[str] = field(default_factory=list)


def parse_log(text: str) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line.strip())
        if m:
            entries.append(LogEntry(date.fromisoformat(m.group(1)), m.group(2), m.group(3)))
        elif entries and line.startswith("- "):
            entries[-1].bullets.append(line[2:].strip())
    return entries


@dataclass
class Digest:
    start: date
    end: date
    registered: list[str] = field(default_factory=list)
    ingested: list[tuple[str, str | None]] = field(default_factory=list)  # (title, page)
    effects: list[tuple[str, str, str]] = field(default_factory=list)  # (page, effect, reason)
    touched: Counter = field(default_factory=Counter)
    queries: list[str] = field(default_factory=list)
    ideas: list[str] = field(default_factory=list)
    lints: list[str] = field(default_factory=list)
    new_questions: list[str] = field(default_factory=list)
    review: list[tuple[str, str]] = field(default_factory=list)
    pending: int = 0
    needs_text: int = 0
    highlights_changed: list[str] = field(default_factory=list)

    def render(self) -> str:
        eff = Counter(e for _, e, _ in self.effects)
        L = [
            "---",
            "type: digest",
            f"title: Digest {self.start} ~ {self.end}",
            f"period: '{self.start} ~ {self.end}'",
            "---",
            "",
            f"# Digest {self.start} ~ {self.end}",
            "",
            "> `sb digest`가 log.md로 만든 요약입니다. 기록되지 않은 변화는 나오지 않습니다.",
            "",
            "## 한눈에",
            f"- 새로 등록한 자료: {len(self.registered)}",
            f"- 위키에 반영한 자료: {len(self.ingested)}",
            f"- 고친 페이지: {len(self.touched)}",
            "- 지식 변화: "
            + (", ".join(f"{k} {eff[k]}" for k in EFFECTS if eff[k]) or "기록 없음"),
            f"- 새 열린 질문: {len(self.new_questions)}",
            f"- 질의 {len(self.queries)} · 아이디어 기록 {len(self.ideas)} "
            f"· 점검 {len(self.lints)}",
            f"- 지금 검토 대기: {len(self.review)} · 반영 대기 자료: {self.pending}"
            + (f" · 텍스트 없음: {self.needs_text}" if self.needs_text else ""),
            "",
        ]
        important = [e for e in self.effects if e[1] in ("contradict", "replace", "narrow")]
        if important:
            L += ["## ⚡ 확인할 지식 변화 (충돌·대체·축소)", ""]
            L += [f"- **{e}** [[{p}]] — {r or '이유 기록 없음'}" for p, e, r in important]
            L.append("")
        if self.ingested:
            L += ["## 반영된 자료", ""]
            L += [f"- [[{p}|{t}]]" if p else f"- {t}" for t, p in self.ingested]
            L.append("")
        others = [e for e in self.effects if e not in important]
        if others:
            L += ["## 그 밖의 변화", ""]
            L += [f"- {e} [[{p}]]" + (f" — {r}" if r else "") for p, e, r in others]
            L.append("")
        if self.touched:
            L += ["## 가장 많이 고쳐진 페이지", ""]
            L += [f"- [[{p}]] ({n}회)" for p, n in self.touched.most_common(10)]
            L.append("")
        if self.new_questions:
            L += ["## 새로 생기거나 갱신된 열린 질문", ""]
            L += [f"- [[{q}]]" for q in self.new_questions]
            L.append("")
        if self.highlights_changed:
            L += ["## Zotero 하이라이트가 바뀐 논문 (다시 반영 필요)", ""]
            L += [f"- {t}" for t in self.highlights_changed]
            L.append("")
        if self.review:
            L += ["## 검토 대기", ""]
            L += [f"- [[{p}]] — {r}" for p, r in self.review]
            L.append("")
        if self.registered:
            L += ["## 등록된 자료", ""]
            L += [f"- {t}" for t in self.registered]
            L.append("")
        if self.queries or self.ideas or self.lints:
            L += ["## 질의·아이디어·점검 기록", ""]
            L += [f"- 질의: {q}" for q in self.queries]
            L += [f"- 아이디어: {i}" for i in self.ideas]
            L += [f"- 점검: {x}" for x in self.lints]
            L.append("")
        return "\n".join(L).rstrip() + "\n"


def build_digest(store: StoreConfig, days: int = 7, end: date | None = None) -> Digest:
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    d = Digest(start, end)
    text = store.log_md.read_text(encoding="utf-8") if store.log_md.exists() else ""
    for e in parse_log(text):
        if not (start <= e.day <= end):
            continue
        if e.kind == "register":
            if e.title.startswith("zotero sync"):
                d.registered += [
                    re.sub(r"^[^:]+:\s*(`[^`]*`\s*)?", "", b)
                    for b in e.bullets
                    if b.startswith(("added:", "metadata only:", "pdf attached:"))
                ]
            else:
                d.registered.append(e.title)
        elif e.kind == "ingest":
            page = None
            for b in e.bullets:
                if b.startswith("source:"):
                    m = LINK_TARGET_RE.search(b)
                    page = m.group(1) if m else None
                elif b.startswith("touched:"):
                    for t in LINK_TARGET_RE.findall(b):
                        d.touched[t] += 1
                        if t.startswith("wiki/questions/") and t not in d.new_questions:
                            d.new_questions.append(t)
                else:
                    m = EFFECT_RE.match(b)
                    if m:
                        target = m.group(1).removesuffix(".md")
                        d.effects.append((target, m.group(2).lower(), (m.group(3) or "").strip()))
            d.ingested.append((e.title, page))
            if page:
                d.touched[page] += 1
        elif e.kind == "query":
            d.queries.append(e.title)
        elif e.kind == "idea":
            d.ideas.append(e.title)
        elif e.kind == "lint":
            d.lints.append(e.title)
    for p in load_pages(store):
        if p.frontmatter.get("review") == "pending":
            d.review.append((p.rel, str(p.frontmatter.get("review_reason", ""))))
    for s in SourceRepository(store).all():
        if s.status == CompileStatus.PENDING:
            d.pending += 1
        elif s.status == CompileStatus.NEEDS_TEXT:
            d.needs_text += 1
        if s.annotations_changed:
            d.highlights_changed.append(s.title or s.source_id)
    return d
