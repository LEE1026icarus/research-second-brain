# Requirements → Implementation Map

Legend: ✅ implemented (Phase 1) · 🧩 modeled/scaffolded (data structures &
extension points in place, agent logic in a later phase) · 📅 planned.

| § | Requirement | Status | Where |
|---|-------------|--------|-------|
| 1 | Project overview / goal | ✅ | `README.md` |
| 2.1 | Raw / Structured / Wiki separation; originals never modified | ✅ | `config.py`, `agents/ingestion.py` (copy, not move) |
| 2.2 | Incremental update with strengthen/narrow/extend/contradict/replace/unchanged | ✅ | `models/enums.py:UpdateEffect`, `wiki/agent.py` |
| 2.3 | Provenance / traceability (file, title, author, year, DOI, URL, page, section, quote) | ✅ | `models/provenance.py` |
| 2.4 | Fact vs. synthesis vs. idea separation | ✅ | `models/enums.py:Epistemic`; ideas kept out of wiki |
| 3.1 | Supported source types (paper, report, news, web, patent, dataset, note, …) | ✅ | `models/enums.py:SourceType`, ext→type map |
| 3.2 | Google Scholar Alert parsing; metadata-only fallback | 🧩 | `ingest_metadata_only`; parser 📅 Phase 2 |
| 3.3 | Gmail-based auto collection | 📅 | Phase 2 |
| 3.4 | Web & news ingest with distinct source type / evidence level | 🧩 | `SourceType.NEWS/WEBPAGE` + evidence map; fetcher 📅 Phase 2 |
| 4 | Source metadata fields | ✅ | `models/source.py` |
| 5 | Paper-specific extraction (bibliographic … discussion) | ✅ | `models/extraction.py`, `agents/extraction.py` |
| 6 | Wiki page types (papers/concepts/theories/…/questions) | ✅ | `config.py`, `wiki/store.py` |
| 7 | Wiki page generation procedure (extract→compare→update→cross-link→overview→open-q) | ✅ | `wiki/agent.py:integrate` |
| 8 | Integrated overview pages | ✅ | `wiki/templates.py:OVERVIEW_SECTIONS`, `_update_overviews` |
| 9 | Concept pages (cumulative) | ✅ | `wiki/templates.py:CONCEPT_SECTIONS`, `_update_concept_page` |
| 10 | Knowledge graph node types | 🧩 | `models/graph.py:Node`, `NodeType` |
| 11 | Explicit relationship (edge) types | 🧩 | `models/graph.py:Edge`, `EdgeType` |
| 12 | Claim-level knowledge (source/evidence/direction/significance/…) | 🧩 | `models/claim.py`; rendered on paper pages ✅ |
| 13 | Synapse engine (semantic/missing-edge/contradiction/transfer/gaps) | 📅 | Phase 4 |
| 14 | Idea engine output template | 🧩 | `models/idea.py` fields = §14 template |
| 15 | Idea/knowledge separation (ideas/ folders) | ✅ | `store/ideas/*`, never written to wiki |
| 16 | Idea lifecycle states | 🧩 | `models/enums.py:IdeaStatus` |
| 17 | Agent role separation | ✅/🧩 | Ingestion+Extraction+Wiki ✅; Graph/Synapse/Idea/Reviewer 📅 |
| 18 | Wiki agent conservative operation | ✅ | `wiki/agent.py` (append + cite, no deletion, contradictions surfaced) |
| 19 | Idea agent operation (evidence/interpretation/speculation) | 🧩 | `models/idea.py` fields |
| 20 | Source trust / evidence levels | ✅ | `EvidenceLevel` + `SOURCE_TYPE_TO_EVIDENCE` |
| 21 | Duplicate detection (DOI/title/author/year/URL/hash) | ✅ | `store/repository.py:find_duplicate`, `Source.fingerprints` |
| 22 | Git-based versioning of wiki changes | ✅ | plain markdown/JSON store |
| 23 | Obsidian compatibility (wikilink/backlink/tags/frontmatter) | ✅ | `wiki/page.py` |
| 24 | Knowledge graph visualization | 📅 | Phase 6 |
| 25 | Keyword / semantic / graph search | ✅/📅 | keyword ✅ (`search.py`); semantic & graph 📅 |
| 26 | Natural-language Q&A with sources | 📅 | Phase 6 |
| 27 | Automatic digest | ✅ | `digest.py`, `sb digest` |
| 28 | Research gap detection | 📅 | Phase 4 |
| 29 | Personal research context / projects | ✅ | `models/project.py`, `sb project` |
| 30 | MCP / external agent interface | 📅 | Phase 6 |
| 31 | Folder watcher auto-ingest | ✅/📅 | `sb ingest-dir` ✅; live watcher 📅 |
| 32 | Human-in-the-loop review | 🧩 | `WikiUpdate` surfaces effects/contradictions for review |
| 33 | Phased implementation plan | ✅ | this document |
| 34 | End-to-end target flow | ✅/📅 | ingest→raw→extract→compare→update ✅; graph→synapse→ideas 📅 |

## Phase status

- **Phase 1 — Core Wiki:** ✅ implemented & tested.
- **Phase 2 — Automation** (Gmail/Scholar, web/news fetch, live watcher): 📅
- **Phase 3 — Knowledge Graph** (node/edge build, similarity, communities): 🧩 models ready.
- **Phase 4 — Synapse** (missing edges, transfer, gap detection): 📅
- **Phase 5 — Idea Engine** (RQ/hypothesis/method/data generation, evaluation): 🧩 models ready.
- **Phase 6 — Interface** (graph UI, semantic search, chat, MCP/API): 📅
