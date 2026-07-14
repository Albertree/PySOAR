"""HTML report for abstraction_rel3 — select by RELATION-DISTRIBUTION match, with the
comparison SCOPE discovered by search (no `all` predicate, no count, no given bias).

Per task shows: (1) scope×property 탐색 로그 = bias 발견, (2) 같은색 객체 간 비교 매트릭스
(who is '>' whom), (3) 프로파일(관계 분포)→색 맵 + pair간 COMM 시연, (4) 선택 근거(논리),
(5) 실행 격자(train+test). Appends the module source. Writes arc/abstraction_rel3_report.html.
"""
from __future__ import annotations

import html
import os

from arbor.solver import _load_survey, SURVEY_AGI, objects_of
from debugger.reports.abstraction import per_pair_objects
from debugger.reports.abstraction_rel3 import discover, profile, apply_map, _pair_map, sign, PROPS

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
    return (f'<b class="sw" style="background:{PAL[int(c) % 10]}"></b>{c}' if c is not None else "—")


def _pf(pf):
    return "(" + " ".join(pf) + ")"


def compare_matrix(pair, sel_color, prop):
    """N×N compare matrix among same-colour objects on `prop` — the row that is '>' vs all is
    the max; each row also shows its sorted profile + resulting colour."""
    outmap = {id(o): oc for (o, oc) in pair.recolored}
    objs = sorted([o for o in pair.allobjs if o.color == sel_color], key=lambda o: -PROPS[prop](o))
    head = "".join(f"<th>{PROPS[prop](o)}</th>" for o in objs)
    rows = ""
    for o in objs:
        cells = ""
        for q in objs:
            if q is o:
                cells += '<td class="diag">·</td>'
            else:
                s = sign(PROPS[prop](o), PROPS[prop](q))
                cls = {">": "gt", "<": "lt", "=": "eq"}[s]
                cells += f'<td class="{cls}">{s}</td>'
        pf = profile(o, pair.allobjs, "same-colour group", prop)
        col = outmap.get(id(o))
        allgt = all(x == ">" for x in pf)
        rows += (f'<tr class="{ "bigrow" if allgt else "" }"><th>{prop} {PROPS[prop](o)}</th>{cells}'
                 f'<td class="pf">{_pf(pf)}</td><td>→ {_sw(col)}</td></tr>')
    return (f'<table class="cmp"><tr><th>{prop} \\ {prop}</th>{head}<th>프로파일</th><th>색</th></tr>{rows}</table>')


def search_table(log, sol):
    rows = ""
    for combo, why in log:
        rows += f'<tr class="rej"><td>✗</td><td>{html.escape(combo)}</td><td>{html.escape(why)}</td></tr>'
    if sol:
        rows += (f'<tr class="acc"><td>✓</td><td>{html.escape(sol["scope"])} · {html.escape(sol["prop"])}</td>'
                 f'<td>프로파일이 pair간 COMM + 전 train 재현 → <b>발견</b></td></tr>')
    return f'<table class="srch"><tr><th></th><th>scope · property</th><th>판정</th></tr>{rows}</table>'


def comm_table(pairs, sol):
    """profile → colour, showing the SAME profile recurs in every pair (2nd-order COMM)."""
    maps = [_pair_map(p, sol["sel_color"], sol["scope"], sol["prop"]) for p in pairs if p.recolored]
    keys = sorted(sol["map"], key=lambda pf: pf.count(">"), reverse=True)
    head = "".join(f"<th>pair {i}</th>" for i in range(len(maps)))
    rows = ""
    for pf in keys:
        cells = "".join(f"<td>{_sw(m.get(pf))}</td>" for m in maps)
        agree = {m.get(pf) for m in maps if pf in m}
        badge = '<span class="ok">COMM</span>' if len(agree) == 1 else '<span class="bad">DIFF</span>'
        rows += f'<tr><th>{_pf(pf)}</th>{cells}<td>{badge}</td></tr>'
    return f'<table class="cmm"><tr><th>관계 분포(프로파일)</th>{head}<th></th></tr>{rows}</table>'


