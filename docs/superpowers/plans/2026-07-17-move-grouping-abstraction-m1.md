# move 그룹핑 추상화 M‑1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** M2(단일 다세포 객체 이동) 클래스가 pixel 잔여를 object 로 되묶는 **그룹핑 탐색** + **강체 앵커-Δ 재표현**으로 풀리게 한다.

**Architecture:** grid-래핑된 move 의 pixel 잔여를 `compress` 가 blob(cellset)으로 되묶고(그룹핑 술어를 규칙활성 탐색), `_antiunify_ast_grid` 가 그 blob contents 를 재귀 anti-unify, `resolve_cellset` 이 cellset 을 "input 객체 + Δ"(강체, relative/absolute/corner 통합 좌표문법)로 재표현한다. `TASK.solution` 은 G0-only(P5).

**Tech Stack:** Python 3, `unittest`, SOAR 커널(`soar/`), ARBOR(`arbor/`), procedural_memory operators/rules(JSON). 진입점 `python -m debugger.build`, 오라클 `PYTHONPATH=. python3 tests/verify_refactor.py`.

## Global Constraints
- **DSL 동결:** 새 transformation DSL 금지 — `make_grid`·`coloring` 만. 새 property 금지(§2-1/§7).
- **P5:** `TASK.solution` 의 모든 항은 **G0** 유래. `objects_of(G1)`/output 대응은 train 도출·검증에만.
- **행동보존:** `PYTHONPATH=. python3 tests/verify_refactor.py` 가 easy a–i 골든과 일치해야 함(신규 풀림 태스크만 재기준화). 매 Task 종료 시 실행.
- **정직한 탐색(§1-3/§1-5):** Δ·그룹핑·색은 후보생성→train적용→대조→기각/생존. 시도·기각이 트레이스/대시보드에 남아야 함.
- **테스트 실행:** `PYTHONPATH=. python3 -m unittest tests.<module> -v`.
- **커밋:** 각 Task 끝에서 커밋([[commit-after-execution]] — 코드 실행·검증 후). 첫 커밋에 스펙(`docs/superpowers/specs/2026-07-17-move-grouping-abstraction-design.md`) 동봉.

---

## File Structure
- `arbor/reasoning/program_ast.py` — (수정) `_antiunify_ast_grid` 에 contents=blob 재귀; `grid_inner_op_counts` 헬퍼.
- `procedural_memory/operators/generalize.py` — (수정) grid-inner 불일치 감지 → `needs-compress`.
- `procedural_memory/operators/compress.py` — (수정) grid-래핑 잔여 blob화 + 그룹핑 술어 + `grouping-idx` cursor.
- `arbor/reasoning/antiunify.py` — (수정) `_resolve_cellset` 강체 앵커-Δ 좌표문법.
- `procedural_memory/production_rules/compress.json`, `resolve.json` — (수정) 그룹핑 cursor 순회 규칙.
- `procedural_memory/operators/resolve.py` — (수정) resolve 실패 시 다음 그룹핑 신호.
- `debugger/reports/program_viewer.py` — (수정) 그룹핑 술어·Δ 시도/기각 노출.
- `tests/test_move_grouping.py` — (신규) 단위 테스트.
- `tests/golden_steps.json`, `tests/verify_refactor.py` — (수정 없음/재기준화) 행동보존.

---

## Task 1: `_antiunify_ast_grid` — contents=blob 재귀

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (`_antiunify_ast_grid`, 402-432 부근)
- Test: `tests/test_move_grouping.py` (신규)

**Interfaces:**
- Consumes: 기존 `_antiunify_ast_blob(asts)`, `_antiunify_ast_pixel(asts)`, `_reprefix_inner_vars`.
- Produces: `antiunify_ast([grid>blob, grid>blob])` → grid skeleton with contents=program(blob body) + `?c.cellsetN`/`?c.colorN` slots.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_move_grouping.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as PA


