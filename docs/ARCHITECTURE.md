# Architecture

## Layers (spec §2.1)

The system strictly separates three layers of knowledge and never lets a
higher layer mutate a lower one.

```
┌─────────────────────────────────────────────────────────────┐
│ WIKI KNOWLEDGE   store/wiki/*.md   synthesized, cross-linked  │  ← generated
├─────────────────────────────────────────────────────────────┤
│ STRUCTURED       store/structured/*.json   extracted fields   │  ← generated
├─────────────────────────────────────────────────────────────┤
│ RAW              store/raw/*   original bytes (immutable)     │  ← never modified
└─────────────────────────────────────────────────────────────┘
```

Bookkeeping (`Source` records, the graph, projects) lives in `store/index/` and
`store/kg/`. Research **ideas** live in `store/ideas/` and are deliberately kept
out of the wiki so speculation is never mistaken for confirmed knowledge
(spec §4, §15).

## Package map

```
src/secondbrain/
├── config.py            StoreConfig + path resolution (SECOND_BRAIN_STORE / ./store)
├── models/              Pydantic models = the shared vocabulary
│   ├── enums.py         SourceType, EvidenceLevel, UpdateEffect, NodeType, EdgeType, …
│   ├── provenance.py    Provenance (source → title/doi/page/quote)
│   ├── source.py        Source (metadata §4 + dedup fingerprints §21)
│   ├── extraction.py    PaperExtraction (the §5 field set)
│   ├── claim.py         Claim (subject→object, direction, significance §12)
│   ├── graph.py         Node / Edge (§10, §11)
│   ├── idea.py          Idea (§14 template, §16 lifecycle, §19 epistemic split)
│   └── project.py       ResearchProject (§29)
├── store/repository.py  JSON persistence (Source/Extraction/Graph/Project repos)
├── agents/
│   ├── ingestion.py     IngestionAgent  – collect, hash, dedup, preserve raw
│   └── extraction.py    ExtractionAgent + Extractor protocol + HeuristicPaperExtractor
├── wiki/
│   ├── page.py          WikiPage (frontmatter + H2 sections + wikilinks)
│   ├── store.py         WikiStore (locate/load/save by page type)
│   ├── templates.py     Canonical section skeletons (§8, §9)
│   └── agent.py         WikiAgent – the incremental update engine (§7)
├── pipeline/            IngestPipeline – orchestrates the §34 flow
├── search.py            keyword_search (§25)
├── digest.py            build_digest (§27)
└── cli.py               `sb` command-line interface
```

## Ingest data flow (spec §7, §34)

```
sb ingest FILE
   │
   ▼
IngestionAgent.ingest_file
   • sha256 hash, dedup via SourceRepository.find_duplicate (DOI / hash / URL / title)
   • copy raw bytes to store/raw/<id><ext>   (original untouched)
   • persist Source with evidence_level derived from source_type
   │
   ▼
ExtractionAgent.extract
   • read_source_text (pypdf for PDF; text for md/txt/html)
   • Extractor.extract → PaperExtraction (best-effort; missing = empty, never fabricated)
   • persist store/structured/<id>.json
   │
   ▼
WikiAgent.integrate
   • write/update paper page (frontmatter + sectioned body + provenance)
   • detect relevant concepts → update concept pages (append with citations)
   • classify UpdateEffect (strengthen/extend/contradict/…)
   • update topic overview
   • turn "future work" into open-question pages
   • returns WikiUpdate (feeds the digest)
```

## Extension points (Phases 2–6)

The design keeps later phases as *additive* plug-ins:

- **LLM extraction** — implement the `Extractor` protocol and pass it to
  `ExtractionAgent` / `IngestPipeline`. No caller changes.
- **Knowledge Graph** — `GraphRepository`, `Node`, `Edge`, and `Claim` already
  exist; a `GraphAgent` builds nodes/edges from extractions after wiki
  integration.
- **Synapse / Idea engines** — consume the graph and write `Idea` objects into
  `store/ideas/`; models and lifecycle states are already defined.
- **Automation** — Gmail/Scholar ingest and a folder watcher feed the same
  `IngestPipeline` (the `sb ingest-dir` command is the manual equivalent).
- **Interfaces** — an MCP/API server exposes read/search over the same
  repositories; the store is plain files so a UI can read it directly.

## Why plain files

Markdown + JSON on disk makes the whole knowledge base **Git-versionable**
(spec §22) — every change is a diff showing what changed and (via provenance)
which source caused it — and **Obsidian-compatible** (spec §23) with
frontmatter, tags, and `[[wikilinks]]`.
