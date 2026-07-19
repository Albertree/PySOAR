# -*- coding: utf-8 -*-
"""
object_comparison — 08ed6ac7 의 **object 노드**를 직접 골라 0·1·2차 비교를 HTML 로 보여준다.
(comparison_orders 와 같은 방식이되 대상이 OBJECT.)

시나리오 1 (올바른 대응 — 길이 1위 → 파랑):
  P0G0 회색 가장 긴 · P0G1 파랑 · P1G0 회색 가장 긴 · P1G1 파랑
시나리오 2 (어긋난 대응 — 2위→빨강 vs 1위→파랑):
  P0G0 회색 2번째 긴 · P0G1 빨강 · P1G0 회색 가장 긴 · P1G1 파랑

각 시나리오: 0차 = object 4개 property dict / 1차 = compare(G0obj,G1obj) 2개 /
2차 = compare(1차,1차) 1개 (제안: verdict끼리 같음/다름만, 하위값 없음).

    python3 -m legacy.compare_viz.object_comparison     # -> arc/object_comparison.html
"""
from __future__ import annotations

import html
import json
import os

from debugger.reports.comparison_orders import _flat, _sv     # 재사용: flat leaf 맵 / 값 축약

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "object_comparison.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
# object property 그룹 순서 (길이·크기 먼저)
_OPRI = {"area": 0, "size": 1, "shape": 2, "color": 3, "coordinate": 4,
         "position": 5, "method": 6, "symmetry": 7, "contents": 8}


def _ogrouped(paths):
    from itertools import groupby

    def key(p):
        top = p.split(".")[0]
        sub = tuple(int(s) if s.isdigit() else s for s in p.split(".")[1:])
        return (_OPRI.get(top, 9), top, sub)
    for top, grp in groupby(sorted(paths, key=key), key=lambda p: p.split(".")[0]):
        yield top, list(grp)


def _obj_color(node):
    j = node.to_json()
    return next((int(k) for k, v in j["color"].items() if v), 0)


def _obj_grid_html(node, H, W):
    """object 를 전체 격자 위에 위치시켜 렌더 (색+위치+모양 한눈에)."""
    j = node.to_json()
    col = _obj_color(node)
    cells = {(r, c) for r, c in j["coordinate"]}
    rows = ""
    for r in range(H):
        tds = "".join(f"<td style='background:{PALETTE[col] if (r, c) in cells else '#0d1117'}'></td>"
                      for c in range(W))
        rows += f"<tr>{tds}</tr>"
    return f"<table class=g>{rows}</table>"


def _first_table(flat):
    rows = []
    for top, paths in _ogrouped(flat):
        rows.append(f"<tr class=grp><td colspan=4>{top}</td></tr>")
        for p in paths:
            t, a, b = flat[p]
            sub = p[len(top) + 1:] or "(전체)"
            cls = "comm" if t == "COMM" else "diff"
            rows.append(f"<tr class={cls}><td class=sub>{html.escape(sub)}</td><td class=v>{t}</td>"
                        f"<td>{_sv(a)}</td><td>{_sv(b)}</td></tr>")
    return ("<table class=t><tr><th>property</th><th>verdict</th><th>값1</th><th>값2</th></tr>"
            + "".join(rows) + "</table>")


def _second_table(f0, f1):
    rows, same = [], True
    for top, paths in _ogrouped(set(f0) | set(f1)):
        rows.append(f"<tr class=grp><td colspan=4>{top}</td></tr>")
        for p in paths:
            v0 = f0.get(p, ("∅",))[0]
            v1 = f1.get(p, ("∅",))[0]
            agree = (v0 == v1)
            same = same and agree
            sub = p[len(top) + 1:] or "(전체)"
            cls = "comm" if agree else "diff"
            rows.append(f"<tr class={cls}><td class=sub>{html.escape(sub)}</td><td>{v0}</td><td>{v1}</td>"
                        f"<td class=v>{'COMM' if agree else 'DIFF'}</td></tr>")
    verdict = ("두 pair 의 object 변환이 <b>구조적으로 동일</b>" if same
               else "두 pair 의 object 변환이 <b>일부 property 에서 다름</b>")
    return ("<table class=t><tr><th>property</th><th>1차_P0</th><th>1차_P1</th><th>관계 같음?</th></tr>"
            + "".join(rows) + "</table>" + f"<div class=note>⇒ {verdict}</div>")


def _pick(idx, grid_node, color, rank):
    """grid 의 object 중 지정 color, 셀 수 내림차순 rank 번째 노드."""
    from arbor.solver import _obj_cc
    objs = []
    for oid in idx["children"].get(grid_node.node_id, []):
        cells, col = _obj_cc(idx["nodes"][oid])
        if col == color:
            objs.append((len(cells), oid))
    objs.sort(key=lambda t: -t[0])
    return idx["nodes"][objs[rank][1]]


def _obj_card(name, node, H, W):
    return (f"<div class=card><div class=lbl>{name}</div>{_obj_grid_html(node, H, W)}"
            f"<pre>{html.escape(json.dumps(node.to_json(), ensure_ascii=False, indent=1))}</pre></div>")


