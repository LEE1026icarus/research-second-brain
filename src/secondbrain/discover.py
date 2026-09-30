"""`sb discover` — new papers worth a look (spec §3.2 alerts, §29 project context).

Seeds, all from things the user chose:

* papers in the library (their OpenAlex IDs from ``sb refs``) → new works citing them,
* each research project's ``important_references`` (DOIs) → new works citing them,
* each project's ``keywords`` → recent works matching them.

Works already in the library, and works shown in an earlier run, are skipped.
The result is a reading list in ``reports/discover-<date>.md``. Nothing is
registered or ingested automatically — add what you want to Zotero, then
``sb zotero sync``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .config import StoreConfig
from .openalex import OpenAlex, _norm_doi, _slim, load_citations, short_id
from .store import ProjectRepository, SourceRepository


@dataclass
class Hit:
    work: str
    info: dict
    reasons: list[str] = field(default_factory=list)
    projects: set[str] = field(default_factory=set)
    score: float = 0.0


@dataclass
class DiscoverResult:
    since: str
    hits: list[Hit] = field(default_factory=list)
    seeds: int = 0
    skipped_known: int = 0
    search_errors: list[str] = field(default_factory=list)


def _state_path(store: StoreConfig) -> Path:
    return store.kg / "discover.json"


def _load_state(store: StoreConfig) -> dict:
    p = _state_path(store)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"seen": [], "seed_ids": {}}


def discover(
    store: StoreConfig,
    oa: OpenAlex,
    days: int = 90,
    per_seed: int = 10,
    include_seen: bool = False,
    today: date | None = None,
) -> DiscoverResult:
    today = today or date.today()
    since = (today - timedelta(days=days)).isoformat()
    res = DiscoverResult(since=since)
    state = _load_state(store)
    cites = load_citations(store)
    sources = SourceRepository(store).all()
    projects = ProjectRepository(store).all()

    known_ids = {e["openalex"] for e in cites["sources"].values() if e.get("openalex")}
    known_dois = {_norm_doi(s.doi) for s in sources if s.doi}
    seen = set(state.get("seen", []))
    hits: dict[str, Hit] = {}

    def add(work: dict, reason: str, weight: float, project: str | None = None) -> None:
        wid = short_id(work["id"])
        info = _slim(work)
        info["publication_date"] = work.get("publication_date")
        if wid in known_ids or (info.get("doi") and info["doi"] in known_dois):
            res.skipped_known += 1
            return
        if wid in seen and not include_seen:
            return
        h = hits.setdefault(wid, Hit(wid, info))
        if reason not in h.reasons:
            h.reasons.append(reason)
            h.score += weight
        if project:
            h.projects.add(project)

    # 1) new works citing papers in my library
    for s in sources:
        entry = cites["sources"].get(s.source_id) or {}
        if not entry.get("openalex"):
            continue
        res.seeds += 1
        label = f"[[{s.wiki_page}|{s.title}]]" if s.wiki_page else (s.title or s.source_id)
        for w in oa.citing(entry["openalex"], since=since, per_page=per_seed):
            add(w, f"내 논문 {label}을(를) 인용", 2.0)

    # 2) projects: important references and keywords
    seed_ids: dict[str, str] = state.setdefault("seed_ids", {})
    for p in projects:
        for doi in p.important_references:
            doi = _norm_doi(doi)
            if not doi:
                continue
            if doi not in seed_ids:
                w = oa.work_by_doi(doi)
                if not w:
                    continue
                seed_ids[doi] = short_id(w["id"])
            res.seeds += 1
            for w in oa.citing(seed_ids[doi], since=since, per_page=per_seed):
                add(w, f"프로젝트 '{p.title}'의 핵심 문헌 {doi}를 인용", 2.0, p.title)
        for kw in p.keywords:
            res.seeds += 1
            for w in oa.search_recent(kw, since=since, per_page=per_seed):
                add(w, f"프로젝트 '{p.title}' 키워드 '{kw}'", 1.0, p.title)

    # Relevance boost: title shares a word with any project keyword.
    terms = {
        t.lower()
        for p in projects
        for kw in p.keywords + p.research_interests
        for t in kw.replace(",", " ").split()
        if len(t) >= 4
    }
    for h in hits.values():
        title = (h.info.get("title") or "").lower()
        matched = sorted(t for t in terms if t in title)
        if matched:
            h.score += 1.0
            h.reasons.append(f"제목에 프로젝트 키워드 포함: {', '.join(matched)}")

    res.hits = sorted(
        hits.values(),
        key=lambda h: (-h.score, -(h.info.get("cited_by_count") or 0), h.info.get("title") or ""),
    )
    res.search_errors = list(oa.search_errors)
    state["seen"] = sorted(seen | set(hits))
    state["last_run"] = today.isoformat()
    _state_path(store).parent.mkdir(parents=True, exist_ok=True)
    _state_path(store).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def render(res: DiscoverResult, limit: int = 40) -> str:
    L = [
        "---",
        "type: report",
        f"title: 새 논문 후보 ({date.today().isoformat()})",
        f"since: '{res.since}'",
        "---",
        "",
        f"# 새 논문 후보 — {res.since} 이후",
        "",
        "> `sb discover`가 OpenAlex에서 찾은 **읽을 후보**입니다. 위키 지식이 아니고 자동으로 "
        "등록되지 않습니다. 읽을 논문은 Zotero에 DOI로 추가한 뒤 `sb zotero sync`하세요.",
        "",
        f"기준 {res.seeds}개 · 후보 {len(res.hits)}편 · 이미 가진 논문 제외 {res.skipped_known}건",
        "",
    ]
    if res.search_errors:
        L += ["> ⚠️ OpenAlex 키워드 검색 실패: " + "; ".join(res.search_errors), ""]
    for h in res.hits[:limit]:
        w = h.info
        who = (
            (w["authors"][0] + (" et al." if w.get("n_authors", 0) > 1 else ""))
            if w.get("authors")
            else ""
        )
        doi = f" · doi: `{w['doi']}`" if w.get("doi") else ""
        proj = f" · 프로젝트: {', '.join(sorted(h.projects))}" if h.projects else ""
        L.append(
            f"- **{w.get('title')}** — {who} ({w.get('publication_date') or w.get('year')})"
            f"{doi}{proj}"
        )
        L += [f"  - {r}" for r in h.reasons]
    if not res.hits:
        L.append("- 새 후보가 없습니다.")
    return "\n".join(L).rstrip() + "\n"
