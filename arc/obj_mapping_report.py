# -*- coding: utf-8 -*-
"""
obj_mapping_report -- 임시 확인용 HTML. easy000a·made000b·08ed6ac7 세 문제에서
P0.G0 아래 object ↔ P0.G1 아래 object 를 9속성(ARCKG compare) 비교한 N/9 매핑을,
각 object 의 contents(색배열)·속성·소속과 함께 자세히 보고한다. 특히 9/9(안 변함) 매핑을 강조.

9속성: area·color·contents·coordinate·method·position·shape·size·symmetry.
  시각화는 **contents(색배열, 투명=빈칸)** 만 한다 (사용자 요청 2026-07-08 — shape 제거).
  비교 테이블의 각 셀에 **호버**하면 두 object 의 contents + comparison receipt dict 가 뜬다.

  run:  python3 -m arc.obj_mapping_report   →  arc/obj_mapping_report.html
"""
from __future__ import annotations

import html
import json
import os

from arc.make_made_tasks import write_all
from arc.expr_solver import build_arckg
from ARCKG.comparison import compare as kg_compare

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "obj_mapping_report.html")
PALETTE = {0: "#1b1b1b", 1: "#0074D9", 2: "#FF4136", 3: "#2ECC40", 4: "#FFDC00",
           5: "#AAAAAA", 6: "#F012BE", 7: "#FF851B", 8: "#7FDBFF", 9: "#870C25"}
PROPS = ["area", "color", "contents", "coordinate", "method",
         "position", "shape", "size", "symmetry"]
N = len(PROPS)
EMPTY = "#D6FFFF"                 # 투명(빈=13) 셀 = ARC-TBD/basics/settings.json 팔레트 색 13 [214,255,255]


def _load():
    """대시보드와 **동일한 15문제** (easy 9 + made 2 + ARC-AGI 4)를 순서대로 반환."""
    write_all()
    from arc.focus_solver import _load_survey, SURVEY_AGI
    return _load_survey(agi_ids=SURVEY_AGI)          # [(tid, task), ...]


def _colors(cd):
    return ",".join(str(k) for k, v in cd.items() if v) or "-"


def _pos(p):
    lt = p.get("left_top", {})
    return f"({lt.get('row_index')},{lt.get('col_index')})"


def _sym(s):
    return ",".join(k.replace("_symm", "") for k, v in s.items() if v) or "-"


def _content_grid(cg):
    """object contents(bbox 색배열, 투명=13) 를 미니그리드로 — **inline-grid div** 로 그려
    flex/table 레이아웃 영향 없이 셀이 항상 9×9 정사각형이 되게 한다 (팝업 찌부 방지, 사용자 요청).
    빈(투명=13) 셀 = 연한 파랑."""
    ncol = len(cg[0]) if cg and cg[0] else 1
    cells = "".join(
        f"<div style='background:{EMPTY if v == 13 else PALETTE.get(v, '#333')}'></div>"
        for row in cg for v in row)
    return f"<div class=mg style='grid-template-columns:repeat({ncol},9px)'>{cells}</div>"


def _ordinal(i):
    return f"{i + 1}번째"


def _obj_props_html(oid, j, i):
    """object 한 개의 카드: '몇 번째' 순번 + O-이름 + contents 미니그리드 + 텍스트 속성행.
    시각화는 contents 만 (shape 미니그리드 제거)."""
    short = oid.split(".")[-1]
    rows = [
        ("소속(id)", html.escape(oid)),
        ("area", j["area"]),
        ("color", _colors(j["color"])),
        ("coordinate", html.escape(str(j["coordinate"]))[:46]),
        ("method", ",".join(k for k, v in j["method"].items() if v) or "-"),
        ("position(lt)", _pos(j["position"])),
        ("size", f"{j['size']['height']}×{j['size']['width']}"),
        ("symmetry", _sym(j["symmetry"])),
    ]
    body = "".join(f"<div class=prow><span class=pk>{html.escape(k)}</span>"
                   f"<span class=pv>{v}</span></div>" for k, v in rows)
    hdr = (f"<div class=ohdr><span class=ord>{_ordinal(i)}</span>"
           f"<span class=oname>{html.escape(short)}</span></div>")
    grid = f"<div class=mini><div class=mlbl>contents</div>{_content_grid(j['contents'])}</div>"
    return (f"<div class=objcard>{hdr}"
            f"<div class=cardbody><div class=grids>{grid}</div><div>{body}</div></div></div>")


