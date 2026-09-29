"""Knowledge Graph node and edge models (spec §10, §11)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from .enums import EdgeType, NodeType
from .provenance import Provenance


class Node(BaseModel):
    """A typed entity in the knowledge graph (spec §10)."""

    node_id: str = Field(default_factory=lambda: f"node-{uuid.uuid4().hex[:12]}")
    node_type: NodeType
    label: str
    aliases: list[str] = Field(default_factory=list)
    # Sources that mention/support this node, for traceability.
    source_ids: list[str] = Field(default_factory=list)
    wiki_page: str | None = Field(default=None, description="Relative path of the wiki page.")

    def key(self) -> str:
        """Stable identity key used to merge duplicate nodes."""
        return f"{self.node_type.value}:{' '.join(self.label.lower().split())}"


class Edge(BaseModel):
    """A typed, meaningful relationship between two nodes (spec §11)."""

    edge_id: str = Field(default_factory=lambda: f"edge-{uuid.uuid4().hex[:12]}")
    source: str = Field(..., description="node_id of the tail.")
    target: str = Field(..., description="node_id of the head.")
    edge_type: EdgeType
    weight: float = Field(default=1.0, ge=0.0)
    provenance: list[Provenance] = Field(default_factory=list)

    def key(self) -> str:
        return f"{self.source}-{self.edge_type.value}-{self.target}"
