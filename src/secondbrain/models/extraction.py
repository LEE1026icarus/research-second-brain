"""Structured extraction from a source (the 'Structured Source' layer, spec §2.1, §5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .claim import Claim
from .provenance import Provenance


class PaperExtraction(BaseModel):
    """Paper-specific structured information (spec §5).

    Every field is optional: extraction is best-effort and we never fabricate
    values that are not present in the source (spec §18). Missing data stays
    ``None`` rather than being guessed.
    """

    source_id: str

    # Bibliographic
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    doi: str | None = None

    # Research context
    purpose: str | None = None
    research_questions: list[str] = Field(default_factory=list)
    theoretical_background: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)

    # Research design
    methodology: str | None = None
    research_design: str | None = None
    data: str | None = None
    sample: str | None = None
    study_period: str | None = None
    unit_of_analysis: str | None = None

    # Variables
    independent_variables: list[str] = Field(default_factory=list)
    dependent_variables: list[str] = Field(default_factory=list)
    mediating_variables: list[str] = Field(default_factory=list)
    moderating_variables: list[str] = Field(default_factory=list)
    control_variables: list[str] = Field(default_factory=list)

    # Analysis
    analysis_methods: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    algorithms: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)

    # Results
    key_findings: list[str] = Field(default_factory=list)
    significant_relationships: list[str] = Field(default_factory=list)
    nonsignificant_relationships: list[str] = Field(default_factory=list)

    # Discussion
    theoretical_contributions: list[str] = Field(default_factory=list)
    practical_contributions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)

    # Claim-level structured knowledge (spec §12)
    claims: list[Claim] = Field(default_factory=list)

    # Raw text captured for later re-processing (kept out of the wiki layer)
    abstract: str | None = None

    def self_provenance(self) -> Provenance:
        """Provenance object pointing at this paper (document-level)."""
        return Provenance(
            source_id=self.source_id,
            title=self.title,
            authors=self.authors,
            year=self.year,
            doi=self.doi,
        )
