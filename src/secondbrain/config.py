"""Filesystem layout and configuration for the Second Brain store.

The store is intentionally a plain directory tree so the wiki is
Obsidian-compatible (spec §23) and the whole knowledge base is
Git-versionable (spec §22).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_STORE_ENV = "SECOND_BRAIN_STORE"


@dataclass(frozen=True)
class StoreConfig:
    """Resolved paths for every part of the knowledge store."""

    root: Path

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def structured(self) -> Path:
        return self.root / "structured"

    @property
    def wiki(self) -> Path:
        return self.root / "wiki"

    @property
    def kg(self) -> Path:
        return self.root / "kg"

    @property
    def ideas(self) -> Path:
        return self.root / "ideas"

    @property
    def index(self) -> Path:
        return self.root / "index"

    @property
    def sources_file(self) -> Path:
        return self.index / "sources.json"

    @property
    def graph_file(self) -> Path:
        return self.kg / "graph.json"

    @property
    def index_md(self) -> Path:
        """Content catalog the agent reads first (Karpathy LLM-Wiki pattern)."""
        return self.root / "index.md"

    @property
    def log_md(self) -> Path:
        """Append-only history of ingests, queries, lint passes."""
        return self.root / "log.md"

    @property
    def projects_file(self) -> Path:
        return self.index / "projects.json"

    def ensure(self) -> None:
        """Create the full directory tree if it does not exist."""
        wiki_types = [
            "papers", "sources", "concepts", "theories", "methods", "datasets",
            "researchers", "organizations", "technologies", "topics",
            "overviews", "questions", "synthesis",
        ]
        idea_kinds = [
            "emerging", "research-questions", "hypotheses",
            "method-transfer", "domain-transfer", "rejected",
        ]
        for d in (self.raw, self.structured, self.kg, self.index):
            d.mkdir(parents=True, exist_ok=True)
        for t in wiki_types:
            (self.wiki / t).mkdir(parents=True, exist_ok=True)
        for k in idea_kinds:
            (self.ideas / k).mkdir(parents=True, exist_ok=True)


def resolve_store(explicit: str | os.PathLike[str] | None = None) -> StoreConfig:
    """Resolve the store root from an explicit path, env var, or ``./store``."""
    if explicit is not None:
        root = Path(explicit)
    elif os.environ.get(DEFAULT_STORE_ENV):
        root = Path(os.environ[DEFAULT_STORE_ENV])
    else:
        root = Path.cwd() / "store"
    return StoreConfig(root=root.expanduser().resolve())
