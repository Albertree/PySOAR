# ARBOR — Claude 세션 지침

## ⚠️ 필수: 매 행동 전 하네스를 읽는다
**ARBOR 솔버**(operator body `procedural_memory/operators/` · 규칙 `procedural_memory/production_rules/` ·
지각/추론 `arbor/` · 트레이서·대시보드 `debugger/`·`arc/fine_trace.py` · 커널 `soar/`)를
설계·작성·수정·리팩터하거나 그 트레이스를 해석하기 **직전마다**, 반드시 [ARBOR_HARNESS.md](ARBOR_HARNESS.md)
를 다시 읽고 그 §7 체크리스트로 스스로를 점검한다.

하네스 요지 (전문은 파일 참조 — 압축본이 아니라 원본을 읽을 것):
- **막힌다고 새 operator/DSL/property 를 임의로 만들지 않는다.** 필요하면 멈추고 사용자에게 제안·의논 후 결정.
- **정답을 알아도 최적 변환을 바로 박지 않는다.** 구현 대상은 "정답"이 아니라 지능체의 *생각 단위 모듈*.
- **수식/좌표/선택은 탐색+검증으로 도출한다** (예: `(H-h, W-w)` 를 손계산 금지 → `H-1,H+3,h-H,H*2,H-w…`
  가설 생성→train 대조→검증).
- **정보는 ARCKG 노드 property 에서**, **근거는 compare(COMM/DIFF)** 에서. 항목 비교뿐 아니라 **관계 비교
  (2차·n차)** 를 쓴다.
- ARC = analogical reasoning: **Pair 간 GRID relation 을 비교해 공통 relation(structure mapping /
  anti-unification)** 을 찾는다. relation 은 property COMM/DIFF 일 수도, *sequence of transformation* 일 수도.

## 프로젝트 맥락
- ARBOR = ARCKG(TASK→PAIR→GRID→OBJECT→PIXEL 5계층 지식그래프)로 ARC 를 푸는 symbolic 추론 에이전트.
  SOAR 결정 커널은 `soar/`(옛 이름 *PySOAR*, C++ Soar 9.6.5 를 차등 오라클로 둔 충실 재구현).
- **self-contained**: ARCKG 노드·`compare()`(`arbor/perception/arckg/`), 기초 DSL(`procedural_memory/dsl/`),
  데이터(`data/`)를 레포에 vendor — 외부 `~/Desktop/ARC-solver` 의존 0. 진입점 `python -m debugger.build`.
  리팩터 진행상태·구조는 memory `[[seokki-refactor]]` + `docs/REFACTOR_PLAN.md`.
- 현행 작업 = hypothesize monolith 해체 → within-pair compare → 2차/n차 relation → search → G0-resolve →
  compose 재건. 상세 규약: `~/Desktop/wiki/wiki/{pysoar,arbor-operators,arckg-node-edge}.md`, 7원리(P1–P7)는
  `arbor-execution-trace.md`.
- 성공 판정: 4문제(easy000a·made000b·08ed6ac7·made000a)의 step 수가 서로 달라지고, 근거(COMM/DIFF)가 WM 에 남는다.
