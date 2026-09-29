"""Digest generation (spec §27).

Summarizes the current state of the knowledge base: source counts, wiki page
counts by type, open questions, and detected contradictions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .config import StoreConfig
from .store import SourceRepository


@dataclass
class Digest:
    total_sources: int = 0
    sources_by_type: dict[str, int] = field(default_factory=dict)
    wiki_pages: dict[str, int] = field(default_factory=dict)
    open_questions: int = 0
    contradictions: int = 0

    def render(self) -> str:
        lines = ["# Second Brain Digest", ""]
        lines.append(f"**Total sources:** {self.total_sources}")
        for t, n in sorted(self.sources_by_type.items()):
            lines.append(f"- {t}: {n}")
        lines.append("")
        lines.append("**Wiki pages:**")
        for t, n in sorted(self.wiki_pages.items()):
            lines.append(f"- {t}: {n}")
        lines.append("")
        lines.append(f"**Open questions:** {self.open_questions}")
        lines.append(f"**Contradictions flagged:** {self.contradictions}")
        return "\n".join(lines)


def build_digest(store: StoreConfig) -> Digest:
    d = Digest()
    sources = SourceRepository(store).all()
    d.total_sources = len(sources)
    d.sources_by_type = dict(Counter(s.source_type.value for s in sources))

    for type_dir in sorted(p for p in store.wiki.iterdir() if p.is_dir()):
        count = len(list(type_dir.glob("*.md")))
        if count:
            d.wiki_pages[type_dir.name] = count

    d.open_questions = len(list((store.wiki / "questions").glob("*.md")))
    # A contradiction is any concept page with a non-empty "Conflicting Findings".
    for page in (store.wiki / "concepts").glob("*.md"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        if "## Conflicting Findings" in text:
            body = text.split("## Conflicting Findings", 1)[1]
            body = body.split("\n## ", 1)[0]
            if body.strip():
                d.contradictions += 1
    return d