class TestGridBlobAntiunify(unittest.TestCase):
    def _grid_blob(self, cells, col):
        b = [PA.step("coloring", target=PA.cellset(PA.const(cells)), color=PA.const(col))]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_with_blob_contents_recurses(self):
        a = self._grid_blob([7, 8], 3)
        b = self._grid_blob([20, 21], 3)          # 같은 색, cellset DIFF
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        parts = {s["call"]: s["args"] for s in sk["body"]}
        inner = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertEqual(inner[0]["args"]["target"]["ref"], "cellset")
        self.assertTrue(any(k.startswith("?c.cells") for k in slots))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGridBlobAntiunify -v`
Expected: FAIL (현재 `_antiunify_ast_grid` 는 blob inner body 를 pixel 로 처리해 None 또는 오분류).

- [ ] **Step 3: Implement — blob inner 분기 추가**

`_antiunify_ast_grid` 의 `if call == "set_grid_contents" and all("program" in leaf ...)` 블록에서, inner body 가 cellset 이면 `_antiunify_ast_blob`, pixel 이면 `_antiunify_ast_pixel` 로 dispatch:

```python
        if call == "set_grid_contents" and all("program" in leaf for leaf in leaves):
            inner_asts = [program(leaf["program"]["body"]) for leaf in leaves]
            if all(_is_cellset_body(ia["body"]) for ia in inner_asts):
                sk_inner, inner_slots = _antiunify_ast_blob(inner_asts)
            else:
                sk_inner, inner_slots = _antiunify_ast_pixel(inner_asts)
            if sk_inner is None:
                return None, None
            leaf = {"program": {"body": (sk_inner or {}).get("body", [])}}
            for nm, meta in (inner_slots or {}).items():
                slots[f"?c.{nm[1:]}"] = meta
            leaf = _reprefix_inner_vars(leaf, "?c.")
            body.append({"call": call, "args": {key: leaf}})
            continue
```

`_reprefix_inner_vars` 의 `if "cells" in new_tgt:` 분기는 이미 존재(현재 unreachable 주석) — cellset var 재바인딩이 이제 도달.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGridBlobAntiunify -v`
Expected: PASS

- [ ] **Step 5: 행동보존 + 커밋**

```bash
PYTHONPATH=. python3 tests/verify_refactor.py   # 골든 일치 확인
git add arbor/reasoning/program_ast.py tests/test_move_grouping.py docs/superpowers/specs/2026-07-17-move-grouping-abstraction-design.md docs/superpowers/plans/2026-07-17-move-grouping-abstraction-m1.md
git commit -m "feat(program-ast): _antiunify_ast_grid contents=blob 재귀 (move M-1 Task1)"
```

---

## Task 2: grid-inner 불일치 감지 → `needs-compress`

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (신규 헬퍼 `grid_inner_op_counts`)
- Modify: `procedural_memory/operators/generalize.py` (`_op_generalize` fallback)
- Test: `tests/test_move_grouping.py`

**Interfaces:**
- Produces: `program_ast.grid_inner_op_counts(ast) -> list[int] | None` (grid>pixel/blob 이면 inner contents op 수, 아니면 None). generalize 는 이 값들의 집합 크기>1 이면 `needs-compress`.

- [ ] **Step 1: Write the failing test**

```python
class TestGridInnerCounts(unittest.TestCase):
    def _grid_pixel(self, idxs):
        b = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(0)) for i in idxs]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_inner_op_counts_reads_contents_length(self):
        self.assertEqual(PA.grid_inner_op_counts(self._grid_pixel([1, 2, 3])), [3])

    def test_grid_inner_op_counts_none_for_nongrid(self):
        flat = PA.program([PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(0))])
        self.assertIsNone(PA.grid_inner_op_counts(flat))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGridInnerCounts -v`
Expected: FAIL (`AttributeError: grid_inner_op_counts`).

- [ ] **Step 3: Implement 헬퍼 + generalize 결선**

`program_ast.py` 에 추가:

```python
def grid_inner_op_counts(ast):
    """grid>pixel/blob 이면 set_grid_contents 의 nested program body 길이 [n], 아니면 None."""
    body = (ast or {}).get("body") or []
    if not _is_grid_body(body):
        return None
    for s in body:
        if s["call"] == "set_grid_contents":
            leaf = s["args"]["contents"]
            if "program" in leaf:
                return [len(leaf["program"]["body"])]
    return None
```

