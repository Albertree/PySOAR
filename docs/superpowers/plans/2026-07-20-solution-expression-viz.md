# TASK.solution 표현식 시각화 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** program report 의 TASK.solution 을 불투명한 `cellset` 대신 함수·symbol 조합 표현식(`select(object, …)`, `coordinate(obj)-bottom_right(obj)+(v,w)` 등)으로 렌더하고, DIFF 를 `?varN=expr` 로 변수화해 anti-unification 과정을 드러낸다. Step B 에 픽셀→객체 compress 단계를 가로로 붙인다.

**Architecture:** 순수 문자열 변환 로직(선택자→조건, move→벡터식, solution→표시줄)을 새 모듈 `debugger/reports/solution_expr.py` 로 분리(단위 테스트). `program_report.py` 는 이 모듈을 호출해 Step C(solution) 텍스트뷰를 재구성한다. 시각화-먼저 — 솔버는 불변, 리포트가 기존 survivor/slot/resolved 데이터로 재표기.

**Tech Stack:** Python 3, `unittest`(기존 tests/ 관례), `debugger/reports/program_report.py`, `debugger/solve_cache.py`(run_solve), `arbor/reasoning/program_ast`.

## Global Constraints

- **count 금지 · output_grid symbol 금지**: 모든 표현식은 `input_grid` 객체·속성과 좌표 변환만 사용(P5). `count(`, `output_grid` 문자열이 생성 표현에 나오면 안 된다.
- **PAIR program 렌더 불변**: `display_source(ast)`(slot_exprs 없음) 는 러너-안전 형태 유지. 새 표현식은 **TASK.solution 에만** 적용.
- **회귀 0**: pytest 170 passed/4 skipped 유지, `python -m debugger.score move` = 60/60 불변(솔버 미변경이므로 자동), PAIR program 러너 parity 불변.
- **속성=함수**: `color(o)` `area(o)` `shape(o)` `top_left(o)` `bottom_right(o)` `size(o)` `coordinate(o)`; `o.x` 접근자 금지.
- **선택자→조건 매핑(고정)**: `color=k→color(o) == k` · `size=z→area(o) == z` · `shape#i→shape(o) == shapei` · `bounded→color(o) != 0`.
- **결정성**: 반복은 정렬(PYTHONHASHSEED=0 기준). 변수 번호(`?var1,2,…`)는 solution body 등장 순서로 결정적 부여.
- 커밋은 각 태스크 검증 후(사용자 규칙 [[commit-after-execution]]). 브랜치 `solution-expression-viz`.

---

### Task 1: 선택자 → select 조건식 (`selector_to_condition`)

**Files:**
- Create: `debugger/reports/solution_expr.py`
- Test: `tests/test_solution_expr.py`

**Interfaces:**
- Produces: `selector_to_condition(sel: str|None) -> (cond: str, shape_ref: str|None)` — 솔버 선택자 이름(`"shape#0"`,`"color=2"`,`"size=4"`,`"bounded"`)을 select 조건식으로. shape# 는 `shape_ref`(예 `"shape0"`)를 함께 반환(정의줄 생성용), 그 외 None.

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_solution_expr.py
import unittest
from debugger.reports.solution_expr import selector_to_condition


class TestSelectorToCondition(unittest.TestCase):
    def test_color(self):
        self.assertEqual(selector_to_condition("color=2"), ("color(o) == 2", None))

    def test_size(self):
        self.assertEqual(selector_to_condition("size=4"), ("area(o) == 4", None))

    def test_bounded_is_color_not_zero(self):
        self.assertEqual(selector_to_condition("bounded"), ("color(o) != 0", None))

    def test_shape_returns_ref(self):
        self.assertEqual(selector_to_condition("shape#0"), ("shape(o) == shape0", "shape0"))
        self.assertEqual(selector_to_condition("shape#3"), ("shape(o) == shape3", "shape3"))

    def test_none_or_unknown_faithful(self):
        self.assertEqual(selector_to_condition(None), ("true", None))
        self.assertEqual(selector_to_condition("weird"), ("weird", None))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py -q`
Expected: FAIL — `ModuleNotFoundError: debugger.reports.solution_expr`

- [ ] **Step 3: 최소 구현**

```python
# debugger/reports/solution_expr.py
# -*- coding: utf-8 -*-
"""TASK.solution 표현식 렌더 — 솔버 선택자/resolved 를 함수·symbol 조합 표현식으로 재표기.
설계: docs/superpowers/specs/2026-07-20-solution-expression-viz-design.md. 시각화-먼저(솔버 불변).
금지: count·output_grid symbol (P5, input_grid 만)."""
from __future__ import annotations
import re


