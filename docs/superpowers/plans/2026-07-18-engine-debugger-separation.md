# 실행 엔진 ↔ 디버거 분리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ARBOR 솔버 실행을 방출/시각화에서 떼어내, 채점은 방출 비용 0으로 빠르게 돌고 디버거는 journal 을 시간순 replay 해 대시보드를 재구성하게 만든다.

**Architecture:** 제자리 재구성(A안) — 사이클 로직(`_Tracer.run`, 하강·ONC·arg-substate)은 물리적으로 안 옮긴다. 방출 지점에 sink 이음새를 넣어(NullSink=headless, JournalSink=debug), WM 스냅샷을 event-sourcing 델타로 바꾸고, HTML 데이터 재구성을 순수 Renderer 로 분리한다. 출력 계약(events/wm_states)을 고정한 채 내부만 바꿔 60/60 을 보존한다.

**Tech Stack:** Python 3, 자체 SOAR 커널(`soar/`), pytest.

## Global Constraints

- move 60/60 유지 (검증: `PYTHONHASHSEED` 0/1/42 모두 60/60)
- 전체 pytest 신규 회귀 0 (기존 10 실패 = easy_a 미해결·낡은 트레이스 스키마, 동일 유지)
- `debugger/dashboard.py`·`_HTML`·`make_dashboard` 불변 — Renderer 는 기존 `events`/`wm_states` 자료구조를 그대로 재생산
- 새 operator/DSL/property 만들지 않음 (ARBOR_HARNESS §1-1) — 이 작업은 인프라 분리만
- 커밋 메시지 끝에: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: WM journal 훅 (stage a — 동작 중립)

**Files:**
- Modify: `soar/wm.py` (`__init__`, `add`, `remove`)
- Test: `tests/test_wm_journal.py`

**Interfaces:**
- Produces: `WorkingMemory.journal` (기본 None). None 이 아니면 `add`→`("+",(i,a,v))`, `remove`→`("-",(i,a,v))` 를 append. 실제 상태 변경(신규 add / 존재하던 remove)일 때만 append.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_wm_journal.py`:
```python
from soar.wm import WorkingMemory


def test_journal_none_by_default_no_error():
    wm = WorkingMemory()
    assert wm.journal is None
    wm.add("S1", "x", 1)          # journal=None 이어도 안전
    wm.remove("S1", "x", 1)


def test_journal_records_only_real_mutations():
    wm = WorkingMemory()
    log = []
    wm.journal = log
    wm.add("S1", "x", 1)          # 신규 → 기록
    wm.add("S1", "x", 1)          # 중복 → 무기록(WM 셋 의미)
    wm.remove("S1", "x", 1)       # 존재 → 기록
    wm.remove("S1", "x", 1)       # 이미 없음 → 무기록
    assert log == [("+", ("S1", "x", 1)), ("-", ("S1", "x", 1))]
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_wm_journal.py -v`
Expected: FAIL — `AttributeError: 'WorkingMemory' object has no attribute 'journal'`

- [ ] **Step 3: 구현**

`soar/wm.py` `__init__` 끝에 추가:
```python
        self.journal: "list | None" = None       # debug 시 JournalSink 가 붙임; None=headless(무비용)
```

`add` 를 다음으로:
```python
    def add(self, identifier: str, attr: str, value: Any) -> Triple:
        w = (identifier, attr, value)
        if w not in self._wmes:
            self._wmes.add(w)
            self._invalidate()                           # 반복순서·인덱스 캐시 무효화(§2-6)
            if self.journal is not None:                 # event-sourcing(디버그): 실제 변경만
                self.journal.append(("+", w))
        return w
```

`remove` 를 다음으로:
```python
    def remove(self, identifier: str, attr: str, value: Any) -> bool:
        w = (identifier, attr, value)
        if w in self._wmes:
            self._wmes.discard(w)
            self._invalidate()                           # 반복순서·인덱스 캐시 무효화(§2-6)
            if self.journal is not None:
                self.journal.append(("-", w))
            return True
        return False
```

- [ ] **Step 4: 통과 확인 + 회귀 게이트**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_wm_journal.py -v`
Expected: PASS (2 passed)

Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: 신규 실패 없음 — `165 passed, 10 failed, 11 skipped` (기존과 동일)

- [ ] **Step 5: 커밋**

