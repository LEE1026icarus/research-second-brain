"""Keyword search over the wiki (spec §25 Keyword Search).

Phase 1 provides exact keyword search across page titles and bodies. Semantic
(embedding) and graph search are introduced in later phases behind the same
:func:`search` entry point.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import StoreConfig


@dataclass
class SearchHit:
    path: str
    title: str
    score: int
    snippet: str


def keyword_search(store: StoreConfig, query: str, limit: int = 20) -> list[SearchHit]:
    terms = [t.lower() for t in query.split() if t.strip()]
    hits: list[SearchHit] = []
    for path in sorted(store.wiki.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        low = text.lower()
        score = sum(low.count(t) for t in terms)
        if score == 0:
            continue
        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        snippet = _snippet(text, terms)
        hits.append(
            SearchHit(
                path=str(path.relative_to(store.root)),
                title=title,
                score=score,
                snippet=snippet,
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def _snippet(text: str, terms: list[str], width: int = 120) -> str:
    low = text.lower()
    for t in terms:
        idx = low.find(t)
        if idx != -1:
            start = max(0, idx - width // 2)
            return " ".join(text[start : start + width].split())
    return ""
