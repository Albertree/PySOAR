# -*- coding: utf-8 -*-
"""
focus_solver -- SLICE 1 of the goal-backward / focus-descent rebuild.

Replaces the hard-coded pipeline (observe->compare->generalize->compose) with the
agreed REFLEX LOOP, applied per node and driven by need/impasse:

solve is an UNDEFINED operator: the agent is given "solve the task" as a GOAL but has
NO knowledge of how. Proposing + selecting solve with no apply rule => OPERATOR
no-change impasse (the canonical SOAR "operator-implementation" subgoal). The substate
that opens exists to FIGURE OUT how to apply solve; focus descends one ARCKG level and
observe/compare gather what implementing it needs:

    S1  ^goal solve, ^focus TASK       -> OBSERVE task first (reveals its pairs P0,P1,Pa)
                                         -> then solve (focus now ^seen) -> ONC -> S2
    S2  ^focus P0                      -> observe P0 + COMPARE peers P0,P1,Pa:
                                             P0,P1 = {input:y, output:y} ; Pa = {input:y, output:n}
                                         -> IMBALANCE discovered HERE: Pa lacks 'output'
                                         -> ^goal DISCOVERED (S2 ^goal G)(G ^node Pa)(G ^produce output)
                                         -> solve (goal + focus seen) -> ONC -> S3
    S3  ^focus P0.G0 ...               -> observe + compare grids -> ^goal -> solve -> ONC -> S4
    ...

Perception->Deliberation->Action: observe (focus-gated) ALWAYS runs before solve
(solve is gated on the focus being ^seen). The GOAL (produce Pa.output) is NOT handed
down -- it is DISCOVERED inside S2 after observing and comparing all peers. solve keys
on ^goal (+ observed focus), so it never encodes "solve by comparing".

Scope (honest): no chunking / result-return is wired yet, so solve never actually
implements -- every level ONC-descends to the bottom, easy000a stays UNSOLVED. What is
verified is the principled control structure (undefined solve -> operator no-change ->
implement-subgoal -> descend, goal discovered in-substate). Wiring result + chunking so
solve produces the grid and is LEARNED is the next slice.

    python3 arc/focus_solver.py        # -> arc/focus_dashboard.html
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production          # noqa: E402
from arc.expr_solver import build_arckg, _load_value, _tup   # noqa: E402 (reuse, read-only)


# ---------------------------------------------------------------------------
# ARCKG index: id -> node / parent / children / level (so observe/compare/descend
# can walk the hierarchy the lens defines).
# ---------------------------------------------------------------------------
def index_arckg(root):
    nodes, parent, children, level, edges = {}, {}, {}, {}, {}

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
        children[nid] = [c.node_id for _, c in kid_edges]
        edges[nid] = [(e, c.node_id) for e, c in kid_edges]

    walk(root, None, "task")
    return {"nodes": nodes, "parent": parent, "children": children,
            "level": level, "edges": edges}


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


# ---------------------------------------------------------------------------
# operator bodies (RHS functions): the ARCKG/comparison work
# ---------------------------------------------------------------------------
def _load_props(ag, nid, node):
    """노드의 to_json 속성 전부를 (nid ^property nid.property) 아래 **한 토글**로 묶어 적재한다.
    → dashboard 에서 한 노드 토글 아래가 [property(1토글)] + [자식 node 토글들] + [개별 relation
    토글들] 로 정리된다 (사용자 요청 2026-07-08). 솔버는 속성을 WM 이 아니라 to_json() 으로 직접
    읽으므로(이 묶음은 표시 전용) 안전하다."""
    pid = f"{nid}.property"
    ag.wm.add(nid, "property", pid)
    for k, v in node.to_json().items():
        _load_value(ag.wm, pid, k, v)


def _artifact_slot(ag, nid, level):
    """harness §6 의 파생 아티팩트 슬롯을 노드에 건다: TASK.solution / PAIR.program.
    to_json property 가 아니라(task.py/pair.py 계약 상 관측만) *구조적 슬롯* 이므로 ^property 밖
    별도 edge 로 둔다. 비어있는 채로 시작하고, 이후 흐름(search→program · generalize→solution)이
    이 슬롯을 채운다. 이걸 driver 로 쓸 것: 슬롯이 비면 impasse → 하강."""
    if level == "task":
        ag.wm.add(nid, "solution", "{}")          # 빈 dict — 이후 흐름(generalize)이 채움
    elif level == "pair":
        ag.wm.add(nid, "program", "{}")           # 빈 dict — 이후 흐름(search)이 채움


def _op_observe(ag):
    """관측 커서 ^focus 가 가리키는 **단 하나**의 노드를 관측한다 (형제 곁다리 로드 없음 — 사용자
    교정: 관측된 것끼리만 compare 대상). 그 뒤 커서를 같은 계층(^level)의 다음 미관측 노드로
    옮긴다(하나하나 훑기). 계층 전부 관측되면 ^observed + 비교 agenda 를 짠다(compare 가 소비)."""
    idx, sid = ag.kg["idx"], ag.stack[-1].id
    f = _cursor(ag)
    if f is None:
        return                                  # arg(대상) 미정 → 변화 없음 → ONC impasse → arg-선택 substate
    node, lvl = idx["nodes"][f], idx["level"][f]
    ag.wm.add(f, "type", lvl)
    _load_props(ag, f, node)                    # 이 노드의 to_json → ^property 한 토글
    _artifact_slot(ag, f, lvl)                  # TASK.solution / PAIR.program 슬롯 (§6)
    for edge, c in idx["edges"][f]:
        ag.wm.add(f, edge, c)                   # 자식 존재(ref)
    # ^seen 표시 + cursor 소비는 apply*observe 규칙이 (body 뒤 settle 에서).


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
    elif kind == "object":
        # OBJECT: 각 train pair 의 G0-objects ↔ G1-objects 대응(correspondence). 하강 이유가
        # contents DIFF(=GRID 하위 구성요소의 변환을 알아야 함)라, GRID간 object 대응이 핵심
        # (GRID 내부 object 비교는 부차 — 사용자 설계). match = N×M kg_compare → score 순위.
        bygrid = {}
        for o in group:
            bygrid.setdefault(par[o], []).append(o)             # object → 그 grid
        bypair = {}
        for g in bygrid:
            bypair.setdefault(par[g], []).append(g)             # grid → 그 pair
        order = 0
        for p in sorted(pp for pp, gs in bypair.items() if len(gs) >= 2):   # G0·G1 다 있는 train pair
            g0, g1 = sorted(bypair[p])
            cid = f"{sid}.cmp:match.{p.split('.')[-1]}"
            ag.wm.add(cid, "g0", g0); ag.wm.add(cid, "g1", g1); ag.wm.add(cid, "pair", p)
            specs.append((cid, "match", order)); order += 1
    for cid, k, order in specs:
        ag.wm.add(sid, "cmp", cid)                       # 계층 아래 비교 목록(선언적)
        ag.wm.add(cid, "kind", k)
        ag.wm.add(cid, "order", str(order))
    if specs:
        ag.wm.add(sid, "to-compare", "yes")     # compare(arg 없이) 제안 → SELECT 가 cmp-active 세움
    else:
        ag.wm.add(sid, "compared", "yes")       # 비교 없음(object/단일) → 하강/정지


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


def _op_select(ag):
    """**arg-선택 substate 의 operator.** observe/compare 가 arg 없이 propose 되어 걸린 impasse 를
    푼다 — superstate 의 다음 관측/비교 대상을 preference(순서상 **첫 미완료** = a안)로 골라 super 의
    ^cursor / ^cmp-active 를 세운다. 그러면 super 의 observe/compare 가 그 arg 로 apply 가능해져
    impasse 가 해소되고 substate 는 pop 된다(fine_trace). §1-3 의 '후보 탐색'은 이 body 에 얹을 자리.
      select-for observe: 다음 미관측 focus → super ^cursor. 없으면 super ^observed + 비교 agenda.
      select-for compare: 다음 미완료 cmp → super ^cmp-active. 없으면 super ^compared."""
    sid = ag.stack[-1].id                                        # 현재 = arg-선택 substate
    sup = next((v for (i, a, v) in ag.wm if i == sid and a == "superstate"), None)
    for_op = next((v for (i, a, v) in ag.wm if i == sid and a == "select-for"), None)
    if for_op == "observe":
        idx = ag.kg.get("idx") if getattr(ag, "kg", None) else None
        # (A) 소속(membership) 순서 유지: 노드 id 로 정렬. id 가 계층적(parent.child)이라 정렬하면
        #     부모별로 묶인다 — P0.G0, P0.G1, P1.G0, P1.G1, Pa.G0. 부모를 넘나드는 마구잡이 관측 방지.
        unseen = sorted(n for n in _focus_group(ag, sup) if not ag.wm.contains(n, "seen", "yes"))
        if unseen:
            target = unseen[0]
            ag.wm.add(sup, "cursor", target)                    # super 커서 = 첫 미관측(정렬순)
            # (B) 상위 level cursor 유지: 관측 대상의 부모 노드를, 그 부모를 ^focus 로 가진 goal 의
            #     ^cursor 로 세운다(P0.G0 관측 중이면 PAIR goal ^cursor=P0). 하강해도 소속 path 가
            #     상위 level 에 유지된다(그 goal 은 관측 끝나 inert — 표시용).
            par = idx["parent"].get(target) if idx else None
            pgoal = next((i for (i, a, v) in ag.wm if a == "focus" and v == par), None) if par else None
            if pgoal is not None:
                for (i, a, v) in list(ag.wm):
                    if i == pgoal and a == "cursor":
                        ag.wm.remove(i, a, v)                   # 이전 부모 cursor 치우고
                ag.wm.add(pgoal, "cursor", par)                # 현재 부모로 갱신
        else:                                                    # 다 관측 → 비교 국면 전환
            ag.wm.add(sup, "observed", "yes")
            _build_agenda(ag, sup, _focus_group(ag, sup))        # (sup ^cmp ..) + ^to-compare
    elif for_op == "compare":
        pend = [(int(next(v for (i2, a2, v) in ag.wm if i2 == cid and a2 == "order")), cid)
                for (i, a, cid) in ag.wm if i == sup and a == "cmp"
                and not ag.wm.contains(cid, "done", "yes")]
        if pend:
            pend.sort(); ag.wm.add(sup, "cmp-active", pend[0][1])
        else:
            ag.wm.add(sup, "compared", "yes")
    ag.wm.add(sid, "selected", "yes")                            # 이 substate 는 대상 정함 → retract → pop


def _wm_vals(ag, cid, attr):
    return [v for (i, a, v) in ag.wm if i == cid and a == attr]


def _do_compare_kind(ag, sid, c, kind):
    """cmp 마커 c 의 kind·arg(WM 에 선언적으로 있음)를 읽어 그 한 비교를 실행 (원자연산)."""
    from ARCKG.comparison import compare as kg_compare
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
    elif kind == "predict":
        _predict_test_output(ag, sid)


def _score_frac(s):
    """kg_compare result.score('n/total' = COMM수/전체속성) → (n, total). robust."""
    try:
        n, tot = str(s).split("/")
        return int(n), int(tot) or 1
    except Exception:                                              # noqa: BLE001
        return 0, 1


def _compare_objects(ag, sid, c, g0, g1, pair, kg_compare, nodes, idx, topk=16):
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
    for rank, (sim, n, tot, a, b, rel) in enumerate(scored[:topk]):    # 상위만 노출(폭발 방지)
        mid = f"{c}.m{rank}"
        ag.wm.add(c, "match", mid)
        ag.wm.add(mid, "g0obj", a)
        ag.wm.add(mid, "g1obj", b)
        ag.wm.add(mid, "score", f"{n}/{tot}")
        ag.wm.add(mid, "rank", str(rank))
    ag.wm.add(c, "n-compared", str(len(scored)))                  # 총 N×M 비교 수(로그, §1-5)
    best = {}                                                      # G0-object 당 최선 대응
    for (sim, n, tot, a, b, rel) in scored:
        best.setdefault(a, rel)
    for rel in best.values():
        _store_relation(ag, rel)                                  # 변환 스펙(COMM/DIFF) 만 full 저장
    ag.kg.setdefault("obj_match", {})[pair] = [(a, b, n, tot) for (sim, n, tot, a, b, rel) in scored]


def _cross_grids(ag, sid, which, pairs, kg_compare, nodes, idx):
    """두 훈련 pair 를 GRID 레벨에서 비교(structure mapping) — which: input(G0↔G0)·
    output(G1↔G1)·change((G0-G1)↔(G0-G1) 2차). LCA=TASK 아래 저장. property별 COMM/DIFF 를
    kg['cross'][which] 에 남겨 predict 가 이용."""
    p0, p1 = sorted(pairs)[:2]
    if which == "change":
        w = ag.kg.get("within_edge", {})
        if p0 in w and p1 in w:
            rel = kg_compare(w[p0], w[p1])
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
    결핍; 예: Pa 에 output 없음)이면 goal 발견 = (node=결핍노드, produce=결핍역할)."""
    idx = ag.kg["idx"]
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
        ag.wm.remove(root.node_id, "solution", "{}")          # 빈 슬롯 → 채운 값으로
        ag.wm.add(root.node_id, "solution", "output=상수(불변)")
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
    if missing:                                                     # 표면비교로 다 못 채움 → 하강
        gid = f"{sid}.goal"
        ag.wm.add(sid, "goal", gid)
        ag.wm.add(gid, "produce", ",".join(missing))


