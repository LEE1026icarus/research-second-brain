"""Personal research project / context model (spec §29)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ResearchProject(BaseModel):
    """A user's own research project used to personalize idea generation.

    The Idea Engine can prioritize connections relevant to registered
    projects (spec §29).
    """

    project_id: str = Field(default_factory=lambda: f"proj-{uuid.uuid4().hex[:8]}")
    title: str
    research_question: str | None = None
    keywords: list[str] = Field(default_factory=list)
    theory: list[str] = Field(default_factory=list)
    method: list[str] = Field(default_factory=list)
    dataset: list[str] = Field(default_factory=list)
    current_stage: str | None = None
    important_references: list[str] = Field(default_factory=list)
    research_interests: list[str] = Field(default_factory=list)
