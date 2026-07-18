# Part B: xform 소멸 — coloring 이 pixel relation 에서 직접 발화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `xform`·`g0cells`·`g1color`·`comm`·`diff` 낯선 중간 symbol 을 없애고, coloring 규칙이 pixel relation(변화 셀)에서 arg(좌표·색)를 comp1/comp2 로 직접 결정해 발화하게 한다. hypothesize 는 H-space 로 후보를 노출(대시보드 가시화).

**Architecture:** compare 가 이미 남기는 pixel relation(E_G0Xi-G1Xi, color DIFF)을 hypothesize 가 H-space 에 `recolor-rel` 로 노출 → propose*coloring 이 그 relation 구조(comp1/comp2)를 조건으로 걸고 arg 를 규칙이 결정 → apply body 는 원자연산(그 좌표에 그 색 칠함 + 좌표-리터럴 coloring step 방출). 단계: B1(추가·안전) → B2(핵심·발화 전환) → B3(xform 제거).

**Tech Stack:** Python 3, SOAR productions(JSON), program_ast, pytest.

## Global Constraints

- move 60/60 유지 — `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60` (seed 0/1/42). 각 태스크 게이트.
- **PAIR.program byte 불변**: relation-발화 coloring 이 현행 xform-발화와 **동일한 셀·색·순서**의 coloring step 을 내야 함. move000a 등의 PAIR.program(AST-json)을 현행과 대조.
- 전체 pytest 신규 회귀 0 (현재 174 passed/5 failed/4 skipped). solve WM 형식 바뀌면 `engine_golden.pkl` 재생성(60/60·byte 확인 후).
- 새 DSL 금지(coloring 만). 새 operator 금지(coloring 은 이미 존재; relation-발화로 조건만 바꿈).
- 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## 사전 사실(실측)
pixel relation `E_G0Xi-G1Xi` WM 구조: `E ^category C`; `C ^color <col>`(`<col> ^type DIFF ^comp1 <in> ^comp2 <out>`); `C ^coordinate <crd>`(`<crd> ^category <cc>`); `<cc> ^row_index <ri>`(`<ri> ^comp1 <r>`); `<cc> ^col_index <ci>`(`<ci> ^comp1 <cx>`). 좌표는 COMM(comp1=comp2), 색은 DIFF(출력=comp2). `_compare_pixels` 가 변화 셀(color DIFF)만 저장.

---

### Task 1: hypothesize 가 H-space + recolor-rel 노출 (추가·dormant)

**Files:** Modify `procedural_memory/operators/hypothesize.py`; Test `tests/test_recolor_rel.py`

**Interfaces:** Produces: PIXEL hypothesize 가 `ag.create_hspace(...)` 로 H substate 를 열고, 각 재채색 후보 pixel relation `E`(변화 셀)를 `(<h> ^recolor-rel <E>)` 로 노출. **xform 은 그대로 둔다**(이번엔 추가만; coloring 은 아직 xform 로 발화). H-space 는 대시보드에 가설공간으로 표시.

- [ ] **Step 1: 실패 테스트** `tests/test_recolor_rel.py`: move000a 를 solve 한 WM 에서 `recolor-rel` 마커가 변화 셀 pixel relation 을 가리키고(개수=변화셀 수), 각 relation 이 color DIFF·coordinate COMM 구조를 가짐을 assert.
- [ ] **Step 2: 실패 확인** — recolor-rel 없음.
- [ ] **Step 3: 구현** — `_op_hypothesize` PIXEL 분기에서, 변화 셀 pixel relation(WM 의 `E_G0Xi-G1Xi`, color DIFF)을 찾아 H-space 에 `recolor-rel` 로 노출. (relation 은 compare pxmatch 산물; 없으면 hypothesize 가 pxmatch 를 트리거하거나 residual 로부터 대응 relation id 를 조회.) xform 생성부는 유지.
- [ ] **Step 4: 게이트** — 60/60 불변(xform 이 여전히 발화), `pytest -q` 신규 회귀 0, test_recolor_rel PASS. 대시보드 재생성 시 H-space 표시 확인.
- [ ] **Step 5: 커밋** `feat(hypothesize): PIXEL 재채색 후보를 H-space 에 recolor-rel 로 노출(가시화, 추가)`

---

### Task 2: coloring 이 relation 에서 발화 (핵심 — 발화 전환)

**Files:** Modify `procedural_memory/production_rules/coloring.json`(propose/apply 조건), `procedural_memory/operators/coloring.py`(`_op_coloring` body); Test `tests/test_coloring_from_relation.py`; Regenerate `engine_golden.pkl`

