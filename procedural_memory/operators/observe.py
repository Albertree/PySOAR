# -*- coding: utf-8 -*-
"""ARBOR operator body: observe (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arc.expr_solver import build_arckg, _load_value, _tup
from arbor.perception.nav import _cursor, _focus_group, _load_props


def _op_observe(ag):
    """관측 커서 ^focus 가 가리키는 **단 하나**의 노드를 관측한다 (형제 곁다리 로드 없음 — 사용자
    교정: 관측된 것끼리만 compare 대상). 그 뒤 커서를 같은 계층(^level)의 다음 미관측 노드로
    옮긴다(하나하나 훑기). 계층 전부 관측되면 ^observed + 비교 agenda 를 짠다(compare 가 소비)."""
    idx, sid = ag.kg["idx"], ag.stack[-1].id
    f = _cursor(ag)
    if f is None:
        return                                  # arg(대상) 미정 → 변화 없음 → ONC impasse → arg-선택 substate
    node, lvl = idx["nodes"][f], idx["level"][f]
    if lvl == "pixel":
        # PIXEL 은 색+좌표뿐이고 hypothesize 가 grid 를 직접 읽으므로 **픽셀 property 를 WM 에 안 올린다**.
        # 성능: 큰 격자(예 196 픽셀)를 커서로 하나씩 훑으면 WM 폭증+naive rematch 로 매우 느려짐 →
        # focus 픽셀 전부를 한 번에 seen 표시(bulk)해 관측을 O(1) 로. (개별 관측 정보는 어차피 안 씀.)
        for p in _focus_group(ag, sid):
            ag.wm.add(p, "seen", "yes")
        return
    _load_props(ag, f, node, lvl)               # ^property = {type + to_json + 아티팩트 슬롯}
    for edge, c in idx["edges"][f]:
        ag.wm.add(f, edge, c)                   # 자식 존재(ref) — edge(구조)는 property 밖 그대로


def _imbalance_goal(group, props, key):
    """A FLAT presence-dict property (value -> bool), e.g. roles={input:T, output:F},
    where ONE member differs from the majority -> that member is incomplete; return
    what it is missing. Non-flat / non-bool dicts (nested grid props) -> skip (None)."""
    dicts = [props[m][key] for m in group]
    if not all(isinstance(d, dict) and all(isinstance(v, bool) for v in d.values())
               for d in dicts):
        return None
    sigs = {m: tuple(sorted(props[m][key].items())) for m in group}
    cnt = Counter(sigs.values())
    if len(cnt) < 2:
        return None
    majority = dict(cnt.most_common(1)[0][0])
    for m in group:
        if sigs[m] != cnt.most_common(1)[0][0]:
            mind = props[m][key]
            missing = [sk for sk, sv in majority.items() if sv and not mind.get(sk)]
            return {"minority": m, "missing": missing[0] if missing else "?"}
    return None


def _build_agenda(ag, sid, group):
    """관측 끝난 계층의 비교 목록을 **WM 에 선언적으로** 깐다 (Python 리스트 아님 — 프로세스가
    고정 스크립트가 아니라 *규칙이 소비하는 WM 구조*가 되도록). 각 비교 = (S ^cmp <cid>) 마커 +
    (<cid> ^kind ..)(^order i)[+ arg WME]. (S ^cmp-active <첫>) = 커서. compare 규칙이 하나씩 소비.
    무엇을 비교할지는 ARCKG level 구조로 지각(perception): peers / within / cross / predict.
      PAIR : peers — 관측된 pair 들 비교 → 불균형(결핍 역할) 발견
      GRID : 훈련 pair 별 within(G0↔G1) → cross(입력·변화·출력 삼중쌍) → predict
      OBJECT: 각 train pair 의 G0-objects ↔ G1-objects 대응(match, score 순위)."""
    idx = ag.kg["idx"]; lvls, par = idx["level"], idx["parent"]
    kind = lvls[group[0]] if group else None
    specs = []                                          # (cid, kind, order)
    if kind == "pair" and len(group) >= 2:
        cid = f"{sid}.cmp:peers"
        for m in group:
            ag.wm.add(cid, "member", m)                 # arg: 비교할 pair 들 (WM 에 선언적)
        specs.append((cid, "peers", 0))
    elif kind == "grid":
        bypair = {}
        for g in group:
            bypair.setdefault(par[g], []).append(g)
        train = sorted(p for p, gs in bypair.items() if len(gs) >= 2)   # G0·G1 다 있는 훈련 pair
        order = 0
        for p in train:
            g0, g1 = sorted(bypair[p])
            cid = f"{sid}.cmp:within.{p.split('.')[-1]}"
            ag.wm.add(cid, "g0", g0); ag.wm.add(cid, "g1", g1); ag.wm.add(cid, "pair", p)
            specs.append((cid, "within", order)); order += 1
        if len(train) >= 2:
            for which in ("input", "change", "output"):
                cid = f"{sid}.cmp:cross.{which}"
                ag.wm.add(cid, "which", which)
                for p in train:
                    ag.wm.add(cid, "pair", p)
                specs.append((cid, "cross", order)); order += 1
        specs.append((f"{sid}.cmp:predict", "predict", order))
        if train:
            ag.wm.add(sid, "to-hypothesize", "yes")         # within/cross 비교 끝나면 GRID hypothesize 발화

    elif kind == "object":
        # OBJECT: G0→G1 transformation 은 **한 PAIR 안**에서 찾는다 (사용자 교정 2026-07-10).
        # inter-PAIR object 비교(P1·P2 의 G0×G1 매칭)는 **하지 않는다** — 변환은 P0 하나에서
        # 도출하고, 다른 pair 는 나중에 그 변환을 *선택적으로 적용·검증*(부하 O(n²)→피함).
        # 그래서 여기선 **첫 train pair 한 개**의 G0-objs ↔ G1-objs 대응만 만든다.
        bygrid, bypair = {}, {}
        for o in group:
            bygrid.setdefault(par[o], []).append(o)             # object → 그 grid
        for g in bygrid:
            bypair.setdefault(par[g], []).append(g)             # grid → 그 pair
        train = sorted(pp for pp, gs in bypair.items() if len(gs) >= 2)   # G0·G1 다 있는 pair
        if train:
            p = train[0]                                        # 첫 PAIR 만 (다음 PAIR 로 안 넘어감)
            g0, g1 = sorted(bypair[p])
            cid = f"{sid}.cmp:match.{p.split('.')[-1]}"
            ag.wm.add(cid, "g0", g0); ag.wm.add(cid, "g1", g1); ag.wm.add(cid, "pair", p)
            specs.append((cid, "match", 0))
            ag.wm.add(sid, "to-hypothesize", "yes")             # match 끝나면 hypothesize 발화(OBJECT 만)
    elif kind == "pixel":
        # PIXEL: GRID.pixels 를 G0·G1 로 나눠 **G0-pixels ↔ G1-pixels 교차 비교**(cross-grid 우선 —
        # grid 내부 pixel 끼리보다). object match 와 동형, 단위만 pixel. 같은 좌표끼리 kg_compare →
        # color/coord COMM/DIFF 만(**delta·크기비교 없음**; 좌표차 표현은 별도 단계). (사용자 2026-07-10)
        bygrid = {}
        for px in group:
            bygrid.setdefault(par[px], []).append(px)           # pixel → 그 GRID
        grids = sorted(bygrid)                                   # [G0, G1] (같은 pair)
        if len(grids) >= 2:
            g0, g1 = grids[0], grids[1]
            cid = f"{sid}.cmp:pxmatch"
            ag.wm.add(cid, "g0", g0); ag.wm.add(cid, "g1", g1)
            specs.append((cid, "pxmatch", 0))
            ag.wm.add(sid, "to-hypothesize", "yes")             # pxmatch 끝나면 hypothesize(PIXEL) 발화
    for cid, k, order in specs:
        ag.wm.add(sid, "cmp", cid)                       # 계층 아래 비교 목록(선언적)
        ag.wm.add(cid, "kind", k)
        ag.wm.add(cid, "order", str(order))
    if specs:
        ag.wm.add(sid, "to-compare", "yes")     # compare(arg 없이) 제안 → SELECT 가 cmp-active 세움
    else:
        ag.wm.add(sid, "compared", "yes")       # 비교 없음(object/단일) → 하강/정지
