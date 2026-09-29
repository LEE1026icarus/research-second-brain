from __future__ import annotations

from secondbrain.agents.extraction import HeuristicPaperExtractor
from secondbrain.digest import build_digest
from secondbrain.models import Source, SourceType
from secondbrain.pipeline import IngestPipeline
from secondbrain.search import keyword_search


def test_extractor_pulls_fields():
    src = Source(source_id="s1", source_type=SourceType.JOURNAL_ARTICLE, title="T")
    from tests.conftest import SAMPLE_TEXT

    ex = HeuristicPaperExtractor().extract(src, SAMPLE_TEXT)
    assert ex.doi == "10.1234/jis.2023.0456"
    assert ex.research_questions
    assert ex.methodology
    assert ex.future_work  # drives open-question detection
    assert "Technology Acceptance Model (TAM)" in ex.theoretical_background
    assert "Structural Equation Modeling (SEM)" in ex.analysis_methods


def test_pipeline_creates_wiki_and_preserves_raw(store, sample_file):
    result = IngestPipeline(store).run(sample_file, title="Sample Paper")
    assert not result.was_duplicate
    # Raw preserved and never mutated (copied under store/raw).
    assert (store.root / result.source.local_file).exists()
    # Paper page created.
    assert (store.root / result.wiki_update.paper_page).exists()
    # Provenance is traceable back to the source id.
    page_text = (store.root / result.wiki_update.paper_page).read_text()
    assert result.source.source_id in page_text


def test_pipeline_detects_duplicates(store, sample_file):
    pipe = IngestPipeline(store)
    first = pipe.run(sample_file)
    second = pipe.run(sample_file)
    assert not first.was_duplicate
    assert second.was_duplicate


def test_search_and_digest(store, sample_file):
    IngestPipeline(store).run(sample_file, title="Sample Paper")
    hits = keyword_search(store, "perceived usefulness")
    assert hits and hits[0].score > 0
    d = build_digest(store)
    assert d.total_sources == 1
    assert d.wiki_pages.get("papers") == 1
    assert d.open_questions >= 1