# operator body(RHS 함수) = production 으로 못 하는 원자연산만:
#   observe = to_json 로드 · compare = kg_compare · select = 다음 대상 고르기(§1-3 탐색의 자리).
# 제어(무엇을 언제)는 전부 propose/apply 규칙 + WM 플래그로. solve 는 미구현(ONC=하강),
# submit 은 apply-only(답은 output-link 에).
OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare, "select": _op_select}


# ---------------------------------------------------------------------------
# productions -- FOCUS-SCOPED conditions (not a global flag pipeline). Each operator
# fires because of the gap at the CURRENT focus, and the order emerges from it.
# ---------------------------------------------------------------------------
# STATE-RELATIVE: <s> binds to the current (sub)state (the one holding ^focus). So the
# SAME rules fire in the top state and in every substate as attention descends -- a
# substate's focus (one level deeper) gets observed/compared by these same productions.
def _propose(name, conds):
    return _propose_named(f"propose*{name}", name, conds)


def _propose_named(prod_name, op_name, conds):
    # same RHS as _propose, but an explicit production name -- lets one operator
    # (solve) have TWO proposal variants (Soar's role*operator*variant convention).
    return Production(
        prod_name, conds,
        [Action("<s>", "operator", "<o>", "+"),
         Action("<o>", "name", op_name), Action("<o>", "node", "<f>")])


