# -*- coding: utf-8 -*-
"""
score_examples — 전체 ARC(training+evaluation)를 첫 두 pair 로 스캔해 얻은
2차 GRID 점수(size/color/contents 일치 개수, 둘 다 DIFF=일치)별 예시를 시각화.

스캔 결과(첫 두 pair): 3점 1094 · 2점 25(3종 다) · 1점 1(size만일치뿐) · 0점 0(없음).

    python3 -m arc.compare_viz.score_examples     # -> arc/score_examples.html
"""
from __future__ import annotations

import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "score_examples.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
PROPS = ["size", "color", "contents"]
ROOTS = [os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI/training"),
         os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI/evaluation")]

# 스캔으로 찾은 예시 (점수, 종류설명, tid)
EXAMPLES = [
    (3, "전부 일치 — 두 변환이 구조적으로 동일", "08ed6ac7"),
    (2, "size 불일치 (color·contents 일치)", "878187ab"),
    (2, "color 불일치 (size·contents 일치)", "137eaa0f"),
    (2, "contents 불일치 (size·color 일치)", "5ad8a7c0"),
    (1, "size 만 일치 (color·contents 불일치) — 전체에서 유일한 1점", "d931c21c"),
]


def _find(tid):
    from arc.dataset import load_task
    for r in ROOTS:
        hits = glob.glob(os.path.join(r, f"{tid}.json"))
        if hits:
            return load_task(hits[0])
    return None


def _verdicts(inp, out):
    size = "COMM" if (len(inp), len(inp[0])) == (len(out), len(out[0])) else "DIFF"
    ci = set(v for row in inp for v in row); co = set(v for row in out for v in row)
    color = "COMM" if ci == co else "DIFF"
    contents = "COMM" if inp == out else "DIFF"
    return {"size": size, "color": color, "contents": contents}


def _grid_html(g):
    n = max(len(g), len(g[0]))
    cs = max(7, min(15, 240 // n))
    rows = "".join("<tr>" + "".join(
        f"<td style='width:{cs}px;height:{cs}px;background:{PALETTE[v] if 0 <= v < 10 else '#333'}'></td>"
        for v in r) + "</tr>" for r in g)
    return f"<table class=g>{rows}</table>"


def _chips(v):
    return "".join(f"<span class='chip {'c' if v[p] == 'COMM' else 'd'}'>{p} "
                   f"{'✓' if v[p] == 'COMM' else '✗'}</span>" for p in PROPS)


def _section(score, kind, tid):
    task = _find(tid)
    if task is None:
        return f"<section><h3>{score}점 — {kind}</h3><div class=note>태스크 {tid} 를 찾지 못함</div></section>"
    t = task["train"]
    g = {"P0G0": t[0]["input"], "P0G1": t[0]["output"], "P1G0": t[1]["input"], "P1G1": t[1]["output"]}
    v0 = _verdicts(g["P0G0"], g["P0G1"])
    v1 = _verdicts(g["P1G0"], g["P1G1"])
    agree = {p: v0[p] == v1[p] for p in PROPS}
    grids = (f"<div class=ends>{_grid_html(g['P0G0'])}<span class=arr>→</span>{_grid_html(g['P0G1'])}</div>"
             f"<div class=pl>pair0</div>"
             f"<div class=ends>{_grid_html(g['P1G0'])}<span class=arr>→</span>{_grid_html(g['P1G1'])}</div>"
             f"<div class=pl>pair1</div>")
    second = "".join(
        f"<tr class={'c' if agree[p] else 'd'}><td>{p}</td><td>{v0[p]}</td><td>{v1[p]}</td>"
        f"<td class=v>{'일치' if agree[p] else '불일치'}</td>"
        f"<td>{'← 둘 다 DIFF라 일치' if (v0[p] == 'DIFF' and v1[p] == 'DIFF') else ''}</td></tr>"
        for p in PROPS)
    return (f"<section><h3><span class='sb s{score}'>{score}점</span> {kind} "
            f"<span class=tid>{tid}</span></h3>"
            f"<div class=grids>{grids}</div>"
            f"<div class=onecol><div class=lbl>1차 (각 pair 의 grid 변화)</div>"
            f"<div class=cr>pair0: {_chips(v0)}</div><div class=cr>pair1: {_chips(v1)}</div></div>"
            f"<div class=onecol><div class=lbl>2차 (두 변환의 일치, 둘 다 DIFF=일치)</div>"
            f"<table class=t><tr><th>property</th><th>pair0</th><th>pair1</th><th>2차</th><th></th></tr>"
            f"{second}</table></div></section>")


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    secs = [_section(*e) for e in EXAMPLES]
    zero = ("<section class=empty><h3><span class='sb s0'>0점</span> 전부 불일치</h3>"
            "<div class=note>전체 ARC(training 400 + evaluation 120)의 <b>첫 두 pair</b>에서 <b>0점은 없음</b>. "
            "0점이 되려면 size·color·contents 가 모두 불일치여야 하고, 특히 <b>contents 불일치</b>는 한 pair 가 "
            "<i>입력=출력(항등)</i>이어야 하는데, 거기에 더해 size·color 까지 갈리는 조합이 존재하지 않는다. "
            "(contents 는 거의 모든 pair 에서 둘 다 바뀜 → 2차에서 늘 '일치' → 점수를 깎지 못함.)</div></section>")
    doc = f"""<!doctype html><meta charset='utf-8'><title>2차 GRID 점수별 예시</title>
<style>{CSS}</style>
<h1>2차 GRID comparison 점수별 예시 (첫 두 pair · 전체 ARC 스캔)</h1>
<p class=lead>점수 = size·color·contents 중 <b>두 pair 의 verdict 가 일치하는 개수</b> (둘 다 DIFF 도 일치).
스캔 분포: <b>3점 1094 · 2점 25 · 1점 1 · 0점 0</b>. 2점은 3종류(size/color/contents 불일치) 다 존재,
1점은 size만일치 하나뿐, 0점은 전무.</p>
{''.join(secs)}{zero}
"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.6 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin:0 0 16px;max-width:940px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 14px;background:#161b22}
section.empty{border-style:dashed;background:#12161c}
h3{font-size:14px;margin:0 0 10px;color:#e6edf3} .tid{color:#6e7681;font-weight:normal;margin-left:6px}
.sb{display:inline-block;padding:2px 9px;border-radius:6px;font-weight:bold;margin-right:6px}
.s3{background:#0f2a17;color:#3fb950} .s2{background:#1c2f4a;color:#79c0ff}
.s1{background:#3a2e12;color:#e3b341} .s0{background:#3a1518;color:#ff7b72}
.grids{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.ends{display:flex;gap:6px;align-items:center} .arr{color:#8b949e;font-size:16px}
.pl{color:#8b949e;font-size:11px;margin-right:10px}
table.g{border-collapse:collapse} table.g td{border:1px solid #202020}
.onecol{margin:6px 0} .lbl{font-size:12px;color:#adbac7;margin-bottom:3px}
.cr{margin:2px 0}
.chip{display:inline-block;padding:1px 8px;border-radius:11px;font-size:12px;border:1px solid;margin-right:4px}
.chip.c{background:#0f2a17;color:#3fb950;border-color:#238636} .chip.d{background:#2a1416;color:#f85149;border-color:#8b2c2c}
table.t{border-collapse:collapse;font-size:12px;margin-top:2px}
table.t th,table.t td{border:1px solid #30363d;padding:2px 10px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.c td{background:#0f1f13} tr.c .v{color:#3fb950;font-weight:bold}
tr.d td{background:#2a1416} tr.d .v{color:#f85149;font-weight:bold}
.note{color:#c9a05a} .empty .note{color:#d0a0a0}
"""


if __name__ == "__main__":
    print("wrote", build())
