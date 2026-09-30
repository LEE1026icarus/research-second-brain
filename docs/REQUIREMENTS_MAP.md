# 요구사항 → 구현 상태

표시: ✅ 동작함 · 📝 에이전트 규칙(`AGENTS.md`)으로 정의됨 — 에이전트가 수행, `sb lint`가 일부 검사 · 🧩 데이터 모델만 있음 · 📅 계획

"📝"는 코드가 아니라 LLM 에이전트가 규칙을 따라 수행한다는 뜻입니다. 품질은 사용하는 모델과 규칙에 달려 있습니다.

| § | 요구사항 | 상태 | 위치 |
|---|---|---|---|
| 2.1 | Raw / Structured / Wiki 분리, 원본 수정 금지 | ✅ | `sb add`(복사), AGENTS.md §1 |
| 2.2 | 증분 업데이트와 효과 판정 | 📝 | AGENTS.md §2 "기존 내용 수정", Change Log, `sb done --effect` |
| 2.3 | 출처 추적 (쪽·절·인용) | ✅ / 📝 | `structured/`의 쪽 표시, 출처 형식 규칙, `sb lint`의 `uncited`·`claim-without-page` |
| 2.4 | 사실·종합·아이디어 구분 | 📝 / ✅ | AGENTS.md §2, `sb lint`의 `idea-in-wiki`·`idea-without-source` |
| 3.1 | 자료 유형 | ✅ / 📅 | PDF·TXT·MD·HTML ✅, DOCX·PPTX·XLSX·HWP 파서 📅 |
| 3.2–3.4 | Scholar Alert, Gmail, 웹·뉴스 수집 | ✅ / 📅 | 알림 대체: `sb discover`(내 논문·핵심 문헌 피인용, 키워드). Gmail·웹 수집 📅 |
| (추가) | Zotero 연동 | ✅ | `sb zotero sync`: 서지 정보·PDF·하이라이트·메모, 재실행 안전, PDF 나중 첨부 처리 |
| (추가) | 인용 검증 | ✅ | `sb verify`: 인용문·수치를 인용 쪽 원문과 대조 |
| 4 | Source 메타데이터 | ✅ | `models/source.py`, `index/sources.json` |
| 5 | 논문 정보 추출 | 📝 | AGENTS.md §3.1 논문 페이지 형식 |
| 6 | Wiki 페이지 유형 | ✅ | `wiki/` 폴더 (+ `sources/`, `synthesis/`) |
| 7 | Ingest 절차 | 📝 | AGENTS.md §4.1 (12단계) |
| 8, 9 | Overview, Concept 페이지 | 📝 | AGENTS.md §3.3–3.6 |
| 10, 11 | Knowledge Graph Node/Edge | ✅ | `sb graph`: Claims·페이지 링크·인용으로 `kg/graph.json` (paper/concept/theory/method/dataset/claim/variable, predicts·based_on·uses_method·cites 등) |
| 12 | Claim 단위 지식 | 📝 / 🧩 | 논문 페이지 `## Claims` 고정 형식, `models/claim.py` |
| 13 | Synapse Engine | ✅ / 📝 | `sb graph`가 충돌·빠진 관계·방법/이론 이전·근거/시간 공백 후보를 뽑고, 에이전트가 판단 (AGENTS.md §4.4). 의미 유사도 후보는 📅 |
| 14–16 | Idea 형식, 분리, Lifecycle | 📝 / ✅ | AGENTS.md §3.9, `ideas/` 폴더, `sb lint` |
| 17 | Agent 역할 분리 | 📝 | 한 에이전트가 AGENTS.md의 절차별로 수행. Reviewer 역할은 `sb lint` + 사용자 검토 |
| 18, 19 | 보수적 Wiki 작성 / 탐색적 Idea | 📝 | AGENTS.md §2, §5 |
| 20 | 증거 수준 | ✅ / 📝 | `EvidenceLevel`, 뉴스·블로그로 Established Findings 금지 규칙 |
| 21 | 중복 탐지 | ✅ / 📝 | 해시·DOI·URL·제목 ✅, 프리프린트와 게재본 같은 판 차이는 에이전트가 확인 |
| 22 | 변경 추적 | ✅ | `log.md`, 페이지별 Change Log, git |
| 23 | Obsidian 호환 | ✅ | 볼트 `store/`, `aliases`, 경로형 링크, `.obsidian/app.json` |
| 24 | Graph 시각화 | ✅ / 📅 | Obsidian Graph View ✅, 필터·커뮤니티 UI 📅 |
| 25 | 검색 | ✅ / 📅 | 사용자: Obsidian 검색(필요 시 Omnisearch·Smart Connections 플러그인). 에이전트: `sb search` ✅. 에이전트용 의미·그래프 검색 📅 |
| 26 | 질의응답 | 📝 | AGENTS.md §4.2 (Wiki에 있는 내용으로만 답변, 출처 필수) |
| 27 | Digest | ✅ | `sb digest [--days] [--save]` |
| 28 | Research Gap 탐지 | ✅ / 📝 | `sb graph`: 충돌, 빠진 관계, 종단·인과 근거 부족, 오래된 근거. 국가·산업·모집단 공백은 에이전트 판단 |
| 29 | 개인 연구 프로젝트 | ✅ / 📝 | `sb project`, 아이디어 우선순위 규칙 |
| 30 | MCP / API | 📅 | Phase 6 |
| 31 | 폴더 감시 | ✅ / 📅 | `sb add-dir inbox` ✅, 실시간 감시 📅 |
| 32 | Human-in-the-Loop | 📝 / ✅ | `review: pending` 규칙, `sb status` 검토 목록 |
