# _grid_decide delta-const 우선 해소 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_grid_decide` 가 여러 후보 중 delta-const 예측을 우선 채택하게 해 move size 를 AMBIGUOUS→DECIDE(keep) 로 만들고, skeleton·대시보드의 `pending:size` 를 뿌리에서 없앤다.

**Architecture:** size/color 의 `decision`/`value` 계산을 `_dec(preds)` 에서 `_resolve_decision(cands)`(delta-const 우선)로 교체 + category 노출. move 흐름 불변(여전히 contents 로 하강), 답은 grouping/TASK.solution.

**Tech Stack:** Python 3, pytest.

## Global Constraints

- move 60/60 유지 — `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60` (seed 0/1/42)
- 전체 pytest 신규 회귀 0 (현재 기준선 `182 passed, 10 failed, 11 skipped`; 10=pre-existing). solve WM 형식 바뀌면 `tests/fixtures/engine_golden.pkl` 을 60/60·pending-부재 확인 후 태스크 안에서 재생성.
- 답(TASK.solution 실행) 불변. 대시보드/skeleton 에서 `pending:size` 제거.
- 새 operator/DSL 금지. 내부 kind 문자열(KEEP/CONST/MAP/SET-MAP) 유지(`_size_leaf` 등이 파싱).
- 커밋 트레일러: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `_resolve_decision`(delta 우선) + `_grid_decide` size/color 교체

**Files:**
- Modify: `arbor/reasoning/program.py` (`_grid_decide` size·color decision/value, 새 헬퍼 `_resolve_decision`·`_cat`)
- Test: `tests/test_delta_priority.py`
- Regenerate: `tests/fixtures/engine_golden.pkl`

**Interfaces:**
- Produces: `_resolve_decision(cands) -> (decision, value, category)` where cands=`[(kind, pred, ok)]`; delta-const(kind≠"CONST") 예측 우선, 없으면 output-const(CONST). 단일 예측 DECIDE(value), delta끼리 갈림 AMBIGUOUS, 없음 DESCEND. `_cat(kind) = "output-const" if kind=="CONST" else "delta-const"`.
- `_grid_decide` 반환의 size/color dict 에 `"category"` 필드 추가(채택 카테고리).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_delta_priority.py`:
```python
from arbor.reasoning.program import _resolve_decision, _grid_decide
from arbor.env.dataset import list_tasks, load_task


def test_delta_beats_output_const():
    # KEEP(delta,(5,5)) vs CONST(output,(8,8)) → delta 우선 DECIDE(5,5)
    dec, val, cat = _resolve_decision([("KEEP", (5, 5), True), ("CONST", (8, 8), True)])
    assert dec == "DECIDE" and val == (5, 5) and cat == "delta-const"


def test_output_const_when_no_delta():
    dec, val, cat = _resolve_decision([("CONST", (3, 3), True)])
    assert dec == "DECIDE" and val == (3, 3) and cat == "output-const"


def test_deltas_disagree_ambiguous():
    dec, val, cat = _resolve_decision([("KEEP", (5, 5), True), ("MAP[x]", (6, 6), True)])
    assert dec == "AMBIGUOUS" and val is None


def test_empty_descend():
    assert _resolve_decision([("KEEP", (5, 5), False)]) == ("DESCEND", None, None)


def test_move_size_decides_keep_not_pending():
    tid, p = list_tasks("move")[0]
    t = load_task(p)
    dec = _grid_decide(t["train"], t["test"][0]["input"])
    assert dec["size"]["decision"] == "DECIDE"                      # AMBIGUOUS 아님
    assert dec["size"]["value"] == (len(t["test"][0]["input"]), len(t["test"][0]["input"][0]))  # keep=test 입력크기
    assert dec["size"]["category"] == "delta-const"
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_delta_priority.py -v`
Expected: FAIL — `_resolve_decision` 없음 / move size 가 AMBIGUOUS.

- [ ] **Step 3: 구현**

`arbor/reasoning/program.py` 에 헬퍼 추가(`_dec` 근처):
```python
def _cat(kind):
    """후보 kind → 카테고리: output-const(출력값 일치=CONST) / delta-const(변화 일관=KEEP/MAP/SET-MAP)."""
    return "output-const" if kind == "CONST" else "delta-const"


def _resolve_decision(cands):
    """valid 후보 중 **delta-const 예측 우선**(구조적 일반화 > 표면 출력일치). 단일 예측 → DECIDE(값),
    여럿(delta 끼리 갈림) → AMBIGUOUS, 없음 → DESCEND. 반환 (decision, value, category)."""
    valid = [(k, v) for k, v, ok in cands if ok]
    if not valid:
        return "DESCEND", None, None
    delta = [(k, v) for k, v in valid if k != "CONST"]
    pool = delta if delta else valid                         # delta 있으면 delta, 없으면 output(CONST)
    cat = "delta-const" if delta else "output-const"
    preds = {v for _, v in pool}
    if len(preds) == 1:
        return "DECIDE", next(iter(preds)), cat
    return "AMBIGUOUS", None, cat