def selector_to_condition(sel):
    """솔버 선택자 이름 → (select 조건식, shape_ref|None). 채택된 선택자 충실 렌더.
    bounded → color(o) != 0 (표현계층 색0≠배경 완화, 설계 §3-2)."""
    if not sel:
        return "true", None
    if sel.startswith("color="):
        return f"color(o) == {sel[len('color='):]}", None
    if sel.startswith("size="):
        return f"area(o) == {sel[len('size='):]}", None
    if sel == "bounded":
        return "color(o) != 0", None
    if sel.startswith("shape#"):
        ref = f"shape{sel[len('shape#'):]}"
        return f"shape(o) == {ref}", ref
    return sel, None                       # 정직 fallback (row=/col= 등 move 미사용)
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/solution_expr.py tests/test_solution_expr.py
git commit -m "feat(report): selector_to_condition — 솔버 선택자→select 조건식 (bounded→color!=0)"
```

---

### Task 2: 이동 resolved → 벡터 산술식 (`move_to_vector`)

**Files:**
- Modify: `debugger/reports/solution_expr.py`
- Test: `tests/test_solution_expr.py`

**Interfaces:**
- Consumes: `selector_to_condition` (동일 모듈)
- Produces: `move_to_vector(row_tok: str, col_tok: str, objvar: str) -> str` — resolved `move[ROW,COL]` 의 축 토큰과 객체변수명으로 벡터-산술 표현식. 앵커: 제자리`coordinate(obj)` · 상대`coordinate(obj) + (Δr,Δc)` · 절대`coordinate(obj) - top_left(obj) + (r,c)` · 끝`… + (0,c)` · 코너`coordinate(obj) - bottom_right(obj) + bottom_right(input_grid)` · BR`coordinate(obj) - bottom_right(obj) + (v,w)`. 혼합축은 성분별.

- [ ] **Step 1: 실패 테스트 작성 (tests/test_solution_expr.py 에 추가)**

```python
from debugger.reports.solution_expr import move_to_vector


class TestMoveToVector(unittest.TestCase):
    def test_keep_is_bare_coordinate(self):
        self.assertEqual(move_to_vector("r0+0", "c0+0", "obj0"), "coordinate(obj0)")

    def test_relative_delta(self):
        self.assertEqual(move_to_vector("r0+1", "c0+1", "obj0"),
                         "coordinate(obj0) + (1, 1)")
        self.assertEqual(move_to_vector("r0-2", "c0+3", "obj0"),
                         "coordinate(obj0) + (-2, 3)")

    def test_br_both_axes(self):
        self.assertEqual(move_to_vector("BR=2", "BR=2", "obj0"),
                         "coordinate(obj0) - bottom_right(obj0) + (2, 2)")

    def test_absolute_both_axes(self):
        self.assertEqual(move_to_vector("=1", "=1", "obj0"),
                         "coordinate(obj0) - top_left(obj0) + (1, 1)")

    def test_edge_both_axes(self):
        self.assertEqual(move_to_vector("0", "0", "obj0"),
                         "coordinate(obj0) - top_left(obj0) + (0, 0)")

    def test_grid_corner(self):
        self.assertEqual(move_to_vector("H-h", "W-w", "obj0"),
                         "coordinate(obj0) - bottom_right(obj0) + bottom_right(input_grid)")

    def test_mixed_abs_row_br_col(self):
        # 축별 다른 모델: row 절대=1, col BR=2 → 성분별 anchor/target
        self.assertEqual(move_to_vector("=1", "BR=2", "obj0"),
                         "coordinate(obj0) - (top_left(obj0).r, bottom_right(obj0).c) + (1, 2)")
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py::TestMoveToVector -q`
Expected: FAIL — `ImportError: cannot import name 'move_to_vector'`

- [ ] **Step 3: 구현 (solution_expr.py 에 추가)**

```python
def _parse_axis(tok):
    """이동 축 토큰 → (kind, target, anchor_comp_kind). kind: rel|abs|edge|corner|br|raw.
    anchor_comp_kind: 'tl'(top_left)|'br'(bottom_right)|'0'(없음=상대). target: int|'corner'|str."""
    m = re.match(r"^[rc]0([+-]\d+)$", tok)
    if m:
        return ("rel", int(m.group(1)), "0")
    if tok.startswith("BR="):
        return ("br", int(tok[len("BR="):]), "br")
    if tok.startswith("="):
        return ("abs", int(tok[len("="):]), "tl")
    if tok == "0":
        return ("edge", 0, "tl")
    if tok in ("H-h", "W-w"):
        return ("corner", "corner", "br")
    return ("raw", tok, "0")


