"""Provenance primitives that make every claim traceable to a source (spec §2.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """A pointer back to the exact place a piece of knowledge came from.

    Every synthesized statement in the wiki and every claim in the graph
    should carry at least one Provenance so it can be traced to a raw source
    (spec §2.3).
    """

    source_id: str = Field(..., description="ID of the source this came from.")
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    page: str | None = Field(default=None, description="Page or page range, e.g. '12-14'.")
    section: str | None = None
    quote: str | None = Field(default=None, description="Verbatim quote supporting the claim.")

    def short_ref(self) -> str:
        """A compact human-readable citation like 'Smith (2021)'."""
        who = self.authors[0].split(",")[0] if self.authors else (self.title or self.source_id)
        year = f" ({self.year})" if self.year else ""
        return f"{who}{year}"
