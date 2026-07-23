# Grammar A — P1: 표현 노드 + 실행기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** program AST 에 직렬화되는 `select`/`coordinate_of`/`eq` 표현 노드와 그것을 raw grid 에 해소하는 실행기 경로를 **순수-추가**로 얹어, 이후 phase 가 cellset 을 이 표현으로 대체할 토대를 만든다.

**Architecture:** program_ast.py 에 노드 생성자·to_source 렌더·실행기 분기를 추가한다. 실행기는 raw grid 로부터 `Grid` ARCKG 노드를 만들어 `pixels_of`/property DSL 로 `select` 를 해소한다. 기존 cellset/pixel/coord 경로는 **손대지 않는다** → 아무것도 새 노드를 emit 하지 않으므로 move 60/60 은 불변이어야 한다(행동동치의 정의).

**Tech Stack:** Python 3.11+, unittest, 기존 `arbor.reasoning.program_ast`, `arbor.perception.arckg.grid.Grid`, `procedural_memory.dsl`(pixels_of/pixel_coordinate/pixel_color).

## Global Constraints

- 새 operator/DSL/property 를 임의로 만들지 않는다(ARBOR_HARNESS §1-1). 이 플랜은 기존 DSL(`select`/`pixels_of`/`coordinate_of`/`pixel_coordinate`/`pixel_color`)과 program_ast 표현만 확장한다.
- 결과에 영향 주는 반복은 결정적 키로 정렬한다(§2-6).
- 커밋은 코드 실행·검증(테스트/score) 끝난 뒤에 한다(사용자 규칙 [[commit-after-execution]]).
- 행동보존 게이트: `python -m debugger.score move` = **60/60**. 이 플랜의 어떤 태스크도 이 값을 바꾸면 안 된다(순수 추가).
- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 브랜치 seokki-refactor 에서 작업(이미 이 브랜치).

**범위 경계:** 이 문서는 **P1(표현 노드 + pixel-level 실행기)만** 다룬다. P2(compress emit 전환)·P3(generalize/resolve)·P4(규칙발화 정화)·P5(하네스 갱신)는 P1 이 green 으로 안착한 뒤 각자의 플랜으로 잇는다. object-level `select` 해소는 P2 에서(compress 가 object program 을 emit 할 때) 추가한다 — P1 은 move000a 를 재현하기에 충분한 **pixel-level** 만.

---

## File Structure

- `arbor/reasoning/program_ast.py` (수정) — 노드 생성자(`select`/`coordinate_of`/`eq`), `to_source` 분기, 실행기 분기(`_resolve_select_coords`, `_execute_pixel_body` 훅), 술어 컴파일러(`_compile_pred`). program AST 의 단일 책임을 유지(다른 파일 분할 없음 — 기존 패턴 따름).
- `tests/test_grammar_a_nodes.py` (생성) — 생성자·to_source 단위 테스트.
- `tests/test_grammar_a_execute.py` (생성) — 실행기 해소·cellset 동치 단위 테스트.

---

## Task 1: Grammar A 노드 생성자 + to_source 렌더

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (생성자 블록 `def ref(...)` 근처, `to_source`/`_contents_program_src`)
- Test: `tests/test_grammar_a_nodes.py`

**Interfaces:**
- Produces:
  - `select(grid, level, pred) -> {"select": {"grid": grid, "level": level, "pred": pred}}` — `grid` 는 노드참조 문자열 또는 `"input"`(실행 대상 격자 마커), `level` ∈ {"pixel","object"}, `pred` = eq 노드.
  - `coordinate_of(x) -> {"coordinate_of": x}`
  - `eq(accessor, value) -> {"eq": {"accessor": accessor, "value": value}}` — `accessor` = property DSL 함수명 문자열(예 `"pixel_coordinate"`), `value` = 리터럴.
  - `to_source(ast)` 가 select-target step 을 `coloring(coordinate_of(select(<grid>,<level>, <accessor>==<value>)), color=<c>)` 로 렌더.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_grammar_a_nodes.py
# -*- coding: utf-8 -*-
"""P1 Task1: Grammar A 표현 노드 생성자 + to_source 렌더."""
import unittest
from arbor.reasoning import program_ast as PA


