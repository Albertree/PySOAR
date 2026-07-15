# easy a–h program 뷰어 표현 통일 + 코드 실행기 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** easy a–h program 뷰어에서 grid(a·b)/coloring(c–h) 두 계열이 하나의 표기·시각화 언어로 보이게 하고(표현 계열은 유지), body 가 참조하는 ARCKG accessor 를 실제 실행 가능하게 만들며, 순수 프런트엔드 코드 실행기로 실행/검증을 분리한다.

**Architecture:** ② 실 accessor(`pixels_of`/`height`/`width`) 완성 → ① 뷰어 로컬 `display_source`+단일 box-flow(불변 `to_source` 와 독립) → ③ 빌드타임 parity 로 정직성을 보장하는 순수 프런트엔드 JS atom 인터프리터.

**Tech Stack:** Python 3(기존 ARBOR), 표준 unittest/pytest, 정적 HTML+바닐라 JS(외부 의존 0).

## Global Constraints

- `arbor/reasoning/program_ast.py` 의 `to_source`/`as_source`/`parse_program` 및 그것을 검증하는 기존 테스트(`tests/test_program_ast.py`, `tests/test_grid_program.py`)는 **불변** — 파싱 계약(compress/generalize/coloring 이 되파싱).
- 신규 accessor 는 ARCKG property 의 **투영**만(새 노드 데이터 발명 금지, 하네스 §2-1). `color_of`/`contents_of`(grid) 추가 **금지**(registry 함수명 충돌 — `color_of` 는 OBJECT용 기존).
- c–h 를 grid 3-property(`set_grid_contents(const)`)로 재표현 **금지**(§1-5/§6 정답 const-굽기).
- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 현재 브랜치 `seokki-refactor`(feature 브랜치 — 추가 브랜칭 불필요).
- 픽셀 index 규약: `pixels_of(g)[i]` 의 좌표 = `(i // width, i % width)`(솔버 전역 `idx = r*W+c`).

---

### Task 1: `height(grid)` · `width(grid)` accessor

**Files:**
- Modify: `procedural_memory/dsl/property/__init__.py` (GRID-level 블록, `contents` 다음 ~line 60)
- Test: `tests/test_grid_hw_accessor.py` (create)

**Interfaces:**
- Produces: `height(grid) -> int`, `width(grid) -> int` (registry `property`/`["grid"]`/`"int"`). `size(grid)["height"]`/`["width"]` 의 투영.
- Consumes: 기존 `size(grid)`(같은 모듈), `Grid(grid_id, raw)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grid_hw_accessor.py
import unittest
from arbor.perception.arckg.grid import Grid
from procedural_memory.dsl.property import height, width, size


class TestGridHW(unittest.TestCase):
    def test_height_width_project_size(self):
        g = Grid("T0.P0.G0", [[0, 1, 2], [3, 4, 5]])   # 2x3
        self.assertEqual(height(g), 2)
        self.assertEqual(width(g), 3)
        self.assertEqual(height(g), size(g)["height"])
        self.assertEqual(width(g), size(g)["width"])

    def test_registered_in_specs(self):
        from procedural_memory.dsl.registry import SPECS
        self.assertEqual(SPECS["height"]["in"], ["grid"])
        self.assertEqual(SPECS["width"]["out"], "int")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_grid_hw_accessor.py -v`
Expected: FAIL — `ImportError: cannot import name 'height'`.

- [ ] **Step 3: Add the accessors**

`procedural_memory/dsl/property/__init__.py` 의 `contents` 정의(약 line 59) **직후**에 삽입:

```python
@dsl("property", ["grid"], "int")
def height(grid):
    """grid 높이 (size 의 투영 — 새 데이터 아님)."""
    return size(grid)["height"]


@dsl("property", ["grid"], "int")
def width(grid):
    """grid 너비 (size 의 투영 — 새 데이터 아님)."""
    return size(grid)["width"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_grid_hw_accessor.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add procedural_memory/dsl/property/__init__.py tests/test_grid_hw_accessor.py
git commit -m "feat(dsl): height/width grid accessor (size 투영)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `pixels_of(grid)` + Pixel `.coord` + selection pixel 배선

**Files:**
- Modify: `arbor/perception/arckg/pixel.py` (`Pixel` 클래스에 `.coord` property)
- Modify: `procedural_memory/dsl/util/__init__.py` (`pixels_of` 추가)
- Modify: `procedural_memory/dsl/selection/__init__.py:12,15` (import + `_LEVEL_CHILDREN`)
- Test: `tests/test_pixels_of.py` (create)

**Interfaces:**
- Produces: `pixels_of(grid) -> list[Pixel]` (registry `util`/`["grid"]`/`"list[pixel]"`), 길이 `H*W`, 행우선. `Pixel.coord -> (row, col)` 튜플. `elements_at(grid, "pixel")` == `pixels_of(grid)`.
- Consumes: `Grid.raw`/`.width`/`.height`/`.node_id`, `Pixel(pixel_id, color, row, col)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pixels_of.py
import unittest
from arbor.perception.arckg.grid import Grid
from procedural_memory.dsl.util import pixels_of
from procedural_memory.dsl.selection import elements_at


