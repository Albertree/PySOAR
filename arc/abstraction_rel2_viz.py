"""HTML report for abstraction_rel2 — 'largest' via COMM/DIFF + arithmetic '>', no concept.
Shows, per pair: grids, the N×N area-compare matrix among same-colour objects (who is '>'
than whom), each object's resulting colour, the COMM selection profile, the logical reason,
the general rule, and train/test execution grids. Appends the module source for audit.
Writes arc/abstraction_rel2_report.html."""
from __future__ import annotations

import html
import os

from arc.focus_solver import _load_survey, SURVEY_AGI, objects_of
from arc.abstraction import per_pair_objects, Obj
from arc.abstraction_rel2 import (compare_area, area_profile, is_greater_than_all_siblings,
                                  greater_count, same_color_siblings)

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]
CELL = 15


def g_grid(grid, label=None):
    if not grid:
        return '<div class="gwrap"><div class="grid empty">∅</div></div>'
    W = len(grid[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in grid for v in row)
    lab = f'<div class="glab">{html.escape(label)}</div>' if label else ""
    return (f'<div class="gwrap">{lab}<div class="grid" '
            f'style="grid-template-columns:repeat({W},{CELL}px)">{cells}</div></div>')


def _sw(c):
    return (f'<b class="sw" style="background:{PAL[int(c) % 10]}"></b>{c}'
            if c is not None else "—")


def compare_matrix(objs, sel_color, outmap):
    """N×N area-compare matrix among same-colour objects: cell = '>'/'<'/'=' (DIFF/COMM)."""
    greys = sorted([o for o in objs if o.color == sel_color], key=lambda o: -o.size)
    head = "".join(f"<th>a{o.size}</th>" for o in greys)
    rows = ""
    for o in greys:
        cells = ""
        for q in greys:
            if q is o:
                cells += '<td class="diag">·</td>'
            else:
                t, sign = compare_area(o, q)
                cls = "gt" if sign == ">" else ("lt" if sign == "<" else "eq")
                cells += f'<td class="{cls}">{t[0]}{sign}</td>'
        big = is_greater_than_all_siblings(o, objs)
        col = outmap.get(id(o))
        rows += (f'<tr class="{ "bigrow" if big else "" }"><th>area {o.size}</th>{cells}'
                 f'<td>→ {_sw(col)}{" <b class=badge>bigger-than-all</b>" if big else ""}</td></tr>')
    return (f'<table class="cmp"><tr><th>area \\ area</th>{head}<th>out color</th></tr>{rows}</table>')


def pair_block(k, ex, objs, sel_color):
    outmap = {}  # rebuild from recolor: we need mapping; recompute via per_pair
    return ""  # placeholder (unused)


def build():
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    tid = "08ed6ac7"
    task = tasks[tid]
    pairs = per_pair_objects(task)
    sel_color = next(iter({o.color for p in pairs for (o, _oc) in p.recolored}))

    parts = [f'<section class="card"><h2>{tid} — <span class="sub">selection color (COMM) = '
             f'{_sw(sel_color)}</span></h2>']

    blue_prof = []
    for k, p in enumerate(pairs):
        ex = task["train"][k]
        outmap = {id(o): oc for (o, oc) in p.recolored}
        big = next((o for o in p.allobjs if o.color == sel_color
                    and is_greater_than_all_siblings(o, p.allobjs)), None)
        blue_prof.append(outmap.get(id(big)) if big else None)
        grids = g_grid(ex["input"], "input") + '<div class="arrow">→</div>' + g_grid(ex["output"], "output")
        parts.append(f'<div class="pair"><div class="ptit">pair {k}</div>'
                     f'<div class="grow">{grids}</div>'
                     f'<div class="mtit">같은 색({sel_color}) 객체 간 area 비교 매트릭스 '
                     f'(compare→DIFF, 깊은분석→arithmetic \'>\'):</div>'
                     f'{compare_matrix(p.allobjs, sel_color, outmap)}</div>')

    comm = "COMM ✓" if len(set(blue_prof)) == 1 else "not COMM ✗"
    parts.append(f'<div class="reason"><b>선택 프로파일</b> "∀ 같은색 형제 s: area DIFF ∧ area &gt; s" '
                 f'→ 출력색 {blue_prof} — <span class="ok">{comm}</span></div>')
    parts.append('<div class="reason"><b>선택 근거 (논리식, 개념 주입 0):</b><br>'
                 f'<code>color(o) COMM {sel_color} ∧ (∀ s: color(s) COMM {sel_color} '
                 f'→ area(o) DIFF area(s) ∧ area(o) &gt; area(s))</code></div>')

    # general rule table
    table = {}
    for p in pairs:
        for (o, oc) in p.recolored:
            table[greater_count(o, p.allobjs)] = oc
    trows = "".join(f'<tr><td>{gc}</td><td>{_sw(c)}</td></tr>' for gc, c in sorted(table.items()))
    parts.append('<div class="reason"><b>일반 규칙</b> — color = table[ #{o가 \'>\'인 같은색 형제 수} ]:'
                 f'<table class="gen"><tr><th>greater_count</th><th>color</th></tr>{trows}</table></div>')

    # execution
    def apply(grid):
        objs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
        out = [row[:] for row in grid]
        for o in objs:
            if o.color != sel_color:
                continue
            c = table.get(greater_count(o, objs))
            if c is None:
                return None
            for (r, cc) in o.cells:
                out[r][cc] = c
        return out

    parts.append('<h3>실행결과 (예측 vs 정답)</h3><div class="exec">')
    for k, ex in enumerate(task["train"]):
        pred = apply(ex["input"]); ok = pred == ex["output"]
        parts.append(f'<div class="ecase"><div class="etit">train {k} {"✅" if ok else "❌"}</div>'
                     + g_grid(ex["input"], "in") + g_grid(pred, "predicted")
                     + g_grid(ex["output"], "expected") + '</div>')
    tp = task["test"][0]; pred = apply(tp["input"]); exp = tp.get("output")
    ok = pred == exp if exp is not None else None
    parts.append('<div class="ecase test"><div class="etit">TEST '
                 f'{"✅" if ok else ("❌" if ok is False else "?")}</div>'
                 + g_grid(tp["input"], "in") + g_grid(pred, "predicted")
                 + (g_grid(exp, "expected") if exp is not None else "") + '</div></div>')
    parts.append('</section>')

    # source code appendix
    src = open(os.path.join(os.path.dirname(__file__), "abstraction_rel2.py")).read()
    parts.append('<section class="card"><h2>구현 소스 — arc/abstraction_rel2.py</h2>'
                 f'<pre class="code">{html.escape(src)}</pre></section>')

    doc = (f'<!doctype html><meta charset="utf-8"><title>abstraction_rel2 — largest via COMM/DIFF</title>'
           f'<style>{CSS}</style>'
           f'<h1>largest 없이 — COMM/DIFF + arithmetic \'&gt;\' 로 선택</h1>'
           f'<p class="hsub">08ed6ac7: 회색 객체를 형제들과 compare → DIFF의 깊은분석 \'&gt;\' → '
           f'"모든 형제보다 큼" 프로파일이 pair간 COMM → test input 만으로 선택</p>'
           f'{"".join(parts)}')
    out = os.path.join(os.path.dirname(__file__), "abstraction_rel2_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


CSS = """
body{background:#15171c;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px} .hsub{color:#8b93a3;margin:0 0 20px}
.card{background:#1c1f26;border:1px solid #2a2e38;border-radius:10px;padding:18px 20px;margin:0 0 22px}
.card h2{font-size:16px;margin:0 0 12px} .card h2 .sub{color:#8b93a3;font-weight:400;font-size:13px}
.card h3{font-size:13px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.04em;margin:16px 0 8px;border-top:1px solid #262a34;padding-top:12px}
.grid{display:grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}
.grid i{width:%CELL%px;height:%CELL%px;display:block}
.gwrap{display:inline-flex;flex-direction:column;gap:3px} .glab{font-size:10px;color:#8b93a3}
.grow{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0} .arrow{color:#8b93a3;font-size:18px}
.pair{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:12px;margin:0 0 12px}
.ptit{font-weight:700;color:#cfd6e2} .mtit{font-size:12px;color:#9aa3b2;margin:8px 0 4px}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin:0 3px;border:1px solid #0006}
.cmp,.gen{border-collapse:collapse;margin:4px 0;font-size:12px}
.cmp th,.cmp td,.gen th,.gen td{border:1px solid #2a2e38;padding:4px 8px;text-align:center}
.cmp th,.gen th{background:#20242e;color:#cfd6e2}
.cmp .gt{color:#4FCC30;font-weight:700} .cmp .lt{color:#F93C31} .cmp .eq{color:#FFDC00} .cmp .diag{color:#444}
.bigrow{background:#14301f} .badge{background:#1f6f43;color:#c9f5da;font-size:10px;padding:1px 6px;border-radius:5px;margin-left:6px}
.reason{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:10px 12px;margin:8px 0}
.reason code{background:#0f1116;padding:2px 6px;border-radius:4px;color:#ffe6a8}
.ok{color:#4FCC30;font-weight:700}
.exec{display:flex;flex-direction:column;gap:10px}
.ecase{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:10px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.ecase.test{border-color:#3a5a7a} .etit{font-weight:700;min-width:80px}
.code{background:#0f1116;border:1px solid #262a34;border-radius:6px;padding:12px;font:12px/1.5 SFMono-Regular,Menlo,monospace;white-space:pre;overflow-x:auto;color:#b8c4d8}
""".replace("%CELL%", str(CELL))


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
    print("open it:  open", p)