```bash
git add soar/wm.py tests/test_wm_journal.py
git commit -m "feat(wm): 선택적 journal 훅 (event-sourcing 기반, 기본 None=무비용)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: golden 고정 + sink 라우팅 (stage b — 스냅샷 그대로, byte 동일)

**Files:**
- Create: `arbor/engine/sink.py`
- Create: `tests/fixtures/engine_golden.pkl` (pickle — WM 의 grid 튜플이 JSON 라운드트립에서 list 로 깨지는 것 방지, solve_cache 와 동일 이유)
- Modify: `arbor/engine/trace.py` (`_Tracer.__init__`, `emit`, `run` 반환)
- Test: `tests/test_engine_renderer.py`

**Interfaces:**
- Consumes: `WorkingMemory.journal` (Task 1).
- Produces:
  - `arbor.engine.sink.NullSink`: `event(*a, **k)` no-op; 클래스속성 `events=[]`, `_wm_states=[]`.
  - `arbor.engine.sink.JournalSink(agent)`: `event(phase, kind, label, cycle, goal_stack, highlight=None, detail=None, rule=None, wave=None)`. stage b 에서는 즉시 full 스냅샷+dedup 해 `self.events`(list) / `self._wm_states`(list) 를 채운다. 이벤트 dict 스키마 = 기존 `_Tracer.emit` 과 동일.
  - `_Tracer(task, tid, setup, sink=None)`: `sink` None → `JournalSink(self.ag)`. `_Tracer.events`/`_Tracer._wm_states` = sink 의 것(property). `run()` 은 `self.events` 반환.

- [ ] **Step 1: golden 캡처(리팩터 전 코드로) + 커밋**

`tests/fixtures/` 없으면 만들고, 아래 스크립트를 1회 실행해 fixture 생성(pickle — 튜플 보존):
```bash
mkdir -p tests/fixtures
PYTHONHASHSEED=0 python -c "
import pickle, sys; sys.path.insert(0,'.')
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve
sel = [list_tasks('easy_a')[0], list_tasks('move')[0], list_tasks('move')[1]]
out = {}
for tid,p in sel:
    r = run_solve(tid, load_task(p), max_cycles=500, use_cache=False)
    out[tid] = {'events': r['events'], 'wm_states': r['wm_states']}
pickle.dump(out, open('tests/fixtures/engine_golden.pkl','wb'))
print('golden tids:', list(out))
"
```
Expected 출력: `golden tids: ['<easy_a id>', 'move000a', 'move000b']`
```bash
git add -f tests/fixtures/engine_golden.pkl
git commit -m "test(engine): 리팩터 전 events/wm_states golden 고정(easy_a·move000a·move000b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(`git add -f` — `tests/fixtures/` 가 .gitignore 대상일 수 있어 강제 추가. 아니면 `-f` 무해.)

- [ ] **Step 2: 특성화 테스트 작성(지금 green, 리팩터 내내 유지)**

`tests/test_engine_renderer.py`:
```python
import os, pickle
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve

_GOLD = pickle.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "engine_golden.pkl"), "rb"))
_PATHS = {tid: p for ds in ("easy_a", "move") for tid, p in list_tasks(ds)}


def _run(tid):
    return run_solve(tid, load_task(_PATHS[tid]), max_cycles=500, use_cache=False)


def test_debug_output_matches_golden():
    for tid, g in _GOLD.items():
        r = _run(tid)
        assert r["events"] == g["events"], f"{tid} events 불일치"
        assert r["wm_states"] == g["wm_states"], f"{tid} wm_states 불일치"
```

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_engine_renderer.py -v`
Expected: PASS (리팩터 전이라 당연히 일치 — 이후 모든 stage 에서 이 green 을 유지하는 게 게이트)

- [ ] **Step 3: sink 모듈 작성**

`arbor/engine/sink.py`:
```python
# -*- coding: utf-8 -*-
"""ARBOR engine sinks — 실행(Engine)과 방출(디버거)을 잇는 이음새.

Engine(_Tracer.run 사이클)은 방출 지점마다 sink.event(...) 만 호출한다(의존성 역전).
NullSink = headless(채점·대량; 비용 0). JournalSink = debug.
(stage b: JournalSink 는 기존 emit 과 동일하게 full 스냅샷+dedup — byte 동일 검증용.
 stage c 에서 event-sourcing 델타 + Renderer 로 교체.)"""
from __future__ import annotations

from soar.wm import _wm_key


class NullSink:
    """headless: 방출 no-op. wm.journal 도 안 붙여 실행이 방출 비용을 전혀 안 낸다."""
    events: list = []
    _wm_states: list = []

    def event(self, *a, **k):
        pass


