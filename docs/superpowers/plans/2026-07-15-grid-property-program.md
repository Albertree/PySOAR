# G1 3-property program (Phase 1) + program 뷰어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** grid-level 에서 결론나는 태스크(easy a/b)가 `set_grid_size/color/contents` 3-property program + task.solution 을 내고, easy a–h 의 program 을 focus_dashboard 연결 페이지에서 확인할 수 있게 한다.

**Architecture:** `arbor/reasoning/program_ast.py` 에 3-property program 계열(새 step op `set_grid_size/color/contents`, 새 leaf `keep`/`delta`)을 추가하고, `_grid_decide` 결과를 3-property AST 로 만드는 순수 빌더를 둔다. `synthesize` 가 grid-결정 태스크에 그 program 을 per-pair 물질화하고(추가적), 그다음 파이프라인(generalize→apply_solution)으로 라우팅한다(재기준화, 체크포인트). 마지막에 `②` 뷰어로 easy a–h program 을 렌더.

**Tech Stack:** Python 3 표준 라이브러리, `unittest`, SOAR 커널(`soar/`), 기존 program-ast 인프라.

## Global Constraints

- **하네스 재독**: 이 계획의 모든 솔버 변경 직전 `ARBOR_HARNESS.md` 를 다시 읽는다(CLAUDE.md 의무). 특히 §1-1(새 primitive atom 금지 — set_grid* 는 승인된 **고차 DSL = make_grid+coloring 조합**), §1-3(값은 탐색에서, 손계산 금지), §1-5(program 은 실행·train 검증), §2-5(대시보드 반영).
- **transformation 원자 동결**: `make_grid`·`coloring` 2개만. `set_grid_size/color/contents` 는 그 *조합*(고차 DSL), 새 원자 아님.
- **golden 재기준화(이 Phase 의 성격)**: Task 7 에서 grid-결정 태스크의 solve 흐름이 바뀌므로 `tests/golden_steps.json` 을 **새 행동으로 재캡처**한다. 그 전(Task 1–6)까지는 **기존 골든 9/9 유지**가 게이트다. Task 7 이후 게이트 = 재캡처된 골든 + made000b + a/b 정답.
- **a/b 정답 불변**: 무슨 변경을 하든 easy000a/b 는 최종적으로 **✓풀림(정답)** 이어야 한다. survey 17 렌더 무크래시.
- **행동 격리**: grid-결정이 아닌 태스크(c–h·made·AGI)의 step 수는 Task 1–6 에서 **불변**이어야 한다(경로 무변). 바뀌면 조사.
- 단위 테스트: `python -m unittest tests.test_grid_program -v` (신규) + `tests.test_program_ast` (회귀). 골든: `PYTHONPATH=. python3 tests/verify_refactor.py`. made000b/survey 체크는 각 태스크에 명시.
- 커밋 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- 스펙: `docs/superpowers/specs/2026-07-15-grid-property-program-design.md`.

## 파일 구조

- **Modify** `arbor/reasoning/program_ast.py` — 3-property 계열: 생성자(`set_grid_size/color/contents` step helper, `keep`/`delta` leaf), `_is_grid_body`, `to_source`/`execute`/`ops_of_ast`/`antiunify_ast` 의 grid 분기, `grid_program(size,color,contents)` 빌더.
- **Modify** `procedural_memory/dsl/transformation/__init__.py` — `set_grid_size`/`set_grid_color`/`set_grid_contents` 를 `@dsl("transformation", …)` 고차 DSL(body=make_grid/coloring 조합)로 등록.
- **Modify** `procedural_memory/operators/synthesize.py` — contents-DECIDE(및 size/color) 결론을 3-property `PAIR.program` 으로 물질화.
- **Modify** (Task 7) `procedural_memory/operators/synthesize.py`·`verify.py`·해당 `production_rules/*.json` — grid-결정 태스크를 per-pair program → generalize → apply_solution 파이프라인으로 라우팅.
- **Modify** `tests/golden_steps.json` — Task 7 재기준화.
- **Create** `debugger/reports/program_viewer.py` — ② easy a–h program 뷰어 페이지. **Modify** `debugger/build.py` — 우상단 버튼 링크 교체 + companion 빌드.
- **Create** `tests/test_grid_program.py`.

---

## Task 1: program_ast — 3-property 스키마 + to_source

