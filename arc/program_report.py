# -*- coding: utf-8 -*-
"""
program_report -- hypothesize 가 합성한 **PAIR.program(실행가능 flat Python, level-1 형식)** 을
문제별로 보여주고, 브라우저에서 **직접 실행**해 output grid 를 볼 수 있는 별도 HTML.

각 섹션: (1) full program (self-contained — DSL 정의 + input_grid 선언 포함해 그대로 복붙 실행가능),
(2) input grid, (3) ▶ 실행 버튼 → apply_DSL/coloring(JS 재구현)로 프로그램을 eval → output grid 렌더 +
train output 과 일치 표시. program 이 없으면(object level 실패) 그 사유 표시.

    python3 arc/program_report.py     # -> arc/program_report.html
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "program_report.html")

# level-1 program 이 self-contained 로 실행되게 앞에 붙일 DSL 정의(파이썬). 화면 표시 + 복붙용.
_PREAMBLE = '''\
# --- DSL (ARC-TBD level-1) ---
def coloring(grid, cells, color):
    g = [row[:] for row in grid]
    for (r, c) in cells:
        g[r][c] = color
    return g
def make_grid(height, width, fill):
    return [[fill] * width for _ in range(height)]
def apply_DSL(grid, func, *args):
    return func(grid, *args)
def obj(coord, color):                       # object: 좌표(셀)·색 — .coord/.color 로 참조
    o = type("Obj", (), {})(); o.coord = coord; o.color = color; return o
# --- input (this pair) ---
input_grid = %s
# --- objects & synthesized program (rule-based) ---
'''


def _run_programs():
    """15 태스크를 돌려 (tid, program, input, output, ok) 뽑는다. program 은 PAIR.program(합성됐으면)."""
    from arc.focus_solver import _load_survey, SURVEY_AGI, setup_focus_agent
    from arc.fine_trace import _Tracer
    out = []
    for tid, task in _load_survey(agi_ids=SURVEY_AGI):
        prog, ok = None, False
        try:
            tr = _Tracer(task, tid, setup=setup_focus_agent)
            tr.run(max_cycles=1000)
            prog = next((v for (i, a, v) in tr.ag.wm if a == "program" and v != "{}"), None)
            ok = "yes" in [v for (i, a, v) in tr.ag.wm if a == "hypothesized"]
        except Exception as e:                              # noqa: BLE001
            prog = f"# 실행 오류: {type(e).__name__}: {e}"
        out.append({"id": tid, "program": prog, "ok": ok,
                    "input": task["train"][0]["input"], "output": task["train"][0]["output"]})
    return out


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin-bottom:18px}
section{border:1px solid #30363d;border-radius:9px;padding:14px 16px;margin:0 0 16px;background:#161b22}
h2{font-size:15px;margin:0 0 10px}
.row{display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap}
pre{background:#0b0e14;border:1px solid #30363d;border-radius:7px;padding:11px 13px;overflow:auto;
 max-height:340px;font-size:12px;color:#c9d1d9;white-space:pre;flex:1 1 340px;min-width:320px}
.gcol{display:flex;flex-direction:column;gap:5px;align-items:flex-start}
.glbl{font-size:11px;color:#8b949e}
table.g{border-collapse:collapse;table-layout:fixed} table.g td{width:13px;height:13px;min-width:13px;border:1px solid #222}
button{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 16px;font:13px ui-monospace;cursor:pointer}
button:hover{background:#2ea043}
.verdict{font-weight:bold;margin-top:6px} .ok{color:#3fb950} .bad{color:#f85149}
.none{color:#8b949e;font-style:italic}
"""