def _apply(name, attr):
    # writes the result flag ON THE FOCUS NODE the operator targeted (<o> ^node <f>)
    return Production(
        f"apply*{name}",
        [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", name), Cond("<o>", "node", "<f>")],
        [Action("<f>", attr, "yes")])


def _apply_state(name, *acts):
    # solving-pipeline apply: writes result flag(s) ON THE STATE <s> (the goal-holder),
    # not the focus node. ``acts`` = (attr, val[, pref]) tuples. Body (SOLVE_BODIES)
    # runs as this rule fires; the flags here gate the NEXT operator (generate-and-test).
    return Production(
        f"apply*{name}",
        [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", name)],
        [Action("<s>", a[0], a[1], a[2] if len(a) > 2 else "+") for a in acts])


def _propose_nonode(prod_name, op_name, conds):
    # arg(대상)를 붙이지 않고 operator 제안 (^node 없음). 대상은 arg-선택 substate 의 select 가
    # super 의 커서로 정한다 — "propose 에 arg 를 박지 않는다"(사용자 요청)의 실체.
    return Production(prod_name, conds,
                      [Action("<s>", "operator", "<o>", "+"), Action("<o>", "name", op_name)])


PRODUCTIONS = [
    # ── 관측/비교: arg(대상)를 propose 에 **박지 않는다.** super 에 세워진 ^cursor / ^cmp-active
    #    (= arg-선택 substate 의 select 가 정해준 것)가 있어야 apply 된다. 없으면 body·apply 규칙
    #    둘 다 변화 없음 → **ONC impasse → arg-선택 substate** 가 열리고 그 안 select 가 대상을 정함.
    _propose_nonode("propose*observe", "observe",
                    [Cond("<s>", "to-observe", "yes"), Cond("<s>", "observed", "<o>", negated=True)]),
    _propose_nonode("propose*compare", "compare",
                    [Cond("<s>", "to-compare", "yes"), Cond("<s>", "compared", "<x>", negated=True),
                     Cond("<s>", "answer-ready", "<ar>", negated=True)]),   # 답 나오면 compare 멈추고 submit
    # apply: super 커서(^cursor/^cmp-active)로 결과 플래그(^seen/^done) + 커서 **소비**(다음엔 다시 select).
    Production("apply*observe",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "observe"), Cond("<s>", "cursor", "<f>")],
               [Action("<f>", "seen", "yes"), Action("<s>", "cursor", "<f>", "-")]),
    Production("apply*compare",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "compare"), Cond("<s>", "cmp-active", "<f>")],
               [Action("<f>", "done", "yes"), Action("<s>", "cmp-active", "<f>", "-")]),

    # ── select: arg-선택 substate 안에서 한 번 발화 — body 가 super 커서(^cursor/^cmp-active)를
    #    세우고 자기 자신에 ^selected 표시. 그러면 -(^selected) 조건이 깨져 retract → substate 는
    #    더 고를 게 없어 SNC → fine_trace 가 pop → super 의 observe/compare 가 그 arg 로 apply.
    _propose_nonode("propose*select*observe", "select",
                    [Cond("<s>", "select-for", "observe"), Cond("<s>", "selected", "<x>", negated=True)]),
    _propose_nonode("propose*select*compare", "select",
                    [Cond("<s>", "select-for", "compare"), Cond("<s>", "selected", "<x>", negated=True)]),

    # submit: predict 가 답을 output-link 에 얹고 ^answer-ready → 제출·채점.
    _propose("submit", [Cond("<s>", "answer-ready", "yes"), Cond("<s>", "done", "<x>", negated=True)]),

    # solve = 미구현(apply·body 없음) → ONC impasse → 한 ARCKG 계층 하강(fine_trace._do_descend).
    _propose_named("propose*solve*bootstrap", "solve",
                   [Cond("<s>", "goal", "solve"), Cond("<s>", "observed", "yes")]),
    _propose_named("propose*solve*fallback", "solve",
                   [Cond("<s>", "goal", "<g>"), Cond("<g>", "produce", "<p>"),
                    Cond("<s>", "compared", "yes"), Cond("<s>", "answer-ready", "<a>", negated=True)]),

    _apply_state("submit", ("done", "yes")),
    # select·solve 는 apply 규칙 없음: select body 가 super 커서를 세우는 것(=arg 고르기, §1-3 탐색
    # 자리)이 곧 적용이고, solve 는 의도적 미구현(=하강).
]


