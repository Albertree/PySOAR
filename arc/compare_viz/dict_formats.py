# -*- coding: utf-8 -*-
"""
dict_formats — 0차·1차·2차 × GRID·OBJECT·PIXEL = 9칸의 dict **template** 을 실제 08ed 로 보여준다.
기존 comparison.py 의 nested dict 구조·id·score 를 **유지**하되, 2차만 개선한 drop-in template.

  0차 = node.to_json()                                     (property dict)
  1차 = compare(노드,노드)  = {id, result:{type, score, category:{ …nested… }}}   ← 현행 유지(값 포함)
  2차 = compare(1차,1차)    = {id, result:{type, score, category:{ …같은 property tree… }}}
        · leaf 는 **type 만**(두 1차 verdict 일치? — 둘 다 DIFF=COMM) · comp1/comp2 **없음**
        · category 마다 **score** (일치 자식 수 / 전체) · id 는 nested 로 유지

    python3 -m arc.compare_viz.dict_formats     # -> arc/dict_formats.html
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dict_formats.html")
LEVELS = ["GRID", "OBJECT", "PIXEL"]


def _agree(a, b):
    """2차 개선 규칙: 두 1차 결과 노드를 property tree 로 정렬해 재귀 비교.
    - 내부노드(category 보유): 자식별 _agree → category, **score = 일치자식/전체**, type = 전부일치면 COMM.
    - 잎(값 노드): 두 1차 verdict 가 같으면 COMM (**둘 다 DIFF 도 COMM = agreement**). comp1/comp2 안 넣음."""
    ca, cb = a.get("category"), b.get("category")
    if isinstance(ca, dict) and isinstance(cb, dict):
        keys = sorted(set(ca) | set(cb), key=str)
        cat = {}
        for k in keys:
            cat[k] = _agree(ca[k], cb[k]) if (k in ca and k in cb) else {"type": "DIFF"}
        comm = sum(1 for v in cat.values() if v["type"] == "COMM")
        tot = len(cat) or 1
        return {"type": "COMM" if comm == tot else "DIFF", "score": f"{comm}/{tot}", "category": cat}
    return {"type": "COMM" if a.get("type") == b.get("type") else "DIFF"}


def _second(r0, r1):
    """2차 결과 dict (id nested 유지 + agreement result)."""
    return {"id": {"id1": r0.get("id"), "id2": r1.get("id")}, "result": _agree(r0["result"], r1["result"])}


def _abbrev(o):
    """표시용: 긴 배열(contents·coordinate)만 …+N 으로 축약. 구조는 보존."""
    if isinstance(o, list):
        return [_abbrev(x) for x in o[:3]] + [f"…+{len(o) - 3}"] if len(o) > 6 else [_abbrev(x) for x in o]
    if isinstance(o, dict):
        return {k: _abbrev(v) for k, v in o.items()}
    return o


def _pick(idx, grid_node, color, rank):
    from arc.focus_solver import _obj_cc
    objs = [(len(_obj_cc(idx["nodes"][o])[0]), o) for o in idx["children"].get(grid_node.node_id, [])
            if _obj_cc(idx["nodes"][o])[1] == color]
    objs.sort(key=lambda t: -t[0])
    return idx["nodes"][objs[rank][1]]


def _pix(idx, grid_node, r, c):
    for pid in idx.get("pixels", {}).get(grid_node.node_id, []):
        j = idx["nodes"][pid].to_json()["coordinate"]
        if j["row_index"] == r and j["col_index"] == c:
            return idx["nodes"][pid]
    return None


def _pre(obj):
    return f"<pre>{html.escape(json.dumps(_abbrev(obj), ensure_ascii=False, indent=1))}</pre>"


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arc.focus_solver import build_arckg, index_arckg, _load_survey, SURVEY_AGI
    from ARCKG.comparison import compare as kg
    task = dict(_load_survey(agi_ids=SURVEY_AGI))["08ed6ac7"]
    root = build_arckg("08ed6ac7", task)
    idx = index_arckg(root)
    p0, p1 = root.example_pairs[0], root.example_pairs[1]
    nodes = {
        "GRID": (p0.input_grid, p0.output_grid, p1.input_grid, p1.output_grid),
        "OBJECT": (_pick(idx, p0.input_grid, 5, 0), _pick(idx, p0.output_grid, 1, 0),
                   _pick(idx, p1.input_grid, 5, 0), _pick(idx, p1.output_grid, 1, 0)),
        "PIXEL": (_pix(idx, p0.input_grid, 0, 5), _pix(idx, p0.output_grid, 0, 5),
                  _pix(idx, p1.input_grid, 1, 7), _pix(idx, p1.output_grid, 1, 7)),
    }
    src = {"GRID": "P0G0 grid", "OBJECT": "P0G0 회색가장긴 object", "PIXEL": "P0G0 pixel(0,5)"}
    cells = {}
    for lv in LEVELS:
        a, b, c, d = nodes[lv]
        r0, r1 = kg(a, b), kg(c, d)
        cells[("0차", lv)] = f"<div class=meta>{src[lv]} · node.to_json()</div>{_pre(a.to_json())}"
        cells[("1차", lv)] = f"<div class=meta>compare(G0, G1) · id·type·score·category (값 포함)</div>{_pre(r0)}"
        cells[("2차", lv)] = f"<div class=meta>compare(1차_P0, 1차_P1) · id·type·score·category (verdict만·둘다DIFF=COMM)</div>{_pre(_second(r0, r1))}"
    ROWDESC = {
        "0차": "노드 <b>property dict</b> (to_json).",
        "1차": "compare(노드,노드) = <b>{id, result:{type, score, category:{…nested…}}}</b>. 잎에 comp1/comp2 값. <i>현행 유지.</i>",
        "2차": "compare(1차,1차) = 같은 nested 구조·id·score 유지. <b>잎은 type 만</b>(둘 다 DIFF=COMM), <b>값 없음</b>, category마다 score.",
    }
    thead = "<tr><th></th>" + "".join(f"<th>{lv}</th>" for lv in LEVELS) + "</tr>"
    body = ""
    for order in ("0차", "1차", "2차"):
        body += (f"<tr><td class=rh><b>{order}</b><div class=rd>{ROWDESC[order]}</div></td>"
                 + "".join(f"<td class=cell>{cells[(order, lv)]}</td>" for lv in LEVELS) + "</tr>")
    tmpl = html.escape(
        '0차: <node>.to_json()\n'
        '1차: { "id": {"id1": ID, "id2": ID},\n'
        '       "result": { "type": COMM|DIFF, "score": "n/total",\n'
        '                   "category": { <prop>: {"type","score","category":{…}}   // 내부노드\n'
        '                                        | {"type","comp1","comp2"} } } }    // 잎(값)\n'
        '2차: { "id": {"id1": <1차 id>, "id2": <1차 id>},\n'
        '       "result": { "type": COMM|DIFF, "score": "n/total",\n'
        '                   "category": { <prop>: {"type","score","category":{…}}   // 내부노드(재귀)\n'
        '                                        | {"type"} } } }                    // 잎 = verdict 일치?만')
    doc = f"""<!doctype html><meta charset='utf-8'><title>dict template 0·1·2차 × GRID·OBJECT·PIXEL</title>