class TestGrammarANodes(unittest.TestCase):
    def test_constructors_shape(self):
        pred = PA.eq("pixel_coordinate", [3, 2])
        self.assertEqual(pred, {"eq": {"accessor": "pixel_coordinate", "value": [3, 2]}})
        sel = PA.select("input", "pixel", pred)
        self.assertEqual(sel["select"]["grid"], "input")
        self.assertEqual(sel["select"]["level"], "pixel")
        self.assertEqual(sel["select"]["pred"], pred)
        co = PA.coordinate_of(sel)
        self.assertIn("coordinate_of", co)

    def test_json_serializable(self):
        import json
        sel = PA.coordinate_of(PA.select("input", "pixel", PA.eq("pixel_coordinate", [3, 2])))
        self.assertEqual(json.loads(json.dumps(sel)), sel)   # 순수 dict(람다 없음)

    def test_to_source_renders_select_target(self):
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_coordinate", [3, 2]))),
                        color=PA.const(0))]
        src = PA.to_source(PA.program(body))
        self.assertIn("select(input, pixel, pixel_coordinate==[3, 2])", src)
        self.assertIn("coordinate_of(", src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_grammar_a_nodes.py -v`
Expected: FAIL — `AttributeError: module 'arbor.reasoning.program_ast' has no attribute 'select'`

- [ ] **Step 3: 생성자 추가**

`program_ast.py` 의 `def ref(level, index_leaf):   return {"ref": level, "index": index_leaf}` 아래에 추가:

```python
# ── Grammar A: 조건-선택 표현 (cellset 대체) ──────────────
def eq(accessor, value):
    """직렬화되는 술어 노드: accessor(property DSL 함수명) 의 값이 value 와 같은가."""
    return {"eq": {"accessor": accessor, "value": value}}


def select(grid, level, pred):
    """grid(노드참조 문자열 또는 'input' 마커) 아래 level 요소 중 pred 맞는 것.
    실행 시 raw grid 로부터 ARCKG 노드를 만들어 pixels_of/objects_of + pred 로 해소."""
    return {"select": {"grid": grid, "level": level, "pred": pred}}


def coordinate_of(x):
    """선택결과 → 좌표(들). coloring target 으로 쓰는 래핑."""
    return {"coordinate_of": x}
```

- [ ] **Step 4: to_source 렌더 추가**

`_contents_program_src` 의 target 분기(`if tgt.get("ref") == "cellset":` … `elif tgt.get("ref") == "coord":` … `else:`)에서, cellset 분기 **앞에** select-target 분기를 추가한다. 그리고 최상위 `to_source` 의 pixel/object 계열 루프(`for i, s in enumerate(body)`)에도 동일 헬퍼를 태우려면, 우선 표시 전용 헬퍼를 하나 두고 두 곳에서 쓴다. 아래 헬퍼를 `_contents_program_src` 위에 추가:

```python
def _sel_src(target):
    """coordinate_of(select(...)) target → 소스 조각. select-target 이 아니면 None."""
    if "coordinate_of" not in target:
        return None
    inner = target["coordinate_of"]
    sel = inner.get("select")
    if sel is None:
        return None
    p = sel["pred"]["eq"]
    return f"coordinate_of(select({sel['grid']}, {sel['level']}, {p['accessor']}=={p['value']}))"
```

그리고 `_contents_program_src` 의 for 루프 첫 줄에서 select-target 을 먼저 처리:

```python
    for s in body:
        tgt = s["args"]["target"]
        col = _leaf_src(s["args"]["color"])
        sel = _sel_src(tgt)
        if sel is not None:
            parts.append(f"coloring({sel}, color={col})")
            continue
        if tgt.get("ref") == "cellset":
            ...
```

또한 최상위 `to_source` 의 pixel/object 루프에서 select-target 을 만나면 한 줄로 렌더한다. `for i, s in enumerate(body):` 루프 안 `tgt = s["args"]["target"]; col = ...` 다음에:

```python
        sel = _sel_src(tgt)
        if sel is not None:
            steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {sel}, {col})")
            continue
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_grammar_a_nodes.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 커밋**

