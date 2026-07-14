# -*- coding: utf-8 -*-
"""ARBOR operator body: grid_slots (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from pysoar import Agent, Cond, Action, Production
from arc.expr_solver import build_arckg, _load_value, _tup


def _op_set_grid_size(ag):
    """grid.size 슬롯 설정 DSL (apply body). ^size-hyp(예측값)을 읽어 grid_size 슬롯으로 물질화.
    ^size-ready 로 다음 단계(set_grid_color)를 순차 발화(operator-tie 회피)."""
    sid = ag.stack[-1].id
    expr = next((v for (i, a, v) in ag.wm if i == sid and a == "size-hyp"), "unknown")
    ag.wm.add(sid, "slot-grid_size", expr)          # program 의 grid_size 슬롯
    ag.wm.add(sid, "size-set", "yes"); ag.wm.add(sid, "size-ready", "yes")


def _op_set_grid_color(ag):
    """grid.color 슬롯 설정 DSL (apply body). ^color-hyp(예측값)을 읽어 grid_color 슬롯으로 물질화."""
    sid = ag.stack[-1].id
    expr = next((v for (i, a, v) in ag.wm if i == sid and a == "color-hyp"), "unknown")
    ag.wm.add(sid, "slot-grid_color", expr)
    ag.wm.add(sid, "color-set", "yes"); ag.wm.add(sid, "color-ready", "yes")
