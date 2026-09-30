# Research Second Brain — 에이전트 운영 규칙 (Schema)

이 파일은 이 저장소에서 일하는 LLM 에이전트(Kiro, Claude Code, Codex 등)가 따르는 규칙입니다.
에이전트는 **자료를 읽고, 이해하고, Wiki를 쓰고 고치는 일**을 합니다.
정확해야 하는 일(원본 보존, 중복 탐지, 텍스트 파싱, 목록·기록 생성, 검사)은 `sb` 명령이 합니다.
이 규칙은 사용자와 함께 계속 고쳐 나갑니다. 규칙을 바꾸자는 제안이 있으면 이 파일을 수정하세요.

## 1. 폴더 구조와 계층

볼트(Obsidian에서 여는 폴더)는 `store/`입니다. 모든 경로는 `store/` 기준입니다.

| 경로 | 계층 | 누가 쓰나 | 규칙 |
|---|---|---|---|
| `raw/` | Raw Source | `sb add` | **절대 수정·삭제 금지** |
| `structured/<source_id>.md` | 파싱된 원문 텍스트 | `sb add` | 읽기 전용. `<!-- page N -->`로 쪽이 구분됨 |
| `wiki/papers/`, `wiki/sources/` | Structured Source | 에이전트 | 한 자료당 한 페이지. **원문에서 확인한 내용만** (Source Fact) |
| `wiki/concepts/`, `theories/`, `methods/`, `datasets/`, `technologies/`, `researchers/`, `organizations/`, `topics/`, `overviews/` | Wiki Knowledge | 에이전트 | 여러 자료를 합친 설명 (Synthesis). 모든 서술에 출처 |
| `wiki/questions/` | 열린 질문 | 에이전트 | 논문이 제기했거나 자료 사이에서 드러난 질문 |
| `wiki/synthesis/` | 질의 답변 | 에이전트 | 사용자가 저장하기로 한 답변·비교·분석 |
| `ideas/<종류>/` | Idea / Hypothesis | 에이전트 | **확정 지식 아님.** `wiki/`에 섞지 않음 |
| `index.md` | 전체 목록 | `sb index` | 직접 수정 금지. 질문에 답할 때 먼저 읽음 |
| `log.md` | 작업 기록 | `sb` 명령 | 추가만 가능 |
| `index/sources.json`, `index/projects.json` | 등록부 | `sb` 명령 | 직접 수정 금지 |

`wiki/papers/`는 학술 논문, `wiki/sources/`는 보고서·뉴스·웹·특허·메모 등 나머지 자료입니다.

## 2. 작성 규칙 (모든 페이지 공통)

### 파일명과 링크
- 파일명은 대표 이름을 소문자와 하이픈으로 바꾼 것입니다. 한글 가능. 예: `wiki/concepts/온라인-고객-리뷰.md`, `wiki/theories/expectancy-disconfirmation-theory.md`
- 이론·방법처럼 영문명이 표준인 것은 영문 파일명을 쓰고, 한국어 이름은 frontmatter `aliases`에 넣습니다. 같은 대상에 페이지를 두 개 만들지 않습니다. **새 페이지를 만들기 전에 `index.md`와 `sb search`로 기존 페이지(별칭 포함)를 반드시 찾아봅니다.**
- 링크는 볼트 기준 경로로, 확장자 없이 씁니다: `[[wiki/concepts/온라인-고객-리뷰|온라인 고객 리뷰]]`

### 출처 표기 (가장 중요)
- 형식: `([[wiki/papers/<slug>|저자 외, 연도]], p.128)`. 쪽을 모르면 `§5.2`처럼 절을 씁니다.
- 쪽 번호는 `structured/` 파일의 `<!-- page N -->` 표시에서 읽습니다. **추측해서 쓰지 않습니다.**
- `wiki/` 아래 Synthesis 페이지의 목록 항목(`- ...`)은 **모두** 논문·자료 페이지 링크를 포함해야 합니다. `sb lint`가 검사합니다.
- 원문 인용은 짧게(한두 문장) 하고 `> "..." (p.N)` 형식을 씁니다. 단락 전체를 옮기지 않습니다(저작권).

