"""End-to-end ingest pipeline (spec §34).

    New source -> collect -> preserve raw -> extract structured info
    -> compare with existing wiki -> update knowledge -> (KG / synapse / ideas)

Phase 1 wires the first five stages. Later phases plug the Graph, Synapse, and
Idea agents into :meth:`IngestPipeline.run` after wiki integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..agents.extraction import ExtractionAgent, Extractor
from ..agents.ingestion import IngestionAgent
from ..config import StoreConfig
from ..models import PaperExtraction, Source, SourceType
from ..wiki import WikiAgent, WikiUpdate


@dataclass
class PipelineResult:
    source: Source
    extraction: PaperExtraction | None
    wiki_update: WikiUpdate | None
    was_duplicate: bool


class IngestPipeline:
    def __init__(self, store: StoreConfig, extractor: Extractor | None = None) -> None:
        self.store = store
        self.store.ensure()
        self.ingestion = IngestionAgent(store)
        self.extraction = ExtractionAgent(store, extractor)
        self.wiki = WikiAgent(store)

    def run(
        self,
        path: str | Path,
        *,
        source_type: SourceType | None = None,
        title: str | None = None,
    ) -> PipelineResult:
        ingest = self.ingestion.ingest_file(path, source_type=source_type, title=title)
        if ingest.is_duplicate:
            return PipelineResult(ingest.source, None, None, was_duplicate=True)

        extraction = self.extraction.extract(ingest.source)
        wiki_update = self.wiki.integrate(ingest.source, extraction)
        return PipelineResult(ingest.source, extraction, wiki_update, was_duplicate=False)
