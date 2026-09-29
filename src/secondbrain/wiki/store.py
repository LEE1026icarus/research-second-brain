"""Reading and writing wiki pages on disk (spec §6, §22, §23)."""

from __future__ import annotations

from pathlib import Path

from slugify import slugify

from ..config import StoreConfig
from ..models import WikiPageType
from .page import WikiPage


class WikiStore:
    """Locates, loads, and saves markdown pages under ``store/wiki/``."""

    def __init__(self, store: StoreConfig) -> None:
        self.store = store

    def path_for(self, page_type: WikiPageType, name: str) -> Path:
        return self.store.wiki / page_type.value / f"{slugify(name)}.md"

    def rel_path(self, page_type: WikiPageType, name: str) -> str:
        return str(self.path_for(page_type, name).relative_to(self.store.root))

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