`generalize.py` `_op_generalize` — fallback 을 grid-aware 로:

```python
    sk, slots = antiunify_ast(asts)
    if sk is None:                                        # 구조 불일치/부족
        from arbor.reasoning.program_ast import grid_inner_op_counts
        inner = [grid_inner_op_counts(a) for a in asts]
        grid_mismatch = (all(x is not None for x in inner)
                         and len({x[0] for x in inner if x}) > 1)
        if not ag.wm.contains(sid, "compressed", "yes") and (compressible(progs) or grid_mismatch):
            ag.wm.add(sid, "needs-compress", "yes")
            return
        ag.wm.add(sid, "generalized", "failed")
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGridInnerCounts -v`
Expected: PASS

- [ ] **Step 5: 행동보존 + 커밋**

```bash
PYTHONPATH=. python3 tests/verify_refactor.py
git add arbor/reasoning/program_ast.py procedural_memory/operators/generalize.py tests/test_move_grouping.py
git commit -m "feat(generalize): grid-래핑 inner 불일치→needs-compress (move M-1 Task2)"
```

---

## Task 3: `compress` — grid-래핑 잔여 blob화 (grid 래퍼 유지)

**Files:**
- Modify: `procedural_memory/operators/compress.py` (`_blob_program`)
- Test: `tests/test_move_grouping.py`

**Interfaces:**
- Consumes: `program_ast.as_source`, `parse_program`, `program`, `step`, `cellset`, `const`, `contents_program`, `set_grid_size/color/contents`, `_is_grid_body`.
- Produces: `compress._blob_program(code, W) -> json` — grid>pixel 입력이면 grid>blob(inner contents 만 blob화, size/color leaf 보존) 출력.

- [ ] **Step 1: Write the failing test**

```python
import json
from procedural_memory.operators import compress as CG

class TestCompressGridWrapped(unittest.TestCase):
    def test_grid_pixel_program_compresses_inner_keeps_wrapper(self):
        # 잔여 4셀(=2셀 객체 이동): W=5. 나간자리 idx 0,1(색0); 들어온자리 idx 12,13(색3)
        inner = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(c))
                 for i, c in [(0, 0), (1, 0), (12, 3), (13, 3)]]
        gp = PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                             PA.contents_program(inner))
        out = json.loads(CG._blob_program(json.dumps(gp), 5))
        parts = {s["call"]: s["args"] for s in out["body"]}
        self.assertIn("set_grid_size", parts)                 # 래퍼 유지
        blob_body = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in blob_body))
        self.assertEqual(len(blob_body), 2)                   # 2 덩어리(나간/들어온)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestCompressGridWrapped -v`
Expected: FAIL (현재 `_blob_program` 은 `parse_program(as_source(grid))=None` → None 반환).

- [ ] **Step 3: Implement — grid 분기**

`compress.py` `_blob_program` 을 grid-aware 로. grid AST 면 inner contents body 를 blob화해 grid 로 재조립:

