# arc-dsl 흡수 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** michaelhodel/arc-dsl 의 GRID transform 어휘를 `SPECS` 에 흡수하고, `compare` 의 COMM/DIFF 가 effect 일치로 DSL 을 제안(propose)→arg 를 즉시결정/탐색으로 채우고→train 으로 검증하는 경로를 만든다.

**Architecture:** transform/select/relation 프리미티브를 새 모듈에 vendoring(ARCKG 중복은 재구현 금지·기존 소스 재사용). `derive_required_effect` 가 COMM/DIFF→verb 집합을 내고, `effect.matches` 로 후보 DSL fan-out, `resolve_and_verify` 가 arg 를 ①relation ②selection ③표현식탐색 으로 채워 train 검증. 시도·기각은 `hypothesis` WME + dashboard 로 잔존. 새 SOAR operator `transform_search` 가 `synthesize` 의 contents-DESCEND 공백에서 발화.

**Tech Stack:** Python 3, `unittest`(`python -m unittest tests.X -v`), 자체 SOAR 커널(`soar/`), ARCKG(`arbor/perception/arckg/`).

## Global Constraints

- **§1-1 finder 금지**: propose 는 하드매핑이 아니라 effect 일치. required-effect 도출은 generic 관찰만(문제특이 값·1:1 매핑 금지). 한 관찰이 후보 *집합*을 낸다.
- **§1-3/§4-1 수식은 탐색**: 좌표/offset 은 후보식 생성→train 적용→대조→기각/생존. 손계산 금지.
- **§1-5 시도·기각 잔존**: 모든 후보(생존+기각)를 `hypothesis` WME 로 물질화.
- **§2-1 ARCKG 우선**: property/object 정보는 ARCKG 노드 또는 그 소스(`arbor/perception/arckg/hodel.py:find_all_objects`, `_mostcolor`)를 재사용. 재구현 금지 = WRAP.
- **grid 표현**: ARBOR 내부는 `list[list[int]]` (arc-dsl 의 `tuple[tuple]` 아님). vendored body 는 list 입출력.
- **object cell 표현**: `find_all_objects(raw)` 원소 = `{"obj": frozenset((color,(row,col))), "pos": (rmin,cmin), ...}`.
- **effect 양식**: `effect(verb, kind="grid")`. `matches(required, provided)` = kind 일치 & (verb 일치 or ANY).
- **verb 버킷(고정)**: reflect=hmirror/vmirror/dmirror/cmirror · rotate=rot90/rot180/rot270 · recolor=replace/switch/recolor · translate=move/shift · crop=crop/subgrid/{top,bottom,left,right}half/trim · upscale=upscale/hupscale/vupscale · downscale=downscale/compress · create=canvas · concat=hconcat/vconcat · fill=fill/paint/underfill/underpaint/cover.
- **스코프(이번 플랜)**: 수직 슬라이스 = param-free(rot/mirror) + relation-arg(replace/switch) + searched-arg(move/shift). 나머지 transform·relation vocab·property WRAP 전량은 Task 8(batch) + 후속 스펙.

---

### Task 1: param-free transform 원자 vendoring + 등록

기존 `transformation/__init__.py` 는 "frozen 원자 2개(make_grid/coloring)" 시드다 — 건드리지 말고 **새 모듈** `transformation/hodel_transforms.py` 에 vendoring 후 패키지에서 import.

**Files:**
- Create: `procedural_memory/dsl/transformation/hodel_transforms.py`
- Modify: `procedural_memory/dsl/transformation/__init__.py` (끝에 import 1줄)
- Test: `tests/test_hodel_transforms.py`

**Interfaces:**
- Produces: `SPECS` 에 `rot90,rot180,rot270,hmirror,vmirror,dmirror,cmirror,compress,trim,tophalf,bottomhalf,lefthalf,righthalf` 등록. 각 body: `fn(grid: list[list[int]]) -> list[list[int]]`. effect: rot*→`effect("rotate","grid")`, {h,v,d,c}mirror→`effect("reflect","grid")`, compress/trim→`effect("downscale","grid")`, *half→`effect("crop","grid")`.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_hodel_transforms.py`

```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestParamFree(unittest.TestCase):
    def test_registered_with_effect(self):
        import procedural_memory.dsl as d
        for name, verb in [("rot90","rotate"),("hmirror","reflect"),("vmirror","reflect"),
                           ("rot180","rotate"),("rot270","rotate"),("dmirror","reflect"),
                           ("cmirror","reflect"),("trim","downscale"),("tophalf","crop")]:
            self.assertIn(name, d.SPECS)
            self.assertEqual(d.SPECS[name]["kind"], "transformation")
            self.assertEqual(d.SPECS[name]["effect"], {"verb": verb, "kind": "grid"})

    def test_bodies(self):
        from procedural_memory.dsl.registry import body
        g = [[1,2],[3,4]]
        self.assertEqual(body("rot90")(g), [[3,1],[4,2]])
        self.assertEqual(body("rot180")(g), [[4,3],[2,1]])
        self.assertEqual(body("hmirror")(g), [[3,4],[1,2]])
        self.assertEqual(body("vmirror")(g), [[2,1],[4,3]])
        self.assertEqual(body("dmirror")(g), [[1,3],[2,4]])
        self.assertEqual(body("tophalf")([[1,1],[2,2],[3,3]]), [[1,1]])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_hodel_transforms -v` · Expected: FAIL (`rot90` not in SPECS).

- [ ] **Step 3: 구현** — `procedural_memory/dsl/transformation/hodel_transforms.py`

```python
# -*- coding: utf-8 -*-
"""arc-dsl(michaelhodel) GRID transform 어휘 vendoring — list[list] 표현.
frozen 원자(make_grid/coloring)와 분리된 확장 어휘. propose 는 effect 일치로 걸린다."""
from procedural_memory.dsl.registry import dsl
from procedural_memory.dsl.effect import effect


