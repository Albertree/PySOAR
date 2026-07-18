# PAIR.program 픽셀-리터럴 + grouping→TASK.solution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PAIR.program 을 픽셀-리터럴(`coloring((r,c), 색)`)로 두고, 객체 grouping(cellset)을 compress 별도 slot→TASK.solution 으로 이관해 계층을 하네스 §0.5 에 맞춘다.

**Architecture:** program_ast 에 `ref("coord",[r,c])` 타깃을 추가(dormant)하고 표시/러너도 지원 → compress 를 `grouping` slot 으로 돌려 PAIR.program 을 안 덮게 하고 generalize 가 그 slot 을 anti-unify → 마지막에 픽셀 emit 을 리터럴 좌표로 전환. 답은 TASK.solution 실행에서 나오므로 표현 변경의 solve 리스크가 낮다.

**Tech Stack:** Python 3, 자체 SOAR 커널, program_ast(AST-json), pytest, Node(러너 parity).

## Global Constraints

- move 60/60 유지 — 게이트: `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60` (seed 0/1/42)
- 전체 pytest 신규 회귀 0 — 현재 기준선 `170 passed, 10 failed, 11 skipped` (10 = 기존 pre-existing). 단, solve WM 를 바꾸는 Task 3·4 는 `tests/fixtures/engine_golden.pkl`(구 engine-refactor 특성화)이 **의도적으로** 낡으므로 그 태스크 안에서 재생성한다(아래 명시).
- TASK.solution/resolve/apply_solution 산물 불변(답 불변). cellset 은 TASK.solution 에만, PAIR.program(example)엔 없어야 함.
- 새 operator/DSL/finder 금지(ARBOR_HARNESS §1-1). `ref("coord")` 는 기존 coloring position 에 리터럴을 넣는 것(§5 승인).
- 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: program_ast `ref("coord")` 지원 (dormant)

**Files:**
- Modify: `arbor/reasoning/program_ast.py` (`_is_pixel_body`, `_execute_pixel_body`, `ops_of_ast`, `_render_contents_src`)
- Test: `tests/test_coord_target.py`

**Interfaces:**
- Produces: coloring 타깃 `{"ref":"coord","index":{"const":[r,c]}}` — build 는 기존 `PA.ref("coord", PA.const([r,c]))`.
  - `_execute_pixel_body`: `ref=="coord"` → 위치 `(r,c)=index.const` 직접(`//W` 안 함).
  - `ops_of_ast`: coord → `(tuple([r,c]), color)` (해시가능; anti-unify 위치 키).
  - `_is_pixel_body`: `ref in ("pixel","coord")` 를 픽셀 body 로 인정.
  - to_source 렌더: `coloring((r,c), color=..)`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_coord_target.py`:
```python
import json
from arbor.reasoning import program_ast as PA


def test_coord_execute_paints_literal_cell():
    # 2x3 grid, coord (1,2) 를 색 7 로
    ast = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([1, 2])), color=PA.const(7))])
    out = PA.execute(json.loads(json.dumps(ast)), [[0, 0, 0], [0, 0, 0]])
    assert out == [[0, 0, 0], [0, 0, 7]]


def test_coord_ops_and_pixel_body():
    body = [PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(3))]
    ast = PA.program(body)
    assert PA._is_pixel_body(body) is True                 # coord 도 픽셀 body
    assert PA.ops_of_ast(ast) == [((0, 1), 3)]             # 좌표 튜플 키


def test_coord_antiunify_positional_comm_diff():
    # 두 pair: 같은 좌표(0,1) COMM, 색 DIFF → 색 slot
    a0 = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(3))])
    a1 = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])), color=PA.const(5))])
    sk, slots = PA.antiunify_ast([a0, a1])
    assert sk is not None and any(s["kind"] == "color" for s in slots.values())
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_coord_target.py -v`
Expected: FAIL — coord 타깃이 `//W` 로 깨지거나 `_is_pixel_body`/ops 가 coord 를 모름.

- [ ] **Step 3: program_ast 에 coord 지원 추가**

`arbor/reasoning/program_ast.py`:

`_is_pixel_body` 를:
```python
def _is_pixel_body(body):
    return bool(body) and all(s["args"]["target"].get("ref") in ("pixel", "coord") for s in body)
```

