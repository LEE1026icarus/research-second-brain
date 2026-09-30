# Research Second Brain 🧠

논문·보고서·뉴스·메모를 넣으면 **LLM 에이전트가 읽고**, 출처가 달린 Obsidian Wiki를 계속 고쳐 나가는 개인 연구용 Second Brain입니다.
[Karpathy의 LLM Wiki 패턴](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)을 따르되, 연구용으로 쪽 단위 출처, Claim, 사실·종합·아이디어 분리, 증분 업데이트 판정, 사용자 검토를 규칙으로 더했습니다.

## 역할 분담

| 누가 | 하는 일 |
|---|---|
| **LLM 에이전트** (Kiro, Claude Code, Codex 등) | 원문 읽기, 논문 페이지 작성, 개념·이론·방법·Overview 갱신, 강화·충돌 판정, 질문 답변, 아이디어 생성 — **규칙은 [`AGENTS.md`](AGENTS.md)** |
| **`sb` 명령** (이 저장소의 코드) | 원본 보존, 중복 탐지, 쪽 번호가 붙은 텍스트 파싱, `index.md`·`log.md` 생성, 링크·출처·아이디어 누출 검사(`sb lint`) |
| **사용자** | 자료 고르기, 질문하기, `review: pending` 항목 검토 |

정규식 규칙으로 논문을 요약하지 않습니다. 이해가 필요한 일은 LLM이, 정확해야 하는 일은 코드가 합니다.

## 시작하기

```bash
git clone https://github.com/LEE1026icarus/research-second-brain.git
cd research-second-brain
python -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e .
sb init            # store/ 볼트 생성
```

Obsidian에서 **`store/` 폴더를 볼트로 엽니다.** (`store/.obsidian/app.json`에 링크 설정이 들어 있습니다.)

### 에이전트 연결
- **Kiro**: `.kiro/steering/second-brain.md`가 `AGENTS.md`를 자동으로 불러옵니다.
- **Claude Code**: `CLAUDE.md`가 `AGENTS.md`를 불러옵니다.
- **Codex 등**: `AGENTS.md`를 바로 읽습니다.

### 사용 예
```text
나:  inbox에 논문 넣었어. 반영해줘.
에이전트: sb add-dir inbox → structured/ 원문 읽기 → wiki 페이지 작성·갱신
          → sb index → sb lint → sb done → 변경 요약과 검토 항목 보고
나:  기대 불일치 이론을 쓴 연구들의 공통 한계는?
에이전트: index.md → 관련 페이지 → 출처와 함께 답변 (Wiki에 없으면 없다고 답함)
나:  위키 점검해줘 / 연결 가능한 연구 아이디어 찾아줘
```

## `sb` 명령

| 명령 | 설명 |
|---|---|
| `sb add <파일> [--type journal_article]` | 원본을 `raw/`에 복사, 중복 확인, `structured/<id>.md`에 `<!-- page N -->`가 붙은 텍스트 생성 |
| `sb add-dir inbox` | 폴더 안의 지원 파일 전부 등록 |
| `sb pending [--json]` | 에이전트가 아직 반영하지 않은 자료 |
| `sb done <id> --page ... --touched ... --effect ...` | 반영 완료 표시와 `log.md` 기록 |
| `sb index` | frontmatter로 `index.md` 재생성 |
| `sb lint [--json] [--log]` | 끊어진 링크, 출처 없는 서술, 쪽 번호 없는 Claim, 연결 없는 자료, `wiki/`에 섞인 아이디어, frontmatter 오류 검사. error가 있으면 exit 1 |
| `sb verify [--page ...]` | 인용문·수치가 인용한 쪽에 실제로 있는지 원문과 대조. 지어낸 인용은 error |
| `sb digest [--days 7] [--save]` | 이번 주 새 자료, 고친 페이지, 충돌·대체 판정, 검토 대기 요약 |
| `sb refs` | OpenAlex에서 참고문헌 목록을 받아 "내 논문들이 많이 인용하는데 나는 없는 논문" 추천 (`reports/reading-suggestions.md`) |
| `sb graph` | Claims·인용으로 `kg/graph.json`을 만들고 충돌·빠진 관계·방법/이론 이전·근거 공백 후보를 뽑음 (`reports/synapse-candidates.md`) |
| `sb discover [--days 90]` | 내 논문이나 프로젝트 핵심 문헌을 새로 인용한 논문, 프로젝트 키워드의 최근 논문 (`reports/discover-<날짜>.md`) |
| `sb log <kind> <제목> -b ...` | `log.md`에 기록 추가 |
| `sb search <검색어>` | 키워드 검색 |
| `sb status` | 자료·페이지 수와 검토 대기 목록 |
| `sb project add "제목" --rq ... --keywords ... --refs <DOI>` / `list` | 내 연구 프로젝트 등록 (아이디어 우선순위, 새 논문 알림용) |
| `sb zotero sync [-c 컬렉션] [-t 태그]` | Zotero에서 논문 가져오기 (서지 정보 + PDF + 내 하이라이트·메모). 여러 번 실행해도 안전 |
| `sb zotero collections` | Zotero 컬렉션 목록 |