### 사실·종합·아이디어 구분
- `wiki/papers/`, `wiki/sources/`: 원문에 적힌 것만 씁니다. 해석을 붙이려면 `(해석)`이라고 표시합니다.
- Synthesis 페이지: 여러 자료를 합친 설명은 가능하지만 근거가 된 자료를 모두 인용합니다. **자료 하나에서만 나온 일반화는 "(단일 연구)"라고 표시합니다.**
- 추론, 가설, 연구 아이디어는 `ideas/`에만 씁니다.
- 원문에 없는 수치·효과크기·저자·연도를 지어내지 않습니다. 모르면 비워 두거나 "원문에 없음"이라고 씁니다.

### 증거 수준
자료 페이지 frontmatter의 `evidence_level`(peer_reviewed > conference > preprint > government_report > research_institute_report > industry_report > news > blog > personal_note)을 따릅니다. 뉴스·블로그·메모만으로 Established Findings를 만들지 않습니다. 이런 자료는 "Recent Developments"나 "참고"로만 씁니다.

### 언어
본문은 한국어로 씁니다. 이론·방법·변수명은 처음 나올 때 원어를 함께 씁니다. 예: 기대 불일치 이론(Expectancy-Disconfirmation Theory)

### 기존 내용 수정
- **삭제하지 않습니다.** 새 자료가 기존 서술을 바꾸면 기존 문장을 남기고 옆에 새 근거를 붙입니다.
- 대체된 서술은 `~~기존 문장~~ (superseded: [[새 자료]] — 이유)`로 표시합니다.
- 충돌은 숨기지 않고 `Conflicting Findings`에 양쪽 근거를 모두 적습니다.
- 페이지를 고칠 때마다 그 페이지 맨 아래 `## Change Log`에 한 줄 남깁니다:
  `- 2026-09-29 [[wiki/papers/x|저자 외, 2020]]: strengthen — 이유`
- 효과는 `strengthen`(강화), `narrow`(적용범위 축소), `extend`(새 맥락으로 확장), `contradict`(충돌), `replace`(대체), `unchanged`(변화 없음) 중 하나입니다.

### 사용자 검토 대상 (Human-in-the-Loop)
다음 경우 해당 페이지 frontmatter에 `review: pending`과 `review_reason: ...`을 넣고, 작업 보고에서 따로 알립니다.
- 새 핵심 개념·이론 페이지를 만들었을 때
- `contradict`나 `replace` 판정을 했을 때
- 기존 페이지 내용의 1/3 이상을 고쳤을 때
- 새 Research Gap을 적었을 때
- 잠재력이 높다고 판단한 아이디어를 만들었을 때

사용자가 확인하면 `review: done`으로 바꿉니다.

## 3. 페이지 형식

모든 페이지에 frontmatter가 있어야 하고, `type`과 `title`은 필수입니다. `summary`는 `index.md`에 표시되는 한 줄 설명입니다.

### 3.1 논문 페이지 `wiki/papers/<slug>.md`