<style>{CSS}</style>
<h1>compare dict <b>template</b> — 0·1·2차 × GRID·OBJECT·PIXEL (기존 대체용, 08ed 실제 데이터)</h1>
<p class=lead>nested dict 구조·<code>id</code>·<code>score</code> 를 <b>유지</b>. 바뀌는 건 <b>2차</b>뿐 —
잎에서 두 1차 verdict 의 <b>일치(둘 다 DIFF=COMM)</b>만 두고 comp1/comp2 값은 빼며, 각 category 에 그 일치들의
<b>score(n/total)</b> 를 매긴다. 나머지(0·1차)는 현행 그대로.</p>
<div class=tmpl><div class=tl>공통 template</div><pre>{tmpl}</pre></div>
<table class=m>{thead}{body}</table>
"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:16px;margin:0 0 4px} .lead{color:#8b949e;margin:0 0 12px;max-width:980px} code{color:#79c0ff}
.tmpl{border:1px solid #30363d;border-radius:8px;background:#12161c;padding:8px 12px;margin:0 0 14px}
.tl{color:#d2a8ff;font-size:12px;margin-bottom:4px}
.tmpl pre{background:transparent;border:0;color:#adbac7;margin:0;font-size:12px;white-space:pre;overflow:auto}
table.m{border-collapse:collapse;width:100%;table-layout:fixed}
table.m th,table.m td{border:1px solid #30363d;vertical-align:top;padding:8px 10px}
table.m th{background:#1c2128;color:#e6edf3;font-size:13px}
.rh{width:160px;background:#161b22;color:#e6edf3} .rd{color:#8b949e;font-size:11px;font-weight:normal;margin-top:4px}
.cell{background:#0d1117} .meta{color:#d2a8ff;font-size:11px;margin-bottom:5px}
pre{background:#010409;border:1px solid #30363d;border-radius:6px;padding:7px 9px;margin:0;
 overflow:auto;max-height:360px;font-size:11px;color:#c9d1d9;white-space:pre}
"""


if __name__ == "__main__":
    print("wrote", build())