def move_to_vector(row_tok, col_tok, objvar):
    """resolved move[ROW,COL] → 벡터-산술 표현식(설계 §3-4). 같은-모델은 깔끔형, 혼합은 성분별."""
    r = _parse_axis(row_tok)
    c = _parse_axis(col_tok)
    coord = f"coordinate({objvar})"
    # 제자리(둘 다 rel Δ0)
    if r[0] == "rel" and c[0] == "rel":
        if r[1] == 0 and c[1] == 0:
            return coord
        return f"{coord} + ({r[1]}, {c[1]})"
    # 둘 다 격자코너
    if r[0] == "corner" and c[0] == "corner":
        return f"{coord} - bottom_right({objvar}) + bottom_right(input_grid)"
    # 앵커 성분(각 축)과 target 성분
    def _anchor(comp, axis):                       # axis: 'r'|'c'
        if comp == "tl":
            return f"top_left({objvar}).{axis}"
        if comp == "br":
            return f"bottom_right({objvar}).{axis}"
        return "0"                                 # 상대축은 anchor 0
    def _target(kind, tgt, axis):
        if kind == "corner":
            return f"bottom_right(input_grid).{axis}"
        return str(tgt)                            # rel Δ / abs v / br v / edge 0
    ar, ac = _anchor(r[2], "r"), _anchor(c[2], "c")
    tr, tc = _target(r[0], r[1], "r"), _target(c[0], c[1], "c")
    # 두 축 anchor 종류 같으면 whole-point 형태(top_left(obj)/bottom_right(obj))
    if r[2] == c[2] and r[2] in ("tl", "br"):
        whole = "top_left" if r[2] == "tl" else "bottom_right"
        return f"{coord} - {whole}({objvar}) + ({tr}, {tc})"
    # 혼합: 성분별 anchor
    return f"{coord} - ({ar}, {ac}) + ({tr}, {tc})"
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py -q`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/solution_expr.py tests/test_solution_expr.py
git commit -m "feat(report): move_to_vector — 이동 resolved→벡터산술식(제자리/상대/절대/끝/코너/BR/혼합)"
```

---

### Task 3: solution → 표시줄 조립 (`render_solution_lines`)

**Files:**
- Modify: `debugger/reports/solution_expr.py`
- Test: `tests/test_solution_expr.py`

**Interfaces:**
- Consumes: `selector_to_condition`, `move_to_vector`
- Produces: `render_solution_lines(solution_ast, resolved, comm, shapes) -> list[str]` —
  - `solution_ast`: `T.property ^solution` dict
  - `resolved`: `{ "?c.cells1": "move[BR=2,BR=2]@color=2", "?c.color1": "color@color=2", ... }`
  - `comm`: `{"size": bool, "color": bool}` — set_grid_size/color 가 pair 간 COMM(값 동일)인지 (`_compare_asts` 파생). True=COMM(리터럴), False=DIFF(변수화)
  - `shapes`: `{ "shape0": [[1,-1],[1,1]] }` — shape# 참조용 2d array (Task 4 에서 채움; 없으면 `[]` 자리표시)
  - 반환: 표시할 텍스트 라인 리스트(설계 §5 형태). 객체 바인딩·shape 정의·`?varN` 정의·본문.

