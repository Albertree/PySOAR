# program/solution AST 저장형 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PAIR.program / TASK.solution 의 canonical 저장형을 flat Python 문자열에서 균일 typed-arg nested-dict AST 로 바꾸되, easy_a 9태스크 step 수를 완전 보존한다.

**Architecture:** 신규 `arbor/reasoning/program_ast.py` 에 스키마·`to_source`·`execute`·`render_header`·`ops_of_ast`·`antiunify_ast` 를 모은다. 모든 program/solution **읽기** 지점을 `as_source()`(legacy 문자열/AST-json 모두 flat 문자열로 정규화)로 감싼 뒤, **쓰기(emit)** 지점을 하나씩 AST-json 으로 뒤집는다. 마지막에 anti-unify 내부를 정규식 파싱→AST 로, 그리고 anti-unify 대시보드 뷰를 실제 저장 AST 로 교체한다.

**Tech Stack:** Python 3 (표준 라이브러리만), `unittest`, SOAR 커널(`soar/`), vendored ARCKG(`arbor/perception/arckg/`).

## Global Constraints

- **행동보존 게이트 (모든 flip 태스크 필수):** `PYTHONPATH=. python3 tests/verify_refactor.py` 가 `PASS: 9/9 step 일치` 를 내야 한다. 하나라도 MISMATCH 면 그 커밋은 실패 — 되돌린다. (easy000a=1227, b=1227, c=2851, d=2851, e=2890, f=2890, g=2851, h=2851, i=2740)
- **새 operator/DSL/transformation atom 금지** (ARBOR_HARNESS.md §1-1). transformation atom 은 `coloring`·`make_grid` 2개 동결. 이 작업은 storage/serialization 변경이지 새 풀이 능력 추가가 아니다.
- **문자열 exec/eval 금지.** 실행은 AST 인터프리터로만 (오늘 `execute_solution` 과 동일 철학).
- **ARCKG 노드 미수정.** Pixel/Object 에 `.coord` 등 추가하지 않는다 — 이름차(`.coord`↔`.coordinate`)는 인터프리터가 흡수.
- 단위 테스트 실행: `python -m unittest tests.test_program_ast -v`. (이 환경엔 pytest 없음 — `unittest` 사용.)
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 스펙: `docs/superpowers/specs/2026-07-15-program-ast-design.md`.

---

## 파일 구조

- **Create** `arbor/reasoning/program_ast.py` — AST 스키마·`to_source`·`execute`·`render_header`·`ops_of_ast`·`antiunify_ast`·`as_source`. (신규, 이 작업의 핵심)
- **Create** `tests/test_program_ast.py` — 위 모듈 단위 테스트 (unittest).
- **Modify** `arbor/reasoning/program.py` — `_pixel_residual_program`·`_global_recolor_program` 이 AST(json) 방출.
- **Modify** `arbor/reasoning/antiunify.py` — `render_skeleton`→`to_source` 위임, `execute_solution`→`execute` 위임, `parse_program`(정규식) 은퇴, `antiunify`→`antiunify_ast` 위임. `_align`·`resolve_slot`·`solution_candidates` 는 **유지**.
- **Modify** `procedural_memory/operators/coloring.py` — `program-code` 를 AST(json) 로 방출.
- **Modify** `procedural_memory/operators/verify.py` — program 읽기/쓰기 `as_source` 정규화, sentinel `null`.
- **Modify** `procedural_memory/operators/hypothesize.py` — `base-program` 읽기 `as_source`.
- **Modify** `procedural_memory/operators/generalize.py` — program 읽기 `as_source`→AST, `antiunify_ast` 사용.
- **Modify** `procedural_memory/operators/compose.py` — `execute`·`to_source` 사용.
- **Modify** `procedural_memory/operators/synthesize.py` — GRID-closure program 을 AST 로.
- **Modify** `arbor/perception/nav.py` — 빈 슬롯 sentinel `"{}"`→`null`(빈 program).
- **Modify** `debugger/reports/easy_antiunify_viz.py` — 저장 AST + 실제 compare 결과로 렌더.

---

## Task 1: AST 스키마 + `to_source`

`program_ast.py` 를 만들고 AST 생성자와, AST→현행 flat Python 문자열을 **바이트 동일**하게 내는 `to_source` 를 구현한다. (P1)

**Files:**
- Create: `arbor/reasoning/program_ast.py`
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Produces:
  - `const(v) -> {"const": v}` · `var(name) -> {"var": name}` · `expr(e) -> {"expr": e}` · `ref(level, index_leaf) -> {"ref": level, "index": index_leaf}`
  - `step(op, **args) -> {"call": op, "args": {...}}`
  - `program(body, input_grid="G0", output="grid", slots=None) -> dict`
  - `to_source(ast: dict) -> str` (AST → flat Python; 빈/None → `"output_grid = input_grid"` 아님, 아래 규칙)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_program_ast.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.reasoning import program_ast as P


class TestToSource(unittest.TestCase):
    def test_two_step_pixel_program_roundtrips_to_exact_legacy_string(self):
        ast = P.program([
            P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3)),
            P.step("coloring", target=P.ref("pixel", P.const(12)), color=P.const(3)),
        ])
        expected = (
            "in_px = pixels_of(input_grid)\n"
            "P0 = in_px[5]\n"
            "P1 = in_px[12]\n"
            "\n"
            "tfg0 = input_grid\n"
            "tfg1 = apply_DSL(tfg0, coloring, P0.coord, 3)\n"
            "tfg2 = apply_DSL(tfg1, coloring, P1.coord, 3)\n"
            "output_grid = tfg2"
        )
        self.assertEqual(P.to_source(ast), expected)

    def test_object_level_uses_in_objs(self):
        ast = P.program([P.step("coloring", target=P.ref("object", P.const(3)), color=P.const(4))])
        src = P.to_source(ast)
        self.assertIn("in_objs = objects_of(input_grid)", src)
        self.assertIn("O0 = in_objs[3]", src)
        self.assertIn("apply_DSL(tfg0, coloring, O0.coord, 4)", src)

    def test_slot_variable_renders_name_not_value(self):
        ast = P.program(
            [P.step("coloring", target=P.ref("pixel", P.var("?src0")), color=P.var("?color0"))],
            slots={"?src0": {"kind": "src", "pos": 0}, "?color0": {"kind": "color", "pos": 0}},
        )
        src = P.to_source(ast)
        self.assertIn("P0 = in_px[?src0]", src)
        self.assertIn("apply_DSL(tfg0, coloring, P0.coord, ?color0)", src)

    def test_empty_program_is_none_source(self):
        self.assertEqual(P.to_source(None), "{}")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arbor.reasoning.program_ast'`

- [ ] **Step 3: 최소 구현**