# ---------------------------------------------------------------------------
# input + agent setup (mirrors expr_solver.setup_arc_agent shape so the tracer reuses it)
# ---------------------------------------------------------------------------
def inject_focus(ag):
    """INPUT: separate PERCEPTION from the agent's parsed MODEL (option a).

      input-link (percept):  I2 -^task-> <percept> -^raw-> {json}   [environment-owned, READ-ONLY]
      state (ARCKG model):   S1 -^arckg-> <root> -^example-> P0 ..  [observe/compare fill this]
      top goal:              S1 -^goal-> solve                      [drives solve; NO ^focus at top]
      attention:             S2 -^focus-> P0 ...                    [^focus lives on substates, descends]

    The environment delivers ONLY the raw, unparsed task onto ^io.input-link -- a
    PERCEPT node (its own id) carrying identity (^type/^name) + the literal ^raw dict.
    Perception is environment-owned and never mutated by the agent's operators.

    The parsed ARCKG is the agent's OWN structure, anchored on the top STATE via
    (S1 ^arckg <root>) -- NOT dangling off the input-link. observe/compare augment
    <root> and its descendants (the model), so a substate whose ^focus points one
    ARCKG level deeper is reading/extending the SUPERSTATE's shared, S1-anchored
    model (the SOAR 'substate reads superstate' regime) -- never the raw percept.

    <percept> and <root> are DISTINCT ids on purpose: if they were the same node,
    observe augmenting the model would still be mutating the input-link's percept.
    Justification for the two new symbols (per the no-free-symbols rule):
      ^arckg  -- anchors the agent-built model on its state, so the parse is a
                 deliberative structure, not part of environment perception.
      percept -- keeps perception a separate, immutable node the operators only read."""
    if ag.kg.get("arckg_root") is not None:
        return
    root = build_arckg(ag.task_id, ag.task)
    ag.kg["arckg_root"] = root
    ag.kg["idx"] = index_arckg(root)
    rid = root.node_id
    # (1) raw perception on the input-link -- a PERCEPT node distinct from the ARCKG
    #     root, so augmenting the model never touches what the environment delivered.
    pid = f"percept-{rid}"
    ag.add_input_wme("I2", "task", pid)              # input-link -> percept node
    ag.add_input_wme(pid, "type", "task")            # identity only
    ag.add_input_wme(pid, "name", ag.task_id)
    ag.add_input_wme(pid, "raw", json.dumps(ag.task))  # the literal task dict
    # (2) the parsed ARCKG root on the STATE + the top GOAL + the attention ^focus on the
    #     task. Perception-Deliberation-Action: observe (focus-gated) fires FIRST and
    #     reveals the task's children (the pairs); ONLY THEN does solve fire (it is gated
    #     on the focus being ^seen -- "look before you attempt", a universal ordering, NOT
    #     a domain method). solve, being UNIMPLEMENTED, then yields an operator no-change
    #     impasse and the substate descends one ARCKG level.
    ag.wm.add("S1", "arckg", rid)                     # ARCKG root lives on the state
    ag.wm.add("S1", "goal", "solve")                  # TOP GOAL: solve the task (bootstrap, under-specified)
    ag.wm.add("S1", "level", "TASK")                  # ARCKG 계층명(대문자)
    ag.wm.add("S1", "focus", rid)                     # 이 계층 노드 그룹 = TASK 하나
    ag.wm.add("S1", "to-observe", "yes")              # 관측할 게 있음 → observe(arg 없이) 제안 → impasse → select


