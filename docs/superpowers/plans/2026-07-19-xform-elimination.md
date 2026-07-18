# Part B: xform 소멸 — coloring 이 실제 compare relation 에서 직접 발화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `xform`·`g0cells`·`g1color`·`comm`·`diff`·`g0idx`·`has-recolor` 중간 symbol 을 없애고, coloring 이
**이미 존재하는 compare relation**(pixel `E_G0Xi-G1Xi` · object `E_G0Oi-G1Oj`, color DIFF)에서 arg(좌표·색)를
직접 얻어 발화하게 한다. pixel·object 두 레벨 모두. hypothesize 는 sim 핸드오프 + H-space(가시화)만 남기고 xform 생성 중단.

**Architecture (실측 검증됨):** `_compare_pixels`(pxmatch) 는 이미 각 변화 셀을 `Tmove000a.P0.E_G0X26-G1X26`
(`^type DIFF`; `category.color {DIFF, comp1=in, comp2=out}`; `category.coordinate {COMM, row_index/col_index
comp1=comp2}`) 로 WM 에 남긴다 — coloring 이 comp2(색)·coordinate comp1(좌표)로 arg 를 정하면 그대로 발화 가능.
`_compare_objects`(match) 는 `E_G0Oi-G1Oj`(`category.color` 는 **presence-dict**: `category.k {comp2=True}` 인 k
가 출력색; `category.coordinate {COMM, comp1=object 셀목록}`) 를 남긴다. 지금은 hypothesize 가 이 관계들을 **무시**하고
residual/대응을 xform 으로 **재계산**한다 — Part B 는 그 재계산을 없애고 관계에서 직접 발화한다.

**Tech Stack:** Python 3, SOAR productions(JSON), program_ast, pytest.

## Global Constraints (게이트 — 매 태스크)

- **move 60/60**: `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60`. (pixel recolor + move 의 object no-op 경로)
- **easy 8/8**: `PYTHONHASHSEED=0 python -m debugger.score easy` → `SCORE: 8/8`. (grid 레벨 — xform 무관이나 회귀 감시)
- **08ed6ac7 behavior-preserve**: 08ed6ac7 은 BASE 에서 이미 오답(score wrong)이지만 **object recolor 경로를 타는 유일한 게이트 태스크**
  (obj-recolor xform 4 → object-ref coloring step 2). 따라서 정답이 아니라 **PAIR.program 의 object coloring step 이
  BASE(53a9ace)와 byte 동일**함을 게이트로 둔다. flip/rotate 는 BASE 에서 이미 crash/오답이라 게이트 아님.
- **PAIR.program byte 불변**: move000a·move000b·08ed6ac7 의 예제 PAIR.program(AST-json) 이 BASE 와 동일(같은 coloring
  step 집합·좌표/객체·색·순서). 다르면 STOP·진단.
- **pytest 신규 회귀 0**: 현재 174 passed/5 failed/4 skipped. solve WM 형식이 바뀌면 `engine_golden.pkl` 재생성(위 게이트 통과 후).
- 새 DSL 금지(coloring 만). 새 operator 금지. 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

## 사전 사실 (실측, PYTHONHASHSEED=0)

**pixel relation** `Tmove000a.P0.E_G0X26-G1X26` (셀 (3,2), 색 7→0):
```
E ^type DIFF ^category C
C ^color <col>       ; <col> ^type DIFF ^comp1 7 ^comp2 0                 # comp2 = 출력색
C ^coordinate <crd>  ; <crd> ^type COMM ^category <cc>
<cc> ^row_index <ri> ; <ri> ^type COMM ^comp1 3 ^comp2 3                  # comp1 = 행
<cc> ^col_index <ci> ; <ci> ^type COMM ^comp1 2 ^comp2 2                  # comp1 = 열
```
pxmatch 는 **첫 pair(P0)만** 돈다(Gap A — Task 1 이 pair 마다 돌게). 변화 셀(color DIFF)만 저장.

