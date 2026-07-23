# Grammar A — P2: compress cellset → pixel select emit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `cellset` 표현을 emission·skeleton 양쪽에서 완전히 제거하고, 셀을 그리드 pixel list 에서 뽑는 `coordinate_of(select("input","pixel", coord_in("pixel_coordinate",[coords])))` 로 대체한다 — cellset 이 어떤 프로그램에도 나오지 않게. move 60/60 + objc 유지.

**Architecture:** 사용자 2단 모델의 **1차 pixel compress**. 바뀐 셀 그룹 하나 = select 1 op(coord 리스트를 술어로) → op수 보존 = anti-unify 정렬 그대로. `ops_of_ast` 가 select-target 을 cellset 과 **동일 shape(frozenset of coords, color)** 로 정규화해 anti-unify(`_antiunify_ast_blob`)·resolve(`_resolve_cellset`) 로직 변경을 최소화한다. 2차(픽셀→object 공통소속)는 다음 청크.

**Tech Stack:** Python, unittest, 기존 `arbor/reasoning/program_ast.py`·`antiunify.py`·`procedural_memory/operators/compress.py`.

## Global Constraints

- **cellset 은 최종적으로 emission·skeleton 어디에도 없어야 한다**(사용자 2026-07-23). 셀은 `select("input","pixel", coord_in(...))` 로 grid pixel list 에서.
- **객체당 select 1 op** 유지(coord 리스트 술어) → op수 보존 → move 60/60 anti-unify 정렬 보존.
- 게이트: `python -m debugger.score move` = **60/60** + `python -m debugger.score objc` = **10/10** (각 phase 후). 회귀 시 그 phase 에서 멈춤.
- 새 원자 `coord_in` 은 §5 사용자 승인됨(2026-07-23). 그 외 새 operator/DSL/property 임의생성 금지(§1-1).
- slot 값 = **coord 리스트**((r,c)), 인덱스 아님(pixel_coordinate 가 (r,c) 라서). 결정적 정렬(§2-6). 커밋은 검증 후. Co-Authored-By 말미.
- 브랜치 seokki-refactor.

**노드 shape (확정):**
- 술어: `coord_in(accessor, values)` → `{"in": {"accessor": accessor, "values": values}}`. accessor="pixel_coordinate", values=`[[r,c],...]`(const) 또는 `{"var":"?cellsN"}`.
- target: `coordinate_of(select("input","pixel", coord_in("pixel_coordinate", [[r,c],...])))`.
- 실행: select 가 input pixel 중 coord∈values 인 것을 고름 → coordinate_of → 그 좌표들 → coloring. dest 셀도 input 격자에 그 좌표의 (배경)픽셀이 있으므로 input 실행 가능(P5 준수 — 최종 리터럴 좌표는 resolve 가 input-식으로 대체).

**범위 밖:** 2차(픽셀 공통소속→object), object-level select, rotate/flip. cellset 노드 **생성자 자체**는 레거시 호환으로 남겨도 되나(P2 는 emit 만 제거), 최종 grep 에서 emitted program 에 cellset=0 이면 목표 달성.

---

## Phase 2a — additive: coord_in 술어 + 실행기 + ops_of_ast/anti-unify/resolve 의 select 지원 (cellset 과 공존)

이 phase 는 **아무것도 select 를 emit 하지 않는다** → move/objc 게이트는 정의상 불변. select-target 을 각 단계가 cellset 과 **동치**로 처리함을 단위테스트로 고정.

### Task 1: coord_in 술어 + _compile_pred 확장 + 실행기 (additive)

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (생성자 블록; `_compile_pred`; `_sel_src`/to_source)
- Test: `tests/test_coord_in.py`

**Interfaces:**
- Produces: `coord_in(accessor, values) -> {"in": {"accessor":..., "values":...}}`. `_compile_pred` 가 `eq`·`in` 둘 다 컴파일. `_resolve_select_coords` 는 P1 그대로(select 가 pred 로 필터하니 coord_in 도 자동 처리) — 단 values 가 const 일 때. `to_source` 가 coord_in 을 `pixel_coordinate∈[coords]` 로 렌더.

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_coord_in.py
import unittest
from arbor.reasoning import program_ast as PA


