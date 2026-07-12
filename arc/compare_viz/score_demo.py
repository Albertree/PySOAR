# -*- coding: utf-8 -*-
"""
score_demo — 1차 '유사도'(identity) 와 2차 '일치도'(agreement) 를 08ed6ac7 로 시각화.
  · 1차 score = 보존된 속성 수/3   (size/color/contents 각 COMM/DIFF, any-DIFF→DIFF rollup)
  · 2차 score = verdict 일치 속성/3 (둘 다 DIFF 도 '일치'=COMM)  ← 핵심
대비로 '2차를 any-DIFF→DIFF 로 잘못 세면' 도 같이 보여 준다.

    python3 -m arc.compare_viz.score_demo     # -> arc/score_demo.html
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "score_demo.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
PROPS = ["size", "color", "contents"]


def _grid_html(g):
    rows = "".join("<tr>" + "".join(
        f"<td style='background:{PALETTE[v] if 0 <= v < 10 else '#333'}'></td>" for v in r) + "</tr>" for r in g)
    return f"<table class=g>{rows}</table>"


def _chip(prop, verdict):
    ok = verdict == "COMM"
    return f"<span class='chip {'c' if ok else 'd'}'>{prop} {'✓COMM' if ok else '✗DIFF'}</span>"


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arc.focus_solver import build_arckg, _load_survey, SURVEY_AGI
    from ARCKG.comparison import compare as kg
    task = dict(_load_survey(agi_ids=SURVEY_AGI))["08ed6ac7"]
    root = build_arckg("08ed6ac7", task)
    p0, p1 = root.example_pairs[0], root.example_pairs[1]
    raw = {"P0G0": task["train"][0]["input"], "P0G1": task["train"][0]["output"],
           "P1G0": task["train"][1]["input"], "P1G1": task["train"][1]["output"]}
    # 1차: 3속성 top-level verdict (compare category 에 이미 rollup 돼 있음)
    c0 = kg(p0.input_grid, p0.output_grid)["result"]["category"]
    c1 = kg(p1.input_grid, p1.output_grid)["result"]["category"]
    v0 = {p: c0[p]["type"] for p in PROPS}
    v1 = {p: c1[p]["type"] for p in PROPS}
    s0 = sum(v0[p] == "COMM" for p in PROPS)
    s1 = sum(v1[p] == "COMM" for p in PROPS)
    # 2차 올바름(agreement): 둘 다 DIFF 도 일치
    agree = {p: v0[p] == v1[p] for p in PROPS}
    s2 = sum(agree.values())
    # 2차 잘못(any-DIFF→DIFF): 한쪽이라도 DIFF 면 DIFF
    wrong = {p: (v0[p] == "COMM" and v1[p] == "COMM") for p in PROPS}
    s2w = sum(wrong.values())

    def pair_row(lbl, ga, gb, v, s):
        chips = "".join(_chip(p, v[p]) for p in PROPS)
        return (f"<div class=prow><div class=ends>{_grid_html(raw[ga])}"
                f"<span class=arr>→</span>{_grid_html(raw[gb])}</div>"
                f"<div class=mid><div class=cap>{lbl}</div>{chips}"
                f"<span class='score sim'>유사도 {s}/3</span></div></div>")

    def second_row(p):
        a = "일치" if agree[p] else "불일치"
        cls = "c" if agree[p] else "d"
        both_diff = v0[p] == "DIFF" and v1[p] == "DIFF"
        star = " <span class=star>← 둘 다 DIFF인데 일치</span>" if both_diff else ""
        return (f"<tr class={cls}><td>{p}</td><td>{v0[p]}</td><td>{v1[p]}</td>"
                f"<td class=v>{'COMM(일치)' if agree[p] else 'DIFF(불일치)'}</td><td>{star}</td></tr>")

    second = "".join(second_row(p) for p in PROPS)
    doc = f"""<!doctype html><meta charset='utf-8'><title>1차 유사도 vs 2차 일치도</title>