```python
# arbor/reasoning/program_ast.py
# -*- coding: utf-8 -*-
"""ARBOR program AST — PAIR.program / TASK.solution 의 canonical 저장형.

균일 typed-arg nested-dict:
  program = {"input": {"grid": "G0"}, "body": [step...], "output": {"var": "grid"}, "slots"?: {...}}
  step    = {"call": op, "args": {name: leaf|node}}
  leaf    = {"const": v} | {"var": name} | {"expr": e} | {"ref": level, "index": leaf}
op ∈ frozen transformation atom (coloring, make_grid) 만. 그 외는 조합.

to_source(ast) 는 현행 flat Python 문자열과 바이트 동일을 낸다(이행 안전장치·복붙 실행용).
"""
from __future__ import annotations
import json


# ── 생성자 ──────────────────────────────────────────────
def const(v):                 return {"const": v}
def var(name):                return {"var": name}
def expr(e):                  return {"expr": e}
def ref(level, index_leaf):   return {"ref": level, "index": index_leaf}


def step(op, **args):
    return {"call": op, "args": dict(args)}


def program(body, input_grid="G0", output="grid", slots=None):
    p = {"input": {"grid": input_grid}, "body": list(body), "output": {"var": output}}
    if slots is not None:
        p["slots"] = slots
    return p


# ── leaf → 소스 조각 ────────────────────────────────────
def _leaf_src(leaf):
    """color/index leaf 를 소스 토큰으로. const=값, var/expr=이름/식 그대로."""
    if "const" in leaf:
        return str(leaf["const"])
    if "var" in leaf:
        return leaf["var"]
    if "expr" in leaf:
        return leaf["expr"]
    raise ValueError(f"bad leaf: {leaf}")


# ── to_source ───────────────────────────────────────────
_LEVEL = {"pixel": ("in_px = pixels_of(input_grid)", "in_px", "P"),
          "object": ("in_objs = objects_of(input_grid)", "in_objs", "O")}


def to_source(ast) -> str:
    """AST → 현행 flat Python 문자열 (없으면 sentinel '{}')."""
    if not ast or not ast.get("body"):
        return "{}"
    body = ast["body"]
    used = {}                                   # level → (src_line, ref_name, var_prefix)
    for s in body:
        tgt = s["args"]["target"]
        used.setdefault(tgt["ref"], _LEVEL[tgt["ref"]])
    # defs: 각 level 의 소스 선언 라인(등장 순), 그다음 스텝별 참조 정의
    defs = [v[0] for v in used.values()]
    steps = ["tfg0 = input_grid"]
    for i, s in enumerate(body):
        tgt = s["args"]["target"]
        _, ref_name, prefix = _LEVEL[tgt["ref"]]
        idx_src = _leaf_src(tgt["index"])
        col_src = _leaf_src(s["args"]["color"])
        defs.append(f"{prefix}{i} = {ref_name}[{idx_src}]")
        steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {prefix}{i}.coord, {col_src})")
    steps.append(f"output_grid = tfg{len(body)}")
    return "\n".join(defs + [""] + steps)
```

> **주의(def 순서):** 현행 `_pixel_residual_program` 은 def 를 `[src_line, P0, P1, ...]` 로 낸다(모든 P 정의가 소스 선언 뒤에 연속). 위 구현은 `defs = [src_lines...] + [P0.., P1..]` 이므로 단일 level 일 때 정확히 그 순서다. 다중 level(object+pixel merge)은 Task 7 에서 별도 처리한다(이 태스크 범위 아님).

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (4 tests)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_program_ast.py
git commit -m "feat(program-ast): AST 스키마 + to_source (현행 문자열 재현)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `execute()` AST 인터프리터

