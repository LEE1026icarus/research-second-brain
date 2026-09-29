"""Reading and writing wiki pages on disk (spec §6, §22, §23)."""

from __future__ import annotations

from pathlib import Path

from slugify import slugify

from ..config import StoreConfig
from ..models import WikiPageType
from .page import WikiPage, wikilink


class WikiStore:
    """Locates, loads, and saves markdown pages under ``store/wiki/``."""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store

    @staticmethod
    def slug(name: str) -> str:
        # allow_unicode keeps Hangul readable in filenames (Obsidian handles UTF-8 names).
        return slugify(name, allow_unicode=True, max_length=120, word_boundary=True) or "untitled"

    def path_for(self, page_type: WikiPageType, name: str) -> Path:
        return self.store.wiki / page_type.value / f"{self.slug(name)}.md"

    def rel_path(self, page_type: WikiPageType, name: str) -> str:
        return str(self.path_for(page_type, name).relative_to(self.store.root))

    def link(self, page_type: WikiPageType, name: str, alias: str | None = None) -> str:
        """Unambiguous Obsidian wikilink, e.g. ``[[concepts/국내-여행|국내 여행]]``.

        The target is the path relative to the wiki vault root (``store/wiki``),
        so a concept and an overview with the same name never collide.
        """
        return wikilink(f"{page_type.value}/{self.slug(name)}", alias or name)

    def exists(self, page_type: WikiPageType, name: str) -> bool:
        return self.path_for(page_type, name).exists()

    def load(self, page_type: WikiPageType, name: str) -> WikiPage | None:
        path = self.path_for(page_type, name)
        if not path.exists():
            return None
        return WikiPage.parse(path.read_text(encoding="utf-8"))

    def save(self, page_type: WikiPageType, name: str, page: WikiPage) -> Path:
        path = self.path_for(page_type, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page.render(), encoding="utf-8")
        return path

    def all_paths(self) -> list[Path]:
        return sorted(self.store.wiki.rglob("*.md"))