def task_card(tid, task):
    sol, log, sel_color = discover(task)
    pairs = per_pair_objects(task)
    solved = sol is not None
    v = "SOLVE" if solved else "IMPASSE"
    parts = [f'<section class="card"><h2><span class="{ "vs" if solved else "vi" }">{v}</span> '
             f'{html.escape(tid)}'
             + (f' <small>selection color (COMM) = {_sw(sel_color)}</small>' if sel_color is not None else '')
             + '</h2>']

    parts.append('<h3>① scope × property 탐색 — 비교 bias를 발견 (준 게 아니라 찾음)</h3>')
    parts.append(search_table(log, sol))
    if not solved:
        parts.append('<p class="note">→ 어떤 scope/property 조합도 프로파일이 pair간 COMM+재현이 아님 '
                     '= 정직한 abstraction-gap (다른 규칙 필요).</p></section>')
        return "".join(parts), v

    parts.append(f'<h3>② 같은색({sel_color}) 객체 간 {sol["prop"]} 비교 매트릭스 '
                 f'(compare→DIFF→arithmetic \'&gt;\')</h3>')
    for k, p in enumerate(pairs):
        parts.append(f'<div class="pair"><div class="ptit">pair {k}</div>'
                     + g_grid(task["train"][k]["input"], "input") + '<span class="arrow">→</span>'
                     + g_grid(task["train"][k]["output"], "output")
                     + compare_matrix(p, sel_color, sol["prop"]) + '</div>')

    parts.append('<h3>③ 관계 분포(프로파일) → 색  ·  pair간 COMM 시연 (2차 compare)</h3>')
    parts.append(comm_table(pairs, sol))

    blue = min(sol["map"], key=lambda pf: pf.count("<"))
    parts.append('<h3>④ 선택 근거 (논리 — \'all\'·count 없음)</h3>')
    parts.append(f'<div class="reason"><code>test input의 각 color-COMM({sel_color}) 객체 o에 대해:  '
                 f'profile(o | scope={html.escape(sol["scope"])}, {sol["prop"]})  ==  {_pf(blue)}'
                 f'  인 o 를 파랑(1)으로.</code><br>'
                 f'<span class="sub">— 예시의 파란 객체 관계분포 {_pf(blue)} 와 <b>COMM(같음)</b>인 객체를 고른다. '
                 f'값(3)을 세지 않고 분포를 매칭.</span></div>')

    parts.append('<h3>⑤ 실행결과 (예측 vs 정답)</h3><div class="exec">')
    for k, ex in enumerate(task["train"]):
        pred = apply_map(ex["input"], sel_color, sol["scope"], sol["prop"], sol["map"])
        ok = pred == ex["output"]
        parts.append(f'<div class="ecase"><div class="etit">train {k} {"✅" if ok else "❌"}</div>'
                     + g_grid(ex["input"], "in") + g_grid(pred, "predicted") + g_grid(ex["output"], "expected")
                     + '</div>')
    tp = task["test"][0]
    pred = apply_map(tp["input"], sel_color, sol["scope"], sol["prop"], sol["map"])
    exp = tp.get("output"); ok = pred == exp if exp is not None else None
    parts.append('<div class="ecase test"><div class="etit">TEST '
                 f'{"✅" if ok else ("❌" if ok is False else "?")}</div>'
                 + g_grid(tp["input"], "in") + g_grid(pred, "predicted")
                 + (g_grid(exp, "expected") if exp is not None else "") + '</div></div></section>')
    return "".join(parts), v