```python
def _blob_program(code, W, predicate="color"):
    """pixel program(AST-json|legacy) → blob(object-level) AST-json.
    grid>pixel 이면 inner contents 만 blob화하고 size/color leaf 보존. 압축 불가면 None."""
    from arbor.reasoning.program_ast import _is_grid_body
    try:
        ast = json.loads(code) if code and code.lstrip().startswith("{") else None
    except (ValueError, TypeError):
        ast = None
    if ast and _is_grid_body(ast.get("body") or []):
        parts = {s["call"]: s["args"] for s in ast["body"]}
        cleaf = parts["set_grid_contents"]["contents"]
        inner = (cleaf.get("program") or {}).get("body") if "program" in cleaf else None
        if not inner:
            return None
        ops = [(t["args"]["target"]["index"]["const"], t["args"]["color"]["const"])
               for t in inner if t["args"]["target"].get("ref") == "pixel"]
        if len(ops) != len(inner):
            return None
        blob_body = _blob_body(ops, W, predicate)
        if blob_body is None:
            return None
        new = dict(parts)
        new_contents = set_grid_contents(contents_program(blob_body))
        body = [set_grid_size(parts["set_grid_size"]["size"]),
                set_grid_color(parts["set_grid_color"]["color"]),
                new_contents]
        return json.dumps(program(body))
    # ── 기존 flat pixel 경로 (변경 없음) ──
    ops = parse_program(as_source(code))
    if not ops:
        return None
    blob_body = _blob_body(ops, W, predicate)
    return json.dumps(program(blob_body)) if blob_body else None


def _blob_body(ops, W, predicate="color"):
    """(idx,color) 목록 → blob step 리스트. Task 4 에서 predicate 분기; 여기선 color(연결성) 기본."""
    blobs = _blobs(ops, W)
    blobs.sort(key=lambda b: b[0][0])
    body = []
    for (cells, col) in blobs:
        idxs = [r * W + c for (r, c) in cells]
        body.append(step("coloring", target=cellset(const(idxs)), color=const(col)))
    return body if body else None
```

import 에 `set_grid_size, set_grid_color, set_grid_contents, contents_program` 추가:
```python
from arbor.reasoning.program_ast import (as_source, program, step, cellset, const,
    set_grid_size, set_grid_color, set_grid_contents, contents_program)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestCompressGridWrapped -v`
Expected: PASS

- [ ] **Step 5: 행동보존 + 커밋**

```bash
PYTHONPATH=. python3 tests/verify_refactor.py
git add procedural_memory/operators/compress.py tests/test_move_grouping.py
git commit -m "feat(compress): grid-래핑 잔여 blob화·래퍼 보존 (move M-1 Task3)"
```

---

## Task 4: `resolve_cellset` — 강체 앵커-Δ 좌표문법

**Files:**
- Modify: `arbor/reasoning/antiunify.py` (`_resolve_cellset`, 347-396)
- Test: `tests/test_move_grouping.py`

**Interfaces:**
- Consumes: 기존 `_components`, `_obj_atoms`, `_axis_matches`, `_selectors`, `_MATCH_CAP`.
- Produces: `_resolve_cellset(vals, train, comps, sels) -> (survivors=[(name, fn(grid)->cells)], tried)`. survivors[i][1](grid) 는 소스객체를 앵커-Δ(relative/absolute/corner) 로 강체 이동한 **cells(픽셀 인덱스 리스트)** 반환.

- [ ] **Step 1: Write the failing test**

```python
from arbor.reasoning import antiunify as AU

class TestResolveCellsetRigidDelta(unittest.TestCase):
    def _pair(self, grid_in, dest_cells):
        return {"input": grid_in, "output": grid_in}       # output 미사용(dest 는 vals 로 전달)

    def test_relative_offset_resolves_rigidly(self):
        # 3x5 grid, 소스객체=색3 두 셀 (0,0),(0,1)=idx0,1. dest= +2행 이동 → (2,0),(2,1)=idx10,11
        g0 = [[3,3,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
        g1 = [[3,3,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]           # 두번째 pair: 같은 오프셋, 다른 위치는 아래서
        train = [{"input": g0, "output": g1}, {"input": g0, "output": g1}]
        comps = [AU._components(e["input"]) for e in train]
        sels = AU._selectors(comps)
        vals = [[10, 11], [10, 11]]                          # +2행 dest (relative)
        slot = {"kind": "cellset", "pos": 0, "values": vals}
        survivors, tried = AU.resolve_slot(slot, train)
        self.assertTrue(survivors, f"no survivor; tried={tried}")
        cells = survivors[0][1](g0)
        self.assertEqual(sorted(cells), [10, 11])            # G0 에 적용 시 dest 재현
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestResolveCellsetRigidDelta -v`
Expected: FAIL (현재 `_resolve_cellset` 은 canonical anchor(keep/edge)만 → relative +2행 미표현 → survivor 없음).

- [ ] **Step 3: Implement — 앵커-Δ 좌표문법 (canonical 대체)**

