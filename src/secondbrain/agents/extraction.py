"""Extraction Agent: turn raw sources into structured knowledge (spec §5, §17).

Extraction is *pluggable*. Phase 1 ships a dependency-light heuristic
extractor that works on real PDF/text without an LLM. A later phase can
register an LLM-backed :class:`Extractor` implementing the same protocol
without changing any caller.

Guiding rule (spec §18): never fabricate. If a field is not found it stays
empty rather than being guessed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from ..config import StoreConfig
from ..models import PaperExtraction, Source
from ..store import ExtractionRepository


class Extractor(Protocol):
    """Anything that can produce a :class:`PaperExtraction` from source text."""

    def extract(self, source: Source, text: str) -> PaperExtraction: ...


def read_source_text(store: StoreConfig, source: Source) -> str:
    """Best-effort plain-text extraction of a raw file.

    Supports PDF (via pypdf) and plain-text/markdown/html. Returns an empty
    string when we hold no local full text (metadata-only sources).
    """
    if not source.local_file:
        return ""
    path = store.root / source.local_file
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".txt", ".md", ".html", ".htm"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:  # pragma: no cover - malformed PDF
        return ""


# --- Heuristic extractor -------------------------------------------------

_SECTION_CUES = {
    "purpose": [
        r"purpose of this (study|paper|research)",
        r"we (aim|seek) to",
        r"this (study|paper) (examines|investigates|explores)",
    ],
    "methodology": [
        r"\bmethodolog",
        r"\bmethod(s)?\b",
        r"we (conducted|performed|used)",
    ],
    "limitations": [r"\blimitation", r"\bconstraint"],
    "future_work": [
        r"future research",
        r"further (study|research|work)",
        r"future work",
        r"should (examine|explore|investigate)",
    ],
}


class HeuristicPaperExtractor:
    """Regex/keyword extractor. Deterministic, offline, best-effort.

    It pulls a title, DOI, abstract, candidate research questions, methodology
    hints, key concepts (capitalized noun phrases), and limitations. It is
    intentionally conservative: unknown fields stay empty (spec §18).
    """

    DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
    YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

    def extract(self, source: Source, text: str) -> PaperExtraction:
        ex = PaperExtraction(source_id=source.source_id)
        ex.title = source.title
        ex.doi = source.doi or self._first(self.DOI_RE, text)

        if not text.strip():
            return ex  # metadata-only source

        ex.abstract = self._abstract(text)
        year = self._first(self.YEAR_RE, text)
        ex.year = int(year) if year else None

        ex.research_questions = self._sentences_with(
            text, [r"research question", r"\bRQ\d?\b", r"we ask whether", r"do(es)? .* affect"]
        )[:5]
        ex.methodology = self._first_sentence_matching(text, _SECTION_CUES["methodology"])
        ex.purpose = self._first_sentence_matching(text, _SECTION_CUES["purpose"])
        ex.limitations = self._sentences_with(text, _SECTION_CUES["limitations"])[:5]
        ex.future_work = self._sentences_with(text, _SECTION_CUES["future_work"])[:5]
        ex.key_concepts = self._key_phrases(ex.abstract or text[:2000])
        return ex

    # --- helpers ---
    @staticmethod
    def _first(pattern: re.Pattern[str], text: str) -> str | None:
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _sentences(text: str) -> list[str]:
        # Simple sentence splitter; good enough for cue matching.
        parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
        return [p.strip() for p in parts if len(p.strip()) > 20]

    def _sentences_with(self, text: str, cues: list[str]) -> list[str]:
        pats = [re.compile(c, re.IGNORECASE) for c in cues]
        out: list[str] = []
        for s in self._sentences(text):
            if any(p.search(s) for p in pats):
                out.append(s)
        return out

    def _first_sentence_matching(self, text: str, cues: list[str]) -> str | None:
        found = self._sentences_with(text, cues)
        return found[0] if found else None

    @staticmethod
    def _abstract(text: str) -> str | None:
        m = re.search(
            r"abstract\b[:\s]*(.{80,1500}?)(?:\n\s*\n|introduction\b|keywords\b|1\.\s)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            return " ".join(m.group(1).split())
        return None

    @staticmethod
    def _key_phrases(text: str) -> list[str]:
        # Capitalized multi-word phrases are decent concept candidates.
        phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text or "")
        seen: dict[str, int] = {}
        for p in phrases:
            seen[p] = seen.get(p, 0) + 1
        ranked = sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))
        # Drop very common non-concepts.
        stop = {"The", "This", "These", "We", "In", "Our"}
        return [p for p, _ in ranked if p.split()[0] not in stop][:12]


class ExtractionAgent:
    def __init__(self, store: StoreConfig, extractor: Extractor | None = None) -> None:
        self.store = store
        self.extractor = extractor or HeuristicPaperExtractor()
        self.repo = ExtractionRepository(store)

    def extract(self, source: Source) -> PaperExtraction:
        text = read_source_text(self.store, source)
        extraction = self.extractor.extract(source, text)
        self.repo.save(extraction)
        return extraction