- [ ] **Step 1: 실패 테스트 작성 (tests/test_solution_expr.py 에 추가)**

```python
from debugger.reports.solution_expr import render_solution_lines


class TestRenderSolutionLines(unittest.TestCase):
    def _sol(self):
        return {"body": [
            {"call": "set_grid_size", "args": {"size": {"const": {"height": 8, "width": 8}}}},
            {"call": "set_grid_color", "args": {"color": {"expr": "color(input_grid)"}}},
            {"call": "set_grid_contents", "args": {"contents": {"program": {"body": [
                {"call": "coloring", "args": {"target": {"ref": "cellset", "cells": {"var": "?c.cells0"}},
                                              "color": {"const": 0}}},
                {"call": "coloring", "args": {"target": {"ref": "cellset", "cells": {"var": "?c.cells1"}},
                                              "color": {"var": "?c.color1"}}},
            ]}}}]}

    def test_move000a_shape_relative(self):
        resolved = {"?c.cells0": "move[r0+0,c0+0]@shape#0",
                    "?c.cells1": "move[r0+1,c0+1]@shape#0",
                    "?c.color1": "color@shape#0"}
        lines = render_solution_lines(self._sol(), resolved,
                                      {"size": True, "color": False},
                                      {"shape0": [[1, -1], [1, 1]]})
        text = "\n".join(lines)
        self.assertIn("shape0 = [[1, -1], [1, 1]]", text)
        self.assertIn("obj0 = select(object, shape(o) == shape0)", text)
        self.assertIn("set_grid_size = (8, 8)", text)                 # COMM → 리터럴
        self.assertIn("?var1 = color(input_grid)", text)              # DIFF color → 변수
        self.assertIn("set_grid_color = ?var1", text)
        self.assertIn("?var2 = coordinate(obj0)", text)               # cells0 제자리
        self.assertIn("coloring(?var2, 0)", text)                     # 지우기(색0 리터럴)
        self.assertIn("?var3 = coordinate(obj0) + (1, 1)", text)      # cells1 상대이동
        self.assertIn("?var4 = color(obj0)", text)                    # color1
        self.assertIn("coloring(?var3, ?var4)", text)
        self.assertNotIn("cellset", text)                            # raw cellset 제거
        self.assertNotIn("?c.", text)                                # 내부 슬롯명 노출 안 함

    def test_bounded_br_uses_color_not_zero(self):
        resolved = {"?c.cells0": "move[r0+0,c0+0]@bounded",
                    "?c.cells1": "move[BR=2,BR=2]@bounded",
                    "?c.color1": "color@bounded"}
        text = "\n".join(render_solution_lines(self._sol(), resolved,
                        {"size": True, "color": False}, {}))
        self.assertIn("obj0 = select(object, color(o) != 0)", text)
        self.assertIn("coordinate(obj0) - bottom_right(obj0) + (2, 2)", text)
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py::TestRenderSolutionLines -q`
Expected: FAIL — `ImportError: cannot import name 'render_solution_lines'`

- [ ] **Step 3: 구현 (solution_expr.py 에 추가)**

