# -*- coding: utf-8 -*-
"""solve 캐시 — 태스크를 1회만 solve 하고 그 결과를 dashboard·program report 가 공유한다.

병목은 ARBOR 솔버 재실행이었다(태스크당 2번: dashboard + report). 이 캐시로:
  · 한 번 solve 한 결과(events/wm/wm_states/attempts)를 디스크에 저장 → 두 리포트가 재사용(솔버 1회).
  · 입력(task JSON) 이 안 바뀐 태스크는 재-solve 없이 캐시 로드 → 푼 문제/안 바뀐 문제 스킵.

캐시 키 = task 내용 해시. **솔버 로직을 바꾸면 캐시가 낡으므로** `debugger/traces/.solve_cache/` 를
지우거나 run_solve(use_cache=False) 로 강제 재계산한다(clear_cache() 제공).
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle

# pickle 사용: wm_states 등에 튜플이 있어 JSON 라운드트립 시 list 로 바뀌면 wm_deltas 의 set 연산이
# 깨진다(unhashable list). pickle 은 튜플/객체를 그대로 보존한다.
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces", ".solve_cache")


def _task_hash(task) -> str:
    return hashlib.md5(json.dumps(task, sort_keys=True).encode()).hexdigest()[:12]


def clear_cache():
    """전체 solve 캐시 삭제(솔버 로직 변경 후 재계산 강제용)."""
    import shutil
    if os.path.isdir(_CACHE_DIR):
        shutil.rmtree(_CACHE_DIR)


def run_solve(tid, task, max_cycles=500, use_cache=True):
    """태스크를 solve(또는 캐시 로드)해 {events, wm, wm_states, attempts, error} 반환.
    dashboard(_dash_data)·program report(_collect) 가 이 하나를 공유한다(솔버 1회).
    캐시 히트 = 같은 task 해시 + 같은(이상) max_cycles → 솔버 재실행 없음."""
    h = _task_hash(task)
    cf = os.path.join(_CACHE_DIR, f"{tid}.pkl")
    if use_cache and os.path.exists(cf):
        try:
            c = pickle.load(open(cf, "rb"))
            if c.get("hash") == h and c.get("max_cycles", 0) >= max_cycles:
                return c["result"]
        except (pickle.PickleError, KeyError, OSError, EOFError):
            pass
    from arbor.engine.trace import _Tracer
    from arbor.agent.focus import setup_focus_agent
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    events = tr.run(max_cycles=max_cycles)                 # 예외는 호출측(_safe_dash_data)이 격리
    result = {
        "events": events,
        "wm": [list(t) for t in tr.ag.wm],                 # [(id, attr, value), ...]
        "wm_states": tr._wm_states,
        "attempts": tr.attempts,
        "error": None,
    }
    if use_cache:
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            pickle.dump({"hash": h, "max_cycles": max_cycles, "result": result}, open(cf, "wb"))
        except (OSError, pickle.PickleError):
            pass
    return result