`_execute_pixel_body` 의 pixel/object 분기(`ix = _leaf_value(...)` 직전)에 coord 분기 추가 — `if tgt.get("ref") == "cellset":` 블록 바로 뒤, `ix = _leaf_value(tgt["index"], ...)` 앞에:
```python
        if tgt.get("ref") == "coord":                       # 리터럴 좌표 (r,c) 직접
            pos = _leaf_value(tgt["index"], grid_in, choice)
            if pos is None or col is None:
                continue
            r, c = pos
            if 0 <= r < H and 0 <= c < W:
                grid[r][c] = col
            continue
```

`ops_of_ast` 의 `else`(pixel/object) 분기를 coord 도 처리하도록:
```python
        else:
            idx_leaf = tgt["index"]
            idx = idx_leaf.get("const") if "const" in idx_leaf else None
            if isinstance(idx, list):                        # coord [r,c] → 해시가능 튜플 키
                idx = tuple(idx)
            ops.append((idx, col))
```

to_source contents 렌더(`coloring({tgt.get('ref')}[{...}])` 부분)에 coord 분기:
```python
        elif tgt.get("ref") == "coord":
            parts.append(f"coloring({tuple(tgt['index']['const'])}, color={col})")
        else:
            parts.append(f"coloring({tgt.get('ref')}[{_leaf_src(tgt['index'])}], color={col})")
```
(`if tgt.get("ref") == "cellset":` … `elif ref=="coord"` … `else` 순서로.)

`_antiunify_ast_pixel` 의 skeleton 조립(`body.append(step("coloring", target=ref("pixel", idx_leaf), color=col_leaf))`)이 coord 입력(ops 값이 튜플)일 때 coord 타깃을 내도록:
```python
        if isinstance(sk_idx, tuple):                        # coord 입력 → coord 스켈레톤(리터럴 유지)
            body.append(step("coloring", target=ref("coord", const(list(sk_idx))), color=col_leaf))
        else:
            body.append(step("coloring", target=ref("pixel", idx_leaf), color=col_leaf))
```
(`sk_idx` 가 None(=slot)이면 기존 `ref("pixel", var)` 그대로 — 비-이동 픽셀 slot 경로는 전체 스위트가 지킨다.)

- [ ] **Step 4: 통과 확인 + 회귀 게이트**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_coord_target.py -v`
Expected: PASS (3 passed)

Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `173 passed, 10 failed, 11 skipped` (기존 170 + 신규 3). **10 failed 불변**이 핵심(dormant 이라 solve 불변).

- [ ] **Step 5: 커밋**

```bash
git add arbor/reasoning/program_ast.py tests/test_coord_target.py
git commit -m "feat(ast): coloring ref('coord',[r,c]) 리터럴 좌표 타깃 지원(dormant)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 표시·러너 coord 지원 (dormant)

**Files:**
- Modify: `debugger/reports/program_viewer.py` (`_coloring_seq_lines` 또는 display_source 의 coloring 렌더, 러너 JS `runBody`/ATOM)
- Test: `tests/test_coord_display.py`

**Interfaces:**
- Consumes: coord AST(Task 1).
- Produces: display_source 가 coord 타깃을 `coloring(g, (r,c), color)` 로 렌더. 러너 JS 가 coord 타깃을 실행(격자 (r,c) 채색).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_coord_display.py`:
```python
import debugger.reports.program_viewer as pv
from arbor.reasoning import program_ast as PA


def test_display_source_renders_literal_coord():
    ast = PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([2, 8])), color=PA.const(0))])
    src = pv.display_source(ast)
    assert "(2, 8)" in src or "(2,8)" in src           # 리터럴 좌표 표기
    assert "cellset" not in src and "pixels_of" not in src
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_coord_display.py -v`
Expected: FAIL — display_source 가 coord 를 리터럴로 렌더 안 함.

- [ ] **Step 3: display_source + 러너 coord 렌더/실행**

`debugger/reports/program_viewer.py` 의 coloring 스텝 렌더 함수(`_coloring_seq_lines`, 픽셀/오브젝트/cellset 분기 있는 곳)에 coord 분기 추가 — cellset/pixel 분기 옆에:
```python
        elif ref == "coord":
            r, c = tgt["index"]["const"]
            lines.append(f"g = coloring(g, ({r}, {c}), {col})")
