# -*- coding: utf-8 -*-
"""ARBOR engine renderer — journal(JournalSink) → dashboard 가 쓰는 events + wm_states.

순수 함수: 실행을 모르고 journal 만 본다. seed WM(부착 시점)에서 시작해 각 이벤트 cursor
까지의 WM 델타를 시간순 적용해 그 시점 WM 을 복원하고, 안 바뀌면 직전 인덱스 재사용(dedup).
결과 자료구조는 기존 _Tracer.emit 산출과 동일."""
from __future__ import annotations

from arbor.soar.wm import _wm_key


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