```

`_grid_decide` 의 size dict 계산을:
```python
    out["size"] = {"type": "NUMBER", "within": [sz(i) == sz(o) for i, o in pairs],
                   "cands": cs, "decision": _dec(preds), "value": (next(iter(preds)) if len(preds) == 1 else None)}
```
를:
```python
    dsz, vsz, csz = _resolve_decision(cs)
    out["size"] = {"type": "NUMBER", "within": [sz(i) == sz(o) for i, o in pairs],
                   "cands": cs, "decision": dsz, "value": vsz, "category": csz}
```

color dict 도 동일하게:
```python
    out["color"] = {"type": "SET", "within": [a == b for a, b in zip(ci, co)],
                    "cands": cp, "decision": _dec(preds), "value": (next(iter(preds)) if len(preds) == 1 else None),
                    "map": gm if (gm and any(k != v for k, v in gm.items())) else None}
```
를:
```python
    dco, vco, cco = _resolve_decision(cp)
    out["color"] = {"type": "SET", "within": [a == b for a, b in zip(ci, co)],
                    "cands": cp, "decision": dco, "value": vco, "category": cco,
                    "map": gm if (gm and any(k != v for k, v in gm.items())) else None}
```
(`preds` 지역변수는 이제 안 읽히지만 후보 생성 코드는 그대로 — cands `cs`/`cp` 에 kind 가 다 담긴다. `_dec` 는 삭제하지 않는다(회귀 위험 회피).)

- [ ] **Step 4: 통과 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_delta_priority.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 60/60 + 전체 스위트 + golden 재생성**

Run: `PYTHONHASHSEED=0 python -m debugger.score move` → `SCORE: 60/60`
Seeds: `for s in 0 1 42; do PYTHONHASHSEED=$s python -m debugger.score move 2>&1 | tail -1; done` → 셋 다 60/60. 하나라도 깨지면 STOP.

golden 재생성(60/60 확인 후, Step 5 스크립트 재사용):
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
Expected: `10 failed` 불변(신규 회귀 0), passed = 기존 + 신규 5.

- [ ] **Step 6: 대시보드 재생성 + `pending:size` 제거 확인**

```bash
PYTHONHASHSEED=0 python -m debugger.build move
PYTHONHASHSEED=0 python -c "
h=open('debugger/traces/move_dashboard.html').read()
n=h.count('{\"pending\": \"size\"}')
n2=h.count('pending')   # RETE match 주석의 'pending' 포함(무관, 참고용)
print('skeleton pending:size 개수:', n, '| 전체 pending 문자열(주석포함):', n2)
assert n==0, 'skeleton 에 아직 pending:size!'
print('OK: 대시보드에서 pending:size 뿌리 제거')
"
```
Expected: `OK: 대시보드에서 pending:size 뿌리 제거` (skeleton pending:size = 0)

- [ ] **Step 7: 커밋**

```bash
git add arbor/reasoning/program.py tests/test_delta_priority.py tests/fixtures/engine_golden.pkl
git commit -m "feat(solver): _grid_decide delta-const 우선 해소 — move size DECIDE(keep), pending 뿌리 제거

- _resolve_decision: valid 후보 중 delta-const(KEEP/MAP/SET-MAP) 예측 우선, 없으면 output-const.
- move size AMBIGUOUS→DECIDE(keep=test입력크기) → skeleton size pending→size(input_grid) → 대시보드 pending:size 제거.
- move 흐름·60/60 불변(여전히 contents 하강). size/color 에 category 노출. golden 재생성.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 범위 밖 (비목표)

- version-space(genuine delta 타이), `_grid_decide` 완전 이관, color SET-MAP delta 구조화 — 이후.
- 카테고리 이름의 대시보드/리포트 표시 반영(verdict 문자열 병기) — 이번엔 데이터(category 필드)만; 표시는 필요 시 후속.

## Self-Review 결과

- **Spec coverage**: §1 해소규칙→Step3(_resolve_decision) · §2 pending제거→Step6(대시보드) · §3 60/60→Step5 · §4 category→Step3(필드) · §7 검증→Step5/6. 누락 없음.
- **Placeholder scan**: 각 Step 실제 코드·명령·기대. TBD 없음.
- **Type consistency**: `_resolve_decision(cands)->(decision,value,category)` 가 Step1 테스트·Step3 구현·Step3 wire-in 에서 일치. cands 튜플 `(kind,pred,ok)` 형태 유지(소비자 무손상).