```
(정확한 변수명은 그 함수의 기존 pixel 분기(`{_ACCESSOR[ref]}(input_grid)[{idx}].coord`)와 나란히 맞춘다. cellset 은 `for ix in ...` 형태였음.)

러너 JS(`runBody`/ATOM 근처, `target.ref` 로 분기하는 곳)에 coord 실행:
```javascript
      } else if (t.ref === "coord") { var rc = t.index.const; g[rc[0]][rc[1]] = col;
```
(기존 pixel/cellset 실행 분기와 같은 위치. `col` 은 그 스텝의 색.)

- [ ] **Step 4: 통과 + Node 러너 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_coord_display.py -v`
Expected: PASS

Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `+1` (기존 대비 신규 1) passed, `10 failed` 불변.

- [ ] **Step 5: 커밋**

```bash
git add debugger/reports/program_viewer.py tests/test_coord_display.py
git commit -m "feat(report): display_source·러너 coord 타깃 렌더/실행 지원(dormant)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: compress → grouping slot, generalize 가 grouping 을 anti-unify

**Files:**
- Modify: `procedural_memory/operators/compress.py` (`_op_compress`)
- Modify: `procedural_memory/operators/generalize.py` (`_op_generalize`)
- Regenerate: `tests/fixtures/engine_golden.pkl`

**Interfaces:**
- Consumes: 기존 compress 의 blob(cellset) 산출.
- Produces: `(pair.node_id + ".property") ^grouping <cellset-AST>`; `PAIR.property.program` 은 픽셀 그대로. generalize 는 grouping 있으면 그걸, 없으면 program 을 anti-unify.

- [ ] **Step 1: `_op_compress` 를 grouping slot 으로**

`procedural_memory/operators/compress.py` `_op_compress` 안, PAIR.program 을 덮어쓰던 부분:
```python
        ag.wm.remove(ppid, "program", raw)     # was: code
        ag.wm.add(ppid, "program", blob)                  # pixel → blob(객체) program
```
를 아래로(program 유지, grouping 에 기록):
```python
        ag.wm.add(ppid, "grouping", blob)                 # 객체 grouping = 별도 아티팩트(PAIR.program 픽셀 유지)
```

- [ ] **Step 2: `_op_generalize` 가 grouping 우선 소비**

`procedural_memory/operators/generalize.py` `_op_generalize` 의 asts 수집 루프에서 `program` 만 읽던 것을 grouping 우선으로:
```python
    for p in getattr(root, "example_pairs", []) or []:
        ppid = f"{p.node_id}.property"
        v = next((v for (i, a, v) in ag.wm if i == ppid and a == "grouping"), None)   # 있으면 객체 grouping
        if v in (None, "{}"):
            v = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)  # 없으면 픽셀 program
        if v in (None, "{}"):
            continue
        progs.append(as_source(v))
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
```
(move-preempt `_all_pixel_residual(asts)` 는 첫 발화 때 program(픽셀)을 봄 — 이 루프가 grouping 미존재 시 program 을 담으므로 preempt 판정 보존. compress 후 재발화 땐 grouping 을 담아 blob anti-unify.)

- [ ] **Step 3: 60/60 + 예제pair cellset 부재 확인**

Run: `PYTHONHASHSEED=0 python -m debugger.score move`
Expected: `SCORE: 60/60`

Run (example pair PAIR.program 에 cellset 없어야):
```bash
PYTHONHASHSEED=0 python -c "
import sys; sys.path.insert(0,'.')
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve, clear_cache
clear_cache()
tid,p=list_tasks('move')[0]
r=run_solve(tid, load_task(p), max_cycles=500, use_cache=False)
T=f'T{tid}'
progs=[v for (i,a,v) in r['wm'] if i.endswith('.property') and a=='program' and i.startswith(T+'.P')]
groups=[v for (i,a,v) in r['wm'] if a=='grouping']
print('example PAIR.program 개수', len(progs), '| cellset 포함?', any('cellset' in (p or '') for p in progs))
print('grouping slot 개수', len(groups), '| cellset 포함?', any('cellset' in (g or '') for g in groups))
assert not any('cellset' in (p or '') for p in progs), 'PAIR.program 에 아직 cellset!'
assert any('cellset' in (g or '') for g in groups), 'grouping 에 cellset 있어야'
print('OK: cellset 은 grouping 에만, PAIR.program 은 픽셀')
"
```
Expected: `OK: cellset 은 grouping 에만, PAIR.program 은 픽셀`

- [ ] **Step 4: golden 재생성(의도적 갱신) + 전체 스위트**

solve WM 가 바뀌었으므로(신규 grouping slot) 구 engine golden 을 새 산출로 재생성한다(60/60·cellset-부재를 Step 3 에서 이미 확인 → 정당한 갱신):
```bash
PYTHONHASHSEED=0 python -c "
import pickle, sys; sys.path.insert(0,'.')
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve
sel=[list_tasks('easy_a')[0], list_tasks('move')[0], list_tasks('move')[1]]
out={}
for tid,p in sel:
    r=run_solve(tid, load_task(p), max_cycles=500, use_cache=False)
    out[tid]={'events':r['events'],'wm_states':r['wm_states']}
