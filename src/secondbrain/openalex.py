"""Citation data from OpenAlex (read-only): `sb refs` and `sb discover`.

For each registered source with a DOI (or a findable title) this module gets
its OpenAlex record and reference list, and stores them in
``kg/citations.json``. From that it builds:

* citation edges *inside* the library (which of my papers cite each other),
* reading suggestions: works that several of my papers cite but I don't have.

Many journals (including many Korean ones) do not deposit reference lists, so
OpenAlex may return none. In that case the agent writes a ``## References``
section on the paper page from the paper's own reference list, one line per
reference in the form ``- 저자 (연도) | 제목 | 학술지 | doi: ...``; `sb refs`
then resolves those lines against OpenAlex by DOI or title.

No key is needed for light use; set ``OPENALEX_API_KEY`` for a larger daily
allowance (https://openalex.org — free account).
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import StoreConfig
from .store import SourceRepository
from .vault import FRONTMATTER_RE, SECTION_RE

API = "https://api.openalex.org"
SELECT = "id,doi,display_name,publication_year,cited_by_count,authorships,referenced_works"
WORK_SELECT = "id,doi,display_name,publication_year,cited_by_count,authorships"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s|,;]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(1[89]\d\d|20\d\d)\b")

Fetch = Callable[[str], dict]


class OpenAlexError(RuntimeError):
    pass


class SearchUnavailable(OpenAlexError):
    """Title search failed (e.g. anonymous search paused); DOI lookups may still work."""


def http_fetch(api_key: str | None = None) -> Fetch:
    def fetch(url: str) -> dict:
        if api_key:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"api_key": api_key})
        req = urllib.request.Request(url, headers={"User-Agent": "research-second-brain"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed host
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            if exc.code in (409, 429):
                raise OpenAlexError(
                    "OpenAlex daily allowance used up. Set OPENALEX_API_KEY "
                    "(free account at openalex.org) or try again tomorrow."
                ) from exc
            try:
                msg = json.loads(exc.read().decode("utf-8")).get("message", "")
            except Exception:  # noqa: BLE001
                msg = ""
            if "search=" in url or ".search:" in url:
                raise SearchUnavailable(msg or f"HTTP {exc.code}") from exc
            raise OpenAlexError(f"HTTP {exc.code} for {url.split('?')[0]} {msg}".strip()) from exc
        except urllib.error.URLError as exc:
            raise OpenAlexError(f"cannot reach OpenAlex ({exc.reason})") from exc

    return fetch


def short_id(openalex_id: str) -> str:
    return openalex_id.rsplit("/", 1)[-1]


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")
    return doi.rstrip(".") or None


def _norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").lower()
    return re.sub(r"[\W_]+", "", t)


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm_title(a), _norm_title(b)).ratio()


def _slim(work: dict) -> dict:
    authors = [
        (a.get("author") or {}).get("display_name")
        for a in work.get("authorships") or []
        if (a.get("author") or {}).get("display_name")
    ]
    return {
        "title": work.get("display_name"),
        "year": work.get("publication_year"),
        "doi": _norm_doi(work.get("doi")),
        "cited_by_count": work.get("cited_by_count", 0),
        "authors": authors[:3],
        "n_authors": len(authors),
    }


@dataclass
class OpenAlex:
    fetch: Fetch
    search_errors: list[str] = field(default_factory=list)

    def _search(self, url: str) -> dict:
        try:
            return self.fetch(url)
        except SearchUnavailable as exc:
            if str(exc) not in self.search_errors:
                self.search_errors.append(str(exc))
            return {}

    def work_by_doi(self, doi: str) -> dict | None:
        doi = _norm_doi(doi)
        if not doi:
            return None
        data = self.fetch(f"{API}/works/doi:{urllib.parse.quote(doi)}?select={SELECT}")
        return data or None

    def search_title(
        self, title: str, year: int | None = None, min_sim: float = 0.85
    ) -> dict | None:
        params = {"search": title[:250], "per_page": "5", "select": SELECT}
        if year:
            params["filter"] = f"publication_year:{year - 1}-{year + 1}"
        data = self._search(f"{API}/works?{urllib.parse.urlencode(params)}")
        best, best_sim = None, 0.0
        for w in data.get("results") or []:
            sim = title_similarity(title, w.get("display_name") or "")
            if sim > best_sim:
                best, best_sim = w, sim
        return best if best_sim >= min_sim else None

    def works(self, ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        ids = [short_id(i) for i in ids]
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            params = {
                "filter": "openalex:" + "|".join(chunk),
                "per_page": "50",
                "select": WORK_SELECT,
            }
            data = self.fetch(f"{API}/works?{urllib.parse.urlencode(params)}")
            for w in data.get("results") or []:
                out[short_id(w["id"])] = _slim(w)
        return out

    def citing(self, work_id: str, since: str | None = None, per_page: int = 25) -> list[dict]:
        flt = f"cites:{short_id(work_id)}"
        if since:
            flt += f",from_publication_date:{since}"
        params = {
            "filter": flt,
            "per_page": str(per_page),
            "sort": "publication_date:desc",
            "select": WORK_SELECT + ",publication_date",
        }
        data = self.fetch(f"{API}/works?{urllib.parse.urlencode(params)}")
        return data.get("results") or []

    def search_recent(self, query: str, since: str, per_page: int = 25) -> list[dict]:
        params = {
            "search": query,
            "filter": f"from_publication_date:{since}",
            "per_page": str(per_page),
            "sort": "relevance_score:desc",
            "select": WORK_SELECT + ",publication_date",
        }
        data = self._search(f"{API}/works?{urllib.parse.urlencode(params)}")
        return data.get("results") or []


# --- references written by the agent on paper pages ---------------------------


def page_doi(store: StoreConfig, wiki_page: str | None) -> str | None:
    """DOI written in the paper page frontmatter (when the source record has none)."""
    if not wiki_page or not (store.root / f"{wiki_page}.md").exists():
        return None
    m = FRONTMATTER_RE.match((store.root / f"{wiki_page}.md").read_text(encoding="utf-8"))
    d = DOI_RE.search(m.group(1)) if m else None
    return _norm_doi(d.group(0)) if d else None


def page_references(store: StoreConfig, wiki_page: str | None) -> list[str]:
    """Lines of the ``## References`` section of a paper page (agent-written)."""
    if not wiki_page:
        return []
    path = store.root / f"{wiki_page}.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    body = text[m.end() :] if m else text
    heads = list(SECTION_RE.finditer(body))
    for i, h in enumerate(heads):
        if h.group(1).strip().lower() in ("references", "참고문헌"):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            return [
                ln.strip()[2:].strip()
                for ln in body[h.end() : end].splitlines()
                if ln.strip().startswith("- ")
            ]
    return []


