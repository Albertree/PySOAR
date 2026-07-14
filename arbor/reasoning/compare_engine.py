# -*- coding: utf-8 -*-
"""ARBOR reasoning.compare_engine — compare receipt/relation 도출 (focus_solver 분리)."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arc.expr_solver import build_arckg, _load_value, _tup
from arbor.perception.nav import _edge_name, _lca, _receipt_leaves


def _store_receipt(ag, host_id, attr, val):
    """comparison receipt(result 하위)를 relation 노드 아래 **nested cascade** 로 적재한다.
    list(격자·좌표)는 셀 단위로 폭발시키지 않고 **통짜 한 leaf**(_tup), dict 는 하위 토글, scalar
    는 leaf. → category ▸ → size ▸ → {type, comp1, comp2} 로 **모든 property·COMM/DIFF 무관 전부**
    펼쳐진다 (사용자 요청: 전부 보여야 함). id 구분자는 노드와 동일하게 '.' 로 통일."""
    if isinstance(val, list):
        ag.wm.add(host_id, attr, _tup(val))              # 격자/좌표 = 통짜 한 leaf (폭발 금지)
    elif isinstance(val, dict):
        sub = f"{host_id}.{attr}"
        ag.wm.add(host_id, attr, sub)
        for k, v in val.items():
            _store_receipt(ag, sub, str(k), v)
    else:
        ag.wm.add(host_id, attr, val)


def _agree(a, b):
    """2차 개선(사용자 결정 2026-07-12): 두 1차 결과 노드를 **property tree 로 정렬**해 재귀 비교.
    **모든 노드가 {type, score, category} 로 통일**(구조 일관) — comp1/comp2 값은 안 넣음:
      · 내부노드(category 보유) → 자식별 _agree; score = 일치자식/전체, type = 전부일치면 COMM.
      · 잎(하위 없음, 예 contents) → 그 자체가 한 단위 비교 → **score 1/1(일치)·0/1(불일치)**, category={}.
        (둘 다 DIFF 도 일치=COMM = agreement.)"""
    ca, cb = a.get("category"), b.get("category")
    if isinstance(ca, dict) and isinstance(cb, dict):
        cat = {}
        for k in sorted(set(ca) | set(cb), key=str):
            cat[k] = (_agree(ca[k], cb[k]) if (k in ca and k in cb)
                      else {"type": "DIFF", "score": "0/1",
                            "comp1": ca.get(k, {}).get("type"), "comp2": cb.get(k, {}).get("type"),
                            "category": {}})
        comm = sum(1 for v in cat.values() if v["type"] == "COMM")
        tot = len(cat) or 1
        return {"type": "COMM" if comm == tot else "DIFF", "score": f"{comm}/{tot}", "category": cat}
    va, vb = a.get("type"), b.get("type")                          # 두 1차 verdict (COMM/DIFF)
    t = "COMM" if va == vb else "DIFF"
    return {"type": t, "score": "1/1" if t == "COMM" else "0/1",   # 잎: comp1/comp2 = 1차 verdict
            "comp1": va, "comp2": vb, "category": {}}               #   → COMM-COMM vs DIFF-DIFF 구분 보존


def _compare2(r0, r1):
    """2차(relation vs relation) 비교 = property-tree 정렬 + agreement + category별 score. id 는 nested 유지.
    현행 kg_compare(receipt,receipt)가 값까지 끌어와 {type,score,category} 봉투를 씌우던 것을 대체."""
    return {"id": {"id1": r0.get("id"), "id2": r1.get("id")}, "result": _agree(r0["result"], r1["result"])}


def _compare(a, b):
    """**단일 compare 진입점** (사용자 결정 2026-07-13): 들어온 인자 타입을 보고 자동분기.
      · 노드 × 노드          → property 비교(1차, ARCKG kg_compare: id·type·score·category + comp1/comp2 값).
      · 관계결과 × 관계결과    → agreement 비교(2차+, _compare2: 통일 nested·score·잎 comp1/comp2=1차 verdict).
    관계결과 = {"result": …} 를 가진 dict. 관계의 관계…(n차)도 이 분기로 재귀 처리된다."""
    from arbor.perception.arckg.comparison import compare as _kg   # vendored
    if isinstance(a, dict) and "result" in a and isinstance(b, dict) and "result" in b:
        return _compare2(a, b)
    return _kg(a, b)


def _store_relation(ag, receipt, anchor=None):
    """ARCKG compare() 의 comparison receipt(dict)를 relation edge 로 WM 에 적재한다
    (harness §0.5: relation = compare 결과 = edge). receipt 전체가 하나의 relation node:
    (edge ^type COMM/DIFF)(edge ^score n/total)(edge ^<property> COMM/DIFF). 반환 = node id.
    'type' 은 ARC-solver receipt 규약(result.type = 전체 COMM/DIFF); verdict 는 안 쓴다.

    이름·위치 = ARC-solver 의 relation json 파일과 동형: node id = '{LCA}/{E_a-b}' (LCA 폴더
    경로 + memory_paths 파일이름). edge 는 한 폴더에 뭉치지 않고 **각자의 LCA 노드** 아래로
    분산(P0 것은 P0, P1 것은 P1, 2차는 task root) 되어, 각 node 가 '하위 노드 무엇 vs 다른
    노드 무엇의 비교결과' 를 자기 이름으로 담는다. → WM 토글 트리에 cascade 로 보인다 (§2-5)."""
    res = receipt.get("result", {})
    idobj = receipt.get("id", "?")
    nodes = ag.kg.get("idx", {}).get("nodes", {})
    lca = anchor or _lca(_receipt_leaves(idobj))
    host = lca if (lca and lca in nodes) else "S1"
    rid = f"{lca or 'S1'}.{_edge_name(idobj, lca)}"       # ARC-solver 파일이름(E_a-b) — 구분자 '.' 로 통일
    ag.wm.add(rid, "type", res.get("type", "?"))          # 전체 COMM/DIFF (result.type 규약; top-level 요약)
    ag.wm.add(rid, "score", res.get("score", "?"))
    _store_receipt(ag, rid, "category", res.get("category", {}))   # category → nested cascade, 전부 (사용자 요청)
    ag.wm.add(host, "relation", rid)                      # LCA 노드 아래 개별 edge (folder 미러)
    ag.kg.setdefault("relations_wm", []).append(rid)
    return rid