**object relation** `T08ed6ac7.P0.E_G0O0-G1O1` (object O0→O1, 색 5→3, 같은 위치):
```
E ^type DIFF ^category C
C ^color <col>  ; <col> ^type DIFF ^category <pd>                          # presence-dict
<pd> ^k <e_k>   ; <e_k> ^type DIFF ^comp1 <bool> ^comp2 <bool>   (k=0..9)  # comp2=True 인 k = 출력색
C ^coordinate <crd> ; <crd> ^type COMM ^comp1 ((3,3),(4,3),..) ^comp2 (동일)  # 객체 셀목록(=칠할 대상)
```
현행 object xform: `g1color`=출력객체 색(첫 present), `g0cells`=객체 셀목록, `g0idx`=objects_of(input) 인덱스.
→ 관계에서 출력색 = `comp2=True 인 k`, 셀 = coordinate comp1, 객체인덱스는 relation id 의 O-번호(objects_of 순서와 정렬).

## 현행 흐름 (참조)

- OBJECT/PIXEL substate: observe → `_build_agenda`(cmp 목록) → compare(pxmatch/match) → **hypothesize**(residual/대응 → xform)
  → coloring(xform 소비 → sim 칠·program step) → verify(sim==out? PAIR.program 기록) → `_advance_or_finish`(다음 pair 커서 +1,
  `_reset_synth` 로 xform 등 clear → hypothesize 재발화).
- hypothesize PIXEL: `sup` substate 의 sim/program-code 를 이어받아 sim0 초기화(**sim 핸드오프 — 유지**) 후 residual→xform.
- coloring `_op_coloring`: `_recolor_pending`(diff color ∧ comm coordinate ∧ ¬applied) 을 순서대로 frozen coloring 적용 +
  step(pixel=`ref("coord",[r,c])`, object=`ref("object",i)`) 방출.

---

### Task 1: pixel compare 를 train pair 마다 실행 (enabler·추가·안전)

**Files:** Modify `procedural_memory/operators/observe.py`(`_build_agenda` pixel 분기); Test `tests/test_pxmatch_per_pair.py`

**Interfaces:** Produces: PIXEL 관측 후 agenda 가 grid `within` 처럼 **각 train pair 마다** `cmp:pxmatch.{pair}`
(kind=pxmatch, g0=Pk.G0, g1=Pk.G1)를 깐다. compare 가 각각 소비 → 각 pair 의 `Pk.E_G0Xi-G1Xi` color-DIFF relation 이 WM 에.
**hypothesize/coloring 은 아직 xform 로 발화**(이번엔 관계만 추가). idx 에 모든 pair 의 pixel 이 이미 있으므로 focus 확장 불필요.

- [ ] **Step 1: 실패 테스트** `tests/test_pxmatch_per_pair.py`: move000a solve 후, 각 train pair p(변화 있는)에 대해
  `{p}.E_G0X..-G1X..` color-DIFF relation 이 WM 에 있고, 그 개수 = 그 pair 의 raw G0≠G1 변화셀 수임을 assert. (BASE 는 P0 만 → 실패)
- [ ] **Step 2: 실패 확인** — P1 relation 없음.
- [ ] **Step 3: 구현** — `_build_agenda` pixel 분기: focus group 의 grid 만 쓰지 말고, `grid within` 처럼 idx 구조에서
  **G0·G1 둘 다 있는 모든 train pair** 를 찾아 pair 마다 `cid=f"{sid}.cmp:pxmatch.{p.split('.')[-1]}"`(g0=Pk.G0,g1=Pk.G1,
  kind=pxmatch,order=증가) 를 깐다. (compare `_compare_pixels` 는 이미 idx["pixels"][g0/g1] 로 직접 읽으므로 focus 무관.)
- [ ] **Step 4: 게이트** — move 60/60 · easy 8/8 · pytest 신규 회귀 0 · test_pxmatch_per_pair PASS. (xform 여전히 발화 → 답 불변)
- [ ] **Step 5: 커밋** `feat(observe): PIXEL compare 를 train pair 마다 실행 — 각 pair 의 E_G0Xi-G1Xi 관계 확보(추가)`

---

### Task 2: pixel coloring 이 relation 에서 발화 (핵심 — pixel 발화 전환)