pickle.dump(out, open('tests/fixtures/engine_golden.pkl','wb'))
print('golden 재생성:', list(out))
"
```
Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `10 failed` 불변(신규 회귀 0). golden 테스트는 재생성돼 통과.

- [ ] **Step 5: 커밋**

```bash
git add procedural_memory/operators/compress.py procedural_memory/operators/generalize.py tests/fixtures/engine_golden.pkl
git commit -m "refactor(solver): compress→grouping slot, generalize 가 grouping 을 anti-unify

- PAIR.program 을 안 덮고 (pair.property ^grouping) 에 객체 blob 기록.
- generalize 는 grouping 우선(없으면 program) 소비 → cellset 은 TASK.solution 에만.
- move 60/60 불변, example PAIR.program 에서 cellset 제거. golden 재생성(의도적).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 픽셀 emit → 리터럴 coord + resolve 정합 + 리포트 확인

**Files:**
- Modify: `arbor/reasoning/program.py` (`_pixel_residual_program`)
- Modify: `procedural_memory/operators/coloring.py` (PIXEL emit)
- Modify: `procedural_memory/operators/generalize.py` (`_all_pixel_residual` — coord 인정)
- Modify: `procedural_memory/operators/compress.py` (`_blob_program` inner — coord 처리)
- Modify: `arbor/reasoning/antiunify.py` (`resolve_slot` src 경로 coord 정합)
- Regenerate: `tests/fixtures/engine_golden.pkl`

**Interfaces:**
- Produces: PAIR.program(픽셀)이 `coloring((r,c), 색)` 리터럴. move-preempt·blobify·resolve 가 coord 형식을 pixel-idx 와 동등 처리.

**중요(60/60 직결):** coord emit 후에도 move-preempt(`_all_pixel_residual`)·compress blobify(`_blob_program`)가 inner 를 픽셀 body 로 인식해야 compress 가 발화한다. 이동은 `_object_move_program`(격자 유래)로 grouping 하므로 `_blob_program` 은 fallback 이지만, `_all_pixel_residual` 은 이동 preempt 의 게이트라 필수.

- [ ] **Step 1: `_pixel_residual_program` 리터럴 좌표로**

`arbor/reasoning/program.py` `_pixel_residual_program` 의 body 생성:
```python
    body = [PA.step("coloring", target=PA.ref("coord", PA.const([r, c])), color=PA.const(g1[r][c]))
            for (r, c) in changed]
```

- [ ] **Step 2: `coloring.py` PIXEL emit 리터럴 좌표로**

`procedural_memory/operators/coloring.py` 의 body.append(pixel/object emit) 부분:
```python
        body.append(PA.step("coloring", target=PA.ref(level, PA.const(g0i)), color=PA.const(g1col)))
```
를 pixel 이면 좌표 리터럴로(single cell g0c[0]), object 면 기존대로:
```python
        if level == "pixel":
            (rr, cc) = g0c[0]
            body.append(PA.step("coloring", target=PA.ref("coord", PA.const([rr, cc])), color=PA.const(g1col)))
        else:
            body.append(PA.step("coloring", target=PA.ref(level, PA.const(g0i)), color=PA.const(g1col)))
```

- [ ] **Step 3: `_all_pixel_residual`·`_blob_program`·`resolve_slot` coord 정합**

(a) `procedural_memory/operators/generalize.py` `_all_pixel_residual` inner 검사(`ref == "pixel"`)를 coord 도 인정:
```python
        if not (inner and all(x["args"]["target"].get("ref") in ("pixel", "coord") for x in inner)):
            return False
```

