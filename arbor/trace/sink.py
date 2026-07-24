# -*- coding: utf-8 -*-
"""ARBOR engine sinks — 실행(Engine)과 방출(디버거)을 잇는 이음새.

Engine(Runner.run 사이클)은 방출 지점마다 sink.event(...) 만 호출한다(의존성 역전).
NullSink = headless(채점·대량; 비용 0). JournalSink = debug.
(stage c: event-sourcing 델타 기록 — 스냅샷은 Renderer(arbor/trace/renderer.py)가
 journal 을 replay 해서 사후 재구성한다.)"""
from __future__ import annotations


class NullSink:
    """headless: 방출 no-op. wm.journal 을 안 붙여 실행이 방출 비용을 전혀 안 낸다.
    render(NullSink) 이 빈 events/wm_states 를 내도록 seed/wm_log/raw_events 는 빈 튜플
    (클래스-레벨 mutable list 는 인스턴스 간 공유되는 footgun 이라 immutable 튜플로 둔다)."""
    seed: tuple = ()
    wm_log: tuple = ()
    raw_events: tuple = ()

    def event(self, *a, **k):
        pass


class JournalSink:
    """debug(stage c): 이벤트와 WM mutation 을 append-only journal 로 기록.
    seed = 부착 시점 WM(이후 델타의 기준점). wm_log = wm.add/remove 가 append 하는 델타.
    event() 은 그 순간 wm_log 길이(cursor)만 실어 전체 WM 을 안 뜬다 → 실행 중 O(1)."""
    def __init__(self, agent):
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