**Files:** Modify `procedural_memory/production_rules/coloring.json`(propose/apply pixel), `procedural_memory/operators/coloring.py`(`_op_coloring` pixel 분기), `procedural_memory/operators/hypothesize.py`(PIXEL residual→xform 제거, 관계 노출); Test `tests/test_coloring_from_pixel_rel.py`; Regenerate `engine_golden.pkl`

**Interfaces:** Consumes: Task1 의 pair 별 pixel relation. Produces: hypothesize PIXEL 이 sim0/base-program 핸드오프는 유지하되
residual→xform 루프를 제거하고, 현재 pair(pair_cursor)의 pixel relation 들을 H-space 에 `recolor-rel` 로 노출.
`propose*coloring`(pixel) 이 `(<s> ^recolor-rel <E>)` + relation 구조(color DIFF comp2, coordinate row/col comp1)를 조건으로
걸어 op arg(`^row <r> ^col <cx> ^color <out> ^rel <E> ^level pixel`)를 결정. `_op_coloring` 이 그 arg 로 원자 coloring +
`ref("coord",[r,cx])` step 방출 + `<E> ^colored yes`. 다 칠하면 `colored-all`.

- [ ] **Step 1: 실패 테스트** `tests/test_coloring_from_pixel_rel.py`: 손으로 pixel relation WME(위 사전사실 구조: color DIFF
  comp2=색, coordinate row/col comp1=(r,c)) + sim 을 넣고, coloring propose 가 그 arg 를 뽑아 op 를 제안하고 apply 가 (r,c)에
  그 색을 칠하고 `ref("coord",[r,c])` step 을 냄을 assert. (BASE 에 pixel-relation 발화 규칙 없음 → 실패)
- [ ] **Step 2: 실패 확인**.
- [ ] **Step 3: 구현**
  - `hypothesize.py` PIXEL 분기: sim0/base-program 핸드오프 유지(현행 82-88). residual→xform 루프(현행 92-104) 제거. 대신
    현재 pair(pair_cursor)의 pixel relation(WM `{Pk}.E_G0Xi-G1Xi`, color DIFF)을 조회해 `ag.create_hspace` H-space 를 열고
    각 relation 을 `(<h> ^recolor-rel <E>)` + `(sid ^recolor-rel <E>)`(규칙이 걸 앵커)로 노출. relation 없으면(변화 없음) `colored-all`.
  - `coloring.json` `propose*coloring` (pixel): 조건 = `(<s> ^recolor-rel <E>)`, `(<E> ^category <C>)`,
    `(<C> ^color <col>)(<col> ^type DIFF)(<col> ^comp2 <out>)`, `(<C> ^coordinate <crd>)(<crd> ^category <cc>)`,
    `(<cc> ^row_index <ri>)(<ri> ^comp1 <r>)`, `(<cc> ^col_index <ci>)(<ci> ^comp1 <cx>)`, `-(<E> ^colored yes)`.
    액션: `(<o> ^name coloring)(<o> ^row <r>)(<o> ^col <cx>)(<o> ^color <out>)(<o> ^rel <E>)(<o> ^level pixel)`. (한 relation 씩)
  - `coloring.py` `_op_coloring`: pixel arg 경로 — op 의 `row/col/color/rel` 를 읽어 sim 에 frozen coloring(r,c,out) +
    `body.append(PA.step("coloring", target=PA.ref("coord", PA.const([r,cx])), color=PA.const(out)))` + `(<E> ^colored yes)`.
    미적용 recolor-rel 없으면 program-code 기록 + `colored-all`. (xform 경로는 Task4 까지 object 용으로 병존 — pixel 은 relation 경로.)
- [ ] **Step 4: 게이트(핵심)** — move 60/60 · easy 8/8 · **move000a/b PAIR.program byte = BASE**(같은 coord step) · 08ed6ac7 object step byte = BASE · golden 재생성 · pytest 0 회귀. byte 다르면 STOP(발화순서/좌표원천 진단).
- [ ] **Step 5: 커밋** `feat(coloring): PIXEL 이 pixel relation(comp1/comp2)에서 arg 결정해 발화 — pixel xform 대체`

---