`program_ast.py` 에 grid-property step/leaf 생성자와 `to_source` grid 분기를 추가. 격리(아직 소비자 없음).

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_grid_program.py`

**Interfaces:**
- Consumes: 기존 `step`/`program`/`const`.
- Produces:
  - `keep(prop) -> {"keep": prop}` · `delta(remove, add) -> {"delta": {"remove": [...], "add": [...]}}`
  - `set_grid_size(size_leaf)` / `set_grid_color(color_leaf)` / `set_grid_contents(contents_leaf)` → step dicts `{"call": "...", "args": {"size|color|contents": leaf}}`
  - `grid_program(size_leaf, color_leaf, contents_leaf) -> program AST` (body = 세 step, 순서 size→color→contents)
  - `_is_grid_body(body) -> bool` (모든 step 이 set_grid* 이면 True)
  - `to_source` 가 grid body 를 `G1 = set_grid_size(...) ∘ set_grid_color(...) ∘ set_grid_contents(...)` 형으로 렌더

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_grid_program.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as P


class TestGridSchema(unittest.TestCase):
    def test_grid_program_shape(self):
        ast = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[0, 2], [2, 0]]))
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual([s["call"] for s in ast["body"]],
                         ["set_grid_size", "set_grid_color", "set_grid_contents"])
        self.assertEqual(ast["body"][0]["args"]["size"], {"keep": "size"})
        self.assertEqual(ast["body"][2]["args"]["contents"], {"const": [[0, 2], [2, 0]]})

    def test_to_source_grid_renders_setters(self):
        ast = P.grid_program(P.expr("H-1,W-1"), P.delta([5], [1, 2, 3, 4]), P.keep("contents"))
        src = P.to_source(ast)
        self.assertIn("set_grid_size(H-1,W-1)", src)
        self.assertIn("set_grid_color(-[5]+[1, 2, 3, 4])", src)
        self.assertIn("set_grid_contents(keep)", src)
        self.assertTrue(src.rstrip().endswith("output_grid = G1"))

    def test_pixel_body_still_works(self):   # 회귀: 기존 pixel to_source 불변
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        self.assertIn("apply_DSL(tfg0, coloring, P0.coord, 3)", P.to_source(ast))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'keep'`

- [ ] **Step 3: 생성자 + `_is_grid_body` + `to_source` grid 분기 구현** (`program_ast.py`)

생성자(기존 생성자 근처):
```python
def keep(prop):                 return {"keep": prop}
def delta(remove, add):         return {"delta": {"remove": list(remove), "add": list(add)}}
def set_grid_size(size_leaf):    return {"call": "set_grid_size", "args": {"size": size_leaf}}
def set_grid_color(color_leaf):  return {"call": "set_grid_color", "args": {"color": color_leaf}}
def set_grid_contents(c_leaf):   return {"call": "set_grid_contents", "args": {"contents": c_leaf}}

def grid_program(size_leaf, color_leaf, contents_leaf, input_grid="G0"):
    body = [set_grid_size(size_leaf), set_grid_color(color_leaf), set_grid_contents(contents_leaf)]
    return program(body, input_grid=input_grid)

_GRID_OPS = ("set_grid_size", "set_grid_color", "set_grid_contents")

def _is_grid_body(body):
    return bool(body) and all(s.get("call") in _GRID_OPS for s in body)
```

`_grid_leaf_src` (grid leaf → 소스 조각; keep/delta 포함):
```python
def _grid_leaf_src(leaf):
    if "keep" in leaf:  return "keep"
    if "delta" in leaf: return f"-{leaf['delta']['remove']}+{leaf['delta']['add']}"
    return _leaf_src(leaf)          # const/var/expr 재사용
```

`to_source` 최상단에 grid 분기 추가 (기존 `_is_cellset_body` 분기 위/아래):
```python
def to_source(ast) -> str:
    if not ast or not ast.get("body"):
        return "{}"
    body = ast["body"]
    if _is_grid_body(body):
        return _to_source_grid(body)
    if _is_cellset_body(body):
        return _to_source_blob(body)
    # ... 기존 pixel/object 분기 그대로 ...

def _to_source_grid(body):
    parts = {s["call"]: s["args"] for s in body}
    sz = _grid_leaf_src(parts["set_grid_size"]["size"])
    co = _grid_leaf_src(parts["set_grid_color"]["color"])
    ct = _grid_leaf_src(parts["set_grid_contents"]["contents"])
    return ("G0 = input_grid\n"
            f"G1 = set_grid_size({sz}) ∘ set_grid_color({co}) ∘ set_grid_contents({ct})\n"
            "output_grid = G1")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program tests.test_program_ast -v`
Expected: PASS (grid + 기존 program_ast 회귀 전부)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_grid_program.py
git commit -m "feat(grid-program): 3-property 스키마(set_grid*/keep/delta) + to_source

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: program_ast — execute grid 분기 (make_grid+coloring lowering)

