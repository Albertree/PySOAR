# -*- coding: utf-8 -*-
"""
comparison_orders — 한 문제의 그리드 4개로 0차·1차·2차 비교를 HTML 로 보여준다.
**2차는 제안된 방식**: relation 끼리의 비교이므로 각 property 경로에서 *verdict(COMM/DIFF)가
같은지/다른지만* 표기한다. 2차 이상에서는 속성값 각각·하위 비교를 넣지 않는다(폭발 제거).

  · 0차 = 각 grid 의 property dict (to_json)                      4개
  · 1차 = compare(G0,G1) → 경로별 verdict (+ 비교값)               2개
  · 2차 = compare(1차_P0, 1차_P1) → 경로별 verdict끼리 같음/다름    1개  ← 제안(하위값 없음)

    python3 -m arc.compare_viz.comparison_orders     # -> arc/comparison_orders.html
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "comparison_orders.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
AGI20 = ["00576224", "007bbfb7", "009d5c81", "017c7c7b", "025d127b", "03560426", "0520fde7",
         "05269061", "05f2a901", "0692e18c", "09629e4f", "0962bcdd", "0bb8deee", "0becf7df",
         "0c786b71", "0c9aba6e", "0ca9ddb6", "0d3d703e", "0e671a1a", "10fcaaa3"]
# ARC-AGI **evaluation** 50문제 (격자 ≤30×30, ≥2 pair, build/compare 검증됨)
EVAL50 = ["0934a4d8", "135a2760", "136b0064", "13e47133", "142ca369", "16b78196", "16de56c4",
          "1818057f", "195c6913", "1ae2feb7", "20270e3b", "20a9e565", "21897d95", "221dfab4",
          "247ef758", "269e22fb", "271d71e2", "28a6681f", "291dc1e1", "2b83f449", "2ba387bc",
          "2c181942", "2d0172a1", "31f7f899", "332f06d7", "35ab12c3", "36a08778", "38007db0",
          "3a25b0d8", "3dc255db", "3e6067c3", "409aa875", "446ef5d2", "45a5af55", "4a21e3da",
          "4c3d4a41", "4c416de3", "4c7dc4dd", "4e34c42c", "53fb4810", "5545f144", "581f7754",
          "58490d8a", "58f5dbd5", "5961cc34", "5dbc8537", "62593bfd", "64efde09", "65b59efc",
          "67e490f4"]
TASKS = ["08ed6ac7", "8efcae92", "made000a", "easy000g", "easy000i", "easy000a"] + AGI20 + EVAL50


def _flat(result):
    """compare result → {경로: (verdict, v1, v2)} 평평한 leaf 맵 (property 축 보존)."""
    out = {}

    def walk(node, pre):
        cat = node.get("category")
        if cat:
            for k, v in cat.items():
                walk(v, pre + (str(k),))
        else:
            out[".".join(pre)] = (node.get("type"), node.get("comp1"), node.get("comp2"))
    walk(result, ())
    return out


def _grid_html(g):
    rows = "".join("<tr>" + "".join(
        f"<td style='background:{PALETTE[v] if 0 <= v < 10 else '#333'}'></td>" for v in r) + "</tr>" for r in g)
    return f"<table class=g>{rows}</table>"


def _sv(x):
    s = str(x)
    return html.escape(s if len(s) <= 16 else s[:13] + "…")


_PRI = {"size": 0, "color": 1, "contents": 2}    # 항상 size → color → contents 순, 셋 다 포함


def _grouped(paths):
    """경로들을 top property(size/color/contents)로 그룹핑, 그 순서로. 색은 숫자순."""
    from itertools import groupby

    def key(p):
        top = p.split(".")[0]
        sub = tuple(int(s) if s.isdigit() else s for s in p.split(".")[1:])
        return (_PRI.get(top, 3), top, sub)
    for top, grp in groupby(sorted(paths, key=key), key=lambda p: p.split(".")[0]):
        yield top, list(grp)


def _first_table(flat):
    """1차 = 경로별 verdict + 비교한 두 값. size/color/contents 그룹으로."""
    rows = []
    for top, paths in _grouped(flat):
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
    """2차(제안) = 경로별로 두 1차 verdict 가 같은지/다른지만. size/color/contents 그룹, 하위값 없음."""
    rows = []
    same = True
    for top, paths in _grouped(set(f0) | set(f1)):
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
    head = ("<table class=t><tr><th>property</th><th>1차_P0</th><th>1차_P1</th>"
            "<th>관계 같음?</th></tr>")
    verdict = ("두 pair 변환이 <b>구조적으로 동일</b>" if same
               else "두 pair 변환이 <b>일부 경로에서 다름</b>")
    return head + "".join(rows) + "</table>" + f"<div class=note>⇒ {verdict}</div>"


def section(tid, task):
    """한 태스크의 0·1·2차 비교 섹션 HTML (P0·P1 사용). 다른 스크립트에서도 재사용."""
    from arc.focus_solver import build_arckg
    from ARCKG.comparison import compare as kg
    root = build_arckg(tid, task)
    p0, p1 = root.example_pairs[0], root.example_pairs[1]
    grids = [("P0G0", p0.input_grid, task["train"][0]["input"]),
             ("P0G1", p0.output_grid, task["train"][0]["output"]),
             ("P1G0", p1.input_grid, task["train"][1]["input"]),
             ("P1G1", p1.output_grid, task["train"][1]["output"])]
    cards0 = "".join(
        f"<div class=card><div class=lbl>{name}</div>{_grid_html(raw)}"
        f"<pre>{html.escape(json.dumps(node.to_json(), ensure_ascii=False, indent=1))}</pre></div>"
        for name, node, raw in grids)
    r0, r1 = kg(p0.input_grid, p0.output_grid), kg(p1.input_grid, p1.output_grid)
    f0, f1 = _flat(r0["result"]), _flat(r1["result"])
    cards1 = (f"<div class=card><div class=lbl>compare(P0G0, P0G1)</div>{_first_table(f0)}</div>"
              f"<div class=card><div class=lbl>compare(P1G0, P1G1)</div>{_first_table(f1)}</div>")
    card2 = (f"<div class=card wide><div class=lbl>compare(1차_P0, 1차_P1) "
             f"<span class=dim>— 제안: verdict끼리 같음/다름만, 하위값 없음</span></div>{_second_table(f0, f1)}</div>")
    return (f"<section><h2>{tid}</h2>"
            f"<h3>0차 — grid property dict 4개</h3><div class=row>{cards0}</div>"
            f"<h3>1차 — compare(G0,G1) 2개 (경로별 verdict + 값)</h3><div class=row>{cards1}</div>"
            f"<h3>2차 — compare(1차,1차) 1개 <span class=dim>[제안 방식]</span></h3>"
            f"<div class=row>{card2}</div></section>")


def page(sections, subtitle=""):
    return (f"<!doctype html><meta charset='utf-8'><title>compare 0·1·2차 (제안)</title>"
            f"<style>{CSS}</style>"
            f"<h1>compare 차수별 — 0차 property · 1차 · <b>2차(제안 방식)</b>{subtitle}</h1>"
            f"<p class=lead>2차는 relation 끼리 비교라, 각 property 경로에서 <b>verdict(COMM/DIFF)가 같은지/다른지만</b>"
            f" 표기 — 속성값·하위비교는 넣지 않는다. 그래서 2차가 폭발하지 않고 property 축으로 평평하게 읽힌다.</p>"
            f"{''.join(sections)}")


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arc.focus_solver import _load_survey, SURVEY_AGI
    from arc.make_made_tasks import write_all
    write_all()
    agi = sorted(set(SURVEY_AGI + ["8efcae92"] + AGI20 + EVAL50))    # training + evaluation 모두(재귀 glob)
    tasks = dict(_load_survey(agi_ids=agi))                          # easy 9 + made 2 + agi 전부
    sections = []
    for tid in TASKS:
        try:
            sections.append(section(tid, tasks[tid]))
        except Exception as e:                                       # noqa: BLE001
            print(f"  skip {tid}: {type(e).__name__}: {e}")
    with open(OUT, "w") as f:
        f.write(page(sections, subtitle=f" · {len(sections)}문제 (easy·made·ARC-AGI)"))
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin-bottom:18px;max-width:920px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 18px;background:#161b22}
h2{font-size:16px;margin:0 0 6px;color:#e6edf3} h3{font-size:13px;margin:14px 0 6px;color:#adbac7}
.dim{color:#6e7681;font-weight:normal}
.row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.card{border:1px solid #30363d;border-radius:7px;padding:8px 10px;background:#0d1117;max-width:430px}
.card.wide{max-width:100%;flex:1 1 100%}
.lbl{font-size:12px;margin-bottom:6px;color:#d2a8ff}
table.g{border-collapse:collapse;margin-bottom:8px} table.g td{width:13px;height:13px;border:1px solid #222}
table.t{border-collapse:collapse;width:100%;font-size:12px}
table.t th,table.t td{border:1px solid #30363d;padding:2px 7px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.comm td{background:#0f1f13} tr.comm .v{color:#3fb950;font-weight:bold}
tr.diff td{background:#2a1416} tr.diff .v{color:#f85149;font-weight:bold}
tr.grp td{background:#21262d;color:#f0b72f;font-weight:bold;letter-spacing:.5px}
td.sub{color:#8b949e;padding-left:16px}
.note{margin-top:6px;color:#d29922}
pre{background:#010409;border:1px solid #30363d;border-radius:6px;padding:6px 8px;margin:0;
 overflow:auto;max-height:220px;font-size:11px;color:#c9d1d9;white-space:pre}
"""


if __name__ == "__main__":
    print("wrote", build())