<style>{CSS}</style>
<h1>1차 유사도 vs 2차 일치도 — 08ed6ac7</h1>
<p class=lead>같은 문제인데 두 점수가 정반대로 나온다: <b>1차 유사도는 낮고(1/3)</b> —
grid 는 색·내용이 많이 바뀌니까 — <b>2차 일치도는 최고(3/3)</b> — 두 pair 의 <i>변환</i>은 완전히 같으니까.
차이의 핵심은 <b>2차에서 '둘 다 DIFF'를 '일치(COMM)'로 세는 것</b>.</p>

<div class=panel><h2>1차 — 각 pair 의 grid 변화 (유사도 = 보존 속성/3, any-DIFF→DIFF)</h2>
{pair_row("compare(P0G0 → P0G1)", "P0G0", "P0G1", v0, s0)}
{pair_row("compare(P1G0 → P1G1)", "P1G0", "P1G1", v1, s1)}
</div>

<div class=panel><h2>2차 — 두 변환의 일치도 <span class=ok>(올바른 규칙: 둘 다 DIFF → 일치)</span></h2>
<table class=t><tr><th>property</th><th>1차_P0</th><th>1차_P1</th><th>2차 결과</th><th></th></tr>{second}</table>
<div class='score agr big'>일치도 {s2}/3 → {"구조적으로 완전히 동일한 변환" if s2 == 3 else "일부 다름"}</div>
</div>

<div class=panel wrong><h2>❌ 만약 2차를 any-DIFF→DIFF 로 잘못 세면</h2>
<p>color·contents 가 '둘 다 DIFF'인데 이걸 DIFF(불일치)로 치면 →
<span class='score bad'>일치도 {s2w}/3</span> 로 떨어져, <b>같은 변환을 '다른 변환'으로 오독</b>한다.
(1차 유사도 1/3 와 똑같아져서 2차가 아무 새 정보를 못 줌.)</p></div>

<div class=take>정리: <b>1차 = "두 grid 가 얼마나 같나"(유사도, identity)</b> ·
<b>2차 = "두 변환이 얼마나 같나"(일치도, agreement — 둘 다 DIFF는 일치)</b>. 08ed 는 1/3 ↔ 3/3.</div>
"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.6 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin:0 0 16px;max-width:900px}
.panel{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 14px;background:#161b22}
.panel.wrong{border-color:#5a1e1e;background:#1a1113}
.panel h2{font-size:14px;margin:0 0 10px;color:#e6edf3} .ok{color:#3fb950;font-size:12px} .bad{background:#f85149}
.prow{display:flex;gap:20px;align-items:center;margin:8px 0;flex-wrap:wrap}
.ends{display:flex;gap:8px;align-items:center} .arr{color:#8b949e;font-size:18px}
.mid{display:flex;gap:8px;align-items:center;flex-wrap:wrap} .cap{color:#adbac7;margin-right:6px}
table.g{border-collapse:collapse} table.g td{width:13px;height:13px;border:1px solid #222}
.chip{display:inline-block;padding:2px 9px;border-radius:12px;font-size:12px;border:1px solid}
.chip.c{background:#0f2a17;color:#3fb950;border-color:#238636} .chip.d{background:#2a1416;color:#f85149;border-color:#8b2c2c}
.score{padding:3px 11px;border-radius:6px;font-weight:bold;margin-left:6px}
.score.sim{background:#1c2f4a;color:#79c0ff} .score.agr{background:#0f2a17;color:#3fb950}
.score.bad{background:#3a1518;color:#ff7b72;padding:2px 8px;border-radius:5px}
.score.big{display:inline-block;margin-top:10px;font-size:14px;padding:6px 14px}
table.t{border-collapse:collapse;margin-top:4px;font-size:13px}
table.t th,table.t td{border:1px solid #30363d;padding:4px 12px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.c td{background:#0f1f13} tr.c .v{color:#3fb950;font-weight:bold}
tr.d td{background:#2a1416} tr.d .v{color:#f85149;font-weight:bold}
.star{color:#d29922;font-size:11px} .wrong p{color:#d0a0a0}
.take{border:1px solid #30363d;border-radius:9px;padding:12px 16px;background:#12161c;color:#c9d1d9}
"""


if __name__ == "__main__":
    print("wrote", build())
