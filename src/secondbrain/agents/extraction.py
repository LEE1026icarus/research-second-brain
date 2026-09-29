"""Extraction Agent: turn raw sources into structured knowledge (spec §5, §17).

Extraction is *pluggable*. Phase 1 ships a dependency-light heuristic
extractor that works on real PDF/text (Korean and English) without an LLM. A
later phase can register an LLM-backed :class:`Extractor` implementing the same
protocol without changing any caller.

Guiding rule (spec §18): never fabricate. If a field is not found it stays
empty rather than being guessed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from .. import vocab
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


# --- cue vocabularies (English + Korean) ---------------------------------

_CUES: dict[str, list[str]] = {
    "purpose": [
        r"purpose of this (study|paper|research)",
        r"we (aim|seek) to",
        r"this (study|paper) (examines|investigates|explores)",
        r"목적으로\s*한다",
        r"목적은",
        r"목적이다",
    ],
    "methodology": [
        r"\bmethodolog",
        r"\bmethods?\b",
        r"we (conducted|performed|used)",
        r"연구\s*방법",
        r"기법[을과]\s*(사용|활용)",
        r"(을|를)\s*(사용|활용)하여",
    ],
    "research_questions": [
        r"research question",
        r"\bRQ\d?\b",
        r"we ask whether",
        r"연구\s*(질문|문제)\s*[:：\d]",
    ],
    "sample": [
        r"\d[\d,]*\s*(명|건|개\s*기업|부)(?![가-힣]*\s*이상).*(수집|취합|응답|표본|사용자|대상)",
        r"(수집|취합|응답|표본|사용자|대상).*\d[\d,]*\s*(명|건)",
        r"\bN\s*=\s*\d",
        r"\d[\d,]*\s+(respondents|participants|professionals|firms|reviews|tweets)",
    ],
    "data": [r"수집하였다", r"데이터[는를].*(수집|취합)", r"data (were|was) collected"],
    "findings": [
        r"results? (show|indicate|suggest|reveal)",
        r"found that",
        r"we find",
        r"연구\s*결과",
        r"도출되었다",
        r"나타났다",
    ],
    "theoretical_contrib": [
        r"theoretical contribution",
        r"contributes? to .*literature",
        r"학술적",
        r"학문적",
        r"이론적\s*(기여|시사점)",
        r"방법론적\s*확장",
    ],
    "practical_contrib": [r"practical (implication|contribution)", r"managerial", r"실무적"],
    "limitations": [r"\blimitation", r"\bconstraint", r"한계", r"비교적\s*적", r"만을\s"],
    "future_work": [
        r"future (research|work|stud)",
        r"further (study|research|work)",
        r"should (examine|explore|investigate)",
        r"향후",
        r"후속\s*연구",
        r"추후",
        r"(으)?면\s.*수\s*있을\s*것이다",
    ],
}
_CUE_RE = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in _CUES.items()}

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_HEADING_RE = re.compile(
    r"^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*\.|[IVX]+\.\s|\d+(?:\.\d+)*\.?\s|\[|<표|<그림|〈"
    r"|주제어|핵심어|key\s*words?\b|keywords\b|abstract\b|references\b|참고문헌|국내참고문헌)",
    re.IGNORECASE,
)
_KO_AUTHORS = re.compile(r"^[가-힣]{2,4}(?:\s*[,，·ㆍ]\s*[가-힣]{2,4})+$")
_JOURNAL_RE = re.compile(r"^\s*([A-Z][A-Za-z&\- ]{3,80}?),\s*\d+\s*\(\d+\)", re.MULTILINE)
_KEYWORDS_RE = re.compile(r"(?:주제어|핵심어|key\s*words?)\s*[:：]\s*(.+)", re.IGNORECASE)
_KO_ABS_RE = re.compile(
    r"(?:^|\n)\s*\[?\s*(?:요\s*약|국문\s*초록|초\s*록)\s*\]?\s*\n(.{40,4000}?)"
    r"(?=\n\s*(?:주제어|핵심어|key\s*words?|Ⅰ\s*\.|1\.\s))",
    re.IGNORECASE | re.DOTALL,
)
_EN_ABS_RE = re.compile(
    r"(?:^|\n)\s*abstract\b[:\s]*(.{40,4000}?)"
    r"(?=\n\s*\n|\n\s*(?:key\s*words?|keywords|introduction|1\.\s)|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_LIMIT_SECTION_RE = re.compile(r"한계|limitation", re.IGNORECASE)


class HeuristicPaperExtractor:
    """Regex/keyword extractor for Korean and English papers.

    Deterministic, offline, best-effort. Theories and methods are only reported
    when a known name from :mod:`secondbrain.vocab` actually appears in the
    text. Everything it cannot find stays empty (spec §18).
    """

    DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
    YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

    def extract(self, source: Source, text: str) -> PaperExtraction:
        ex = PaperExtraction(source_id=source.source_id)
        ex.title = source.title
        ex.doi = source.doi or self._first(self.DOI_RE, text)
        if ex.doi:
            ex.doi = ex.doi.rstrip(".,;")

        if not text.strip():
            return ex  # metadata-only source

        ex.language = self._language(text)
        lines = [ln.strip() for ln in text.splitlines()]

        if self._looks_like_filename(source.title):
            ex.title = self._guess_title(lines, text) or source.title
        ex.authors = source.author or self._authors(lines)
        journal = _JOURNAL_RE.search(text)
        ex.journal = journal.group(1).strip() if journal else None
        ex.year = self._year(text, journal)

        kw = _KEYWORDS_RE.search(text)
        ex.keywords = [k.strip(" .") for k in re.split(r"[,;·]", kw.group(1))] if kw else []
        ex.keywords = [k for k in ex.keywords if k]
        ex.abstract = self._abstract(text, lines, ex.language)

        sentences = self._sentences(text)
        ex.purpose = self._first_match(sentences, "purpose")
        ex.methodology = self._first_match(sentences, "methodology")
        ex.research_questions = self._matches(sentences, "research_questions")[:5]
        # A sample description is factual; skip sentences that are really limitations.
        ex.sample = next(
            (
                s
                for s in self._matches(sentences, "sample")
                if not self._hits(s, "future_work") and not self._hits(s, "limitations")
            ),
            None,
        )
        ex.data = self._first_match(sentences, "data")
        ex.key_findings = self._matches(sentences, "findings")[:6]
        ex.theoretical_contributions = self._matches(sentences, "theoretical_contrib")[:4]
        ex.practical_contributions = self._matches(sentences, "practical_contrib")[:3]
        ex.limitations, ex.future_work = self._limitations_and_future(text, sentences)

        # Mentions in the abstract, keywords, title, or method sentences count as deliberate.
        emphasis = " ".join(
            [ex.abstract or "", " ".join(ex.keywords), ex.title or ""]
            + self._matches(sentences, "methodology")
        )
        ex.theoretical_background = self._entities("theory", text, emphasis)
        ex.analysis_methods = self._entities("method", text, emphasis)
        ex.key_concepts = self._concepts(ex, text)
        return ex

    # --- metadata helpers ---
    @staticmethod
    def _first(pattern: re.Pattern[str], text: str) -> str | None:
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _language(text: str) -> str:
        ko, en = len(_HANGUL.findall(text)), len(_LATIN.findall(text))
        return "ko" if ko > en * 0.3 else "en"

    @staticmethod
    def _looks_like_filename(title: str | None) -> bool:
        return not title or " " not in title.strip()

    @staticmethod
    def _norm_title(line: str) -> str:
        return re.sub(r"[\s*]+\d*\s*$", "", line).strip(" *")

    def _guess_title(self, lines: list[str], text: str) -> str | None:
        candidates: list[str] = []
        for line in lines[:60]:
            s = self._norm_title(line)
            if not (8 <= len(s) <= 200):
                continue
            if re.search(r"https?://|doi|제\s*\d+\s*권|vol\.|©|@|^\W", s, re.IGNORECASE):
                continue
            if _KO_AUTHORS.match(s) or _HEADING_RE.match(s) or s.endswith("."):
                continue
            candidates.append(s)
        if not candidates:
            return None
        # A title repeated as a running page header is the most reliable signal.
        normalized = [self._norm_title(ln) for ln in text.splitlines()]
        for c in candidates:
            if normalized.count(c) >= 2:
                return c
        return candidates[0]

    @staticmethod
    def _authors(lines: list[str]) -> list[str]:
        for line in lines[:40]:
            if _KO_AUTHORS.match(line):
                return [a.strip() for a in re.split(r"[,，·ㆍ]", line) if a.strip()]
        return []

    def _year(self, text: str, journal: re.Match[str] | None) -> int | None:
        if journal:
            line_end = text.find("\n", journal.end())
            line = text[journal.start() : line_end if line_end != -1 else None]
            m = self.YEAR_RE.search(line)
            if m:
                return int(m.group(0))
        m = re.search(r"제\s*\d+\s*권.*?((?:19|20)\d{2})\s*년", text)
        if m:
            return int(m.group(1))
        first = self._first(self.YEAR_RE, text)
        return int(first) if first else None

    @staticmethod
    def _abstract(text: str, lines: list[str], language: str) -> str | None:
        ko = _KO_ABS_RE.search(text)
        en = _EN_ABS_RE.search(text)
        order = [ko, en] if language == "ko" else [en, ko]
        for m in order:
            if m:
                return " ".join(m.group(1).split())
        # Korean papers often print the summary box right before "주제어" without a heading.
        for i, line in enumerate(lines):
            if re.match(r"(주제어|핵심어)\s*[:：]", line):
                block: list[str] = []
                for prev in reversed(lines[max(0, i - 40) : i]):
                    if not prev and not block:
                        continue  # skip blank lines right above the keywords line
                    if len(prev) < 12 or _HEADING_RE.match(prev):
                        break
                    block.insert(0, prev)
                joined = " ".join(" ".join(block).split())
                return joined if len(joined) >= 80 else None
        return None

    # --- sentence helpers ---
    @staticmethod
    def _paragraphs(text: str) -> list[tuple[bool, str]]:
        """Group lines into (is_heading, paragraph) so headings never merge into sentences."""
        out: list[tuple[bool, str]] = []
        buf: list[str] = []

        def flush() -> None:
            if buf:
                out.append((False, " ".join(buf)))
                buf.clear()

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                flush()
            elif _HEADING_RE.match(line):
                flush()
                out.append((True, line))
            else:
                buf.append(line)
        flush()
        return out

    def _sentences(self, text: str) -> list[str]:
        sentences: list[str] = []
        for is_heading, para in self._paragraphs(text):
            if is_heading:
                continue
            for s in re.split(r"(?<=[.!?])\s+", " ".join(para.split())):
                if len(s.strip()) > 15:
                    sentences.append(s.strip())
        return sentences

    @staticmethod
    def _hits(sentence: str, cue: str) -> bool:
        return any(p.search(sentence) for p in _CUE_RE[cue])

    def _matches(self, sentences: list[str], cue: str) -> list[str]:
        return [s for s in sentences if self._hits(s, cue)]

    def _first_match(self, sentences: list[str], cue: str) -> str | None:
        found = self._matches(sentences, cue)
        return found[0] if found else None

    def _limitations_and_future(
        self, text: str, sentences: list[str]
    ) -> tuple[list[str], list[str]]:
        """Prefer the dedicated limitations section; fall back to cue search."""
        section: list[str] = []
        inside = False
        for is_heading, para in self._paragraphs(text):
            if is_heading:
                if inside:
                    break
                inside = bool(_LIMIT_SECTION_RE.search(para))
                continue
            if inside:
                section.extend(
                    s.strip()
                    for s in re.split(r"(?<=[.!?])\s+", " ".join(para.split()))
                    if len(s.strip()) > 15
                )
        if section:
            future = [s for s in section if self._hits(s, "future_work")]
            limits = [
                s for s in section if self._hits(s, "limitations") or s not in future
            ]
            return limits[:6], future[:6]
        return self._matches(sentences, "limitations")[:5], self._matches(
            sentences, "future_work"
        )[:5]

    # --- entities & concepts ---
    @staticmethod
    def _entities(kind: str, text: str, emphasis: str) -> list[str]:
        """Known theories/methods mentioned at least twice, or once in abstract/keywords."""
        counts = vocab.count_mentions(kind, text)
        emphasized = vocab.count_mentions(kind, emphasis)
        keep = [n for n, c in counts.items() if c >= 2 or n in emphasized]
        return sorted(keep, key=lambda n: -counts[n])

    @staticmethod
    def _concepts(ex: PaperExtraction, text: str) -> list[str]:
        """Author keywords first (most reliable); capitalized phrases as fallback."""
        if ex.keywords:
            candidates = ex.keywords
        else:
            source_text = ex.abstract or text[:2000]
            phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", source_text)
            freq: dict[str, int] = {}
            for p in phrases:
                freq[p] = freq.get(p, 0) + 1
            stop = {"The", "This", "These", "We", "In", "Our"}
            candidates = [
                p for p, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
                if p.split()[0] not in stop
            ]
        journal = (ex.journal or "").lower()
        out: list[str] = []
        for c in candidates:
            if vocab.is_known_entity(c) or (journal and c.lower() == journal):
                continue
            if c not in out:
                out.append(c)
        return out[:12]


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
