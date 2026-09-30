"""sb verify: citations must match the cited pages; PDF printed page detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from secondbrain.agents import IngestionAgent
from secondbrain.parsing import infer_printed_pages, parse_file
from secondbrain.verify import verify

SOURCE = """<!-- page 127 -->
감성 분석: 강한 긍정 5.7%, 긍정 12.5%,
<!-- page 128 -->
중립 30.6%, 부정 37.0%. 토픽 개수를 5개로 정하였다(혼잡도 −6.507). 물가 0.293.
'물가'는 해외여행이 낫다는 의견이었다.
<!-- page 129 -->
제주도: 교통 0.317. 전체 토큰 30,770개.
"""

PAPER = """---
type: paper
title: 테스트 논문
source_id: {sid}
---
# 테스트 논문

## Results
- 부정 37.0% (p.128)
- 혼잡도 -6.507, 물가 0.293 (p.128)
- 제주 교통 0.317 (p.128)
- 토큰 30,770개 (p.129)
- 강한 긍정 5.7% (p.127), 제주 교통 0.317 (p.129)
- 합계 51.2% (p.127–128)
- 합계 42.8% (p.128, 계산)
- 2018-10-25 수집, 2018년 (p.128)

## Quotes
> "'물가'는 해외여행이 낫다는 의견이었다" (p.128)
> "지어낸 인용문입니다" (p.128)
> "교통 0.317" (p.128)

## Bad page
- 무언가 (p.300)
"""

CONCEPT = """---
type: concept
title: 개념
---
# 개념
- 물가 0.293 ([[wiki/papers/테스트-논문|저자, 2020]], p.128)
- 교통 0.317 ([[wiki/papers/테스트-논문|저자, 2020]], p.128)
"""


@pytest.fixture()
def wiki(store, tmp_path):
    raw = tmp_path / "src.txt"
    raw.write_text(SOURCE, encoding="utf-8")
    sid = IngestionAgent(store).ingest_file(raw).source.source_id
    for rel, text in (
        ("wiki/papers/테스트-논문", PAPER.format(sid=sid)),
        ("wiki/concepts/개념", CONCEPT),
    ):
        path = store.root / f"{rel}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return store


def _codes(report):
    return [(f.code, f.detail) for f in report.findings]


def test_verify_flags_only_wrong_citations(wiki):
    rep = verify(wiki)
    codes = _codes(rep)
    paper = [(f.code, f.detail) for f in rep.findings if f.page == "wiki/papers/테스트-논문"]
    concept = [(f.code, f.detail) for f in rep.findings if f.page == "wiki/concepts/개념"]

    # correct citations (incl. minus sign, thousands separator, year/date, grouped pages) pass
    assert not any("37.0" in d or "6.507" in d or "30770" in d or "2018" in d for _, d in codes)
    # number on another page than cited
    assert ("number-other-page", "0.317 is on p.129, cited p.128") in paper
    assert ("number-other-page", "0.317 is on p.129, cited p.128") in concept
    # a number that appears nowhere, unless marked as computed
    assert any(c == "number-not-found" and d.startswith("51.2") for c, d in paper)
    assert ("number-computed", "42.8 marked as computed") in paper
    # quotes: correct / invented / wrong page
    assert any(c == "quote-not-found" and "지어낸" in d for c, d in paper)
    assert ("quote-other-page", "'교통 0.317' is on p.129, cited p.128") in paper
    assert not any("해외여행" in d for _, d in codes)
    # page outside the source
    assert any(c == "page-not-in-source" and d.startswith("p.300") for c, d in paper)
    assert rep.count("error") == 2  # invented quote + missing page


def test_verify_single_page_filter(wiki):
    rep = verify(wiki, only="wiki/concepts/개념")
    assert {f.page for f in rep.findings} == {"wiki/concepts/개념"}


def test_infer_printed_pages_from_headers_and_footers():
    pages = [
        "Joint Sentiment 토픽모델링 121\n본문 454명 2018년\n- 121 -",
        "122 KBR 제24권 제2호 2020년 5월\n본문\n",
        "Joint Sentiment 123\n본문 30,770\n",
        "124 KBR\n본문 0.293",
    ]
    assert infer_printed_pages(pages) == [121, 122, 123, 124]
    assert infer_printed_pages(["본문 3", "본문 17", "그냥 2020"]) is None  # no consistent offset


def test_pdf_pages_use_printed_numbers(tmp_path):
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.set_auto_page_break(False)
    for i in range(4):
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 8, f"Journal header {121 + i}" if i % 2 == 0 else "Journal Vol.24 2020")
        pdf.set_y(40)
        pdf.multi_cell(0, 6, "Body text with 454 users in 2018. " * 4)
        pdf.set_y(-20)
        pdf.cell(0, 8, f"- {121 + i} -", align="C")
    out = tmp_path / "paper.pdf"
    pdf.output(str(out))
    doc = parse_file(Path(out))
    assert doc.page_numbers == [121, 122, 123, 124]
    assert doc.numbering.startswith("printed")
    assert "<!-- page 121 -->" in doc.to_markdown()
