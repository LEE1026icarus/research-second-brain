from __future__ import annotations

import json
from datetime import date

from secondbrain import discover as disc
from secondbrain import openalex as oa
from secondbrain.agents import IngestionAgent
from secondbrain.models import ResearchProject
from secondbrain.store import ProjectRepository


def W(i, title, doi=None, cited=0):
    return {
        "id": f"https://openalex.org/{i}",
        "display_name": title,
        "doi": doi and f"https://doi.org/{doi}",
        "publication_year": 2026,
        "publication_date": "2026-08-01",
        "cited_by_count": cited,
        "authorships": [],
    }


class Fake:
    search_errors: list = []

    def citing(self, work_id, since=None, per_page=10):
        return {
            "W1": [
                W("N1", "Topic modeling of tourist reviews"),
                W("N2", "Stock prices", cited=50),
                W("W2", "My own paper"),
            ],
            "W5": [
                W("N1", "Topic modeling of tourist reviews"),
                W("N3", "Another citing paper", doi="10.1111/mine"),
            ],
        }.get(work_id, [])

    def search_recent(self, q, since, per_page=10):
        return [W("N4", "Dissatisfaction in tourism")]

    def work_by_doi(self, doi):
        return {"id": "https://openalex.org/W5"} if doi == "10.1145/x" else None


def test_discover_ranks_skips_known_and_remembers_seen(store, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("본문", encoding="utf-8")
    s1 = IngestionAgent(store).ingest_file(f, metadata={"doi": "10.1111/mine"}).source
    oa.save_citations(
        store, {"sources": {s1.source_id: {"openalex": "W1"}, "x": {"openalex": "W2"}}, "works": {}}
    )
    ProjectRepository(store).save(
        ResearchProject(
            title="P", keywords=["tourist dissatisfaction"], important_references=["10.1145/x"]
        )
    )
    res = disc.discover(store, Fake(), today=date(2026, 9, 30))
    ids = [h.work for h in res.hits]
    assert ids[0] == "N1"  # cited-by-library + project reference + title keyword
    assert "W2" not in ids and "N3" not in ids  # already in library (by OpenAlex id / DOI)
    assert set(ids) == {"N1", "N2", "N4"} and res.skipped_known == 2
    assert res.since == "2026-07-02"
    assert "제목에 프로젝트 키워드 포함" in " ".join(res.hits[0].reasons)
    assert "**Topic modeling of tourist reviews**" in disc.render(res)

    again = disc.discover(store, Fake(), today=date(2026, 9, 30))
    assert again.hits == []  # already shown
    assert len(disc.discover(store, Fake(), include_seen=True).hits) == 3
    state = json.loads((store.kg / "discover.json").read_text())
    assert state["seed_ids"] == {"10.1145/x": "W5"}