def _scenario(idx, pairs, picks, title, desc, H, W):
    from ARCKG.comparison import compare as kg
    (p0, p1) = pairs
    a = _pick(idx, p0.input_grid, picks[0][0], picks[0][1])
    b = _pick(idx, p0.output_grid, picks[1][0], picks[1][1])
    c = _pick(idx, p1.input_grid, picks[2][0], picks[2][1])
    d = _pick(idx, p1.output_grid, picks[3][0], picks[3][1])
    labels = ["P0G0 " + picks[0][2], "P0G1 " + picks[1][2], "P1G0 " + picks[2][2], "P1G1 " + picks[3][2]]
    cards0 = "".join(_obj_card(lab, n, H, W) for lab, n in zip(labels, (a, b, c, d)))
    r0 = kg(a, b)
    r1 = kg(c, d)
    f0, f1 = _flat(r0["result"]), _flat(r1["result"])
    cards1 = (f"<div class=card><div class=lbl>compare({labels[0]}, {labels[1]})</div>{_first_table(f0)}</div>"
              f"<div class=card><div class=lbl>compare({labels[2]}, {labels[3]})</div>{_first_table(f1)}</div>")
    card2 = (f"<div class=card wide><div class=lbl>compare(1차_P0, 1차_P1) "
             f"<span class=dim>— 제안: verdict끼리 같음/다름만</span></div>{_second_table(f0, f1)}</div>")
    return (f"<section><h2>{title}</h2><p class=sd>{desc}</p>"
            f"<h3>0차 — object property dict 4개</h3><div class=row>{cards0}</div>"
            f"<h3>1차 — compare(G0obj, G1obj) 2개</h3><div class=row>{cards1}</div>"
            f"<h3>2차 — compare(1차,1차) 1개 <span class=dim>[제안]</span></h3><div class=row>{card2}</div></section>")


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arbor.solver import build_arckg, index_arckg, _load_survey, SURVEY_AGI
    task = dict(_load_survey(agi_ids=SURVEY_AGI))["08ed6ac7"]
    root = build_arckg("08ed6ac7", task)
    idx = index_arckg(root)
    pairs = (root.example_pairs[0], root.example_pairs[1])
    H, W = len(task["train"][0]["input"]), len(task["train"][0]["input"][0])
    # (color, rank, label) — 회색=5, 파랑=1, 빨강=2
    s1 = _scenario(idx, pairs,
                   [(5, 0, "회색 가장 긴"), (1, 0, "파랑"), (5, 0, "회색 가장 긴"), (1, 0, "파랑")],
                   "시나리오 1 — 회색 1위 → 파랑 (올바른 대응)",
                   "P0·P1 모두 '가장 긴 회색 → 파랑'. 같은 역할끼리 이은 대응.", H, W)
    s2 = _scenario(idx, pairs,
                   [(5, 1, "회색 2번째 긴"), (2, 0, "빨강"), (5, 0, "회색 가장 긴"), (1, 0, "파랑")],
                   "시나리오 2 — P0(2위→빨강) vs P1(1위→파랑) (어긋난 대응)",
                   "P0 는 '2번째 긴 회색 → 빨강', P1 은 '가장 긴 회색 → 파랑'. 역할이 어긋난 대응.", H, W)
    s3 = _scenario(idx, pairs,
                   [(5, 1, "회색 2번째 긴"), (1, 0, "파랑"), (5, 0, "회색 가장 긴"), (1, 0, "파랑")],
                   "시나리오 3 — P0(2번째 긴 회색 ↔ 파랑) vs P1(가장 긴 회색 ↔ 파랑) (대상 자체가 어긋남)",
                   "P0 는 '2번째 긴 회색'을 파랑과 비교하지만 파랑은 사실 '가장 긴 회색'의 재채색 — 서로 다른 객체를 이음. "
                   "P1 은 올바른 대응. → 2차에 area·size·shape·position 등 DIFF 가 많이 뜬다.", H, W)
    doc = f"""<!doctype html><meta charset='utf-8'><title>object 비교 0·1·2차</title>
<style>{CSS}</style>
<h1>08ed6ac7 — object 비교 (0차 property · 1차 · 2차 제안)</h1>
<p class=lead>08ed 는 회색 세로막대를 길이순위로 재채색(1위→파랑·2위→빨강·3위→초록·4위→노랑).
세 시나리오로 object 를 골라 0·1·2차 비교. 2차는 verdict끼리 같음/다름만(하위값 없음).</p>
{s1}{s2}{s3}"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin-bottom:18px;max-width:920px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 18px;background:#161b22}
h2{font-size:16px;margin:0 0 4px;color:#e6edf3} .sd{color:#8b949e;margin:0 0 6px}
h3{font-size:13px;margin:14px 0 6px;color:#adbac7} .dim{color:#6e7681;font-weight:normal}
.row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.card{border:1px solid #30363d;border-radius:7px;padding:8px 10px;background:#0d1117;max-width:430px}
.card.wide{max-width:100%;flex:1 1 100%}
.lbl{font-size:12px;margin-bottom:6px;color:#d2a8ff}
table.g{border-collapse:collapse;margin-bottom:8px} table.g td{width:12px;height:12px;border:1px solid #1c1c1c}
table.t{border-collapse:collapse;width:100%;font-size:12px}
table.t th,table.t td{border:1px solid #30363d;padding:2px 7px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.comm td{background:#0f1f13} tr.comm .v{color:#3fb950;font-weight:bold}
tr.diff td{background:#2a1416} tr.diff .v{color:#f85149;font-weight:bold}
tr.grp td{background:#21262d;color:#f0b72f;font-weight:bold;letter-spacing:.5px}
td.sub{color:#8b949e;padding-left:16px}
.note{margin-top:6px;color:#d29922}
pre{background:#010409;border:1px solid #30363d;border-radius:6px;padding:6px 8px;margin:0;
 overflow:auto;max-height:240px;font-size:11px;color:#c9d1d9;white-space:pre}
"""


if __name__ == "__main__":
    print("wrote", build())
