"""Korean-paper extraction and incremental integration (synthetic fixtures)."""

from __future__ import annotations

from secondbrain.agents.extraction import HeuristicPaperExtractor
from secondbrain.models import Source, SourceType
from secondbrain.pipeline import IngestPipeline

KO_PAPER_A = """KBR 제1권 제1호 2020년 5월 http://dx.doi.org/10.9999/test.2020.1

온라인 리뷰 기반 서비스 불만족 요인 연구

홍길동, 김철수
Test Business Review, 1(1), 1-20, 2020

[요약]
본 연구는 온라인 리뷰를 활용하여 서비스 불만족 요인을 도출하는 것을 목적으로 한다. 기대 불일치 이론을 기반으로 텍스트마이닝 기법과 LDA 토픽모델링을 활용하였다. 연구 결과, 가격과 대기시간이 주요 불만족 요인으로 도출되었다.

주제어: 온라인 리뷰, 서비스 불만족, 기대 불일치

Ⅲ. 연구 방법론
데이터는 총 300건의 리뷰를 대상으로 수집하였다. LDA 토픽모델링을 적용하였다.

5.2 한계 및 향후 연구 방향
본 연구는 단일 플랫폼 데이터만 사용하였다는 한계가 있다.
향후 연구에서는 여러 플랫폼의 데이터를 비교할 수 있을 것이다.
"""

KO_PAPER_B = """온라인 리뷰 감성과 재방문 의도

박영희, 이민수
Test Business Review, 2(1), 1-15, 2021

[요약]
본 연구는 온라인 리뷰의 감성이 재방문 의도에 미치는 영향을 검증하는 것을 목적으로 한다. 감성 분석과 LDA 토픽모델링을 활용하였다.

주제어: 온라인 리뷰, 재방문 의도

5.2 한계 및 향후 연구 방향
향후 연구에서는 종단 데이터를 활용할 수 있을 것이다.
"""


def _source() -> Source:
    return Source(source_id="s-ko", source_type=SourceType.JOURNAL_ARTICLE, title="ko_file")


def test_korean_metadata_and_sections():
    ex = HeuristicPaperExtractor().extract(_source(), KO_PAPER_A)
    assert ex.language == "ko"
    assert ex.title == "온라인 리뷰 기반 서비스 불만족 요인 연구"
    assert ex.authors == ["홍길동", "김철수"]
    assert ex.journal == "Test Business Review"
    assert ex.year == 2020
    assert ex.doi == "10.9999/test.2020.1"
    assert ex.keywords == ["온라인 리뷰", "서비스 불만족", "기대 불일치"]
    assert ex.abstract and ex.abstract.startswith("본 연구는")
    assert ex.purpose and "목적으로 한다" in ex.purpose
    assert ex.sample and "300건" in ex.sample
    assert any("한계" in s for s in ex.limitations)
    assert any("향후" in s for s in ex.future_work)


def test_bilingual_gazetteer_maps_to_canonical_names():
    ex = HeuristicPaperExtractor().extract(_source(), KO_PAPER_A)
    assert "Expectancy-Disconfirmation Theory" in ex.theoretical_background
    assert "Latent Dirichlet Allocation (LDA)" in ex.analysis_methods
    # Known theories are not duplicated as free-form concepts.
    assert "기대 불일치" not in ex.key_concepts
    assert "온라인 리뷰" in ex.key_concepts


def test_second_paper_updates_shared_pages_incrementally(store, tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text(KO_PAPER_A, encoding="utf-8")
    b.write_text(KO_PAPER_B, encoding="utf-8")
    pipe = IngestPipeline(store)
    first = pipe.run(a, source_type=SourceType.JOURNAL_ARTICLE)
    second = pipe.run(b, source_type=SourceType.JOURNAL_ARTICLE)

    concept = store.wiki / "concepts" / "온라인-리뷰.md"
    method = store.wiki / "methods" / "latent-dirichlet-allocation-lda.md"
    assert "wiki/concepts/온라인-리뷰.md" in first.wiki_update.created_pages
    assert "wiki/concepts/온라인-리뷰.md" in second.wiki_update.updated_pages
    for page in (concept, method):
        text = page.read_text(encoding="utf-8")
        assert "홍길동 외 (2020)" in text and "박영희 외 (2021)" in text
    # Overview accretes both papers instead of being regenerated.
    overview = (store.wiki / "overviews" / "온라인-리뷰.md").read_text(encoding="utf-8")
    assert overview.count("— ") >= 2