def parse_reference(line: str) -> tuple[str | None, str | None, int | None]:
    """(doi, title, year) from ``저자 (연도) | 제목 | 학술지 | doi: ...``."""
    doi_m = DOI_RE.search(line)
    doi = _norm_doi(doi_m.group(0)) if doi_m else None
    parts = [p.strip() for p in line.split("|")]
    year_m = YEAR_RE.search(parts[0]) if parts else None
    title = parts[1] if len(parts) > 1 and parts[1] else None
    return doi, title, int(year_m.group(1)) if year_m else None


# --- sb refs -------------------------------------------------------------------


@dataclass
class RefsReport:
    fetched: list[str] = field(default_factory=list)  # source ids updated
    not_found: list[str] = field(default_factory=list)  # titles not in OpenAlex
    no_references: list[str] = field(default_factory=list)  # found, but no reference list
    unresolved_refs: int = 0
    search_errors: list[str] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)
    internal: list[tuple[str, str]] = field(default_factory=list)  # (citing sid, cited sid)


def citations_path(store: StoreConfig) -> Path:
    return store.kg / "citations.json"


def load_citations(store: StoreConfig) -> dict:
    p = citations_path(store)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"sources": {}, "works": {}}


def save_citations(store: StoreConfig, data: dict) -> None:
    p = citations_path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_refs(
    store: StoreConfig, oa: OpenAlex, only: str | None = None, force: bool = False
) -> RefsReport:
    rep = RefsReport()
    data = load_citations(store)
    sources = SourceRepository(store).all()
    for s in sources:
        if only and s.source_id != only:
            continue
        entry = data["sources"].get(s.source_id, {})
        page_refs = page_references(store, s.wiki_page)
        if entry and not force and entry.get("n_page_refs", 0) == len(page_refs):
            continue
        doi = s.doi or page_doi(store, s.wiki_page)
        work = oa.work_by_doi(doi) if doi else None
        if work is None and s.title:
            work = oa.search_title(s.title, s.year)
        if work is None:
            data["sources"][s.source_id] = {"openalex": None, "fetched": date.today().isoformat()}
            continue
        refs = [short_id(r) for r in work.get("referenced_works") or []]
        origin = "openalex"
        unresolved: list[str] = []
        if not refs and page_refs:
            origin = "page"
            for line in page_refs:
                doi, title, year = parse_reference(line)
                w = oa.work_by_doi(doi) if doi else None
                if w is None and title:
                    w = oa.search_title(title, year)
                if w is None:
                    unresolved.append(line)
                else:
                    refs.append(short_id(w["id"]))
                    data["works"][short_id(w["id"])] = _slim(w)
            rep.unresolved_refs += len(unresolved)
        data["sources"][s.source_id] = {
            "openalex": short_id(work["id"]),
            "title": work.get("display_name"),
            "cited_by_count": work.get("cited_by_count", 0),
            "references": refs,
            "ref_origin": origin if refs else None,
            "n_page_refs": len(page_refs),
            "unresolved": unresolved,
            "fetched": date.today().isoformat(),
        }
        data["works"][short_id(work["id"])] = _slim(work)
        rep.fetched.append(s.source_id)

    # Metadata for referenced works we have not seen yet (batched).
    wanted = {r for e in data["sources"].values() for r in e.get("references") or []}
    missing = sorted(wanted - set(data["works"]))
    if missing:
        data["works"].update(oa.works(missing))
    save_citations(store, data)
    titles = {x.source_id: x.title or x.source_id for x in sources}
    for sid, e in data["sources"].items():
        if sid not in titles:
            continue
        if not e.get("openalex"):
            rep.not_found.append(titles[sid])
        elif not e.get("references"):
            rep.no_references.append(titles[sid])
    rep.suggestions, rep.internal = analyze(store, data)
    rep.search_errors = list(oa.search_errors)
    return rep