def _T(g): return [list(row) for row in zip(*g)]           # transpose


@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot90(grid):
    return [list(r) for r in zip(*grid[::-1])]

@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot180(grid):
    return [list(r[::-1]) for r in grid[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot270(grid):
    return [list(r) for r in list(zip(*grid))[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def hmirror(grid):
    return [list(r) for r in grid[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def vmirror(grid):
    return [list(r[::-1]) for r in grid]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def dmirror(grid):
    return [list(r) for r in zip(*grid)]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def cmirror(grid):
    return [list(r) for r in zip(*[row[::-1] for row in grid[::-1]])]

@dsl("transformation", ["grid"], "grid", effect=effect("downscale", "grid"))
def compress(grid):
    ri = {i for i, r in enumerate(grid) if len(set(r)) == 1}
    ci = {j for j in range(len(grid[0])) if len({grid[i][j] for i in range(len(grid))}) == 1}
    return [[v for j, v in enumerate(r) if j not in ci]
            for i, r in enumerate(grid) if i not in ri] or [[]]

@dsl("transformation", ["grid"], "grid", effect=effect("downscale", "grid"))
def trim(grid):
    return [list(r[1:-1]) for r in grid[1:-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def tophalf(grid):
    return [list(r) for r in grid[:len(grid) // 2]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def bottomhalf(grid):
    return [list(r) for r in grid[len(grid) // 2 + len(grid) % 2:]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def lefthalf(grid):
    return [list(r[:len(grid[0]) // 2]) for r in grid]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def righthalf(grid):
    return [list(r[len(grid[0]) // 2 + len(grid[0]) % 2:]) for r in grid]
```

- [ ] **Step 4: import 배선** — `procedural_memory/dsl/transformation/__init__.py` 끝에 추가:

```python
from procedural_memory.dsl.transformation import hodel_transforms  # noqa: F401,E402  (@dsl 발화)
```

- [ ] **Step 5: 통과 확인** — Run: `python -m unittest tests.test_hodel_transforms -v` · Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add procedural_memory/dsl/transformation/hodel_transforms.py procedural_memory/dsl/transformation/__init__.py tests/test_hodel_transforms.py
git commit -m "feat(#dsl) param-free transform 원자 vendoring(rot/mirror/compress/trim/half) + effect 등록"
```

---

### Task 2: relation-arg transform (replace/switch) vendoring

**Files:**
- Modify: `procedural_memory/dsl/transformation/hodel_transforms.py`
- Test: `tests/test_hodel_transforms.py` (테스트 클래스 추가)

**Interfaces:**
- Produces: `SPECS["replace"]` body `replace(grid, replacee, replacer) -> grid`, `SPECS["switch"]` body `switch(grid, a, b) -> grid`. 둘 다 `effect("recolor","grid")`.

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_hodel_transforms.py` 에 클래스 추가:

```python
class TestRecolor(unittest.TestCase):
    def test_registered(self):
        import procedural_memory.dsl as d
        for n in ("replace", "switch"):
            self.assertEqual(d.SPECS[n]["effect"], {"verb": "recolor", "kind": "grid"})

    def test_bodies(self):
        from procedural_memory.dsl.registry import body
        self.assertEqual(body("replace")([[1,2],[2,1]], 2, 5), [[1,5],[5,1]])
        self.assertEqual(body("switch")([[1,2],[2,1]], 1, 2), [[2,1],[1,2]])
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_hodel_transforms.TestRecolor -v` · Expected: FAIL (`replace` KeyError).

- [ ] **Step 3: 구현** — `hodel_transforms.py` 에 추가:

```python
@dsl("transformation", ["grid", "color", "color"], "grid", effect=effect("recolor", "grid"))
def replace(grid, replacee, replacer):
    return [[replacer if v == replacee else v for v in r] for r in grid]

@dsl("transformation", ["grid", "color", "color"], "grid", effect=effect("recolor", "grid"))
def switch(grid, a, b):
    return [[a if v == b else (b if v == a else v) for v in r] for r in grid]
```

- [ ] **Step 4: 통과 확인** — Run: `python -m unittest tests.test_hodel_transforms.TestRecolor -v` · Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add procedural_memory/dsl/transformation/hodel_transforms.py tests/test_hodel_transforms.py
git commit -m "feat(#dsl) recolor transform vendoring(replace/switch) + recolor effect"
```

---

### Task 3: searched-arg transform (move/shift) + raw-grid object 재사용

`move` 는 object arg(②selection)+offset arg(③search)를 함께 요구한다. object 는 ARCKG 와 동일 소스 `find_all_objects` 를 재사용(재구현 금지).

**Files:**
- Modify: `procedural_memory/dsl/transformation/hodel_transforms.py`
- Test: `tests/test_hodel_transforms.py`

**Interfaces:**
- Produces: `SPECS["shift"]` body `shift(grid, obj_cells, offset) -> grid`, `SPECS["move"]` body `move(grid, obj_cells, offset) -> grid`. 둘 다 `effect("translate","grid")`. `obj_cells` = `frozenset((color,(r,c)))`, `offset` = `(di,dj)`. `move` = cover(bg)+paint(shift).

- [ ] **Step 1: 실패 테스트 추가**

```python
class TestTranslate(unittest.TestCase):
    def test_registered(self):
        import procedural_memory.dsl as d
        for n in ("move", "shift"):
            self.assertEqual(d.SPECS[n]["effect"], {"verb": "translate", "kind": "grid"})

    def test_move_covers_and_paints(self):
        from procedural_memory.dsl.registry import body
        g = [[5,0,0],[0,0,0],[0,0,0]]           # bg=0, obj={(5,(0,0))}
        obj = frozenset({(5, (0, 0))})
        self.assertEqual(body("move")(g, obj, (2, 2)),
                         [[0,0,0],[0,0,0],[0,0,5]])
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_hodel_transforms.TestTranslate -v` · Expected: FAIL.

- [ ] **Step 3: 구현** — `hodel_transforms.py` 에 추가:

```python
from collections import Counter

def _bg(grid):
    return Counter(v for r in grid for v in r).most_common(1)[0][0]

def _paint(grid, obj_cells):
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for v, (i, j) in obj_cells:
        if 0 <= i < H and 0 <= j < W:
            out[i][j] = v
    return out

@dsl("transformation", ["grid", "object", "position"], "grid", effect=effect("translate", "grid"))
def shift(grid, obj_cells, offset):
    di, dj = offset
    return _paint(grid, frozenset((v, (i + di, j + dj)) for v, (i, j) in obj_cells))

@dsl("transformation", ["grid", "object", "position"], "grid", effect=effect("translate", "grid"))
def move(grid, obj_cells, offset):
    bg = _bg(grid)
    covered = _paint(grid, frozenset((bg, (i, j)) for _, (i, j) in obj_cells))
    di, dj = offset
    return _paint(covered, frozenset((v, (i + di, j + dj)) for v, (i, j) in obj_cells))
```

- [ ] **Step 4: 통과 확인** — Run: `python -m unittest tests.test_hodel_transforms.TestTranslate -v` · Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add procedural_memory/dsl/transformation/hodel_transforms.py tests/test_hodel_transforms.py
git commit -m "feat(#dsl) translate transform vendoring(move/shift) — obj=find_all_objects 재사용"
```

---

### Task 4: required-effect 도출 (COMM/DIFF → verb 집합)

**Files:**
- Create: `arbor/reasoning/transform_search.py`
- Test: `tests/test_transform_search.py`

**Interfaces:**
- Produces: `derive_required_effect(train: list[dict]) -> list[dict]`. `train` 원소 = `{"input": grid, "output": grid}`. 반환 = effect dict 리스트(`{"verb","kind":"grid"}`), generic 관찰 기반. 후속 Task 6 이 소비.

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_transform_search.py`

```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning.transform_search import derive_required_effect

def verbs(train):
    return {e["verb"] for e in derive_required_effect(train)}

class TestRequiredEffect(unittest.TestCase):
    def test_size_preserved_pixels_preserved(self):
        # 회전/반사/이동 후보 — 픽셀 다중집합 보존, 팔레트 보존, 격자는 다름
        t = [{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]}]   # rot90
        self.assertTrue({"rotate","reflect","translate"} <= verbs(t))

    def test_palette_diff_recolor(self):
        t = [{"input": [[1,1],[0,0]], "output": [[2,2],[0,0]]}]   # 1→2
        self.assertIn("recolor", verbs(t))

    def test_dims_swapped(self):
        t = [{"input": [[1,2,3]], "output": [[1],[2],[3]]}]       # (1,3)->(3,1)
        self.assertTrue({"rotate","reflect"} <= verbs(t))

    def test_upscale(self):
        t = [{"input": [[1]], "output": [[1,1],[1,1]]}]           # x2
        self.assertIn("upscale", verbs(t))
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_transform_search -v` · Expected: FAIL (module 없음).

- [ ] **Step 3: 구현** — `arbor/reasoning/transform_search.py`

```python
# -*- coding: utf-8 -*-
"""transform_search — COMM/DIFF 기반 effect 도출 + DSL 후보 fan-out + arg resolve/verify.
DSL 은 finder 가 아니라 search 가 열거하는 어휘. propose=effect 일치, arg=즉시|탐색, 검증=train."""
from collections import Counter
from procedural_memory.dsl.effect import effect, matches


def _dims(g): return (len(g), len(g[0]))
def _palette(g): return frozenset(v for r in g for v in r)
def _multiset(g): return Counter(v for r in g for v in r)


def derive_required_effect(train):
    """generic 관찰만으로 required verb 집합을 낸다(문제특이 값·1:1 매핑 금지). 한 관찰이 후보 *집합*을 냄."""
    verbs = set()
    d = [(_dims(e["input"]), _dims(e["output"])) for e in train]
    same_dims = all(i == o for i, o in d)
    swapped = all((o[0], o[1]) == (i[1], i[0]) for i, o in d)
    changed = any(e["input"] != e["output"] for e in train)
    pal_keep = all(_palette(e["input"]) == _palette(e["output"]) for e in train)
    ms_keep = all(_multiset(e["input"]) == _multiset(e["output"]) for e in train)

    if same_dims and changed:
        if ms_keep:
            verbs |= {"rotate", "reflect", "translate"}   # 픽셀 보존 → 재배치류
        if not pal_keep:
            verbs.add("recolor")                          # 팔레트 변화 → 재채색
    if swapped and not same_dims:
        verbs |= {"rotate", "reflect"}
    # 확대/축소 (정수배)
    def ratio(i, o, ax):
        a, b = i[ax], o[ax]
        return ("up", b // a) if b >= a and a and b % a == 0 else \
               ("down", a // b) if a and b and a % b == 0 else (None, None)
    if all(ratio(i, o, 0)[0] == "up" and ratio(i, o, 1)[0] == "up" for i, o in d) and not same_dims:
        verbs.add("upscale")
    if all(ratio(i, o, 0)[0] == "down" and ratio(i, o, 1)[0] == "down" for i, o in d) and not same_dims:
        verbs |= {"downscale", "crop"}
    return [effect(v, "grid") for v in sorted(verbs)]
```

- [ ] **Step 4: 통과 확인** — Run: `python -m unittest tests.test_transform_search -v` · Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add arbor/reasoning/transform_search.py tests/test_transform_search.py
git commit -m "feat(#dsl) required-effect 도출 — COMM/DIFF generic 관찰→verb 집합(§3-2)"
```

---

### Task 5: candidate fan-out + arg resolve + verify 엔진

**Files:**
- Modify: `arbor/reasoning/transform_search.py`
- Test: `tests/test_transform_search.py`

**Interfaces:**
- Consumes: `derive_required_effect` (Task 4), `SPECS`/`body` (dsl), `matches` (effect), `find_all_objects` (hodel).
- Produces:
  - `candidate_transforms(required: list[dict]) -> list[str]` — kind=transformation 이고 effect 가 required 중 하나와 matches 되는 DSL 이름들.
  - `transform_search(train: list[dict]) -> dict` — `{"required":[verb...], "candidates":[name...], "hypotheses":[{rule,args_src,verdict,why}], "survivor": {rule,plan}|None}`. hypotheses 는 시도·기각 전부(§1-5). survivor = train 전체 통과한 첫 후보.

- [ ] **Step 1: 실패 테스트 추가**

```python
from arbor.reasoning.transform_search import candidate_transforms, transform_search

class TestSearchEngine(unittest.TestCase):
    def test_fanout_by_effect(self):
        req = derive_required_effect([{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]}])
        cands = candidate_transforms(req)
        self.assertIn("rot90", cands)      # rotate
        self.assertIn("hmirror", cands)    # reflect
        self.assertNotIn("make_grid", cands)

    def test_solves_rot90(self):
        t = [{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]},
             {"input": [[5,6],[7,8]], "output": [[7,5],[8,6]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "rot90")
        self.assertTrue(any(h["verdict"] == "reject" for h in r["hypotheses"]))  # 기각 잔존

    def test_solves_replace(self):
        t = [{"input": [[1,1],[0,0]], "output": [[2,2],[0,0]]},
             {"input": [[1,0],[1,0]], "output": [[2,0],[2,0]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "replace")
        self.assertEqual(r["survivor"]["plan"]["args"], [1, 2])

    def test_solves_move_by_search(self):
        # 단일 obj 를 (H-1,W-1) 코너로 — offset 은 탐색으로 도출
        t = [{"input": [[5,0,0],[0,0,0],[0,0,0]], "output": [[0,0,0],[0,0,0],[0,0,5]]},
             {"input": [[0,0],[3,0]], "output": [[0,0],[0,3]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "move")
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_transform_search.TestSearchEngine -v` · Expected: FAIL.

- [ ] **Step 3: 구현** — `transform_search.py` 에 추가:

```python
import procedural_memory.dsl as _dsl            # SPECS 채우는 import 부작용
from procedural_memory.dsl.registry import SPECS, body
from arbor.perception.arckg.hodel import find_all_objects


def candidate_transforms(required):
    return [n for n, s in SPECS.items()
            if s["kind"] == "transformation" and s["effect"]
            and any(matches(r, s["effect"]) for r in required)]


def _recolor_map(train):
    """전 train pair 셀단위 입력색→출력색 전역맵(크기 COMM 만). 비함수면 None. ①relation 즉시 arg."""
    if any(_dims(e["input"]) != _dims(e["output"]) for e in train):
        return None
    mp = {}
    for e in train:
        i, o = e["input"], e["output"]
        for r in range(len(i)):
            for c in range(len(i[0])):
                a, b = i[r][c], o[r][c]
                if a in mp and mp[a] != b:
                    return None
                mp[a] = b
    return mp


def _offset_formulas():
    """offset(di,dj) 후보식 — {0,±1, H-1,W-1, -uppermost,-leftmost, H-h,W-w} 조합(§4-1). 손계산 금지."""
    comp = {
        "0": lambda H, W, oh, ow, u, l: 0,
        "1": lambda H, W, oh, ow, u, l: 1,
        "-1": lambda H, W, oh, ow, u, l: -1,
        "H-1-u": lambda H, W, oh, ow, u, l: H - 1 - u,      # 하단 코너로
        "W-1-l": lambda H, W, oh, ow, u, l: W - 1 - l,      # 우측 코너로
        "-u": lambda H, W, oh, ow, u, l: -u,               # 상단
        "-l": lambda H, W, oh, ow, u, l: -l,               # 좌측
    }
    return comp


def _apply_translate(name, grid, sel, di_f, dj_f):
    """sel(=선택규칙), offset 식을 grid 에 적용. 실패(obj 없음/여럿)면 None."""
    objs = [d["obj"] for d in find_all_objects(grid)]
    objs = [o for o in objs if len(o) > 0]
    if sel == "single" and len(objs) != 1:
        return None
    if not objs:
        return None
    obj = max(objs, key=len) if sel == "largest" else objs[0]
    rows = [i for _, (i, _) in obj]; cols = [j for _, (_, j) in obj]
    u, l = min(rows), min(cols)
    oh, ow = max(rows) - u + 1, max(cols) - l + 1
    H, W = len(grid), len(grid[0])
    di, dj = di_f(H, W, oh, ow, u, l), dj_f(H, W, oh, ow, u, l)
    return body(name)(grid, obj, (di, dj))


def _arg_plans(name, train):
    """DSL 이름별 arg 후보 plan 목록 산출. plan={apply: grid->grid|None, args, src}.
    ①relation 즉시(recolor) ②selection ③표현식탐색(translate). param-free 는 인자 없음."""
    verb = SPECS[name]["effect"]["verb"]
    if verb in ("rotate", "reflect", "downscale", "crop"):
        return [{"apply": (lambda g, n=name: body(n)(g)), "args": [], "src": "param-free"}]
    if verb == "recolor":
        mp = _recolor_map(train)
        if not mp:
            return []
        diff = [(a, b) for a, b in mp.items() if a != b]
        plans = []
        if name == "replace" and len(diff) == 1:
            a, b = diff[0]
            plans.append({"apply": (lambda g, a=a, b=b: body("replace")(g, a, b)),
                          "args": [a, b], "src": "relation(color-DIFF)"})
        if name == "switch" and len(diff) == 2 and diff[0] == (diff[1][1], diff[1][0]):
            a, b = diff[0]
            plans.append({"apply": (lambda g, a=a, b=b: body("switch")(g, a, b)),
                          "args": [a, b], "src": "relation(color-DIFF)"})
        return plans
    if verb == "translate":
        comp = _offset_formulas()
        plans = []
        for sel in ("single", "largest"):
            for din, dif in comp.items():
                for djn, djf in comp.items():
                    plans.append({
                        "apply": (lambda g, n=name, s=sel, a=dif, b=djf: _apply_translate(n, g, s, a, b)),
                        "args": [sel, f"di={din}", f"dj={djn}"], "src": "search(offset)"})
        return plans
    return []


def transform_search(train):
    required = derive_required_effect(train)
    cands = candidate_transforms(required)
    hyps, survivor = [], None
    for name in cands:
        plans = _arg_plans(name, train)
        if not plans:
            hyps.append({"rule": name, "args_src": None, "verdict": "reject", "why": "arg 미해결"})
            continue
        for plan in plans:
            try:
                ok = all(plan["apply"](e["input"]) == e["output"] for e in train)
            except Exception:
                ok = False
            hyps.append({"rule": name, "args_src": plan["src"], "args": plan["args"],
                         "verdict": "survive" if ok else "reject"})
            if ok and survivor is None:
                survivor = {"rule": name, "plan": {"args": plan["args"], "src": plan["src"]}}
    return {"required": [e["verb"] for e in required], "candidates": cands,
            "hypotheses": hyps, "survivor": survivor}
```

- [ ] **Step 4: 통과 확인** — Run: `python -m unittest tests.test_transform_search.TestSearchEngine -v` · Expected: PASS (rot90/replace/move survivor, reject 잔존).

- [ ] **Step 5: Commit**

```bash
git add arbor/reasoning/transform_search.py tests/test_transform_search.py
git commit -m "feat(#dsl) transform_search 엔진 — effect fan-out + arg resolve(①②③) + train verify"
```

---

### Task 6: SOAR operator `transform_search` + propose/apply + synthesize 훅

`synthesize` 의 contents `decision=="DESCEND"`(현재 그냥 하강) 지점에서 신 operator 를 발화시킨다.

**Files:**
- Create: `procedural_memory/operators/transform_search.py`
- Create: `procedural_memory/production_rules/transform_search.json`
- Modify: `procedural_memory/operators/__init__.py:17` (OPERATOR_BODIES 에 등록)
- Modify: `procedural_memory/operators/synthesize.py:69-74` (DESCEND 분기에 신호 WME 추가)
- Test: `tests/test_transform_search_op.py`

**Interfaces:**
- Consumes: `transform_search(train)` (Task 5), 커널 `Agent`(`ag.wm.add`, `ag.task["train"]`), loader `PRODUCTIONS`.
- Produces: operator body `_op_transform_search(ag)` — `transform_search` 결과를 `hypothesis` WME 로 물질화하고 survivor 를 `parent` 슬롯에 올림. `production_rules/transform_search.json` propose 조건 = `(<s> ^transform-search-open yes)`.

- [ ] **Step 1: synthesize DESCEND 분기에 신호 추가** — `synthesize.py:69-74` 의 `else:` 블록 끝(`ag.wm.add(gid, "produce", …)` 다음 줄)에 추가:

```python
        if dec["contents"]["note"] == "DESCEND":
            ag.wm.add(parent, "transform-search-open", "yes")   # DSL transform 탐색 진입(Task6)
```

- [ ] **Step 2: 실패 테스트 작성** — `tests/test_transform_search_op.py`

```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTransformSearchOp(unittest.TestCase):
    def test_body_writes_hypotheses_and_survivor(self):
        from procedural_memory.operators.transform_search import _op_transform_search

        class WM:
            def __init__(self): self.t = []
            def add(self, i, a, v): self.t.append((i, a, v))
        class AG:
            def __init__(self):
                self.wm = WM()
                self.stack = [type("S", (), {"id": "s1"})()]
                self.task = {"train": [
                    {"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]},
                    {"input": [[5,6],[7,8]], "output": [[7,5],[8,6]]}]}
        ag = AG()
        # superstate 없으면 parent=None; 테스트용으로 self-parent 처리
        ag.wm.t.append(("s1", "superstate", "root"))
        _op_transform_search(ag)
        hyps = [v for (i, a, v) in ag.wm.t if a == "hypothesis"]
        self.assertTrue(hyps)                                   # 후보 물질화
        surv = [v for (i, a, v) in ag.wm.t if a == "transform-survivor"]
        self.assertTrue(any("rot90" in s for s in surv))

    def test_json_loads_in_productions(self):
        from procedural_memory.loader import PRODUCTIONS
        names = [p.name for p in PRODUCTIONS]
        self.assertIn("propose*transform_search", names)
        self.assertIn("apply*transform_search", names)
```

- [ ] **Step 3: 실패 확인** — Run: `python -m unittest tests.test_transform_search_op -v` · Expected: FAIL.

- [ ] **Step 4: operator body 구현** — `procedural_memory/operators/transform_search.py`

```python
# -*- coding: utf-8 -*-
"""ARBOR operator body: transform_search — synthesize 의 contents-DESCEND 공백에서 DSL transform 탐색.
effect 일치 후보를 열거→arg resolve→train verify. 시도·기각을 hypothesis WME 로 잔존(§1-5)."""
from __future__ import annotations
from arbor.reasoning.transform_search import transform_search


def _op_transform_search(ag):
    s = ag.stack[-1].id
    parent = next((v for (i, a, v) in ag.wm.t if i == s and a == "superstate"), s) \
        if hasattr(ag.wm, "t") else \
        next((v for (i, a, v) in ag.wm if i == s and a == "superstate"), s)
    res = transform_search(ag.task["train"])
    ag.wm.add(s, "required-effect", "/".join(res["required"]) or "(none)")
    ag.wm.add(s, "candidates", ",".join(res["candidates"]) or "(none)")
    for k, h in enumerate(res["hypotheses"], 1):
        hh = f"{s}.T{k}"
        ag.wm.add(s, "hypothesis", hh)
        ag.wm.add(hh, "rule", h["rule"])
        ag.wm.add(hh, "args", str(h.get("args", [])))
        ag.wm.add(hh, "src", str(h.get("args_src")))
        ag.wm.add(hh, "verdict", h["verdict"])
    if res["survivor"]:
        sv = res["survivor"]
        ag.wm.add(parent, "transform-survivor", f"{sv['rule']} {sv['plan']['args']}")
        ag.wm.add(parent, "answer-ready", "yes")
    else:
        ag.wm.add(parent, "transform-verdict", "생존 후보 없음 → 하강")
    ag.wm.add(s, "transform-search-done", "yes")
```

- [ ] **Step 5: propose/apply json** — `procedural_memory/production_rules/transform_search.json` (set_grid_color.json 템플릿, 새 order 30/31):

```json
{
  "operator": "transform_search",
  "doc": "synthesize 의 contents-DESCEND 공백에서 DSL transform 을 effect 일치로 제안·검증. ^transform-search-open 로 발화",
  "propose": [
    {
      "name": "propose*transform_search",
      "order": 30,
      "conditions": [
        {"id": "<s>", "attr": "transform-search-open", "value": "yes", "negated": false},
        {"id": "<s>", "attr": "transform-search-done", "value": "<x>", "negated": true}
      ],
      "actions": [
        {"id": "<s>", "attr": "operator", "value": "<o>", "pref": "+", "referent": null},
        {"id": "<o>", "attr": "name", "value": "transform_search", "pref": "+", "referent": null}
      ]
    }
  ],
  "apply": [
    {
      "name": "apply*transform_search",
      "order": 31,
      "conditions": [
        {"id": "<s>", "attr": "operator", "value": "<o>", "negated": false},
        {"id": "<o>", "attr": "name", "value": "transform_search", "negated": false}
      ],
      "actions": [
        {"id": "<s>", "attr": "transform-search-step", "value": "yes", "pref": "+", "referent": null}
      ]
    }
  ]
}
```

- [ ] **Step 6: OPERATOR_BODIES 배선** — `procedural_memory/operators/__init__.py`: import 추가 + dict 등록:

```python
from procedural_memory.operators.transform_search import _op_transform_search
```

그리고 `OPERATOR_BODIES` dict 에 `"transform_search": _op_transform_search,` 추가.

- [ ] **Step 7: 통과 확인** — Run: `python -m unittest tests.test_transform_search_op -v` · Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add procedural_memory/operators/transform_search.py procedural_memory/production_rules/transform_search.json procedural_memory/operators/__init__.py procedural_memory/operators/synthesize.py tests/test_transform_search_op.py
git commit -m "feat(#dsl) transform_search operator + propose/apply + synthesize DESCEND 훅"
```

---

### Task 7: focus_dashboard transform_search 패널 (§2-5)

**Files:**
- Modify: dashboard 생성부 (`grep -rl "focus_dashboard" debugger arc arbor` 로 위치 확정; 예상 `debugger/build.py` 또는 `arc/fine_trace.py`)
- Test: `tests/test_dashboard_transform_panel.py`

**Interfaces:**
- Consumes: WM 의 `required-effect`, `candidates`, `hypothesis`(rule/args/src/verdict), `transform-survivor` WME.
- Produces: dashboard HTML 에 `transform-search` 패널 문자열 — required-effect·후보 DSL·각 시도(rule·arg src·verdict)·survivor.

- [ ] **Step 1: 위치 확정** — Run: `grep -rln "focus_dashboard\|def.*dashboard\|hypothesis" debugger arc | head`. 렌더 함수(WM→HTML)를 찾는다. 패널 삽입점 = 기존 hypothesis 렌더 블록 옆.

- [ ] **Step 2: 실패 테스트 작성** — `tests/test_dashboard_transform_panel.py`

```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestPanel(unittest.TestCase):
    def test_render_transform_panel(self):
        # 렌더 함수는 Step1 에서 확정한 실제 이름으로 교체
        from debugger.build import render_transform_panel   # 확정 후 정확 경로
        wm = [("s1", "required-effect", "reflect/rotate/translate"),
              ("s1", "candidates", "rot90,hmirror,move"),
              ("s1", "hypothesis", "s1.T1"),
              ("s1.T1", "rule", "rot90"), ("s1.T1", "src", "param-free"),
              ("s1.T1", "verdict", "survive"),
              ("root", "transform-survivor", "rot90 []")]
        html = render_transform_panel(wm)
        self.assertIn("rot90", html)
        self.assertIn("survive", html)
        self.assertIn("reflect/rotate/translate", html)
```

- [ ] **Step 3: 실패 확인** — Run: `python -m unittest tests.test_dashboard_transform_panel -v` · Expected: FAIL.

- [ ] **Step 4: 구현** — 확정한 dashboard 모듈에 렌더 함수 추가 + 기존 렌더 파이프라인에서 호출:

```python
def render_transform_panel(wm):
    """WM 의 transform_search 흔적을 HTML 패널로. required·후보·시도(verdict)·survivor."""
    def g(iid, attr):
        return [v for (i, a, v) in wm if i == iid and a == attr]
    req = (g("s1", "required-effect") or ["(none)"])[0]
    cands = (g("s1", "candidates") or ["(none)"])[0]
    rows = []
    for (i, a, v) in wm:
        if a == "hypothesis":
            rule = (g(v, "rule") or ["?"])[0]
            src = (g(v, "src") or [""])[0]
            verdict = (g(v, "verdict") or ["?"])[0]
            cls = "survive" if verdict == "survive" else "reject"
            rows.append(f'<tr class="{cls}"><td>{rule}</td><td>{src}</td><td>{verdict}</td></tr>')
    surv = [v for (i, a, v) in wm if a == "transform-survivor"]
    surv_html = f'<p><b>survivor:</b> {surv[0]}</p>' if surv else "<p>survivor 없음</p>"
    return (f'<div class="transform-search-panel"><h3>transform_search</h3>'
            f'<p><b>required-effect:</b> {req}</p><p><b>candidates:</b> {cands}</p>'
            f'<table><tr><th>rule</th><th>arg src</th><th>verdict</th></tr>'
            f'{"".join(rows)}</table>{surv_html}</div>')
```

기존 렌더 함수(Step1 확정)에서 이 패널을 최종 HTML 에 이어붙인다.

- [ ] **Step 5: 통과 확인** — Run: `python -m unittest tests.test_dashboard_transform_panel -v` · Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add debugger/ tests/test_dashboard_transform_panel.py
git commit -m "feat(#dsl) dashboard transform_search 패널 — 후보·시도·verdict·survivor(§2-5)"
```

---

### Task 8: 나머지 어휘 batch vendoring + constants/types + 테스트 사다리 검증

**Files:**
- Modify: `procedural_memory/dsl/transformation/hodel_transforms.py` (나머지 transform)
- Create: `procedural_memory/dsl/selection/hodel_selection.py` + selection `__init__.py` import
- Create: `procedural_memory/dsl/relation/hodel_relation.py` + relation `__init__.py` import
- Create: `semantic_memory/arc_constants.py`
- Test: `tests/test_vocab_batch.py`

**Interfaces:**
- Produces: transformation 나머지(`fill,paint,underfill,underpaint,cover,recolor,crop,subgrid,hconcat,vconcat,hsplit,vsplit,hupscale,vupscale,upscale,downscale,cellwise,canvas,normalize,toobject,asobject` — effect 는 verb 버킷 표대로) · selection VENDOR(`box,corners,backdrop,delta,neighbors,dneighbors,ineighbors,connect,shoot,frontiers,colorfilter,sizefilter,ofcolor,asindices,toindices,occurrences`) · relation VENDOR(`hmatching,vmatching,manhattan,adjacent,bordering,position,gravitate`) · WRAP(`objects,partition,fgpartition` → `find_all_objects`; `mostcolor,palette,height,width,shape,color,corners` → ARCKG `to_json`/`hodel`). constants 테이블.

- [ ] **Step 1: batch 등록 테스트** — `tests/test_vocab_batch.py`: 각 이름이 `SPECS` 에 있고 kind/effect 가 verb 버킷 표와 일치하는지 루프 검증(각 함수의 body 는 arc-dsl 원본을 list 표현으로 이식; 스칼라/집합 반환 함수는 effect=None). WRAP 함수는 `find_all_objects`/ARCKG 소스를 호출하는지 확인.

```python
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import procedural_memory.dsl as d

EXPECT = {  # name -> (kind, verb|None)
    "fill": ("transformation", "fill"), "cover": ("transformation", "fill"),
    "crop": ("transformation", "crop"), "upscale": ("transformation", "upscale"),
    "downscale": ("transformation", "downscale"), "hconcat": ("transformation", "concat"),
    "canvas": ("transformation", "create"),
    "objects": ("selection", None), "colorfilter": ("selection", None),
    "hmatching": ("relation", None), "manhattan": ("relation", None),
}

class TestBatch(unittest.TestCase):
    def test_registered(self):
        for name, (kind, verb) in EXPECT.items():
            self.assertIn(name, d.SPECS, name)
            self.assertEqual(d.SPECS[name]["kind"], kind, name)
            eff = d.SPECS[name]["effect"]
            self.assertEqual(eff["verb"] if eff else None, verb, name)
```

- [ ] **Step 2: 실패 확인** — Run: `python -m unittest tests.test_vocab_batch -v` · Expected: FAIL.

- [ ] **Step 3: transform 나머지 이식** — `hodel_transforms.py` 에 verb 버킷 표대로 `@dsl` 추가. body 는 arc-dsl 원본(scratchpad `arc-dsl/dsl.py`)을 list 표현으로 이식(tuple→list, `mostcolor`→`_bg`). 예:

```python
@dsl("transformation", ["grid", "color", "object"], "grid", effect=effect("fill", "grid"))
def fill(grid, value, patch):
    H, W = len(grid), len(grid[0]); out = [r[:] for r in grid]
    for (i, j) in patch:
        if 0 <= i < H and 0 <= j < W: out[i][j] = value
    return out

@dsl("transformation", ["grid", "size"], "grid", effect=effect("upscale", "grid"))
def upscale(grid, factor):
    return [[v for v in row for _ in range(factor)] for row in grid for _ in range(factor)]

@dsl("transformation", ["color", "size"], "grid", effect=effect("create", "grid"))
def canvas(value, dims):
    return [[value] * dims[1] for _ in range(dims[0])]
```

(나머지 transform·selection·relation 함수는 scratchpad `arc-dsl/dsl.py` 의 동명 함수 body 를 list 표현으로 그대로 이식. 스칼라/집합 반환은 effect=None.)

- [ ] **Step 4: selection/relation 모듈 + WRAP** — `hodel_selection.py`, `hodel_relation.py` 생성 후 각 category `__init__.py` 에서 import. WRAP 예:

```python
# hodel_selection.py
from procedural_memory.dsl.registry import dsl
from arbor.perception.arckg.hodel import find_all_objects

@dsl("selection", ["grid"], "list[object]")   # WRAP: ARCKG 와 동일 소스 재사용(§2-1)
def objects(grid):
    return [d["obj"] for d in find_all_objects(grid)]
```

- [ ] **Step 5: constants/types** — `semantic_memory/arc_constants.py`: `constants.py` 의 방향벡터/스칼라를 dict 로. arg 탐색(§3-3 ③)의 상수 어휘로 노출.

```python
DIRECTIONS = {"DOWN": (1, 0), "RIGHT": (0, 1), "UP": (-1, 0), "LEFT": (0, -1),
              "ORIGIN": (0, 0), "UNITY": (1, 1), "NEG_UNITY": (-1, -1),
              "UP_RIGHT": (-1, 1), "DOWN_LEFT": (1, -1)}
SCALARS = {f"N{i}": i for i in range(11)}
```

- [ ] **Step 6: 통과 확인 + 온톨로지 재생성** — Run:
```
python -m unittest tests.test_vocab_batch -v
python -c "import procedural_memory.dsl as d; print(len(d.SPECS))"
python -m semantic_memory.build
```
Expected: PASS; SPECS 길이 대폭 증가; `ontology.json` 갱신.

- [ ] **Step 7: 테스트 사다리 검증 (성공 판정 §2-4)** — Run: `python -m debugger.build`. 4문제(easy000a·made000b·08ed6ac7·made000a)의 **step 수·후보 수·하강 깊이가 서로 다른지**, transform_search 를 타는 문제에서 survivor 가 `program.json` 에 남고 시도·기각이 대시보드에 보이는지 확인. 모두 같은 step 이면 실패(탐색 은닉) → §5/§7.

- [ ] **Step 8: 기존 테스트 회귀 확인** — Run: `python -m unittest tests.test_dsl tests.test_decide tests.test_soar_solver -v`. Expected: 기존 통과 유지(신 어휘가 기존 경로를 깨지 않음).

- [ ] **Step 9: Commit**

```bash
git add procedural_memory/dsl semantic_memory tests/test_vocab_batch.py
git commit -m "feat(#dsl) 나머지 transform/select/relation batch vendoring + WRAP + constants; 테스트 사다리 검증"
```

---

## Self-Review (스펙 대조)

- **스펙 §1 어휘 등록(WRAP/VENDOR)** → Task 1-3(슬라이스), Task 8(batch+WRAP). ✅
- **스펙 §2 synthesize contents 공백 훅** → Task 6 Step 1. ✅
- **스펙 §3-1 propose=effect 일치** → Task 5 `candidate_transforms`+`matches`. ✅
- **스펙 §3-2 required-effect 도출(generic)** → Task 4. ✅
- **스펙 §3-3 arg ①relation ②selection ③search** → Task 5 `_arg_plans`(recolor 즉시 / translate 선택+offset 탐색) / param-free. ✅
- **스펙 §3-4 SOAR 배선(operator+json+OPERATOR_BODIES+helpers 재사용)** → Task 6. (offset 탐색은 `_offset_formulas` 로 §4-1 형식 재현; 기존 helpers 와 동형.) ✅
- **스펙 §4 dashboard 패널** → Task 7. ✅
- **스펙 §5 테스트 사다리·수직 슬라이스(param-free/replace/move)** → Task 5 테스트 + Task 8 Step 7. ✅
- **스펙 §1-5 constants/types** → Task 8 Step 5. ✅
- **스펙 §7 리스크**: R1(finder)=Task 4 generic-only+후보집합, R3(은닉)=Task 5/6 hypothesis 잔존+Task 8 step 다양성 판정. ✅

**Placeholder scan**: 각 코드 스텝에 실제 body/테스트 포함. Task 7 Step 1·Task 8 Step 3 은 "scratchpad 원본 이식"·"렌더 함수 위치 grep" 지시가 있으나, 이식 규칙(tuple→list, verb 버킷)과 grep 명령이 구체적이라 실행 가능. ✅

**Type consistency**: `transform_search(train)->{required,candidates,hypotheses,survivor}` (Task 5) ↔ `_op_transform_search` 소비(Task 6) ↔ dashboard WME(Task 7) 일치. `find_all_objects` 반환 `{"obj":frozenset((color,(r,c)))}` ↔ `move/shift` obj_cells 일치. ✅
