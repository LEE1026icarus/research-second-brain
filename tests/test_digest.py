from __future__ import annotations

from datetime import date

from secondbrain.digest import build_digest, parse_log

LOG = """---
type: log
---
# Log

## [2026-09-01] ingest | 오래된 논문
- source: `src-old` → [[wiki/papers/old]]

## [2026-09-28] register | zotero sync (collection Tourism)
- added: `src-a` 논문 A
- metadata only: `src-b` 논문 B

## [2026-09-29] ingest | 논문 A
- source: `src-a` → [[wiki/papers/a]]
- touched: [[wiki/concepts/x]]
- touched: [[wiki/questions/q1]]
- effect: wiki/concepts/x: contradict — 방향이 반대
- effect: wiki/theories/t: strengthen — 같은 결과
- effect: 형식이 틀린 줄

## [2026-09-30] query | 공통 한계는?
## [2026-09-30] idea | 방법 이전 후보 2건
## [2026-09-30] lint | 0 errors, 1 warnings
"""


def test_parse_log():
    entries = parse_log(LOG)
    assert [e.kind for e in entries] == ["ingest", "register", "ingest", "query", "idea", "lint"]
    assert entries[2].bullets[0].startswith("source:")


def test_digest_counts_only_the_period_and_highlights_conflicts(store):
    store.log_md.write_text(LOG, encoding="utf-8")
    d = build_digest(store, days=7, end=date(2026, 9, 30))
    assert d.registered == ["논문 A", "논문 B"]
    assert d.ingested == [("논문 A", "wiki/papers/a")]  # 2026-09-01 is outside the week
    assert ("wiki/concepts/x", "contradict", "방향이 반대") in d.effects
    assert len(d.effects) == 2 and d.new_questions == ["wiki/questions/q1"]
    text = d.render()
    assert "## ⚡ 확인할 지식 변화" in text and "**contradict** [[wiki/concepts/x]]" in text
    assert "질의 1 · 아이디어 기록 1 " in text