grid program 을 실행: `set_grid_size`→차원, `set_grid_color`→base fill, `set_grid_contents`→셀 값. frozen atom 조합으로 lowering.

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_grid_program.py`

**Interfaces:**
- Consumes: `procedural_memory.dsl.transformation.make_grid`·`coloring` (frozen).
- Produces: `execute` 가 grid body 를 처리 — contents leaf 지원: `{"const": grid}`(고정) · `{"keep":"contents"}`(=G0).

- [ ] **Step 1: 실패 테스트 작성** (`tests/test_grid_program.py` 에 클래스 추가)

```python
class TestGridExecute(unittest.TestCase):
    def test_const_contents_produces_that_grid(self):
        out_grid = [[0, 2, 0], [2, 0, 2]]
        ast = P.grid_program(P.const({"height": 2, "width": 3}), P.const([0, 2]), P.const(out_grid))
        self.assertEqual(P.execute(ast, [[9, 9, 9], [9, 9, 9]]), out_grid)   # 입력 무관 상수출력

    def test_keep_contents_is_identity(self):
        g0 = [[1, 0], [0, 1]]
        ast = P.grid_program(P.keep("size"), P.keep("color"), P.keep("contents"))
        self.assertEqual(P.execute(ast, g0), g0)

    def test_keep_size_const_contents(self):   # size=keep(=G0 dims), contents=const 같은 크기
        g0 = [[0, 0], [0, 0]]
        ast = P.grid_program(P.keep("size"), P.const([0, 5]), P.const([[5, 0], [0, 5]]))
        self.assertEqual(P.execute(ast, g0), [[5, 0], [0, 5]])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program.TestGridExecute -v`
Expected: FAIL (execute 가 grid body 를 pixel 로 오해 → KeyError `target` 또는 오답)

- [ ] **Step 3: `execute` grid 분기 구현** (`execute` 함수 시작에 분기 추가)

```python
def execute(ast, grid_in, choice=None):
    if not ast or not ast.get("body"):
        return [list(r) for r in grid_in]
    if _is_grid_body(ast["body"]):
        return _execute_grid(ast["body"], grid_in, choice)
    # ... 기존 pixel/cellset 분기 그대로 ...

def _execute_grid(body, grid_in, choice):
    """set_grid_size/color/contents → make_grid+coloring lowering. contents 가 산출을 지배."""
    from procedural_memory.dsl.transformation import make_grid, coloring
    parts = {s["call"]: s["args"] for s in body}
    ct = parts["set_grid_contents"]["contents"]
    if "keep" in ct:                      # 항등 = G0
        return [list(r) for r in grid_in]
    if "const" in ct:                     # 상수/결정된 grid = 그대로 산출
        return [list(r) for r in ct["const"]]
    # 그 외(remap 등 leaf)는 Phase 1 범위 밖 → 항등 fallback (구현 확장 지점)
    return [list(r) for r in grid_in]
```

> **행동보존/정직(§1-5):** contents=const 는 "그 grid 를 낸다"이다. size/color leaf 는 Phase 1 에서 실행상
> 관측·검증용(색집합·크기가 const contents 와 일치하는지)이며 산출은 contents 가 지배 — const contents 가
> train 출력과 일치함은 `_grid_decide` 가 이미 검증. (make_grid 기반 셀별 물질화 렌더는 to_source·뷰어에서.)

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program tests.test_program_ast -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_grid_program.py
git commit -m "feat(grid-program): execute grid 분기 (contents 가 산출 지배)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `grid_program_from_decide` 빌더 (_grid_decide → 3-property AST)

`_grid_decide` 의 per-property 결정(KEEP/CONST/MAP/SET-MAP + note)을 3-property AST 로 매핑하는 순수 함수. 격리 테스트.

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (또는 `arbor/reasoning/program.py` — 빌더는 grid-decide 근처가 자연스러우면 거기; import 순환 피해 `program_ast` 권장)
- Test: `tests/test_grid_program.py`

**Interfaces:**
- Consumes: `_grid_decide(train, paG0)` 반환 dict(스펙: `{prop: {type, within, cands, decision, value, note?, map?}}`).
- Produces: `grid_program_from_decide(dec) -> program AST | None` — 세 property 모두 DECIDE 면 3-property AST, 아니면 None(하강 case).

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestGridBuilder(unittest.TestCase):
    def test_constant_output_task_ab_shape(self):
        # a/b 형: size DECIDE(KEEP), color DECIDE(CONST set), contents DECIDE(상수출력, value=고정 grid)
        fixed = [[0, 2, 0], [2, 0, 2]]
        dec = {
            "size":     {"decision": "DECIDE", "value": (2, 3), "within": [True, True], "cands": [("KEEP", (2, 3), True)]},
            "color":    {"decision": "DECIDE", "value": frozenset({0, 2}), "cands": [("CONST", frozenset({0, 2}), True)]},
            "contents": {"decision": "DECIDE", "value": fixed, "note": "상수출력", "cands": [("CONST", "상수출력", True)]},
        }
        ast = P.grid_program_from_decide(dec)
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual(ast["body"][2]["args"]["contents"], {"const": fixed})   # 상수출력 → const grid
        self.assertEqual(P.execute(ast, [[9, 9, 9], [9, 9, 9]]), fixed)          # 실행하면 그 grid

    def test_descend_returns_none(self):
        dec = {"size": {"decision": "DECIDE", "value": (2, 2)},
               "color": {"decision": "DECIDE", "value": frozenset({0})},
               "contents": {"decision": "DESCEND", "value": None}}
        self.assertIsNone(P.grid_program_from_decide(dec))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program.TestGridBuilder -v`
