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
| `sb log <kind> <제목> -b ...` | `log.md`에 기록 추가 |
| `sb search <검색어>` | 키워드 검색 |
| `sb status` | 자료·페이지 수와 검토 대기 목록 |
| `sb project add/list` | 내 연구 프로젝트 등록 (아이디어 우선순위용) |

지원 형식: PDF(pypdf), TXT/MD(쪽 표시 인식), HTML. 스캔본은 `needs_text`로 표시됩니다. 더 나은 파서(OpenDataLoader PDF, HWP 등)는 `src/secondbrain/parsing.py`에 추가할 수 있습니다.

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

MIT License.