def _prune_receipt(receipt):
    """플로팅 윈도우용 comparison receipt dict — 큰 배열(contents/shape/coordinate)은
    {type} 로만(그림은 위에서 보이므로), 스칼라 속성은 comp1/comp2 까지 남긴다."""
    r = receipt["result"]
    cat = {}
    for k, v in r.get("category", {}).items():
        if not isinstance(v, dict):
            continue
        e = {"type": v.get("type")}
        if k not in ("contents", "shape", "coordinate"):
            if "comp1" in v:
                e["comp1"] = v["comp1"]
            if "comp2" in v:
                e["comp2"] = v["comp2"]
        cat[k] = e
    return {"id": receipt.get("id"), "type": r.get("type"),
            "score": r.get("score"), "category": cat}


def _pop(a_short, b_short, ja, jb, receipt):
    """셀 호버 시 뜨는 플로팅 윈도우: 두 object contents + comparison receipt dict."""
    grids = (f"<div class=popcol><div class=mlbl>{html.escape(a_short)} (G0)</div>{_content_grid(ja['contents'])}</div>"
             f"<div class=popcol><div class=mlbl>{html.escape(b_short)} (G1)</div>{_content_grid(jb['contents'])}</div>")
    dump = html.escape(json.dumps(_prune_receipt(receipt), indent=2, ensure_ascii=False))
    return (f"<div class=pop><div class=popgrids>{grids}</div>"
            f"<pre class=receipt>{dump}</pre></div>")


def _task_section(tid, task):
    root = build_arckg(tid, task)
    p0 = root.example_pairs[0]
    o0, o1 = p0.input_grid.objects, p0.output_grid.objects
    j0 = {o.node_id: o.to_json() for o in o0}
    j1 = {o.node_id: o.to_json() for o in o1}
    short = lambda oid: oid.split(".")[-1]

    # full receipt per (a,b) — 셀 숫자와 호버 팝업 둘 다에 사용
    rcpt = {(a.node_id, b.node_id): kg_compare(a, b) for a in o0 for b in o1}

    def commlist(a, b):
        cat = rcpt[(a.node_id, b.node_id)]["result"]["category"]
        return [k for k in PROPS if cat.get(k, {}).get("type") == "COMM"]

    head = "<tr><th>G0＼G1</th>" + "".join(
        f"<th>{html.escape(short(b.node_id))}</th>" for b in o1) + "</tr>"
    body, tops = "", []
    for ai, a in enumerate(o0):
        cells = ""
        for bi, b in enumerate(o1):
            comm = commlist(a, b)
            n = len(comm)
            cls = "top" if n == N else ("hi" if n >= 5 else "lo")
            pop = _pop(short(a.node_id), short(b.node_id),
                       j0[a.node_id], j1[b.node_id], rcpt[(a.node_id, b.node_id)])
            cells += f"<td class='{cls}'>{n}/{N}{pop}</td>"
            if n == N:
                tops.append((a.node_id, ai, b.node_id, bi, comm))
        body += f"<tr><th>{html.escape(short(a.node_id))}</th>{cells}</tr>"
    mtx = f"<table class=mtx>{head}{body}</table>"

    top_html = ""
    if tops:
        for aid, ai, bid, bi, comm in tops:
            top_html += (f"<div class=topmap><b>{html.escape(short(aid))}</b> "
                         f"(<span class=mem>{html.escape(aid)}</span>) &nbsp;↔ {N}/{N} ↔&nbsp; "
                         f"<b>{html.escape(short(bid))}</b> "
                         f"(<span class=mem>{html.escape(bid)}</span>) "
                         f"<span class=hint>— 9속성 전부 COMM(=제자리 불변): "
                         f"{html.escape(','.join(comm))}</span>"
                         "<div class=pairwrap>"
                         + _obj_props_html(aid, j0[aid], ai) + _obj_props_html(bid, j1[bid], bi)
                         + "</div></div>")
    else:
        top_html = f"<div class=hint>{N}/{N} 매핑 없음 (모든 object 가 변함)</div>"

    g0objs = "".join(_obj_props_html(o.node_id, j0[o.node_id], i) for i, o in enumerate(o0))
    g1objs = "".join(_obj_props_html(o.node_id, j1[o.node_id], i) for i, o in enumerate(o1))
    return (f"<section><h2>{html.escape(tid)}</h2>"
            f"<div class=sub>P0.G0 objects ({len(o0)}) ↔ P0.G1 objects ({len(o1)}) — N/{N} 매트릭스 "
            f"<span class=hint>(셀에 <b>호버</b> → 두 contents + receipt dict)</span></div>{mtx}"
            f"<div class=sub>{N}/{N} 매핑 (제자리 불변 = 탐색 제약)</div>{top_html}"
            f"<div class=sub>P0.G0 (input) objects</div><div class=objrow>{g0objs}</div>"
            f"<div class=sub>P0.G1 (output) objects</div><div class=objrow>{g1objs}</div></section>")