```markdown
---
type: paper
title: 논문 제목
aliases: [영문 제목]
authors: [최윤진, 이소현]
year: 2020
venue: Korea Business Review 24(2)
doi: 10.xxxx/xxxx
url:
source_id: src-xxxxxxxxxxxx
raw: raw/src-xxxxxxxxxxxx.pdf
citekey: choi2020jst            # Zotero에서 온 자료만
zotero_key: ABCD1234            # Zotero에서 온 자료만
zotero: zotero://select/library/items/ABCD1234
source_type: journal_article
evidence_level: peer_reviewed
language: ko
keywords: [저자 주제어]
summary: 한 줄 요약
tags: [paper]
---
# 논문 제목

## Summary
원문에 근거한 3~6문장 요약. 해석을 넣지 않습니다.

## Research Context
- 목적, 연구질문, 이론적 배경([[wiki/theories/...]]), 주요 개념([[wiki/concepts/...]]) — 항목마다 p.N

## Research Design
- 연구방법, 연구설계, 데이터(출처·수집일), 표본(N), 연구기간, 분석단위 — 항목마다 p.N

## Variables
- 독립 / 종속 / 매개 / 조절 / 통제. 탐색·질적 연구라 해당 없으면 그렇게 씁니다.

## Analysis
- 분석방법([[wiki/methods/...]]), 모델, 알고리즘, 평가척도(예: perplexity, coherence) — p.N

## Results
- 주요 결과, 유의한 관계, 비유의 관계, 효과 방향, 효과크기 — p.N. 표는 핵심만 옮깁니다.

## Claims
- **C1** 주어 → 대상 | direction: + / − / 0 / mixed | sig: 유의 여부 | effect: 효과크기 | context: 맥락·모집단 | method: 방법 | confidence: high / medium / low | p.N

## Discussion
- 학문적 기여 / 실무적 기여 / 한계 / 향후 연구 — p.N

## Related Pages
- 이 논문이 연결된 개념·이론·방법·Overview·질문 링크

## Parsing Notes
- (필요할 때만) 파싱이 깨져 확인하지 못한 표·그림, 원본 확인이 필요한 부분
```

**서지 정보의 출처:** `sb pending --json`에 `zotero_key`가 있는 자료는 Zotero에서 가져온 것입니다. 제목·저자·연도·학술지·DOI·citekey는 **Zotero 값을 그대로** frontmatter에 쓰고, 파싱된 원문과 다르면 Zotero 값을 따르되 차이를 `## Parsing Notes`에 적습니다. Zotero 정보는 사용자가 관리하므로 에이전트가 Zotero를 고치지 않습니다.

`Claims`는 Knowledge Graph의 재료입니다. 논문의 핵심 주장·발견을 하나씩, 반드시 쪽 번호와 함께 씁니다. 탐색적 연구(토픽모델링 등)라면 "A 여행지에서 B 토픽이 도출됨(가중치 0.317)"처럼 도출 결과를 Claim으로 씁니다.

### 3.2 기타 자료 페이지 `wiki/sources/<slug>.md`
논문 페이지와 같되 `type: source`, 그리고 `organization`, `publication_date`를 씁니다. 해당하지 않는 절(Variables 등)은 뺍니다.

### 3.3 개념 `wiki/concepts/` (요구사항 §9)
frontmatter: `type: concept`, `title`, `aliases`, `sources: [src-...]`, `summary`, `tags`

절: Definition · Theoretical Origin · Related Constructs · Measurement · Common Antecedents · Common Outcomes · Established Findings · Conflicting Findings · Boundary Conditions · Applications · Related Papers · Open Questions · Change Log

### 3.4 이론 `wiki/theories/`
`type: theory`. 절: Definition · Core Propositions · Key Constructs · Applications · Established Findings · Conflicting Findings · Boundary Conditions · Related Papers · Open Questions · Change Log

### 3.5 방법 `wiki/methods/`
`type: method`. 절: Description · Typical Use Cases · Evaluation Metrics · Known Limitations · Applications(어느 연구에서 무엇에 썼나) · Related Papers · Change Log

### 3.6 Overview `wiki/overviews/` (요구사항 §8)
`type: overview`. 논문을 나열하지 말고, **이 분야에서 지금 알려진 것**을 통합해서 씁니다.
절: Current Understanding · Major Theories · Important Variables · Established Findings · Conflicting Findings · Recent Developments · Research Gaps · Open Questions · Key Papers · Change Log

### 3.7 열린 질문 `wiki/questions/`
`type: question`, `status: open / partially-answered / answered`. 절: Question · Why It Is Open(누가 제기했나, 근거) · Related Concepts · Related Papers · Status · Change Log

### 3.8 저장된 답변 `wiki/synthesis/`
`type: synthesis`, `question: 원래 질문`, `date`. 본문은 답변이고, 모든 서술에 출처를 붙입니다.

### 3.9 아이디어 `ideas/<종류>/` (요구사항 §14–§16, §19)
종류: `emerging`, `research-questions`, `hypotheses`, `method-transfer`, `domain-transfer`, `rejected`