(b) `procedural_memory/operators/compress.py` `_blob_program` inner op 추출(`if t["args"]["target"].get("ref") == "pixel"`)이 coord 도 idx 로 변환:
```python
        W_ = W
        ops = []
        for t in inner:
            tg = t["args"]["target"]
            if tg.get("ref") == "pixel":
                ops.append((tg["index"]["const"], t["args"]["color"]["const"]))
            elif tg.get("ref") == "coord":
                r_, c_ = tg["index"]["const"]
                ops.append((r_ * W_ + c_, t["args"]["color"]["const"]))
        if len(ops) != len(inner):
            return None
```
(기존 리스트컴프 한 줄을 위 루프로 교체. 이동은 `_object_move_program` 경로라 이 fallback 은 비-이동 blobify 용.)

(c) `arbor/reasoning/antiunify.py` `resolve_slot` 의 src targets 계산:
```python
    targets = [(vals[i] // len(train[i]["input"][0]), vals[i] % len(train[i]["input"][0]))
               for i in range(N)]
```
를 coord 튜플도 처리:
```python
    def _rc(v, W):
        return (tuple(v) if isinstance(v, (list, tuple)) else (v // W, v % W))
    targets = [_rc(vals[i], len(train[i]["input"][0])) for i in range(N)]
```

- [ ] **Step 4: 60/60 + 전체 스위트 + golden 재생성**

Run: `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60`
Seeds: `for s in 0 1 42; do PYTHONHASHSEED=$s python -m debugger.score move 2>&1 | tail -1; done` → 셋 다 60/60
golden 재생성(Task 3 Step 4 스크립트 재실행) → `pytest tests/ -q` → `10 failed` 불변.

- [ ] **Step 5: move 리포트 재생성 + 리터럴 좌표 확인**

```bash
PYTHONHASHSEED=0 python -m debugger.reports.program_viewer move
PYTHONHASHSEED=0 python -c "
import re, html as H
h=open('debugger/traces/move_program_report.html').read()
srcs=[H.unescape(s) for s in re.findall(r'<pre class=\"src\">(.*?)</pre>', h, re.S)]
lit=sum(1 for s in srcs if re.search(r'coloring\(g, \(\d+, ?\d+\),', s))
cell=sum(1 for s in srcs if 'cellset' in s)
print('리터럴 좌표 coloring 포함 src', lit, '| cellset 포함 src', cell)
assert lit>0, '리터럴 좌표 렌더 안 됨'
print('OK: Step A 리터럴 좌표(러너 실행가능), cellset 은 TASK.solution(Step C)만')
"
```
Expected: `OK: ...` (Step A 에 `coloring(g, (r, c), ..)`, cellset 은 Step C 에만)

- [ ] **Step 6: 커밋**

```bash
git add arbor/reasoning/program.py procedural_memory/operators/coloring.py arbor/reasoning/antiunify.py tests/fixtures/engine_golden.pkl
git commit -m "feat(solver): PAIR.program 픽셀 emit 을 리터럴 좌표(ref coord)로 + resolve 정합

- _pixel_residual_program·coloring PIXEL emit → coloring((r,c),색) 리터럴.
- resolve_slot src 경로가 coord 튜플/idx 둘 다 처리(비-이동 픽셀 정합).
- move 60/60(seed 0/1/42) 불변, Step A 리터럴·러너 실행가능. golden 재생성.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 범위 밖 (비목표)

- Part-2(op-body arg 규칙화), `task_section:614` tp 버그, golden fixture 크기(git-lfs) — 별건.
- object(비-이동) blob 경로의 리터럴화 — 이번 범위는 픽셀 좌표 + move grouping 이관.

## Self-Review 결과

- **Spec coverage**: §1 표현→Task1(ast)+Task2(표시)+Task4(emit) · §2 파이프라인→Task3 · §2b 정합성→Task4 Step3(resolve)+Task1(ops/antiunify) · §3 60/60→각 Task 게이트 · §4 결과→Task4 Step5. 누락 없음.
- **Placeholder scan**: 각 Step 에 실제 코드·명령·기대. TBD 없음.
- **Type consistency**: `ref("coord", const([r,c]))` 형식이 Task1(빌드/실행/ops)·Task2(표시/러너)·Task4(emit)에서 일치. grouping slot attr `"grouping"` 이 Task3 compress(쓰기)·generalize(읽기) 일치.
- **golden 처리**: solve WM 를 바꾸는 Task3·4 가 각각 golden 재생성(60/60·cellset-부재 확인 후) → 스위트 10 failed 유지.