```bash
git add arbor/reasoning/program_ast.py tests/test_grammar_a_nodes.py
git commit -m "$(cat <<'EOF'
feat(ast): Grammar A 노드 select/coordinate_of/eq + to_source 렌더 (P1-1)

직렬화되는 조건-선택 표현(cellset 대체용). 순수 추가 — 아직 아무도 emit 안 함.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 술어 컴파일러 + select 해소 + pixel-level 실행기

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (`_execute_pixel_body`, 신규 `_compile_pred`/`_resolve_select_coords`)
- Test: `tests/test_grammar_a_execute.py`

**Interfaces:**
- Consumes: Task1 의 `select`/`coordinate_of`/`eq`. `arbor.perception.arckg.grid.Grid`, `procedural_memory.dsl.util.pixels_of`, `procedural_memory.dsl.property.pixel_coordinate`/`pixel_color`.
- Produces:
  - `_compile_pred(pred) -> callable(node) -> bool` — `eq` accessor 를 property DSL 함수명으로 해소, 좌표 dict(`{"row_index","col_index"}`)는 `(r,c)` 튜플로 정규화 후 비교.
  - `_resolve_select_coords(target, grid_in) -> list[(r,c)]` — `coordinate_of(select("input", level, pred))` 를 grid_in 으로 해소(정렬된 좌표 목록).
  - `execute(ast, grid_in, choice)` 가 select-target coloring step 을 처리(pixel-level).

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_grammar_a_execute.py
# -*- coding: utf-8 -*-
"""P1 Task2: select-target coloring 실행기 = cellset 과 동치(pixel-level)."""
import unittest
from arbor.reasoning import program_ast as PA


class TestGrammarAExecute(unittest.TestCase):
    def setUp(self):
        # move000a train0 input (8x8, 색7 픽셀 @ (3,2))
        self.g0 = [[0] * 8 for _ in range(8)]
        self.g0[3][2] = 7

    def test_select_pixel_by_coordinate_recolors(self):
        # (3,2) 셀을 0 으로 칠함 = "원위치 비움"
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_coordinate", [3, 2]))),
                        color=PA.const(0))]
        out = PA.execute(PA.program(body), self.g0)
        expect = [[0] * 8 for _ in range(8)]                 # (3,2) 도 0 → 전부 0
        self.assertEqual(out, expect)

    def test_select_paint_matches_cellset(self):
        # (4,3) 셀을 7 로 칠함 — cellset([35]) 프로그램과 동일 결과여야
        W = 8
        sel_prog = PA.program([PA.step("coloring",
                     target=PA.coordinate_of(PA.select("input", "pixel",
                              PA.eq("pixel_coordinate", [4, 3]))), color=PA.const(7))])
        cell_prog = PA.program([PA.step("coloring",
                     target=PA.cellset(PA.const([4 * W + 3])), color=PA.const(7))])
        self.assertEqual(PA.execute(sel_prog, self.g0), PA.execute(cell_prog, self.g0))

    def test_select_pixel_by_color(self):
        # 색7 픽셀을 3 으로 — pixel_color 술어
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_color", 7))),
                        color=PA.const(3))]
        out = PA.execute(PA.program(body), self.g0)
        self.assertEqual(out[3][2], 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_grammar_a_execute.py -v`
Expected: FAIL — select-target 을 만난 `_execute_pixel_body` 가 `_leaf_value` 에서 `ValueError` 또는 오답.

- [ ] **Step 3: 술어 컴파일러 + select 해소 구현**

`program_ast.py` 의 `# ── execute ─` 섹션 위(또는 `_leaf_value` 위)에 추가:

```python
def _norm_coord(v):
    """property 좌표값 정규화: {"row_index":r,"col_index":c} → (r,c); list/tuple → tuple; 그 외 그대로."""
    if isinstance(v, dict) and "row_index" in v and "col_index" in v:
        return (v["row_index"], v["col_index"])
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return v


def _compile_pred(pred):
    """eq 술어 노드 → callable(node)->bool. accessor = property DSL 함수명."""
    from procedural_memory.dsl import property as _prop   # vendored property DSL
    e = pred["eq"]
    accessor = getattr(_prop, e["accessor"])
    want = _norm_coord(e["value"])

    def ok(node):
        return _norm_coord(accessor(node)) == want
    return ok


def _resolve_select_coords(target, grid_in):
    """coordinate_of(select("input", level, pred)) → [(r,c)...] (정렬). select-target 아니면 None."""
    if "coordinate_of" not in target:
        return None
    sel = target["coordinate_of"].get("select")
    if sel is None:
        return None
    from arbor.perception.arckg.grid import Grid
    from procedural_memory.dsl.util import pixels_of, objects_of
    gnode = Grid("_exec", grid_in)
    pred = _compile_pred(sel["pred"])
    if sel["level"] == "pixel":
        chosen = [p for p in pixels_of(gnode) if pred(p)]
        coords = [tuple(p.coord) for p in chosen]
    else:                                                    # object (P2 에서 본격 사용)
        from procedural_memory.dsl.property import coordinate_of as _coord_of
        chosen = [o for o in objects_of(gnode) if pred(o)]
        coords = [tuple(rc) for o in chosen for rc in _coord_of(o)]
    return sorted(coords)
```