지원 형식: PDF(pypdf), TXT/MD(쪽 표시 인식), HTML. PDF는 머리말·꼬리말의 쪽 번호(예: 121~141)를 찾아 `<!-- page 121 -->`처럼 **학술지 인쇄 쪽 번호**로 표시합니다. 스캔본은 `needs_text`로 표시됩니다. 더 나은 파서(OpenDataLoader PDF, HWP 등)는 `src/secondbrain/parsing.py`에 추가할 수 있습니다.

## Zotero 연동

논문은 Zotero에서 관리하고, 이 볼트는 Zotero를 **읽기만** 합니다.

1. Zotero 데스크톱 → 설정 → 고급 → **"Allow other applications on this computer to communicate with Zotero"** 켜기
2. Zotero를 켜 둔 상태에서:
   ```bash
   sb zotero collections                 # 컬렉션 확인
   sb zotero sync -c "Tourism" --dry-run # 가져올 목록 미리 보기
   sb zotero sync -c "Tourism"           # 가져오기
   ```
3. 에이전트에게 "대기 중인 논문 반영해줘"라고 말합니다.

- 제목·저자·연도·학술지·DOI·태그·citekey(Better BibTeX 포함)는 Zotero 값을 씁니다. 에이전트가 원문에서 추측하지 않습니다.
- PDF 첨부가 없는 항목은 서지 정보만 등록되고(`needs_text`), 나중에 Zotero에 PDF를 붙인 뒤 다시 `sync`하면 자동으로 이어집니다.
- 같은 논문을 `sb add`로 먼저 넣었어도 DOI·제목으로 찾아 연결하므로 중복되지 않습니다.
- 논문 페이지에 `zotero://select/...` 링크가 들어가서, Obsidian에서 누르면 Zotero의 해당 항목이 열립니다.
- Zotero 앱 없이 쓰려면 `--mode web`과 환경변수 `ZOTERO_API_KEY`, `ZOTERO_USER_ID`를 씁니다. 이때 PDF는 Zotero 저장소에 동기화된 것만 받을 수 있습니다. 그룹 라이브러리는 `--group <ID>`.

## Zotero 하이라이트·메모

Zotero PDF 리더에서 칠한 하이라이트와 메모도 `sync`할 때 쪽 번호와 함께 `structured/<id>.annotations.md`로 가져옵니다. 에이전트는 하이라이트한 부분을 우선 반영하고, 메모는 원문 사실이 아닌 "내 메모"로 구분해 논문 페이지의 `## My Highlights`에 씁니다. 이미 반영한 논문에 하이라이트를 더하면 `sb pending`에 `annotations-updated`로 다시 나타납니다.

## 인용 검증 (`sb verify`)

LLM이 쓴 위키에서 가장 위험한 것은 그럴듯한 가짜 출처입니다. `sb verify`는 `(p.128)`처럼 쪽을 인용한 모든 줄에서 **따옴표 안 인용문과 수치**를 뽑아 원문의 그 쪽에 있는지 확인합니다.
- 원문 어디에도 없는 인용문 → error (`quote-not-found`)
- 다른 쪽에 있는 인용문·수치 → warning, 실제 쪽 번호를 알려줌
- 원문에 없는 수치 → warning. 계산한 값이면 `(계산)` 표시
- 말을 바꿔 쓴 서술(의역)은 판단하지 못합니다. 그 부분은 사용자 검토가 필요합니다.

## Dataview 대시보드