class JournalSink:
    """debug(stage b): 기존 _Tracer.emit 로직을 그대로 옮긴 것 — full 스냅샷 + 연속 동일 dedup."""
    def __init__(self, agent):
        self.ag = agent
        self.events: list = []
        self._wm_states: list = []
        self._last_key = None
        self._last_si = -1

    def event(self, phase, kind, label, cycle, goal_stack,
              highlight=None, detail=None, rule=None, wave=None):
        wm = [list(t) for t in self.ag.wm]           # wm.__iter__ 는 이미 결정적 정렬순(_wm_key)
        key = tuple(tuple(t) for t in wm)
        if key == self._last_key:
            si = self._last_si
        else:
            si = len(self._wm_states)
            self._wm_states.append(wm)
            self._last_key, self._last_si = key, si
        self.events.append({
            "seq": len(self.events), "phase": phase, "kind": kind, "label": label,
            "cycle": cycle, "wave": wave, "highlight": highlight or [],
            "wm_state": si, "goal_stack": list(goal_stack), "detail": detail, "rule": rule,
        })
```

- [ ] **Step 4: `_Tracer` 를 sink 로 라우팅**

`arbor/engine/trace.py` `_Tracer.__init__`: `self.events = []` 줄을 제거하고 sink 를 만든다. `self.ag = setup(...)` **뒤**에:
```python
        from arbor.engine.sink import JournalSink
        self.sink = sink if sink is not None else JournalSink(self.ag)
```
그리고 `__init__` 시그니처에 `sink=None` 추가:
```python
    def __init__(self, task, tid="0a", setup=None, sink=None):
```
`_Tracer` 클래스에 property 추가(기존 `self.events`/`self._wm_states` 소비처 호환):
```python
    @property
    def events(self):
        return self.sink.events

    @property
    def _wm_states(self):
        return self.sink._wm_states
```
기존 `emit` 본문 전체를 아래로 교체(스냅샷 로직은 sink 로 이동):
```python
    def emit(self, phase, kind, label, highlight=None, detail=None, rule=None, wave=None):
        self.sink.event(phase, kind, label, self.cycle, [g.id for g in self.ag.stack],
                        highlight=highlight, detail=detail, rule=rule, wave=wave)
```
`run()` 의 `return self.events` 는 property 로 그대로 동작(변경 불필요).

- [ ] **Step 5: 통과 확인 + 회귀 게이트**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_engine_renderer.py -v`
Expected: PASS — sink 라우팅 후에도 events/wm_states 가 golden 과 byte 동일.

Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `165 passed, 10 failed, 11 skipped` (기존 동일)

- [ ] **Step 6: 커밋**