```python
def _split_move(resolved_val):
    """'move[ROW,COL]@sel' → (row_tok, col_tok, sel). 파싱 실패 시 (None,None,None)."""
    m = re.match(r"^move\[(.+?),(.+?)\](?:@(.+))?$", resolved_val)
    if not m:
        return None, None, None
    return m.group(1), m.group(2), (m.group(3) or None)


def _sel_of(resolved_val):
    """resolved 값의 @선택자 ('move[..]@color=2'→'color=2', 'color@bounded'→'bounded')."""
    return resolved_val.rsplit("@", 1)[1] if "@" in resolved_val else None


def render_solution_lines(solution_ast, resolved, comm, shapes):
    """설계 §5 형태의 표시줄 리스트. 시각화-먼저(솔버 데이터 재표기). 결정적."""
    body = solution_ast.get("body") or []
    parts = {s["call"]: s["args"] for s in body}
    # 1) 공통 선택자 → 객체 바인딩 obj0 (선택자-일관: 모든 슬롯 동일 @sel)
    sel = next((_sel_of(v) for v in resolved.values() if _sel_of(v)), None)
    cond, shape_ref = selector_to_condition(sel)
    lines = []
    if shape_ref is not None:
        lines.append(f"{shape_ref} = {shapes.get(shape_ref, '[]')}")
    lines.append(f"obj0 = select(object, {cond})")
    objvar = "obj0"
    var_i = [0]

    def _new_var():
        var_i[0] += 1
        return f"?var{var_i[0]}"

    # 2) set_grid_size (COMM→리터럴, DIFF→변수화)
    sz = parts["set_grid_size"]["size"]
    if comm.get("size", True):
        v = sz.get("const") or {}
        lit = f"({v.get('height')}, {v.get('width')})" if isinstance(v, dict) else str(v)
        lines.append(f"set_grid_size = {lit}")
    else:
        vn = _new_var(); lines.append(f"{vn} = size(input_grid)")
        lines.append(f"set_grid_size = {vn}")
    # 3) set_grid_color
    co = parts["set_grid_color"]["color"]
    if comm.get("color", True):
        lines.append(f"set_grid_color = {co.get('const', co.get('expr'))}")
    else:
        vn = _new_var(); lines.append(f"{vn} = color(input_grid)")
        lines.append(f"set_grid_color = {vn}")
    # 4) coloring 스텝 (cellset=DIFF 슬롯 → 변수화; color=const→리터럴/var→color(obj))
    prog = parts["set_grid_contents"]["contents"].get("program", {}).get("body", [])
    for s in prog:
        tgt = s["args"]["target"]; colr = s["args"]["color"]
        cell_var = tgt.get("cells", {}).get("var") if tgt.get("ref") == "cellset" else None
        # 좌표 변수
        if cell_var and cell_var in resolved:
            rt, ct, _ = _split_move(resolved[cell_var])
            expr = move_to_vector(rt, ct, objvar) if rt else f"coordinate({objvar})"
        else:
            expr = f"coordinate({objvar})"
        vcoord = _new_var(); lines.append(f"{vcoord} = {expr}")
        # 색
        if "const" in colr:
            cterm = str(colr["const"])
        else:
            cvar = colr.get("var")
            vcol = _new_var(); lines.append(f"{vcol} = color({objvar})")
            cterm = vcol
        lines.append(f"coloring({vcoord}, {cterm})")
    return lines
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr.py -q`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/solution_expr.py tests/test_solution_expr.py
git commit -m "feat(report): render_solution_lines — DIFF 변수화+함수식 조립(cellset 은퇴, ?varN)"
```

---

### Task 4: shape 2d array 역추적 + COMM 판정 헬퍼

**Files:**
- Modify: `debugger/reports/program_report.py`
- Test: `tests/test_solution_expr_integration.py` (신규)

**Interfaces:**
- Consumes: WM(`_collect` 결과), `arbor.reasoning.antiunify._components`, `_compare_asts`(기존 program_report)
- Produces (program_report.py 내부 헬퍼):
  - `_shapes_for(resolved, slots, train_inputs) -> {shape_ref: 2d array}` — shape# 선택자가 있으면 mover 객체(pair0)의 shape property(bbox 2D, 1/-1) 를 역추적. mover = resolved cellset DIFF 의 pair0 셀들이 속한 객체.
  - `_solution_comm(pair_asts) -> {"size": bool, "color": bool}` — pair0/pair1 program 의 set_grid_size/color 값 동일 여부(`_compare_asts` 재사용, 없으면 True).

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_solution_expr_integration.py
import glob, json, unittest
from debugger.solve_cache import run_solve


def _load(tid):
    return json.load(open(glob.glob(f"data/**/move/{tid}.json", recursive=True)[0]))


class TestSolutionExprIntegration(unittest.TestCase):
    def test_move000a_full_render_has_expressions(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000a", _load("move000a"))
        self.assertIn("select(object", html)
        self.assertIn("coordinate(obj0)", html)
        self.assertNotIn("cellset=?c.cells", html)      # raw cellset 제거

    def test_bounded_task_uses_color_not_zero(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000o", _load("move000o"))
        self.assertIn("color(o) != 0", html)
        self.assertIn("bottom_right(obj0)", html)       # BR 앵커
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr_integration.py -q`
Expected: FAIL (아직 program_report 통합 전 — `cellset` 잔존 또는 `select(object` 없음)