Expected: FAIL — no attribute `grid_program_from_decide`

- [ ] **Step 3: 빌더 구현** (`program_ast.py`)

```python
def _size_leaf(d):
    cands = d.get("cands") or []
    kinds = {k for k, _, ok in cands if ok}
    if "KEEP" in kinds:                    # 출력크기=입력크기
        return keep("size")
    for k, v, ok in cands:                 # MAP[H1=...] → expr
        if ok and k.startswith("MAP"):
            return expr(k[k.find("[") + 1:k.rfind("]")])
    h, w = d["value"]
    return const({"height": h, "width": w})

def _color_leaf(d):
    for k, v, ok in (d.get("cands") or []):
        if ok and k.startswith("KEEP"):
            return keep("color")
    # SET-MAP(-{rem}+{add}) 은 Phase 1 의 a/b(CONST) 가 안 타는 경로 → 구현 시 kind 문자열
    # "SET-MAP(-[..]+[..])" 를 파싱해 delta(remove, add) 로(또는 _grid_decide 가 remove/add 를
    # 구조로 노출하도록 값-파생 확장). 전역remap 태스크에서 골든으로 검증. Phase 1 필수 아님.
    return const(sorted(d["value"]))                       # 기본: 색집합 상수

def grid_program_from_decide(dec):
    if any(dec[p]["decision"] != "DECIDE" for p in ("size", "color", "contents")):
        return None
    cnote = dec["contents"].get("note")
    if cnote == "항등":
        c_leaf = keep("contents")
    else:                                  # 상수출력·전역remap → const grid (검증된 value)
        c_leaf = const(dec["contents"]["value"])
    return grid_program(_size_leaf(dec["size"]), _color_leaf(dec["color"]), c_leaf)
```

> **주의(delta 정확도):** `_grid_decide` 의 SET-MAP 후보는 `(-{rem}+{add})` 정보를 문자열 kind 로만 노출한다
> (program.py 의 `_grid_decide` color 분기 참조: `f"SET-MAP(-{sorted(rem0)}+{sorted(add0)})"`). 구현 시 그 kind
> 문자열을 파싱하거나 `_grid_decide` 가 remove/add 를 구조로도 노출하도록 **작은 확장**(값 파생, §1-1 아님)을 한다.
> 테스트는 CONST/KEEP 경로만 강제(위); SET-MAP delta 는 실제 태스크(전역remap)에서 골든으로 검증.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program tests.test_program_ast -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_grid_program.py
git commit -m "feat(grid-program): _grid_decide → 3-property AST 빌더

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: set_grid_size/color/contents 를 고차 DSL 로 등록

세 DSL 을 `@dsl("transformation", …)` 로 등록(body=frozen atom 조합). ontology 에 spec 노출(§dsl-taxonomy 성장).

**Files:**
- Modify: `procedural_memory/dsl/transformation/__init__.py`
- Test: `tests/test_grid_program.py`

**Interfaces:**
- Consumes: 기존 `make_grid`·`coloring`·`@dsl`·`effect`.
- Produces: `SPECS` 에 `set_grid_size`/`set_grid_color`/`set_grid_contents` 등록(kind="transformation", in/out/effect). body 는 조합.

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestGridDSLRegistered(unittest.TestCase):
    def test_three_setters_in_specs(self):
        from procedural_memory.dsl.registry import SPECS
        for name in ("set_grid_size", "set_grid_color", "set_grid_contents"):
            self.assertIn(name, SPECS)
            self.assertEqual(SPECS[name]["kind"], "transformation")
    def test_frozen_atoms_still_two(self):   # make_grid·coloring 동결 불변
        from procedural_memory.dsl.registry import SPECS
        self.assertIn("make_grid", SPECS); self.assertIn("coloring", SPECS)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program.TestGridDSLRegistered -v`
Expected: FAIL — `set_grid_size` not in SPECS

- [ ] **Step 3: 등록** (`transformation/__init__.py` 에 추가; body 는 조합)

```python
@dsl("transformation", ["size"], "grid", effect=effect("create", "grid"))
def set_grid_size(grid, size):
    """G1 의 차원 설정 = make_grid 조합. (고차 DSL: frozen make_grid 로 lowering.)"""
    return make_grid(size, fill=0)