`_resolve_cellset` 을 재작성. 소스객체는 selector 로 고르고(모양 평행이동 일치 확인), **dest 앵커(min r, min c)** 를 `_axis_matches` 로 resolve → 강체 이동 fn:

```python
def _resolve_cellset(vals, train, comps, sels):
    """cellset slot → (survivors, tried). 소스객체(selector·모양평행이동 일치) 를 dest 로 강체 이동.
    dest 앵커(min r,min c)를 좌표문법(_axis_matches)으로 resolve → relative/absolute/corner 통합. §P5."""
    N = len(vals)
    dests = []
    for i in range(N):
        W = len(train[i]["input"][0])
        dests.append(sorted((idx // W, idx % W) for idx in vals[i]))
    dest_anchor = [(min(r for r, _ in d), min(c for _, c in d)) for d in dests]  # (dr0, dc0) per pair
    keyed, tried = [], []
    for si, (sname, sfn) in enumerate(sels):
        objs = [sfn(comps[i]) for i in range(N)]
        if any(o is None for o in objs):
            continue
        atoms, ok_shape = [], True
        for i in range(N):
            src = sorted(objs[i]); d = dests[i]
            if len(src) != len(d):
                ok_shape = False; break
            sr, sc = min(r for r, _ in src), min(c for _, c in src)
            dr, dc = min(r for r, _ in d), min(c for _, c in d)
            if sorted((r - sr, c - sc) for r, c in src) != sorted((r - dr, c - dc) for r, c in d):
                ok_shape = False; break                        # 모양(평행이동 불변) 불일치
            atoms.append(_obj_atoms(objs[i], train[i]["input"]))
        if not ok_shape:
            tried.append((f"move@{sname}: 모양 불일치", False)); continue
        r_hits, r_tr = _axis_matches(atoms, dest_anchor, 0)    # dest 앵커 행식
        c_hits, c_tr = _axis_matches(atoms, dest_anchor, 1)    # dest 앵커 열식
        if not r_hits or not c_hits:
            tried.append((f"move@{sname}: 앵커식 없음", False)); continue
        for rn, rf, rd in r_hits:
            for cn, cf, cd in c_hits:
                name = f"move({rn},{cn})@{sname}"
                key = (_axis_tier(rn, 0) + _axis_tier(cn, 1), rd + cd, si, len(name))
                keyed.append((key, name, _translate_obj_fn(sfn, rf, cf)))
    keyed.sort(key=lambda t: t[0])
    for _k, name, fn in keyed[:_MATCH_CAP]:
        tried.append((name, True))
    survivors = [(name, fn) for _k, name, fn in keyed[:_MATCH_CAP]]
    if not survivors:
        tried.append(("<no anchor-delta>", False))
    return survivors, tried


def _translate_obj_fn(sfn, rf, cf):
    """(선택자, 앵커행식, 앵커열식) → fn(grid): 소스객체를 (rf,cf) 앵커로 강체 이동한 cells(idx)."""
    def fn(g):
        cells = sfn(_components(g))
        if cells is None:
            return None
        a = _obj_atoms(cells, g)
        tr, tc = rf(a), cf(a)
        if tr is None or tc is None:
            return None
        sr = min(r for r, _ in cells); sc = min(c for _, c in cells)
        W = len(g[0])
        return [ (r - sr + tr) * W + (c - sc + tc) for (r, c) in cells ]
    return fn
```

