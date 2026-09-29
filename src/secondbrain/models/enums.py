"""Controlled vocabularies used across the Second Brain.

These enums encode the spec's fixed vocabularies (source types, evidence
levels, update effects, relationship types, idea lifecycle) so the whole
system speaks one language and values are validated at the boundary.
"""

from __future__ import annotations

from enum import Enum


class SourceType(str, Enum):
    """Kinds of knowledge sources the system ingests (spec §3.1)."""

    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    PREPRINT = "preprint"
    GOVERNMENT_REPORT = "government_report"
    RESEARCH_INSTITUTE_REPORT = "research_institute_report"
    INDUSTRY_REPORT = "industry_report"
    NEWS = "news"
    WEBPAGE = "webpage"
    PATENT = "patent"
    DATASET = "dataset"
    PERSONAL_NOTE = "personal_note"
    PRESENTATION = "presentation"
    BLOG = "blog"
    OTHER = "other"


class EvidenceLevel(str, Enum):
    """Trust tiers for a source (spec §20).

    Ordered from strongest to weakest so consumers can compare with
    ``EvidenceLevel.rank``.
    """

    PEER_REVIEWED = "peer_reviewed"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    GOVERNMENT_REPORT = "government_report"
    RESEARCH_INSTITUTE_REPORT = "research_institute_report"
    INDUSTRY_REPORT = "industry_report"
    NEWS = "news"
    BLOG = "blog"
    PERSONAL_NOTE = "personal_note"
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        """Higher rank == stronger evidence."""
        order = [
            EvidenceLevel.UNKNOWN,
            EvidenceLevel.PERSONAL_NOTE,
            EvidenceLevel.BLOG,
            EvidenceLevel.NEWS,
            EvidenceLevel.INDUSTRY_REPORT,
            EvidenceLevel.RESEARCH_INSTITUTE_REPORT,
            EvidenceLevel.GOVERNMENT_REPORT,
            EvidenceLevel.PREPRINT,
            EvidenceLevel.CONFERENCE,
            EvidenceLevel.PEER_REVIEWED,
        ]
        return order.index(self)


# Default mapping from a source type to an evidence level.
SOURCE_TYPE_TO_EVIDENCE: dict[SourceType, EvidenceLevel] = {
    SourceType.JOURNAL_ARTICLE: EvidenceLevel.PEER_REVIEWED,
    SourceType.CONFERENCE_PAPER: EvidenceLevel.CONFERENCE,
    SourceType.PREPRINT: EvidenceLevel.PREPRINT,
    SourceType.GOVERNMENT_REPORT: EvidenceLevel.GOVERNMENT_REPORT,
    SourceType.RESEARCH_INSTITUTE_REPORT: EvidenceLevel.RESEARCH_INSTITUTE_REPORT,
    SourceType.INDUSTRY_REPORT: EvidenceLevel.INDUSTRY_REPORT,
    SourceType.NEWS: EvidenceLevel.NEWS,
    SourceType.WEBPAGE: EvidenceLevel.BLOG,
    SourceType.PATENT: EvidenceLevel.GOVERNMENT_REPORT,
    SourceType.DATASET: EvidenceLevel.RESEARCH_INSTITUTE_REPORT,
    SourceType.PERSONAL_NOTE: EvidenceLevel.PERSONAL_NOTE,
    SourceType.PRESENTATION: EvidenceLevel.INDUSTRY_REPORT,
    SourceType.BLOG: EvidenceLevel.BLOG,
    SourceType.OTHER: EvidenceLevel.UNKNOWN,
}


class AccessStatus(str, Enum):
    """Whether we hold the full text or only metadata (spec §3.2)."""

    FULL_TEXT = "full_text"
    METADATA_ONLY = "metadata_only"
    PENDING = "pending"


class UpdateEffect(str, Enum):
    """How a new source affects an existing piece of knowledge (spec §2.2)."""

    STRENGTHEN = "strengthen"
    NARROW = "narrow"
    EXTEND = "extend"
    CONTRADICT = "contradict"
    REPLACE = "replace"
    UNCHANGED = "unchanged"


class KnowledgeLayer(str, Enum):
    """The three managed layers (spec §2.1)."""

    RAW = "raw"
    STRUCTURED = "structured"
    WIKI = "wiki"


class Epistemic(str, Enum):
    """Separation of fact, synthesis, and speculation (spec §4, §19)."""

    SOURCE_FACT = "source_fact"
    SYNTHESIS = "synthesis"
    IDEA = "idea"


class NodeType(str, Enum):
    """Knowledge graph node types (spec §10)."""

    PAPER = "paper"
    CONCEPT = "concept"
    THEORY = "theory"
    METHOD = "method"
    DATASET = "dataset"
    VARIABLE = "variable"
    FINDING = "finding"
    CLAIM = "claim"
    RESEARCHER = "researcher"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    RESEARCH_QUESTION = "research_question"


class EdgeType(str, Enum):
    """Explicit, meaningful relationship types (spec §11)."""

    USES = "uses"
    EXTENDS = "extends"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    TESTS = "tests"
    PREDICTS = "predicts"
    MODERATES = "moderates"
    MEDIATES = "mediates"
    MEASURES = "measures"
    APPLIES_TO = "applies_to"
    BASED_ON = "based_on"
    DERIVED_FROM = "derived_from"
    SIMILAR_TO = "similar_to"
    CITES = "cites"
    USES_DATASET = "uses_dataset"
    USES_METHOD = "uses_method"


class Direction(str, Enum):
    """Direction of an effect in a claim (spec §12)."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NONE = "none"
    MIXED = "mixed"
    UNSPECIFIED = "unspecified"


class Significance(str, Enum):
    """Statistical significance of a claim (spec §12)."""

    SIGNIFICANT = "significant"
    NOT_SIGNIFICANT = "not_significant"
    UNSPECIFIED = "unspecified"


class WikiPageType(str, Enum):
    """Wiki page categories (spec §6)."""

    PAPER = "papers"
    CONCEPT = "concepts"
    THEORY = "theories"
    METHOD = "methods"
    DATASET = "datasets"
    RESEARCHER = "researchers"
    ORGANIZATION = "organizations"
    TECHNOLOGY = "technologies"
    TOPIC = "topics"
    OVERVIEW = "overviews"
    QUESTION = "questions"


class IdeaKind(str, Enum):
    """Idea folders (spec §15)."""

    EMERGING = "emerging"
    RESEARCH_QUESTION = "research-questions"
    HYPOTHESIS = "hypotheses"
    METHOD_TRANSFER = "method-transfer"
    DOMAIN_TRANSFER = "domain-transfer"
    REJECTED = "rejected"


class IdeaStatus(str, Enum):
    """Idea lifecycle states (spec §16)."""

    DETECTED = "detected"
    REVIEWING = "reviewing"
    PROMISING = "promising"
    DEVELOPING = "developing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONVERTED_TO_PROJECT = "converted_to_project"
