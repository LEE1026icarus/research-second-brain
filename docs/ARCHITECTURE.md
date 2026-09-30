# Architecture

## 원칙: 이해는 LLM, 확인은 코드

```
            사용자 ──(자료, 질문, 검토)──┐
                                        ▼
 inbox/ ──sb add──▶ raw/ + structured/ ──읽기──▶ LLM 에이전트 ──쓰기──▶ wiki/, ideas/
                    (보존·중복·파싱)             (AGENTS.md 규칙)          │
                                                     ▲                    │
                                     sb index / sb lint / sb done ◀───────┘
                                     (목록·검사·기록 — 틀리면 에이전트가 고침)
```

- 에이전트는 [`AGENTS.md`](../AGENTS.md)를 따릅니다. 페이지 형식, 출처 표기, 증분 업데이트 판정, 검토 대상, Ingest·Query·Lint·Idea 절차가 모두 이 파일에 있습니다.
- 코드는 지식을 쓰지 않습니다. 에이전트가 쓴 결과를 목록으로 만들고, 기록하고, 검사합니다.

## 계층 (요구사항 §2.1)

| 계층 | 위치 | 작성 |
|---|---|---|
| Raw Source | `raw/` | `sb add` (복사만, 수정 금지) |
| 파싱 텍스트 | `structured/<id>.md` (`<!-- page N -->`) | `sb add` |
| Structured Source | `wiki/papers/`, `wiki/sources/` (원문 사실만, 쪽 번호 필수) | 에이전트 |
| Wiki Knowledge | `wiki/concepts/` 등 (여러 자료 종합, 모든 항목에 출처) | 에이전트 |
| Idea | `ideas/` (Evidence·Interpretation·Speculation 구분) | 에이전트 |

## 코드 구성

```
src/secondbrain/
├── cli.py              `sb` 명령
├── parsing.py          파일 → 쪽별 텍스트 (pypdf, text, html; 파서 추가 지점)
├── agents/ingestion.py 등록: 해시, 중복 탐지, raw 복사, structured 생성, 상태 pending
├── vault.py            index.md 생성, log.md 기록, lint, 검색
├── store/repository.py sources.json, projects.json, graph.json
├── models/             Source(상태 포함), Claim, Node/Edge, Idea, ResearchProject, enums
├── wiki/page.py        frontmatter/절 파싱 도우미
└── config.py           볼트 경로
```

## `sb lint` 검사 항목

| 코드 | 수준 | 내용 |
|---|---|---|
| `frontmatter` | error | frontmatter 없음, YAML 오류, `type`/`title` 누락 |
| `broken-link` | error | 존재하지 않는 페이지로의 링크 |
| `idea-in-wiki` | error | `wiki/` 안의 아이디어 페이지 (§15) |
| `idea-without-source` | error | 근거 자료 링크가 없는 아이디어 (§19) |
| `missing-source-page` | error | compiled인데 자료 페이지가 없음 |
| `uncited` | warn | 종합 페이지의 목록 항목에 자료 링크가 없음 (§2.3) |
| `claim-without-page` | warn | 쪽·절 표시가 없는 Claim |
| `unconnected-source` | warn | 어떤 개념·이론·방법·Overview에서도 링크되지 않은 자료 페이지 |
| `orphan` | warn | 들어오는 링크가 없는 페이지 |
| `needs-text` | warn | 텍스트를 뽑지 못한 자료 (스캔본 등) |
| `needs-review` / `pending-source` / `index-stale` | info | 검토 대기, 미반영 자료, 목록 갱신 필요 |

## 앞으로 붙일 부분
- **파서:** `parsing.py`의 `_PARSERS`에 OpenDataLoader PDF, Docling, HWP 파서를 추가하면 호출부 변경 없이 적용됩니다.
- **Knowledge Graph (Phase 3):** 논문 페이지의 `## Claims` 형식이 고정되어 있으므로, 이를 파싱해 `kg/graph.json`의 Node/Edge를 만드는 명령을 추가합니다.
- **자동화 (Phase 2):** Gmail·Scholar Alert, 폴더 감시는 `sb add`까지만 자동으로 하고, 반영은 에이전트가 합니다. 완전 자동이 필요하면 에이전트를 비대화형으로 실행합니다(예: Kiro CLI `--no-interactive`).
- **MCP (Phase 6):** `vault.py`의 검색·lint·목록 함수를 MCP 도구로 노출합니다.
