"""Ingestion Agent: collect and register a source (spec §17, §3, §21).

Responsibilities:
* preserve the raw bytes untouched under ``store/raw/`` (spec §2.1),
* compute a file hash and detect duplicates (spec §21),
* create a :class:`Source` record with metadata + evidence level.

The agent never edits an original file.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from ..config import StoreConfig
from ..models import (
    SOURCE_TYPE_TO_EVIDENCE,
    AccessStatus,
    EvidenceLevel,
    Source,
    SourceType,
)
from ..store import SourceRepository

# Map file extensions to a default source type (spec §3.1).
_EXT_TYPE = {
    ".pdf": SourceType.JOURNAL_ARTICLE,
    ".docx": SourceType.OTHER,
    ".pptx": SourceType.PRESENTATION,
    ".xlsx": SourceType.DATASET,
    ".html": SourceType.WEBPAGE,
    ".htm": SourceType.WEBPAGE,
    ".md": SourceType.PERSONAL_NOTE,
    ".txt": SourceType.PERSONAL_NOTE,
}


class IngestResult:
    def __init__(self, source: Source, *, duplicate_of: Source | None = None) -> None:
        self.source = source
        self.duplicate_of = duplicate_of

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None


class IngestionAgent:
    def __init__(self, store: StoreConfig) -> None:
        self.store = store
        self.sources = SourceRepository(store)

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()

    def ingest_file(
        self,
        path: str | Path,
        *,
        source_type: SourceType | None = None,
        title: str | None = None,
    ) -> IngestResult:
        """Register a local file as a source, preserving the raw bytes.

        If an identical file (or same DOI/URL) already exists it is treated as
        a duplicate and no second copy is stored (spec §21).
        """
        src_path = Path(path).expanduser().resolve()
        if not src_path.is_file():
            raise FileNotFoundError(src_path)

        file_hash = self._hash_file(src_path)
        stype = source_type or _EXT_TYPE.get(src_path.suffix.lower(), SourceType.OTHER)
        source_id = f"src-{uuid.uuid4().hex[:12]}"

        candidate = Source(
            source_id=source_id,
            source_type=stype,
            title=title or src_path.stem,
            local_file=None,
            file_hash=file_hash,
            access_status=AccessStatus.FULL_TEXT,
            evidence_level=SOURCE_TYPE_TO_EVIDENCE.get(stype, EvidenceLevel.UNKNOWN),
            peer_reviewed=stype == SourceType.JOURNAL_ARTICLE or None,
        )

        dup = self.sources.find_duplicate(candidate)
        if dup is not None:
            return IngestResult(dup, duplicate_of=dup)

        # Preserve raw bytes: copy (never move/modify the original).
        self.store.raw.mkdir(parents=True, exist_ok=True)
        dest = self.store.raw / f"{source_id}{src_path.suffix.lower()}"
        shutil.copy2(src_path, dest)
        candidate.local_file = str(dest.relative_to(self.store.root))

        self.sources.save(candidate)
        return IngestResult(candidate)

    def ingest_metadata_only(self, source: Source) -> IngestResult:
        """Register a source we could not fetch full text for (spec §3.2)."""
        source.access_status = AccessStatus.METADATA_ONLY
        if source.evidence_level == EvidenceLevel.UNKNOWN:
            source.evidence_level = SOURCE_TYPE_TO_EVIDENCE.get(
                source.source_type, EvidenceLevel.UNKNOWN
            )
        dup = self.sources.find_duplicate(source)
        if dup is not None:
            return IngestResult(dup, duplicate_of=dup)
        self.sources.save(source)
        return IngestResult(source)
