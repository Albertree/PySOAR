# -*- coding: utf-8 -*-
"""
thinking_ops -- ARBOR의 고정 "생각 operator"를 focus_solver 위에 얹는 모듈.

원칙(사용자 제약):
  - operator는 고정·일반. 계층 이름 금지. args는 WM/다른 operator 산물에서만.
  - 관계(relation)는 카탈로그가 아니라 *도출*한다: compare → refine(greater/less)
    → aggregate(role). "가장 큰/긴"은 여기서 만들어진다 (wiki arckg-node-edge의
    "가장 긴 회색 막대" 요구).
  - 근거 없는 새 property/operator 금지. 아래 SCHEMA는 ARC-solver/ARCKG/*.py 의
    실제 to_json() 스키마(GRID 3·OBJECT 8·PIXEL 2·TASK/PAIR roles)에서만 나온다.

이 모듈은 순수 함수(SCHEMA/components/derive_*) + 두 operator body(_op_aggregate)
+ 대시보드 detail 렌더(focus_detail)만 제공한다. productions 는 focus_solver 가
자기 헬퍼(_propose/_apply)로 만든다 (한 곳에서 규칙을 본다).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SCHEMA -- 각 ARCKG property 를 orderable(순서형: greater/less 가능) 과
# presence/categorical(COMM/DIFF 만) 로 가른다. 실제 to_json 스키마 그대로.
#   orderable : area(int) · size{height,width} · position{corner{row,col}} ·
#               coordinate{row,col}(PIXEL) · GRID size
#   presence  : color{0..9} · symmetry{..} · method{..} · roles{..}
#   categorical: contents · shape · coordinate(list, OBJECT)
# ---------------------------------------------------------------------------
ORDERABLE_PROPS = {"area", "size", "position", "coordinate"}


def components(prop, val):
    """orderable property 를 (component_name, scalar) 목록으로 평탄화한다.
    presence/categorical/알 수 없는 모양이면 [] (비교엔지엔 안 태움)."""
    if prop == "area" and isinstance(val, int) and not isinstance(val, bool):
        return [("area", val)]
    if prop == "size" and isinstance(val, dict):
        return [(f"size.{k}", val[k]) for k in ("height", "width")
                if isinstance(val.get(k), int)]
    if prop == "position" and isinstance(val, dict):
        out = []
        for corner, rc in val.items():
            if isinstance(rc, dict):
                for k in ("row_index", "col_index"):
                    if isinstance(rc.get(k), int):
                        out.append((f"position.{corner}.{k}", rc[k]))
        return out
    if prop == "coordinate" and isinstance(val, dict):        # PIXEL only
        return [(f"coordinate.{k}", val[k]) for k in ("row_index", "col_index")
                if isinstance(val.get(k), int)]
    return []


# ---------------------------------------------------------------------------
# refine -- 형제 group 을 orderable component 별로 pairwise 비교 → greater 관계.
# (less 는 greater 의 역이라 저장 안 함. aggregate 가 greater 만으로 role 계산.)
# ---------------------------------------------------------------------------
def derive_relations(group, props):
    """group: 노드 id 목록. props: {nid: to_json()}.
    반환: [{"a","b","on","kind":"greater"}]  (a 가 b 보다 on 에서 큼)."""
    rels = []
    if len(group) < 2:
        return rels
    keys = sorted(set.intersection(*[set(props[m].keys()) for m in group]))
    for k in keys:
        if k not in ORDERABLE_PROPS:
            continue
        # component -> {member: scalar}
        comp_vals: dict = {}
        ok = True
        for m in group:
            comps = components(k, props[m][k])
            if not comps:                      # 이 property 가 이 노드에선 순서형 아님
                ok = False
                break
            for cname, s in comps:
                comp_vals.setdefault(cname, {})[m] = s
        if not ok:
            continue
        for cname, mv in comp_vals.items():
            if len(set(mv.values())) <= 1:     # 전부 같음 → COMM (관계 없음)
                continue
            for a in group:
                for b in group:
                    if a != b and mv[a] > mv[b]:
                        rels.append({"a": a, "b": b, "on": cname, "kind": "greater"})
    return rels


def derive_roles(group, rels):
    """greater 관계에서 role 도출: 어떤 component 에서 *모든 참여자보다 큼* =
    extremum+ (예: 최대 area), *모두보다 작음* = extremum-.  ("가장 큰"의 정체)."""
    roles = []
    comps = sorted(set(r["on"] for r in rels))
    for c in comps:
        gcount: dict = {}
        present: set = set()
        for r in rels:
            if r["on"] != c:
                continue
            gcount[r["a"]] = gcount.get(r["a"], 0) + 1
            present.add(r["a"])
            present.add(r["b"])
        parts = [m for m in group if m in present]
        if len(parts) < 2:
            continue
        for m in parts:
            g = gcount.get(m, 0)
            if g == len(parts) - 1:
                roles.append({"node": m, "on": c, "role": "extremum+"})
            elif g == 0:
                roles.append({"node": m, "on": c, "role": "extremum-"})
    return roles


# ---------------------------------------------------------------------------
# WME 표기 -- 관계·역할을 WM 에 남겨 대시보드 WM 패널에서 "채워지는" 걸 보이게.
#   관계(승자에 부착, arckg-node-edge 의 relational profile):
#       (a ^greater "on # b")
#   역할:
#       (node ^role "extremum+ # on")
# ---------------------------------------------------------------------------
def _short(nid):
    return str(nid).split(".")[-1]


def write_relations(ag, f, group, props):
    """compare 가 부른다: focus f 의 형제 group 에서 관계를 도출해 WM+원장에 기입.
    관계가 하나라도 생기면 (f ^gather-pending yes) 를 세워 aggregate 를 부른다."""
    rels = derive_relations(group, props)
    if not rels:
        return 0
    for r in rels:
        ag.wm.add(r["a"], "greater", f"{r['on']} # {_short(r['b'])}")
    ag.kg.setdefault("relations", []).extend(rels)
    ag.kg["last_relations"] = rels
    ag.wm.add(f, "gather-pending", "yes")      # aggregate 게이트 (관계가 쌓였다)
    return len(rels)


def _op_aggregate(ag):
    """aggregate operator body: gather-pending 인 focus 의 형제 group 에서
    쌓인 greater 관계 → role(extremum+/-) 도출해 WM+원장에 기입."""
    from arbor.solver import _focus, _siblings          # 지연 import (순환 방지)
    idx, f = ag.kg["idx"], _focus(ag)
    group = [s for s in _siblings(idx, f)]
    rels = [r for r in ag.kg.get("relations", []) if r["a"] in group and r["b"] in group]
    roles = derive_roles(group, rels)
    for ro in roles:
        ag.wm.add(ro["node"], "role", f"{ro['role']} # {ro['on']}")
    ag.kg.setdefault("roles", []).extend(roles)
    ag.kg["last_roles"] = roles
    if roles:                                    # role 도출됨 → find 가 대상 선택할 차례
        ag.wm.add(f, "select-pending", "yes")    # (gathering 체인: aggregate→find, tie 방지)


# ---------------------------------------------------------------------------
# 대시보드 detail -- focus_solver 의 kg 모양에 맞춘 하단 패널 데이터.
# (dashboard._kg_detail 이 kg.get("_focus") 를 보고 이걸 호출.)
# ---------------------------------------------------------------------------
def focus_detail(kg, op):
    if op in ("find", "hypothesize", "predict", "evaluate", "verify", "compose", "submit"):
        from arbor.reasoning.solve_ops import solve_detail
        return solve_detail(kg, op)
    if op == "observe":
        return {"kind": "observe", "note": "focus 노드 property + 자식 존재 적재"}
    if op == "compare":
        rels = kg.get("last_relations", [])
        cmps = kg.get("compares", [])
        last = cmps[-1] if cmps else {}
        return {"kind": "compare",
                "comm": last.get("comm", []), "diff": last.get("diff", []),
                "relations": [{"a": _short(r["a"]), "b": _short(r["b"]),
                               "on": r["on"], "kind": r["kind"]} for r in rels]}
    if op == "aggregate":
        roles = kg.get("last_roles", [])
        return {"kind": "aggregate",
                "roles": [{"node": _short(r["node"]), "on": r["on"],
                           "role": r["role"]} for r in roles]}
    return {"kind": op}