def analyze(store: StoreConfig, data: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    """Reading suggestions and citation edges inside the library."""
    sources = {s.source_id: s for s in SourceRepository(store).all()}
    mine_by_work = {e["openalex"]: sid for sid, e in data["sources"].items() if e.get("openalex")}
    my_dois = {(_norm_doi(s.doi)) for s in sources.values() if s.doi}
    internal: list[tuple[str, str]] = []
    counts: dict[str, list[str]] = {}
    for sid, e in data["sources"].items():
        for ref in e.get("references") or []:
            if ref in mine_by_work:
                internal.append((sid, mine_by_work[ref]))
                continue
            w = data["works"].get(ref, {})
            if w.get("doi") and w["doi"] in my_dois:
                continue
            counts.setdefault(ref, []).append(sid)
    suggestions = [
        {"work": ref, **data["works"].get(ref, {}), "cited_by_mine": sids}
        for ref, sids in counts.items()
    ]
    suggestions.sort(key=lambda x: (-len(x["cited_by_mine"]), -(x.get("cited_by_count") or 0)))
    return suggestions, internal


def _work_line(w: dict) -> str:
    who = ""
    if w.get("authors"):
        who = w["authors"][0] + (" et al." if (w.get("n_authors") or 0) > 1 else "") + " "
    doi = f" · doi: `{w['doi']}`" if w.get("doi") else ""
    return (
        f"{who}({w.get('year') or 'n.d.'}) **{w.get('title') or w.get('work')}**"
        f" · 피인용 {w.get('cited_by_count') or 0}{doi}"
    )


def render_reading_report(store: StoreConfig, rep: RefsReport, limit: int = 30) -> str:
    sources = {s.source_id: s for s in SourceRepository(store).all()}

    def mine(sid: str) -> str:
        s = sources.get(sid)
        if s and s.wiki_page:
            return f"[[{s.wiki_page}|{s.title}]]"
        return (s.title if s else sid) or sid

    L = [
        "---",
        "type: report",
        "title: 읽을 만한 논문 (인용 기반)",
        f"updated: '{date.today().isoformat()}'",
        "---",
        "",
        "# 읽을 만한 논문 (인용 기반)",
        "",
        "> `sb refs`가 OpenAlex 인용 데이터로 만든 목록입니다. "
        "내 라이브러리 논문들이 많이 인용하지만 "
        "나는 아직 갖고 있지 않은 논문 순서입니다. 추천일 뿐이며 위키 지식이 아닙니다. "
        "읽고 싶은 논문은 Zotero에 DOI로 추가한 뒤 `sb zotero sync`하세요.",
        "",
        f"## 추천 ({min(limit, len(rep.suggestions))}/{len(rep.suggestions)})",
        "",
    ]
    for w in rep.suggestions[:limit]:
        cited = ", ".join(mine(s) for s in w["cited_by_mine"][:5])
        L.append(f"- {_work_line(w)} — 내 논문 {len(w['cited_by_mine'])}편이 인용: {cited}")
    if not rep.suggestions:
        L.append("- (아직 없음 — 인용 목록이 있는 논문이 더 필요합니다)")
    L += ["", "## 내 라이브러리 안의 인용 관계", ""]
    L += [f"- {mine(a)} → {mine(b)}" for a, b in rep.internal] or ["- (없음)"]
    if rep.no_references or rep.not_found:
        L += ["", "## 인용 목록을 못 가져온 자료", ""]
        L += [
            f"- {t} — OpenAlex에 참고문헌 목록이 없음. 에이전트가 논문 페이지에 "
            "`## References`를 적으면 다시 시도합니다"
            for t in rep.no_references
        ]
        L += [f"- {t} — OpenAlex에서 찾지 못함" for t in rep.not_found]
    return "\n".join(L).rstrip() + "\n"