def build():
    data = _run_programs()
    palette = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00", "#AAAAAA",
               "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
    sections = []
    for d in data:
        if d["program"] and d["program"].startswith("tfg0"):
            full = (_PREAMBLE % json.dumps(d["input"])) + d["program"] + "\n"
            body = (f"<div class=row>"
                    f"<pre id='prog{d['id']}'>{full}</pre>"
                    f"<div class=gcol><span class=glbl>input_grid</span><div id='in{d['id']}'></div>"
                    f"<button onclick=\"run('{d['id']}')\">▶ 실행</button>"
                    f"<span class=glbl>output (실행 결과)</span><div id='out{d['id']}'></div>"
                    f"<div class=verdict id='v{d['id']}'></div></div>"
                    f"<div class=gcol><span class=glbl>expected P0.G1</span><div id='exp{d['id']}'></div></div>"
                    f"</div>")
        else:
            reason = d["program"] or "object level 에서 합성 실패 (recolor 규칙 미해당 → PIXEL 대상)"
            body = f"<div class=none>program 없음 — {reason if reason.startswith('#') else reason}</div>"
        sections.append(f"<section><h2>{d['id']}{' ✓' if d['ok'] else ''}</h2>{body}</section>")

    payload = {d["id"]: {"input": d["input"], "output": d["output"],
                         "program": d["program"] if (d["program"] or "").startswith("tfg0") else None}
               for d in data}
    doc = f"""<!doctype html><meta charset='utf-8'><title>ARBOR level-1 programs</title>
<style>{CSS}</style>
<h1>ARBOR — hypothesize 가 합성한 실행가능 프로그램 (level-1)</h1>
<p class=lead>규칙기반 coloring 이 써 낸 flat Python. <b>▶ 실행</b> = DSL(apply_DSL/coloring)을 JS 로
재구현해 프로그램을 그대로 실행 → output grid. expected(P0.G1)와 비교.</p>
{''.join(sections)}
<script>
const D={json.dumps(payload)}, PAL={json.dumps(palette)};
function gridHTML(g){{if(!g)return'';let h='<table class=g>';for(const row of g){{h+='<tr>';
 for(const v of row){{h+='<td style="background:'+(PAL[v]||'#D6FFFF')+'"></td>';}}h+='</tr>';}}return h+'</table>';}}
function coloring(grid,cells,color){{let g=grid.map(r=>r.slice());for(const [r,c] of cells){{if(g[r]&&g[r][c]!==undefined)g[r][c]=color;}}return g;}}
function make_grid(h,w,fill){{return Array.from({{length:h}},()=>Array(w).fill(fill));}}
function apply_DSL(grid,func){{const args=Array.prototype.slice.call(arguments,2);return func.apply(null,[grid].concat(args));}}
function obj(coord,color){{return {{coord:coord,color:color}};}}
function eq(a,b){{return JSON.stringify(a)===JSON.stringify(b);}}
function run(id){{
 const t=D[id];if(!t||!t.program)return;
 // 파이썬 program → JS: (r, c) 튜플 → [r,c], 변수(tfg/O/T/output_grid) 선언
 let js=t.program.replace(/\\((\\d+),\\s*(\\d+)\\)/g,'[$1,$2]').replace(/^(tfg\\d+|output_grid|O\\d+|T\\d+)\\s*=/gm,'var $1 =');
 let input_grid=t.input.map(r=>r.slice());
 try{{ eval(js); }}catch(e){{ document.getElementById('v'+id).innerHTML='<span class=bad>실행 오류: '+e+'</span>'; return; }}
 document.getElementById('out'+id).innerHTML=gridHTML(output_grid);   // program 이 var 로 선언(eval leak)
 const ok=eq(output_grid,t.output);
 document.getElementById('v'+id).innerHTML=ok?'<span class=ok>✓ output == P0.G1 (프로그램이 정확히 재현)</span>':'<span class=bad>✗ 불일치</span>';
}}
// 초기 렌더: input / expected grid
for(const id in D){{const t=D[id];
 const ig=document.getElementById('in'+id);if(ig)ig.innerHTML=gridHTML(t.input);
 const eg=document.getElementById('exp'+id);if(eg)eg.innerHTML=gridHTML(t.output);}}
</script>"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


if __name__ == "__main__":
    print("wrote", build())
