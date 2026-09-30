"""Deterministic vault tools the LLM agent calls: index, log, lint, search.

The vault root is the store directory (open it in Obsidian). Links are written
as vault-absolute paths without extension, e.g. ``[[wiki/concepts/국내-여행|국내 여행]]``.

Nothing here writes knowledge. These tools only catalog, record, and check
what the agent wrote, so mistakes are caught by code rather than trusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from .config import StoreConfig
from .models import CompileStatus
from .store import SourceRepository

LINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
PAGE_REF_RE = re.compile(r"(?:\bp{1,2}\.\s*\d|§\s*\d|\bsec\.\s*\d|\d+\s*쪽)", re.IGNORECASE)
SOURCE_LINK_RE = re.compile(r"\[\[wiki/(?:papers|sources)/")

# Page folders under wiki/ whose bullet points are synthesis and must cite sources.
SYNTHESIS_TYPES = {
    "concepts",
    "theories",
    "methods",
    "datasets",
    "technologies",
    "topics",
    "overviews",
    "questions",
    "researchers",
    "organizations",
    "synthesis",
}
SOURCE_TYPES = {"papers", "sources"}
# Sections that are navigation, not claims.
NAV_SECTIONS = {
    "related pages",
    "related papers",
    "related concepts",
    "key papers",
    "sources",
    "see also",
    "links",
    "change log",
    "status",
}
REQUIRED_FRONTMATTER = ("type", "title")


@dataclass
class Page:
    path: Path
    rel: str  # vault-relative, without .md
    folder: str  # e.g. "concepts" (second path part under wiki/ or ideas/)
    area: str  # "wiki" | "ideas" | other
    frontmatter: dict
    body: str
    fm_error: str | None = None

    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title") or self.path.stem)

    def links(self) -> list[str]:
        return [t.strip() for t in LINK_RE.findall(self.body)]

    def sections(self) -> list[tuple[str, str]]:
        heads = list(SECTION_RE.finditer(self.body))
        out = []
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(self.body)
            out.append((m.group(1).strip(), self.body[m.end() : end]))
        return out


def load_pages(store: StoreConfig) -> list[Page]:
    pages: list[Page] = []
    for area in ("wiki", "ideas"):
        base = store.root / area
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            fm, body, err = {}, text, None
            m = FRONTMATTER_RE.match(text)
            if m:
                try:
                    fm = yaml.safe_load(m.group(1)) or {}
                    if not isinstance(fm, dict):
                        fm, err = {}, "frontmatter is not a mapping"
                except yaml.YAMLError as exc:
                    err = f"invalid YAML: {exc.__class__.__name__}"
                body = text[m.end() :]
            else:
                err = "missing frontmatter"
            rel_path = path.relative_to(store.root)
            parts = rel_path.parts
            pages.append(
                Page(
                    path=path,
                    rel=str(rel_path.with_suffix("")),
                    folder=parts[1] if len(parts) > 2 else "",
                    area=area,
                    frontmatter=fm,
                    body=body,
                    fm_error=err,
                )
            )
    return pages


def resolve_link(store: StoreConfig, target: str, by_stem: dict[str, list[str]]) -> str | None:
    """Return the vault-relative target a link points to, or None if it is broken."""
    target = target.strip().removesuffix(".md")
    if (store.root / f"{target}.md").exists() or (store.root / target).is_file():
        return target
    matches = by_stem.get(Path(target).name, [])
    return matches[0] if len(matches) == 1 else None  # Obsidian shortest-path links


# --- index.md --------------------------------------------------------------

_INDEX_ORDER = [
    ("wiki", "overviews", "Overviews"),
    ("wiki", "topics", "Topics"),
    ("wiki", "concepts", "Concepts"),
    ("wiki", "theories", "Theories"),
    ("wiki", "methods", "Methods"),
    ("wiki", "datasets", "Datasets"),
    ("wiki", "technologies", "Technologies"),
    ("wiki", "researchers", "Researchers"),
    ("wiki", "organizations", "Organizations"),
    ("wiki", "papers", "Papers"),
    ("wiki", "sources", "Other Sources"),
    ("wiki", "questions", "Open Questions"),
    ("wiki", "synthesis", "Synthesis (filed answers)"),
]


def build_index(store: StoreConfig) -> str:
    pages = load_pages(store)
    lines = [
        "---",
        "type: index",
        "title: Index",
        f"updated: '{date.today().isoformat()}'",
        "---",
        "",
        "# Index",
        "",
        "> `sb index`가 자동 생성합니다. 직접 수정하지 마세요. "
        "에이전트는 질문에 답할 때 이 파일을 먼저 읽습니다.",
        "",
    ]
    for area, folder, label in _INDEX_ORDER:
        group = [p for p in pages if p.area == area and p.folder == folder]
        if not group:
            continue
        lines.append(f"## {label} ({len(group)})")
        lines.append("")
        for p in sorted(group, key=lambda x: x.title):
            meta = []
            fm = p.frontmatter
            if folder in SOURCE_TYPES:
                authors = fm.get("authors") or []
                if authors:
                    who = authors[0] + (" 외" if len(authors) > 1 else "")
                    meta.append(f"{who} ({fm.get('year', 'n.d.')})")
                if fm.get("evidence_level"):
                    meta.append(str(fm["evidence_level"]))
            if fm.get("sources"):
                meta.append(f"sources: {len(fm['sources'])}")
            if fm.get("review") == "pending":
                meta.append("🔎 review")
            summary = f" — {fm['summary']}" if fm.get("summary") else ""
            suffix = f" _({'; '.join(meta)})_" if meta else ""
            lines.append(f"- [[{p.rel}|{p.title}]]{summary}{suffix}")
        lines.append("")
    ideas = [p for p in pages if p.area == "ideas"]
    if ideas:
        lines += [f"## Ideas ({len(ideas)}) — 확정 지식 아님", ""]
        for p in sorted(ideas, key=lambda x: (x.folder, x.title)):
            status = p.frontmatter.get("status", "detected")
            lines.append(f"- [[{p.rel}|{p.title}]] _({p.folder}; {status})_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_index(store: StoreConfig) -> Path:
    store.index_md.write_text(build_index(store), encoding="utf-8")
    return store.index_md


# --- log.md ----------------------------------------------------------------

LOG_KINDS = {"register", "ingest", "query", "lint", "idea", "review", "note"}


def append_log(store: StoreConfig, kind: str, title: str, bullets: list[str] | None = None) -> None:
    """Append a greppable entry: ``## [YYYY-MM-DD] kind | title``."""
    if kind not in LOG_KINDS:
        raise ValueError(f"kind must be one of {sorted(LOG_KINDS)}")
    if not store.log_md.exists():
        store.log_md.write_text(
            "---\ntype: log\ntitle: Log\n---\n\n# Log\n\n"
            "> 추가만 하는 기록입니다. "
            "`grep '^## \\[' log.md | tail`로 최근 항목을 볼 수 있습니다.\n",
            encoding="utf-8",
        )
    entry = [f"\n## [{date.today().isoformat()}] {kind} | {title}"]
    entry += [f"- {b}" for b in bullets or []]
    with store.log_md.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(entry) + "\n")