@dsl("transformation", ["grid", "color"], "grid", effect=effect("recolor", "grid"))
def set_grid_color(grid, color):
    """G1 의 base/palette 설정. color 집합의 base(fill) 로 배경 확정 — 나머지 색은 contents 가 채움."""
    return grid                          # base/palette 는 표시·검증용; 산출은 contents 지배(Phase 1)

@dsl("transformation", ["grid", "contents"], "grid", effect=effect("create", "grid"))
def set_grid_contents(grid, contents):
    """G1 의 셀 값 = coloring 조합(또는 상수/항등). Phase 1: const grid 그대로, keep=입력."""
    return [list(r) for r in contents] if contents is not None else grid
```

> **하네스 §1-1**: 이 셋은 make_grid/coloring 을 부르는 **조합**일 뿐 새 primitive 아님. `make_grid`·`coloring`
> 정의는 무변(동결). ontology 재생성이 있으면(`python -m semantic_memory.build`) 재생성.

- [ ] **Step 4: 테스트 통과 + 골든 무영향 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program -v` → PASS
Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py`
Expected: `PASS: 9/9` (DSL 등록만; 솔버 흐름 무변)

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add procedural_memory/dsl/transformation/__init__.py tests/test_grid_program.py
git commit -m "feat(grid-program): set_grid_size/color/contents 고차 DSL 등록 (make_grid+coloring 조합)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: antiunify_ast — grid(3-property) 계열 dispatch

3-property program 들의 anti-unify: 세 step 이 정렬돼 있으니 property 별 arg 비교(COMM=상수, DIFF=slot).

**Files:**
- Modify: `arbor/reasoning/program_ast.py`
- Test: `tests/test_grid_program.py`

**Interfaces:**
- Produces: `antiunify_ast` 가 전부 grid body 면 grid 경로 — property 별 leaf 동일=유지, 다르면 `{"var":"?<prop>"}` + slot.

- [ ] **Step 1: 실패 테스트 작성**

```python
class TestGridAntiunify(unittest.TestCase):
    def test_identical_grid_programs_no_slots(self):
        a = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[0, 2]]))
        b = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[0, 2]]))
        sk, slots = P.antiunify_ast([a, b])
        self.assertEqual(slots, {})
        self.assertTrue(P._is_grid_body(sk["body"]))

    def test_diff_contents_becomes_slot(self):
        a = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[0, 2]]))
        b = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[2, 0]]))
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?contents", slots)
        self.assertEqual(sk["body"][2]["args"]["contents"], {"var": "?contents"})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program.TestGridAntiunify -v`
Expected: FAIL (antiunify_ast 가 grid body 를 pixel 로 오해 → None 또는 KeyError)

- [ ] **Step 3: `antiunify_ast` grid 분기 구현**

```python
def antiunify_ast(asts):
    valid = [a for a in asts if a and a.get("body")]
    if len(valid) < 2:
        return None, None
    if all(_is_grid_body(a["body"]) for a in valid):
        return _antiunify_ast_grid(valid)
    if all(_is_cellset_body(a["body"]) for a in valid):
        return _antiunify_ast_blob(valid)
    return _antiunify_ast_pixel(valid)

def _antiunify_ast_grid(asts):
    import json as _json
    props = [("set_grid_size", "size"), ("set_grid_color", "color"), ("set_grid_contents", "contents")]
    body, slots = [], {}
    partsN = [{s["call"]: s["args"] for s in a["body"]} for a in asts]
    for call, key in props:
        leaves = [pn[call][key] for pn in partsN]
        same = all(_json.dumps(x, sort_keys=True) == _json.dumps(leaves[0], sort_keys=True) for x in leaves)
        if same:
            leaf = leaves[0]
        else:
            leaf = {"var": f"?{key}"}
            slots[f"?{key}"] = {"kind": key, "pos": key, "values": leaves}
        body.append({"call": call, "args": {key: leaf}})
    return program(body, slots=slots), slots
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m unittest tests.test_grid_program tests.test_program_ast -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add arbor/reasoning/program_ast.py tests/test_grid_program.py
git commit -m "feat(grid-program): antiunify_ast grid(3-property) 계열 dispatch

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.5: 명명 정리 — `set_grid_*` DSL 이름 + `compose`→`apply_solution` (골든 보존)

명명 충돌 정리(사용자 2026-07-16). **골든 보존**(rename 뿐 — DSL 은 아직 솔버 미사용, apply_solution 은 같은
operator 다른 이름=같은 cycle). dead operator `set_grid_size`/`set_grid_color` **제거는 Task 6**(재기준화)에서.

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (생성자 `set_gridsize`→`set_grid_size` 등, `_GRID_OPS`, `_to_source_grid`/`_execute_grid`/`_antiunify_ast_grid`)
- Modify: `procedural_memory/dsl/transformation/__init__.py` (`@dsl` 등록 이름)
- Modify: `tests/test_grid_program.py` (참조)
- Rename: `procedural_memory/operators/compose.py`→`apply_solution.py`, `production_rules/compose.json`→`apply_solution.json`
- Modify: `procedural_memory/operators/__init__.py`(OPERATOR_BODIES 매핑), 및 `compose` operator 를 참조하는 규칙/`ag.kg["compose"]` 등 전 참조

