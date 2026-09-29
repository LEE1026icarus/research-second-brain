"""Claim-level knowledge: the finest structured unit (spec §12)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from .enums import Direction, Significance
from .provenance import Provenance


class Claim(BaseModel):
    """A single relationship asserted by a source.

    Example (spec §12)::

        perceived usefulness --(positive)--> adoption intention

    Claims are the atoms the Knowledge Graph and Synapse Engine reason over.
    Each carries its own provenance and confidence so the system can weigh
    conflicting evidence (spec §2.4, §18).
    """

    claim_id: str = Field(default_factory=lambda: f"claim-{uuid.uuid4().hex[:12]}")
    subject: str = Field(..., description="The antecedent / cause / independent construct.")
    predicate: str = Field(default="relates_to", description="Relationship verb, e.g. 'predicts'.")
    object: str = Field(..., description="The outcome / dependent construct.")

    direction: Direction = Direction.UNSPECIFIED
    significance: Significance = Significance.UNSPECIFIED
    effect_size: str | None = None

    context: str | None = None
    population: str | None = None
    method: str | None = None

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    provenance: Provenance

    def signature(self) -> str:
        """Normalized subject→object signature for contradiction detection."""
        s = " ".join(self.subject.lower().split())
        o = " ".join(self.object.lower().split())
        return f"{s}=>{o}"

    def one_line(self) -> str:
        arrow = {
            Direction.POSITIVE: "→(+)",
            Direction.NEGATIVE: "→(-)",
            Direction.NONE: "→(0)",
            Direction.MIXED: "→(±)",
            Direction.UNSPECIFIED: "→",
        }[self.direction]
        return f"{self.subject} {arrow} {self.object}"