```markdown
---
type: idea
epistemic: idea
title: 아이디어 제목
status: detected   # detected → reviewing → promising → developing → accepted / rejected / converted_to_project
kind: method-transfer
detected_by: missing-edge | contradiction | method-transfer | theory-transfer | dataset-gap | scale-gap | temporal-gap | domain-transfer | semantic
confidence: low | medium | high
related_project: proj-xxxx   # 있으면
created: 2026-09-29
---
# 아이디어 제목
## Observed Connection
## Why This Connection Matters
## Existing Evidence      ← 원문 근거만, 모두 인용 (Evidence)
## Interpretation         ← 근거에서 합리적으로 읽어낸 것
## Speculation            ← 검증되지 않은 추측임을 명시
## Research Gap
## Research Question
## Possible Hypothesis
## Possible Method
## Possible Data
## Expected Contribution
## Risks / Limitations
## Supporting Sources
## Confidence
## User Feedback          ← 사용자 평가와 날짜
```

## 4. 작업 절차

### 4.1 Ingest (새 자료 반영)
사용자가 "새 자료 반영해줘", "inbox 처리해줘", "이 논문 넣어줘"라고 하면:

1. 필요하면 등록부터 합니다: 논문은 `sb zotero sync [--collection 이름]`, 그 밖의 파일은 `sb add <파일> --type ...` 또는 `sb add-dir inbox`. 그다음 `sb pending --json`으로 대기 목록을 봅니다.
2. `structured/<source_id>.md`를 **처음부터 끝까지** 읽습니다. 초록만 보고 페이지를 만들지 않습니다.
   - 텍스트가 깨졌으면(2단 섞임, 표 붕괴) 읽을 수 있는 범위만 쓰고 `## Parsing Notes`에 적습니다. 가능하면 `raw/` 원본을 직접 확인합니다.
   - `needs_text` 상태(스캔본 등)는 건너뛰고 사용자에게 알립니다.
3. 같은 연구의 다른 판(프리프린트와 게재본 등)이 이미 있는지 `index.md`에서 확인합니다. 있으면 기존 페이지에 합치고 그렇게 기록합니다.
4. 자료 페이지(`wiki/papers/` 또는 `wiki/sources/`)를 3.1 형식으로 씁니다.
5. 영향받는 개념·이론·방법·데이터셋을 정합니다. 기준은 **이 자료에서 핵심적으로 다루는 것**이고, 지나가듯 언급된 것은 페이지를 만들지 않습니다.
6. 각 대상에 대해:
   - 기존 페이지가 있으면 읽고, 새 자료와 비교해 효과(strengthen/narrow/extend/contradict/replace/unchanged)를 판정한 뒤 해당 절에 반영하고 Change Log를 남깁니다.
   - 없으면 새로 만듭니다. 정의 같은 절은 **이 자료에 근거가 있을 때만** 채우고, 나머지는 비워 둡니다.
7. 관련 Overview를 갱신합니다. 없고 주제가 뚜렷하면 새로 만들고 `review: pending`을 붙입니다. 목록이 아니라 통합 서술로 씁니다.
8. 향후 연구·한계·자료 사이의 공백에서 열린 질문을 `wiki/questions/`에 만들거나 갱신합니다.
9. 자료 페이지의 `Related Pages`와 대상 페이지들의 `Related Papers`가 서로 연결되게 합니다. **연결되지 않은 자료 페이지는 반영된 것이 아닙니다.**
10. `sb index`를 실행한 뒤 `sb lint`를 실행하고, error가 없어질 때까지 고칩니다. warning도 가능한 한 고칩니다.
11. `sb done <source_id> --page wiki/papers/<slug> --touched <페이지> ... --effect "<페이지>: <효과> — <이유>" ...`를 실행합니다.
12. 사용자에게 보고합니다: 한 줄 요약, 만든 페이지와 고친 페이지, 판정한 효과, 검토가 필요한 항목, 파싱 문제.

자료 하나는 보통 5~15개 페이지를 건드립니다. 여러 자료를 한꺼번에 처리할 때는 **하나씩 끝까지** 처리합니다.