```bash
git add arbor/engine/sink.py arbor/engine/trace.py tests/test_engine_renderer.py
git commit -m "refactor(engine): 방출을 sink 이음새로 분리(NullSink/JournalSink) — 출력 byte 불변

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: event-sourcing 델타 + Renderer (stage c)

**Files:**
- Create: `arbor/engine/renderer.py`
- Modify: `arbor/engine/sink.py` (`JournalSink` 을 델타 기록으로; `NullSink` 에 빈 `seed`/`wm_log`/`raw_events`)
- Modify: `arbor/engine/trace.py` (`_Tracer.events`/`_wm_states` 를 **lazy render+memoize** property 로, `run()` 반환 유지)
- Test: `tests/test_engine_renderer.py` (기존 golden 테스트가 게이트)

**Interfaces:**
- Consumes: `WorkingMemory.journal`(Task 1), golden 테스트(Task 2).
- Produces:
  - `JournalSink(agent)`: `seed`(부착 시점 WM list), `wm_log`(=agent.wm.journal), `raw_events`(list of dict: phase/kind/label/cycle/wave/highlight/detail/rule/goal_stack/cursor). `event(...)` 은 cursor=`len(self.wm_log)` 만 기록(스냅샷 없음).
  - `NullSink`: `seed=[]`, `wm_log=[]`, `raw_events=[]` (render 가 빈 결과를 내도록) + `event()` no-op.
  - `arbor.engine.renderer.render(sink) -> (events, wm_states)`: seed 에서 시작해 각 이벤트 cursor 까지 델타 replay → 그 시점 WM 복원, 연속 동일 dedup. 반환 자료구조 = 기존과 동일.
  - `_Tracer.events`/`_Tracer._wm_states`: **lazy render+memoize** property (`self.sink` 을 render → 캐시). `run()` 은 `return self.events` 유지. 기존 소비자(`debugger/solve_cache.py`, `debugger/dashboard.py:fine_trace`, `debugger/reports/*`)가 **무변경**으로 계속 동작.

> **설계 주의(중요):** Task 2 는 `_Tracer.events`/`_wm_states` 를 `self.sink.events` 로 직접 위임하는 property 로 만들었다. 델타 `JournalSink` 은 그 리스트가 없으므로, **삭제하지 말고** journal 을 render 해 주는 lazy property 로 바꾼다. `debugger/dashboard.py`(fine_trace, line 98-100)와 `debugger/reports/*` 가 `_Tracer` 를 직접 만들어 `tr.run()` 반환·`tr._wm_states` 를 쓰므로, 이 인터페이스를 유지해야 그것들이 안 깨진다(스펙 "dashboard.py 불변"). `solve_cache` 도 이 property 로 그대로 동작 → **Task 3 는 solve_cache 를 건드리지 않는다**(Task 4 에서 mode 만 추가).

- [ ] **Step 1: Renderer 작성**

`arbor/engine/renderer.py`:
```python
# -*- coding: utf-8 -*-
"""ARBOR engine renderer — journal(JournalSink) → dashboard 가 쓰는 events + wm_states.

순수 함수: 실행을 모르고 journal 만 본다. seed WM(부착 시점)에서 시작해 각 이벤트 cursor
까지의 WM 델타를 시간순 적용해 그 시점 WM 을 복원하고, 안 바뀌면 직전 인덱스 재사용(dedup).
결과 자료구조는 기존 _Tracer.emit 산출과 동일."""
from __future__ import annotations

from soar.wm import _wm_key


def render(sink):
    """JournalSink → (events, wm_states). events[i]['wm_state'] = wm_states 인덱스."""
    running = set(tuple(t) for t in sink.seed)      # 부착 전 초기 WM(S1/io 마커)
    wm_states, events = [], []
    last_key, last_si, pos = None, -1, 0
    for e in sink.raw_events:
        while pos < e["cursor"]:                    # 이 이벤트 시점까지 델타 적용
            sign, triple = sink.wm_log[pos]
            if sign == "+":
                running.add(triple)
            else:
                running.discard(triple)
            pos += 1
        snap = sorted([list(t) for t in running], key=_wm_key)
        key = tuple(tuple(t) for t in snap)
        if key == last_key:
            si = last_si
        else:
            si = len(wm_states)
            wm_states.append(snap)
            last_key, last_si = key, si
        events.append({
            "seq": len(events), "phase": e["phase"], "kind": e["kind"], "label": e["label"],
            "cycle": e["cycle"], "wave": e["wave"], "highlight": e["highlight"],
            "wm_state": si, "goal_stack": e["goal_stack"], "detail": e["detail"], "rule": e["rule"],
        })
    return events, wm_states
```

- [ ] **Step 2: `JournalSink` 델타 교체 + `NullSink` 에 빈 seed/wm_log/raw_events**

`arbor/engine/sink.py` 에서 `NullSink` 을 아래로(render 가 빈 결과를 내도록 빈 리스트 3개 추가):
```python
class NullSink:
    """headless: 방출 no-op. wm.journal 을 안 붙여 실행이 방출 비용을 전혀 안 낸다.
    render(NullSink) 이 빈 events/wm_states 를 내도록 seed/wm_log/raw_events 는 빈 리스트."""
    seed: list = []
    wm_log: list = []
    raw_events: list = []

    def event(self, *a, **k):
        pass
```
그리고 `JournalSink` 전체를 아래로 교체(stage b full-snapshot 버전 → 델타 버전):
```python
class JournalSink:
    """debug(stage c): 이벤트와 WM mutation 을 append-only journal 로 기록.
    seed = 부착 시점 WM(이후 델타의 기준점). wm_log = wm.add/remove 가 append 하는 델타.
    event() 은 그 순간 wm_log 길이(cursor)만 실어 전체 WM 을 안 뜬다 → 실행 중 O(1)."""
    def __init__(self, agent):
        self.ag = agent
        self.raw_events: list = []
        self.wm_log: list = []
        self.seed = list(agent.wm)                  # 부착 전 초기 WM — Renderer replay 시작점
        agent.wm.journal = self.wm_log              # 이후 모든 mutation 이 wm_log 로

    def event(self, phase, kind, label, cycle, goal_stack,
              highlight=None, detail=None, rule=None, wave=None):
        self.raw_events.append({
            "phase": phase, "kind": kind, "label": label, "cycle": cycle, "wave": wave,
            "highlight": highlight or [], "detail": detail, "rule": rule,
            "goal_stack": list(goal_stack), "cursor": len(self.wm_log),
        })
```
`sink.py` 상단의 `from soar.wm import _wm_key` 는 이제 sink 에서 안 쓰이므로 **제거**(renderer 로 이동됨 — T2 minor 해소).

- [ ] **Step 3: `_Tracer.events`/`_wm_states` 를 lazy render+memoize property 로**

Task 2 에서 넣은 두 property 는 `self.sink.events` 를 직접 읽는다 — 델타 sink 엔 그게 없다. **삭제하지 말고** journal 을 render 해 주는 lazy property 로 바꾼다(기존 소비자 무변경 유지가 목적). `arbor/engine/trace.py` `_Tracer.__init__` 의 `self.sink = ...` 아래에:
```python
        self._rendered = None                       # (events, wm_states) 캐시 — 최초 접근 시 1회 render
```
그리고 Task 2 의 두 property 를 아래로 교체:
```python
    def _render(self):
        if self._rendered is None:
            from arbor.engine.renderer import render
            self._rendered = render(self.sink)      # journal → (events, wm_states), 1회 memoize
        return self._rendered

    @property
    def events(self):
        return self._render()[0]

    @property
    def _wm_states(self):
        return self._render()[1]
```
`emit`(Task 2 의 delegating 버전)과 `run()` 의 `return self.events` 는 **그대로**(events property 가 render 를 트리거). `debugger/solve_cache.py` 는 이 property 로 그대로 동작하므로 **건드리지 않는다**.

- [ ] **Step 4: 통과 확인 + 회귀 게이트**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_engine_renderer.py -v`
Expected: PASS — 델타 replay 로 재구성한 events/wm_states 가 golden 과 여전히 byte 동일.

Run: `PYTHONHASHSEED=0 python -m pytest tests/ -q`
Expected: `168 passed, 10 failed, 11 skipped` (Task 2 이후와 동일 — Task 3 는 신규 테스트 없음)

- [ ] **Step 5: 대시보드 데이터 byte 검증(수동 게이트)**

```bash
PYTHONHASHSEED=0 python -c "
import sys; sys.path.insert(0,'.')
from arbor.env.dataset import list_tasks, load_task
from debugger.build import _dash_data
from debugger.solve_cache import clear_cache
clear_cache()
tid,p = list_tasks('move')[0]
d = _dash_data(load_task(p), tid)
print('n_steps', d['n_steps'], 'wm_states', len(d['wm_states']), 'correct', d['correct_attempt'])
"
```
Expected: `correct` 가 0 (첫 후보로 정답) 이고 n_steps/wm_states 가 0 아님 — 대시보드 파이프라인이 Renderer 산출로 정상 동작.

- [ ] **Step 6: 커밋**

```bash
git add arbor/engine/renderer.py arbor/engine/sink.py arbor/engine/trace.py
git commit -m "refactor(engine): WM 스냅샷 → event-sourcing 델타 + 순수 Renderer(시간순 replay)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: NullSink headless 빠른 경로 (stage d)

**Files:**
- Modify: `debugger/solve_cache.py` (`run_solve` 에 `mode` 파라미터)
- Test: `tests/test_engine_renderer.py` (score==debug attempts 동치 추가)

**Interfaces:**
- Consumes: `NullSink`(Task 2), `JournalSink`/`render`(Task 3).
- Produces: `run_solve(tid, task, max_cycles=500, use_cache=True, mode="debug")`. `mode="score"` → NullSink, `{events:[], wm:[...], wm_states:[], attempts, error}`. `mode="debug"` → 기존(Renderer).

- [ ] **Step 1: score==debug attempts 동치 테스트 작성**

`tests/test_engine_renderer.py` 에 추가:
```python
def test_score_mode_same_attempts_as_debug():
    for tid in _GOLD:
        t = load_task(_PATHS[tid])
        deb = run_solve(tid, t, max_cycles=500, use_cache=False, mode="debug")
        sco = run_solve(tid, t, max_cycles=500, use_cache=False, mode="score")
        assert [a["correct"] for a in sco["attempts"]] == [a["correct"] for a in deb["attempts"]]
        assert sco["events"] == [] and sco["wm_states"] == []
```

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_engine_renderer.py::test_score_mode_same_attempts_as_debug -v`
Expected: FAIL — `run_solve() got an unexpected keyword argument 'mode'`

- [ ] **Step 2: `run_solve` 에 `mode` 추가**

`debugger/solve_cache.py` `run_solve` 시그니처와 본문:
```python
def run_solve(tid, task, max_cycles=500, use_cache=True, mode="debug"):
    """mode='score' → NullSink(방출·스냅샷 0, attempts 만) / 'debug' → JournalSink+Renderer."""
    h = _task_hash(task)
    cf = os.path.join(_CACHE_DIR, f"{tid}.{mode}.pkl")
    if use_cache and os.path.exists(cf):
        try:
            c = pickle.load(open(cf, "rb"))
            if c.get("hash") == h and c.get("max_cycles", 0) >= max_cycles:
                return c["result"]
        except (pickle.PickleError, KeyError, OSError, EOFError):
            pass
    from arbor.engine.trace import _Tracer
    from arbor.agent.focus import setup_focus_agent
    if mode == "score":
        from arbor.engine.sink import NullSink
        tr = _Tracer(task, tid, setup=setup_focus_agent, sink=NullSink())
        tr.run(max_cycles=max_cycles)
        result = {"events": [], "wm": [list(t) for t in tr.ag.wm],
                  "wm_states": [], "attempts": tr.attempts, "error": None}
    else:
        tr = _Tracer(task, tid, setup=setup_focus_agent)     # JournalSink 기본
        tr.run(max_cycles=max_cycles)
        from arbor.engine.renderer import render
        events, wm_states = render(tr.sink)
        result = {"events": events, "wm": [list(t) for t in tr.ag.wm],
                  "wm_states": wm_states, "attempts": tr.attempts, "error": None}
    if use_cache:
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            pickle.dump({"hash": h, "max_cycles": max_cycles, "result": result}, open(cf, "wb"))
        except (OSError, pickle.PickleError):
            pass
    return result
```
(캐시 파일명에 `mode` 를 넣어 score/debug 캐시를 분리한다.)

- [ ] **Step 3: 통과 확인**

Run: `PYTHONHASHSEED=0 python -m pytest tests/test_engine_renderer.py -v`
Expected: PASS (3 passed — golden + score 동치)

- [ ] **Step 4: 60/60 빠른 경로 + 결정성 게이트**

`/private/tmp/.../scratchpad/score_move.py` 의 `run_solve(...)` 호출에 `mode="score"` 추가(이미 `use_cache=False`), 그리고:
```bash
for seed in 0 1 42; do echo "seed $seed"; PYTHONHASHSEED=$seed python <scratchpad>/score_move.py 2>&1 | tail -1; done
```
Expected: 세 seed 모두 `SCORE: 60/60`, 시간은 debug 경로보다 단축.

- [ ] **Step 5: 커밋**

```bash
git add debugger/solve_cache.py tests/test_engine_renderer.py
git commit -m "feat(engine): run_solve mode='score' headless 빠른 경로(NullSink) — 채점 방출비용 0

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 범위 밖 (이 계획 비목표 — 후속)

- **stage e** 모듈 rename(`trace.py` → `engine.py`+`renderer.py`, `_Tracer` → 엔진 이름): seam 검증 뒤 순수 파일 이동으로 별건.
- **Part-2**: op-body arg 탈절차화·원자단위 분해, `_build_agenda`/generalize/`_resolve_cellset` 규칙화, xform↔ARCKG relation 통합, op-body 사고단계 `sink.thought(...)` 이벤트.
- 낡은 트레이스 스키마(`event["wm"]`) 참조 2개 테스트 수정.

## Self-Review 결과

- **Spec coverage**: §1(경계/계약)→Task2, §2(event-sourcing 델타)→Task1+Task3, §3(데이터흐름/mode)→Task4, §4 단계 a→d 각각 Task1~4 로 매핑. stage e·Part-2 는 명시적 범위 밖. 누락 없음.
- **Placeholder scan**: 모든 step 에 실제 코드/명령/기대출력 존재. TBD 없음.
- **Type consistency**: `JournalSink(agent)`·`event(phase,kind,label,cycle,goal_stack,...)`·`render(sink)->(events,wm_states)`·`run_solve(...,mode=)` 시그니처가 Task 간 일치. `sink.seed`/`sink.wm_log`/`sink.raw_events` 이름이 Task3(생성)과 renderer(소비)에서 동일.
