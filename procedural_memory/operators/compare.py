# -*- coding: utf-8 -*-
"""ARBOR operator body: compare (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.perception.perception import _score_frac
from arbor.reasoning.compare_engine import _compare, _store_relation
from procedural_memory.operators.observe import _imbalance_goal


def _op_compare(ag):
    """^cmp-active 가 가리키는 비교 하나를 수행(원자연산: kg_compare / imbalance / predict — array
    비교는 production 으로 못 하니 body 가 그 원자연산만). ^done 은 apply*compare 규칙이. 다음
    비교 선택(커서 이동)은 **select operator** 가 한다 (arg 결정 분리, 사용자 요청)."""
    sid = ag.stack[-1].id
    c = next((v for (i, a, v) in ag.wm if i == sid and a == "cmp-active"), None)
    if c is None:
        return
    kind = next((v for (i, a, v) in ag.wm if i == c and a == "kind"), None)
    _do_compare_kind(ag, sid, c, kind)


def _wm_vals(ag, cid, attr):
    return [v for (i, a, v) in ag.wm if i == cid and a == attr]


def _compare_pixels(ag, sid, c, g0, g1, kg_compare, nodes, idx):
    """PIXEL: G0-pixels ↔ G1-pixels 를 **같은 좌표끼리** 교차 비교(cross-grid 우선). 각 쌍 kg_compare →
    color/coord COMM/DIFF. **뺄셈·delta·크기비교 없음**(동등성만) — 좌표차/이동량 표현은 별도 단계.
    변화 셀(color DIFF)만 relation(receipt)으로 저장 = pixel 수준 변환 스펙(어느 셀이 어떻게 바뀌나)."""
    def _rc(p):
        j = nodes[p].to_json()["coordinate"]
        return (j["row_index"], j["col_index"])
    px1 = {_rc(p): p for p in idx.get("pixels", {}).get(g1, [])}
    for p0 in sorted(idx.get("pixels", {}).get(g0, [])):
        p1 = px1.get(_rc(p0))
        if p1 is None:
            continue
        rel = kg_compare(nodes[p0], nodes[p1])
        if rel["result"].get("category", {}).get("color", {}).get("type") == "DIFF":   # 색 바뀐 셀만 relation
            # anchor 없이 — pixel id(T..P0.G0.X21, T..P0.G1.X21)의 LCA=T..P0(pair) 아래 E_G0X21-G1X21 로
            # 저장(object relation 과 동일 관례). cmp 마커(S..cmp:pxmatch)를 앵커로 쓰면 S1 밑 잘못된 위치가 됨.
            _store_relation(ag, {"id": {"id1": p0, "id2": p1}, "result": rel["result"]})


def _do_compare_kind(ag, sid, c, kind):
    """cmp 마커 c 의 kind·arg(WM 에 선언적으로 있음)를 읽어 그 한 비교를 실행 (원자연산)."""
    kg_compare = _compare              # 단일 진입점(노드→property·관계→agreement 자동분기)
    idx = ag.kg["idx"]; nodes = idx["nodes"]
    if kind == "peers":
        _compare_peers(ag, sid, _wm_vals(ag, c, "member"))
    elif kind == "within":                                          # 한 pair G0↔G1 = 1차 변화
        g0, g1, p = _wm_vals(ag, c, "g0")[0], _wm_vals(ag, c, "g1")[0], _wm_vals(ag, c, "pair")[0]
        rel = kg_compare(nodes[g0], nodes[g1])
        _store_relation(ag, rel)                                   # (p ^relation p.E_G0-G1) + cascade
        ag.kg.setdefault("within_edge", {})[p] = rel               # cross-change 에서 재사용(kg dict)
    elif kind == "cross":
        which = _wm_vals(ag, c, "which")[0]
        _cross_grids(ag, sid, which, sorted(_wm_vals(ag, c, "pair")), kg_compare, nodes, idx)
    elif kind == "match":                                           # OBJECT: G0-objs ↔ G1-objs 대응
        g0, g1, p = _wm_vals(ag, c, "g0")[0], _wm_vals(ag, c, "g1")[0], _wm_vals(ag, c, "pair")[0]
        _compare_objects(ag, sid, c, g0, g1, p, kg_compare, nodes, idx)
    elif kind == "pxmatch":                                         # PIXEL: G0-pixels ↔ G1-pixels 교차
        g0, g1 = _wm_vals(ag, c, "g0")[0], _wm_vals(ag, c, "g1")[0]
        _compare_pixels(ag, sid, c, g0, g1, kg_compare, nodes, idx)
    elif kind == "predict":
        _predict_test_output(ag, sid)


def _compare_objects(ag, sid, c, g0, g1, pair, kg_compare, nodes, idx, topk=None):
    """한 train pair 의 **G0-objects × G1-objects 전부**를 kg_compare 해 유사도(score=COMM/전체)로
    내림차순 순위. 높은 순위 = GRID 간 대응(correspondence) 후보 — '어느 object 가 어느 것이 됐나'.
    (하드코딩 매칭 아님 — score 는 compare 결과에서, 순위는 그 정렬일 뿐, §1-5.)

    크기 관리(§2-5 는 가시성, 하지만 N×M full cascade 는 큰 격자에서 폭발):
      · 랭킹은 **상위 topk 만** (c ^match <mid>) 로 노출 + 총 비교 수(^n-compared) 로그.
      · full relation edge(무엇이 COMM/DIFF = per-object 변환 스펙)는 **G0-object 당 최선 대응 1개만**
        저장(N 개, N×M 아님) — 이게 hypothesize 가 쓸 변환 근거."""
    g0objs, g1objs = idx["children"].get(g0, []), idx["children"].get(g1, [])
    scored = []
    for a in g0objs:
        for b in g1objs:
            rel = kg_compare(nodes[a], nodes[b])
            n, tot = _score_frac(rel["result"].get("score", "0/1"))
            scored.append((n / tot, n, tot, a, b, rel))
    scored.sort(key=lambda t: (-t[0], t[3], t[4]))                # 유사도 ↓, 결정적 tiebreak
    # **대응 결과 = relation** 으로만 WM 에 남긴다 (LCA=pair 아래 E_G0O2-G1O0, S1 의 ARCKG 처럼 깔끔).
    # 전체 N×M 순위(옛 m0..mN 후보 무더기)는 WM 에 안 쏟는다 — 그건 중간 탐색값이라 kg dict 에만 두고,
    # 필요하면 대시보드가 참조한다. hypothesize 는 대응을 _fg_correspondence 로 재계산하므로 무영향.
    best = {}                                                      # G0-object 당 최선 대응
    for (sim, n, tot, a, b, rel) in scored:
        best.setdefault(a, rel)
    for rel in best.values():
        _store_relation(ag, rel)                                  # (pair ^relation pair.E_G0O2-G1O0) + cascade
    ag.wm.add(c, "n-compared", str(len(scored)))                  # 총 비교 수 하나(로그) — 개별 순위는 WM 밖
    ag.kg.setdefault("obj_match", {})[pair] = [(a, b, n, tot) for (sim, n, tot, a, b, rel) in scored]


def _cross_grids(ag, sid, which, pairs, kg_compare, nodes, idx):
    """두 훈련 pair 를 GRID 레벨에서 비교(structure mapping) — which: input(G0↔G0)·
    output(G1↔G1)·change((G0-G1)↔(G0-G1) 2차). LCA=TASK 아래 저장. property별 COMM/DIFF 를
    kg['cross'][which] 에 남겨 predict 가 이용."""
    p0, p1 = sorted(pairs)[:2]
    if which == "change":
        w = ag.kg.get("within_edge", {})
        if p0 in w and p1 in w:
            rel = kg_compare(w[p0], w[p1])         # 관계×관계 → _compare 가 agreement(2차)로 자동분기
            _store_relation(ag, rel)
            ag.kg.setdefault("cross", {})["change"] = rel
        return
    e0, e1 = dict(idx["edges"][p0]), dict(idx["edges"][p1])
    g0, g1 = e0.get(which), e1.get(which)
    if g0 and g1:
        rel = kg_compare(nodes[g0], nodes[g1])
        _store_relation(ag, rel)
        ag.kg.setdefault("cross", {})[which] = rel
        ag.wm.add(sid, f"{which}-fixed", "yes" if rel["result"]["type"] == "COMM" else "no")


def _compare_peers(ag, sid, group):
    """관측된 형제(pair)들의 property 비교 → COMM/DIFF. 불균형(다수는 있는 역할을 소수 하나가
    결핍; 예: Pa 에 output 없음)이면 goal 발견 = (node=결핍노드, produce=결핍역할).
    **각 pair 쌍(P0-P1·P0-Pa·P1-Pa)의 비교결과는 relation edge 로도 WM 에 남긴다** — grid/object
    비교와 동일 관례(§2-2·§2-5). LCA=TASK 아래 E_P0-P1 … 로 cascade (사용자 교정 2026-07-11:
    peers 비교가 결과를 relation 으로 안 남겨서 E_P0-P1 등이 WM 에 안 보이던 문제)."""
    kg_compare = _compare              # 단일 진입점(노드→property·관계→agreement 자동분기)
    from itertools import combinations
    idx = ag.kg["idx"]
    for a, b in combinations(sorted(group), 2):              # 모든 pair 쌍 → relation edge
        _store_relation(ag, kg_compare(idx["nodes"][a], idx["nodes"][b]))
    props = {m: idx["nodes"][m].to_json() for m in group}
    keys = sorted(set.intersection(*[set(p.keys()) for p in props.values()]))
    diff, imbal = [], None
    for k in keys:
        vals = [props[m][k] for m in group]
        if all(v == vals[0] for v in vals):
            ag.wm.add(sid, "comm", k)
        else:
            ag.wm.add(sid, "diff", k); diff.append(k)
            if imbal is None and len(group) >= 3 and isinstance(vals[0], dict):
                imbal = _imbalance_goal(group, props, k)
    if diff:
        gid = f"{sid}.goal"
        ag.wm.add(sid, "goal", gid)
        if imbal:
            ag.wm.add(gid, "node", imbal["minority"])               # e.g. Pa
            ag.wm.add(gid, "produce", imbal["missing"])             # e.g. output
        else:
            ag.wm.add(gid, "produce", ",".join(diff))


def _predict_test_output(ag, sid):
    """cross-pair 결과로 테스트 출력 Pa.G1 의 GRID 3속성(size·color·contents)을 채운다:
      - 출력끼리(G1↔G1) 전체 COMM → 출력 상수 → Pa.G1 = 관측된 훈련 출력 → 제출 준비.
      - 아니면 속성별(size·color): 출력끼리 그 속성 COMM 이면 그대로 / within 변화가 pair 간
        일관(2차 COMM)이면 그 공통변화 적용. contents 는 DIFF=범주형이라 표면비교로 못 얻어 제외.
      - 3속성 다 정해지면 ^answer-ready, 아니면 goal(produce 미결) → solve*fallback → object 하강."""
    root = ag.kg["arckg_root"]
    cross = ag.kg.get("cross", {})
    out_rel = cross.get("output")
    # ① 출력 상수? (두 훈련 출력이 표면 동일 → 테스트 출력도 그 상수)
    if out_rel is not None and out_rel["result"]["type"] == "COMM":
        ans = ag.task["train"][0]["output"]
        ag.kg["answer"] = ans
        ag.add_output_wme("answer", tuple(tuple(r) for r in ans))
        ag.wm.add(sid, "answer-ready", "yes")
        ag.wm.add(sid, "predict", "output=상수(불변) → Pa.G1 = 훈련 출력")
        pid = f"{root.node_id}.property"                      # 아티팩트 슬롯은 이제 property 아래
        ag.wm.remove(pid, "solution", "{}")                   # 빈 슬롯 → 채운 값으로
        ag.wm.add(pid, "solution", "output=상수(불변)")
        return
    # ② 속성별 도출 (size·color; contents 제외)
    out_cat = (out_rel or {}).get("result", {}).get("category", {})
    chg_cat = (cross.get("change") or {}).get("result", {}).get("category", {})
    got = {}
    for prop in ("size", "color"):
        if out_cat.get(prop, {}).get("type") == "COMM":
            got[prop] = "출력끼리 COMM → 그대로"
        elif chg_cat.get(prop, {}).get("type") == "COMM":
            got[prop] = "변화 일관 → 공통변화 적용"
        if prop in got:
            ag.wm.add(sid, f"predict-{prop}", got[prop])
    missing = [p for p in ("size", "color", "contents") if p not in got]   # contents 는 항상 미결
    ag.wm.add(sid, "predict", f"채움={list(got)} · 미결={missing}")