class TestCoordIn(unittest.TestCase):
    def setUp(self):
        self.g = [[0, 0, 0], [0, 7, 0], [0, 0, 0]]   # 색7 @ (1,1)

    def test_coord_in_single(self):
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                 PA.coord_in("pixel_coordinate", [[1, 1]]))),
                        color=PA.const(3))]
        out = PA.execute(PA.program(body), self.g)
        self.assertEqual(out[1][1], 3)

    def test_coord_in_multi_one_op(self):
        # 두 셀을 한 op 로 (op수 보존): (0,0)과 (2,2) 를 5 로
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                 PA.coord_in("pixel_coordinate", [[0, 0], [2, 2]]))),
                        color=PA.const(5))]
        out = PA.execute(PA.program(body), self.g)
        self.assertEqual(out[0][0], 5); self.assertEqual(out[2][2], 5)
        self.assertEqual(out[1][1], 7)                # 나머지 불변

    def test_to_source_coord_in(self):
        body = [PA.step("coloring", target=PA.coordinate_of(PA.select("input","pixel",
                        PA.coord_in("pixel_coordinate", [[1,1]]))), color=PA.const(3))]
        src = PA.to_source(PA.program(body))
        self.assertIn("coord_in", src) if "coord_in" in src else self.assertIn("pixel_coordinate", src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_coord_in.py -v` → FAIL (`coord_in` 없음).

- [ ] **Step 3: 구현** — `program_ast.py`:
  1. 생성자 추가(select/coordinate_of 옆):
```python
def coord_in(accessor, values):
    """membership 술어: accessor(node) 의 값이 values 집합에 속함 (eq 의 집합판; coord 리스트 등)."""
    return {"in": {"accessor": accessor, "values": values}}
```
  2. `_compile_pred` 를 eq·in 둘 다 처리하도록:
```python
def _compile_pred(pred):
    from procedural_memory.dsl import property as _prop
    if "eq" in pred:
        e = pred["eq"]; accessor = getattr(_prop, e["accessor"]); want = _norm_coord(e["value"])
        return lambda node: _norm_coord(accessor(node)) == want
    if "in" in pred:
        e = pred["in"]; accessor = getattr(_prop, e["accessor"])
        wants = {_norm_coord(v) for v in e["values"]}
        return lambda node: _norm_coord(accessor(node)) in wants
    raise ValueError(f"bad pred {pred}")
```
  3. `_sel_src` 가 `in` 술어를 렌더(eq 분기 옆): `p=sel["pred"]; ... "pixel_coordinate∈[...]"`. 구체 문자열은 자유(테스트는 "coord_in" 또는 "pixel_coordinate" 존재만 확인).

- [ ] **Step 4: 통과 확인** — `python -m pytest tests/test_coord_in.py tests/test_grammar_a_execute.py -v` → PASS.

- [ ] **Step 5: 커밋** — `feat(ast): coord_in membership 술어 + 실행기 (P2a-1, additive)`.

### Task 2: ops_of_ast + anti-unify 의 select-body 지원 (cellset 동치, additive)

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (`ops_of_ast`, `_is_select_body` 신설, `antiunify_ast` 분기, `_antiunify_ast_grid` inner 분기, `_antiunify_ast_blob` → 스켈레톤 emit 을 target 종류에 맞게)
- Test: `tests/test_select_antiunify.py`

**Interfaces:**
- Consumes: Task1 coord_in. Produces: `ops_of_ast` 가 select-target → `(frozenset(coord-tuples), color)` (cellset 과 동일 shape, 단 coords). `_is_select_body(body)` = 모든 target 이 coordinate_of(select). `antiunify_ast`/`_antiunify_ast_grid` 가 select-body 를 blob 경로로 라우팅하되 **스켈레톤은 select-target 으로 emit**(COMM=const coord_in, DIFF=var coord_in).

- [ ] **Step 1: 실패 테스트** — 두 pair 의 select-body program(같은 색, 다른 coord set)을 `antiunify_ast` → 스켈레톤에 **cellset 없음**, DIFF 가 var slot, slot['values'] = per-pair coord 리스트. (구체 assert: `PA._is_select_body(sk['body'])` or 스켈레톤 target 에 "select" 존재, slots 에 ?cells0 등.)

```python
# tests/test_select_antiunify.py
import unittest, json
from arbor.reasoning import program_ast as PA

def _selstep(coords, col):
    return PA.step("coloring",
        target=PA.coordinate_of(PA.select("input","pixel", PA.coord_in("pixel_coordinate", coords))),
        color=PA.const(col))

class TestSelectAntiunify(unittest.TestCase):
    def test_diff_coords_become_slot_no_cellset(self):
        a = PA.program([_selstep([[3,2]], 0), _selstep([[4,3]], 7)])
        b = PA.program([_selstep([[6,0]], 0), _selstep([[7,1]], 7)])
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        blob = json.dumps(sk)
        self.assertNotIn('"cellset"', blob)            # cellset 어디에도 없음
        self.assertIn("select", blob)                  # select 스켈레톤
        self.assertTrue(any(k.startswith("?cells") for k in slots))

    def test_ops_of_ast_select_shape(self):
        a = _selstep([[3,2],[3,3]], 5)
        ops = PA.ops_of_ast(PA.program([a]))
        (tgt, col), = ops
        self.assertEqual(col, 5)
        self.assertEqual(set(tgt), {(3,2),(3,3)})       # frozenset of coord tuples
```

- [ ] **Step 2: 실패 확인** — FAIL (ops_of_ast/anti-unify 가 select 미지원).

- [ ] **Step 3: 구현** (설계 — 구현자 판단으로 아래 계약 충족):
  - `ops_of_ast`: target 에 `"coordinate_of"` 있으면 그 select 의 `coord_in.values` → const 면 `frozenset(tuple(c) for c in values)`, var 면 None. color 는 기존대로. (cellset/ref 분기는 그대로 둠 — 공존.)
  - `_is_select_body(body)`: `bool(body) and all("coordinate_of" in s["args"]["target"] for s in body)`.
  - `antiunify_ast`: `all(_is_cellset_body)` 다음에 `all(_is_select_body)` 분기 추가 → `_antiunify_ast_group(valid, kind="select")`. `_antiunify_ast_grid` 의 inner contents 분기도 `_is_select_body` 면 select 경로.
  - `_antiunify_ast_blob` 를 target-emit 파라미터화(`emit="cellset"|"select"`) 하거나 `_antiunify_ast_select` 를 추가: 정렬·비교 로직은 `_antiunify_ast_blob` 과 동일(ops_of_ast 가 같은 shape 반환), **스켈레톤 target 만** COMM→`coordinate_of(select("input","pixel", coord_in("pixel_coordinate", const(sorted(cells)))))`, DIFF→`coordinate_of(select("input","pixel", coord_in("pixel_coordinate", var(?cellsN))))`. slot['values'] = per-pair sorted coord 리스트.
  - **DRY 주의:** `_antiunify_ast_blob` 와 로직 중복 금지 — 공통 코어를 뽑아 emit 만 분기.

- [ ] **Step 4: 통과 + 실행기 var 지원 확인** — select 스켈레톤의 var coord_in 을 execute 가 choice 로 해소해야 함(Task3 resolve 가 fn 제공). 여기선 anti-unify 산출만 검증. `python -m pytest tests/test_select_antiunify.py tests/test_nested_antiunify.py -v` → PASS(기존 cellset nested 테스트 회귀 없음).

- [ ] **Step 5: 커밋** — `feat(ast): ops_of_ast+anti-unify select-body 지원(cellset 동치) (P2a-2)`.

### Task 3: resolve + execute 의 select-var 지원 (cellset 동치, additive)

**Files:**
- Modify: `arbor/reasoning/antiunify.py` (`resolve_slot`/`_resolve_cellset` 이 coord-리스트 값 처리), `arbor/reasoning/program_ast.py` (`_execute_pixel_body`/`_resolve_select_coords` 가 var coord_in 을 choice 로 해소)
- Test: `tests/test_select_resolve.py`

**Interfaces:**
- Consumes: Task2 의 select 스켈레톤/slot. Produces: `resolve_slot(slot='cellset', values=coord리스트)` 가 fn(grid)→coords 생존자 반환(기존 `_resolve_cellset` 로직 재사용 — 단 vals 가 이미 (r,c) 면 idx//W 변환 스킵). execute 가 `coordinate_of(select(..., coord_in(var(?n))))` 를 `choice[?n](grid)` → coords → 채색.

- [ ] **Step 1: 실패 테스트** — move000a 두 train pair 의 select 스켈레톤+slot 을 `resolve_slot` → 생존자 fn 이 각 train G0 에서 올바른 dest coords 를 냄. + execute(스켈레톤, G0, choice=생존자) == cellset 경로 결과. (동치 pin.)

- [ ] **Step 2: 실패 확인.**

- [ ] **Step 3: 구현:**
  - `_resolve_cellset`: `vals[i]` 원소가 (r,c) 리스트/튜플이면 그대로, 정수 인덱스면 기존 idx//W. (분기 한 줄.) 나머지 로직 불변.
  - `resolve_slot`: kind=='cellset' 경로 그대로(값이 coord 여도 `_resolve_cellset` 이 처리). 필요시 새 kind='select' 를 cellset 과 동일 처리.
  - `_execute_pixel_body`/`_resolve_select_coords`: select 의 coord_in.values 가 `{"var":...}` 면 `choice[var](grid_in)` → coords(정규화), const 면 기존. 반환 coords 정렬.
- [ ] **Step 4: 통과** — `python -m pytest tests/test_select_resolve.py -v` + 전체 스위트 회귀 없음.
- [ ] **Step 5: 커밋** — `feat(resolve): select-var resolve+execute (cellset 동치) (P2a-3)`.

### Task 4: Phase 2a 게이트

- [ ] `python -m pytest -q` 전체 통과.
- [ ] `python -m debugger.score move` = 60/60 (additive — 불변) · `python -m debugger.score objc` = 10/10.
- [ ] 빈 커밋 `test(gate): P2a 완료 — select 지원 additive, move 60/60·objc 10/10 불변`.

---

## Phase 2b — switch: compress + anti-unify skeleton emit 을 cellset → select 로 flip

이제 실제 emission 을 바꾼다. 여기서 move/objc 가 깨지면 select 경로가 cellset 과 **비동치**라는 신호 → 그 지점 진단.

### Task 5: compress emit 전환

**Files:** Modify `procedural_memory/operators/compress.py` (`_blob_body`, `_object_change_program`) — `cellset(const(idxs))` → `coordinate_of(select("input","pixel", coord_in("pixel_coordinate", [[r,c],...])))`. (idxs → (r,c) 변환은 W 로.) 이미 좌표를 아는 자리라 직접 치환.
**Interfaces:** Consumes 2a. Produces: compress 가 select-body grid program 을 grouping 으로 emit.

- [ ] Step 1: 실패/특성 테스트 — `_object_change_program(move000a g0,g1,W)` 결과 JSON 에 `"cellset"` 없음, `"select"` 있음, execute 결과 == g1.
- [ ] Step 2~4: 구현 → 테스트 → **게이트 move 60/60 + objc 10/10**(핵심). 회귀 시 2a 동치 결함 진단·수정.
- [ ] Step 5: 커밋 `feat(compress): emit select(pixel,coord_in) — cellset 폐기 (P2b)`.

### Task 6: report 확인

- [ ] `python -m debugger.reports.program_report move` + `objc` 재생성 → grep: `move_program_report.html` 에 `cellset`(코드 src) 미등장, `select(` 등장. Step A.5 COMPRESS 가 select 표현으로 렌더됨.

---

## Phase 2c — cleanup: 죽은 cellset 경로 제거

### Task 7: dead cellset emit/경로 제거

**Files:** Modify `program_ast.py`(_antiunify_ast_blob 등 select 로 대체돼 미사용분), `compress.py`(cellset import/헬퍼 미사용분). cellset **노드 생성자·execute cellset 분기**는 레거시 안전상 남길 수 있으나, **compress·anti-unify 가 더는 cellset 을 emit 하지 않음**을 grep 으로 고정.
- [ ] `grep -rn 'cellset(' procedural_memory/operators/compress.py` = 0 (emit 없음).
- [ ] 전체 스위트 + 게이트 move 60/60 + objc 10/10.
- [ ] 커밋 `refactor: compress/anti-unify 에서 cellset emit 제거 — select 로 일원화 (P2c)`.

---

## Self-Review (작성자 점검)
- Spec 커버리지: spec §3 C3(compress emit)·C1/C2 확장(coord_in) 을 구현. cellset 제거 = 사용자 핵심 요구.
- 위험: Phase 2b 가 핵심(동치 flip). 2a 가 각 단계 동치를 단위테스트로 미리 pin 하므로 2b 회귀 시 어느 단계 결함인지 국소화됨.
- 타입 일관: coord_in `{"in":{"accessor","values"}}`, select target `coordinate_of(select)`, slot values=coord 리스트 — Task1~5 전반 동일.
- 미결정 여지: `_antiunify_ast_blob` DRY(공통코어 추출) 는 구현자 재량이나 로직 중복 금지 명시.

## 다음 (P2 후)
- **2차**: 픽셀 coord 리스트 → "공통 소속" object 개념으로 승격(select object). 
- 이후 rotate/flip.