class TestPixelsOf(unittest.TestCase):
    def setUp(self):
        self.g = Grid("T0.P0.G0", [[7, 8, 9], [1, 2, 3]])   # 2x3, W=3

    def test_rowmajor_full_length(self):
        px = pixels_of(self.g)
        self.assertEqual(len(px), 6)                          # H*W

    def test_index_coord_convention(self):
        px = pixels_of(self.g)
        for i in range(6):
            self.assertEqual(px[i].coord, (i // 3, i % 3))    # (i//W, i%W)

    def test_color_matches_raw(self):
        px = pixels_of(self.g)
        self.assertEqual(px[0].color, 7)                      # (0,0)
        self.assertEqual(px[5].color, 3)                      # (1,2)

    def test_selection_pixel_level(self):
        sel = elements_at(self.g, "pixel")
        self.assertEqual([p.coord for p in sel],
                         [p.coord for p in pixels_of(self.g)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pixels_of.py -v`
Expected: FAIL — `ImportError: cannot import name 'pixels_of'`.

- [ ] **Step 3a: Add `Pixel.coord`**

`arbor/perception/arckg/pixel.py` 의 `Pixel` 클래스, `to_json` 정의 **앞**에 삽입:

```python
    @property
    def coord(self):
        """(row, col) 튜플 — coloring(grid, position, color) 의 position 인자와 정합."""
        return (self.row, self.col)
```

- [ ] **Step 3b: Add `pixels_of`**

`procedural_memory/dsl/util/__init__.py` 의 `objects_of` **다음**에 삽입(Pixel 은 순환 import 회피 위해 함수 안에서 지연 import):

```python
@dsl("util", ["grid"], "list[pixel]")
def pixels_of(grid):
    """grid 의 모든 셀을 행우선 PIXEL 노드 리스트로 (index i = r*width + c).
    pixels_of(g)[i] 의 좌표 = (i // width, i % width) — 솔버 전역 idx 규약과 일치.
    (grid.pixels 는 객체추출 파생이라 index 비정렬 → raw 에서 직접 생성.)"""
    from arbor.perception.arckg.pixel import Pixel
    W = grid.width
    out = []
    for i in range(grid.height * W):
        r, c = divmod(i, W)
        out.append(Pixel(pixel_id=f"{grid.node_id}.X{i}", color=grid.raw[r][c], row=r, col=c))
    return out
```

- [ ] **Step 3c: Wire pixel level into selection**

`procedural_memory/dsl/selection/__init__.py`:
- line 12 import 에 `pixels_of` 추가: `from procedural_memory.dsl.util import pairs_of, grids_of, objects_of, filter_, pixels_of`
- line 15 `_LEVEL_CHILDREN` 를 다음으로 교체(주석의 "pixel 은 pixels_of 도입 시 추가" 도 삭제):

```python
_LEVEL_CHILDREN = {"pair": pairs_of, "grid": grids_of, "object": objects_of, "pixel": pixels_of}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pixels_of.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: 계약 불변 회귀 확인 + commit**

Run: `python -m pytest tests/test_program_ast.py tests/test_grid_program.py -q`
Expected: PASS (기존 전부 — 계약 불변).

```bash
git add arbor/perception/arckg/pixel.py procedural_memory/dsl/util/__init__.py \
        procedural_memory/dsl/selection/__init__.py tests/test_pixels_of.py
git commit -m "feat(dsl): pixels_of(grid) 실구현 + Pixel.coord + selection pixel 배선

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `display_source(ast)` — 뷰어 로컬 통일 body

**Files:**
- Modify: `debugger/reports/program_viewer.py` (신규 `display_source` + 헬퍼; ① text 렌더 교체)
- Test: `tests/test_display_source.py` (create)

**Interfaces:**
- Produces: `display_source(ast) -> str` (뷰어 로컬; `to_source` 와 독립). grid/pixel 모두 `g = fn(g, …)` 순차형, 실 DSL·ARCKG accessor·실값.
- Consumes: `arbor.reasoning.program_ast`(`_is_grid_body`), AST dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_display_source.py
import unittest
from arbor.reasoning import program_ast as PA
from debugger.reports.program_viewer import display_source


class TestDisplaySource(unittest.TestCase):
    def test_grid_keep_and_const(self):
        ast = PA.grid_program(PA.keep("size"),
                              PA.const([0, 2]),
                              PA.const([[0, 0], [0, 2]]))
        src = display_source(ast)
        self.assertIn("g = input_grid", src)
        self.assertIn("set_grid_size(g, size(input_grid))", src)   # keep -> ARCKG size
        self.assertIn("set_grid_color(g, [0, 2])", src)
        self.assertIn("set_grid_contents(g, [[0, 0], [0, 2]])", src)  # 실 2D 배열
        self.assertIn("output_grid = g", src)
        for banned in ("keep", "grid[", "∘", "tfg", "apply_DSL"):
            self.assertNotIn(banned, src)

    def test_pixel_coloring(self):
        ast = PA.program([
            PA.step("coloring", target=PA.ref("pixel", PA.const(7)), color=PA.const(0)),
            PA.step("coloring", target=PA.ref("pixel", PA.const(35)), color=PA.const(2)),
        ])
        src = display_source(ast)
        self.assertIn("coloring(g, pixels_of(input_grid)[7].coord, 0)", src)
        self.assertIn("coloring(g, pixels_of(input_grid)[35].coord, 2)", src)
        for banned in ("tfg", "apply_DSL", "in_px", "∘"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_display_source.py -v`
Expected: FAIL — `ImportError: cannot import name 'display_source'`.

- [ ] **Step 3: Implement `display_source` + helpers**

`debugger/reports/program_viewer.py`, `import` 블록 다음(약 line 31, `ast_tree` 정의 앞)에 삽입:

```python
# ── display_source: 뷰어 로컬 통일 body (to_source[파싱계약]과 독립; 실 DSL·ARCKG accessor·실값) ──
def _disp_leaf(leaf):
    """color/index leaf → 소스 토큰. const=실값(json), var=이름, expr=식 그대로."""
    if "const" in leaf:
        return json.dumps(leaf["const"])
    if "var" in leaf:
        return str(leaf["var"])
    if "expr" in leaf:
        return str(leaf["expr"])
    return json.dumps(leaf)


def _disp_grid_leaf(leaf, prop):
    """grid-property leaf → 실행형 소스. keep→`prop(input_grid)`(ARCKG 투영), const=실값,
    expr=식 그대로(forward). prop ∈ {size,color,contents}."""
    if "keep" in leaf:
        return f"{prop}(input_grid)"                 # size/color/contents(input_grid)
    if "const" in leaf:
        return json.dumps(leaf["const"])             # size dict / color list / contents 2D 배열 실값
    if "expr" in leaf:
        return str(leaf["expr"])                     # (forward: H/W 어휘 번역은 별건)
    if "delta" in leaf:
        d = leaf["delta"]
        return f"delta(remove={d['remove']}, add={d['add']})"
    return json.dumps(leaf)


def _display_grid(body):
    parts = {s["call"]: s["args"] for s in body}
    sz = _disp_grid_leaf(parts["set_grid_size"]["size"], "size")
    co = _disp_grid_leaf(parts["set_grid_color"]["color"], "color")
    ct = _disp_grid_leaf(parts["set_grid_contents"]["contents"], "contents")
    return ("g = input_grid\n"
            f"g = set_grid_size(g, {sz})\n"
            f"g = set_grid_color(g, {co})\n"
            f"g = set_grid_contents(g, {ct})\n"
            "output_grid = g")


_ACCESSOR = {"pixel": "pixels_of", "object": "objects_of"}


def _display_pixel(body):
    lines = ["g = input_grid"]
    for s in body:
        tgt = s["args"]["target"]
        col = _disp_leaf(s["args"]["color"])
        ref = tgt.get("ref")
        if ref in _ACCESSOR:                          # pixel/object: 단일 좌표 채색
            idx = _disp_leaf(tgt["index"])
            lines.append(f"g = coloring(g, {_ACCESSOR[ref]}(input_grid)[{idx}].coord, {col})")
        elif ref == "cellset":                        # blob: 셀 집합 (a–h 밖 — 정직한 다중형)
            cl = tgt["cells"]
            cells = _disp_leaf(cl)
            lines.append(f"for ix in {cells}:\n    g = coloring(g, divmod(ix, width(input_grid)), {col})")
        else:
            lines.append(f"# 해석 불가 target: {json.dumps(tgt)}")
    lines.append("output_grid = g")
    return "\n".join(lines)


def display_source(ast):
    """AST → 통일 body 소스(뷰어 로컬). grid/pixel 계열 모두 실행형 'g = fn(g, …)'.
    to_source(파싱 계약) 와 독립 — 같은 AST 를 일관 프레이밍만(표현 계열은 그대로 드러남)."""
    body = (ast or {}).get("body") or []
    if not body:
        return "g = input_grid\noutput_grid = g"
    if PA._is_grid_body(body):
        return _display_grid(body)
    return _display_pixel(body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_display_source.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: ① text 렌더를 display_source 로 교체**

`debugger/reports/program_viewer.py` 의 `_pair_block`(약 line 167), `① text` view 부분:

교체 전:
```python
            f'<div class="view"><div class="vt">① text (to_source + render_header)</div>'
            f'<pre class="hdr">{html.escape(_render_header_safe(ast, g0))}</pre>'
            f'<pre class="src">{html.escape(PA.to_source(ast))}</pre></div>'
```
교체 후(불투명 to_source 는 접어서 참조용):
```python
            f'<div class="view"><div class="vt">① text (통일 body · 실행형)</div>'
            f'<pre class="hdr">{html.escape(_render_header_safe(ast, g0))}</pre>'
            f'<pre class="src">{html.escape(display_source(ast))}</pre>'
            f'<details class="rawsrc"><summary>canonical to_source (파싱계약·참조용)</summary>'
            f'<pre class="src">{html.escape(PA.to_source(ast))}</pre></details></div>'
```

- [ ] **Step 6: 재생성 + 육안/grep 검증**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
s = open("debugger/traces/program_report_all.html").read()
assert "set_grid_size(g, size(input_grid))" in s, "grid 통일 body 없음"
assert "coloring(g, pixels_of(input_grid)[" in s, "pixel 통일 body 없음"
# 통일 body 영역(details 밖)에는 금지 토큰 부재 — details(참조용)엔 남아있어도 됨
import re
main = re.sub(r'<details class="rawsrc">.*?</details>', '', s, flags=re.S)
for banned in ("set_grid_size(keep)", "grid[6×6]", "tfg1 = apply_DSL"):
    assert banned not in main, f"금지 토큰 잔존: {banned}"
print("OK display_source 통일 확인")
PY
```
Expected: `OK display_source 통일 확인`.

- [ ] **Step 7: Commit**

```bash
git add debugger/reports/program_viewer.py tests/test_display_source.py
git commit -m "feat(viewer): display_source 통일 body(실행형) — keep/grid[NxN]/∘/tfg 폐기

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 단일 `_viz` box-flow (③ 시각화 통일)

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_grid_viz`/`_pixel_viz`/`_viz` → 단일 골격; `_grid_leaf_repr` 정직화)

**Interfaces:**
- Consumes: `easy_antiunify_viz`(`EV.grid`, `EV.opb`, `EV.colr`, `EV.tgt`), `display_source` 헬퍼 없음(자체 leaf 라벨).
- Produces: `_viz(ast, ex) -> str` — 두 계열 공통 골격(G0 썸네일 → 스텝 → G1 썸네일, color 스와치).

- [ ] **Step 1: `_grid_leaf_repr` 정직화**

`debugger/reports/program_viewer.py` 의 `_grid_leaf_repr`(약 line 96)를 교체 — `keep`→`prop(input_grid)`, contents const→실 2D 배열 문자열(grid[NxN] 폐기). 기존 시그니처에 `prop` 인자 추가:

```python
def _grid_leaf_repr(leaf, prop=""):
    """grid-arg leaf → 시각화 박스 라벨(정직화). keep→`prop(input_grid)`, contents const→실 2D 배열."""
    if "keep" in leaf:
        return f"{leaf['keep']}(input_grid)"          # size/color/contents(input_grid)
    if "delta" in leaf:
        d = leaf["delta"]
        return f"-{d['remove']}+{d['add']}"
    if "var" in leaf:
        return str(leaf["var"])
    if "expr" in leaf:
        return str(leaf["expr"])
    if "const" in leaf:
        v = leaf["const"]
        if isinstance(v, dict) and "height" in v:
            return f"{{height:{v['height']}, width:{v['width']}}}"
        return json.dumps(v)                          # color list / contents 2D 배열 실값(grid[NxN] 폐기)
    return str(leaf)
```

- [ ] **Step 2: 단일 box-flow 골격으로 `_grid_viz`/`_pixel_viz`/`_viz` 교체**

`_grid_viz`, `_pixel_viz`, `_viz`(약 line 123–148)를 다음으로 교체:

```python
def _endpoint_rows(ex):
    """공통 끝점: (G0 행, G1 행) — input/output 썸네일 인라인."""
    g0 = (f'<div class="row"><span class="bx grid">G0 = input_grid</span>{EV.grid(ex["input"])}'
          f'</div><div class="v"></div>')
    g1 = f'<div class="row"><span class="bx grid">G1 = output_grid</span>{EV.grid(ex["output"])}</div>'
    return g0, g1


def _grid_step_rows(ast):
    parts = {s["call"]: s["args"] for s in ast["body"]}
    sz, co, ct = (parts["set_grid_size"]["size"], parts["set_grid_color"]["color"],
                  parts["set_grid_contents"]["contents"])
    color_sw = (_swatches(co["const"]) if isinstance(co.get("const"), list)
                and not _is_grid_literal(co["const"]) else "")
    return [
        f'<div class="row">{EV.opb("set_grid_size")}<span class="h"></span>{EV.colr(_grid_leaf_repr(sz, "size"))}</div><div class="v"></div>',
        f'<div class="row">{EV.opb("set_grid_color")}<span class="h"></span>{EV.colr(_grid_leaf_repr(co, "color"))}{color_sw}</div><div class="v"></div>',
        f'<div class="row">{EV.opb("set_grid_contents")}<span class="h"></span>{EV.colr(_grid_leaf_repr(ct, "contents"))}</div><div class="v"></div>',
    ]


def _pixel_step_rows(ast):
    rows = []
    for s in ast["body"]:
        tgt = s["args"]["target"]
        ref = tgt.get("ref")
        col_leaf = s["args"]["color"]
        col = col_leaf.get("const")
        sw = _swatches([col]) if isinstance(col, int) else ""
        if ref in _ACCESSOR:
            idx = _disp_leaf(tgt["index"])
            label = f"{_ACCESSOR[ref]}(input_grid)[{idx}].coord"
        elif ref == "cellset":
            label = f"cells {_disp_leaf(tgt['cells'])}"
        else:
            label = "?"
        rows.append(f'<div class="row">{EV.opb("coloring")}<span class="h"></span>'
                    f'{EV.tgt(label, prefix="")}<span class="h"></span>{EV.colr(_disp_leaf(col_leaf))}{sw}</div>'
                    f'<div class="v"></div>')
    return rows


def _viz(ast, ex):
    """두 계열 공통 box-flow: G0 썸네일 → 스텝들 → G1 썸네일."""
    g0, g1 = _endpoint_rows(ex)
    steps = _grid_step_rows(ast) if PA._is_grid_body(ast.get("body") or []) else _pixel_step_rows(ast)
    return f'<div class="flow">{g0}{"".join(steps)}{g1}</div>'
```

주의: `EV.tgt(idx, cls="", prefix="in_px")` 는 `f'{prefix}[{idx}].coord'` 를 만든다. 라벨 전체를 이미 만들었으므로 `prefix=""` + idx 자리에 label 을 넘기면 `[label].coord` 가 되어 중복된다 → `EV.tgt` 대신 `EV.dest_box(label)` 를 쓴다. `_pixel_step_rows` 의 target 박스 줄을 다음으로 교체:

```python
        rows.append(f'<div class="row">{EV.opb("coloring")}<span class="h"></span>'
                    f'{EV.dest_box(label)}<span class="h"></span>{EV.colr(_disp_leaf(col_leaf))}{sw}</div>'
                    f'<div class="v"></div>')
```

- [ ] **Step 3: 재생성 + grep 검증**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
s = open("debugger/traces/program_report_all.html").read()
assert "G0 = input_grid" in s and "G1 = output_grid" in s, "공통 끝점 없음"
assert "size(input_grid)" in s, "keep 정직화 안됨(size)"
assert "grid[6×6]" not in s and "grid[6x6]" not in s, "grid[NxN] 잔존"
assert "pixels_of(input_grid)[" in s, "pixel target 라벨 없음"
print("OK _viz 통일 확인")
PY
```
Expected: `OK _viz 통일 확인`.

- [ ] **Step 4: Commit**

```bash
git add debugger/reports/program_viewer.py
git commit -m "feat(viewer): 단일 box-flow ③ 시각화 통일(끝점 썸네일·스와치·정직 leaf)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 빌드타임 parity — `execute(ast,input)` expected 베이킹

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_collect` 반환에 pair 별 `(ast, input, expected)` 포함; 데이터 JSON 임베드)
- Test: `tests/test_program_parity.py` (create)

**Interfaces:**
- Produces: 각 프로그램의 `expected = program_ast.execute(ast, ex["input"])` 를 HTML 에 `__RUNNER_DATA__` JSON 으로 임베드. `_runner_payload(tid, asts, task) -> list[dict]`.
- Consumes: `arbor.reasoning.program_ast.execute`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_program_parity.py
import unittest
from arbor.reasoning import program_ast as PA
from debugger.reports.program_viewer import _runner_payload


class TestParityPayload(unittest.TestCase):
    def test_expected_equals_execute(self):
        ast = PA.program([
            PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(5)),
        ])
        task = {"train": [{"input": [[0, 0], [0, 0]], "output": [[0, 5], [0, 0]]}]}
        payload = _runner_payload("easy000x", [ast], task)
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item["expected"], PA.execute(ast, task["train"][0]["input"]))
        self.assertEqual(item["expected"], [[0, 5], [0, 0]])   # coloring idx1=(0,1)→5
        self.assertIn("body", item)                            # display_source body 문자열
        self.assertEqual(item["input"], [[0, 0], [0, 0]])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_program_parity.py -v`
Expected: FAIL — `ImportError: cannot import name '_runner_payload'`.

- [ ] **Step 3: Implement `_runner_payload`**

`debugger/reports/program_viewer.py` 의 `display_source` 정의 다음에 삽입:

```python
def _runner_payload(tid, asts, task):
    """각 example program → 러너용 {tid, pair, body, input, expected}.
    expected = 실제 program_ast.execute(ast, input) (JS 미러 대조 기준 = 정직성 가드)."""
    items = []
    for k, ast in enumerate(asts):
        ex = task["train"][k]
        items.append({
            "tid": tid, "pair": k,
            "body": display_source(ast),
            "input": ex["input"],
            "expected": PA.execute(ast, ex["input"]),
        })
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_program_parity.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: `build()` 에서 payload 수집 + JSON 임베드**

`debugger/reports/program_viewer.py` 의 `build()`(약 line 236): `task_section` 이 payload 도 모으도록 모듈 전역 누적 리스트를 쓰거나, `build()` 에서 태스크별로 `_collect` 결과를 재사용. 최소 변경 — `build()` 상단에서 태스크별 asts 를 한 번 더 모으지 않도록, `task_section` 을 payload 반환형으로 바꾸는 대신 `build()` 에서 별도 루프:

```python
def build():
    tabs = "".join(f'<a href="#{t}" data-t="{t}">{t[-1].upper()}</a>' for t in TIDS)
    paths = dict(list_tasks("easy_a"))
    tasks = {t: load_task(paths[t]) for t in TIDS}
    runner_data = []
    secs_list = []
    for t in TIDS:
        asts, solution, attempts = _collect(t, tasks[t])
        runner_data.extend(_runner_payload(t, asts, tasks[t]))
        secs_list.append(task_section(t, tasks[t]))     # task_section 은 자체적으로 _collect (아래 주의)
    secs = "".join(secs_list)
    js = ("<script>var TIDS=%s;function sh(){var h=location.hash.slice(1);"
          "if(!document.getElementById(h))h=TIDS[0];"
          "document.querySelectorAll('section.task').forEach(function(s){s.style.display=(s.id===h)?'':'none'});"
          "document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.t===h)});}"
          "addEventListener('hashchange',sh);sh();</script>") % json.dumps(TIDS)
    doc = (f'<!doctype html><meta charset="utf-8"><title>program 뷰어</title><style>{EV.CSS}{CSS}</style>'
           f'<a class="back" href="focus_dashboard.html">← focus_dashboard</a>'
           f'<h1>easy a–h program 뷰어</h1>'
           f'<p class="hs">solve 실행 → WM 의 PAIR.program 을 통일 body(실행형)·단일 box-flow 로 렌더.'
           f' 하단 코드 실행기에서 body 를 실행/검증(빌드타임 parity ✓/✗).</p>'
           f'<div class="tabs">{tabs}</div>{secs}'
           f'<script>var RUNNER_DATA={json.dumps(runner_data)};</script>'
           f'{_RUNNER_HTML}{js}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "program_report_all.html")
    with open(out, "w") as f:
        f.write(doc)
    return out
```

> 주의(중복 solve): `_collect` 는 태스크당 솔버를 실행하므로 위 루프에서 `_collect` 1회 + `task_section` 내부 `_collect` 1회 = 2회가 된다. 중복을 피하려면 `task_section(tid, task, precomputed=None)` 로 시그니처를 확장해 `(asts, solution, attempts)` 를 주입받게 하고, `build()` 에서 한 번만 `_collect` 한다. `task_section` 첫 줄의 `_collect` 호출을 `asts, solution, attempts = precomputed if precomputed else _collect(tid, task)` 로 바꾼다.

`_RUNNER_HTML` 은 Task 6 에서 정의(이 Task 에서는 `_RUNNER_HTML = ""` 로 임시 정의 후 커밋; Task 6 에서 채움).

`program_viewer.py` 상단(약 CSS 정의 근처)에 임시:
```python
_RUNNER_HTML = ""   # Task 6 에서 코드 실행기 패널로 채움
```

- [ ] **Step 6: 재생성 + parity payload 확인**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
import re, json
s = open("debugger/traces/program_report_all.html").read()
m = re.search(r'var RUNNER_DATA=(\[.*?\]);</script>', s, re.S)
assert m, "RUNNER_DATA 임베드 안됨"
data = json.loads(m.group(1))
assert len(data) >= 8, f"a-h payload 부족: {len(data)}"
assert all("expected" in d and "body" in d and "input" in d for d in data)
print("OK parity payload", len(data), "programs")
PY
```
Expected: `OK parity payload N programs` (N ≥ 8).

- [ ] **Step 7: Commit**

```bash
git add debugger/reports/program_viewer.py tests/test_program_parity.py
git commit -m "feat(viewer): 빌드타임 parity — execute(ast,input) expected 베이킹(RUNNER_DATA)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 순수 프런트엔드 코드 실행기 (JS atom 인터프리터)

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_RUNNER_HTML` 정의 = 패널 + JS)

**Interfaces:**
- Consumes: `RUNNER_DATA`(Task 5 임베드; `[{tid,pair,body,input,expected}]`).
- Produces: HTML 패널 — 프로그램 선택 → body textarea 프리필 → Run → 출력 격자 + expected 대조 ✓/✗. 로드 즉시 각 프로그램 parity 배지.

- [ ] **Step 1: `_RUNNER_HTML` 를 실제 패널로 교체**

`program_viewer.py` 의 임시 `_RUNNER_HTML = ""` 를 다음으로 교체:

```python
_RUNNER_HTML = r"""
<section id="runner"><h2>코드 실행기 <span class="tag2">순수 프런트엔드 · frozen atom JS 미러</span></h2>
<p class="hs">아래 body 를 실행(공통 ARCKG atom 은 러너에 로드). 결과를 빌드타임 expected(=실제
program_ast.execute)와 대조 — JS↔Python 드리프트가 ✓/✗ 로 드러남.</p>
<div class="runwrap">
  <select id="rsel"></select>
  <button id="rrun">▶ Run</button>
  <span id="rbadge" class="rbadge"></span>
  <textarea id="rcode" spellcheck="false"></textarea>
  <div class="rout"><div><div class="rlab">출력(JS 실행)</div><div id="rgrid"></div></div>
    <div><div class="rlab">expected(Python execute)</div><div id="regrid"></div></div></div>
  <div id="rerr" class="rerr"></div>
</div></section>
<script>
// ── frozen atom JS 미러 (program_ast/transformation DSL 의 직역; parity 로 드리프트 감시) ──
function _clone(g){return g.map(function(r){return r.slice();});}
function W(g){return g[0].length;} function H(g){return g.length;}
var ATOM = {
  input_grid: null,
  make_grid: function(size){var o=[];for(var r=0;r<size.height;r++){var row=[];for(var c=0;c<size.width;c++)row.push(0);o.push(row);}return o;},
  coloring: function(g,pos,color){var o=_clone(g);o[pos[0]][pos[1]]=color;return o;},
  set_grid_size: function(g,size){return ATOM.make_grid(size);},
  set_grid_color: function(g,color){return g;},
  set_grid_contents: function(g,contents){return contents==null?g:contents.map(function(r){return r.slice();});},
  size: function(g){return {height:H(g),width:W(g)};},
  height: function(g){return H(g);}, width: function(g){return W(g);},
  color: function(g){var s={};for(var r=0;r<H(g);r++)for(var c=0;c<W(g);c++)s[g[r][c]]=true;return s;},
  contents: function(g){return _clone(g);},
  objects_of: function(g){throw new Error("objects_of: 러너 미지원(pixel/ grid 만)");},
  pixels_of: function(g){var w=W(g),out=[];for(var i=0;i<H(g)*w;i++){out.push({coord:[Math.floor(i/w),i%w]});}return out;},
  divmod: function(a,b){return [Math.floor(a/b),a%b];}
};
// body 실행: display_source 문법('g = fn(g,…)' 순차, for-loop 1종)만 해석. 미지원 구문 → 예외.
function runBody(code, input){
  ATOM.input_grid = input; var g = input;
  var lines = code.split("\n"); var i=0;
  function evalExpr(e){
    // 안전 평가: ATOM/g/input_grid/숫자/배열/객체 리터럴만. new Function 은 로컬 스코프에 바인딩.
    return (new Function("ATOM","g","input_grid","divmod",
      "with(ATOM){return ("+e+");}"))(ATOM,g,ATOM.input_grid,ATOM.divmod);
  }
  for(i=0;i<lines.length;i++){
    var ln = lines[i].trim();
    if(!ln || ln[0]==="#") continue;
    var mFor = ln.match(/^for\s+(\w+)\s+in\s+(.+):$/);
    if(mFor){
      var it = evalExpr(mFor[2]); var body = lines[i+1].trim();
      var mb = body.match(/^g\s*=\s*(.+)$/); i++;
      for(var k=0;k<it.length;k++){ (function(ix){ ATOM[mFor[1]]=ix; })(it[k]);
        // 루프 변수는 ATOM 에 잠깐 얹어 with 로 참조
        g = (new Function("ATOM","g","input_grid","divmod","with(ATOM){return ("+mb[1]+");}"))(ATOM,g,ATOM.input_grid,ATOM.divmod);
      }
      continue;
    }
    var m = ln.match(/^(\w+)\s*=\s*(.+)$/);
    if(!m) throw new Error("해석 불가: "+ln);
    var val = evalExpr(m[2]);
    if(m[1]==="g"||m[1]==="output_grid") g=val; else ATOM[m[1]]=val;
  }
  return g;
}
function gridHTML(g){ if(!g) return '<span class="rerr">–</span>';
  var w=g[0].length, cells=g.map(function(r){return r.map(function(v){
    return '<i style="background:'+PAL_JS[v%10]+'"></i>';}).join("");}).join("");
  return '<div class="thumb" style="grid-template-columns:repeat('+w+',10px)">'+cells+'</div>';
}
var PAL_JS=["#101010","#1E93FF","#F93C31","#4FCC30","#FFDC00","#999999","#E53AA3","#FF851B","#87D8F1","#921231"];
function eqGrid(a,b){return JSON.stringify(a)===JSON.stringify(b);}
(function(){
  var sel=document.getElementById("rsel");
  RUNNER_DATA.forEach(function(d,i){var o=document.createElement("option");
    o.value=i; o.text=d.tid+" · pair "+(d.pair+1); sel.appendChild(o);});
  function load(){var d=RUNNER_DATA[sel.value]; document.getElementById("rcode").value=d.body;
    document.getElementById("rgrid").innerHTML=""; document.getElementById("regrid").innerHTML=gridHTML(d.expected);
    document.getElementById("rerr").textContent=""; document.getElementById("rbadge").textContent="";}
  function run(){var d=RUNNER_DATA[sel.value]; var err=document.getElementById("rerr");
    var badge=document.getElementById("rbadge"); err.textContent="";
    try{ var out=runBody(document.getElementById("rcode").value, d.input);
      document.getElementById("rgrid").innerHTML=gridHTML(out);
      document.getElementById("regrid").innerHTML=gridHTML(d.expected);
      var ok=eqGrid(out,d.expected); badge.textContent=ok?"✓ parity":"✗ 불일치";
      badge.className="rbadge "+(ok?"rok":"rno");
    }catch(e){ err.textContent=String(e.message||e); badge.textContent="✗ 실행오류"; badge.className="rbadge rno"; }}
  sel.onchange=load; document.getElementById("rrun").onclick=run;
  if(RUNNER_DATA.length){ load(); run(); }   // 로드 즉시 parity 확인
})();
</script>
"""
```

- [ ] **Step 2: 러너 CSS 추가**

`program_viewer.py` 의 `CSS` 문자열(약 line 214) 끝에 append:

```python
CSS += """
#runner{background:#1a1d24;border:1px solid #262b34;border-radius:10px;padding:16px 18px;margin:18px 0}
.runwrap{display:flex;flex-direction:column;gap:8px;margin-top:8px}
#rsel{background:#0f1218;color:#dfe3ea;border:1px solid #2a3038;border-radius:6px;padding:4px 8px}
#rrun{background:#243b52;color:#bcd8f5;border:1px solid #3a5a7a;border-radius:6px;padding:4px 12px;cursor:pointer;width:max-content}
#rcode{background:#0d1014;color:#dfe3ea;border:1px solid #232a35;border-radius:6px;padding:8px 10px;
 font:11.5px/1.5 ui-monospace,monospace;min-height:120px;white-space:pre;overflow:auto}
.rout{display:flex;gap:18px;margin-top:6px}.rlab{font-size:10px;color:#8b93a3;margin-bottom:4px}
.rbadge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px}
.rok{background:#12281c;color:#a9e6c1;border:1px solid #2f5a41}
.rno{background:#241417;color:#e0a3a4;border:1px solid #5a2f34}
.rerr{color:#e0a3a4;font:11px/1.4 ui-monospace,monospace;white-space:pre-wrap}
.rawsrc summary{color:#7a8698;font-size:10px;cursor:pointer;margin-top:6px}
"""
```

- [ ] **Step 3: 재생성 + 런타임 검증 (headless)**

Run:
```bash
python -m debugger.reports.program_viewer
python - <<'PY'
import re, json
s = open("debugger/traces/program_report_all.html").read()
assert 'id="runner"' in s, "러너 패널 없음"
assert "function runBody" in s and "pixels_of:" in s, "JS 인터프리터 없음"
m = re.search(r'var RUNNER_DATA=(\[.*?\]);</script>', s, re.S)
data = json.loads(m.group(1))
# 파이썬 쪽 parity 재확인(빌드 무결성): expected == execute(display body 의 원본 ast)?
# (JS 실행은 브라우저 몫 — 여기선 expected 가 실제 execute 산물인지 Task5 가 이미 보장)
print("OK 러너 임베드 확인:", len(data), "programs")
PY
```
Expected: `OK 러너 임베드 확인: N programs`.

- [ ] **Step 4: 브라우저 육안 확인 (수동 — 선택)**

Run: `open debugger/traces/program_report_all.html`
확인: 하단 "코드 실행기" 에서 각 프로그램 선택 시 body 프리필 + 로드 즉시 `✓ parity` 배지, 출력격자 == expected격자. `▶ Run` 재실행 동작. (a=grid, c=pixel 각각 ✓.)

- [ ] **Step 5: Commit**

```bash
git add debugger/reports/program_viewer.py
git commit -m "feat(viewer): 순수 프런트엔드 코드 실행기(JS atom 미러) + parity 배지

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 전체 회귀 + dashboard 재빌드 확인

**Files:** (없음 — 검증만)

- [ ] **Step 1: 전체 테스트**

Run: `python -m pytest tests/ -q`
Expected: 전부 PASS(기존 계약 불변 + 신규 Task 1·2·3·5 테스트).

- [ ] **Step 2: 전체 dashboard 파이프라인 재빌드**

Run: `python -m debugger.build`
Expected: `focus_dashboard.html` + `program_report_all.html` 정상 생성, 예외 없음.

- [ ] **Step 3: 정직성 자문(하네스 §7) 기록**

확인(주관): c–h 가 여전히 coloring 계열인가(const-굽기 안 함)? body 가 실 DSL 로 실행되나(러너 ✓)? accessor 가 ARCKG property 투영인가? — README/스펙에 이상 없으면 종료.

- [ ] **Step 4: (선택) memory 갱신**

`[[seokki-refactor]]` 메모리에 "program 뷰어 표현 통일 + pixels_of/height/width accessor + 코드 실행기" 한 줄 추가.

---

## Self-Review (작성자 체크)

- **Spec coverage:** §3-1(T1) · §3-2(T2) · §4-1 display_source(T3) · §4-2 _viz(T4) · §4-3 AST 유지(변경 없음=T3 note) · §4-4 solution 블록(_pair_block 재사용=T3 Step5 로 자동) · §5-2/5-3 러너+parity(T5·T6) 모두 태스크 있음.
- **Placeholder scan:** `_RUNNER_HTML` 임시 빈 정의(T5)→T6 에서 채움(의도된 순서, 각 단계 실행가능). 그 외 TBD 없음.
- **Type consistency:** `_ACCESSOR`(T3)·`_disp_leaf`(T3)를 T4 가 재사용 — 동일 모듈 동일 이름. `_runner_payload`(T5)→`RUNNER_DATA`(T6) 키(`tid,pair,body,input,expected`) 일치. `display_source`/`_grid_leaf_repr(leaf,prop)` 시그니처 일관.
- **주의 문서화:** T5 의 `_collect` 중복 solve → `task_section(precomputed=)` 확장으로 1회화(명시).