- [ ] **Step 1: DSL rename.** `program_ast.py`·`transformation/__init__.py`·`tests/test_grid_program.py` 에서
`set_gridsize`→`set_grid_size`, `set_gridcolor`→`set_grid_color`, `set_gridcontents`→`set_grid_contents` 일괄.
(주의: 이 이름은 아직 존재하는 operator `set_grid_size`/`set_grid_color` 와 SPECS/production 별개 namespace 라
런타임 충돌 없음 — operator 제거는 Task 6.) 단위 테스트 `python -m unittest tests.test_grid_program` PASS.

- [ ] **Step 2: compose→apply_solution rename.** `grep -rn "compose" procedural_memory/ arbor/` 로 전 참조 파악
후: 파일 2개 rename, operator 이름·`OPERATOR_BODIES`·규칙 참조·`ag.kg["compose"]`/kg 키·doc 문자열 을 `apply_solution`
으로. (loader 가 `production_rules/*.json` 을 이름으로 로드하므로 파일명+operator 필드 일치 확인.)

- [ ] **Step 3: 골든 게이트 (보존)**

Run: `python -m unittest tests.test_grid_program tests.test_program_ast -v` → PASS
Run: `cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 tests/verify_refactor.py` → `PASS: 9/9`
(rename 뿐이라 step 수 불변. MISMATCH 면 compose 참조 누락 — grep 재점검.)

- [ ] **Step 4: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add -A
git commit -m "refactor(naming): set_grid_* DSL 이름 통일 + compose→apply_solution operator (골든 보존)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: compare 는 비교만 — `_predict_test_output` 판정을 hypothesize 로 이관 ⚠️ 핵심 리스크 (골조 정정)

정답 예측 단락을 compare 에서 들어내고, 판정(관계→3속성)을 hypothesize 로 옮긴다. **all-3 → 3-property
program 생성, 부분 → 하강.** SOAR 흐름 변경 → **골든 재기준화**. (스펙 §7 정정 2026-07-16.)

> **⚠️ 이 태스크는 솔버 핵심 흐름(compare↔hypothesize 경계)을 바꾼다 — Tasks 1-5(격리)와 성격이 다르다.**
> 착수 전 `ARBOR_HARNESS.md` 재독. bite-size 로 안 쪼개지거나 c–h 정답이 깨지면 **멈추고 사용자와 의논.**

**Files:**
- Modify: `procedural_memory/operators/compare.py` (`_predict_test_output` 제거/축소 — 비교 결과만 남김)
- Delete: `procedural_memory/operators/grid_slots.py` 의 `set_grid_size`/`set_grid_color` operator + `production_rules/set_grid_{size,color}.json` (dead scaffold 제거; 명명 충돌 해소)
- Modify: `procedural_memory/operators/hypothesize.py` (grid 판정: cross/`_grid_decide` 관계 → 3속성 → all-3: `grid_program_from_decide` per-pair emit / 부분: 하강)
- Modify: 관련 `production_rules/*.json` (compare 후 grid-hypothesize 발화; predict 종류 조정)
- Modify: `tests/golden_steps.json` (재캡처)

**Interfaces:**
- Consumes: `program_ast.grid_program_from_decide`(Task 3), `_grid_decide`, `ag.kg["cross"]`(compare 산물), `root.example_pairs`.

- [ ] **Step 1: 흐름 discovery (필수).** `compare.py`(`_op_compare` kind=predict → `_predict_test_output` ①②),
  `hypothesize.py`(level 별 진입; grid → H-space/synthesize), `solve.json`/`compare.json`/`hypothesize.json`/
  `synthesize.json` 규칙, `S1 ^pair-idx` 커서, `answer-ready`/`produce`/`grid-descend` 배선을 읽어
  **"compare 가 어디서 답을 내고(①), 어디서 하강 신호(②)를 세우는가"** 를 특정. 이관 계획을 report 에 적고 진행.

- [ ] **Step 2: compare 를 비교만으로.** `_predict_test_output` 의 답-예측/answer-ready/branch 를 compare 에서
  제거(cross 결과는 `ag.kg["cross"]` 에 그대로 남김). compare 는 관계만 남기고 끝나게.

- [ ] **Step 3: hypothesize 가 판정·생성.** grid 단계 hypothesize 가 cross 관계(+`_grid_decide`)로 3속성 결정:
  `gp = grid_program_from_decide(dec)`; `gp` 있으면(all-3) 각 example pair 에 `PAIR.program = json.dumps(gp)`
  물질화 + 답 경로(program 실행/기존) 연결; `None`(부분)이면 하강(`produce`/`grid-descend` — 현행 c–h 경로).

