# Research Second Brain 🧠

A personal research knowledge infrastructure. It ingests diverse sources
(papers, reports, news, web pages, datasets, personal notes), keeps a
**provenance-tracked Markdown wiki** and a **knowledge graph** incrementally up
to date, and is designed to surface new connections, research gaps, and
research-idea candidates as your library grows.

It is **not** a plain document store or a one-shot RAG Q&A bot. Every time a new
source arrives, existing knowledge is *updated in place* — strengthened,
narrowed, extended, or flagged as contradicted — rather than regenerated.

> Status: **Phase 1 (Core Wiki) implemented and tested.** Phases 2–6 (automation,
> knowledge graph, synapse engine, idea engine, interfaces) are scaffolded
> against the same models and documented in [`docs/REQUIREMENTS_MAP.md`](docs/REQUIREMENTS_MAP.md).

---

## Core design principles

The implementation is built around the principles in the requirements spec:

| Principle | Where it lives |
|-----------|----------------|
| **Three-layer separation** — Raw / Structured / Wiki are never conflated; originals are never modified | `store/raw`, `store/structured`, `store/wiki`; `IngestionAgent` copies (never moves) raw bytes |
| **Incremental updates** — new sources update existing pages, classified as `strengthen / narrow / extend / contradict / replace / unchanged` | `wiki/agent.py` (`UpdateEffect`) |
| **Provenance / traceability** — every synthesized statement cites its source | `models/provenance.py`, inline `(…, source: …)` citations |
| **Fact vs. synthesis vs. idea** — verified facts, cross-source synthesis, and speculative ideas are kept distinct | `Epistemic` enum; ideas stored under `store/ideas/`, never in the wiki |
| **Evidence levels** — peer-reviewed → … → personal note | `EvidenceLevel` with `.rank` |
| **Git-versionable & Obsidian-compatible** — plain markdown + YAML frontmatter + `[[wikilinks]]` | `wiki/page.py` |

---

## Quick start

```bash
# Python 3.11+ required
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Create a store (defaults to ./store, or set SECOND_BRAIN_STORE)
sb init

# Ingest a paper (PDF / txt / md / html …)
sb ingest examples/sample_paper.txt --title "Perceived Usefulness and GenAI Adoption"

# Explore
sb sources          # list registered sources
sb wiki             # list generated wiki pages
sb search "perceived usefulness adoption"
sb digest           # knowledge-base summary
sb show wiki/papers/<slug>.md
```

Point a folder watcher target at a directory:

```bash
sb ingest-dir ./inbox
```

Register your own project so idea generation can prioritize what's relevant to you:

```bash
sb project add "GenAI adoption in orgs" --rq "How do teams adopt GenAI?" --keywords "genai, adoption, teams"
```

---

## What one ingest does (spec §7 / §34)

```
New source
   ↓  IngestionAgent   – register, hash, dedup, preserve raw
   ↓  ExtractionAgent  – pull bibliographic + research fields (offline heuristics; LLM-pluggable)
   ↓  WikiAgent        – create/UPDATE paper page, concept pages, overview
   ↓                     add [[wikilinks]] + provenance citations
   ↓                     detect open questions from "future work"
Knowledge base updated
```

The knowledge store on disk:

```
store/
├── raw/          # untouched original files (never modified)
├── structured/   # one JSON extraction per source
├── wiki/         # Markdown knowledge (Obsidian-ready)
│   ├── papers/  concepts/  theories/  methods/  datasets/
│   ├── researchers/  organizations/  technologies/  topics/
│   └── overviews/  questions/
├── kg/           # knowledge graph (graph.json)
├── ideas/        # emerging/ research-questions/ hypotheses/ … (kept OUT of the wiki)
└── index/        # sources.json, projects.json
```

---

## Architecture & requirements coverage

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — components, data flow, extension points.
- [`docs/REQUIREMENTS_MAP.md`](docs/REQUIREMENTS_MAP.md) — every spec section (§1–§34) mapped to code and phase.

**Korean papers** are supported by the heuristic extractor (요약·주제어·한계 및 향후 연구
sections, Korean author lines, `제N권` volume headers). Theories and methods are recognized
through a bilingual gazetteer in `src/secondbrain/vocab.py` (e.g. `기대 불일치` →
*Expectancy-Disconfirmation Theory*), so Korean and English sources share the same wiki pages.
Extend that file as your library grows.

The agents mirror the spec's logical roles (§17): **Ingestion**, **Extraction**,
**Wiki**, and (scaffolded for later phases) **Graph**, **Synapse**, **Idea**,
**Reviewer**. Extraction is pluggable via an `Extractor` protocol so an
LLM-backed extractor can replace the Phase-1 heuristic one without touching
callers.

## Development

```bash
pip install -e ".[dev]"
pytest        # test suite
ruff check .  # lint
```

## License

MIT — see [LICENSE](LICENSE).