**Interfaces:** Consumes: recolor-rel(Task1). Produces: `propose*coloring` 이 `(<h> ^recolor-rel <E>)` + relation 구조(color DIFF comp2, coordinate comp1)를 조건으로 걸어 operator arg(`^row <r> ^col <cx> ^color <out>`)를 relation 으로 결정. `_op_coloring` 은 그 arg 로 원자 coloring + 좌표-리터럴 step 방출. **xform-발화 경로 제거**(has-recolor 대신 recolor-rel).

- [ ] **Step 1: 실패 테스트** `tests/test_coloring_from_relation.py`: 손으로 만든 pixel relation WME(color DIFF comp2=색, coordinate comp1=(r,c))을 넣고 `_op_coloring`(또는 arg 추출 헬퍼)이 그 (r,c)에 그 색을 칠하고 좌표-리터럴 step 을 냄을 assert.
- [ ] **Step 2: 실패 확인**.
- [ ] **Step 3: 구현**
  - `coloring.json` `propose*coloring`: 조건을 `has-recolor` 대신 `(<s> ^recolor-rel <E>)` + relation 구조 바인딩(comp2=out, row/col comp1=r,cx)으로. 액션에 `(<o> ^row <r>)(<o> ^col <cx>)(<o> ^color <out>)(<o> ^from-relation <E>)`. TIE 방지(한 번에 하나) 위해 미적용 마커(예: `<E> ^colored` 없음).
  - `_op_coloring`: operator 의 `row/col/color` 를 읽어 sim 에 frozen coloring 적용 + `PA.step("coloring", target=PA.ref("coord", PA.const([r,cx])), color=PA.const(out))` 방출 + `<E> ^colored yes` 표시. 다 칠하면 `colored-all`.
- [ ] **Step 4: 게이트(핵심)**
  - `debugger.score move` → 60/60(seed 0/1/42).
  - **PAIR.program byte 대조**: move000a/b 의 예제 PAIR.program(AST-json)이 이 변경 **전(60e0432)**과 동일한지(같은 coloring step 집합·좌표·색). 다르면 STOP·진단(발화 순서/좌표 원천).
  - golden 재생성(60/60·byte 확인 후) + `pytest -q` 신규 회귀 0.
- [ ] **Step 5: 커밋** `feat(coloring): pixel relation 에서 arg 결정해 발화(comp1/comp2) — xform 발화 대체`

---

### Task 3: xform·g0cells·g1color·comm·diff 심볼 제거

**Files:** Modify `procedural_memory/operators/hypothesize.py`, `procedural_memory/operators/coloring.py`(`_recolor_pending` 등 xform 참조), `procedural_memory/operators/verify.py`(있으면); Test 유지

**Interfaces:** Consumes: Task2(coloring 이 relation 으로 발화). Produces: hypothesize 가 xform/g0cells/g1color/comm/diff/g0idx/has-recolor WME 를 **더는 만들지 않음**. WM 에서 그 심볼 소멸.

- [ ] **Step 1: 삭제** — `_op_hypothesize` 의 xform 생성부(PIXEL·OBJECT 분기의 `xform`/`px`/`diff`/`comm`/`g0cells`/`g1color`/`g0idx`/`has-recolor` add) 제거. `_recolor_pending`(coloring.py) 등 xform 참조 헬퍼 제거/대체. object 경로가 xform 를 쓰면 그 경로도 recolor-rel 로(또는 object recolor 는 Task2 범위면 함께).
- [ ] **Step 2: 게이트** — 60/60(seed 0/1/42), PAIR.program byte 불변(Task2 대비), golden 재생성, `pytest -q` 신규 회귀 0. WM 에 `xform`/`g0cells`/`g1color` 부재 실측.
- [ ] **Step 3: 커밋** `refactor(hypothesize): xform/g0cells/g1color/comm/diff 심볼 제거 — coloring 은 relation 직결`

---

## 범위 밖
- compare `_build_agenda` arg 선택 규칙화(Part 2 다른 항목).
- object-level coloring(다중 셀 배열) 의 규칙-only arg — 픽셀 스칼라 경로 우선; object recolor 는 후속(필요 시 노드참조).
- generalize/resolve 탈절차화.

## Self-Review
- **Spec(B) coverage**: B.2 발화 메커니즘→Task2 · B.3 H-space→Task1 · B.1 symbol 소멸→Task3 · B.4 60/60·byte→각 게이트. 누락 없음.
- **의존 순서**: Task1(H-space 노출, 추가) → Task2(발화 전환, xform-발화 제거) → Task3(xform 생성 제거). Task2 전에 recolor-rel 있어야 규칙이 걸림.
- **리스크**: Task2 가 핵심 — PAIR.program byte 대조를 게이트로 두어 발화순서/좌표원천 차이를 즉시 잡는다. 깨지면 STOP·진단(부분 롤백).