def mark_compiled(
    store: StoreConfig,
    source_id: str,
    wiki_page: str,
    touched: list[str],
    effects: list[str],
    note: str | None = None,
) -> None:
    """Record that the agent finished integrating a source (spec §22 traceability)."""
    repo = SourceRepository(store)
    src = repo.get(source_id)
    if src is None:
        raise KeyError(source_id)
    page = wiki_page.removesuffix(".md")
    if not (store.root / f"{page}.md").exists():
        raise FileNotFoundError(f"{page}.md does not exist; write the source page first")
    src.status = CompileStatus.COMPILED
    src.wiki_page = page
    src.compiled_date = datetime.now()
    repo.save(src)
    bullets = [f"source: `{source_id}` → [[{page}]]"]
    bullets += [f"touched: [[{t.removesuffix('.md')}]]" for t in touched]
    bullets += [f"effect: {e}" for e in effects]
    if note:
        bullets.append(f"note: {note}")
    append_log(store, "ingest", src.title or source_id, bullets)


# --- lint ------------------------------------------------------------------


@dataclass
class Issue:
    level: str  # error | warn | info
    code: str
    page: str
    detail: str


@dataclass
class LintReport:
    issues: list[Issue] = field(default_factory=list)

    def add(self, level: str, code: str, page: str, detail: str) -> None:
        self.issues.append(Issue(level, code, page, detail))

    def count(self, level: str) -> int:
        return sum(1 for i in self.issues if i.level == level)