AST 를 입력 grid 에 실행해 출력 grid 를 낸다. 숫자 처리는 현행 `antiunify.execute_solution` 과 **동일**(ix//W, ix%W). (P1)

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Consumes: Task 1 의 `program`/`step`/`ref`/`const`/`var`.
- Produces: `execute(ast: dict, grid_in: list, choice: dict | None = None) -> list`
  - `choice`: solution 실행 시 `{slot_name: fn(grid_in)->int}`. 없으면 concrete pair-program.

- [ ] **Step 1: 실패 테스트 작성** (`tests/test_program_ast.py` 에 클래스 추가)

```python
class TestExecute(unittest.TestCase):
    def test_concrete_pixel_program_recolors_cell(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        # 2x2 grid, index 1 = (0,1)
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[0, 3], [0, 0]])

    def test_two_steps_apply_in_order(self):
        ast = P.program([
            P.step("coloring", target=P.ref("pixel", P.const(0)), color=P.const(5)),
            P.step("coloring", target=P.ref("pixel", P.const(3)), color=P.const(7)),
        ])
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[5, 0], [0, 7]])

    def test_slot_index_uses_choice_fn(self):
        ast = P.program(
            [P.step("coloring", target=P.ref("pixel", P.var("?src0")), color=P.var("?color0"))],
            slots={"?src0": {"kind": "src", "pos": 0}, "?color0": {"kind": "color", "pos": 0}},
        )
        choice = {"?src0": (lambda g: 2), "?color0": (lambda g: 9)}
        out = P.execute(ast, [[0, 0], [0, 0]], choice=choice)
        self.assertEqual(out, [[0, 0], [9, 0]])   # index 2 = (1,0)

    def test_out_of_range_index_skipped(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(99)), color=P.const(3))])
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[0, 0], [0, 0]])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestExecute -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'execute'`

- [ ] **Step 3: 최소 구현** (`program_ast.py` 에 추가)

```python
def _leaf_value(leaf, grid_in, choice):
    """index/color leaf → 정수. const=값, var=choice[name](grid_in), expr 는 미지원(호출측이 var 로 변환)."""
    if "const" in leaf:
        return leaf["const"]
    if "var" in leaf:
        fn = (choice or {}).get(leaf["var"])
        return fn(grid_in) if fn else None
    raise ValueError(f"execute: unresolved leaf {leaf}")


def execute(ast, grid_in, choice=None):
    """AST 를 grid_in 에 실행 → 출력 grid. (숫자 처리 = antiunify.execute_solution 과 동일.)"""
    if not ast or not ast.get("body"):
        return [list(r) for r in grid_in]
    H, W = len(grid_in), len(grid_in[0])
    grid = [list(r) for r in grid_in]
    for s in ast["body"]:
        tgt = s["args"]["target"]
        ix = _leaf_value(tgt["index"], grid_in, choice)
        col = _leaf_value(s["args"]["color"], grid_in, choice)
        if ix is None or col is None:
            continue
        r, c = ix // W, ix % W
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = col
    return grid
```

> **행동보존 근거:** `antiunify.execute_solution`(antiunify.py:199-213)도 `r,cc = ix//W, ix%W` 로 범위 검사 후 `grid[r][cc]=c`. 동일 산술.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (8 tests 누적)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_program_ast.py
git commit -m "feat(program-ast): execute() AST 인터프리터 (execute_solution 산술 동일)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `render_header()` — 표시용 앞단 자동생성

AST 가 실제 쓰는 op·accessor 만 DSL `SPECS` 에서 골라 시그니처 라인 + `input_grid` 를 방출한다. **저장 안 함**, 렌더/복붙용. (P1)

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Consumes: `procedural_memory.dsl.registry.SPECS` (이미 존재: `{name: {name,kind,in,out,effect,body}}`).
- Produces: `render_header(ast: dict, grid_in: list) -> str`

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestHeader(unittest.TestCase):
    def test_header_lists_used_op_and_input_grid(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        h = P.render_header(ast, [[0, 0], [0, 0]])
        self.assertIn("coloring", h)                       # 사용한 op 시그니처
        self.assertIn("pixels_of", h)                      # pixel ref → pixels_of accessor
        self.assertIn("input_grid = [[0, 0], [0, 0]]", h)  # 현 grid 스냅샷

    def test_header_omits_unused_object_accessor(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        h = P.render_header(ast, [[0, 0], [0, 0]])
        self.assertNotIn("objects_of", h)                  # object 미사용 → 생략
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestHeader -v`
Expected: FAIL — no attribute `render_header`

- [ ] **Step 3: 최소 구현** (`program_ast.py` 에 추가)

```python
# level ref → 필요한 accessor DSL 이름
_LEVEL_ACCESSOR = {"pixel": "pixels_of", "object": "objects_of"}


def _sig(name):
    """SPECS 명세 → 한 줄 시그니처 (없으면 이름만)."""
    from procedural_memory.dsl.registry import SPECS
    s = SPECS.get(name)
    if not s:
        return f"# {name}(...)"
    return f"# {name}({', '.join(s['in'])}) -> {s['out']}"


def render_header(ast, grid_in) -> str:
    """AST 가 쓰는 op·accessor 시그니처 + 현 input_grid. 저장 안 함(표시/복붙용)."""
    import json as _json
    ops, accs = [], []
    for s in (ast.get("body") or []):
        if s["call"] not in ops:
            ops.append(s["call"])
        lvl = s["args"]["target"]["ref"]
        acc = _LEVEL_ACCESSOR.get(lvl)
        if acc and acc not in accs:
            accs.append(acc)
    lines = ["# --- DSL (used) ---"]
    lines += [_sig(n) for n in ops + accs]
    lines += ["# --- input (this pair) ---", f"input_grid = {_json.dumps(grid_in)}"]
    return "\n".join(lines)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (10 tests 누적)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_program_ast.py
git commit -m "feat(program-ast): render_header() — SPECS 기반 앞단 자동생성

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `ops_of_ast()` + `antiunify_ast()`

AST 에서 `(index, color)` 튜플 추출 + 두 AST 를 정렬·구조비교해 skeleton AST + slots 를 낸다. `antiunify.py` 의 검증된 `_align`/slot 로직을 재사용한다. (P1)

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Consumes: `arbor.reasoning.antiunify._align` (기존, 유지).
- Produces:
  - `ops_of_ast(ast) -> list[tuple[int, int]]` (concrete AST 만; slot 있으면 값 대신 None)
  - `antiunify_ast(asts: list[dict]) -> tuple[dict | None, dict | None]` — (skeleton_ast, slots). slots 스키마는 현행과 동일: `{name: {"kind": "src"|"color", "pos": int, "values": [per-pair]}}`.

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestAntiunify(unittest.TestCase):
    def test_common_index_common_color_no_slots(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertEqual(slots, {})
        self.assertEqual(P.ops_of_ast(sk), [(5, 3)])

    def test_diff_color_becomes_color_slot(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(8))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?color0", slots)
        self.assertEqual(slots["?color0"]["kind"], "color")
        self.assertEqual(slots["?color0"]["values"], [3, 8])
        # skeleton 의 color 는 var 로 승격
        self.assertEqual(sk["body"][0]["args"]["color"], {"var": "?color0"})

    def test_diff_index_becomes_src_slot(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(9)), color=P.const(3))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?src0", slots)
        self.assertEqual(slots["?src0"]["values"], [1, 9])
        self.assertEqual(sk["body"][0]["args"]["target"]["index"], {"var": "?src0"})

    def test_different_op_count_returns_none(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3)),
                       P.step("coloring", target=P.ref("pixel", P.const(2)), color=P.const(4))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIsNone(sk)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestAntiunify -v`
Expected: FAIL — no attribute `ops_of_ast`

- [ ] **Step 3: 최소 구현** (`program_ast.py` 에 추가)

```python
def ops_of_ast(ast):
    """concrete AST → [(pixel_index, color)]. slot(var) leaf 는 그 자리 None."""
    ops = []
    for s in (ast.get("body") or []):
        idx_leaf = s["args"]["target"]["index"]
        col_leaf = s["args"]["color"]
        idx = idx_leaf.get("const") if "const" in idx_leaf else None
        col = col_leaf.get("const") if "const" in col_leaf else None
        ops.append((idx, col))
    return ops


def antiunify_ast(asts):
    """정렬된 per-pair AST 들 → (skeleton_ast, slots). 위치별 COMM=상수, DIFF=var 승격.
    _align(COMM 최대화 순열) 재사용. op 수 다르면 (None, None)."""
    from arbor.reasoning.antiunify import _align
    progs = [ops_of_ast(a) for a in asts if a and a.get("body")]
    progs = [p for p in progs if p and all(o[0] is not None for o in p)]
    if len(progs) < 2:
        return None, None
    n = len(progs[0])
    if any(len(p) != n for p in progs):
        return None, None
    ref = progs[0]
    aligned = [ref] + [_align(ref, p) for p in progs[1:]]
    body, slots = [], {}
    for i in range(n):
        idxs = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_idx = idxs[0] if len(set(idxs)) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        idx_leaf = const(sk_idx) if sk_idx is not None else var(f"?src{i}")
        col_leaf = const(sk_col) if sk_col is not None else var(f"?color{i}")
        if sk_idx is None:
            slots[f"?src{i}"] = {"kind": "src", "pos": i, "values": idxs}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        body.append(step("coloring", target=ref_leaf(idx_leaf), color=col_leaf))
    return program(body, slots=slots), slots
```

> `ref_leaf` 헬퍼가 필요하다 — pixel ref 를 만든다. `program_ast.py` 상단 생성자 근처에 추가:
> ```python
> def ref_leaf(index_leaf, level="pixel"):
>     return ref(level, index_leaf)
> ```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (14 tests 누적)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_program_ast.py
git commit -m "feat(program-ast): ops_of_ast + antiunify_ast (_align 재사용)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `as_source()` 정규화 + 전 읽기 지점 감싸기

program/solution/program-code 를 읽는 모든 곳을 `as_source()` 로 감싼다 — legacy 문자열이든 AST-json 이든 flat 문자열을 돌려주므로, 이후 emit flip 이 소비 로직을 안 깨게 하는 shim. **행동 불변** (아직 emit 은 문자열이라 as_source 는 항등). (P2)

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (`as_source` 추가)
- Modify: `procedural_memory/operators/generalize.py:24`, `compose.py:15-19`, `verify.py:25`, `hypothesize.py:48`, `debugger/reports/program_report.py:70`
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Produces: `as_source(wm_value: str | None) -> str` — AST-json dict(`"body"` 보유)면 `to_source`, 아니면 원문. `None`/`"{}"`→`"{}"`.

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestAsSource(unittest.TestCase):
    def test_legacy_string_passthrough(self):
        s = "in_px = pixels_of(input_grid)\nP0 = in_px[1]\n\ntfg0 = input_grid\noutput_grid = tfg0"
        self.assertEqual(P.as_source(s), s)

    def test_ast_json_rendered_to_source(self):
        import json
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        self.assertEqual(P.as_source(json.dumps(ast)), P.to_source(ast))

    def test_empty_sentinels(self):
        self.assertEqual(P.as_source(None), "{}")
        self.assertEqual(P.as_source("{}"), "{}")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestAsSource -v`
Expected: FAIL — no attribute `as_source`

- [ ] **Step 3: `as_source` 구현** (`program_ast.py` 에 추가)

```python
def as_source(wm_value):
    """WM 저장값(legacy flat 문자열 | AST-json | None | '{}') → flat 문자열('{}'=미합성)."""
    if wm_value in (None, "{}", ""):
        return "{}"
    if isinstance(wm_value, str) and wm_value.lstrip().startswith("{"):
        try:
            obj = json.loads(wm_value)
        except (ValueError, TypeError):
            return wm_value
        if isinstance(obj, dict) and ("body" in obj or "input" in obj):
            return to_source(obj)
        return wm_value          # '{}' 등 program 아닌 dict
    return wm_value
```

- [ ] **Step 4: 읽기 지점 감싸기.** 각 파일에서 program 값을 소비하기 직전 `as_source` 적용.

`procedural_memory/operators/generalize.py` — 상단 import 에 추가하고 line 24 근처 수집부:
```python
# import 추가
from arbor.reasoning.program_ast import as_source
# 기존:  code = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
# 변경:
code = as_source(next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None))
if code == "{}":
    code = None
```

`procedural_memory/operators/verify.py` line 25:
```python
# import 추가
from arbor.reasoning.program_ast import as_source
# 기존:  code = next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), "output_grid = input_grid")
# 변경:
code = as_source(next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), None))
if code == "{}":
    code = "output_grid = input_grid"
```

`procedural_memory/operators/hypothesize.py` line 48:
```python
# import 추가
from arbor.reasoning.program_ast import as_source
# 기존:  base_prog = next((v for (i, a, v) in ag.wm if i == sup and a == "program-code"), None) if sup else None
# 변경:
_bp = next((v for (i, a, v) in ag.wm if i == sup and a == "program-code"), None) if sup else None
base_prog = as_source(_bp) if _bp else None
if base_prog == "{}":
    base_prog = None
```

`procedural_memory/operators/compose.py` — `sol = ag.kg.get("solution")` 는 dict(내부표현)라 as_source 불필요. 이 태스크에선 변경 없음(Task 8 에서 다룸).

`debugger/reports/program_report.py` line 70:
```python
# import 추가 (파일 상단)
from arbor.reasoning.program_ast import as_source
# 기존:  prog = next((v for (i, a, v) in tr.ag.wm if a == "program" and v != "{}"), None)
# 변경:
_p = next((v for (i, a, v) in tr.ag.wm if a == "program" and v != "{}"), None)
prog = as_source(_p) if _p else None
```

- [ ] **Step 5: 단위 테스트 + 골든 게이트**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (17 tests 누적)

Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9 step 일치` (as_source 가 legacy 문자열에 항등이므로 행동 불변)

- [ ] **Step 6: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_program_ast.py \
        procedural_memory/operators/generalize.py procedural_memory/operators/verify.py \
        procedural_memory/operators/hypothesize.py debugger/reports/program_report.py
git commit -m "refactor(program-ast): as_source() 로 전 program 읽기 지점 정규화 (행동 불변)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: coloring operator emit → AST

`coloring.py::_op_coloring` 이 `program-code` 를 문자열 대신 AST-json 으로 저장한다. `base-program` merge(object+pixel)도 AST body 이어붙이기로. 소비처(verify/hypothesize)는 Task 5 의 `as_source` 로 이미 정규화됨 → 행동 불변. (P2)

**Files:**
- Modify: `procedural_memory/operators/coloring.py`
- Modify: `arbor/reasoning/program_ast.py` (다중 level `to_source` + base merge 지원)
- Test: `tests/test_program_ast.py`

**Interfaces:**
- Consumes: Task 1-2 생성자·`to_source`.
- Produces: `to_source` 가 object+pixel 혼합(base merge) AST 를 현행 문자열과 동일하게 렌더.

- [ ] **Step 1: 실패 테스트 작성** (다중 level merge 의 현행 문자열 재현)

```python
class TestMergeSource(unittest.TestCase):
    def test_object_then_pixel_merge_matches_legacy(self):
        # object 가설(O0) 뒤에 pixel 잔여(P0) 를 이어붙인 base-merge 형태
        ast = P.program([
            P.step("coloring", target=P.ref("object", P.const(2)), color=P.const(4)),
            P.step("coloring", target=P.ref("pixel", P.const(7)), color=P.const(5)),
        ])
        src = P.to_source(ast)
        # 두 소스 선언이 모두 등장하고, tfg 체인이 연속(0->1->2)이어야
        self.assertIn("in_objs = objects_of(input_grid)", src)
        self.assertIn("in_px = pixels_of(input_grid)", src)
        self.assertIn("O0 = in_objs[2]", src)
        self.assertIn("P1 = in_px[7]", src)
        self.assertIn("tfg1 = apply_DSL(tfg0, coloring, O0.coord, 4)", src)
        self.assertIn("tfg2 = apply_DSL(tfg1, coloring, P1.coord, 5)", src)
        self.assertTrue(src.rstrip().endswith("output_grid = tfg2"))
```

> **주의:** 현행 merge 는 변수 접두사를 step 종류(P/O)로, 인덱스는 step 순번 `i` 로 매긴다(coloring.py:47 `{var}{k}`, k=step 순번). 위 기대는 그 규칙(O0=step0, P1=step1) 을 따른다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestMergeSource -v`
Expected: FAIL — 현재 `to_source` 는 defs 를 `[모든 src_line...] + [스텝 defs...]` 로 내지만 step 순번 접두사는 이미 맞음. 실패 지점 확인 후 다음 스텝.

- [ ] **Step 3: `to_source` 다중 level 확정.** Task 1 의 `to_source` 는 이미 step 순번 `i` 로 `{prefix}{i}` 를 낸다. 다중 level 시 def 순서만 "각 level src_line(등장순) → 스텝 defs" 이면 된다. 현 구현이 그러하므로 통과할 것. 실패하면 아래로 교체:

```python
def to_source(ast) -> str:
    if not ast or not ast.get("body"):
        return "{}"
    body = ast["body"]
    src_lines, seen = [], set()
    for s in body:
        lvl = s["args"]["target"]["ref"]
        if lvl not in seen:
            seen.add(lvl); src_lines.append(_LEVEL[lvl][0])
    defs, steps = list(src_lines), ["tfg0 = input_grid"]
    for i, s in enumerate(body):
        tgt = s["args"]["target"]
        _, ref_name, prefix = _LEVEL[tgt["ref"]]
        defs.append(f"{prefix}{i} = {ref_name}[{_leaf_src(tgt['index'])}]")
        steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {prefix}{i}.coord, {_leaf_src(s['args']['color'])})")
    steps.append(f"output_grid = tfg{len(body)}")
    return "\n".join(defs + [""] + steps)
```

- [ ] **Step 4: 단위 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v`
Expected: PASS (18 tests 누적)

- [ ] **Step 5: `_op_coloring` 이 AST 를 만들어 저장.** `coloring.py:30-51` 의 문자열 조립을 AST 조립으로 교체. 소스 문자열 저장 대신 `json.dumps(ast)`:

```python
# coloring.py 상단 import
import json
from arbor.reasoning import program_ast as PA
from arbor.reasoning.program_ast import as_source

# ... (grid 시뮬은 그대로 두고, program-code 조립부만 교체) ...
# 기존 defs/steps 문자열 로직 (line 30-51) 대신:
px = bool(order) and ag.wm.contains(order[0], "px", "yes")
base_v = next((v for (i, a, v) in ag.wm if i == sid and a == "base-program"), None) if px else None
base_ast = None
if base_v:
    bv = as_source(base_v)                      # 항상 flat; base 가 이미 AST 면 to_source
    # base 를 AST 로 되읽기: base_v 가 AST-json 이면 그대로, 아니면 legacy → 파싱 불가 시 steps 재구성
    try:
        base_ast = json.loads(base_v) if base_v.lstrip().startswith("{") and "body" in json.loads(base_v) else None
    except (ValueError, TypeError):
        base_ast = None
level = "pixel" if px else "object"
body = list(base_ast["body"]) if base_ast else []
for xid in order:
    g0c = [tuple(c) for c in (_wx(xid, "g0cells") or ())]; g1col = int(_wx(xid, "g1color") or 0)
    g0i = int(_wx(xid, "g0idx") or 0)
    for (r, c) in g0c:
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            grid = coloring(grid, (r, c), g1col)
    ag.wm.add(xid, "applied", "yes")
    body.append(PA.step("coloring", target=PA.ref(level, PA.const(g0i)), color=PA.const(g1col)))
ast = PA.program(body)
ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
ag.wm.add(sid, "program-code", json.dumps(ast))
ag.wm.add(sid, "colored-all", "yes")
```

> **주의(행동보존 미묘점):** 현행 merge 는 base 의 `tfg` 번호를 이어가고 P 인덱스를 `base_n+k` 로 매긴다. AST body 는 단순 이어붙이기라 `to_source` 가 step 순번으로 다시 번호를 매기므로 **최종 문자열이 현행과 동일**해진다(verify 는 as_source 로 문자열을 받음). 단, base 가 legacy 문자열이면 `base_ast=None` → body 가 잔여만 담겨 object 파트가 유실될 수 있다. 이 태스크는 Task 6 이므로 base(program-code)도 이미 AST(같은 operator 산물) → 항상 `base_ast` 확보됨. 확인: 골든 게이트가 이를 검출한다.

- [ ] **Step 6: 골든 게이트**

Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9 step 일치`
(MISMATCH 시: base merge 인덱싱 차이 — Step 5 주의 참고. `_op_coloring` 산출 AST 의 `to_source` 를 legacy `_op_coloring` 문자열과 직접 비교하는 임시 디버그로 좁힌다.)

- [ ] **Step 7: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add procedural_memory/operators/coloring.py arbor/reasoning/program_ast.py tests/test_program_ast.py
git commit -m "refactor(program-ast): coloring operator 가 program-code 를 AST-json 으로 방출

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 나머지 emit → AST (`program.py`·`synthesize.py`·`render_skeleton`)

`_pixel_residual_program`·`_global_recolor_program`·synthesize GRID-closure·`render_skeleton` 이 AST-json 을 방출. 소비처는 `as_source`(Task 5) 로 정규화되어 있으므로 행동 불변. (P2)

**Files:**
- Modify: `arbor/reasoning/program.py`
- Modify: `procedural_memory/operators/synthesize.py`
- Modify: `arbor/reasoning/antiunify.py` (`render_skeleton` → AST 반환 + `to_source` 위임)
- Modify: `procedural_memory/operators/generalize.py`, `compose.py` (render_skeleton 산출 저장 시 `json.dumps`)

**Interfaces:**
- `_pixel_residual_program(g0, g1) -> str(json.dumps(ast)) | None`
- `render_skeleton(skeleton_ast, slots) -> str` — 지금은 문자열 반환 계약이라, **AST-json 문자열**을 반환하도록 바꾸고 호출측이 그대로 WM 에 저장.

- [ ] **Step 1: 실패 테스트 작성** (`_pixel_residual_program` 이 AST-json 을 내고, as_source 로 legacy 형태 재현)

```python
class TestEmitAst(unittest.TestCase):
    def test_pixel_residual_emits_ast_json_that_rendersback(self):
        from arbor.reasoning.program import _pixel_residual_program
        g0 = [[0, 0], [0, 0]]
        g1 = [[0, 3], [0, 0]]                       # index 1 → color 3
        out = _pixel_residual_program(g0, g1)
        import json
        ast = json.loads(out)                       # 이제 AST-json 이어야
        self.assertEqual(P.ops_of_ast(ast), [(1, 3)])
        self.assertIn("apply_DSL(tfg0, coloring, P0.coord, 3)", P.as_source(out))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestEmitAst -v`
Expected: FAIL — `json.loads` 가 현행 flat 문자열에서 `JSONDecodeError`

- [ ] **Step 3: `_pixel_residual_program` 교체** (`program.py:236-250`)

```python
def _pixel_residual_program(g0, g1):
    """pixel 잔차(G0≠G1 셀만 재채색) AST. 같은 크기 pair 만(크기변화 → None)."""
    if len(g0) != len(g1) or len(g0[0]) != len(g1[0]):
        return None
    import json
    from arbor.reasoning import program_ast as PA
    H, W = len(g0), len(g0[0])
    changed = [(r, c) for r in range(H) for c in range(W) if g0[r][c] != g1[r][c]]
    body = [PA.step("coloring", target=PA.ref("pixel", PA.const(r * W + c)), color=PA.const(g1[r][c]))
            for (r, c) in changed]
    return json.dumps(PA.program(body))
```

- [ ] **Step 4: `_global_recolor_program` 교체** (`program.py:147-162`)

```python
def _global_recolor_program(g0grid, cmap):
    """전역 색맵을 coloring 만으로 표현한 AST (셀을 target 색별로 묶어 각 셀 재채색)."""
    import json
    from arbor.reasoning import program_ast as PA
    H, W = len(g0grid), len(g0grid[0])
    body = []
    bytarget = {}
    for r in range(H):
        for c in range(W):
            s = g0grid[r][c]; t = cmap.get(s, s)
            if t != s:
                bytarget.setdefault(t, []).append((r, c))
    for t in sorted(bytarget):
        for (r, c) in bytarget[t]:
            body.append(PA.step("coloring", target=PA.ref("pixel", PA.const(r * W + c)), color=PA.const(t)))
    return json.dumps(PA.program(body))
```

> **행동보존 주의:** 현행 `_global_recolor_program` 은 셀묶음을 한 step(`apply_DSL(..., [[r,c],...], t)`)으로 냈다. 위는 셀 단위 step 으로 편다. 이는 `to_source`/`execute` 산출 grid 는 동일하나 **program 문자열 형태가 다르다**. 이 함수의 소비처(synthesize→verify→PAIR.program→generalize)가 셀묶음 문자열을 정규식 파싱하는지 확인 필요: `parse_program` 은 `in_px[digit]` 만 파싱하므로 셀묶음 형태(`[[r,c],...]`)는 원래도 파싱 불가였다 → generalize 에서 이 pair 는 skip 됐다. 셀단위로 펴면 파싱 가능해져 **동작이 바뀔 수 있다.** → 골든 게이트로 검출. MISMATCH 면 셀묶음을 유지하는 별도 step 형(`target=ref("pixels", const([[r,c]...]))`)이 필요 — 그 경우 **멈추고 사용자와 의논**(하네스 §5; 스키마 확장 결정).

- [ ] **Step 5: `render_skeleton` 을 AST 기반으로** (`antiunify.py:216-232`)

```python
def render_skeleton(skeleton, slots) -> str:
    """skeleton(AST) + slots → TASK.solution 저장값(AST-json). (계약: 문자열 반환 유지, 내용은 json.)"""
    import json
    if not skeleton:
        return "{}"
    from arbor.reasoning.program_ast import program
    sk = dict(skeleton); sk["slots"] = slots
    return json.dumps(sk)
```

> `antiunify()`(구 문자열 기반)는 Task 8 에서 `antiunify_ast` 로 대체될 때까지 유지되나, 이 태스크에서 `render_skeleton` 의 입력 `skeleton` 은 아직 구 `{"ops":[...]}` 형이다. **호환 처리:** 구 skeleton(`{"ops":[(idx,col)]}`) 을 AST 로 변환 후 저장:
> ```python
> def render_skeleton(skeleton, slots) -> str:
>     import json
>     if not skeleton:
>         return "{}"
>     from arbor.reasoning.program_ast import program, step, ref, const, var
>     src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
>     col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
>     body = []
>     for i, (idx, col) in enumerate(skeleton["ops"]):
>         idx_leaf = const(idx) if idx is not None else var(src_at[i])
>         col_leaf = const(col) if col is not None else var(col_at[i])
>         body.append(step("coloring", target=ref("pixel", idx_leaf), color=col_leaf))
>     ast = program(body); ast["slots"] = slots
>     return json.dumps(ast)
> ```

- [ ] **Step 6: synthesize GRID-closure → AST** (`synthesize.py:60-65`). 상수/항등 program 도 AST 로:

```python
# synthesize.py — program 저장부
import json
from arbor.reasoning import program_ast as PA
# 전역 재채색: _global_recolor_program 은 이미 AST-json 반환(Task 7 Step 4)
# 항등(output=input): 빈 body AST
# 기존:  ag.wm.add(ppid, "program", "output_grid = input_grid")  또는 상수출력 문자열
# 변경(항등):
ag.wm.add(ppid, "program", json.dumps(PA.program([])))     # 빈 body = 항등(execute 가 input 복사)
```

> 상수출력(출력이 입력과 무관한 고정 grid)은 현행이 문자열 주석이었다. 이 경우 program 표현이 coloring 조합으로 불가 → 현행처럼 **빈/미합성(null)** 로 두고 GRID-verdict 로만 노출(스펙 §2 비목표: 새 atom 금지). 해당 분기는 `ag.wm.add(ppid, "program", None)` 로 두거나 기존 문자열 유지 후 as_source 통과. 골든이 이 pair 의 step 에 영향 없음 확인.

- [ ] **Step 7: 골든 게이트**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v` → PASS
Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9 step 일치`
(Step 4 주의의 색맵 셀단위 전개가 MISMATCH 를 내면 그 지점에서 멈추고 사용자와 의논.)

- [ ] **Step 8: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program.py arbor/reasoning/antiunify.py \
        procedural_memory/operators/synthesize.py tests/test_program_ast.py
git commit -m "refactor(program-ast): 나머지 emit(program.py/synthesize/render_skeleton) → AST-json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: anti-unify 내부를 AST 로 (정규식 은퇴)

`generalize` 가 PAIR.program(이제 AST-json)을 json.loads 해 `antiunify_ast` 로 넘기고, `compose` 가 `execute` 를 쓴다. 정규식 `parse_program`/`_STEP`/`_DEF`·구 `antiunify()`·`execute_solution` 을 은퇴(또는 얇은 위임). (P3)

**Files:**
- Modify: `procedural_memory/operators/generalize.py`
- Modify: `procedural_memory/operators/compose.py`
- Modify: `arbor/reasoning/antiunify.py` (`execute_solution`→`execute` 위임; `antiunify`/`parse_program` 은퇴)

**Interfaces:**
- Consumes: `program_ast.antiunify_ast`, `program_ast.execute`, `program_ast.as_source`.
- `generalize` 가 `ag.kg["solution"]` 에 `{"skeleton": <AST>, "slots": ..., "programs": <AST 리스트>, "tid": ...}` 저장 (skeleton 이 이제 AST).

- [ ] **Step 1: 실패 테스트 작성** (generalize 경로의 핵심: 두 AST → solution AST 실행)

```python
class TestSolutionExecute(unittest.TestCase):
    def test_antiunify_then_execute_on_new_input(self):
        # 두 pair: 같은 위치(idx1) 다른 색 → color slot; execute 는 choice 로 색 주입
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(8))])
        sk, slots = P.antiunify_ast([a, b])
        choice = {"?color0": (lambda g: 5)}
        out = P.execute(sk, [[0, 0], [0, 0]], choice=choice)
        self.assertEqual(out, [[0, 5], [0, 0]])     # idx1=(0,1) → 5
```

- [ ] **Step 2: 테스트 실패 확인 → 통과** (antiunify_ast/execute 는 Task 2·4 에 이미 존재)

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast.TestSolutionExecute -v`
Expected: PASS (이미 구현됨 — 이 테스트는 통합 계약 고정용)

- [ ] **Step 3: `generalize` 를 AST 경로로.** `generalize.py` 전체를 아래로 교체 (import 줄 10 + 함수 본체 13-42):

```python
# -*- coding: utf-8 -*-
"""ARBOR operator body: generalize (anti-unification, procedural LTM leaf).

per-pair `PAIR.program`(AST) 들을 anti-unify 해 `TASK.solution`(골격 + 변수 slot)을 물질화한다.
COMM=상수 고정, DIFF=변수 slot(per-pair 값=근거). resolve(G0 유래 식)는 다음 operator. (§0.5·§2-2)
"""
from __future__ import annotations

import json
from arbor.reasoning.program_ast import antiunify_ast, as_source


def _op_generalize(ag):
    sid = ag.stack[-1].id
    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "generalized", "failed")
        return
    tid = root.node_id
    # 존재하는 example-pair program(AST-json)들을 순서대로 수집
    asts = []
    for p in getattr(root, "example_pairs", []) or []:
        ppid = f"{p.node_id}.property"
        v = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if v in (None, "{}"):
            continue
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
    sk, slots = antiunify_ast(asts)
    if sk is None:                                        # 구조 불일치/부족 → 정직히 실패
        ag.wm.add(sid, "generalized", "failed")
        return
    sk_with = dict(sk); sk_with["slots"] = slots
    solution = json.dumps(sk_with)
    tpid = f"{tid}.property"
    old = next((v for (i, a, v) in ag.wm if i == tpid and a == "solution"), None)
    if old in (None, "{}") and old is not None:
        ag.wm.remove(tpid, "solution", old)
    ag.wm.add(tpid, "solution", solution)                 # TASK.solution 물질화(§2-5)
    for name, s in slots.items():                         # slot 근거 = DIFF per-pair 값
        ag.wm.add(tpid, "slot", f"{name}[{s['kind']}]=DIFF{s['values']}")
    ag.kg["solution"] = {"skeleton": sk, "slots": slots, "programs": asts, "tid": tid}
    ag.kg["generalize"] = {"solution": as_source(solution),   # 대시보드용은 flat 문자열
                           "slots": {n: s["values"] for n, s in slots.items()}}
    ag.wm.add(sid, "generalized", "yes")
```

> `antiunify_ast`(Task 4)는 `(skeleton_ast, slots)` 를 낸다. skeleton 은 `program()` 형(이미 `slots` 키 없음) → 여기서 `sk_with["slots"]=slots` 로 병합해 저장. `ag.kg["solution"]["skeleton"]` 은 slots 없는 순수 AST(compose 가 slots 를 따로 받음).

- [ ] **Step 4: `compose` 를 `execute` 로.** `compose.py` 의 import 줄 10 과 line 29·38-40 을 교체:

```python
# 기존 line 10:
#   from arbor.reasoning.antiunify import solution_candidates, execute_solution, render_skeleton
# 변경:
import json
from arbor.reasoning.antiunify import solution_candidates        # 유지(version space)
from arbor.reasoning.program_ast import execute

# 기존 line 29:
#   grid = execute_solution(sol["skeleton"], sol["slots"], choice, ag.task["test"][0]["input"])
# 변경 (skeleton 은 이제 AST):
grid = execute(sol["skeleton"], ag.task["test"][0]["input"], choice=choice)

# 기존 line 38-40:
#   if ag.wm.contains(ppid, "program", "{}"):
#       ag.wm.remove(ppid, "program", "{}")
#   ag.wm.add(ppid, "program", render_skeleton(sol["skeleton"], sol["slots"]))
# 변경 (test pair program = resolved solution AST):
old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
if old in (None, "{}") and old is not None:
    ag.wm.remove(ppid, "program", old)
test_ast = dict(sol["skeleton"]); test_ast["slots"] = sol["slots"]
ag.wm.add(ppid, "program", json.dumps(test_ast))
```

> `solution_candidates`(antiunify.py:180) 와 `resolve_slot`(antiunify.py:133) 은 `sol["slots"]`·`sol["resolved"]` 만 쓰므로 **그대로 재사용**. skeleton 이 AST 로 바뀌어도 무관. `execute_solution` 은 `execute` 로 대체 — antiunify.py 에 위임 shim 만 남긴다:
> ```python
> def execute_solution(skeleton, slots, choice, grid_in):   # DEPRECATED 위임
>     from arbor.reasoning.program_ast import execute
>     return execute(skeleton, grid_in, choice=choice)      # skeleton=AST
> ```

- [ ] **Step 5: 정규식 은퇴.** `antiunify.py` 의 `parse_program`·`_STEP`·`_DEF`·구 `antiunify()` 를 삭제하거나, 남겨둘 경우 상단에 `# DEPRECATED: AST 경로(program_ast.antiunify_ast) 로 대체됨` 주석. `render_skeleton` 은 Task 7 에서 이미 AST-json 방출. `_align`·`resolve_slot`·`solution_candidates`·`_axis_cands`·`_coord_index_fn` 등 resolve 계열은 **유지**.

- [ ] **Step 6: 골든 게이트**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_program_ast -v` → PASS
Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9 step 일치`

- [ ] **Step 7: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add procedural_memory/operators/generalize.py procedural_memory/operators/compose.py \
        arbor/reasoning/antiunify.py tests/test_program_ast.py
git commit -m "refactor(program-ast): anti-unify/compose 를 AST 경로로 (정규식 파싱 은퇴)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: sentinel `"{}"` → `null` 통일

빈 program 슬롯을 `"{}"` 문자열에서 `null` 로 통일한다. `as_source` 는 이미 둘 다 처리하므로 안전. (P4 마무리)

**Files:**
- Modify: `arbor/perception/nav.py:141` (슬롯 생성)
- Modify: program/solution sentinel 검사 지점(`generalize`·`verify`·`compose`·`program.py::_materialize_pair_programs`)

**Interfaces:** 없음(내부 sentinel 통일).

- [ ] **Step 1: `nav.py:141` 슬롯 생성 변경**

```python
# 기존:  ag.wm.add(pid, "program", "{}")
# 변경:
ag.wm.add(pid, "program", None)
```

동일하게 solution 슬롯 생성 지점(`task` level 초기화)도 `None` 으로.

- [ ] **Step 2: sentinel 검사 지점 갱신.** `"{}"` 비교를 `in (None, "{}")` 로(이행 호환):

```python
# program.py::_materialize_pair_programs (line 226,231)
# 기존:  if cur not in (None, "{}"):
# 유지 (이미 둘 다 처리)  — 단 wm.contains(ppid,"program","{}") → None 도 remove 하도록:
old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
if old in (None, "{}"):
    if old is not None:
        ag.wm.remove(ppid, "program", old)
    ag.wm.add(ppid, "program", code)     # code 는 이제 _pixel_residual_program 의 AST-json
```

`generalize.py`·`verify.py`·`compose.py` 의 `wm.contains(tpid, "solution", "{}")` / `wm.contains(ppid, "program", "{}")` 도 실제 저장된 sentinel(None) 을 remove 하도록 값 조회 후 remove 패턴으로.

- [ ] **Step 3: 골든 게이트**

Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9 step 일치`

- [ ] **Step 4: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/perception/nav.py arbor/reasoning/program.py \
        procedural_memory/operators/generalize.py procedural_memory/operators/verify.py \
        procedural_memory/operators/compose.py
git commit -m "refactor(program-ast): 빈 program sentinel '{}' → null 통일

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: anti-unify 대시보드 뷰 업그레이드

`easy_antiunify_viz.py` 를 `easy_concepts` 재계산 대신 **실제 저장 AST** 를 읽어 렌더하도록 바꾼다. 3열 레이아웃 유지, ②/③의 COMM/DIFF·slot 을 실제 `antiunify_ast` 결과로, 각 뷰 상단에 `render_header` 자동 앞단 표시. (P5)

**Files:**
- Modify: `debugger/reports/easy_antiunify_viz.py`
- (참고) `debugger/build.py:162-164` 의 companion 빌드 훅은 그대로.

**Interfaces:**
- Consumes: 솔버 실행으로 WM 에 남은 PAIR.program(AST-json), `program_ast.{antiunify_ast, execute, render_header, as_source}`, `arbor.engine.trace._Tracer`.

- [ ] **Step 1: 실 데이터 취득 경로 추가.** `program_report.py::_run_programs` 패턴을 재사용해, 각 easy 태스크의 example PAIR program(AST-json)들을 `_Tracer` 로 뽑는 헬퍼 작성:

```python
# easy_antiunify_viz.py 상단
import json
from arbor.reasoning import program_ast as PA
from arbor.engine.trace import _Tracer
from arbor.agent.focus import setup_focus_agent

def _pair_asts(tid, task):
    """솔버를 돌려 example PAIR.program(AST) 리스트 수집. (없으면 [].)"""
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    tr.run(max_cycles=6000)
    out = []
    for (i, a, v) in tr.ag.wm:
        if a == "program" and v not in (None, "{}"):
            try:
                ast = json.loads(v)
            except (ValueError, TypeError):
                continue
            if ast and ast.get("body"):
                out.append(ast)
    return out
```

- [ ] **Step 2: `task_section` 을 실제 AST 로.** `samples()`/`version_space()` 재계산 제거 → `_pair_asts` 로 얻은 두 AST 로 ① 재료(각 AST 를 `to_source`/box-flow 로), ② `antiunify_ast([a,b])` 의 slots 로 COMM/DIFF outline, ③ skeleton AST + slots 를 렌더. 각 열 상단에 `render_header(ast, g0)`.

> 렌더 헬퍼(`flow`/`opb`/`tgt`/`colr`/`pgen`/`dvar`)는 유지하되 입력을 AST step 에서 뽑도록 배선. coloring 전용 하드코딩(`concrete`, `_rank`) 제거.

- [ ] **Step 3: 크기변화/미합성 태스크 처리.** program 이 없는(크기변화) 태스크는 현행처럼 "격자 크기 변화" 배지. `_pair_asts` 가 `[]` 면 그 섹션.

- [ ] **Step 4: 빌드 실행 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m debugger.reports.easy_antiunify_viz`
Expected: `wrote .../traces/easy_antiunify_report.html (NN KB)` — 크래시 없음.

- [ ] **Step 5: 렌더 내용 확인.** 생성된 HTML 을 열어 (a) 저장 AST 기반 program 표시, (b) COMM/DIFF outline 이 실제 slots 반영, (c) 상단 자동 header(사용 accessor + input_grid) 존재 확인.

Run: `cd /Users/sir_k/Desktop/PySOAR && python -c "s=open('debugger/traces/easy_antiunify_report.html').read(); print('header' , 'input_grid =' in s); print('coloring', 'coloring' in s)"`
Expected: 둘 다 `True`

- [ ] **Step 6: 전체 대시보드 빌드 회귀 확인** (companion 훅 포함)

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m debugger.build 2>&1 | tail -5`
Expected: `wrote .../focus_dashboard.html` + `wrote .../easy_antiunify_report.html` 정상.

- [ ] **Step 7: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add debugger/reports/easy_antiunify_viz.py
git commit -m "feat(dashboard): anti-unify 뷰를 실제 저장 AST + compare 결과로 렌더

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 최종 검증 (Acceptance)

- [ ] `PYTHONPATH=. python3 tests/verify_refactor.py` → `PASS: 9/9 step 일치`
- [ ] `python -m unittest tests.test_program_ast -v` → 전부 PASS
- [ ] WM 의 PAIR.program / TASK.solution 이 AST-json (빈 슬롯 = null) 로 존재 — `python -m debugger.build` 후 `focus_dashboard.html` WM leaf 가 `{"input":...,"body":[...]}` 형태로 보임(truncate 되어도 `{"input` 접두 확인).
- [ ] `easy_antiunify_report.html` 이 실제 저장 AST + 실제 compare 결과로 렌더 (재계산 코드 `easy_concepts` 의존 제거 확인: `grep -c easy_concepts debugger/reports/easy_antiunify_viz.py` → 0).
- [ ] `to_source(json.loads(<PAIR.program>))` 로 복붙 실행 가능한 Python 재현.

## 리스크 노트 (실행 중 이 지점에서 멈추고 사용자와 의논)

- **Task 7 Step 4 (전역 색맵 셀단위 전개):** 현행 셀묶음 문자열이 원래 정규식 파싱 불가라 generalize 에서 skip 됐는데, 셀단위로 펴면 파싱 가능해져 anti-unify 대상에 들어올 수 있다 → step 수 변동 가능. MISMATCH 나면 **멈추고 의논**(스키마 확장 여부, 하네스 §5).
- **Task 6 base merge 인덱싱:** base 가 AST 확보 안 되면 object 파트 유실. 골든이 검출. 
- **compare 재사용 결정:** 이 계획은 스펙 §5 의 "얇은 program 전용 구조 compare"(=`ops_of_ast`+`_align`) 를 택했다. ARCKG `comparison.compare` 직접 사용은 채택하지 않음(재귀 계약 불확실·행동보존 위험). 스펙과 일치.