- [ ] **Step 3: 헬퍼 구현 (program_report.py 에 추가, import 상단에 `from debugger.reports import solution_expr as SE`)**

```python
def _solution_comm(pair_asts):
    """pair0/pair1 program 의 set_grid_size/color COMM(값 동일) 여부. pair<2 면 전부 COMM 취급."""
    if len(pair_asts) < 2:
        return {"size": True, "color": True}
    p0 = {s["call"]: s["args"] for s in pair_asts[0].get("body", [])}
    p1 = {s["call"]: s["args"] for s in pair_asts[1].get("body", [])}
    def _same(call, key):
        a = p0.get(call, {}).get(key); b = p1.get(call, {}).get(key)
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return {"size": _same("set_grid_size", "size"), "color": _same("set_grid_color", "color")}


def _shapes_for(resolved, slots, train_inputs):
    """shape# 선택자 참조 → mover(pair0) 객체 shape 2d array(1=채움,-1=빈칸). 없으면 {}."""
    from arbor.reasoning.antiunify import _components, _obj_atoms
    refs = {}
    for val in resolved.values():
        sel = SE._sel_of(val)
        if not (sel and sel.startswith("shape#")):
            continue
        ref = f"shape{sel[len('shape#'):]}"
        if ref in refs:
            continue
        # mover(pair0): resolved cellset DIFF pair0 셀 인덱스가 속한 객체
        cell_slot = next((n for n, v in resolved.items() if v == val and n.startswith("?c.cells")), None)
        p0cells = (slots.get(cell_slot) or [[]])[0] if cell_slot else []
        if not (p0cells and train_inputs):
            continue
        g0 = train_inputs[0]; W = len(g0[0])
        want = {(i // W, i % W) for i in p0cells}
        for cells, _col in _components(g0):
            if want & set(cells):
                a = _obj_atoms(cells, g0)
                refs[ref] = a["shape"]           # ARCKG object shape (bbox 2D 1/-1)
                break
    return refs
```

- [ ] **Step 4: (통합은 Task 5 에서) 헬퍼 단위 확인**

Run: `PYTHONHASHSEED=0 python3 -c "from debugger.reports.program_report import _solution_comm, _shapes_for; print('helpers OK')"`
Expected: `helpers OK` (import 성공)

> 참고: `slots` 는 `?c.cellsN[cellset]=DIFF[[…],[…]]` 파싱값 `{slot_name: [pair0_cells, pair1_cells, …]}`. `_collect` 확장(Task 5)에서 함께 수집한다. `_obj_atoms` 의 `shape` 키 존재는 `arbor/reasoning/antiunify.py::_obj_atoms` 에서 확인(없으면 ARCKG object.to_json()["shape"] 로 대체).

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/program_report.py tests/test_solution_expr_integration.py
git commit -m "feat(report): _solution_comm/_shapes_for — COMM 판정·shape 역추적 헬퍼"
```

---

### Task 5: program_report Step C 통합 (cellset 뷰 → 표현식 뷰)

**Files:**
- Modify: `debugger/reports/program_report.py`

**Interfaces:**
- Consumes: `SE.render_solution_lines`, `_solution_comm`, `_shapes_for`, `_collect`(슬롯 파싱 확장)
- Produces: TASK.solution ① text 뷰가 `render_solution_lines` 결과로 렌더. `_collect` 는 `slots`(`{?c.X: [pair별 cells]}`) 도 수집해 반환.

- [ ] **Step 1: `_collect` 에 slots 파싱 추가** — 기존 `slot_exprs` 옆에 `slots` 수집. `^slot` 값 `?c.cells0[cellset]=DIFF[[26],[48]]` 파싱:

```python
    slot_vals = {}                                    # {?c.X: [pair0_cells, pair1_cells, ...]}
    for (i, a, v) in wm:
        if a == "slot" and isinstance(v, str) and v.startswith("?c."):
            nm = v.split("[", 1)[0]
            mm = re.search(r"=(?:DIFF|COMM)?(\[.*\])$", v)
            if mm:
                try:
                    slot_vals[nm] = json.loads(mm.group(1))
                except (ValueError, TypeError):
                    pass
    return asts, pairs, solution, attempts, slot_exprs, slot_vals
