# PAIR.program size/color per-pair 리터럴화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PAIR.program 의 size/color leaf 를 그 pair 출력의 리터럴 const 로 바꿔 move 의 `set_grid_size({"pending":"size"})` 아티팩트를 없앤다.

**Architecture:** 부분-하강(move/c–h) PAIR.program 을 조립하는 `verify._assemble_pair_program` 에서 skeleton 의 size/color leaf(pending/expr)를 그 pair(`pair_cursor`) 출력의 리터럴 const 로 교체. `_execute_grid` 은 contents 로만 출력을 결정하므로(size/color=선언) 답·60/60 무영향.

**Tech Stack:** Python 3, program_ast(AST-json), pytest.

## Global Constraints

- move 60/60 유지 — `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60` (seed 0/1/42)
- 전체 pytest 신규 회귀 0 (현재 기준선 `180 passed, 10 failed, 11 skipped`; 10 = pre-existing). solve WM 형식이 바뀌면 `tests/fixtures/engine_golden.pkl` 을 태스크 안에서 60/60·pending-부재 확인 후 재생성.
- 답(TASK.solution 실행) 불변. size/color 는 실행에 안 쓰임(선언 전용). PAIR.program 은 답 경로 아님(move 답=grouping/TASK.solution).
- 새 operator/DSL 금지. 리터럴 const 는 a/b CONST 경로가 이미 쓰는 형식 재사용.
- 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: PAIR.program size/color 를 per-pair 리터럴로 + 표시 정리

**Files:**
- Modify: `procedural_memory/operators/verify.py` (`_assemble_pair_program`, 새 헬퍼 `_literal_grid_props`)
- Modify: `debugger/reports/program_viewer.py` (`_grid_leaf_repr` — const size 를 `(H, W)` 로)
- Test: `tests/test_literal_gridprops.py`
- Regenerate: `tests/fixtures/engine_golden.pkl`

**Interfaces:**
- Produces: `verify._literal_grid_props(out) -> (size_leaf, color_leaf)` where `size_leaf = PA.const({"height":H,"width":W})`, `color_leaf = PA.const(sorted(colorset))`. `_assemble_pair_program` replaces the skeleton's `set_grid_size`/`set_grid_color` leaves with these for the current pair.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_literal_gridprops.py`:
```python
import json
from arbor.reasoning import program_ast as PA
from procedural_memory.operators.verify import _literal_grid_props


def test_literal_grid_props_from_output():
    out = [[0, 3, 3], [0, 0, 0]]                        # 2x3, 색 {0,3}
    size_leaf, color_leaf = _literal_grid_props(out)
    assert size_leaf == PA.const({"height": 2, "width": 3})
    assert color_leaf == PA.const([0, 3])              # sorted 색집합


def test_assembled_program_has_literal_size_not_pending():
    # skeleton(size=pending·color=pending·contents=pending) + 하강 coloring body → 조립 결과가
    # 그 pair 출력의 리터럴 size/color 를 갖고, pending 이 없어야 한다.
    import procedural_memory.operators.verify as V
    sk = PA.grid_program(PA.pending("size"), PA.pending("color"),
                         PA.set_grid_contents(PA.pending("contents"))["args"]["contents"])
    code = json.dumps(PA.program([PA.step("coloring", target=PA.ref("coord", PA.const([0, 1])),
                                          color=PA.const(3))]))

    class _Ag:
        task = {"train": [{"input": [[0, 0, 0], [0, 0, 0]], "output": [[0, 3, 0], [0, 0, 0]]}]}
        stack = []
        wm = []
    ag = _Ag()
    # grid-skeleton 을 조상 substate 대신 직접 주입하도록 monkeypatch (_find_grid_skeleton)
    V._find_grid_skeleton = lambda a: json.dumps(sk)
    V.pair_cursor = lambda a: 0
    out = json.loads(V._assemble_pair_program(ag, code))
    parts = {s["call"]: s["args"] for s in out["body"]}
    assert parts["set_grid_size"]["size"] == PA.const({"height": 2, "width": 3})   # 출력 [[0,3,0],[0,0,0]] = 2x3
    assert parts["set_grid_color"]["color"] == PA.const([0, 3])                    # 색집합 {0,3}
    assert "pending" not in json.dumps(out)
```
(주: 두 번째 테스트는 `_find_grid_skeleton`/`pair_cursor` 를 monkeypatch 해 WM 의존을 제거한다. `grid_program(pending,pending,contents_leaf)` 로 pending skeleton 을 만든다.)

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_literal_gridprops.py -v`
Expected: FAIL — `_literal_grid_props` 없음 / 조립 결과에 pending 남음.

- [ ] **Step 3: `_literal_grid_props` + `_assemble_pair_program` 구현**

`procedural_memory/operators/verify.py` 에 헬퍼 추가:
```python
def _literal_grid_props(out):
    """그 pair 출력의 리터럴 size/color leaf (예측·pending 아님 — 실제값). size/color 는 실행에
    안 쓰이는 '선언'(§Round-3 Grid 객체모델)이므로 답 무관 — PAIR.program 을 구체(literal)로 정직화."""
    from arbor.reasoning import program_ast as PA
    colorset = sorted({v for row in out for v in row})
    return (PA.const({"height": len(out), "width": len(out[0])}), PA.const(colorset))