`sb init`이 `store/dashboards/`에 표 4개를 만듭니다: **선행연구 비교표**, **연구 지형**(이론·방법·설계·국가·연도별 논문 수), **검토 대기**, **질문과 아이디어**. Obsidian 커뮤니티 플러그인 [Dataview](https://github.com/blacksmithgu/obsidian-dataview)가 필요합니다.
논문 페이지 frontmatter의 `theories`, `methods`, `design`, `data_type`, `sample_size`, `country`, `domain` 등을 에이전트가 채우므로, "토픽모델링을 쓰고 종단 데이터를 쓴 논문" 같은 조건 검색을 표로 할 수 있습니다. 새 템플릿으로 바꾸려면 `sb init --update-dashboards`.

## 인용 관계·새 논문 (OpenAlex)

- `sb refs`: 각 논문의 참고문헌 목록을 OpenAlex에서 받아 **내 라이브러리 안의 인용 관계**와 **읽을 만한 논문**(내 논문 여러 편이 인용하는데 내가 없는 논문)을 만듭니다. 국내 학술지처럼 OpenAlex에 참고문헌이 없는 논문은 에이전트가 논문 페이지에 `## References`를 적으면 그것으로 찾습니다.
- `sb discover`: 내 논문이나 프로젝트 핵심 문헌(`sb project add --refs <DOI>`)을 **최근에 인용한 논문**과 프로젝트 키워드의 최근 논문을 찾습니다. 한 번 보여준 논문은 다음에 빼고(`--all`로 다시 보기), 자동 등록은 하지 않습니다.
- 키 없이 가볍게 쓸 수 있고, 많이 쓰면 [OpenAlex 무료 API 키](https://openalex.org)를 `OPENALEX_API_KEY`에 넣으세요. OpenAlex 검색이 일시적으로 막히면 DOI 조회만 진행하고 그렇다고 알려줍니다.

## Knowledge Graph와 Synapse 후보 (`sb graph`)

논문 페이지의 `## Claims`(예: `[[개념 A]] → [[개념 B]] | direction: +`)와 인용 관계로 그래프를 만들고, 다음 후보를 뽑아 `reports/synapse-candidates.md`에 씁니다.
- **충돌**: 같은 A→B 관계인데 논문마다 방향이 다름
- **빠진 관계**: A→B, B→C는 있는데 A→C를 다룬 논문이 없음
- **방법·이론 이전**: 한 분야에서만 쓰인 방법·이론
- **근거 공백**: 어떤 이론의 연구가 모두 횡단 설계뿐 / 최근 몇 년 연구가 없음

이 후보는 기계적으로 뽑은 것이라 그대로 아이디어가 아닙니다. "아이디어 찾아줘"라고 하면 에이전트가 후보를 읽고 쓸 만한 것만 `ideas/`에 근거와 함께 씁니다.

## 검색

| 누가 | 무엇으로 |
|---|---|
| 사용자 | **Obsidian 기본 검색**(Ctrl/Cmd+Shift+F). 필요하면 커뮤니티 플러그인 [Omnisearch](https://github.com/scambier/obsidian-omnisearch)(가중치 검색, PDF 포함)나 [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections)(로컬 임베딩 의미 검색) |
| 에이전트 | `index.md` → 링크 따라가기 → `sb search` / `grep`. 별칭(`aliases`)으로도 검색 |

사용자용 검색은 Obsidian 기능으로 충분해서 따로 만들지 않았습니다. Obsidian 플러그인은 에이전트가 호출할 수 없으므로, 페이지가 수천 개로 늘어 에이전트 검색이 부족해지면 그때 의미 검색을 `sb`에 추가합니다.

## 볼트 구조

```
store/                  ← Obsidian 볼트
├── index.md            # 전체 목록 (sb index)
├── log.md              # 작업 기록 (추가만)
├── raw/                # 원본 (수정 금지)
├── structured/         # 쪽 번호가 붙은 파싱 텍스트
├── wiki/
│   ├── papers/ sources/            # 자료별 페이지 (원문 사실만)
│   ├── concepts/ theories/ methods/ datasets/ technologies/
│   ├── researchers/ organizations/ topics/ overviews/   # 종합 지식 (모든 서술에 출처)
│   ├── questions/                  # 열린 질문
│   └── synthesis/                  # 저장한 질의 답변
└── ideas/              # 아이디어·가설 (확정 지식 아님)
```

## 저작권과 공개 저장소
이 저장소는 public이므로 `inbox/`, `raw/`, `structured/`, 생성된 Wiki 페이지는 `.gitignore`로 제외했습니다.
Wiki를 git으로 버전 관리하려면 저장소를 private로 바꾸고 `.gitignore`의 "Generated vault content" 부분을 지우세요.

## 개발

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

- [`AGENTS.md`](AGENTS.md) — 에이전트 규칙 (페이지 형식, 작업 절차)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 구조
- [`docs/REQUIREMENTS_MAP.md`](docs/REQUIREMENTS_MAP.md) — 요구사항별 구현 상태
- [`docs/llm-wiki-guide.html`](docs/llm-wiki-guide.html) — 기능을 쉽게 설명한 한 장짜리 안내 (브라우저로 열기)

MIT License.
