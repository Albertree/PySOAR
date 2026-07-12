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
    from ARCKG.comparison import compare as _kg
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


# ---------------------------------------------------------------------------
# operator bodies (RHS functions): the ARCKG/comparison work
# ---------------------------------------------------------------------------
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
    idx = ag.kg.get("idx") if getattr(ag, "kg", None) else None
    # 무엇을 고를지는 **WM 상태에서 추론**한다 (select-for 값에 의존하지 않음, 사용자 요청):
    #   미관측 focus 노드가 있으면 → 관측 대상(super ^cursor). 관측이 다 끝났으면(없으면) → observed 전환
    #   후, 미완료 cmp 를 비교 대상(super ^cmp-active), 그것도 없으면 compared. (관측이 비교보다 먼저 오므로
    #   'unseen 유무 → observed → cmp' 우선순위가 기존 select-for observe/compare 분기를 그대로 재현.)
    unseen = sorted(n for n in _focus_group(ag, sup) if not ag.wm.contains(n, "seen", "yes"))
    if unseen:                                                   # (A) 관측 대상: 소속 순서(노드 id 정렬)로 첫 미관측
        target = unseen[0]
        ag.wm.add(sup, "cursor", target)                        # super 커서 = 첫 미관측(정렬순 = 부모별 묶임)
        # (B) 상위 level cursor 유지: 관측 대상의 부모를 그 부모를 ^focus 로 가진 goal 의 ^cursor 로 세워
        #     하강해도 소속 path 가 상위 level 에 남게 한다.
        par = idx["parent"].get(target) if idx else None
        pgoal = next((i for (i, a, v) in ag.wm if a == "focus" and v == par), None) if par else None
        if pgoal is not None:
            for (i, a, v) in list(ag.wm):
                if i == pgoal and a == "cursor":
                    ag.wm.remove(i, a, v)
            ag.wm.add(pgoal, "cursor", par)
    elif not ag.wm.contains(sup, "observed", "yes"):            # 다 관측 → 비교 국면 전환
        ag.wm.add(sup, "observed", "yes")
        _build_agenda(ag, sup, _focus_group(ag, sup))            # (sup ^cmp ..) + ^to-compare
    else:                                                        # 관측 끝 → 비교 대상: 미완료 cmp 중 첫(order)
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


def _score_frac(s):
    """kg_compare result.score('n/total' = COMM수/전체속성) → (n, total). robust."""
    try:
        n, tot = str(s).split("/")
        return int(n), int(tot) or 1
    except Exception:                                              # noqa: BLE001
        return 0, 1


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
    # 하강 goal 은 여기서 세우지 않는다 — GRID hypothesize 가 within(G0→G1) 변환을 속성별로 결론지으려
    # 시도한 뒤, 못 내면 그때 goal(produce=미결)을 세운다 (predict↔hypothesize 가 동시에 solve 를
    # 제안해 operator-tie 나는 것 방지; 하강 여부는 hypothesize 의 판정이 주도, 사용자 교정 2026-07-11).


def _obj_cc(node):
    """ARCKG object node → (절대 셀 목록, 색). color dict 중 True 인 것이 그 object 색."""
    j = node.to_json()
    return [tuple(c) for c in j["coordinate"]], next((k for k, v in j["color"].items() if v), 0)


def objects_of(grid):
    """grid 의 4-연결 동색 성분 **전부**(색0 도 하나의 색으로 취급 — background 로 단정해 버리지 않음).
    (셀목록, 색) 을 첫셀·색으로 정렬해 반환. program_report 의 objects_of(실행 DSL)와 **동일 알고리즘**이라
    _fg_index 가 매긴 인덱스가 그대로 합성 program 의 in_objs[i] 에 맞는다."""
    H, W = len(grid), len(grid[0])
    seen, objs = set(), []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen:
                continue
            col, stack, cells = grid[r][c], [(r, c)], []
            while stack:
                y, x = stack.pop()
                if (y, x) in seen or not (0 <= y < H and 0 <= x < W) or grid[y][x] != col:
                    continue
                seen.add((y, x)); cells.append((y, x))
                stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
            objs.append((sorted(cells), col))
    return sorted(objs, key=lambda cc: (cc[0][0], cc[1]))