- [ ] **Step 4: 정답 불변 확인** (재기준화 전 최우선 게이트)

```bash
PYTHONPATH=. python3 -c "
from arbor.env.dataset import list_tasks, load_task
from debugger.build import _dash_data
for tid,p in list_tasks('easy_a'):
    d=_dash_data(load_task(p), tid)
    print(tid,'correct=',d.get('correct_attempt'),'n_steps=',d['n_steps'])
assert all(_dash_data(load_task(p),t).get('correct_attempt') is not None or t=='easy000i'
           for t,p in list_tasks('easy_a')), 'a-h 중 정답 회귀'
print('OK: easy a-h 정답 유지(i 제외)')
"
```
Expected: easy a–h `correct` 非None(i 는 원래 미해결). a/b 에 3-property `PAIR.program` 존재(Task 6 이전 확인 스크립트 재사용).

- [ ] **Step 5: 골든 재기준화 + 커밋.** a/b·c–h 새 step 수 재캡처(§Task 7 Step 4 스크립트) → `golden_steps.json`
  갱신 → `verify_refactor.py` PASS. made000b 정답 유지. 커밋(재기준화 이유 명시):
```bash
cd /Users/sir_k/Desktop/PySOAR
git add procedural_memory/operators/compare.py procedural_memory/operators/hypothesize.py \
        procedural_memory/production_rules/ tests/golden_steps.json
git commit -m "refactor(grid-program): compare=비교만, hypothesize=관계→3-property program (골조 정정) + 골든 재기준화

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> **Fallback(체크포인트):** compare↔hypothesize 재배선이 너무 얽히면 — compare 단락을 남기되 그 자리에서
> program+solution 만 추가 물질화(추가적, 골든 보존)하는 최소안으로 후퇴하고 **의논**. (뷰어 Task 8 은 그걸로도 동작.)

---

## Task 7: 3-property 파이프라인 완결(generalize/apply_solution) + 재기준화 확정

a/b 의 per-pair 3-property program 이 generalize(3-property antiunify, Task 5) → solution → apply_solution(test 실행)
→ 답 으로 이어지는지 확인·완결. (Task 6 에서 답이 이미 program 실행으로 나오면 이 태스크는 solution 물질화 확인.)

**Files:**
- Modify: `procedural_memory/operators/generalize.py`·`apply_solution.py` (grid program 소비 — 대부분 Task 5 로 이미 지원; 배선 확인)
- Modify: `tests/golden_steps.json` (필요 시 최종 재캡처)

- [ ] **Step 1: generalize 가 grid program 을 anti-unify.** example pair 들의 3-property `PAIR.program`(AST-json)을
  `antiunify_ast`(grid 계열, Task 5)로 → `TASK.solution`(3-property, a/b 는 변수 없음=동일). 배선 확인/보완.

- [ ] **Step 2: apply_solution 가 solution 을 test 에 실행.** `execute`(grid 분기, Task 2)로 test G0 → 답. 기존 apply_solution 경로.

- [ ] **Step 3: a/b 파이프라인 정답 + solution 확인**

```bash
cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 -c "
from arbor.env.dataset import list_tasks, load_task
from arbor.engine.trace import _Tracer
from arbor.agent.focus import setup_focus_agent
paths=dict(list_tasks('easy_a'))
for tid in ('easy000a','easy000b'):
    tr=_Tracer(load_task(paths[tid]),tid,setup=setup_focus_agent); tr.run(max_cycles=1500)
    sol=[v for (i,a,v) in tr.ag.wm if a=='solution' and v not in (None,'{}')]
    print(tid,'solution:', sol[:1])
    assert sol, f'{tid} solution 없음'
print('OK: a/b solution 물질화')
"
```
Expected: a/b `TASK.solution` 이 3-property(placeholder 아님).

- [ ] **Step 4: 최종 골든 재기준화.** easy_a 전부 재캡처 → `golden_steps.json` → `verify_refactor.py` PASS. c–h 정답 유지.
```bash
cd /Users/sir_k/Desktop/PySOAR && PYTHONPATH=. python3 -c "
import json
from arbor.env.dataset import list_tasks, load_task
from debugger.build import _dash_data
g={t:{'n_steps':_dash_data(load_task(p),t)['n_steps'],
      'correct_attempt':_dash_data(load_task(p),t).get('correct_attempt')} for t,p in list_tasks('easy_a')}
json.dump(g, open('tests/golden_steps.json','w'), indent=2); print('re-baselined:', {k:v['n_steps'] for k,v in g.items()})
"
```

- [ ] **Step 5: 커밋**
```bash
cd /Users/sir_k/Desktop/PySOAR
git add procedural_memory/operators/generalize.py procedural_memory/operators/apply_solution.py tests/golden_steps.json
git commit -m "feat(grid-program): a/b 3-property 파이프라인 완결(generalize/apply_solution) + 재기준화 확정

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: ② program 뷰어 — easy a–h program 페이지 (버튼 교체)

