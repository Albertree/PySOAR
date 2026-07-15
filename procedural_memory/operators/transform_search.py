# -*- coding: utf-8 -*-
"""ARBOR operator body: transform_search — synthesize 의 contents-DESCEND 공백에서 DSL transform 탐색.
effect 일치 후보를 열거→arg resolve→train verify. 시도·기각을 hypothesis WME 로 잔존(§1-5)."""
from __future__ import annotations
from arbor.reasoning.transform_search import transform_search


def _op_transform_search(ag):
    s = ag.stack[-1].id
    parent = next((v for (i, a, v) in ag.wm.t if i == s and a == "superstate"), s) \
        if hasattr(ag.wm, "t") else \
        next((v for (i, a, v) in ag.wm if i == s and a == "superstate"), s)
    res = transform_search(ag.task["train"])
    ag.wm.add(s, "required-effect", "/".join(res["required"]) or "(none)")
    ag.wm.add(s, "candidates", ",".join(res["candidates"]) or "(none)")
    for k, h in enumerate(res["hypotheses"], 1):
        hh = f"{s}.T{k}"
        ag.wm.add(s, "hypothesis", hh)
        ag.wm.add(hh, "rule", h["rule"])
        ag.wm.add(hh, "args", str(h.get("args", [])))
        ag.wm.add(hh, "src", str(h.get("args_src")))
        ag.wm.add(hh, "verdict", h["verdict"])
    if res["survivor"]:
        sv = res["survivor"]
        ag.wm.add(parent, "transform-survivor", f"{sv['rule']} {sv['plan']['args']}")
        ag.wm.add(parent, "answer-ready", "yes")
    else:
        ag.wm.add(parent, "transform-verdict", "생존 후보 없음 → 하강")
    ag.wm.add(s, "transform-search-done", "yes")
