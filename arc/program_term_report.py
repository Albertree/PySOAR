# -*- coding: utf-8 -*-
"""
program_term_report -- program_term + program_resolve 파이프라인을 HTML 로 시각화
(사용자 요청 2026-07-13). 화면을 **세로 3분할**로 anti-unification 의 재료·과정·결과를 보이고,
상단 **토글 선택기**로 문제(easy_a·easy·ARC-AGI)를 골라 본다:

  ① 재료  = 각 train pair 의 program(관측 G0→G1) + AST(nested-dict term).  = anti-unify 입력.
  ② 과정  = 공통 골격(COMM) + DIFF 슬롯(변수)별 per-pair 값, 그 변수를 object/pixel comparison
            으로 해소하는 탐색(시도·기각이 보인다, §1-5).                    = anti-unify + resolve.
  ③ 결과  = 해소된 스키마(변수→도출식) + 그 스키마를 test input 에서 실행한 출력(정답 대조).

`python arc/program_term_report.py`  ->  arc/program_term_report.html (자기완결).
"""
from __future__ import annotations

import glob
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root

from arc.program_term import observed_program, lift, anti_unify   # noqa: E402
from arc.program_resolve import resolve_schema                    # noqa: E402
from arc.select_solver import fg_objects                          # noqa: E402

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]


# --- 태스크 로딩: easy_a(9) + easy(16) + ARC-AGI(survey + 작은 것 몇 개) ---------
def _load_tasks():
    from arc.dataset import list_tasks
    groups = []
    ea = list_tasks("easy_a")
    if ea:
        groups.append(("easy_a · 단일픽셀 (9)", ea))
    ez = list_tasks("easy")
    if ez:
        groups.append(("easy (16)", ez))
    made = []                                                # 합성 다객체 (COMM/DIFF 선택이 통과하는 예)
    for n in ("made000a", "made000b"):
        p = os.path.join(os.path.dirname(__file__), "data", "made", f"{n}.json")
        if os.path.exists(p):
            made.append((n, p))
    if made:
        groups.append(("made · 합성 다객체 (선택/이동)", made))
    agi_dir = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_AGI")
    named = ["08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab", "845d6e51", "868de0fa"]
    agi = []
    for n in named:
        h = glob.glob(os.path.join(agi_dir, "**", f"{n}.json"), recursive=True)
        if h:
            agi.append((n, h[0]))
    have = {n for n, _ in agi}
    for p in sorted(glob.glob(os.path.join(agi_dir, "training", "*.json"))):   # 작은 train 몇 개
        n = os.path.splitext(os.path.basename(p))[0]
        if n in have:
            continue
        try:
            t = json.load(open(p))
            area = max(len(g["input"]) * len(g["input"][0]) for g in t["train"])
        except Exception:                                                       # noqa: BLE001
            continue
        if area <= 150:                                                         # ~12x12 이하만
            agi.append((n, p))
        if len(agi) >= 14:
            break
    if agi:
        groups.append(("ARC-AGI · 실제 (survey + 작은 것)", agi))
    return groups


# --- 그리드/term 렌더 ---------------------------------------------------------
def _px(g):
    w = len(g[0]) if g else 1
    return 13 if w <= 10 else (10 if w <= 16 else 7)


