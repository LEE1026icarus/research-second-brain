"""OpenAlex citations with a fake API."""

from __future__ import annotations

import urllib.parse

from secondbrain import openalex as oa
from secondbrain.agents import IngestionAgent

WORKS = {
    "W1": {
        "display_name": "My Paper One",
        "doi": "https://doi.org/10.1111/one",
        "publication_year": 2020,
        "cited_by_count": 3,
        "referenced_works": [
            "https://openalex.org/W2",
            "https://openalex.org/W9",
            "https://openalex.org/W8",
        ],
    },
    "W2": {
        "display_name": "My Paper Two",
        "doi": "https://doi.org/10.1111/two",
        "publication_year": 2021,
        "cited_by_count": 1,
        "referenced_works": ["https://openalex.org/W9"],
    },
    "W3": {
        "display_name": "Korean Paper Without Refs",
        "doi": "https://doi.org/10.1111/ko",
        "publication_year": 2020,
        "cited_by_count": 0,
        "referenced_works": [],
    },
    "W8": {
        "display_name": "Rarely Cited",
        "doi": "https://doi.org/10.9999/b",
        "publication_year": 2010,
        "cited_by_count": 5,
    },
    "W9": {
        "display_name": "Classic Theory Paper",
        "doi": "https://doi.org/10.9999/a",
        "publication_year": 1980,
        "cited_by_count": 7000,
        "authorships": [{"author": {"display_name": "Oliver"}}],
    },
    "W7": {
        "display_name": "Found By Title",
        "doi": None,
        "publication_year": 2003,
        "cited_by_count": 50,
    },
}
for k, w in WORKS.items():
    w["id"] = f"https://openalex.org/{k}"


class FakeOA:
    def __init__(self, search_down=False):
        self.calls: list[str] = []
        self.search_down = search_down

    def __call__(self, url: str) -> dict:
        self.calls.append(url)
        parsed = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        if parsed.path.startswith("/works/doi:"):
            doi = urllib.parse.unquote(parsed.path.split("doi:", 1)[1])
            return next((w for w in WORKS.values() if w["doi"] == f"https://doi.org/{doi}"), {})
        if "search" in q:
            if self.search_down:
                raise oa.SearchUnavailable("Anonymous search is paused")
            return {
                "results": [
                    w
                    for w in WORKS.values()
                    if oa.title_similarity(q["search"], w["display_name"]) > 0.5
                ]
            }
        if q.get("filter", "").startswith("openalex:"):
            ids = q["filter"].split(":", 1)[1].split("|")
            return {"results": [WORKS[i] for i in ids if i in WORKS]}
        raise AssertionError(url)


def _register(store, tmp_path, name, doi, title):
    f = tmp_path / f"{name}.txt"
    f.write_text(f"본문 {name}", encoding="utf-8")
    return IngestionAgent(store).ingest_file(f, title=title, metadata={"doi": doi}).source


def _paper_page(store, source, refs: list[str]):
    rel = f"wiki/papers/{source.source_id}"
    path = store.root / f"{rel}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"- {r}" for r in refs)
    path.write_text(
        f"---\ntype: paper\ntitle: t\n---\n# t\n\n## References\n{body}\n\n## Parsing Notes\n",
        encoding="utf-8",
    )
    source.wiki_page = rel
    from secondbrain.store import SourceRepository

    SourceRepository(store).save(source)


def test_refs_build_suggestions_and_internal_links(store, tmp_path):
    one = _register(store, tmp_path, "one", "10.1111/one", "My Paper One")
    two = _register(store, tmp_path, "two", "10.1111/two", "My Paper Two")
    fake = FakeOA()
    rep = oa.refresh_refs(store, oa.OpenAlex(fake))
    assert set(rep.fetched) == {one.source_id, two.source_id}
    assert rep.internal == [(one.source_id, two.source_id)]  # one cites two
    # W9 is cited by both of my papers → ranked first; my own paper W2 is not suggested
    assert [s["work"] for s in rep.suggestions] == ["W9", "W8"]
    assert len(rep.suggestions[0]["cited_by_mine"]) == 2
    report = oa.render_reading_report(store, rep)
    assert "Oliver (1980) **Classic Theory Paper**" in report and "내 논문 2편이 인용" in report

    n = len(fake.calls)
    oa.refresh_refs(store, oa.OpenAlex(fake))  # cached → only nothing new fetched
    assert all("/works/doi:" not in c for c in fake.calls[n:])


def test_page_references_fallback_by_doi_and_title(store, tmp_path):
    ko = _register(store, tmp_path, "ko", "10.1111/ko", "Korean Paper Without Refs")
    rep = oa.refresh_refs(store, oa.OpenAlex(FakeOA()))
    assert rep.no_references == ["Korean Paper Without Refs"]

    _paper_page(
        store,
        ko,
        [
            "Oliver (1980) | Classic Theory Paper | JMR | doi: 10.9999/a",
            "Blei (2003) | Found By Title | JMLR",
            "Nobody (1999) | 존재하지 않는 논문 | 없음",
        ],
    )
    rep = oa.refresh_refs(store, oa.OpenAlex(FakeOA()))  # page refs changed → refetch
    entry = oa.load_citations(store)["sources"][ko.source_id]
    assert entry["ref_origin"] == "page" and entry["references"] == ["W9", "W7"]
    assert rep.unresolved_refs == 1 and not rep.no_references


def test_search_outage_is_reported_not_fatal(store, tmp_path):
    ko = _register(store, tmp_path, "ko", "10.1111/ko", "Korean Paper Without Refs")
    _paper_page(
        store, ko, ["Blei (2003) | Found By Title | JMLR", "Oliver (1980) | x | y | doi: 10.9999/a"]
    )
    rep = oa.refresh_refs(store, oa.OpenAlex(FakeOA(search_down=True)))
    assert rep.search_errors == ["Anonymous search is paused"]
    assert oa.load_citations(store)["sources"][ko.source_id]["references"] == ["W9"]


def test_parse_reference_line():
    assert oa.parse_reference(
        "Lin & He (2009) | Joint Sentiment/Topic Model | CIKM | doi: 10.1145/1645953.1646003"
    ) == ("10.1145/1645953.1646003", "Joint Sentiment/Topic Model", 2009)
