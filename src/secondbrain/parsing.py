"""Turn a raw file into plain text split by page, for the LLM agent to read.

The agent (not this module) does all understanding. This module only makes
the text readable and keeps page boundaries so the agent can cite pages
(spec §2.3). Output is written to ``structured/<source_id>.md`` with
``<!-- page N -->`` markers.

Parsers are tried in order; better ones (OpenDataLoader PDF, Docling, HWP
parsers) can be added to ``_PARSERS`` without touching callers.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

PAGE_MARKER_RE = re.compile(r"^\s*<!--\s*page\s+(\d+)\s*-->\s*$", re.MULTILINE | re.IGNORECASE)


@dataclass
class ParsedDocument:
    pages: list[str]  # text per page (index 0 == first page)
    parser: str
    page_numbers: list[int] | None = None  # printed page numbers, if known
    numbering: str = "physical"  # physical | pdf-labels | printed (inferred)

    @property
    def text_chars(self) -> int:
        return sum(len(p.strip()) for p in self.pages)

    def to_markdown(self) -> str:
        numbers = self.page_numbers or list(range(1, len(self.pages) + 1))
        return "\n\n".join(
            f"<!-- page {n} -->\n{page.strip()}"
            for n, page in zip(numbers, self.pages, strict=True)
        )


def _parse_pdf(path: Path) -> ParsedDocument | None:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        return None
    reader = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in reader.pages]
    doc = ParsedDocument(pages, "pypdf")
    labels = _pdf_labels(reader, len(pages))
    if labels:
        doc.page_numbers, doc.numbering = labels, "pdf-labels"
    else:
        inferred = infer_printed_pages(pages)
        if inferred:
            doc.page_numbers, doc.numbering = (
                inferred,
                f"printed (inferred, offset {inferred[0] - 1:+d})",
            )
    return doc


def _pdf_labels(reader, n: int) -> list[int] | None:
    """Numeric page labels defined in the PDF, if they differ from 1..n."""
    try:
        labels = list(reader.page_labels)
    except Exception:  # noqa: BLE001
        return None
    if len(labels) != n or not all(str(x).isdigit() for x in labels):
        return None
    nums = [int(x) for x in labels]
    if nums == list(range(1, n + 1)) or len(set(nums)) != n:
        return None
    return nums


_EDGE_NUM_RE = re.compile(r"(?<![\d.,])(\d{1,4})(?![\d.,%])")


def infer_printed_pages(pages: list[str], min_share: float = 0.5) -> list[int] | None:
    """Detect journal page numbers printed in headers/footers (e.g. 121..141).

    Collects small integers from the first and last lines of each page and looks
    for a constant offset between them and the physical page index. Returns the
    printed numbers for every page, or None if no offset is clearly supported.
    """
    votes: dict[int, int] = {}
    with_text = 0
    for i, page in enumerate(pages):
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        if not lines:
            continue
        with_text += 1
        edge = lines[:3] + lines[-3:]
        offsets = {int(m.group(1)) - i for ln in edge for m in _EDGE_NUM_RE.finditer(ln)}
        for off in offsets:
            if off >= 1:
                votes[off] = votes.get(off, 0) + 1
    if with_text < 2 or not votes:
        return None
    best, count = max(votes.items(), key=lambda kv: (kv[1], -abs(kv[0] - 1)))
    if count < max(2, min_share * with_text) or best == 1:
        return None
    return [i + best for i in range(len(pages))]


def _parse_text(path: Path) -> ParsedDocument:
    """Plain text / markdown. Honors form feeds and ``<!-- page N -->`` markers."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    markers = list(PAGE_MARKER_RE.finditer(text))
    if markers:
        pages = [
            text[m.end() : markers[i + 1].start() if i + 1 < len(markers) else len(text)]
            for i, m in enumerate(markers)
        ]
        preamble = text[: markers[0].start()].strip()
        if preamble:  # never drop text that precedes the first marker
            pages[0] = preamble + "\n" + pages[0]
        return ParsedDocument(pages, "text", [int(m.group(1)) for m in markers], "markers")
    if "\f" in text:
        return ParsedDocument(text.split("\f"), "text")
    return ParsedDocument([text], "text")


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "nav", "footer", "header", "noscript"}
    _BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _parse_html(path: Path) -> ParsedDocument:
    ex = _TextExtractor()
    ex.feed(path.read_text(encoding="utf-8", errors="ignore"))
    text = re.sub(r"\n\s*\n+", "\n\n", "".join(ex.parts))
    return ParsedDocument([text], "html.parser")


_PARSERS: dict[str, list[Callable[[Path], ParsedDocument | None]]] = {
    ".pdf": [_parse_pdf],
    ".txt": [_parse_text],
    ".md": [_parse_text],
    ".html": [_parse_html],
    ".htm": [_parse_html],
}


def supported_suffixes() -> set[str]:
    return set(_PARSERS)


def parse_file(path: Path) -> ParsedDocument | None:
    """Return the first successful parse with real text, or ``None``."""
    for parser in _PARSERS.get(path.suffix.lower(), []):
        try:
            doc = parser(path)
        except Exception:  # noqa: BLE001 - a broken file must not stop registration
            doc = None
        if doc and doc.text_chars > 0:
            return doc
    return None