def _grid(grid, px=None):
    if not grid:
        return '<span class="nogrid">∅</span>'
    px = px or _px(grid)
    W = len(grid[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in grid for v in row)
    return (f'<div class="grid" style="grid-template-columns:repeat({W},{px}px);'
            f'grid-auto-rows:{px}px">{cells}</div>')


def _term(term):
    if "var" in term:
        return f'<span class="tvar">{html.escape(term["var"])}</span>'
    if "lit" in term:
        v = term["lit"]
        lab = f"{len(v)} cells" if (isinstance(v, list) and v and isinstance(v[0], list)) else html.escape(repr(v))
        return f'<span class="tlit">{lab}</span>'
    if term["op"] == "input":
        return '<span class="tin">input</span>'
    kids = "".join(f"<li>{_term(a)}</li>" for a in term["args"])
    return f'<span class="top">{html.escape(term["op"])}</span><ul class="tree">{kids}</ul>'


def _resolved_term(term, res):
    if "var" in term:
        r = res.get(term["var"])
        if r and r["resolved"]:
            return f'<span class="rvar" title="{html.escape(r["desc"])}">{html.escape(r["desc"])}</span>'
        return f'<span class="ivar">{html.escape(term["var"])} · impasse</span>'
    if "lit" in term:
        v = term["lit"]
        lab = f"{len(v)} cells" if (isinstance(v, list) and v and isinstance(v[0], list)) else html.escape(repr(v))
        return f'<span class="tlit">{lab}</span>'
    if term["op"] == "input":
        return '<span class="tin">input</span>'
    kids = "".join(f"<li>{_resolved_term(a, res)}</li>" for a in term["args"])
    return f'<span class="top">{html.escape(term["op"])}</span><ul class="tree">{kids}</ul>'


def _val(v):
    if isinstance(v, dict) and "lit" in v:
        v = v["lit"]
    if isinstance(v, list) and v and isinstance(v[0], list):
        return f"[{len(v)} cells]"
    return html.escape(repr(v))


# --- 3열 ---------------------------------------------------------------------
def _materials(pairs):
    cards = []
    for i, p in enumerate(pairs):
        code = observed_program(p["input"], p["output"])
        term = lift(code)
        cards.append(f"""
        <div class="mat">
          <div class="mhead">pair {i}</div>
          <div class="mg">{_grid(p['input'])}<span class="ar">→</span>{_grid(p['output'])}</div>
          <pre class="src">{html.escape(code)}</pre>
          <div class="termbox">{_term(term)}</div>
        </div>""")
    return "".join(cards)


def _objpanel(pairs):
    """다객체 pair 면 object 속성을 보여 COMM/DIFF 선택 근거가 눈에 보이게."""
    rows, multi = [], False
    for i, p in enumerate(pairs):
        objs = fg_objects(p["input"], f"P{i}")
        if len(objs) > 1:
            multi = True
        chips = "".join(
            f'<span class="ochip" style="border-color:{PAL[o["color"] % 10]}">'
            f'c{o["color"]}·a{o["area"]}·{max(o["rows"]) - min(o["rows"]) + 1}×{max(o["cols"]) - min(o["cols"]) + 1}</span>'
            for o in objs)
        rows.append(f'<div class="orow">pair{i}: {chips}</div>')
    if not multi:
        return ""
    return ('<div class="objp"><div class="stitle">objects (색·area·hw) — 이 COMM/DIFF 로 선택 근거 도출:</div>'
            + "".join(rows) + "</div>")


def _process(schema, subst, resolutions, pairs):
    blocks = ['<div class="skhead">공통 골격 (COMM = 리터럴로 남음, '
              '<span class="tvar">?k</span> = DIFF 슬롯)</div>'
              f'<div class="termbox">{_term(schema)}</div>'
              + _objpanel(pairs)]
    if not subst:
        blocks.append('<div class="novar">변수 없음 — 모든 pair program 이 구조적으로 동일</div>')
    for v, vals in subst.items():
        r = resolutions[v]
        fillers = " ｜ ".join(f'p{i}: {_val(x)}' for i, x in enumerate(vals))
        tried = "".join(
            f'<div class="cand {"ok" if ok else "no"}">{"✓" if ok else "✗"} {html.escape(str(name))}</div>'
            for name, ok in r["tried"])
        verdict = (f'<div class="survivor">➜ {html.escape(r["desc"])}</div>' if r["resolved"]
                   else f'<div class="impasse">➜ {html.escape(r["desc"])}</div>')
        blocks.append(f"""
        <div class="varblock">
          <div class="vh"><span class="tvar">{html.escape(v)}</span> — 재료(per-pair 값): <span class="fill">{fillers}</span></div>
          <div class="search"><div class="stitle">object/pixel 비교 탐색 (largest·move 함수 없음):</div>{tried}{verdict}</div>
        </div>""")
    return "".join(blocks)


def _result(schema, resolutions, test_in, test_out, expected):
    ok = expected is not None and test_out == expected
    if test_out is None:
        run = ('<div class="glab">실행 결과</div><div class="impasse2">impasse — 변수 미해소로 '
               'test 실행 불가</div>')
    else:
        badge = '<span class="ok">✓ 정답과 일치</span>' if ok else '<span class="bad">✗ 불일치</span>'
        run = f'<div class="glab">실행 결과 {badge}</div>{_grid(test_out)}'
    return f"""
      <div class="rsh"><div class="rlab">해소된 스키마 (변수 → 비교로 도출한 근거)</div>
        <div class="termbox">{_resolved_term(schema, resolutions)}</div></div>
      <div class="trun">
        <div class="tstep"><div class="glab">test 입력</div>{_grid(test_in)}</div>
        <div class="ar2">─ 스키마 실행 ─▶</div>
        <div class="tstep">{run}</div>
        <div class="tstep"><div class="glab">정답(test 출력)</div>{_grid(expected)}</div>
      </div>"""


def _status(R, expected):
    if R["test_output"] is not None and R["test_output"] == expected:
        return ("✓", "sok", "test 통과")
    if R["test_output"] is not None:
        return ("✗", "sbad", "실행됐으나 불일치")
    return ("◑", "swarn", "impasse (부분/미해소)")


def _task(tid, name, path, show):
    disp = "block" if show else "none"
    try:
        task = json.load(open(path))
        pairs = task["train"]
        terms = [lift(observed_program(p["input"], p["output"])) for p in pairs]
        schema, subst = anti_unify(terms)
        test_in = task["test"][0]["input"]
        expected = task["test"][0].get("output")
        R = resolve_schema(schema, subst, pairs, test_in)
        st = _status(R, expected)
        body = f"""
      <div class="cols3">
        <div class="vcol"><div class="ch">① 재료 &nbsp;<small>pair program + AST(term)</small></div>{_materials(pairs)}</div>
        <div class="vcol"><div class="ch">② 과정 &nbsp;<small>anti-unify → 변수 → COMM/DIFF 비교로 해소</small></div>{_process(schema, subst, R['resolutions'], pairs)}</div>
        <div class="vcol"><div class="ch">③ 결과 &nbsp;<small>해소된 스키마 → test 실행</small></div>{_result(schema, R['resolutions'], test_in, R['test_output'], expected)}</div>
      </div>"""
    except Exception as e:                                    # noqa: BLE001
        st = ("!", "sbad", "예외")
        body = f'<div class="err">파이프라인 예외: {html.escape(type(e).__name__)}: {html.escape(str(e)[:200])}</div>'
    section = (f'<section class="task" id="{tid}" style="display:{disp}">'
               f'<h2>{html.escape(name)} <span class="np">{st[2]}</span></h2>{body}</section>')
    return section, st


CSS = """
*{box-sizing:border-box} body{margin:0;background:#0d1117;color:#c9d1d9;
  font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
header{padding:16px 24px;border-bottom:1px solid #21262d;background:#161b22}
h1{margin:0 0 6px;font-size:19px} header p{margin:0;color:#8b949e;max-width:1100px}
.selbar{position:sticky;top:0;z-index:9;background:#0d1117ee;backdrop-filter:blur(6px);
  border-bottom:1px solid #21262d;padding:10px 20px}
.selgrp{margin-bottom:7px} .selgrp:last-child{margin-bottom:0}
.gl{font-size:11px;color:#6e7681;margin-right:8px;display:inline-block;min-width:150px}
.tb{display:inline-block;font:11px ui-monospace,Consolas,monospace;color:#c9d1d9;
  background:#21262d;border:1px solid #30363d;border-radius:5px;padding:3px 8px;margin:2px;
  cursor:pointer} .tb:hover{border-color:#58a6ff} .tb.active{background:#1f6feb;border-color:#1f6feb}
.tb .g{font-weight:700;margin-right:4px}
.sok .g{color:#3fb950} .swarn .g{color:#f0883e} .sbad .g{color:#f85149}
.tb.active .g{color:#fff}
.task{padding:16px 22px;border-bottom:2px solid #21262d}
h2{font-size:16px;margin:0 0 12px;color:#e6edf3} .np{color:#6e7681;font-size:12px;font-weight:400}
.cols3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;align-items:start}
.vcol{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:11px 12px;min-width:0}
.ch{font-weight:700;color:#e6edf3;margin-bottom:9px;padding-bottom:6px;border-bottom:1px solid #21262d}
.ch small{color:#6e7681;font-weight:400;font-size:11px}
.grid{display:grid;gap:1px;background:#30363d;border:1px solid #30363d;border-radius:2px}
.grid i{display:block} .nogrid{color:#6e7681} .glab{font-size:10.5px;color:#8b949e;margin-bottom:3px}
.mat{border:1px solid #21262d;border-radius:6px;padding:8px;margin-bottom:9px;background:#0d1117}
.mhead{color:#58a6ff;font-weight:600;font-size:12px;margin-bottom:5px}
.mg{display:flex;align-items:center;gap:7px;margin-bottom:7px;flex-wrap:wrap} .ar{color:#6e7681}
.src{background:#010409;border:1px solid #21262d;border-radius:5px;padding:6px 8px;margin:0 0 6px;
  font:10.5px/1.5 ui-monospace,Consolas,monospace;color:#8b949e;white-space:pre-wrap;
  word-break:break-all;max-height:110px;overflow:auto}
.termbox{background:#010409;border:1px solid #21262d;border-radius:5px;padding:7px 9px;
  font:11.5px/1.4 ui-monospace,Consolas,monospace;overflow-x:auto}
.tree{list-style:none;margin:2px 0;padding-left:14px;border-left:1px dashed #30363d}
.top{color:#79c0ff;font-weight:600} .tin{color:#8b949e;font-style:italic} .tlit{color:#a5d6ff}
.tvar{color:#0d1117;background:#d29922;border-radius:4px;padding:0 5px;font-weight:700}
.skhead{font-size:11px;color:#8b949e;margin-bottom:6px}
.novar{color:#3fb950;font-family:ui-monospace,Consolas,monospace;margin-top:6px}
.varblock{border:1px solid #30363d;border-radius:6px;padding:8px 9px;margin-top:9px;background:#0d1117}
.vh{font-size:11.5px;margin-bottom:6px} .fill{color:#a5d6ff;font-family:ui-monospace,Consolas,monospace}
.search{border-top:1px dashed #30363d;padding-top:6px}
.stitle{font-size:10.5px;color:#6e7681;margin-bottom:4px}
.objp{border:1px solid #30363d;border-radius:6px;padding:7px 9px;margin-top:8px;background:#0d1117}
.orow{font:11px ui-monospace,Consolas,monospace;margin:2px 0;color:#8b949e}
.ochip{display:inline-block;border:1px solid;border-radius:4px;padding:0 5px;margin:1px 3px 1px 0;
  color:#c9d1d9;font-size:10.5px}
.sig{font-family:ui-monospace,Consolas,monospace;color:#a5d6ff;background:#0d1117;
  border:1px solid #21262d;border-radius:3px;padding:0 4px;font-size:10.5px}
.cand{font:11px ui-monospace,Consolas,monospace;padding:1px 0}
.cand.ok{color:#3fb950} .cand.no{color:#6e7681}
.survivor{margin-top:5px;color:#e3b341;font-weight:600;font-size:11.5px;
  background:#d2992218;border-radius:4px;padding:4px 7px}
.impasse{margin-top:5px;color:#f0883e;font-weight:600;font-size:11.5px;
  background:#f0883e18;border-radius:4px;padding:4px 7px}
.rsh{margin-bottom:10px} .rlab,.tstep .glab{font-size:11px;color:#8b949e;margin-bottom:5px}
.rvar{color:#0d1117;background:#3fb950;border-radius:4px;padding:0 5px;font-weight:600;font-size:11px}
.ivar{color:#0d1117;background:#f0883e;border-radius:4px;padding:0 5px;font-weight:600;font-size:11px}
.trun{display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap;border-top:1px solid #21262d;padding-top:10px}
.ar2{color:#6e7681;font-size:11px;padding-top:16px;white-space:nowrap}
.tstep .grid{outline:1px solid #30363d}
.impasse2{color:#f0883e;font-family:ui-monospace,Consolas,monospace;font-size:11px;
  border:1px dashed #f0883e55;border-radius:5px;padding:8px}
.err{color:#f0883e;font-family:ui-monospace,Consolas,monospace;padding:10px;
  border:1px dashed #f0883e55;border-radius:6px}
.ok{color:#3fb950;font-weight:700} .bad{color:#f85149;font-weight:700}
@media(max-width:1000px){.cols3{grid-template-columns:1fr}}
"""

JS = """
function showTask(id, btn){
  document.querySelectorAll('section.task').forEach(function(s){s.style.display='none';});
  var t=document.getElementById(id); if(t) t.style.display='block';
  document.querySelectorAll('.tb').forEach(function(b){b.classList.remove('active');});
  if(btn) btn.classList.add('active');
  window.scrollTo(0,0);
}
"""


def build():
    groups = _load_tasks()
    bands, sel = [], []
    idx = 0
    first_id = None
    for label, tasks in groups:
        btns = []
        for name, path in tasks:
            tid = f"t{idx}"
            idx += 1
            show = first_id is None
            if first_id is None:
                first_id = tid
            band, st = _task(tid, name, path, show)
            bands.append(band)
            active = " active" if show else ""
            btns.append(f'<span class="tb {st[1]}{active}" onclick="showTask(\'{tid}\',this)">'
                        f'<span class="g">{st[0]}</span>{html.escape(name)}</span>')
        sel.append(f'<div class="selgrp"><span class="gl">{html.escape(label)}</span>{"".join(btns)}</div>')
    intro = ("<b>재료</b>(각 pair 를 관측만으로 재구성한 program+AST) 를 <b>anti-unify</b> → 일치는 "
             "리터럴, 다른 자리만 <span class='tvar'>변수</span>(<b>과정</b>). 변수는 "
             "<b>largest·move 함수 없이</b> object 비교(greater 프로파일)·좌표식 탐색으로 해소하고 "
             "(§1-5·§4-2·§1-3), 해소된 스키마를 <b>test 입력에 실행</b>(<b>결과</b>). 위 토글로 문제 선택 · "
             "<span class='ok'>✓</span> 통과 · <span style='color:#f0883e'>◑</span> impasse · "
             "<span class='bad'>✗</span> 불일치.")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>program_term — 재료·과정·결과 (문제 토글)</title><style>{CSS}</style></head>
<body><header><h1>pair program → anti-unification → resolve → test 실행</h1><p>{intro}</p></header>
<div class="selbar">{"".join(sel)}</div>
{"".join(bands)}
<script>{JS}</script></body></html>"""


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "program_term_report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"wrote {out}  ({os.path.getsize(out) / 1024:.0f} KB)")
    print(f"open it:  {out}")