def _bullets_without_citation(section_body: str) -> list[str]:
    out = []
    for line in section_body.splitlines():
        s = line.strip()
        if not s.startswith(("- ", "* ")) or s.startswith(("- [ ]", "- [x]")):
            continue
        text_only = LINK_RE.sub("", s[2:]).strip(" -—:;,()")
        if len(text_only) < 6:  # pure navigation bullet like "- [[x]]"
            continue
        if not SOURCE_LINK_RE.search(s):
            out.append(s[:80])
    return out


def lint(store: StoreConfig) -> LintReport:
    report = LintReport()
    pages = load_pages(store)
    by_stem: dict[str, list[str]] = {}
    for p in pages:
        by_stem.setdefault(p.path.stem, []).append(p.rel)

    inbound: dict[str, set[str]] = {p.rel: set() for p in pages}
    for p in pages:
        if p.fm_error:
            report.add("error", "frontmatter", p.rel, p.fm_error)
        for key in REQUIRED_FRONTMATTER:
            if not p.fm_error and key not in p.frontmatter:
                report.add("error", "frontmatter", p.rel, f"missing `{key}`")
        for target in p.links():
            resolved = resolve_link(store, target, by_stem)
            if resolved is None:
                report.add("error", "broken-link", p.rel, f"[[{target}]]")
            elif resolved in inbound and resolved != p.rel:
                inbound[resolved].add(p.rel)

    for p in pages:
        fm = p.frontmatter
        # Ideas must never live in the knowledge layer (spec §15).
        if p.area == "wiki" and (fm.get("epistemic") == "idea" or fm.get("type") == "idea"):
            report.add("error", "idea-in-wiki", p.rel, "ideas belong under ideas/, not wiki/")
        if p.area == "ideas" and not SOURCE_LINK_RE.search(p.body):
            report.add("error", "idea-without-source", p.rel, "ideas must cite supporting sources")
        if p.area != "wiki":
            continue
        if not inbound[p.rel]:
            report.add("warn", "orphan", p.rel, "no other page links here")
        if p.folder in SOURCE_TYPES:
            linked_from_synthesis = any(
                src.split("/")[1] in SYNTHESIS_TYPES for src in inbound[p.rel] if "/" in src
            )
            if not linked_from_synthesis:
                report.add(
                    "warn",
                    "unconnected-source",
                    p.rel,
                    "source page not linked from any concept/theory/method/overview page",
                )
            for head, body in p.sections():
                if head.lower().startswith("claims"):
                    for line in body.splitlines():
                        if line.strip().startswith("- ") and not PAGE_REF_RE.search(line):
                            report.add("warn", "claim-without-page", p.rel, line.strip()[:80])
        if p.folder in SYNTHESIS_TYPES:
            for head, body in p.sections():
                if head.lower() in NAV_SECTIONS:
                    continue
                for bullet in _bullets_without_citation(body):
                    report.add("warn", "uncited", p.rel, f"[{head}] {bullet}")
        if fm.get("review") == "pending":
            report.add("info", "needs-review", p.rel, str(fm.get("review_reason", "")))

    for src in SourceRepository(store).all():
        if src.status == CompileStatus.PENDING:
            report.add("info", "pending-source", src.source_id, src.title or "")
        elif src.status == CompileStatus.NEEDS_TEXT:
            report.add("warn", "needs-text", src.source_id, "no parsable text (scan? OCR needed)")
        elif src.status == CompileStatus.COMPILED and src.wiki_page:
            if not (store.root / f"{src.wiki_page}.md").exists():
                report.add("error", "missing-source-page", src.source_id, src.wiki_page)

    indexed = (
        set(LINK_RE.findall(store.index_md.read_text(encoding="utf-8")))
        if store.index_md.exists()
        else set()
    )
    missing = [p.rel for p in pages if p.rel not in indexed]
    if missing:
        report.add(
            "info", "index-stale", "index.md", f"{len(missing)} page(s) not listed; run `sb index`"
        )
    return report


# --- search ----------------------------------------------------------------


@dataclass
class SearchHit:
    rel: str
    title: str
    score: int
    snippet: str


def search(store: StoreConfig, query: str, limit: int = 20) -> list[SearchHit]:
    terms = [t.lower() for t in query.split() if t.strip()]
    hits = []
    for p in load_pages(store):
        low = (p.title + "\n" + p.body).lower()
        score = sum(low.count(t) for t in terms)
        if not score:
            continue
        idx = min((low.find(t) for t in terms if t in low), default=0)
        snippet = " ".join(p.body[max(0, idx - 60) : idx + 60].split())
        hits.append(SearchHit(p.rel, p.title, score, snippet))
    return sorted(hits, key=lambda h: -h.score)[:limit]
