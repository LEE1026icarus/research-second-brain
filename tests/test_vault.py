"""Deterministic tools the LLM agent relies on: register, parse, index, lint, log."""

from __future__ import annotations

from secondbrain import vault
from secondbrain.agents import IngestionAgent
from secondbrain.models import CompileStatus, SourceType
from secondbrain.parsing import parse_file
from secondbrain.store import SourceRepository


def _write(store, rel: str, text: str) -> None:
    path = store.root / f"{rel}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PAPER = """---
type: paper
title: 테스트 논문
authors: [홍길동, 김철수]
year: 2020
evidence_level: peer_reviewed
summary: 테스트용
---
# 테스트 논문

## Claims
- **C1** A → B | direction: + | p.3
- **C2** C → D | direction: +

## Related Pages
- [[wiki/concepts/개념-a|개념 A]]
"""

CONCEPT = """---
type: concept
title: 개념 A
---
# 개념 A

## Established Findings
- A는 B를 높인다 ([[wiki/papers/테스트-논문|홍길동 외, 2020]], p.3)
- 출처가 없는 일반화 문장입니다

## Related Papers
- [[wiki/papers/테스트-논문]]
- [[wiki/papers/없는-논문]]
"""


def test_register_preserves_raw_parses_pages_and_dedups(store, tmp_path):
    src = tmp_path / "paper.txt"
    src.write_text("<!-- page 121 -->\n첫 쪽\n<!-- page 122 -->\n둘째 쪽\n", encoding="utf-8")
    agent = IngestionAgent(store)
    res = agent.ingest_file(src, source_type=SourceType.JOURNAL_ARTICLE)
    s = res.source
    assert (store.root / s.local_file).read_bytes() == src.read_bytes()
    assert s.status == CompileStatus.PENDING and s.pages == 2
    text = (store.root / s.text_file).read_text(encoding="utf-8")
    assert "<!-- page 121 -->" in text and "<!-- page 122 -->" in text
    assert agent.ingest_file(src).is_duplicate


def test_unparsable_file_is_flagged_needs_text(store, tmp_path):
    empty = tmp_path / "scan.txt"
    empty.write_text("   ", encoding="utf-8")
    s = IngestionAgent(store).ingest_file(empty).source
    assert s.status == CompileStatus.NEEDS_TEXT and s.text_file is None


def test_html_parser_drops_scripts(tmp_path):
    page = tmp_path / "a.html"
    page.write_text("<html><script>x=1</script><p>본문</p></html>", encoding="utf-8")
    doc = parse_file(page)
    assert doc and "본문" in doc.pages[0] and "x=1" not in doc.pages[0]


def test_lint_catches_agent_mistakes(store):
    _write(store, "wiki/papers/테스트-논문", PAPER)
    _write(store, "wiki/concepts/개념-a", CONCEPT)
    _write(store, "wiki/concepts/고아-개념", "---\ntype: concept\ntitle: 고아\n---\n# 고아\n")
    _write(store, "wiki/concepts/아이디어", "---\ntype: idea\nepistemic: idea\ntitle: X\n---\n")
    _write(store, "ideas/emerging/근거없음", "---\ntype: idea\ntitle: Y\n---\n# Y\n")
    _write(store, "wiki/concepts/깨진", "no frontmatter")
    codes = {(i.code, i.page) for i in vault.lint(store).issues}

    assert ("broken-link", "wiki/concepts/개념-a") in codes
    assert ("uncited", "wiki/concepts/개념-a") in codes
    assert ("claim-without-page", "wiki/papers/테스트-논문") in codes
    assert ("orphan", "wiki/concepts/고아-개념") in codes
    assert ("idea-in-wiki", "wiki/concepts/아이디어") in codes
    assert ("idea-without-source", "ideas/emerging/근거없음") in codes
    assert ("frontmatter", "wiki/concepts/깨진") in codes
    # The paper is linked from a concept page, so it counts as connected.
    assert ("unconnected-source", "wiki/papers/테스트-논문") not in codes
    # The cited bullet must not be reported.
    uncited = [i.detail for i in vault.lint(store).issues if i.code == "uncited"]
    assert len(uncited) == 1 and "출처가 없는" in uncited[0]


def test_index_and_done_update_status_and_log(store, tmp_path):
    src = tmp_path / "p.txt"
    src.write_text("본문", encoding="utf-8")
    s = IngestionAgent(store).ingest_file(src).source
    _write(store, "wiki/papers/테스트-논문", PAPER)
    _write(store, "wiki/concepts/개념-a", CONCEPT)

    vault.mark_compiled(
        store,
        s.source_id,
        "wiki/papers/테스트-논문",
        touched=["wiki/concepts/개념-a"],
        effects=["wiki/concepts/개념-a: extend — 새 맥락"],
    )
    assert SourceRepository(store).get(s.source_id).status == CompileStatus.COMPILED
    log = store.log_md.read_text(encoding="utf-8")
    assert "] ingest |" in log and "effect: wiki/concepts/개념-a: extend" in log

    index = vault.build_index(store)
    assert "[[wiki/papers/테스트-논문|테스트 논문]]" in index and "홍길동 외 (2020)" in index
    assert "## Concepts (1)" in index