def setup_focus_agent(task, tid="0a", record=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record, io=True)
    ag.task = task
    ag.task_id = tid
    ag.kg = {"_focus": True, "relations": [], "roles": []}     # _focus: dashboard detail 라우팅
    ag.input_functions.append(inject_focus)
    return ag


OP_DOCS = {
    "observe": "arg(대상) **없이** propose → ^cursor(=arg-선택 substate 의 select 가 세워줌)가 있을 때만 관측(property→^property)·^seen. 없으면 no-change → ONC impasse → arg-선택 substate",
    "compare": "arg 없이 propose → ^cmp-active(select 가 세워줌) 있을 때만 그 비교 수행(원자연산 kg_compare). 없으면 impasse. PAIR=peers(불균형→goal), GRID=within×pair→cross(삼중쌍)→predict",
    "select": "arg-선택 substate 안의 operator. observe/compare 가 arg 없이 걸린 impasse 를 푼다 — superstate 의 다음 대상을 preference(순서상 첫 미완료=a안)로 골라 super ^cursor/^cmp-active 세팅 → impasse 해소·pop. §1-3 탐색 자리",
    "submit": "predict 가 output-link 에 얹은 답 제출 → 채점 → ^done",
    "solve": "미구현 operator (apply·body 없음). goal 있고 이 레벨에서 답 못 냄 → 변화 없음 → operator no-change impasse → 한 계층 하강. (bootstrap: TASK 관측 후 PAIR 로)",
}


# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------
def _dash_data(task, tid="0a", max_cycles=1000):   # observe+compare+aggregate+find+solve+…×levels
    from arc.fine_trace import _Tracer
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    events = tr.run(max_cycles=max_cycles)
    wm_states, idx = [], {}
    for e in events:
        key = tuple(tuple(t) for t in e["wm"])
        if key not in idx:
            idx[key] = len(wm_states)
            wm_states.append(e["wm"])
        e["wm_state"] = idx[key]
        del e["wm"]
    # 제출 시도(3회 환경)를 대시보드 후보로: 각 시도의 답 격자 + 정답 여부.
    # HTML 은 c.answer 를 *테스트 pair 별 격자들의 리스트* 로 렌더(c.answer.map(grid)) →
    # 단일 test 답을 리스트로 감싼다.
    candidates = [{"answer": [a["answer"]] if a["answer"] else [],
                   "position": f"attempt {i + 1}: {a['hyp']}",
                   "color": "✓" if a["correct"] else "✗"}
                  for i, a in enumerate(tr.attempts)]
    correct_i = next((i for i, a in enumerate(tr.attempts) if a["correct"]), None)
    from arc.dashboard import wm_deltas
    return {
        "id": tid, "events": events, "wm_states": wm_deltas(wm_states),
        "grids": {"train": task["train"],
                  "test": [{"input": tp["input"]} for tp in task["test"]]},
        "candidates": candidates, "correct_attempt": correct_i, "n_steps": len(events),
    }