- [ ] **Step 4: 실행기 분기 추가**

`_execute_pixel_body` 의 for 루프 첫 부분(`col = _leaf_value(...)` 다음)에서 select-target 을 먼저 처리:

```python
    for s in body:
        tgt = s["args"]["target"]
        col = _leaf_value(s["args"]["color"], grid_in, choice)
        coords = _resolve_select_coords(tgt, grid_in)
        if coords is not None:
            if col is not None:
                for (r, c) in coords:
                    if 0 <= r < H and 0 <= c < W:
                        grid[r][c] = col
            continue
        if tgt.get("ref") == "cellset":
            ...
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_grammar_a_execute.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: 커밋**

```bash
git add arbor/reasoning/program_ast.py tests/test_grammar_a_execute.py
git commit -m "$(cat <<'EOF'
feat(ast): select-target coloring 실행기 = cellset 동치 (P1-2)

_compile_pred(eq→callable, 좌표 dict 정규화) + _resolve_select_coords
(Grid 노드 → pixels_of + pred). pixel-level. object-level 은 P2.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 행동보존 게이트 (move 60/60 불변) + 전체 테스트

**Files:** 없음(검증 전용).

**Interfaces:** Consumes: Task1·Task2 의 추가. Produces: 없음.

- [ ] **Step 1: 전체 단위테스트 통과 확인**

Run: `python -m pytest tests/test_grammar_a_nodes.py tests/test_grammar_a_execute.py tests/test_program_ast.py -v`
Expected: PASS (기존 test_program_ast 회귀 없음 + 신규 통과)

- [ ] **Step 2: move 데이터셋 score 불변 확인 (핵심 게이트)**

Run: `python -m debugger.score move`
Expected: `SCORE: 60/60` (P1 은 순수 추가 — 아무도 새 노드를 emit 하지 않으므로 **반드시 60/60 유지**. 다른 값이면 순수-추가 위반 → 즉시 진단·롤백.)

- [ ] **Step 3: 결정성 확인(§2-6) — 두 seed 로 동일 결과**

Run: `PYTHONHASHSEED=1 python -m debugger.score move && PYTHONHASHSEED=2 python -m debugger.score move`
Expected: 둘 다 `SCORE: 60/60`

- [ ] **Step 4: 게이트 통과 기록 커밋(빈 커밋으로 마일스톤 표시)**

```bash
git commit --allow-empty -m "$(cat <<'EOF'
test(gate): P1 완료 — move 60/60 불변 + Grammar A 노드/실행기 green

표현 노드 + pixel-level 실행기 순수 추가 완료. 다음: P2(compress emit 전환).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (작성자 점검)

- **Spec 커버리지:** 이 플랜은 spec §3 의 **C1(표현 노드)** + **C2(실행기)** 의 pixel-level 부분 = spec §4 의 **P1** 을 구현한다. C3~C6·P2~P5 는 명시적으로 범위 밖(위 "범위 경계"). 누락 없음(P1 한정).
- **Placeholder 스캔:** 모든 step 에 실제 코드/명령/기대출력 있음. "적절히"/"TODO"/"유사" 없음.
- **타입 일관성:** `select`/`coordinate_of`/`eq` 반환 dict 키가 Task1(생성자)·Task2(`_resolve_select_coords`)·to_source(`_sel_src`)에서 동일(`"select"/"grid"/"level"/"pred"/"eq"/"accessor"/"value"/"coordinate_of"`). `pixel_coordinate` 반환 dict 정규화(`_norm_coord`)로 `eq` 비교 일관.
- **행동동치:** P1 은 아무 emit 도 안 바꾸므로 move 60/60 불변이 정의상 성립. Task3 이 이를 게이트로 강제.

---

## 다음 플랜 (P1 green 후)

- **P2** — compress(`_object_change_program`)가 `cellset` 대신 Grammar A(object-level `select` + `coordinate_of`)를 emit. 이때 `_resolve_select_coords` 의 object 분기가 본격 사용됨. 게이트 move 60/60 유지.
- **P3** — generalize(anti-unify) DIFF 재표현 + resolve/verify 의 test-selectability. `@shape#0` 제거.
- **P4** — 규칙발화 정화(object-level·advance_or_finish·sim/recolor-rel).
- **P5** — 하네스 §P5 완화 기록.
