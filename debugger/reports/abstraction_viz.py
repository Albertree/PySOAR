"""Visualize the abstraction pipeline per task, as an HTML report:
  재료1  per-pair programs (each train pair: input→output grids + the pair's SSA program)
  재료2  abstraction method (active binding search: rejects/accept + cross-pair table)
  결과물  TASK.solution (the anti-unified general program)
  실행결과  execution grids (solution applied to every train input + test, vs expected)

Read-only over focus_solver/abstraction; writes arc/abstraction_report.html."""
from __future__ import annotations

import html
import os

from arc.focus_solver import _load_survey, SURVEY_AGI
from debugger.reports.abstraction import per_pair_objects, abstract_task, _apply_solution, RELATIONS

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


def ssa_for_pair(pair):
    rec = pair.recolored
    defs = ["in_objs = objects_of(input_grid)"]
    body = ["tfg0 = input_grid"]
    for k, (o, oc) in enumerate(rec):
        defs.append(f"O{k} = in_objs[{o.idx}]")
        body.append(f"tfg{k+1} = apply_DSL(tfg{k}, coloring, O{k}.coord, {oc})")
    body.append(f"output_grid = tfg{len(rec)}")
    return "\n".join(defs + [""] + body)


def _sw(c):
    return f'<b class="sw" style="background:{PAL[int(c) % 10]}"></b>{c}'


def feature_table(pairs, sel, binding):
    """for a lookup binding: feature-value × pair grid of out-colours, showing that the
    learned table is CONSISTENT (COMM) across pairs — the anti-unification evidence."""
    if binding.kind != "lookup":
        return ""
    fn = binding._featfn
    per_pair = []
    for p in pairs:
        chosen = [o for o in p.allobjs if sel.fn(o, p)]
        outmap = {id(o): oc for (o, oc) in p.recolored}
        m = {}
        for o in chosen:
            m[fn(o, chosen, p)] = outmap.get(id(o))
        per_pair.append(m)
    keys = sorted({k for m in per_pair for k in m}, key=str)
    head = "".join(f"<th>pair {i}</th>" for i in range(len(per_pair)))
    rows = ""
    for k in keys:
        cells = ""
        for m in per_pair:
            cells += (f"<td>{_sw(m[k])}</td>" if k in m and m[k] is not None
                      else '<td class="na">—</td>')
        agree = {m[k] for m in per_pair if k in m}
        badge = ('<span class="ok">COMM</span>' if len(agree) == 1
                 else '<span class="bad">DIFF</span>')
        rows += f'<tr><th>{binding.name} = {html.escape(str(k))}</th>{cells}<td>{badge}</td></tr>'
    return f'<table class="align"><tr><th>{binding.name}(o)</th>{head}<th></th></tr>{rows}</table>'


def search_log_html(r):
    out = '<ul class="search">'
    for t, why in r.tried:
        out += f'<li class="rej">✗ <code>{html.escape(t)}</code> — {html.escape(str(why))}</li>'
    if r.binding:
        out += (f'<li class="acc">✓ selection <code>{html.escape(r.sel.name)}</code> + '
                f'<code>{html.escape(r.binding.describe())}</code></li>')
    out += "</ul>"
    return out


def task_card(tid, task):
    r = abstract_task(tid, task)
    pairs = per_pair_objects(task)
    if r.ok and r.test_ok is not False:
        verdict, vclass = "SOLVE", "vsolve"
    elif r.ok:
        verdict, vclass = "OVERFIT", "vpart"
    elif r.binding is None and "IMPASSE" in r.note:
        verdict, vclass = "IMPASSE", "vimp"
    else:
        verdict, vclass = "N/A", "vna"
    parts = [f'<section class="card"><h2><span class="{vclass}">{verdict}</span> '
             f'{html.escape(tid)} <small>({len(task["train"])} train pairs · '
             f'test {"✅" if r.test_ok else ("❌" if r.test_ok is False else "?")})</small></h2>']

    # ── 재료 1: per-pair programs ──
    has_recolor = any(p.recolored for p in pairs)
    parts.append('<h3>재료 1 · per-pair programs (각 pair의 G0→G1)</h3>')
    if has_recolor:
        for k, p in enumerate(pairs):
            ex = task["train"][k]
            grids = g_grid(ex["input"], "G0") + '<div class="arrow">→</div>' + g_grid(ex["output"], "G1")
            steps = "".join(
                f'<div class="ostep">obj[{o.idx}] size {o.size}, w{o.width} h{o.height} '
                f'holes{o.holes} · {_sw(o.color)}→{_sw(oc)}</div>' for (o, oc) in p.recolored)
            parts.append(f'<div class="pair"><div class="ptit">pair {k}</div>'
                         f'<div class="grow">{grids}</div>'
                         f'<pre class="prog">{html.escape(ssa_for_pair(p))}</pre>'
                         f'<div class="steps">{steps}</div></div>')
    else:
        parts.append(f'<p class="note">{html.escape(r.note)}</p>')

    # ── 재료 2: abstraction 방법 ──
    if has_recolor:
        parts.append('<h3>재료 2 · abstraction 방법 (능동 탐색: selection × feature/relation binding)</h3>')
        parts.append(search_log_html(r))
        if r.binding:
            parts.append(f'<p>selection = <code>{html.escape(r.sel.expr)}</code></p>')
            parts.append(feature_table(pairs, r.sel, r.binding))

    # ── 결과물: TASK.solution ──
    if r.binding is not None:
        parts.append('<h3>결과물 · TASK.solution (anti-unified)</h3>')
        parts.append(f'<pre class="sol">{html.escape(getattr(r, "solution", ""))}</pre>')

    # ── 실행결과: grids ──
    if r.binding is not None:
        parts.append('<h3>실행결과 · solution 적용 (예측 vs 정답)</h3>')
        parts.append('<div class="exec">')
        for k, ex in enumerate(task["train"]):
            pred = _apply_solution(ex["input"], r.sel, r.binding)
            ok = pred == ex["output"]
            parts.append('<div class="ecase">'
                         f'<div class="etit">train {k} {"✅" if ok else "❌"}</div>'
                         + g_grid(ex["input"], "in") + g_grid(pred, "predicted")
                         + g_grid(ex["output"], "expected") + '</div>')
        if task.get("test"):
            tp = task["test"][0]
            pred = _apply_solution(tp["input"], r.sel, r.binding)
            exp = tp.get("output")
            ok = (pred == exp) if exp is not None else None
            mark = "✅" if ok else ("❌" if ok is False else "?")
            parts.append('<div class="ecase test">'
                         f'<div class="etit">TEST {mark}</div>'
                         + g_grid(tp["input"], "in") + g_grid(pred, "predicted")
                         + (g_grid(exp, "expected") if exp is not None else "") + '</div>')
        parts.append('</div>')

    parts.append('</section>')
    return "".join(parts), verdict


