"""sb graph: Claims → graph → Synapse candidates."""

from __future__ import annotations

from datetime import date

from secondbrain import kg
from secondbrain.store import GraphRepository

PU = "[[wiki/concepts/perceived-usefulness|유용성]]"
AI = "[[wiki/concepts/adoption-intention|수용 의도]]"
TR = "[[wiki/concepts/trust|신뢰]]"


def _paper(store, slug, year, claims, *, theories, methods, domain, design):
    body = "\n".join(claims)
    text = f"""---
type: paper
title: {slug}
source_id: src-{slug}
year: {year}
theories: {theories}
methods: {methods}
domain: {domain}
design: {design}
---
# {slug}

## Claims
{body}

## Related Pages
- [[wiki/methods/sem|SEM]]
"""
    path = store.root / f"wiki/papers/{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _page(store, rel, title, typ):
    path = store.root / f"{rel}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntype: {typ}\ntitle: {title}\n---\n# {title}\n", encoding="utf-8")


def test_graph_and_candidates(store):
    for rel, title in (
        ("wiki/concepts/perceived-usefulness", "유용성"),
        ("wiki/concepts/adoption-intention", "수용 의도"),
        ("wiki/concepts/trust", "신뢰"),
    ):
        _page(store, rel, title, "concept")
    _page(store, "wiki/methods/sem", "SEM", "method")
    _paper(
        store,
        "a",
        2012,
        [f"- **C1** {TR} → {PU} | direction: + | p.3"],
        theories="[TAM]",
        methods="[SEM]",
        domain="[fintech]",
        design="cross-sectional",
    )
    _paper(
        store,
        "b",
        2014,
        [f"- **C1** {PU} → {AI} | direction: + | p.5"],
        theories="[TAM]",
        methods="[SEM]",
        domain="[fintech]",
        design="cross-sectional",
    )
    _paper(
        store,
        "c",
        2015,
        [
            f"- **C2** {PU} → {AI} | direction: 0 | p.9",
            "- **C3** 결론만 있는 Claim | direction: n/a | p.10",
        ],
        theories="[TAM]",
        methods="[LDA]",
        domain="[tourism]",
        design="text-mining",
    )

    res = kg.build(store, today=date(2026, 9, 30))
    nodes, edges = GraphRepository(store).load()
    ids = {n.node_id for n in nodes}
    assert {"wiki/concepts/perceived-usefulness", "wiki/papers/a#C1", "wiki/methods/sem"} <= ids
    predicts = [e for e in edges if e.edge_type.value == "predicts"]
    assert len(predicts) == 3 and {e.attrs["direction"] for e in predicts} == {"+", "0"}
    assert any(e.edge_type.value == "uses_method" and e.target == "wiki/methods/sem" for e in edges)
    assert res.claims == 4 and res.relations == 3

    kinds = {c.kind: c for c in res.candidates}
    assert "유용성 → 수용 의도" in kinds["contradiction"].title  # + vs 0 in two papers
    assert "신뢰 → 수용 의도" in kinds["missing-edge"].title  # 신뢰→유용성→수용 의도
    titles = [c.title for c in res.candidates]
    assert any("방법 'SEM'" in t and "'tourism'" in t for t in titles)
    assert any("방법 'LDA'" in t and "'fintech'" in t for t in titles)
    assert any(c.kind == "evidence-gap" and "'TAM'" in c.title for c in res.candidates)
    assert any(c.kind == "temporal-gap" and "'TAM'" in c.title for c in res.candidates)
    report = kg.render_candidates(res)
    assert "## 충돌" in report and "[[wiki/papers/b]] C1, p.5" in report


def test_single_chain_claim_is_not_a_missing_edge(store):
    _paper(
        store,
        "x",
        2025,
        ["- **C1** A → B → C | direction: + | p.1"],
        theories="[]",
        methods="[]",
        domain="[]",
        design="other",
    )
    res = kg.build(store, today=date(2026, 1, 1))
    assert res.relations == 2 and not [c for c in res.candidates if c.kind == "missing-edge"]
