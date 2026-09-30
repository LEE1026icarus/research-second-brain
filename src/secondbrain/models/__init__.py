"""Core data models for the Research Second Brain.

The models mirror the spec's three-layer separation (spec §2.1):

* :class:`Source`          -> raw + metadata bookkeeping
* ``structured/<id>.md``   -> parsed full text with page markers (for the LLM agent)
* wiki pages (markdown)    -> written by the LLM agent following AGENTS.md

plus the knowledge graph (:class:`Node`, :class:`Edge`, :class:`Claim`),
research :class:`Idea` candidates, and personal :class:`ResearchProject` context.
"""

from .claim import Claim
from .enums import (
    SOURCE_TYPE_TO_EVIDENCE,
    AccessStatus,
    CompileStatus,
    Direction,
    EdgeType,
    Epistemic,
    EvidenceLevel,
    IdeaKind,
    IdeaStatus,
    KnowledgeLayer,
    NodeType,
    Significance,
    SourceType,
    UpdateEffect,
    WikiPageType,
)
from .graph import Edge, Node
from .idea import Idea
from .project import ResearchProject
from .provenance import Provenance
from .source import Source

__all__ = [
    "AccessStatus",
    "CompileStatus",
    "Claim",
    "Direction",
    "Edge",
    "EdgeType",
    "Epistemic",
    "EvidenceLevel",
    "Idea",
    "IdeaKind",
    "IdeaStatus",
    "KnowledgeLayer",
    "Node",
    "NodeType",
    "Provenance",
    "ResearchProject",
    "Significance",
    "Source",
    "SourceType",
    "SOURCE_TYPE_TO_EVIDENCE",
    "UpdateEffect",
    "WikiPageType",
]
