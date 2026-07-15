# -*- coding: utf-8 -*-
"""ARBOR reasoning.program — grid/color 탐색 + PAIR.program 물질화 (focus_solver 분리)."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup


def _size_expr_search(train):
    """출력 격자 크기 (H1,W1) 를 입력 크기 (H0,W0)+상수의 **식**으로 도출한다 — 손계산 금지, 후보식을
    생성→모든 train pair 에 적용→출력크기와 대조→기각/생존 (§1-3·§4-1 의 generate-and-test 그대로).
    반환 = (rule={'H':식|None,'W':식|None}, tried={'H':[(식,ok)],'W':[…]}). 살아남는 식이 없으면 None."""
    atoms = [("H0", lambda H, W: H), ("W0", lambda H, W: W)]
    ops = [("-", lambda x, k: x - k), ("+", lambda x, k: x + k),
           ("*", lambda x, k: x * k), ("//", lambda x, k: x // k if k else 0)]
    cands = []
    for nm, fn in atoms:
        cands.append((nm, fn))
        for k in (1, 2, 3):
            for osym, ofn in ops:
                cands.append((f"{nm}{osym}{k}", lambda H, W, fn=fn, ofn=ofn, k=k: ofn(fn(H, W), k)))
    dims = [(len(e["input"]), len(e["input"][0]), len(e["output"]), len(e["output"][0])) for e in train]
    rule, tried, trials = {}, {}, {}
    for axis, ti, own in (("H", 2, "H0"), ("W", 3, "W0")):
        rule[axis] = None; tried[axis] = []; trials[axis] = []
        # 그 축의 '자기' 입력차원(H1←H0, W1←W0)을 먼저 시도 → 정사각이라 값이 같아도 식이 자연스럽게 읽힘
        ordered = sorted(cands, key=lambda dc: not dc[0].startswith(own))
        for desc, fn in ordered:
            per_pair = [{"in": (d[0], d[1]), "expected": d[ti], "got": fn(d[0], d[1]),
                         "ok": fn(d[0], d[1]) == d[ti]} for d in dims]     # 후보 생성 → 즉시 각 pair 테스트
            ok = all(p["ok"] for p in per_pair)                          # 모든 pair 에서 성립?
            tried[axis].append((desc, ok))
            trials[axis].append({"candidate": f"{axis}1={desc}", "per_pair": per_pair, "verdict": ok})
            if ok and rule[axis] is None:
                rule[axis] = desc
    return rule, tried, trials


def _size_apply(train, paG0):
    """전 train 일관 크기식(H0,W0+연산자+상수 brute-force)을 찾아 **Pa.G0 에 적용**한 예측크기.
    반환 = (desc, (H,W)) or (None, None). (§4-1 generate-and-test — 후보식은 _size_expr_search 가 노출.)"""
    dims = [((len(e["input"]), len(e["input"][0])), (len(e["output"]), len(e["output"][0]))) for e in train]
    ops = [("-", lambda x, k: x - k), ("+", lambda x, k: x + k),
           ("*", lambda x, k: x * k), ("//", lambda x, k: x // k if k else 0)]

    def find(ti, own):
        cands = [("H0", lambda H, W: H), ("W0", lambda H, W: W)]
        for nm, fn in list(cands):
            for k in (1, 2, 3):
                for osym, ofn in ops:
                    cands.append((f"{nm}{osym}{k}", lambda H, W, fn=fn, ofn=ofn, k=k: ofn(fn(H, W), k)))
        cands.sort(key=lambda d: not d[0].startswith(own))
        for desc, fn in cands:
            if all(fn(i[0], i[1]) == o[ti] for i, o in dims):
                return desc, fn
        return None, None
    dh, fh = find(0, "H0")
    dw, fw = find(1, "W0")
    if fh and fw and not (dh == "H0" and dw == "W0"):     # keep 과 같으면 별도 취급
        H, W = len(paG0), len(paG0[0])
        return f"H1={dh},W1={dw}", (fh(H, W), fw(H, W))
    return None, None


def _grid_decide(train, paG0):
    """확정 의사결정 절차(사용자 2026-07-13). 속성별 타입으로 후보 생성 → 전 train 검증 → **Pa.G0 적용**
    → 예측 수렴검사. 반환 {prop: {type, within, cands:[(kind,pred,ok)], decision, value}}.
      · size = NUMBER: KEEP·CONST·MAP(크기식 brute-force)
      · color = SET   : KEEP·CONST·SET-MAP(추가/삭제)·MAP(전역재채색)
      · contents=CLASS: 항등·상수출력·전역remap 이면 DECIDE, 아니면 DESCEND (equality 뿐)."""
    def sz(g):
        return (len(g), len(g[0]))
    ins = [e["input"] for e in train]
    outs = [e["output"] for e in train]
    pairs = list(zip(ins, outs))
    out = {}

    # ── size (NUMBER) ──
    cs, preds = [], set()
    keep = all(sz(i) == sz(o) for i, o in pairs)
    if keep:
        cs.append(("KEEP", sz(paG0), True)); preds.add(sz(paG0))
    if all(sz(o) == sz(outs[0]) for o in outs):
        cs.append(("CONST", sz(outs[0]), True)); preds.add(sz(outs[0]))
    desc, val = _size_apply(train, paG0)
    if desc:
        cs.append((f"MAP[{desc}]", val, True)); preds.add(val)
    out["size"] = {"type": "NUMBER", "within": [sz(i) == sz(o) for i, o in pairs],
                   "cands": cs, "decision": _dec(preds), "value": (next(iter(preds)) if len(preds) == 1 else None)}

    # ── color (SET) ──
    ci = [_colorset(i) for i in ins]
    co = [_colorset(o) for o in outs]
    cp, preds = [], set()
    pa = _colorset(paG0)
    if all(a == b for a, b in zip(ci, co)):
        cp.append(("KEEP", pa, True)); preds.add(pa)
    if all(x == co[0] for x in co):
        cp.append(("CONST", co[0], True)); preds.add(co[0])
    add0, rem0 = co[0] - ci[0], ci[0] - co[0]
    if (add0 or rem0) and all((a - rem0) | add0 == b for a, b in zip(ci, co)):
        cp.append((f"SET-MAP(-{sorted(rem0)}+{sorted(add0)})", (pa - rem0) | add0, True)); preds.add((pa - rem0) | add0)
    gm = _color_map_search(train)
    if gm and any(k != v for k, v in gm.items()):
        pc = frozenset(gm.get(v, v) for v in pa)
        cp.append(("MAP", pc, True)); preds.add(pc)
    out["color"] = {"type": "SET", "within": [a == b for a, b in zip(ci, co)],
                    "cands": cp, "decision": _dec(preds), "value": (next(iter(preds)) if len(preds) == 1 else None),
                    "map": gm if (gm and any(k != v for k, v in gm.items())) else None}

    # ── contents (CLASS) ──
    kk, val, note = [], None, "DESCEND"
    if all(i == o for i, o in pairs):
        val, note = paG0, "항등"; kk.append(("KEEP", "항등", True))
    elif all(o == outs[0] for o in outs):
        val, note = outs[0], "상수출력"; kk.append(("CONST", "상수출력", True))
    elif gm and any(k != v for k, v in gm.items()) and all(sz(i) == sz(o) for i, o in pairs):
        val, note = [[gm.get(v, v) for v in row] for row in paG0], "전역remap"; kk.append(("MAP", "전역remap", True))
    out["contents"] = {"type": "CLASS", "within": [i == o for i, o in pairs], "cands": kk,
                       "decision": "DECIDE" if val is not None else "DESCEND", "value": val, "note": note}
    return out


def _dec(preds):
    return "DESCEND" if len(preds) == 0 else ("DECIDE" if len(preds) == 1 else "AMBIGUOUS")


def _color_map_search(train):
    """전 train pair 를 셀 단위로 훑어 **입력색→출력색 전역 함수**를 도출(크기 COMM 인 pair 만).
    한 입력색이 두 출력색으로 가면(=전역 함수 아님, 객체·위치 의존) None. 일관하면 그 map 반환."""
    if any(len(e["input"]) != len(e["output"]) or len(e["input"][0]) != len(e["output"][0])
           for e in train):
        return None
    mp = {}
    for e in train:
        i, o = e["input"], e["output"]
        for r in range(len(i)):
            for c in range(len(i[0])):
                a, b = i[r][c], o[r][c]
                if a in mp and mp[a] != b:
                    return None
                mp[a] = b
    return mp


def _global_recolor_program(g0grid, cmap):
    """전역 색맵을 **기존 coloring DSL** 만으로 표현(§1-1: 새 DSL 없이) — 목표색 t 로 바뀌는 입력셀
    (색 s, cmap[s]=t≠s)을 셀 단위로 재채색하는 AST 로 물질화(program_ast). 셀을 target 색별로 묶어
    순서대로 낸다(전 색 그룹핑은 정렬 안정을 위한 것일 뿐, 실행 산출 grid 는 셀단위와 동일)."""
    import json
    from arbor.reasoning import program_ast as PA
    H, W = len(g0grid), len(g0grid[0])
    body = []
    bytarget = {}
    for r in range(H):
        for c in range(W):
            s = g0grid[r][c]; t = cmap.get(s, s)
            if t != s:
                bytarget.setdefault(t, []).append((r, c))
    for t in sorted(bytarget):
        for (r, c) in bytarget[t]:
            body.append(PA.step("coloring", target=PA.ref("pixel", PA.const(r * W + c)), color=PA.const(t)))
    return json.dumps(PA.program(body))


def _colorset(grid):
    return frozenset(v for row in grid for v in row)


def _grid_prop_value(prop, grid):
    """GRID 목표속성의 값: size=(H,W) · color=색 집합 · contents=격자 그대로."""
    if prop == "size":
        return (len(grid), len(grid[0]))
    if prop == "color":
        return _colorset(grid)
    return tuple(tuple(r) for r in grid)


def _grid_property_hypotheses(prop, train, within_t, xout_t):
    """GRID 목표속성(size|color)에 대한 **가설 후보 생성+검증** (모듈+규칙 기반 시도 탐색 — case 하드코딩
    아님). *관계(COMM/DIFF)가 어떤 가설을 시도할지 고르고*, 실제 train 대조가 채택/기각한다(§2-2·§4-1):
      keep      (within COMM)    : 출력.P = 입력.P
      const     (cross-out COMM) : 출력.P = 훈련출력 공통값 (G1끼리 일정)
      transform (within DIFF)    : 출력.P = f(입력.P) — size=출력크기식 탐색·color=전역색맵 (일정한 변화)
    반환 = [{kind, pred, ok, extra}] — 생성·기각 후보 전부(첫 ok 가 결론). 상위(hypothesize)가 이 리스트를
    WM 에 노출해 '무엇을 시도하고 무엇이 기각됐나'가 보이게 한다(object/pixel 가설과 동형)."""
    ins = [_grid_prop_value(prop, e["input"]) for e in train]
    outs = [_grid_prop_value(prop, e["output"]) for e in train]

    def _fmt(v):
        return f"{v[0]}x{v[1]}" if prop == "size" else (sorted(v) if isinstance(v, frozenset) else v)
    cands = []
    if within_t == "COMM":                                          # 관계가 keep 가설을 시사
        ok = all(o == i for i, o in zip(ins, outs))
        cands.append({"kind": "keep", "pred": "출력=입력", "ok": ok})
    if xout_t == "COMM":                                            # 관계가 const 가설을 시사(G1끼리 COMM)
        shared = outs[0] if all(o == outs[0] for o in outs) else None
        cands.append({"kind": "const", "pred": f"={_fmt(shared)}" if shared is not None else "불일치",
                      "ok": shared is not None, "value": shared})
    if within_t == "DIFF":                                          # 관계가 transform 가설을 시사(변화)
        if prop == "size":
            rule, tried, trials = _size_expr_search(train)
            ok = bool(rule["H"] and rule["W"])
            cands.append({"kind": "transform", "ok": ok, "tried": tried, "rule": rule, "trials": trials,
                          "pred": f"H1={rule['H']},W1={rule['W']}" if ok else "크기식없음"})
        else:
            cmap = _color_map_search(train)
            ok = bool(cmap and any(k != v for k, v in cmap.items()))
            cands.append({"kind": "transform", "ok": ok, "map": cmap if ok else None,
                          "pred": f"전역색맵 {cmap}" if ok else "전역색맵없음"})
    return cands


def _materialize_pair_programs(ag):
    """**모든 example PAIR 에 per-pair program 을 물질화** (사용자 2026-07-14). 현재 substate 가 처리한
    PAIR(sim-pair)은 operator 사이클로 이미 program 을 얻었고, 나머지 PAIR 들은 **같은 generic 합성**
    (pixel 잔차)을 pair 마다 적용해 각자의 `PAIR.property.program` 을 채운다. → N example pair → N program.
    (이미 program 이 있는 PAIR 은 건너뜀; 크기변화 PAIR 은 빈 슬롯 유지 = 정직히 범위 밖.)"""
    root = ag.kg.get("arckg_root")
    if root is None:
        return
    for k, p in enumerate(getattr(root, "example_pairs", []) or []):
        if k >= len(ag.task["train"]):
            break
        ppid = f"{p.node_id}.property"
        cur = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if cur not in (None, "{}"):
            continue                                        # 이미 실제 program 있음(예: sim-pair)
        code = _pixel_residual_program(ag.task["train"][k]["input"], ag.task["train"][k]["output"])
        if code is None:
            continue
        if ag.wm.contains(ppid, "program", "{}"):
            ag.wm.remove(ppid, "program", "{}")
        ag.wm.add(ppid, "program", code)


def _pixel_residual_program(g0, g1):
    """한 pair 의 per-pair program 을 **pixel 잔차**(G0≠G1 인 셀만 그 출력색으로 재채색)로 물질화한다 —
    pixel 경로(_op_hypothesize PIXEL + _op_coloring)가 P0 에 대해 만드는 것과 **동일 형식·동일 산물**.
    같은 크기 pair 에서만 유효(크기변화 → None). 정답을 아는 게 아니라 '달라진 셀을 출력색으로'라는
    generic 재구성이라 §1-5 finder 아님(후보·기각이 없는 결정적 잔차). AST-json 방출(program_ast)."""
    if len(g0) != len(g1) or len(g0[0]) != len(g1[0]):
        return None
    import json
    from arbor.reasoning import program_ast as PA
    H, W = len(g0), len(g0[0])
    changed = [(r, c) for r in range(H) for c in range(W) if g0[r][c] != g1[r][c]]
    body = [PA.step("coloring", target=PA.ref("pixel", PA.const(r * W + c)), color=PA.const(g1[r][c]))
            for (r, c) in changed]
    return json.dumps(PA.program(body))
