"""Deterministic helpers the LLM agent calls (spec §17).

Understanding work (extraction, wiki writing, synthesis, ideas) is done by the
LLM agent following ``AGENTS.md``. Code here only does what must be exact:
registration, dedup, raw preservation, and text parsing.
"""

from .ingestion import IngestionAgent, IngestResult

__all__ = ["IngestionAgent", "IngestResult"]