```

(early return 및 5→6 튜플로: `return [], [], None, [], {}, {}`. 호출부 `task_section`/`build` 언패킹 6개로.)

- [ ] **Step 2: `task_section` 에서 solution ① 뷰를 표현식으로** — `_solution_row` 로 넘기기 전, solution 표시줄을 미리 만들어 `_pair_block` 이 쓰도록 옵션 추가. `_pair_block(label, ast, ex, slot_exprs=None, sol_lines=None)`: `sol_lines` 있으면 ① `<pre class="src">` 를 `"\n".join(sol_lines)` 로 대체(② AST·③ 시각화는 그대로).

```python
# task_section 내
sol_lines = None
if solution is not None:
    comm = _solution_comm([a for a, _p in zip(asts, pairs)])
    shapes = _shapes_for(slot_exprs, slot_vals, [task["train"][p]["input"] for p in pairs])
    sol_lines = SE.render_solution_lines(solution, slot_exprs, comm, shapes)
solrow = _solution_row(ast_ex_pairs, solution, slot_exprs, sol_lines)
```

`_solution_row(..., sol_lines=None)` 은 solution `_pair_block` 호출에 `sol_lines=sol_lines` 전달. `_pair_block` 은 `sol_lines` 있으면 ① src 를 그것으로 렌더.

- [ ] **Step 3: 통합 테스트 통과 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr_integration.py -q`
Expected: PASS (2 tests) — `select(object` 등장, `cellset=?c.cells` 제거, bounded→`color(o) != 0`

- [ ] **Step 4: move 리포트 재생성 + 육안 검증**