CSS = """
body{background:#15171c;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#8b93a3;margin:0 0 20px}
.card{background:#1c1f26;border:1px solid #2a2e38;border-radius:10px;padding:18px 20px;margin:0 0 22px}
.card h2{font-size:16px;margin:0 0 10px;display:flex;align-items:center;gap:8px}
.card h2 small{color:#8b93a3;font-weight:400}
.card h3{font-size:13px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.04em;margin:18px 0 8px;border-top:1px solid #262a34;padding-top:12px}
.vsolve{background:#1f6f43;color:#c9f5da} .vimp{background:#7a4a12;color:#ffdca8}
.vpart{background:#6b4a1a;color:#ffd08a} .vna{background:#333;color:#aaa}
h2 span{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:700}
.grid{display:grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}
.grid i{width:%CELL%px;height:%CELL%px;display:block}
.grid.empty{padding:8px;color:#666}
.gwrap{display:inline-flex;flex-direction:column;gap:3px;align-items:flex-start}
.glab{font-size:10px;color:#8b93a3}
.grow{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:6px 0}
.arrow{color:#8b93a3;font-size:18px}
.pair{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:12px;margin:0 0 12px}
.ptit{font-weight:700;color:#cfd6e2;margin-bottom:4px}
.prog,.sol{background:#0f1116;border:1px solid #262a34;border-radius:6px;padding:10px;font:12px/1.5 SFMono-Regular,Menlo,monospace;white-space:pre;overflow-x:auto;color:#b8e0c8}
.sol{color:#ffe6a8;border-color:#4a3f1a}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
.ostep{background:#20242e;border-radius:5px;padding:3px 8px;font-size:12px}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin:0 3px 0 2px;border:1px solid #0006}
.search{list-style:none;padding:0;margin:6px 0}
.search li{padding:3px 0} .search code{background:#0f1116;padding:2px 6px;border-radius:4px}
.rej{color:#c98b8b} .acc{color:#8fdca8}
.align{border-collapse:collapse;margin:10px 0;font-size:12px}
.align th,.align td{border:1px solid #2a2e38;padding:5px 9px;text-align:left}
.align th{background:#20242e;color:#cfd6e2}
.align .na{color:#555} .ok{color:#4FCC30;font-weight:700} .bad{color:#F93C31;font-weight:700}
.exec{display:flex;flex-direction:column;gap:10px}
.ecase{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:10px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.ecase.test{border-color:#3a5a7a}
.etit{font-weight:700;min-width:80px}
.note{color:#9aa3b2}
.toc{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}
.toc a{color:#cfd6e2;text-decoration:none;background:#1c1f26;border:1px solid #2a2e38;border-radius:6px;padding:5px 10px;font-size:12px}
code{font-family:SFMono-Regular,Menlo,monospace}
""".replace("%CELL%", str(CELL))


def build(order=None):
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    order = order or ["08ed6ac7", "868de0fa", "845d6e51", "009d5c81", "0ca9ddb6", "11852cab"]
    cards, toc = [], []
    for tid in order:
        if tid not in tasks:
            continue
        card, verdict = task_card(tid, tasks[tid])
        cards.append(f'<a id="{tid}"></a>' + card)
        toc.append(f'<a href="#{tid}">{tid} · {verdict}</a>')
    doc = (f'<!doctype html><meta charset="utf-8"><title>ARBOR abstraction report</title>'
           f'<style>{CSS}</style><h1>ARBOR — abstraction 파이프라인 리포트</h1>'
           f'<p class="sub">per-pair programs → 능동 binding 탐색 → TASK.solution → 실행결과 (문제별)</p>'
           f'<div class="toc">{"".join(toc)}</div>{"".join(cards)}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "abstraction_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
    print("open it:  open", p)