### Task 3: object coloring 이 relation 에서 발화 (object 발화 전환)

**Files:** Modify `procedural_memory/production_rules/coloring.json`(propose/apply object), `procedural_memory/operators/coloring.py`, `procedural_memory/operators/hypothesize.py`(OBJECT xform 제거, 관계 노출); Test `tests/test_coloring_from_object_rel.py`; Regenerate `engine_golden.pkl`

**Interfaces:** Consumes: 이미 존재하는 object relation `E_G0Oi-G1Oj`(match compare 산물, color DIFF presence-dict,
coordinate COMM 셀목록). Produces: hypothesize OBJECT 이 xform 대신 **color DIFF 인 object relation** 을 H-space 에
`recolor-rel` 로 노출(sim=G0 유지). `propose*coloring`(object) 이 그 relation 을 조건으로 op arg(`^cells <셀목록> ^color <out>
^objidx <i> ^rel <E> ^level object`)를 결정 — presence-dict 특성상 **출력색 스칼라 추출은 body 헬퍼**(`_out_color_of(ag,E)` =
comp2=True 인 첫 색 index)가 하고, 규칙은 발화조건(color DIFF ∧ coordinate COMM ∧ ¬colored)과 relation 바인딩을 건다.
`_op_coloring` object 경로가 그 셀들을 out 색으로 칠하고 `ref("object", i)` step 방출.

- [ ] **Step 1: 실패 테스트** `tests/test_coloring_from_object_rel.py`: 손으로 object relation WME(color DIFF presence-dict
  comp2=True@색3, coordinate COMM comp1=[(3,3),(4,3)]) + sim 을 넣고, `_out_color_of` 가 3 을 뽑고, coloring apply 가 그
  셀들을 3 으로 칠하고 `ref("object", i)` step 을 냄을 assert. (BASE 에 object-relation 발화 규칙 없음 → 실패)
- [ ] **Step 2: 실패 확인**.
- [ ] **Step 3: 구현**
  - `hypothesize.py` OBJECT 분기: sim=G0 유지. `_fg_correspondence`→xform 루프(현행 106-121) 제거. 대신 현재 pair 의 object
    relation `{Pk}.E_G0Oi-G1Oj` 중 `category.color ^type DIFF` 인 것을 조회해 `(sid ^recolor-rel <E>)`(+H-space) 노출.
    object 인덱스 i = relation id 의 G0O**i** (objects_of(input) 순서와 동일; verify 대조로 확인). `(<E> ^objidx i)` 부착.
  - `coloring.py` 헬퍼 `_out_color_of(ag, E)`: `E.category.color.category.k` 중 `^comp2 True ∧ ^comp1 False` 인 첫 k(int) 반환
    (= 추가된 출력색; 현행 g1color 와 일치해야 함). `_object_cells_of(ag, E)`: `E.category.coordinate ^comp1` 파싱 → 셀 목록.
  - `coloring.json` `propose*coloring` (object): 조건 = `(<s> ^recolor-rel <E>)`, `(<E> ^category <C>)`,
    `(<C> ^color <col>)(<col> ^type DIFF)`, `(<C> ^coordinate <crd>)(<crd> ^type COMM)`, `(<E> ^objidx <i>)`, `-(<E> ^colored yes)`.
    액션: `(<o> ^name coloring)(<o> ^rel <E>)(<o> ^objidx <i>)(<o> ^level object)`. (색·셀은 body 가 relation 에서 추출.)
  - `coloring.py` `_op_coloring` object 경로: op 의 `rel/objidx` → `out=_out_color_of(ag,E)`, `cells=_object_cells_of(ag,E)`,
    각 셀 frozen coloring(r,c,out) + `body.append(PA.step("coloring", target=PA.ref("object", PA.const(i)), color=PA.const(out)))`
    + `(<E> ^colored yes)`.
- [ ] **Step 4: 게이트** — **08ed6ac7 PAIR.program object coloring step byte = BASE(53a9ace)** (같은 object idx·색·순서) ·
  move 60/60 · easy 8/8 · golden 재생성 · pytest 0 회귀. byte 다르면 STOP·진단(색 추출/객체 인덱스 정렬).
