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
