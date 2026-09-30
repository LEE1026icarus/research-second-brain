"""Persistence for sources, the graph, and projects.

Everything is stored as plain JSON so the whole knowledge base stays
diff-friendly and Git-versionable (spec §22). No database is required for
Phase 1; the interfaces here are deliberately narrow so a later phase can
swap in a real graph/embedding store without touching callers.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import StoreConfig
from ..models import Edge, Node, ResearchProject, Source


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


class SourceRepository:
    """Stores :class:`Source` records in ``index/sources.json``."""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store

    def all(self) -> list[Source]:
        raw = _read_json(self.store.sources_file, [])
        return [Source.model_validate(r) for r in raw]

    def get(self, source_id: str) -> Source | None:
        return next((s for s in self.all() if s.source_id == source_id), None)

    def save(self, source: Source) -> None:
        items = self.all()
        items = [s for s in items if s.source_id != source.source_id]
        items.append(source)
        _write_json(self.store.sources_file, [s.model_dump() for s in items])

    def find_duplicate(self, candidate: Source) -> Source | None:
        """Return an existing source that matches on any strong fingerprint (spec §21)."""
        cand = candidate.fingerprints()
        for existing in self.all():
            if existing.source_id == candidate.source_id:
                continue
            ex = existing.fingerprints()
            # DOI / file hash / URL are strong identity signals.
            for key in ("doi", "file_hash", "url"):
                if key in cand and key in ex and cand[key] == ex[key]:
                    return existing
            # Exact normalized title + same first author/year is also a match.
            if (
                "title" in cand
                and cand.get("title") == ex.get("title")
                and candidate.author[:1] == existing.author[:1]
            ):
                return existing
        return None


class GraphRepository:
    """Stores the knowledge graph in ``kg/graph.json`` (spec §10, §11)."""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store

    def load(self) -> tuple[list[Node], list[Edge]]:
        raw = _read_json(self.store.graph_file, {"nodes": [], "edges": []})
        nodes = [Node.model_validate(n) for n in raw.get("nodes", [])]
        edges = [Edge.model_validate(e) for e in raw.get("edges", [])]
        return nodes, edges

    def save(self, nodes: list[Node], edges: list[Edge]) -> None:
        _write_json(
            self.store.graph_file,
            {
                "nodes": [n.model_dump() for n in nodes],
                "edges": [e.model_dump() for e in edges],
            },
        )


class ProjectRepository:
    """Stores personal :class:`ResearchProject` context (spec §29)."""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store

    def all(self) -> list[ResearchProject]:
        return [ResearchProject.model_validate(r) for r in _read_json(self.store.projects_file, [])]

    def save(self, project: ResearchProject) -> None:
        items = [p for p in self.all() if p.project_id != project.project_id]
        items.append(project)
        _write_json(self.store.projects_file, [p.model_dump() for p in items])
