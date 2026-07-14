# -*- coding: utf-8 -*-
"""ARBOR perception.nav — ARCKG index/navigation (focus_solver 에서 분리)."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from pysoar import Agent, Cond, Action, Production
from arc.expr_solver import build_arckg, _load_value, _tup


def index_arckg(root):
    nodes, parent, children, level, edges, pixels = {}, {}, {}, {}, {}, {}

    def walk(node, par, lvl):
        nid = node.node_id
        nodes[nid] = node
        parent[nid] = par
        level[nid] = lvl
        # (edge_name, child) -- the SAME edge names the existing ARCKG/expr_solver uses
        kid_edges = []
        if lvl == "task":
            for c in (getattr(node, "example_pairs", []) or []):
                kid_edges.append(("example", c))
            for c in (getattr(node, "test_pairs", []) or []):
                kid_edges.append(("test", c))
            for _, c in kid_edges:
                walk(c, nid, "pair")
        elif lvl == "pair":
            for attr, edge in (("input_grid", "input"), ("output_grid", "output")):
                g = getattr(node, attr, None)
                if g is not None:
                    kid_edges.append((edge, g))
                    walk(g, nid, "grid")
        elif lvl == "grid":
            for o in (getattr(node, "objects", None) or []):
                kid_edges.append(("object", o))
                walk(o, nid, "object")
            # PIXEL: grid.pixels 를 **GRID 직속**으로 별도 인덱싱한다 (children 이 아니라 pixels[gid] 로).
            # object 아래가 아니라 GRID 아래에 object 와 **형제**로 둔다 (사용자 2026-07-10): GRID 에서 바로
            # pixel 접근 · object 경유 시 같은 픽셀이 여러 object 에 중복되는 복잡성 회피. children 에 안 넣어
            # grid→object 하강은 불변; object 실패 후 grid.pixels 로 하강(_do_descend PIXEL 분기)만 이걸 쓴다.
            gpx = []
            for px in (getattr(node, "pixels", None) or []):
                pid = px.node_id
                nodes[pid] = px; parent[pid] = nid; level[pid] = "pixel"
                edges[pid] = []; children[pid] = []
                gpx.append(pid)
            pixels[nid] = gpx
        children[nid] = [c.node_id for _, c in kid_edges]
        edges[nid] = [(e, c.node_id) for e, c in kid_edges]

    walk(root, None, "task")
    return {"nodes": nodes, "parent": parent, "children": children,
            "level": level, "edges": edges, "pixels": pixels}


def _cursor(ag):
    """관측 커서 = 현재 substate 의 ^cursor (한 노드). observe 가 이걸 ^focus 그룹 안에서
    하나씩 옮기며 훑는다. (계층명 = ^level 대문자, 관측 대상 그룹 = ^focus, 커서 = ^cursor.)"""
    sid = ag.stack[-1].id
    return next((v for (i, a, v) in ag.wm if i == sid and a == "cursor"), None)


def _focus_group(ag, sid):
    """현재 substate 의 ^focus 값들 = 이 계층의 노드 그룹(관측 대상 = operator arg 후보 목록)."""
    return [v for (i, a, v) in ag.wm if i == sid and a == "focus"]


def _siblings(idx, f):
    par = idx["parent"][f]
    return [s for s in idx["children"].get(par, [])] if par else []


def _receipt_leaves(idobj):
    """comparison receipt 의 id(중첩 dict 또는 노드 id 문자열) → 모든 leaf 노드 id 목록.
    1차={id1,id2: node_id str}, n차=id1/id2 가 (n-1)차 id dict (comparison.py 규약)."""
    if isinstance(idobj, str):
        return [idobj]
    if not isinstance(idobj, dict):
        return []
    out = []
    for k in ("id1", "id2"):
        if k in idobj:
            out += _receipt_leaves(idobj[k])
    return out


def _lca(ids):
    """노드 id 들의 최장 공통 세그먼트 prefix = LCA 노드 id. ARC-solver memory_paths.
    _lca_node_id 의 n-원 확장 — relation(1·2·n차 edge)은 LCA 폴더 아래 저장됐다."""
    segs = [i.split(".") for i in ids if isinstance(i, str)]
    if not segs:
        return None
    common = []
    for tup in zip(*segs):
        if all(s == tup[0] for s in tup):
            common.append(tup[0])
        else:
            break
    return ".".join(common) if common else None


def _short(node_id, lca):
    """노드 id → LCA 상대 short name (ARC-solver memory_paths._short_name): LCA 이후 세그먼트를
    점 없이 이어붙임. 예) LCA="T0a.P0", "T0a.P0.G0.O2" → "G0O2"."""
    if lca and node_id.startswith(lca + "."):
        return node_id[len(lca) + 1:].replace(".", "")
    return node_id.split(".")[-1]


def _edge_name(idobj, lca):
    """comparison receipt 의 id → ARC-solver 파일이름 양식 edge 문자열(comparison._id_to_edge_str):
    leaf 노드 id = LCA 상대 short name, 두 피연산자를 E_{a}-{b} 로. 중첩(n차)은 괄호로 감싸
    '무엇과 무엇의 비교'가 보이게 한다. 예) E_G0-G1 · E_G0O0-G1O1 · E_(E_P0G0-P0G1)-(E_P1G0-P1G1)."""
    if isinstance(idobj, str):
        return _short(idobj, lca)
    a, b = idobj.get("id1"), idobj.get("id2")
    sa, sb = _edge_name(a, lca), _edge_name(b, lca)
    if isinstance(a, dict):
        sa = f"({sa})"
    if isinstance(b, dict):
        sb = f"({sb})"
    return f"E_{sa}-{sb}"


def _load_props(ag, nid, node, lvl):
    """노드의 **서술적 사실**을 (nid ^property nid.property) 아래 한 토글로 묶는다 (사용자 결정
    2026-07-09):
      · ^type      = 계층 메타(task/pair/grid/object) — 서술적이라 property 안으로.
      · to_json    = ARCKG 속성 전부.
      · 아티팩트 슬롯 = TASK.solution / PAIR.program (§6 파생 슬롯; 이후 hypothesize/generalize 가 채움).
    operator 가 만드는 **과정 마커(^seen·^cursor 등)는 property 밖**에 둔다 — '문제에 대한 사실' vs
    '에이전트가 한 것' 을 섞지 않기 위해. 솔버는 속성을 to_json() 으로 직접 읽으므로 이 묶음은 표시용."""
    pid = f"{nid}.property"
    ag.wm.add(nid, "property", pid)
    ag.wm.add(pid, "type", lvl)                        # 계층 메타(서술적)
    for k, v in node.to_json().items():
        _load_value(ag.wm, pid, k, v)
    if lvl == "task":                                 # 파생 아티팩트 슬롯 → property 아래
        ag.wm.add(pid, "solution", "{}")              # 빈 dict — 이후 흐름(generalize)이 채움
    elif lvl == "pair":
        ag.wm.add(pid, "program", "{}")               # 빈 dict — 이후 흐름(hypothesize/search)이 채움