CSS = """
body{background:#0e0e10;color:#ddd;font:13px/1.5 -apple-system,Segoe UI,sans-serif;margin:0;padding:22px}
h1{font-size:18px;margin:0 0 4px}.lead{color:#999;margin:0 0 18px}
section{background:#171719;border:1px solid #2a2a2e;border-radius:10px;padding:14px 16px;margin:0 0 16px}
h2{font-size:15px;margin:0 0 4px;color:#8ab}
.sub{color:#8ab;font-weight:600;margin:14px 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.hint{color:#888;font-weight:400;text-transform:none}
table.mtx{border-collapse:collapse;font:12px ui-monospace,Menlo,monospace;margin:4px 0}
table.mtx th{color:#888;padding:3px 9px;border:1px solid #2a2a2e}
table.mtx td{padding:3px 9px;text-align:center;border:1px solid #2a2a2e;position:relative;cursor:help}
td.top{background:#16361f;color:#7fe79a;font-weight:700}td.hi{background:#2a2410;color:#e0c96a}td.lo{color:#666}
/* 셀 호버 플로팅 윈도우 */
.pop{display:none;position:absolute;left:100%;top:0;z-index:50;margin-left:6px;
     background:#0b0b0d;border:1px solid #3a3f52;border-radius:8px;padding:9px 10px;
     box-shadow:0 8px 26px #000a;width:max-content;max-width:560px;text-align:left}
td:hover .pop{display:block}
.popgrids{display:flex;gap:12px;margin-bottom:7px;flex-wrap:wrap}
.popcol{text-align:center;flex:0 0 auto}   /* flex-shrink 0 → 셀이 찌부되지 않고 정사각형 유지 */
pre.receipt{margin:0;font:10.5px/1.4 ui-monospace,Menlo,monospace;color:#bcd;white-space:pre;
     max-height:260px;overflow:auto;background:#08080a;border:1px solid #23232a;border-radius:5px;padding:6px 8px}
.topmap{background:#12120f;border:1px solid #2e3a24;border-radius:8px;padding:8px 11px;margin:6px 0}
.mem{color:#7fb;font-family:ui-monospace,monospace;font-size:11px}
.pairwrap{display:flex;gap:14px;margin-top:8px;flex-wrap:wrap}
.objrow{display:flex;gap:10px;flex-wrap:wrap}
.objcard{background:#0c0c0e;border:1px solid #2a2a2e;border-radius:7px;padding:8px 10px;min-width:220px}
.ohdr{display:flex;align-items:baseline;gap:7px;margin-bottom:6px;border-bottom:1px solid #23232a;padding-bottom:4px}
.ord{background:#2a3550;color:#bcd;font-weight:700;font-size:11px;border-radius:4px;padding:1px 7px}
.oname{color:#7fb;font-family:ui-monospace,monospace;font-weight:700;font-size:12px}
.cardbody{display:flex;gap:9px}
.grids{display:flex;gap:7px;flex:0 0 auto}
.mini{text-align:center}.mlbl{font-size:9px;color:#88a;margin-bottom:2px}
.prow{display:flex;gap:6px;font:11px ui-monospace,Menlo,monospace}
.pk{color:#88a;flex:0 0 82px}.pv{color:#cde;word-break:break-all}
/* 격자선 = gap:1px 사이로 컨테이너 배경색이 비쳐 셀 사이 선이 된다(정사각형 유지 + 격자 복원) */
.mg{display:inline-grid;gap:1px;background:#ffffff26;border:1px solid #ffffff26;vertical-align:top;line-height:0}
.mg>div{width:9px;height:9px}
"""


def _safe_section(tid, task):
    try:
        return _task_section(tid, task)
    except Exception as e:                                       # noqa: BLE001 (낯선 구조 방어)
        return (f"<section><h2>{html.escape(tid)}</h2>"
                f"<div class=hint>렌더 실패: {html.escape(type(e).__name__)}: {html.escape(str(e)[:120])}</div></section>")


def build():
    tasks = _load()
    body = "".join(_safe_section(tid, task) for tid, task in tasks)
    doc = (f"<!doctype html><meta charset='utf-8'><title>ARBOR object mapping</title>"
           f"<style>{CSS}</style>"
           f"<h1>ARBOR — P0.G0 ↔ P0.G1 object mapping (N/{N})</h1>"
           f"<p class=lead>한 PAIR(P0) 안 입력 grid(G0)의 object 와 출력 grid(G1)의 object 를 "
           f"ARCKG compare 로 <b>9속성</b> 비교한 N/{N}. {N}/{N} = 제자리 불변. "
           f"시각화는 <b>contents(색배열)</b>만; 빈칸=투명. 매트릭스 셀에 <b>호버</b>하면 "
           f"두 object 의 contents 와 comparison receipt dict 가 뜬다.</p>{body}")
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


if __name__ == "__main__":
    print("wrote", build())