```

`_assemble_pair_program` 의 body 조립 루프를 size/color 도 교체하도록:
```python
    k = pair_cursor(ag)
    out_grid = ag.task["train"][k]["output"]
    size_leaf, color_leaf = _literal_grid_props(out_grid)
    body = []
    for s in gp.get("body") or []:
        call = s.get("call")
        if call == "set_grid_size":
            s = PA.set_grid_size(size_leaf)                # per-pair 리터럴(pending/expr 대체)
        elif call == "set_grid_color":
            s = PA.set_grid_color(color_leaf)
        elif call == "set_grid_contents":
            leaf = (s.get("args") or {}).get("contents")
            if isinstance(leaf, dict) and "pending" in leaf:
                s = PA.set_grid_contents(PA.contents_program(coloring_body))
        body.append(s)
    return json.dumps(dict(gp, body=body))
```

- [ ] **Step 4: display const size 를 `(H, W)` 로**

`debugger/reports/program_viewer.py` `_grid_leaf_repr` 의 const 분기:
```python
        if isinstance(v, dict) and "height" in v:
            return f"{{height:{v['height']}, width:{v['width']}}}"
```
를:
```python
        if isinstance(v, dict) and "height" in v:
            return f"({v['height']}, {v['width']})"        # 리터럴 크기값 (사용자: '(8,8) 같은 값')
```

- [ ] **Step 5: 통과 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_literal_gridprops.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 60/60 + pending 부재 + 전체 스위트 (+ golden 재생성)**

Run: `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60`

Run (move PAIR.program 에 pending 없고 size 가 const):
```bash
PYTHONHASHSEED=0 python -c "
import sys, json; sys.path.insert(0,'.')
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve, clear_cache
clear_cache()
tid,p=list_tasks('move')[0]
r=run_solve(tid, load_task(p), max_cycles=500, use_cache=False)
T=f'T{tid}'
progs=[v for (i,a,v) in r['wm'] if a=='program' and i.startswith(T+'.P') and 'Pa' not in i]
import re
bad=[v for v in progs if '\"pending\"' in v]
print('예제 PAIR.program', len(progs), '| pending 포함', len(bad))
# size 가 const height/width 인지
for v in progs[:1]:
    ast=json.loads(v); parts={s['call']:s['args'] for s in ast['body']}
    print('set_grid_size leaf =', json.dumps(parts['set_grid_size']['size']))
assert not bad, 'PAIR.program 에 아직 pending!'
print('OK: pending 부재, size 리터럴')
"
```
Expected: `OK: pending 부재, size 리터럴` (set_grid_size leaf = `{"const": {"height": 8, "width": 8}}`)

golden 재생성(60/60·pending-부재 확인 후):
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
pickle.dump(out, open('tests/fixtures/engine_golden.pkl','wb')); print('golden 재생성', list(out))
"
```
Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `10 failed` 불변 (신규 회귀 0), passed = 기존 + 신규 2.

- [ ] **Step 7: move 리포트 재생성 + 시각 확인**

```bash
PYTHONHASHSEED=0 python -m debugger.reports.program_viewer move
PYTHONHASHSEED=0 python -c "
import re, html as H
h=open('debugger/traces/move_program_report.html').read()
srcs=[H.unescape(s) for s in re.findall(r'<pre class=\"src\">(.*?)</pre>', h, re.S)]
lit=sum(1 for s in srcs if re.search(r'g\.size = set_grid_size\(\(\d+, \d+\)\)', s))
pend=sum(1 for s in srcs if 'pending' in s)
print('g.size=(H, W) 리터럴 src', lit, '| pending 포함 src', pend)
assert lit>0 and pend==0, '리터럴 size 안 뜨거나 pending 잔존'
print('OK: Step A g.size=(8, 8) 리터럴, pending 부재')
"
```
Expected: `OK: Step A g.size=(8, 8) 리터럴, pending 부재`

- [ ] **Step 8: 커밋**

```bash
git add procedural_memory/operators/verify.py debugger/reports/program_viewer.py tests/test_literal_gridprops.py tests/fixtures/engine_golden.pkl
git commit -m "feat(solver): PAIR.program size/color 를 per-pair 리터럴로 (pending 아티팩트 제거)

- _assemble_pair_program 이 skeleton 의 size/color(pending/expr)를 그 pair 출력의 리터럴 const 로 교체.
- size/color 는 _execute_grid 이 안 읽는 선언이라 답·60/60 무영향. display const size → (H, W).
- move Step A 에서 set_grid_size({pending}) 사라지고 g.size=(8,8) 리터럴. golden 재생성.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 범위 밖 (비목표)

- full 경로(a/b) size/color 리터럴화 — 게이트 밖, 현행 유지.
- output-const/delta-const 재분류 + delta 우선 + ambiguous 해소 — spec #2.
- `_grid_decide` test-예측 로직의 TASK.solution 층 정돈 — spec #2.

## Self-Review 결과

- **Spec coverage**: §1 목표(리터럴 size/color)→Task1 Step3 · §2 안전(execute=contents)→근거로 Step6 60/60 · §3 범위(_assemble_pair_program)→Task1 · §4 결과(표시)→Step4+Step7 · §5 검증→Step6/7. 누락 없음.
- **Placeholder scan**: 각 Step 실제 코드·명령·기대. TBD 없음.
- **Type consistency**: `_literal_grid_props` 반환(size=const dict height/width, color=const sorted list)이 Step1 테스트·Step3 구현·Step6 확인에서 일치. display `(H,W)` 형식이 Step4·Step7 일치.
