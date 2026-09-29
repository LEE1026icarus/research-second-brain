"""Research idea model produced by the Idea Engine (spec §14, §15, §16, §19)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .enums import IdeaKind, IdeaStatus
from .provenance import Provenance


class Idea(BaseModel):
    """A research idea candidate.

    Ideas are kept strictly separate from confirmed wiki knowledge (spec §15)
    and must always cite their supporting sources (spec §19). The
    evidence/interpretation/speculation split (spec §19) is captured in
    dedicated fields so a reader can see what is grounded vs. speculative.
    """

    idea_id: str = Field(default_factory=lambda: f"idea-{uuid.uuid4().hex[:12]}")
    kind: IdeaKind = IdeaKind.EMERGING
    status: IdeaStatus = IdeaStatus.DETECTED
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)

    title: str

    # spec §14 template fields
    observed_connection: str | None = None
    why_it_matters: str | None = None
    existing_evidence: str | None = None
    research_gap: str | None = None
    research_question: str | None = None
    hypothesis: str | None = None
    method: str | None = None
    data: str | None = None
    expected_contribution: str | None = None
    risks: str | None = None

    # spec §19: explicit epistemic separation
    interpretation: str | None = None
    speculation: str | None = None

    supporting_sources: list[Provenance] = Field(default_factory=list)
    confidence: float = Field(default=0.3, ge=0.0, le=1.0)

    # Link back to the project this idea is relevant to (spec §29)
    related_project_id: str | None = None
