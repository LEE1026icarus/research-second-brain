"""Section skeletons for each wiki page type (spec §8, §9).

New pages start with the canonical section headings from the spec so that
incremental updates always have a well-known place to attach content.
"""

from __future__ import annotations

from ..models import WikiPageType

# Concept page sections (spec §9).
CONCEPT_SECTIONS = [
    "Definition",
    "Theoretical Origin",
    "Related Constructs",
    "Measurement",
    "Common Antecedents",
    "Common Outcomes",
    "Established Findings",
    "Conflicting Findings",
    "Boundary Conditions",
    "Applications",
    "Related Papers",
    "Open Questions",
]

# Overview page sections (spec §8).
OVERVIEW_SECTIONS = [
    "Current Understanding",
    "Major Theories",
    "Important Variables",
    "Established Findings",
    "Conflicting Findings",
    "Recent Developments",
    "Research Gaps",
    "Open Questions",
    "Key Papers",
]

# Paper page sections (mirrors the §5 extraction structure).
PAPER_SECTIONS = [
    "Summary",
    "Research Context",
    "Research Design",
    "Variables",
    "Analysis",
    "Results",
    "Discussion",
    "Claims",
    "Related Pages",
    "Provenance",
]

QUESTION_SECTIONS = [
    "Question",
    "Why It Is Open",
    "Related Concepts",
    "Related Papers",
    "Status",
]

THEORY_SECTIONS = [
    "Definition",
    "Core Propositions",
    "Key Constructs",
    "Applications",
    "Established Findings",
    "Conflicting Findings",
    "Related Papers",
    "Open Questions",
]

METHOD_SECTIONS = [
    "Description",
    "Typical Use Cases",
    "Evaluation Metrics",
    "Known Limitations",
    "Applications",
    "Related Papers",
]

_GENERIC = ["Summary", "Related Pages", "Related Papers"]

_SECTIONS: dict[WikiPageType, list[str]] = {
    WikiPageType.CONCEPT: CONCEPT_SECTIONS,
    WikiPageType.OVERVIEW: OVERVIEW_SECTIONS,
    WikiPageType.PAPER: PAPER_SECTIONS,
    WikiPageType.QUESTION: QUESTION_SECTIONS,
    WikiPageType.THEORY: THEORY_SECTIONS,
    WikiPageType.METHOD: METHOD_SECTIONS,
}


def sections_for(page_type: WikiPageType) -> list[str]:
    return _SECTIONS.get(page_type, _GENERIC)