우상단 "이 문제 anti-unification" 버튼을 **program 뷰어**로 교체. easy a–h 각 태스크의 per-pair program(text+AST+시각화) + task.solution.

**Files:**
- Create: `debugger/reports/program_viewer.py`
- Modify: `debugger/build.py` (버튼 링크 → `program_report_all.html`; companion 빌드 훅)

**Interfaces:**
- Consumes: `_Tracer`+`setup_focus_agent`(태스크별 program 수집), `program_ast.{as_source,to_source,render_header}`, Task 10(program-ast) 렌더러 패턴.

- [ ] **Step 1: 수집 헬퍼.** `program_report.py::_run_programs` / `easy_antiunify_viz.py::_pair_asts` 패턴으로,
easy a–h 각 태스크를 `_Tracer` 로 돌려 example PAIR.program(AST-json) + task.solution 을 수집하는 함수 작성.

- [ ] **Step 2: 렌더.** 태스크 선택 탭(a…h) + 각 태스크: per-pair program 을 (1) `to_source`+`render_header` text,
(2) AST 트리(간단 nested 렌더), (3) 시각화(grid=3-property setter 박스 / pixel=coloring flow — easy_antiunify_viz
헬퍼 재사용). program 없는 태스크(i·미해결)는 "미합성/크기변화" 표식.

- [ ] **Step 3: 버튼 교체.** `debugger/build.py:139-146` 의 nav 앵커 href/텍스트를 `program_report_all.html` +
"▤ 이 문제 program 보기" 로 바꾸고, `__main__` 에서 `program_viewer.build()` 를 companion 으로 빌드.

- [ ] **Step 4: 빌드·렌더 확인**

Run: `cd /Users/sir_k/Desktop/PySOAR && python -m debugger.reports.program_viewer` → `wrote …program_report_all.html`
Run: `cd /Users/sir_k/Desktop/PySOAR && python -c "s=open('debugger/traces/program_report_all.html').read(); print('setter', 'set_grid_contents' in s or 'set_grid_size' in s, '| coloring', 'coloring' in s, '| tabs a-h', all(f'easy000{c}' in s for c in 'abcdefgh'))"`
Expected: 3개 지표 확인(a/b 는 set_grid*, c–h 는 coloring, 탭 a–h 존재).
Run: `cd /Users/sir_k/Desktop/PySOAR && python -m debugger.build 2>&1 | tail -3` → focus_dashboard + program_report_all 정상.

- [ ] **Step 5: 커밋**

```bash
cd /Users/sir_k/Desktop/PySOAR
git add debugger/reports/program_viewer.py debugger/build.py
git commit -m "feat(dashboard): program 뷰어 — easy a-h per-pair program 확인 페이지 (버튼 교체)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 최종 검증

- [ ] `python -m unittest tests.test_grid_program tests.test_program_ast -v` → 전부 PASS.
- [ ] `PYTHONPATH=. python3 tests/verify_refactor.py` → `PASS: 9/9` (Task 7 후 = 재기준화된 기준). made000b 정답 유지.
- [ ] easy000a/b 가 3-property `PAIR.program` + `task.solution` 물질화, 여전히 ✓풀림.
- [ ] `program_report_all.html` 에서 easy a–h program 확인 가능(a/b=set_grid*, c–h=pixel), 버튼이 이 페이지로.
- [ ] `set_grid_size/color/contents` 가 SPECS/ontology 에 고차 DSL 로. make_grid·coloring 동결 불변.

## 리스크 / 멈춤 지점 (하네스 §5)

- **Task 7 (파이프라인 라우팅)**: SOAR 규칙 흐름 변경 — 가장 크다. bite-size 로 안 쪼개지거나 c–h step 이
  바뀌면 **멈추고 의논**. 대안(fallback): Task 6(추가적 물질화)+Task 8(뷰어)만으로도 "a/b program 가시화"는
  달성 — 파이프라인 라우팅은 별도 재설계.
- **§1-5 정직성**: 상수출력을 const grid 로 담는 건 train-검증 결론의 실행 물질화(답 박기 아님). size/color leaf
  가 실제로 관측·검증되는지(색집합·크기 일치) execute/verify 에서 확인.
- **delta/SET-MAP 정확도** (Task 3): `_grid_decide` kind 문자열 파싱 or 구조 확장 — 전역remap 태스크 골든으로 검증.
- **color base/palette 애매성** (Task 4): set_grid_color 실행 역할이 Phase 1 에서 표시·검증용. 색집합이 fill+contents
  로 재현 안 되면 멈추고 §7.
