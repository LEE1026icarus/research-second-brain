"""`sb verify` — check that citations say what the source says (spec §2.3, §17 Reviewer).

`sb lint` checks that a citation *exists*. This module checks that it is
*right*: for every line that cites a page (``p.128``, ``p.128–129``) it takes

* quoted text (``"..."``, ``“...”``, ``‘...’``, ``'...'``) and
* numbers (``0.293``, ``37.0%``, ``30,770``, ``−6.507``)

and looks them up on the cited page(s) of ``structured/<source_id>.md``.
A quote that is nowhere in the source is an error (likely invented); a quote
or number found on a different page is a warning with the page it was found
on. Numbers that do not appear anywhere are warnings (they may be computed,
e.g. a sum, and then the page should say so).

The check is deliberately literal. It cannot judge paraphrases — that remains
the agent's and the user's job.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .config import StoreConfig
from .parsing import PAGE_MARKER_RE
from .store import SourceRepository
from .vault import FRONTMATTER_RE, LINK_RE, load_pages

PAPER_LINK_RE = re.compile(r"\[\[(wiki/(?:papers|sources)/[^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
PAGE_RE = re.compile(
    r"\bpp?\.\s*(\d{1,4})(?:\s*[–—\-~]\s*(\d{1,4}))?"  # p.128, p.128–129, pp.3-5
)
QUOTE_RES = [
    re.compile(r'"([^"\n]{2,300})"'),
    re.compile(r"“([^”\n]{2,300})”"),
    re.compile(r"‘([^’\n]{2,300})’"),
    re.compile(r"(?<![A-Za-z0-9])'([^'\n]{2,300})'(?![A-Za-z0-9])"),
]
NUMBER_RE = re.compile(
    r"(?<![\w.,])[−\-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.,])[−\-]?\d+\.\d+|(?<![\w.,])\d{2,}(?![\w])"
)
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
CLAIM_ID_RE = re.compile(r"\*\*[A-Z]\d+\*\*")
COMPUTED_RE = re.compile(r"계산|computed|derived", re.IGNORECASE)


@dataclass
class Finding:
    level: str  # error | warn | info
    code: str
    page: str  # wiki page (vault-relative)
    line: int
    detail: str


@dataclass
class VerifyReport:
    findings: list[Finding] = field(default_factory=list)
    checked_quotes: int = 0
    checked_numbers: int = 0
    citations: int = 0

    def add(self, *args) -> None:
        self.findings.append(Finding(*args))

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f.level == level)


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s).lower()


def _norm_num(s: str) -> str:
    return s.replace("−", "-").replace(",", "")


def _source_pages(store: StoreConfig, text_file: str) -> dict[int, str]:
    text = (store.root / text_file).read_text(encoding="utf-8", errors="ignore")
    markers = list(PAGE_MARKER_RE.finditer(text))
    pages: dict[int, str] = {}
    for i, m in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        pages[int(m.group(1))] = pages.get(int(m.group(1)), "") + text[m.end() : end]
    return pages


def _numbers_in(text: str) -> set[str]:
    return {_norm_num(m.group(0)).lstrip("-") for m in NUMBER_RE.finditer(text)}


def _checkables(line: str) -> tuple[list[str], list[str]]:
    """Quotes and numbers stated in a line, excluding links and page references."""
    body = LINK_RE.sub(" ", line)
    body = PAGE_RE.sub(" ", body)
    body = CLAIM_ID_RE.sub(" ", body)
    body = re.sub(r"§\s*[\d.]+", " ", body)
    body = ISO_DATE_RE.sub(" ", body)
    quotes: list[str] = []
    for rx in QUOTE_RES:
        for m in rx.finditer(body):
            q = m.group(1).strip()
            if q and not q.startswith(("[[", "http")):
                quotes.append(q)
    for q in quotes:  # numbers inside quotes are checked as part of the quote
        body = body.replace(q, " ")
    numbers = []
    for m in NUMBER_RE.finditer(body):
        n = _norm_num(m.group(0)).lstrip("-")
        if YEAR_RE.match(n):
            continue  # years are usually context ("2018년 수집"), not claims
        numbers.append(n)
    return quotes, numbers


def verify(store: StoreConfig, only: str | None = None) -> VerifyReport:
    report = VerifyReport()
    sources = {s.source_id: s for s in SourceRepository(store).all()}
    pages = load_pages(store)
    page_source: dict[str, str] = {}  # wiki page rel -> source_id
    for p in pages:
        sid = p.frontmatter.get("source_id")
        if p.folder in ("papers", "sources") and sid:
            page_source[p.rel] = str(sid)
    cache: dict[str, dict[int, str]] = {}

    def text_of(sid: str) -> dict[int, str] | None:
        if sid not in cache:
            src = sources.get(sid)
            if not src or not src.text_file or not (store.root / src.text_file).exists():
                return None
            cache[sid] = _source_pages(store, src.text_file)
        return cache[sid]

    for p in pages:
        if only and p.rel != only.removesuffix(".md"):
            continue
        body = p.path.read_text(encoding="utf-8", errors="ignore")
        fm = FRONTMATTER_RE.match(body)
        offset = body[: fm.end()].count("\n") if fm else 0
        in_code = False
        for lineno, line in enumerate(body[fm.end() if fm else 0 :].splitlines(), offset + 1):
            if line.strip().startswith("```"):
                in_code = not in_code
            if in_code or not PAGE_RE.search(line):
                continue
            _verify_line(report, store, p.rel, lineno, line, page_source, text_of)
    return report


def _cited_spans(line: str, page_source: dict[str, str], self_sid: str | None):
    """Yield (source_id, [pages], span_text) for each citation group in a line.

    Adjacent references like ``(p.121, p.126)`` form one group (their pages are
    pooled). A group belongs to the nearest paper/source link before it in the
    same line; on a paper page, bare ``p.N`` refers to the page's own source.
    The span text is the claim between the previous group and this one.
    """
    links = [(m.start(), page_source.get(m.group(1).strip())) for m in PAPER_LINK_RE.finditer(line)]
    refs = list(PAGE_RE.finditer(line))
    groups: list[list[re.Match]] = []
    for m in refs:
        if groups and re.fullmatch(r"[\s,;·/]*", line[groups[-1][-1].end() : m.start()]):
            groups[-1].append(m)
        else:
            groups.append([m])
    prev_end = 0
    for g in groups:
        owner = next((sid for pos, sid in reversed(links) if pos < g[0].start()), None) or self_sid
        pages: list[int] = []
        for m in g:
            first = int(m.group(1))
            last = int(m.group(2)) if m.group(2) else first
            if last < first or last - first > 30:
                last = first
            pages.extend(n for n in range(first, last + 1) if n not in pages)
        yield owner, pages, line[prev_end : g[-1].end()]
        prev_end = g[-1].end()


def _verify_line(report, store, rel, lineno, line, page_source, text_of) -> None:
    self_sid = page_source.get(rel)
    spans = list(_cited_spans(line, page_source, self_sid))
    # If one source is cited once, check the whole line against it.
    if len(spans) == 1:
        spans = [(spans[0][0], spans[0][1], line)]
    # Pages cited anywhere in this line, per source: a match there is accepted,
    # because splitting a line into claim spans is only approximate.
    line_pages: dict[str | None, set[int]] = {}
    for sid, cited, _ in spans:
        line_pages.setdefault(sid, set()).update(cited)
    for sid, cited, span in spans:
        report.citations += 1
        if sid is None:
            report.add(
                "info",
                "unresolved-citation",
                rel,
                lineno,
                f"no source for p.{cited[0]}: {line.strip()[:60]}",
            )
            continue
        src_pages = text_of(sid)
        if src_pages is None:
            report.add("info", "no-source-text", rel, lineno, f"{sid} has no parsed text")
            continue
        missing = [n for n in cited if n not in src_pages]
        if missing:
            have = f"{min(src_pages)}–{max(src_pages)}" if src_pages else "none"
            report.add(
                "error",
                "page-not-in-source",
                rel,
                lineno,
                f"p.{missing[0]} not in {sid} (pages {have})",
            )
            continue
        cited_text = "".join(src_pages[n] for n in sorted(line_pages[sid]) if n in src_pages)
        cited_norm = _norm_text(cited_text)
        cited_nums = _numbers_in(cited_text)
        quotes, numbers = _checkables(span)
        for q in quotes:
            report.checked_quotes += 1
            qn = _norm_text(q)
            if qn in cited_norm:
                continue
            elsewhere = [n for n, t in src_pages.items() if qn in _norm_text(t)]
            if elsewhere:
                report.add(
                    "warn",
                    "quote-other-page",
                    rel,
                    lineno,
                    f"'{q[:40]}' is on p.{elsewhere[0]}, cited p.{cited[0]}",
                )
            else:
                report.add("error", "quote-not-found", rel, lineno, f"'{q[:50]}' not in {sid}")
        for n in numbers:
            report.checked_numbers += 1
            if n in cited_nums:
                continue
            elsewhere = [pg for pg, t in src_pages.items() if n in _numbers_in(t)]
            if elsewhere:
                report.add(
                    "warn",
                    "number-other-page",
                    rel,
                    lineno,
                    f"{n} is on p.{elsewhere[0]}, cited p.{cited[0]}",
                )
            elif COMPUTED_RE.search(span):
                report.add("info", "number-computed", rel, lineno, f"{n} marked as computed")
            else:
                report.add(
                    "warn",
                    "number-not-found",
                    rel,
                    lineno,
                    f"{n} not in {sid} — if computed, mark it '(계산)'",
                )
