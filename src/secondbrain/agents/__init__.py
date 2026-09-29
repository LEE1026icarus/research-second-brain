"""Logical agent roles (spec §17).

Phase 1 implements the first two roles fully:

* :class:`IngestionAgent` -- collect and register sources.
* :class:`ExtractionAgent` -- pull structured info from raw text.

The Wiki Agent lives in :mod:`secondbrain.wiki`. Graph / Synapse / Idea /
Reviewer agents are introduced in later phases against the same models.
"""

from .extraction import ExtractionAgent, Extractor, HeuristicPaperExtractor
from .ingestion import IngestionAgent, IngestResult

__all__ = [
    "ExtractionAgent",
    "Extractor",
    "HeuristicPaperExtractor",
    "IngestionAgent",
    "IngestResult",
]