CSS = """
body{background:#15171c;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px}.hsub{color:#8b93a3;margin:0 0 18px}
.card{background:#1c1f26;border:1px solid #2a2e38;border-radius:10px;padding:18px 20px;margin:0 0 22px}
.card h2{font-size:16px;margin:0 0 10px;display:flex;align-items:center;gap:8px}.card h2 small{color:#8b93a3;font-weight:400}
.card h3{font-size:12.5px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.03em;margin:16px 0 8px;border-top:1px solid #262a34;padding-top:12px}
h2 span{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:700}.vs{background:#1f6f43;color:#c9f5da}.vi{background:#7a4a12;color:#ffdca8}
.grid{display:grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}.grid i{width:%CELL%px;height:%CELL%px;display:block}
.gwrap{display:inline-flex;flex-direction:column;gap:3px;vertical-align:top}.glab{font-size:10px;color:#8b93a3}
.arrow{color:#8b93a3;font-size:18px;margin:0 8px}
.pair{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:12px;margin:0 0 12px}
.ptit{font-weight:700;color:#cfd6e2;margin-bottom:6px}
.sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin:0 3px;border:1px solid #0006}
table{border-collapse:collapse;margin:8px 0;font-size:12px}
th,td{border:1px solid #2a2e38;padding:4px 8px;text-align:center}th{background:#20242e;color:#cfd6e2}
.srch td:first-child{font-weight:700}.srch .rej{color:#c98b8b}.srch .acc{color:#8fdca8}.srch td{text-align:left}
.cmp .gt{color:#4FCC30;font-weight:700}.cmp .lt{color:#F93C31}.cmp .eq{color:#FFDC00}.cmp .diag{color:#444}.cmp .pf{color:#9fb4d8;font-family:Menlo,monospace}
.cmp{display:inline-table;margin-left:12px;vertical-align:top}
.bigrow{background:#14301f}
.cmm .ok{color:#4FCC30;font-weight:700}.cmm .bad{color:#F93C31}
.reason{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:10px 12px}
.reason code{background:#0f1116;padding:2px 6px;border-radius:4px;color:#ffe6a8}.reason .sub{color:#9aa3b2}
.exec{display:flex;flex-direction:column;gap:10px}
.ecase{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:10px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.ecase.test{border-color:#3a5a7a}.etit{font-weight:700;min-width:80px}.note{color:#ffcf9a}
.code{background:#0f1116;border:1px solid #262a34;border-radius:6px;padding:12px;font:12px/1.5 SFMono-Regular,Menlo,monospace;white-space:pre;overflow-x:auto;color:#b8c4d8}
.toc{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}.toc a{color:#cfd6e2;text-decoration:none;background:#1c1f26;border:1px solid #2a2e38;border-radius:6px;padding:5px 10px;font-size:12px}
""".replace("%CELL%", str(CELL))


def build():
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    cards, toc = [], []
    for tid in ("08ed6ac7", "845d6e51", "868de0fa"):
        card, v = task_card(tid, tasks[tid])
        cards.append(f'<a id="{tid}"></a>' + card)
        toc.append(f'<a href="#{tid}">{tid} · {v}</a>')
    src = open(os.path.join(os.path.dirname(__file__), "abstraction_rel3.py")).read()
    appendix = ('<section class="card"><h2>구현 소스 — arc/abstraction_rel3.py</h2>'
                f'<pre class="code">{html.escape(src)}</pre></section>')
    doc = (f'<!doctype html><meta charset="utf-8"><title>abstraction_rel3 — profile match</title>'
           f'<style>{CSS}</style>'
           f'<h1>관계 분포(프로파일) 매칭으로 선택 — count·\'all\'·준 bias 없이</h1>'
           f'<p class="hsub">object를 비교 → DIFF의 arithmetic \'&gt;\'/\'&lt;\' → 그 <b>분포</b>가 pair간 COMM인 '
           f'scope/property를 <b>발견</b> → test input의 각 객체 중 예시 파란 객체와 <b>같은 분포</b>를 가진 것을 파랑으로.</p>'
           f'<div class="toc">{"".join(toc)}</div>{"".join(cards)}{appendix}')
    out = os.path.join(os.path.dirname(__file__), "abstraction_rel3_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
    print("open it:  open", p)