- [ ] **Step 5: 커밋** `feat(coloring): OBJECT 가 object relation(color DIFF presence-dict)에서 발화 — object xform 대체`

---

### Task 4: xform·g0cells·g1color·comm·diff·g0idx·has-recolor 심볼 제거

**Files:** Modify `procedural_memory/operators/hypothesize.py`, `procedural_memory/operators/coloring.py`(`_recolor_pending` 등), `procedural_memory/operators/verify.py`(`_reset_synth` xform 정리), `procedural_memory/production_rules/coloring.json`(has-recolor 발화 규칙 제거); Test 유지 + `tests/test_no_xform_symbol.py`; Regenerate `engine_golden.pkl`

**Interfaces:** Consumes: Task2·3(pixel·object 모두 relation 발화). Produces: hypothesize 가 `xform`/`px`/`diff`/`comm`/
`g0cells`/`g1color`/`g0idx`/`has-recolor` WME 를 **더는 만들지 않음**. `_recolor_pending`(xform 조회) 제거. `_op_coloring`
의 xform 소비 분기 제거(relation 경로만). `_reset_synth` 의 xform 정리 루프 제거(대신 recolor-rel `^colored` 마커 리셋). WM 에서 심볼 소멸.

- [ ] **Step 1: 실패 테스트** `tests/test_no_xform_symbol.py`: move000a·08ed6ac7 solve 후 WM 에 attr `xform`/`g0cells`/`g1color`
  가 **하나도 없음**을 assert. (BASE·Task2·3 후에도 잔존 → 실패)
- [ ] **Step 2: 실패 확인**.
- [ ] **Step 3: 구현** — hypothesize 의 잔여 xform 생성부·`_recolor_pending`·`_op_coloring` xform 분기·`coloring.json` 의
  `has-recolor` 발화 규칙·`_reset_synth` xform 루프 제거. `_reset_synth` 는 대신 pair 넘어갈 때 recolor-rel `^colored`/H-space 리셋.
- [ ] **Step 4: 게이트** — move 60/60 · easy 8/8 · 08ed6ac7 object step byte = BASE · PAIR.program byte 불변(Task3 대비) ·
  golden 재생성 · pytest 0 회귀 · test_no_xform_symbol PASS · WM 에 xform/g0cells/g1color 부재 실측.
- [ ] **Step 5: 커밋** `refactor(hypothesize/coloring): xform/g0cells/g1color/comm/diff 심볼 제거 — coloring 은 relation 직결`

---

## 범위 밖
- compare `_build_agenda`·`select` 의 arg 선택 규칙화(Part 2 다른 항목).
- generalize/resolve 탈절차화. flip/rotate 의 BASE crash(`resolve_slot` dict 좌표) 수정 — 별개 버그.
- object relation 의 다중색(멀티컬러 객체) 정밀화 — 현행 g1color(첫 present) 동치 유지에 한함.

## Self-Review
- **Scope coverage**: pixel 발화→Task2 · object 발화→Task3 · per-pair 관계→Task1 · symbol 소멸→Task4 · 게이트→각 Step4. 누락 없음.
- **의존 순서**: Task1(관계 확보, 추가) → Task2(pixel 발화, pixel xform 제거) → Task3(object 발화, object xform 제거) →
  Task4(잔여 심볼·헬퍼 제거). Task2·3 전에 관계가 WM 에 있어야 규칙이 걸림(Task1·기존 match compare 가 보장).
- **리스크 집중**: Task2(pixel byte-gate)·Task3(object presence-dict 색추출·객체인덱스 정렬, 게이트가 오답 태스크의 behavior-preserve).
  각 Step4 byte 대조로 발화순서/좌표·색 원천 차이를 즉시 STOP·진단. 깨지면 부분 롤백.
- **정직성 주의**: 08ed6ac7 는 BASE 에서 오답 → object 게이트는 "정답"이 아니라 "object coloring step byte 동일"(현행 동작 보존)임을
  보고서·커밋에 명시. easy/flip/rotate 의 BASE 상태(easy 8/8, flip/rotate crash/오답)도 그대로 보존.