def _fg_correspondence(ag, gid0, gid1, g0grid, g1grid):
    """G0 ↔ G1 object 를 유사도 greedy 1-1 대응(중복 없이). **색0 도 하나의 색**으로 포함하되,
    object 정의상 **단색 성분만** 쓴다(격자 전체 같은 비단색 복합노드는 제외 — '0=배경' 가정이 아니라
    '객체=한 색'이라는 원칙). 닫힌 내부영역=구멍(단색 색0)도 정당한 재채색 대상이 된다. 각 대응쌍의
    속성별 COMM/DIFF 도 반환 — 어떤 DSL 을 쓸지 **규칙이 판단**할 근거. 반환 = [(g0obj, g1obj, category)].
    (kg_compare 는 원자연산; 대응·COMM/DIFF 는 데이터, 조립·arg결정은 이후 **규칙**이 한다.)"""
    kg_compare = _compare              # 단일 진입점(노드→property·관계→agreement 자동분기)
    idx = ag.kg["idx"]; nodes = idx["nodes"]

    def _mono(o, grid):     # object 셀이 격자에서 실제로 한 색인가 — 비단색(격자/복합 노드)은 배제
        cells, _ = _obj_cc(nodes[o])
        cols = {grid[r][c] for (r, c) in cells if 0 <= r < len(grid) and 0 <= c < len(grid[0])}
        return len(cols) <= 1
    o0 = [o for o in idx["children"].get(gid0, []) if _mono(o, g0grid)]   # 0 도 색; 단색만
    o1 = [o for o in idx["children"].get(gid1, []) if _mono(o, g1grid)]
    scored = []
    for a in o0:
        for b in o1:
            rel = kg_compare(nodes[a], nodes[b])
            n, tot = _score_frac(rel["result"].get("score", "0/1"))
            scored.append((n / tot, a, b, rel["result"].get("category", {})))
    scored.sort(key=lambda x: -x[0])
    usedA, usedB, out = set(), set(), []
    for _s, a, b, cat in scored:
        if a in usedA or b in usedB:
            continue
        usedA.add(a); usedB.add(b); out.append((a, b, cat))
    return out


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
    (색 s, cmap[s]=t≠s)을 묶어 apply_DSL(coloring). map 을 셀묶음 재채색으로 물질화한 level-1 program."""
    H, W = len(g0grid), len(g0grid[0])
    bytarget = {}
    for r in range(H):
        for c in range(W):
            s = g0grid[r][c]; t = cmap.get(s, s)
            if t != s:
                bytarget.setdefault(t, []).append([r, c])
    lines = ["in_px = pixels_of(input_grid)", "", "tfg0 = input_grid"]
    for k, t in enumerate(sorted(bytarget)):
        lines.append(f"# 전역 색맵: {len(bytarget[t])}개 셀 → 색 {t}")
        lines.append(f"tfg{k + 1} = apply_DSL(tfg{k}, coloring, {bytarget[t]}, {t})")
    lines.append(f"output_grid = tfg{len(bytarget)}")
    return "\n".join(lines)


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


def _op_hypothesize(ag):
    """**hypothesize = 시뮬레이션 open** (조립·검증은 규칙이!). object mapping 대응을 얻어,
    각 대응쌍을 **변환 후보(xform)** 로 WM 에 노출한다 — 속성별 COMM/DIFF 를 그대로 실어(규칙이
    'color DIFF ∧ coordinate COMM → coloring' 을 판단). 시뮬 grid 를 G0(input)로 초기화.
    조립은 이후 coloring operator(규칙 propose/apply)가, 검증은 verify operator 가 한다.
    (여기 body 는 '지각'만 — 대응/COMM-DIFF 노출 + 시뮬 초기화. 조립 로직은 Python 아님·규칙.)"""
    idx, sid = ag.kg["idx"], ag.stack[-1].id
    root = ag.kg["arckg_root"]
    p0 = root.example_pairs[0]
    gid0, gid1 = p0.input_grid.node_id, p0.output_grid.node_id
    ag.wm.add(sid, "sim-pair", p0.node_id)

    g0grid = [list(r) for r in ag.task["train"][0]["input"]]
    g1grid = [list(r) for r in ag.task["train"][0]["output"]]
    if ag.wm.contains(sid, "level", "GRID"):
        # ── GRID hypothesize (사용자 2026-07-11): object/pixel 이 contents 가설을 세우듯, GRID 는
        #    **grid.size·grid.color 가설**을 GRID 비교 관계로부터 생성·검증한다. 절차 시나리오가 아니라
        #    속성마다 `_grid_property_hypotheses` 로 후보(keep/const/transform)를 만들어 train 대조로
        #    채택/기각(§2-2 근거=COMM/DIFF · §4-1 generate-and-test). 관계가 가설을 *고르고*, 검증이 *결정*.
        #      · size/color 중 하나라도 결론 못 냄 → 그 속성은 object/pixel property 의존 → 하강.
        #      · contents 는 GRID 표면 독립 도출 불가 — size·color 규칙이 train 을 재현해야만 '설명'된다.
        #        (size COMM + 전역색맵 재현) → GRID 종결(program+답). 아니면 contents 미결 → 하강.
        train = ag.task["train"]
        within = ag.kg.get("within_edge", {}).get(p0.node_id) or {}
        wcat = within.get("result", {}).get("category", {})
        ocat = (ag.kg.get("cross", {}).get("output") or {}).get("result", {}).get("category", {})
        concl, chosen = {}, {}
        for prop in ("size", "color"):                              # grid.size·grid.color 가설 생성·검증
            hid = f"{sid}.gh.{prop}"
            wt, ot = wcat.get(prop, {}).get("type", "?"), ocat.get(prop, {}).get("type", "?")
            ag.wm.add(sid, "grid-hyp", hid); ag.wm.add(hid, "prop", prop)
            ag.wm.add(hid, "within", wt); ag.wm.add(hid, "cross-out", ot)   # 어떤 관계가 가설을 시사했나
            cands = _grid_property_hypotheses(prop, train, wt, ot)
            log = ag.kg.setdefault("hyp_trials", [])                # **전체 시도표는 WM 아닌 kg 리스트로**(용량안전)
            for cand in cands:                                      # 생성·기각 후보 전부 노출(object/pixel 와 동형)
                ag.wm.add(hid, "cand", f"{cand['kind']}:{cand['pred']}:{'✓' if cand['ok'] else '✗'}")  # WM=요약만
                # kg 로그 = 후보 1행 (표/CSV 용). 관계가 시사한 가설(kind)과 채택여부.
                log.append({"task": ag.task_id, "level": "GRID", "target": prop, "kind": cand["kind"],
                            "candidate": cand["pred"], "verdict": "pass" if cand["ok"] else "fail",
                            "per_pair": None})
                if prop == "size" and cand["kind"] == "transform":     # 크기식 brute-force = 후보별 per-pair 테스트
                    for ax in ("H", "W"):
                        for desc, ok in cand.get("tried", {}).get(ax, [])[:6]:
                            ag.wm.add(hid, "tried", f"{ax}1={desc}:{'✓' if ok else '✗'}")  # WM=앞 6개만
                        for tr in cand.get("trials", {}).get(ax, []):   # kg=전체 (생성→즉시 테스트→결과)
                            log.append({"task": ag.task_id, "level": "GRID", "target": "size",
                                        "kind": f"transform·{ax}", "candidate": tr["candidate"],
                                        "verdict": "pass" if tr["verdict"] else "fail",
                                        "per_pair": tr["per_pair"]})
            win = next((c for c in cands if c["ok"]), None)
            if win:
                ag.wm.add(hid, "status", f"결론 [{win['kind']}] {win['pred']}")
                concl[prop] = f"{win['kind']}:{win['pred']}"; chosen[prop] = win
            else:
                ag.wm.add(hid, "status", "미결 — object/pixel property 의존 → 하강")
        # contents: size·color 규칙이 train 을 재현하면 '설명', 아니면 미결.
        chid = f"{sid}.gh.contents"; ag.wm.add(sid, "grid-hyp", chid); ag.wm.add(chid, "prop", "contents")
        ag.wm.add(chid, "within", wcat.get("contents", {}).get("type", "?"))
        cmap = (chosen.get("color") or {}).get("map")
        size_keep = (chosen.get("size") or {}).get("kind") == "keep"
        if size_keep and cmap and [[cmap.get(v, v) for v in r] for r in g0grid] == g1grid:
            # 크기 유지 + 전역색맵이 train 재현 → GRID 에서 종결(전역 recolor program + 테스트 답)
            ppid = f"{p0.node_id}.property"
            if ag.wm.contains(ppid, "program", "{}"):
                ag.wm.remove(ppid, "program", "{}")
            ag.wm.add(ppid, "program", _global_recolor_program(g0grid, cmap))
            ag.wm.add(chid, "status", "설명됨(전역색맵으로 train 재현)")
            ag.wm.add(sid, "hypothesized", "yes")
            tin = ag.task["test"][0]["input"]
            ans = [[cmap.get(v, v) for v in row] for row in tin]
            ag.kg["answer"] = ans
            ag.add_output_wme("answer", tuple(tuple(r) for r in ans))
            ag.wm.add(sid, "answer-ready", "yes"); ag.wm.add(sid, "grid-verdict", "GRID 종결(전역색맵)")
            return
        ag.wm.add(chid, "status", "미결(셀단위 — object/pixel 로 하강)")
        # size/color 를 GRID 에서 결론했으면 그 예측을 남기고, contents(및 미결 속성)만 하강한다.
        miss = [p for p in ("size", "color") if p not in concl] + ["contents"]
        ag.wm.add(sid, "grid-verdict",
                  f"GRID 예측 size={concl.get('size', '미결')} · color={concl.get('color', '미결')} → 미결={miss} 하강")
        gid = f"{sid}.goal"                                          # 하강 goal (predict 대신 여기서)
        ag.wm.add(sid, "goal", gid); ag.wm.add(gid, "produce", ",".join(miss))
        return
    if ag.wm.contains(sid, "level", "PIXEL"):
        # PIXEL 가설 = **잔여(residual) 처리**: 상위(object) substate 가 재채색한 sim·program 을 이어받아,
        # object 로 못 맞춘 셀(그 sim 이 아직 G1 과 다른 셀)만 pixel 로 재채색해 **object 가설에 덧붙인다**.
        # object 로 완결된 문제(845·868·08ed)는 애초에 PIXEL 로 안 내려온다(object verify 통과). object 가
        # 일부만 처리한 문제(예: 009d5c81)는 그 sim 에서 이어받아 잔여만 pixel 이 마감한다.
        sup = ag.stack[-2].id if len(ag.stack) >= 2 else None
        base_sim = next((v for (i, a, v) in ag.wm if i == sup and a == "sim"), None) if sup else None
        base_prog = next((v for (i, a, v) in ag.wm if i == sup and a == "program-code"), None) if sup else None
        sim0 = [list(r) for r in base_sim] if base_sim else [list(r) for r in g0grid]  # object 재채색 후 상태
        ag.wm.add(sid, "sim", _tup(sim0))                       # pixel sim = object 재채색 결과에서 이어감
        if base_prog:
            ag.wm.add(sid, "base-program", base_prog)           # 덧붙일 object 가설(program)
        # 잔여: object 재채색 후에도 G1 과 다른 셀만. object xform 과 같은 WME 형태(diff=color·comm=coordinate·
        # g0cells·g1color, +px)라 아래 coloring/verify 규칙을 그대로 탄다. g0idx=r*W+c=pixels_of(input)[i].
        # 같은 크기일 때만 셀 단위 재채색 가능(크기변화 → xform 없이 verify 실패 = 정직).
        H0, W0, H1, W1 = len(sim0), len(sim0[0]), len(g1grid), len(g1grid[0])
        W = W0; order = 0
        for r in range(H0 if (H0, W0) == (H1, W1) else 0):
            for c in range(W):
                if sim0[r][c] != g1grid[r][c]:                  # 잔여 변화 셀 = color DIFF ∧ coord COMM
                    xid = f"{sid}.xform.{order}"
                    ag.wm.add(sid, "xform", xid); ag.wm.add(xid, "px", "yes")
                    ag.wm.add(xid, "order", str(order))
                    ag.wm.add(xid, "diff", "color"); ag.wm.add(xid, "comm", "coordinate")
                    ag.wm.add(xid, "g0cells", _tup([[r, c]]))    # 단일 셀 (pixel)
                    ag.wm.add(xid, "g1color", str(g1grid[r][c]))  # 그 셀의 출력 색
                    ag.wm.add(xid, "g0idx", str(r * W + c))       # pixels_of(input)[i]
                    order += 1
    else:
        ag.wm.add(sid, "sim", _tup(g0grid))                     # OBJECT: 시뮬 grid = G0
        # OBJECT 가설: object mapping 대응 → xform (objects_of[i] 참조). in_idx/out_idx 는 program 참조용.
        in_idx = {frozenset(c): k for k, (c, col) in enumerate(objects_of(g0grid))}   # program 의 in_objs[i]
        order = 0
        for a, b, cat in _fg_correspondence(ag, gid0, gid1, g0grid, g1grid):   # 대응쌍 → 변환 후보 노출
            xid = f"{sid}.xform.{order}"
            ag.wm.add(sid, "xform", xid); ag.wm.add(xid, "order", str(order))
            for prop, v in cat.items():                            # 속성별 COMM/DIFF (규칙이 매칭)
                t = v.get("type") if isinstance(v, dict) else v
                if t in ("COMM", "DIFF"):
                    ag.wm.add(xid, t.lower(), prop)                # (xid ^diff color)(xid ^comm coordinate)…
            (g0cells, _), (_, g1color) = _obj_cc(idx["nodes"][a]), _obj_cc(idx["nodes"][b])
            ag.wm.add(xid, "g0cells", _tup([list(c) for c in g0cells]))   # 입력 객체 좌표(색칠 대상)
            ag.wm.add(xid, "g1color", str(g1color))                       # 출력 객체 색(칠할 색)
            ag.wm.add(xid, "g0idx", str(in_idx.get(frozenset(g0cells), 0)))    # objects_of(input)[i] 참조
            order += 1
    if _recolor_pending(ag, sid):              # 재채색(color DIFF ∧ coord COMM) 후보 있으면
        ag.wm.add(sid, "has-recolor", "yes")   # coloring 규칙 한 번만 발화(TIE 방지) — body 가 하나씩
    else:
        ag.wm.add(sid, "colored-all", "yes")   # 없으면 곧장 verify (시뮬=G0, 대개 실패 → PIXEL)


def _recolor_pending(ag, sid):
    """미적용 recolor xform(color DIFF ∧ coordinate COMM)이 남아 있나 — coloring 규칙의 조건."""
    return [x for (i, a, x) in ag.wm if i == sid and a == "xform"
            and ag.wm.contains(x, "diff", "color") and ag.wm.contains(x, "comm", "coordinate")
            and not ag.wm.contains(x, "applied", "yes")]


def _op_coloring(ag):
    """**coloring DSL operator (apply body = 원자연산만)** — 첫 미적용 recolor xform 의 g0cells 를
    g1color 로 시뮬 grid 에 칠한다(procedural_memory.coloring, frozen). '무엇을/언제'는 **규칙**
    (propose*coloring: color DIFF ∧ coord COMM 인 xform 이 있을 때)이 정한다. 하나 칠하고 applied
    표시 → 남은 게 없으면 colored-all(→ verify)."""
    import sys
    _arc = os.path.expanduser("~/Desktop/ARC-solver")
    if _arc not in sys.path:
        sys.path.insert(0, _arc)
    from procedural_memory.DSL.transformation import coloring
    sid = ag.stack[-1].id
    pend = _recolor_pending(ag, sid)
    if not pend:
        ag.wm.add(sid, "colored-all", "yes"); return
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in sim]

    def _wx(xid, attr):
        return next((v for (i, a, v) in ag.wm if i == xid and a == attr), None)
    # level-1 형식: 선택은 **objects_of(input)[i].coord**(OBJECT) / **pixels_of(input)[i].coord**(PIXEL) —
    # 실제 ARCKG 성분/픽셀 참조(provenance), 색은 target literal. PIXEL 이면 셀 단위(pixels_of[i]=r*W+c 번째 셀).
    order = sorted(pend, key=lambda x: int(_wx(x, "order") or "0"))
    px = bool(order) and ag.wm.contains(order[0], "px", "yes")
    base = next((v for (i, a, v) in ag.wm if i == sid and a == "base-program"), None) if px else None
    src, ref, var = (("in_px = pixels_of(input_grid)", "in_px", "P") if px
                     else ("in_objs = objects_of(input_grid)", "in_objs", "O"))
    if base:
        # PIXEL 잔여를 **object 가설(base)에 덧붙인다**: base 의 output_grid 라인만 떼고 tfg 번호를 이어감.
        # in_px·P{k} defs 를 base 뒤에 두고(사용 전 정의됨) 잔여 tfg step 을 tfgK 부터 계속.
        blines = [ln for ln in base.split("\n") if not ln.strip().startswith("output_grid")]
        base_n = int(base.rsplit("output_grid = tfg", 1)[-1].strip()) if "output_grid = tfg" in base else 0
        defs, steps = blines + [src], []
    else:
        defs, steps, base_n = [src], ["tfg0 = input_grid"], 0
    for k, xid in enumerate(order):
        g0c = [tuple(c) for c in (_wx(xid, "g0cells") or ())]; g1col = int(_wx(xid, "g1color") or 0)
        g0i = int(_wx(xid, "g0idx") or 0)
        for (r, c) in g0c:                                     # frozen coloring atom 으로 입력셀 → target색
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                grid = coloring(grid, (r, c), g1col)
        ag.wm.add(xid, "applied", "yes")
        defs.append(f"{var}{k} = {ref}[{g0i}]")               # 입력 성분/픽셀 참조 ([i])
        steps.append(f"tfg{base_n+k+1} = apply_DSL(tfg{base_n+k}, coloring, {var}{k}.coord, {g1col})")  # .coord → 색
    steps.append(f"output_grid = tfg{base_n + len(order)}")
    ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
    ag.wm.add(sid, "program-code", "\n".join(defs + [""] + steps))
    ag.wm.add(sid, "colored-all", "yes")                       # recolor 다 적용 → verify


def _op_verify(ag):
    """**verify operator (apply body)** — 시뮬 grid 를 train output 과 대조(원자). 같으면
    (sid ^hypothesized yes) + PAIR.program 채움, 아니면 (sid ^hypothesized failed → main 이 PIXEL 하강)."""
    sid = ag.stack[-1].id
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in (sim or [])]
    out = ag.task["train"][0]["output"]
    pid = next((v for (i, a, v) in ag.wm if i == sid and a == "sim-pair"), None)
    if grid == [list(r) for r in out]:
        ag.wm.add(sid, "hypothesized", "yes")
        code = next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), "output_grid = input_grid")
        if pid:
            ppid = f"{pid}.property"
            if ag.wm.contains(ppid, "program", "{}"):
                ag.wm.remove(ppid, "program", "{}")
            ag.wm.add(ppid, "program", code)               # 실행가능 flat Python (level-1 형식)
    else:
        ag.wm.add(sid, "hypothesized", "failed")


# ── grid.size / grid.color 를 채우는 두 DSL operator (coloring 과 대등한 기본 DSL 3종의 나머지 둘,
#    사용자 결정 2026-07-12). coloring 이 contents 슬롯을 칠하듯, 이 둘은 **program 의 grid_size /
#    grid_color 슬롯**을 채운다. hypothesize 가 노출한 가설(^size-hyp / ^color-hyp = *표현식*, 리터럴
#    아님 → TASK.solution 일반화 가능)을 읽어 슬롯으로 물질화. 가설이 없거나 'unknown' 이면 슬롯을
#    unknown 으로 남긴다(= 이 level 정보로 못 정함 → 하강 신호, '오류' 아님).
#
#    배선 계약(hypothesize 재작성 때 이걸 세우면 두 operator 가 발화):
#      (sid ^set-size yes)   + (sid ^size-hyp  <expr|unknown>)   → set_grid_size → (sid ^slot-grid_size <expr>)
#      (sid ^set-color yes)  + (sid ^color-hyp <expr|unknown>)   → set_grid_color→ (sid ^slot-grid_color <expr>)
#    지금은 어떤 규칙도 set-size/set-color 를 세우지 않으므로 **휴면**(회귀 0). hypothesize 손볼 때 활성화.
def _op_set_grid_size(ag):
    """grid.size 슬롯 설정 DSL (apply body). ^size-hyp(표현식)을 읽어 grid_size 슬롯으로 물질화."""
    sid = ag.stack[-1].id
    expr = next((v for (i, a, v) in ag.wm if i == sid and a == "size-hyp"), "unknown")
    ag.wm.add(sid, "slot-grid_size", expr)          # program 의 grid_size 슬롯(표현식 or 'unknown')
    ag.wm.add(sid, "size-set", "yes")               # 결과 플래그(재발화 방지 + 슬롯 완료 표시)


def _op_set_grid_color(ag):
    """grid.color 슬롯 설정 DSL (apply body). ^color-hyp(표현식)을 읽어 grid_color 슬롯으로 물질화."""
    sid = ag.stack[-1].id
    expr = next((v for (i, a, v) in ag.wm if i == sid and a == "color-hyp"), "unknown")
    ag.wm.add(sid, "slot-grid_color", expr)
    ag.wm.add(sid, "color-set", "yes")


# operator body(RHS 함수) = production 으로 못 하는 원자연산만:
#   observe = to_json 로드 · compare = kg_compare · select = 다음 대상 고르기(§1-3 탐색의 자리).
#   hypothesize = 슬롯(size·color·contents) 예측 open. 기본 DSL 3종 = set_grid_size·set_grid_color·coloring.
# 제어(무엇을 언제)는 전부 propose/apply 규칙 + WM 플래그로. solve 는 미구현(ONC=하강),
# submit 은 apply-only(답은 output-link 에).
OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare, "select": _op_select,
                   "hypothesize": _op_hypothesize, "coloring": _op_coloring, "verify": _op_verify,
                   "set_grid_size": _op_set_grid_size, "set_grid_color": _op_set_grid_color}


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
    # 하나의 **일반 select** operator — observe·compare 를 이름으로 구분하지 않는다. arg-선택 substate 면
    #   (^select-for <아무값>) 발화하고, **무엇을 고를지는 body 가 WM(미관측 focus 유무·observed·cmp 상태)에서
    #   추론**한다 (사용자 요청 2026-07-10: specific 이름 대신 WM 을 읽어 대상 결정).
    _propose_nonode("propose*select", "select",
                    [Cond("<s>", "select-for", "<sf>"), Cond("<s>", "selected", "<x>", negated=True)]),

    # ── hypothesize: OBJECT 레벨 object mapping 이 끝나면(compared) 발화 — object mapping 을
    #    program(가설)으로 합성·검증(body=시뮬레이션 조립·train 대조). arg-선택 substate 불필요
    #    (대상 object 는 mapping 에 있음). 통과=hypothesized yes(+PAIR.program), 실패=failed.
    # hypothesize = 시뮬레이션 open — body: 시뮬 grid=G0 + 대응→xform 후보(속성별 COMM/DIFF) 노출. 1회.
    _propose_named("propose*hypothesize", "hypothesize",
                   [Cond("<s>", "to-hypothesize", "yes"), Cond("<s>", "compared", "yes"),
                    Cond("<s>", "hyp-open", "<o>", negated=True),
                    Cond("<s>", "answer-ready", "<ar>", negated=True)]),  # 이미 답 남(예:상수출력)→hypothesize 생략
    Production("apply*hypothesize",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "hypothesize")],
               [Action("<s>", "hyp-open", "yes")]),
    # coloring DSL = **규칙기반**: color DIFF ∧ coordinate COMM 인 xform 이 있으면 propose →
    #   apply(body=frozen coloring)가 그 object.coordinate 를 g1color 로 시뮬 grid 에 칠함. 하나씩(multi-cycle).
    _propose_named("propose*coloring", "coloring",     # 단일 marker → 한 번만 propose(TIE 방지)
                   [Cond("<s>", "has-recolor", "yes"), Cond("<s>", "colored-all", "<ca>", negated=True)]),
    Production("apply*coloring",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "coloring")],
               [Action("<s>", "color-step", "yes")]),      # body 가 시뮬 recolor + applied 표시
    # set_grid_size / set_grid_color = 기본 DSL 3종의 나머지 둘(coloring 과 대등). hypothesize 가
    #   ^set-size / ^set-color 를 세우면 발화해 body 가 ^size-hyp / ^color-hyp(표현식)을 grid_size /
    #   grid_color 슬롯으로 물질화. 지금은 그 플래그를 아무도 안 세우므로 **휴면**(회귀 0) — hypothesize 재작성 때 활성화.
    _propose_named("propose*set_grid_size", "set_grid_size",
                   [Cond("<s>", "set-size", "yes"), Cond("<s>", "size-set", "<x>", negated=True)]),
    Production("apply*set_grid_size",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "set_grid_size")],
               [Action("<s>", "size-step", "yes")]),        # body 가 grid_size 슬롯 물질화 + ^size-set
    _propose_named("propose*set_grid_color", "set_grid_color",
                   [Cond("<s>", "set-color", "yes"), Cond("<s>", "color-set", "<x>", negated=True)]),
    Production("apply*set_grid_color",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "set_grid_color")],
               [Action("<s>", "grid-color-step", "yes")]),  # body 가 grid_color 슬롯 물질화 + ^color-set
    # verify = 시뮬 grid 를 train output 과 대조(원자) → hypothesized yes/failed.
    _propose_named("propose*verify", "verify",
                   [Cond("<s>", "colored-all", "yes"), Cond("<s>", "hypothesized", "<h>", negated=True)]),
    Production("apply*verify",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "verify")],
               [Action("<s>", "verify-step", "yes")]),          # body 가 ^hypothesized yes/failed 세움

    # submit: predict 가 답을 output-link 에 얹고 ^answer-ready → 제출·채점.
    _propose("submit", [Cond("<s>", "answer-ready", "yes"), Cond("<s>", "done", "<x>", negated=True)]),

    # solve = 미구현(apply·body 없음) → ONC impasse → 한 ARCKG 계층 하강(fine_trace._do_descend).
    _propose_named("propose*solve*bootstrap", "solve",
                   [Cond("<s>", "goal", "solve"), Cond("<s>", "observed", "yes")]),
    _propose_named("propose*solve*fallback", "solve",
                   [Cond("<s>", "goal", "<g>"), Cond("<g>", "produce", "<p>"),
                    Cond("<s>", "compared", "yes"), Cond("<s>", "answer-ready", "<a>", negated=True)]),
    # OBJECT hypothesize 실패 → solve(미구현) → ONC → _do_descend 가 GRID.pixels 로 하강(PIXEL).
    _propose_named("propose*solve*pixel", "solve",
                   [Cond("<s>", "hypothesized", "failed"), Cond("<s>", "pixel-open", "<p>", negated=True)]),

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
    "coloring": "기본 DSL(contents 슬롯). color DIFF ∧ coord COMM xform 을 frozen coloring 으로 시뮬 grid 에 하나씩 칠함(object·pixel level). program 의 grid_contents 를 채운다",
    "set_grid_size": "기본 DSL(grid_size 슬롯). hypothesize 의 ^size-hyp(표현식) 을 grid_size 슬롯으로 물질화. 가설 없으면 unknown(=현재 정보로 못 정함 → 하강). ^set-size 로 발화",
    "set_grid_color": "기본 DSL(grid_color 슬롯). hypothesize 의 ^color-hyp(표현식) 을 grid_color 슬롯으로 물질화. 가설 없으면 unknown. ^set-color 로 발화",
}


# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------
def _cycle_tree(events):
    """git dev-tree 용 **cycle 별 요약 노드** 목록. 각 노드 = 한 decision cycle:
      depth  = substate 깊이(S1=0, 하강할수록 +1) → 그래프의 lane(가로 위치)
      branch = 이 cycle 에 substate 가 생겼나(가지 침 = impasse)
      summary= 한 줄 요약 (무엇이 선택·적용됐나 / 뭐가 안돼 substate 가 났나)
      step   = 이 cycle 의 첫 이벤트 seq (노드 클릭 시 stepper 점프 대상)."""
    import re
    from itertools import groupby
    nodes = []
    for c, grp in groupby(events, key=lambda e: e["cycle"]):
        ec = list(grp)
        stk = ec[-1].get("goal_stack") or ["S1"]              # cycle 끝 시점의 goal 스택(=살아있는 lane 들)
        depth, gid = max(0, len(stk) - 1), stk[-1]
        op = None
        for e in ec:
            if e["kind"] == "op-select":
                m = re.search(r"name=([a-z]+)", e["label"])
                if m:
                    op = m.group(1)
        sub = [e for e in ec if e["kind"] == "substate"]
        applied = any(e["kind"] == "op-apply" and "새 substate" not in e["label"] for e in ec)
        subd = next((e for e in ec if e["kind"] == "substate" and "생성" in e["label"]), None)
        if sub:                                                   # 가지 침 (impasse → substate)
            lab = (subd or sub[-1])["label"]
            lv = re.search(r"level=([A-Z]+)", lab)
            if "하강" in lab:
                summ = f"‹{op or 'solve'}› 미구현 → 하강" + (f" · {lv.group(1)} 관측 시작" if lv else "")
            elif "arg" in lab:
                summ = f"‹{op or 'observe/compare'}› 대상 미정 → 대상 선택 substate"
            elif "자식 없음" in lab:
                summ = "더 하강할 계층 없음 → 종료"
            else:
                summ = lab[:70]
            knd = "branch"
        elif applied:
            summ, knd = f"‹{op}› 선택 → 적용", "apply"
        elif op:
            summ, knd = f"‹{op}› 제안·선택", "select"
        elif any(e["kind"] == "output" and "answer" in e["label"].lower() for e in ec):
            summ, knd = "답 제출(output)", "output"
        else:
            summ, knd = (ec[-1]["label"] or "")[:70], "phase"
        nodes.append({"cycle": c, "depth": depth, "goal": gid, "op": op or "", "kind": knd,
                      "branch": bool(sub), "summary": summ, "step": ec[0]["seq"], "stack": stk})
    return nodes


def _dash_data(task, tid="0a", max_cycles=1000):   # observe+compare+aggregate+find+solve+…×levels
    from arc.fine_trace import _Tracer
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    events = tr.run(max_cycles=max_cycles)
    wm_states = tr._wm_states           # emit 이 연속중복 병합해 이미 축소·인덱싱(events 는 wm_state 보유)
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
        "cycle_tree": _cycle_tree(events),                  # git dev-tree(좌측 패널) — cycle 노드 + substate 가지
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
SURVEY_AGI = ["08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab", "845d6e51", "868de0fa"]

if __name__ == "__main__":
    # made000a/b 가 없으면 먼저 생성
    from arc.make_made_tasks import write_all
    write_all()
    tasks = _load_survey(agi_ids=SURVEY_AGI)
    print(f"survey: easy 9 + made 2 + ARC-AGI {len(SURVEY_AGI)} — 총 {len(tasks)} 태스크 (max_cycles=1000)")
    out = make_dashboard(tasks, dataset="survey (easy·made·ARC-AGI 15)")
    sz = os.path.getsize(out) / 1e6
    print(f"wrote {out}  ({sz:.1f} MB)\nopen it:  open {out}")