def _rules_manifest():
    return [{"name": p.name,
             "if": [{"id": c.id, "attr": c.attr, "val": c.value, "neg": c.negated} for c in p.conditions],
             "then": [{"id": a.id, "attr": a.attr, "val": a.value, "pref": a.pref} for a in p.actions]}
            for p in PRODUCTIONS]


def _safe_dash_data(task, tid, timeout_s=180):   # 제출 예산과 동일한 문제당 3분
    """_dash_data 를 **태스크당 타임아웃 + 예외 격리**로 감싼다. 일반 ARC-AGI 태스크는 솔버가
    가정한 구조(2 train + 1 test 등)와 달라 크래시하거나 오래 걸릴 수 있으므로, 한 태스크가
    전체 생성을 죽이지 않게 한다. 실패/초과 시 빈 이벤트 stub + ^error 필드 → 대시보드는 그
    태스크를 '무진행(n_steps=0)'으로 표시한다 (다양성 관찰이 목적이라 실패도 하나의 데이터)."""
    import signal
    class _TO(Exception):
        pass
    def _h(sig, frm):
        raise _TO()
    stub = {"id": tid, "events": [], "wm_states": [],
            "grids": {"train": task.get("train", []),
                      "test": [{"input": tp["input"]} for tp in task.get("test", [])]},
            "candidates": [], "correct_attempt": None, "n_steps": 0, "error": None}
    old = signal.signal(signal.SIGALRM, _h)
    try:
        signal.alarm(timeout_s)
        d = _dash_data(task, tid)
        signal.alarm(0)
        return d
    except _TO:
        stub["error"] = f"timeout>{timeout_s}s"
        return stub
    except Exception as e:                               # noqa: BLE001 (관찰용, 어떤 실패든 stub)
        stub["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return stub
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def make_dashboard(tasks, dataset="focus (slice 1)"):
    """tasks: [(tid, task_dict), ...] — 대시보드 TASK BROWSER 에 카드로 나열."""
    from arc.dashboard import _HTML
    if isinstance(tasks, dict):                        # 단일 태스크 하위호환: make_dashboard(task_dict)
        tasks = [("task", tasks)]
    dash = []
    for i, (tid, t) in enumerate(tasks, 1):
        d = _safe_dash_data(t, tid)
        term = "" if d["n_steps"] == 0 else ("✓풀림" if d.get("correct_attempt") is not None else "종료/중지")
        print(f"  [{i:2}/{len(tasks)}] {tid:12} n_steps={d['n_steps']:6} {d.get('error') or term}", flush=True)
        dash.append(d)
    data = {"dataset": dataset, "tasks": dash,
            "rules": _rules_manifest(), "op_docs": OP_DOCS}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_dashboard.html")
    with open(out, "w") as f:
        f.write(_HTML.replace("__DATA__", json.dumps(data)))
    return out


def _load_made_and_real():
    """대시보드에 띄울 태스크: 워크스루의 made000a/b + 실제 08ed6ac7 + easy000a."""
    import glob
    from arc.dataset import list_tasks, load_task
    here = os.path.dirname(os.path.abspath(__file__))
    tasks = []
    for tid in ("made000a", "made000b"):
        p = os.path.join(here, "data", "made", f"{tid}.json")
        if os.path.exists(p):
            tasks.append((tid, load_task(p)))
    real = glob.glob(os.path.expanduser("~/Desktop/ARC-solver/data/**/08ed6ac7.json"), recursive=True)
    if real:
        tasks.append(("08ed6ac7", load_task(real[0])))
    etid, epath = list_tasks("easy_a")[0]
    tasks.append((etid, load_task(epath)))
    return tasks


def _load_survey(n_agi=20, area_cap=200, agi_ids=None, include_easy=True, include_made=True):
    """다양성 관찰용 묶음: easy 9 + made 2 + ARC-AGI 문제.
    - agi_ids 지정 시: **그 id 들 정확히** 사용(area 필터 무시) — 서브셋 재생성용.
    - 미지정 시: training 에서 **max(train grid area) ≤ area_cap** (≈≤14x14) 인 것 앞에서 n_agi 개.
      WM 정렬 병목이 격자크기 비례라 시간/크기 예산 보호. 정렬 결정적 — 재현 가능.
    목적은 풀이가 아니라 '현재 로직이 낯선 태스크에 어떻게 적용되나' 관찰(harness §2-4)."""
    import glob
    from arc.dataset import list_tasks, load_task
    here = os.path.dirname(os.path.abspath(__file__))
    tasks = []
    if include_easy:
        tasks += [(tid, load_task(p)) for tid, p in list_tasks("easy_a")]     # easy 9
    if include_made:
        for tid in ("made000a", "made000b"):                                 # made 2
            p = os.path.join(here, "data", "made", f"{tid}.json")
            if os.path.exists(p):
                tasks.append((tid, load_task(p)))
    agi_root = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI")
    if agi_ids:                                                              # 명시 id 셋
        for tid in agi_ids:
            hits = glob.glob(os.path.join(agi_root, "**", f"{tid}.json"), recursive=True)
            if hits:
                tasks.append((tid, load_task(hits[0])))
        return tasks
    picked = 0                                                              # 자동 선택
    for p in sorted(glob.glob(os.path.join(agi_root, "training", "*.json"))):
        if picked >= n_agi:
            break
        t = load_task(p)
        try:
            area = max(len(g["input"]) * len(g["input"][0]) for g in t["train"])
        except Exception:                                                    # noqa: BLE001
            continue
        if area > area_cap:
            continue
        tasks.append((os.path.splitext(os.path.basename(p))[0], t))
        picked += 1
    return tasks


# 고정 관찰 세트 (사용자 지정 2026-07-09): easy 9 + made 2 + 실제 ARC-AGI 4 = 15
SURVEY_AGI = ["08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab"]

if __name__ == "__main__":
    # made000a/b 가 없으면 먼저 생성
    from arc.make_made_tasks import write_all
    write_all()
    tasks = _load_survey(agi_ids=SURVEY_AGI)
    print(f"survey: easy 9 + made 2 + ARC-AGI {len(SURVEY_AGI)} — 총 {len(tasks)} 태스크 (max_cycles=1000)")
    out = make_dashboard(tasks, dataset="survey (easy·made·ARC-AGI 15)")
    sz = os.path.getsize(out) / 1e6
    print(f"wrote {out}  ({sz:.1f} MB)\nopen it:  open {out}")