Run: `PYTHONHASHSEED=0 python3 -c "from debugger.reports.program_report import build_move; print(build_move())"`
Then: `grep -c 'select(object' debugger/reports/move_program_report.html` (>0), `grep -c 'cellset=?c.cells' debugger/reports/move_program_report.html` (=0)
Expected: 표현식 다수, raw cellset 0

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/program_report.py
git commit -m "feat(report): Step C TASK.solution 을 함수식 표현으로 렌더(cellset→select/coordinate/?varN)"
```

---

### Task 6: Step B — 픽셀→객체 compress 단계 시각화

**Files:**
- Modify: `debugger/reports/program_report.py`
- Modify: `debugger/reports/program_report.py` (CSS 블록)

**Interfaces:**
- Consumes: `_collect`(P{k} 픽셀/객체 program 은 WM 에서 별도 수집), `_thumb`/`_viz`(기존 시각화)
- Produces: `_compress_stages(tid, pair_index, wm) -> html` — pair 의 픽셀 program(coloring 좌표들) → 4-인접 동색 그룹핑 → 객체 program(cellset) 을 가로 단계로. Step B `stepBcontent` 오른쪽에 삽입.

- [ ] **Step 1: 실패 테스트 작성 (tests/test_solution_expr_integration.py 에 추가)**

```python
    def test_compress_stages_present_for_move(self):
        from debugger.reports import program_report as pr
        html = pr.task_section("move000ah", _load("move000ah"))
        self.assertIn("compress", html.lower())          # compress 단계 라벨 등장
        self.assertIn("픽셀", html)                       # 픽셀 단계 라벨
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr_integration.py::TestSolutionExprIntegration::test_compress_stages_present_for_move -q`
Expected: FAIL

- [ ] **Step 3: 구현** — `_collect` 이 `pixel_programs`/`object_programs`(P{k}.program/grouping) 를 수집하도록 확장하거나, `task_section` 에서 WM 재조회. `_compress_stages` 는 각 pair 에 대해 `[픽셀 program 요약]→[그룹핑]→[객체 program 요약]` 단계 박스를 가로로 생성. `_solution_row` 의 Step B `stepBcontent` 에 이어붙인다. (구체 HTML 은 기존 `_thumb`·`.row`·`.gflow` 관례 재사용; 단계 라벨 "픽셀 program"→"4-인접 그룹핑"→"객체 program".) CSS 는 가로 스크롤 컨테이너(`overflow-x:auto`) 추가.

> 상세 마크업은 구현 시 기존 `_grid_step_rows`/`_viz` 패턴을 따르되, 데이터는 `P{k}.program`(픽셀)·`P{k}.grouping`(객체) 두 AST 를 `_viz` 로 각각 렌더하고 그 사이에 "→ 4-인접 동색 그룹핑 →" 화살표 단계를 둔다. 픽셀 program 이 곧 좌표+색이므로 균일하게 항상 표시.

- [ ] **Step 4: 통과 + 재생성 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_solution_expr_integration.py -q`
Then: `PYTHONHASHSEED=0 python3 -c "from debugger.reports.program_report import build_move; print(build_move())"`
Expected: PASS; move_program_report.html 에 compress 단계 렌더

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/program_report.py
git commit -m "feat(report): Step B 에 픽셀→객체 compress 단계 시각화(가로 확장)"
```

---

### Task 7: 전체 회귀 + 최종 재생성

**Files:** (없음 — 검증·재생성만)

- [ ] **Step 1: 전체 테스트**

Run: `PYTHONHASHSEED=0 python3 -m pytest -q`
Expected: `170 passed, 4 skipped`(+ 신규 solution_expr 테스트) — 회귀 0

- [ ] **Step 2: PAIR program 러너 parity 불변 확인**

Run: `PYTHONHASHSEED=0 python3 -m pytest tests/test_program_parity.py tests/test_display_source.py -q`
Expected: PASS — PAIR program 렌더는 slot_exprs=None 유지로 불변

- [ ] **Step 3: move 게이트 불변(솔버 미변경)**

Run: `PYTHONHASHSEED=0 python3 -m debugger.score move`
Expected: `SCORE: 60/60`

- [ ] **Step 4: 리포트 최종 재생성 + 금지어 검사**

Run:
```bash
PYTHONHASHSEED=0 python3 -c "from debugger.reports.program_report import build_move, build_objc; print(build_move()); print(build_objc())"
grep -c 'cellset=?c.cells' debugger/reports/move_program_report.html   # 0
grep -c 'count(' debugger/reports/move_program_report.html             # 0 (금지어)
grep -c 'output_grid' debugger/reports/move_program_report.html        # solution 표현식엔 없어야(PAIR program 은 있음 — solution 영역만 확인은 육안)
```
Expected: raw cellset 0, count 0

- [ ] **Step 5: 커밋**

```bash
git add -A debugger/ docs/
git commit -m "chore(report): solution 표현식 시각화 완료 — 회귀 0, move 60/60 불변, cellset 은퇴(표시)"
```

---

## Self-Review 노트

- **Spec 커버리지**: 표현문법(Task1-2)·변수화(Task3)·shape/COMM(Task4)·통합(Task5)·compress(Task6)·회귀(Task7) = 설계 §3-6 전부 대응.
- **타입 일관성**: `selector_to_condition`→(str,str|None), `move_to_vector`→str, `render_solution_lines`→list[str], `_collect`→6-tuple(slots 추가). 호출부 언패킹 Task5 에서 갱신.
- **리스크**: `_obj_atoms` 의 `shape` 키·`_components` import 경로는 Task4 Step4 에서 확인(없으면 ARCKG object.to_json()["shape"]). compress HTML(Task6)은 기존 `_viz` 재사용으로 위험 축소. 혼합 앵커는 Task2 test 로 커버.
