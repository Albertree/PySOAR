# -*- coding: utf-8 -*-
"""
score_examples_allpairs — 전체 ARC(training+eval)를 **모든 pair** 로 스캔.
각 property(size/color/contents)는 **전 pair 에서 verdict 가 만장일치일 때만 '일치'(COMM), 아니면 DIFF**.
점수 = 일치 property 수. 점수별·종류별 예시를 각 문제의 전 pair 와 함께 시각화.

스캔(모든 pair): 3점 1071 · 2점 45 · 1점 4 · 0점 0.

    python3 -m arc.compare_viz.score_examples_allpairs     # -> arc/score_examples_allpairs.html
"""
from __future__ import annotations

import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "score_examples_allpairs.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
PROPS = ["size", "color", "contents"]
ROOTS = [os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI/training"),
         os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI/evaluation")]

EXAMPLES = [
    (3, "전부 일치 — 세 속성 모두 전 pair 만장일치", "00576224"),
    (2, "size 불일치 (color·contents 일치)", "5587a8d0"),
    (2, "color 불일치 (size·contents 일치)", "137eaa0f"),
    (2, "contents 불일치 (size·color 일치)", "22eb0ac0"),
    (1, "size 만 일치 (color·contents 불일치)", "253bf280"),
    (1, "color 만 일치 (size·contents 불일치)", "d4b1c2b1"),
]


def _find(tid):
    from arc.dataset import load_task
    for r in ROOTS:
        hits = glob.glob(os.path.join(r, f"{tid}.json"))
        if hits:
            return load_task(hits[0])
    return None


def _verdict(inp, out):
    size = "COMM" if (len(inp), len(inp[0])) == (len(out), len(out[0])) else "DIFF"
    ci = set(v for r in inp for v in r); co = set(v for r in out for v in r)
    return {"size": size, "color": "COMM" if ci == co else "DIFF",
            "contents": "COMM" if inp == out else "DIFF"}


def _grid_html(g):
    n = max(len(g), len(g[0]))
    cs = max(5, min(12, 150 // n))
    rows = "".join("<tr>" + "".join(
        f"<td style='width:{cs}px;height:{cs}px;background:{PALETTE[v] if 0 <= v < 10 else '#333'}'></td>"
        for v in r) + "</tr>" for r in g)
    return f"<table class=g>{rows}</table>"


def _section(score, kind, tid):
    task = _find(tid)
    if task is None:
        return f"<section><h3>{score}점 — {kind}</h3><div class=note>{tid} 못 찾음</div></section>"
    tr = task["train"]
    vs = [_verdict(e["input"], e["output"]) for e in tr]
    consist = {p: len({v[p] for v in vs}) == 1 for p in PROPS}
    # 전 pair 그리드
    gcells = "".join(
        f"<div class=pcell><div class=pl>pair{i}</div>"
        f"<div class=ends>{_grid_html(e['input'])}<span class=arr>→</span>{_grid_html(e['output'])}</div></div>"
        for i, e in enumerate(tr))
    # 매트릭스: 행=pair, 열=속성
    head = "<tr><th>pair</th>" + "".join(f"<th>{p}</th>" for p in PROPS) + "</tr>"
    body = ""
    for i, v in enumerate(vs):
        body += f"<tr><td>pair{i}</td>" + "".join(
            f"<td class='{'c' if v[p] == 'COMM' else 'd'}'>{v[p]}</td>" for p in PROPS) + "</tr>"
    summ = "<tr class=sum><td>전 pair 일치?</td>" + "".join(
        f"<td class='{'c' if consist[p] else 'd'} v'>{'일치' if consist[p] else '불일치'}</td>" for p in PROPS) + "</tr>"
    return (f"<section><h3><span class='sb s{score}'>{score}점</span> {kind} "
            f"<span class=tid>{tid} · pair {len(tr)}개</span></h3>"
            f"<div class=grids>{gcells}</div>"
            f"<table class=t>{head}{body}{summ}</table>"
            f"<div class=note2>property 가 전 pair 에서 <b>만장일치일 때만 '일치'</b> — 하나라도 다르면 불일치(DIFF).</div>"
            f"</section>")


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    secs = [_section(*e) for e in EXAMPLES]
    missing = ("<section class=empty><h3>없는 종류</h3><div class=note>"
               "<b>1점 contents만일치</b>(size·color 불일치 + contents 일치)와 <b>0점 전부불일치</b>는 전체 ARC 어디에도 없다. "
               "0점·contents불일치엔 <i>항등 pair(입력=출력)</i>가 필요한데, contents 는 거의 모든 pair 에서 바뀌어 "
               "전 pair 만장일치 DIFF(=일치)로 남기 때문. contents 가 점수를 깎는 경우가 극히 드물다.</div></section>")
    doc = f"""<!doctype html><meta charset='utf-8'><title>2차 GRID 점수 (모든 pair)</title>
<style>{CSS}</style>
<h1>2차 GRID 점수별 예시 — <b>모든 pair</b> 기준 (전체 ARC 스캔)</h1>
<p class=lead>점수 = size·color·contents 중, 각 속성의 within-verdict 가 <b>전 pair 에서 만장일치</b>인 개수
(모두 COMM 또는 모두 DIFF → 일치; 하나라도 섞이면 불일치=DIFF). 분포: <b>3점 1071 · 2점 45 · 1점 4 · 0점 0</b>.</p>
{''.join(secs)}{missing}
"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.6 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin:0 0 16px;max-width:960px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 14px;background:#161b22}
section.empty{border-style:dashed;background:#12161c}
h3{font-size:14px;margin:0 0 10px;color:#e6edf3} .tid{color:#6e7681;font-weight:normal;margin-left:6px}
.sb{display:inline-block;padding:2px 9px;border-radius:6px;font-weight:bold;margin-right:6px}
.s3{background:#0f2a17;color:#3fb950} .s2{background:#1c2f4a;color:#79c0ff}
.s1{background:#3a2e12;color:#e3b341} .s0{background:#3a1518;color:#ff7b72}
.grids{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;margin-bottom:10px}
.pcell{display:flex;flex-direction:column;gap:3px;align-items:center}
.pl{color:#8b949e;font-size:11px} .ends{display:flex;gap:5px;align-items:center} .arr{color:#8b949e}
table.g{border-collapse:collapse} table.g td{border:1px solid #202020}
table.t{border-collapse:collapse;font-size:12px;margin-top:2px}
table.t th,table.t td{border:1px solid #30363d;padding:2px 12px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
td.c{background:#0f2a17;color:#3fb950} td.d{background:#2a1416;color:#f85149}
tr.sum td{border-top:2px solid #539bf5;font-weight:bold} tr.sum .v{font-size:13px}
.note{color:#d0a0a0} .note2{color:#8b949e;font-size:11px;margin-top:5px} .empty .note{color:#d0a0a0}
"""


if __name__ == "__main__":
    print("wrote", build())
