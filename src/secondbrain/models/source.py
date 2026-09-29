"""The Source model: a registered knowledge source and its metadata (spec §4)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .enums import AccessStatus, EvidenceLevel, SourceType


class Source(BaseModel):
    """A single registered source (raw layer bookkeeping + metadata layer).

    Holds the metadata required by spec §4 plus dedup fingerprints (spec §21).
    The raw bytes live on disk under ``store/raw/`` and are never mutated
    (spec §2.1); this record only *points* at them.
    """

    source_id: str
    source_type: SourceType = SourceType.OTHER
    title: str | None = None
    author: list[str] = Field(default_factory=list)
    organization: str | None = None
    publication: str | None = None
    publication_date: date | None = None
    ingestion_date: datetime = Field(default_factory=datetime.utcnow)

    doi: str | None = None
    url: str | None = None
    local_file: str | None = Field(default=None, description="Path within store/raw/.")
    language: str | None = None
    keywords: list[str] = Field(default_factory=list)

    access_status: AccessStatus = AccessStatus.PENDING
    peer_reviewed: bool | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.UNKNOWN

    # --- dedup fingerprints (spec §21) ---
    file_hash: str | None = None

    def fingerprints(self) -> dict[str, str]:
        """Return the identity signals used for duplicate detection."""
        fp: dict[str, str] = {}
        if self.doi:
            fp["doi"] = self.doi.lower().strip()
        if self.file_hash:
            fp["file_hash"] = self.file_hash
        if self.url:
            fp["url"] = self.url.strip().rstrip("/").lower()
        if self.title:
            fp["title"] = " ".join(self.title.lower().split())
        return fp