`_place_canonical_fn`·`_ROW_ANCHORS`·`_COL_ANCHORS` 는 이제 미사용 → 삭제(또는 주석 DEPRECATED).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestResolveCellsetRigidDelta -v`
Expected: PASS

- [ ] **Step 5: 행동보존 + 커밋**

```bash
PYTHONPATH=. python3 tests/verify_refactor.py
git add arbor/reasoning/antiunify.py tests/test_move_grouping.py
git commit -m "feat(resolve): cellset 강체 앵커-Δ 좌표문법(relative/absolute/corner 통합) (move M-1 Task4)"
```

---

## Task 5: 그룹핑 술어 탐색 + `grouping-idx` cursor (규칙 활성)

**Files:**
- Modify: `procedural_memory/operators/compress.py` (`_blob_body` predicate 분기 + `_op_compress` cursor)
- Modify: `procedural_memory/operators/resolve.py` (resolve 실패 → 다음 그룹핑 신호)
- Modify: `procedural_memory/production_rules/compress.json` (propose 조건 + cursor 순회)
- Test: `tests/test_move_grouping.py`

**Interfaces:**
- Produces: `_blob_body(ops, W, predicate)` — predicate ∈ {"color","in_obj","out_obj"}; `_op_compress` 는 `S1 ^grouping-idx k`(기본0) 로 술어 선택, resolve 실패 시 규칙이 k+1 후 compress 재발화. 술어 소진(k≥3) 이면 `generalized=failed`.

- [ ] **Step 1: Write the failing test (predicate 분기)**

```python
class TestGroupingPredicates(unittest.TestCase):
    def test_color_predicate_two_groups(self):
        ops = [(0, 0), (1, 0), (12, 3), (13, 3)]            # 두 색
        body = CG._blob_body(ops, 5, predicate="color")
        self.assertEqual(len(body), 2)
        cols = sorted(s["args"]["color"]["const"] for s in body)
        self.assertEqual(cols, [0, 3])

    def test_in_obj_predicate_groups_by_input_object(self):
        # G0: 색3 객체 (0,0),(0,1). in_obj 그룹핑은 그 좌표를 한 덩어리로.
        g0 = [[3, 3, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]]
        ops = [(0, 0), (1, 0)]                              # 색3 객체가 나간 잔여(같은 좌표)
        body = CG._blob_body_ctx(ops, 5, predicate="in_obj", grid_in=g0)
        self.assertEqual(len(body), 1)                      # 한 input 객체 → 한 덩어리
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGroupingPredicates -v`
Expected: FAIL (`_blob_body` predicate 미분기 / `_blob_body_ctx` 없음).

- [ ] **Step 3: Implement predicate 분기**

`compress.py` — 술어별 그룹핑. color=연결·동색(기존 `_blobs`); in_obj/out_obj=grid 객체 소속으로 묶음:

```python
def _group_by_object(ops, W, grid):
    """ops 픽셀을 grid 의 4-연결 동색 객체 소속으로 묶는다. 같은 객체에 속한 잔여 셀 = 한 cellset.
    (grid = in_obj 면 input_grid, out_obj 면 output_grid.) 소속 못 찾은 셀은 자기 색 연결덩어리로."""
    from arbor.reasoning.antiunify import _components
    comp_of = {}
    for ci, (cells, _col) in enumerate(_components(grid)):
        for (r, c) in cells:
            comp_of[(r, c)] = ci
    groups = {}
    for idx, col in ops:
        key = comp_of.get((idx // W, idx % W), ("solo", idx))
        groups.setdefault(key, []).append((idx, col))
    body = []
    for key in sorted(groups, key=lambda k: str(k)):
        members = groups[key]
        idxs = sorted(i for i, _ in members)
        col = members[0][1]                                 # 그 덩어리의 칠할 색(동일 가정; 아니면 solo 분해)
        if len({c for _, c in members}) == 1:
            body.append(step("coloring", target=cellset(const(idxs)), color=const(col)))
        else:
            for i, c in members:
                body.append(step("coloring", target=cellset(const([i])), color=const(c)))
    return body


def _blob_body(ops, W, predicate="color"):
    blobs = _blobs(ops, W); blobs.sort(key=lambda b: b[0][0])
    body = [step("coloring", target=cellset(const([r * W + c for (r, c) in cells])), color=const(col))
            for (cells, col) in blobs]
    return body or None


def _blob_body_ctx(ops, W, predicate, grid_in=None, grid_out=None):
    if predicate == "in_obj" and grid_in is not None:
        return _group_by_object(ops, W, grid_in) or None
    if predicate == "out_obj" and grid_out is not None:
        return _group_by_object(ops, W, grid_out) or None
    return _blob_body(ops, W, "color")
```

`_blob_program(code, W, predicate, grid_in, grid_out)` 는 `_blob_body_ctx` 를 부르도록 인자 추가. `_op_compress` 는 `grouping-idx` 로 술어 선택 + 각 pair 의 train in/out grid 전달:

```python
_PREDICATES = ["color", "in_obj", "out_obj"]

def _op_compress(ag):
    sid = ag.stack[-1].id
    gi = next((int(v) for (i, a, v) in ag.wm if i == "S1" and a == "grouping-idx"), 0)
    if gi >= len(_PREDICATES):
        ag.wm.add(sid, "generalized", "failed")             # 술어 소진 → 정직 실패
        for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-compress")):
            ag.wm.remove(i, a, v)
        return
    predicate = _PREDICATES[gi]
    root = ag.kg.get("arckg_root")
    # ... (기존 루프; _blob_program(code, W, predicate, gin, gout) 로 호출, gin/gout=train[k] in/out) ...
    # compressed=yes 대신, resolve 실패 시 grouping-idx++ 재시도를 위해 compressed 는 두지 않음.
    ag.kg["compress"] = {"predicate": predicate, "n_pairs": n, "grouping_idx": gi}
```

`resolve.py` `_op_resolve` — 실패 시 다음 그룹핑 신호:

```python
    if not ok_all:
        gi = next((int(v) for (i, a, v) in ag.wm if i == "S1" and a == "grouping-idx"), 0)
        for (i, a, v) in list(ag.wm.matching(identifier="S1", attr="grouping-idx")):
            ag.wm.remove(i, a, v)
        ag.wm.add("S1", "grouping-idx", str(gi + 1))
        # generalized/solution 리셋 → compress 재발화(다음 술어)
        for attr in ("generalized",):
            for (i, a, v) in list(ag.wm.matching(identifier=sid, attr=attr)):
                ag.wm.remove(i, a, v)
        ag.wm.add(sid, "needs-compress", "yes")
    ag.wm.add(sid, "resolved", "yes" if ok_all else "retry-grouping")
```

`compress.json` propose 조건: `needs-compress=yes ∧ ¬(compressed=yes)` 유지하되, `resolve.py` 가 `compressed` 를 걷어내는 대신 `needs-compress` 재설정으로 재발화(위). `production_rules/compress.json` 의 `compressed` negation 조건 확인·유지.

- [ ] **Step 4: Run predicate test + M2 solve smoke**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestGroupingPredicates -v`
Expected: PASS

- [ ] **Step 5: 행동보존 + 커밋**

```bash
PYTHONPATH=. python3 tests/verify_refactor.py
git add procedural_memory/operators/compress.py procedural_memory/operators/resolve.py procedural_memory/production_rules/compress.json tests/test_move_grouping.py
git commit -m "feat(compress): 그룹핑 술어 탐색+grouping-idx cursor 규칙활성 (move M-1 Task5)"
```

---

## Task 6: M2 통합 · 대시보드 · 골든 재기준화

**Files:**
- Modify: `debugger/reports/program_viewer.py` (그룹핑 술어·Δ 노출)
- Modify: `tests/golden_steps.json` (재기준화 — 변경분만)
- Test: `tests/test_move_grouping.py` (M2 e2e), `tests/verify_refactor.py`

**Interfaces:**
- Consumes: `_Tracer`, `setup_focus_agent`, `list_tasks("move")`, `load_task`.
- Produces: M2 태스크(예: move000m/p 3ex) solved=True; move report 에 `compress.predicate`·`resolve` Δ 패널.

- [ ] **Step 1: Write the failing e2e test**

```python
from arbor.env.dataset import list_tasks, load_task
from arbor.agent.focus import setup_focus_agent
from arbor.engine.trace import _Tracer

class TestM2SolvesEndToEnd(unittest.TestCase):
    def _solve(self, tid):
        p = dict(list_tasks("move"))[tid]
        tr = _Tracer(load_task(p), tid, setup=setup_focus_agent)
        tr.run(max_cycles=800)
        return any(a["correct"] for a in tr.attempts)

    def test_m2_corner_and_absolute_solve(self):
        # 길이가 pair 간 일치하는 M2(3ex) 케이스: p(BR/absolute)·bh(shape/corner) 는 mism=False
        self.assertTrue(self._solve("move000p"), "M2 BR/absolute 미해결")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestM2SolvesEndToEnd -v`
Expected: FAIL (통합 전 — grouping/resolve 경로 미완이면 halt).

- [ ] **Step 3: Implement — dashboard 노출 + 필요한 통합 보정**

`program_viewer.py` `_collect`/렌더에 `compress` predicate 와 `resolve` Δ(및 tried) 를 패널로 추가(기존 solution 렌더 곁에). 최소:

```python
    # _collect 반환에 kg["compress"], kg["resolve"] 추가 노출
    compress_info = wm_kg.get("compress")      # {"predicate":..., "grouping_idx":...}
    resolve_info = wm_kg.get("resolve")        # {"resolved":..., "tried":...}
```
그리고 solution 카드 하단에 `<div class="note">그룹핑: {predicate} · Δ: {resolved}</div>` 추가(시도/기각은 접이식).

통합 실행에서 막히면 트레이스(`debugger/traces/move_dashboard.html`)로 어느 단계(compress/generalize/resolve)에서 멈추는지 확인해 해당 Task(3/4/5) 코드 보정.

- [ ] **Step 4: Verify e2e + 골든**

```bash
PYTHONPATH=. python3 -m unittest tests.test_move_grouping.TestM2SolvesEndToEnd -v   # PASS
PYTHONPATH=. python3 tests/verify_refactor.py                                        # easy a-i 골든 일치
PYTHONPATH=. python3 -m debugger.build move                                          # move 대시보드 재생성(렌더 확인)
```
easy 골든이 바뀌었으면(설명 가능한 변화만) `tests/golden_steps.json` 갱신. move 신규 풀림 수 기록.

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/program_viewer.py tests/golden_steps.json tests/test_move_grouping.py
git commit -m "feat(move): M2 그룹핑→blob→강체Δ e2e 풀림 + 대시보드 노출 (move M-1 Task6)"
```

---

## Self-Review (plan ↔ spec)

**Spec coverage:**
- §2.1 Trigger/reachability → Task 2(generalize needs-compress) + Task 3(compress grid-wrap). ✓
- §2.2 그룹핑 규칙활성 탐색 → Task 5(predicates + grouping-idx cursor + resolve 재시도). ✓
- §2.3 대응-Δ 재표현(resolve_cellset) → Task 4(강체 앵커-Δ 좌표문법). ✓ (소스 선택자는 M2 단일객체라 area-rank selector 로 충분; 대응기반 선택은 M‑2.)
- §2.4 아티팩트/대시보드 → Task 6(program_viewer 패널). ✓
- §3 수용/행동보존 → 매 Task Step5 `verify_refactor.py` + Task 6 골든 재기준화. ✓
- §4 신규/변경 표면 → Task 1(_antiunify_ast_grid), 2(generalize), 3–5(compress/resolve/rules), 4(resolve_cellset). ✓ 새 transformation DSL/property 없음.

**Placeholder scan:** 코드 스텝 전부 실코드. Task 6 Step3 의 "막히면 보정"은 통합 디버깅 지시(트레이스 경유) — 플레이스홀더 아님(구체 진입점 제시).

**Type consistency:** `_blob_program(code, W, predicate="color", grid_in, grid_out)`·`_blob_body_ctx(ops,W,predicate,grid_in,grid_out)`·`_resolve_cellset(vals,train,comps,sels)`·`grid_inner_op_counts(ast)->[n]|None` — Task 간 시그니처 일치. `grouping-idx` 는 `S1` 상태에 저장(pair-idx 와 동일 규약).

**주의(실행 중 확인):** grouping-idx 재시도 루프의 o-support 소거는 [[seokki-refactor]] 메모의 `elaborator.o_support_wmes.discard` 주의사항 적용(resolve 리셋 시 필요하면 동일 처리). Task 5 통합에서 무한재발화/미재발화 나오면 그 지점부터 점검.