### 4.2 Query (질문에 답하기)
1. `index.md`를 먼저 읽고, 관련 페이지를 읽고, 링크를 따라갑니다. 키워드는 `sb search`나 `grep -rn`으로 찾습니다(Obsidian 검색창은 사용자용이라 에이전트는 쓸 수 없습니다). `aliases`에 있는 다른 이름·영문명으로도 검색합니다.
2. Wiki에 있는 내용으로만 답하고, 모든 주장에 출처를 붙입니다.
3. Wiki가 부족하면 해당 자료의 `structured/` 원문을 읽습니다. 그래도 없으면 **"이 Wiki에는 해당 자료가 없습니다"**라고 말합니다. 사용자가 요청하지 않으면 웹 검색이나 일반 지식으로 채우지 않습니다. 일반 지식을 쓰면 그렇다고 분명히 표시합니다.
4. 원문을 읽어 새로 알게 된 사실은 해당 페이지에 반영합니다.
5. 가치 있는 답변(비교표, 종합 분석)은 `wiki/synthesis/`에 저장할지 사용자에게 묻습니다.
6. `sb log query "질문 요약" -b "읽은 페이지: ..." -b "저장: ..."`로 기록합니다.

### 4.3 Lint (점검)
사용자가 점검을 요청하거나 자료를 10개쯤 반영할 때마다:
1. `sb lint --log`로 기계적 문제(끊어진 링크, 출처 없는 항목, 연결 없는 페이지, 쪽 번호 없는 Claim, `wiki/`에 섞인 아이디어)를 고칩니다.
2. 의미 점검: 페이지 사이의 모순, 더 새로운 자료에 대체된 서술, 별칭이 다른 중복 페이지(합치고 한쪽을 링크로 남김), 자주 언급되지만 페이지가 없는 개념, 오래된 근거만 있는 영역을 찾습니다.
3. 고친 내용과 사용자가 판단할 것을 보고하고 `sb log lint ...`로 기록합니다.

### 4.4 Synapse / Idea (연결과 아이디어 찾기)
사용자가 요청할 때만 합니다("연결 찾아줘", "아이디어 뽑아줘").
1. Overview, Claims, 열린 질문, `index/projects.json`(사용자의 연구 프로젝트)을 읽습니다.
2. 요구사항 §13의 유형으로 후보를 찾습니다:
   - Missing Edge: A→B, B→C는 있는데 A→C 연구가 없음
   - Contradiction: 같은 관계에 대해 다른 결과
   - Method / Theory / Domain Transfer: 다른 분야의 방법·이론·개념을 옮겨 쓸 가능성
   - Dataset / Scale / Temporal Gap: 새 데이터, 분석 수준 확장, 최근 연구 공백
   - Semantic: 내용은 비슷한데 연결되지 않은 자료
3. 후보마다 3.9 형식으로 `ideas/<종류>/`에 씁니다. Evidence·Interpretation·Speculation을 반드시 나눕니다.
4. 사용자 프로젝트와 관련된 것을 먼저 보여줍니다.
5. `wiki/` 페이지는 고치지 않습니다. 필요하면 해당 페이지의 Research Gaps나 Open Questions 절에 링크만 겁니다.
6. 사용자가 평가하면 `status`와 `User Feedback`을 갱신합니다. rejected는 `ideas/rejected/`로 옮기고 이유를 남깁니다. 반복되는 거절 이유는 이 파일의 규칙으로 추가할지 제안합니다.
7. `sb log idea ...`로 기록합니다.

## 5. 하지 말 것
- `raw/`, `structured/`, `index.md`, `index/*.json` 직접 수정
- 초록·메타데이터·파일명만 보고 자료 페이지 작성. 메타데이터만 있는 자료는 사용자에게 알리고 대기
- 출처 없는 서술, 추측한 쪽 번호, 지어낸 수치
- 아이디어·가설을 `wiki/`에 사실처럼 기록
- 기존 서술 삭제, 충돌 숨기기
- 이유 없이 한 번에 여러 자료를 대충 처리
