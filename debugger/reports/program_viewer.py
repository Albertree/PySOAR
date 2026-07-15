# -*- coding: utf-8 -*-
"""program 뷰어 — easy000a~h(+i) 각 태스크의 PAIR.program(AST) + TASK.solution 을 한 페이지에서 확인
(스펙 §12 후속 서브프로젝트 ②). 우상단 "이 문제 anti-unification" 버튼의 교체 대상.

솔버(_Tracer+setup_focus_agent)를 실제로 돌려 WM 에 남은 값만 그대로 읽는다(재계산·재해석 없음).
각 태스크의 example(train) pair 마다 PAIR.program 을:

  ① text    — program_ast.to_source(ast) + render_header(ast, 그 pair 의 실제 input_grid)
  ② AST 트리 — 원본 typed-arg dict(JSON)을 그대로 nested 렌더 (leaf 값 재해석 없음)
  ③ 시각화  — grid(a/b) = 3-property setter box-flow(G0→set_grid_size∘set_grid_color∘set_grid_contents→G1),
              pixel/object(c–h) = coloring box-flow(easy_antiunify_viz 의 원자 box 헬퍼 재사용)

로 보여주고, 마지막에 TASK.solution(anti-unify 골격 — COMM=상수 유지·DIFF=slot 변수)을 같은 3-뷰로 보여준다.
program 이 없는 태스크(i: 격자 크기 변화 등 미해결)는 플레이스홀더만 표시.

program 문자열은 표시만 한다 — exec/eval 없음(program_ast.to_source/as_source 텍스트 그대로).

    python -m debugger.reports.program_viewer   # -> debugger/traces/program_report_all.html
"""
from __future__ import annotations

import html
import json
import os

from arbor.agent.focus import setup_focus_agent
from arbor.engine.trace import _Tracer
from arbor.env.dataset import list_tasks, load_task
from arbor.reasoning import program_ast as PA
from debugger.reports import easy_antiunify_viz as EV

# easy_a 9 태스크 전부 다룬다: a-h = 필수 범위(스펙 §12), i = 미해결(격자 크기 변화) 참고용 표식.
TIDS = [f"easy000{c}" for c in "abcdefghi"]


# ── display_source: 뷰어 로컬 통일 body (to_source[파싱계약]과 독립; 실 DSL·ARCKG accessor·실값) ──
def _disp_leaf(leaf):
    """color/index leaf → 소스 토큰. const=실값(json), var=이름, expr=식 그대로."""
    if "const" in leaf:
        return json.dumps(leaf["const"])
    if "var" in leaf:
        return str(leaf["var"])
    if "expr" in leaf:
        return str(leaf["expr"])
    return json.dumps(leaf)


def _disp_grid_leaf(leaf, prop):
    """grid-property leaf → 실행형 소스. keep→`prop(input_grid)`(ARCKG 투영), const=실값,
    expr=식 그대로(forward). prop ∈ {size,color,contents}."""
    if "keep" in leaf:
        return f"{prop}(input_grid)"                 # size/color/contents(input_grid)
    if "const" in leaf:
        return json.dumps(leaf["const"])             # size dict / color list / contents 2D 배열 실값
    if "expr" in leaf:
        return str(leaf["expr"])                     # (forward: H/W 어휘 번역은 별건)
    if "delta" in leaf:
        d = leaf["delta"]
        return f"delta(remove={d['remove']}, add={d['add']})"
    return json.dumps(leaf)


def _display_grid(body):
    parts = {s["call"]: s["args"] for s in body}
    sz = _disp_grid_leaf(parts["set_grid_size"]["size"], "size")
    co = _disp_grid_leaf(parts["set_grid_color"]["color"], "color")
    ct = _disp_grid_leaf(parts["set_grid_contents"]["contents"], "contents")
    return ("g = input_grid\n"
            f"g = set_grid_size(g, {sz})\n"
            f"g = set_grid_color(g, {co})\n"
            f"g = set_grid_contents(g, {ct})\n"
            "output_grid = g")


_ACCESSOR = {"pixel": "pixels_of", "object": "objects_of"}


def _display_pixel(body):
    lines = ["g = input_grid"]
    for s in body:
        tgt = s["args"]["target"]
        col = _disp_leaf(s["args"]["color"])
        ref = tgt.get("ref")
        if ref in _ACCESSOR:                          # pixel/object: 단일 좌표 채색
            idx = _disp_leaf(tgt["index"])
            lines.append(f"g = coloring(g, {_ACCESSOR[ref]}(input_grid)[{idx}].coord, {col})")
        elif ref == "cellset":                        # blob: 셀 집합 (a–h 밖 — 정직한 다중형)
            cl = tgt["cells"]
            cells = _disp_leaf(cl)
            lines.append(f"for ix in {cells}:\n    g = coloring(g, divmod(ix, width(input_grid)), {col})")
        else:
            lines.append(f"# 해석 불가 target: {json.dumps(tgt)}")
    lines.append("output_grid = g")
    return "\n".join(lines)


def display_source(ast):
    """AST → 통일 body 소스(뷰어 로컬). grid/pixel 계열 모두 실행형 'g = fn(g, …)'.
    to_source(파싱 계약) 와 독립 — 같은 AST 를 일관 프레이밍만(표현 계열은 그대로 드러남)."""
    body = (ast or {}).get("body") or []
    if not body:
        return "g = input_grid\noutput_grid = g"
    if PA._is_grid_body(body):
        return _display_grid(body)
    return _display_pixel(body)


def _runner_payload(tid, asts, task):
    """각 example program → 러너용 {tid, pair, body, input, expected}.
    expected = 실제 program_ast.execute(ast, input) (JS 미러 대조 기준 = 정직성 가드)."""
    items = []
    for k, ast in enumerate(asts):
        ex = task["train"][k]
        items.append({
            "tid": tid, "pair": k,
            "body": display_source(ast),
            "input": ex["input"],
            "expected": PA.execute(ast, ex["input"]),
        })
    return items


# ── Step 1: 수집 — 솔버 1 회 실행해 example PAIR.program(AST) 전부 + TASK.solution 을 WM 실측값으로 ──
def _collect(tid, task):
    """(pair_asts, solution_ast, attempts) 반환. program/solution 없으면 각각 [] / None(정직하게 미해결)."""
    try:
        tr = _Tracer(task, tid, setup=setup_focus_agent)
        tr.run(max_cycles=6000)                       # PIXEL 하강은 픽셀 개별관측으로 cycle 이 큼
    except Exception:                                 # noqa: BLE001 — 리포트 생성용, 한 태스크 예외가 전체를 죽이지 않게
        return [], None, []
    T = f"T{tid}"
    asts = []
    for k in range(len(task["train"])):
        v = next((v for (i, a, v) in tr.ag.wm if i == f"{T}.P{k}.property" and a == "program"), None)
        if v in (None, "{}"):
            continue
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
    sol_v = next((v for (i, a, v) in tr.ag.wm if i == f"{T}.property" and a == "solution"), None)
    solution = None
    if sol_v not in (None, "{}"):
        try:
            sol = json.loads(sol_v)
        except (ValueError, TypeError):
            sol = None
        if sol and sol.get("body"):
            solution = sol
    return asts, solution, tr.attempts


# ── Step 2a: ② AST 트리 — 원본 dict/list(JSON) 를 그대로 nested 렌더 ──────────────────────────
def _is_matrix(v):
    """grid 리터럴(정수 2차원 리스트) 판별 — 이 경우만 셀 하나하나를 <li> 로 안 풀고 컴팩트 행렬로."""
    return isinstance(v, list) and bool(v) and all(
        isinstance(row, list) and all(isinstance(x, int) for x in row) for row in v)


def ast_tree(node):
    if isinstance(node, dict):
        rows = "".join(f'<li><span class="k">{html.escape(str(k))}</span>{ast_tree(v)}</li>'
                        for k, v in node.items())
        return f'<ul class="astree">{rows}</ul>'
    if _is_matrix(node):
        mat = "\n".join(" ".join(str(x) for x in row) for row in node)
        return f'<pre class="astmat">{html.escape(mat)}</pre>'
    if isinstance(node, list):
        if not node:
            return '<span class="leaf">[]</span>'
        rows = "".join(f'<li>{ast_tree(v)}</li>' for v in node)
        return f'<ul class="astree astlist">{rows}</ul>'
    return f'<span class="leaf">{html.escape(json.dumps(node))}</span>'


# ── Step 2b: ③ 시각화 — grid=3-property box-flow / pixel·object=coloring flow(easy_antiunify_viz 재사용) ──
def _is_grid_literal(v):
    return isinstance(v, list) and bool(v) and isinstance(v[0], list)


def _grid_leaf_repr(leaf, prop=""):
    """grid-arg leaf → 시각화 박스 라벨(정직화). keep→`prop(input_grid)`, contents const→실 2D 배열."""
    if "keep" in leaf:
        return f"{leaf['keep']}(input_grid)"          # size/color/contents(input_grid)
    if "delta" in leaf:
        d = leaf["delta"]
        return f"-{d['remove']}+{d['add']}"
    if "var" in leaf:
        return str(leaf["var"])
    if "expr" in leaf:
        return str(leaf["expr"])
    if "const" in leaf:
        v = leaf["const"]
        if isinstance(v, dict) and "height" in v:
            return f"{{height:{v['height']}, width:{v['width']}}}"
        return json.dumps(v)                          # color list / contents 2D 배열 실값(grid[NxN] 폐기)
    return str(leaf)


def _swatches(colors):
    return "".join(f'<i class="swatch" style="background:{EV.PAL[c % 10]}"></i>' for c in colors)


def _endpoint_rows(ex):
    """공통 끝점: (G0 행, G1 행) — input/output 썸네일 인라인."""
    g0 = (f'<div class="row"><span class="bx grid">G0 = input_grid</span>{EV.grid(ex["input"])}'
          f'</div><div class="v"></div>')
    g1 = f'<div class="row"><span class="bx grid">G1 = output_grid</span>{EV.grid(ex["output"])}</div>'
    return g0, g1


def _grid_step_rows(ast):
    parts = {s["call"]: s["args"] for s in ast["body"]}
    sz, co, ct = (parts["set_grid_size"]["size"], parts["set_grid_color"]["color"],
                  parts["set_grid_contents"]["contents"])
    color_sw = (_swatches(co["const"]) if isinstance(co.get("const"), list)
                and not _is_grid_literal(co["const"]) else "")
    return [
        f'<div class="row">{EV.opb("set_grid_size")}<span class="h"></span>{EV.colr(_grid_leaf_repr(sz, "size"))}</div><div class="v"></div>',
        f'<div class="row">{EV.opb("set_grid_color")}<span class="h"></span>{EV.colr(_grid_leaf_repr(co, "color"))}{color_sw}</div><div class="v"></div>',
        f'<div class="row">{EV.opb("set_grid_contents")}<span class="h"></span>{EV.colr(_grid_leaf_repr(ct, "contents"))}</div><div class="v"></div>',
    ]


def _pixel_step_rows(ast):
    rows = []
    for s in ast["body"]:
        tgt = s["args"]["target"]
        ref = tgt.get("ref")
        col_leaf = s["args"]["color"]
        col = col_leaf.get("const")
        sw = _swatches([col]) if isinstance(col, int) else ""
        if ref in _ACCESSOR:
            idx = _disp_leaf(tgt["index"])
            label = f"{_ACCESSOR[ref]}(input_grid)[{idx}].coord"
        elif ref == "cellset":
            label = f"cells {_disp_leaf(tgt['cells'])}"
        else:
            label = "?"
        rows.append(f'<div class="row">{EV.opb("coloring")}<span class="h"></span>'
                    f'{EV.dest_box(label)}<span class="h"></span>{EV.colr(_disp_leaf(col_leaf))}{sw}</div>'
                    f'<div class="v"></div>')
    return rows


def _viz(ast, ex):
    """두 계열 공통 box-flow: G0 썸네일 → 스텝들 → G1 썸네일."""
    g0, g1 = _endpoint_rows(ex)
    steps = _grid_step_rows(ast) if PA._is_grid_body(ast.get("body") or []) else _pixel_step_rows(ast)
    return f'<div class="flow">{g0}{"".join(steps)}{g1}</div>'


# program_ast.render_header 는 pixel/object body(step.args.target.ref)만 가정 — grid(3-property)
# body 는 target 이 없어(set_grid_* 는 size/color/contents 인자) KeyError('target'). program_ast.py
# 는 solver 쪽 파일이라 수정하지 않고(하네스: 표시 전용, arbor/reasoning/* read-only), 여기서만
# grid body 를 위한 동등한 헤더를 만든다(같은 포맷: 쓰인 DSL 시그니처 + 이 pair 의 input_grid).
def _render_header_safe(ast, g0):
    body = ast.get("body") or []
    if not PA._is_grid_body(body):
        return PA.render_header(ast, g0)
    ops = [s["call"] for s in body]
    lines = ["# --- DSL (used) ---"]
    lines += [PA._sig(n) for n in ops]
    lines += ["# --- input (this pair) ---", f"input_grid = {json.dumps(g0)}"]
    return "\n".join(lines)


# ── 3-뷰 한 pair(또는 TASK.solution) 블록 ────────────────────────────────────────────────────
def _pair_block(label, ast, ex):
    g0 = ex["input"]
    return (f'<div class="pair">'
            f'<div class="lab">{html.escape(str(label))}</div>'
            f'<div class="views">'
            f'<div class="view"><div class="vt">① text (통일 body · 실행형)</div>'
            f'<pre class="hdr">{html.escape(_render_header_safe(ast, g0))}</pre>'
            f'<pre class="src">{html.escape(display_source(ast))}</pre>'
            f'<details class="rawsrc"><summary>canonical to_source (파싱계약·참조용)</summary>'
            f'<pre class="src">{html.escape(PA.to_source(ast))}</pre></details></div>'
            f'<div class="view"><div class="vt">② AST 트리</div>{ast_tree(ast)}</div>'
            f'<div class="view"><div class="vt">③ 시각화</div>{_viz(ast, ex)}</div>'
            f'</div></div>')


def task_section(tid, task, precomputed=None):
    thumbs = "".join(EV.grid(ex["input"]) + EV.grid(ex["output"]) for ex in task["train"])
    tp = task["test"][0]
    thumbs += EV.grid(tp["input"]) + (EV.grid(tp["output"]) if tp.get("output") else "")

    asts, solution, attempts = precomputed if precomputed else _collect(tid, task)
    if not asts:
        same = all(len(e["input"]) == len(e["output"]) and len(e["input"][0]) == len(e["output"][0])
                   for e in task["train"])
        solved = bool(attempts) and any(a["correct"] for a in attempts)
        why = ("" if same else
               "example pair 간 격자 크기 변화(resize) — pixel/object coloring 은 입력과 같은 크기만"
               " 재칠하고, grid 3-property 도 이 크기변화 케이스는 아직 다루지 않는다. ")
        done = ("실제로는 풀렸다(아래 real attempts 참고) — 다만 그 결론이 이 program 스키마로"
                " 물질화되지 않았다." if solved else
                "solve 가 이 태스크의 example PAIR program 을 다 채우지 못했다 — 표시할 실제 AST 없음"
                "(정직하게 미해결로 남김).")
        extra = EV._attempts_block(attempts, tp) if attempts else ""
        return (f'<section class="task" id="{tid}"><h2>{tid}<span class="na">미합성/크기변화</span></h2>'
                f'<div class="thumbs">{thumbs}</div><p class="note">{html.escape(why + done)}</p>{extra}</section>')

    kind = ("3-property grid program (set_grid_size∘set_grid_color∘set_grid_contents)"
            if PA._is_grid_body(asts[0]["body"]) else "pixel/object coloring program")
    pairs_html = "".join(_pair_block(f"PAIR {k + 1}", a, ex)
                          for k, (a, ex) in enumerate(zip(asts, task["train"])))
    if solution is not None:
        sol_html = f'<div class="solblock">{_pair_block("TASK.solution (anti-unify 골격)", solution, task["train"][0])}</div>'
    else:
        sol_html = '<p class="note">TASK.solution 미물질화(generalize 미도달) — per-pair program 만 표시.</p>'

    return (f'<section class="task" id="{tid}"><h2>{tid}<span class="tag2">{html.escape(kind)}</span></h2>'
            f'<div class="thumbs">{thumbs}</div>{pairs_html}{sol_html}{EV._attempts_block(attempts, tp)}</section>')


CSS = """
.views{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin:6px 0 14px}
.view{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;flex:1 1 300px;min-width:240px}
.vt{font-size:11px;color:#8b93a3;text-transform:uppercase;letter-spacing:.03em;margin-bottom:8px;font-weight:700}
.src{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:8px 10px;
 font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#dfe3ea;white-space:pre-wrap;
 overflow-wrap:anywhere;margin:0}
.astree{list-style:none;margin:0;padding-left:14px;font:11.5px/1.6 ui-monospace,monospace}
.view>.astree{padding-left:0}
.astree li{border-left:1px dashed #2a3038;padding-left:10px;margin:2px 0}
.k{color:#7fb2e0;margin-right:6px}
.leaf{color:#e6c99a}
.astmat{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 8px;margin:2px 0 2px 14px;
 font:11px/1.4 ui-monospace,monospace;color:#e6c99a}
.swatch{display:inline-block;width:10px;height:10px;margin-left:2px;border-radius:2px;vertical-align:middle;
 border:1px solid rgba(255,255,255,.25)}
.pair{padding-top:0;margin-top:0}
.pair + .pair{border-top:1px solid #232b36;padding-top:12px;margin-top:12px}
.solblock{border:1px solid #3a5a7a;border-radius:10px;padding:2px 12px 12px;margin-top:16px;background:#131a22}
"""

_RUNNER_HTML = ""   # Task 6 에서 코드 실행기 패널로 채움


def build():
    tabs = "".join(f'<a href="#{t}" data-t="{t}">{t[-1].upper()}</a>' for t in TIDS)
    paths = dict(list_tasks("easy_a"))
    tasks = {t: load_task(paths[t]) for t in TIDS}
    runner_data = []
    secs_list = []
    for t in TIDS:
        asts, solution, attempts = _collect(t, tasks[t])
        runner_data.extend(_runner_payload(t, asts, tasks[t]))
        secs_list.append(task_section(t, tasks[t], precomputed=(asts, solution, attempts)))
    secs = "".join(secs_list)
    js = ("<script>var TIDS=%s;function sh(){var h=location.hash.slice(1);"
          "if(!document.getElementById(h))h=TIDS[0];"
          "document.querySelectorAll('section.task').forEach(function(s){s.style.display=(s.id===h)?'':'none'});"
          "document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.t===h)});}"
          "addEventListener('hashchange',sh);sh();</script>") % json.dumps(TIDS)
    doc = (f'<!doctype html><meta charset="utf-8"><title>program 뷰어</title><style>{EV.CSS}{CSS}</style>'
           f'<a class="back" href="focus_dashboard.html">← focus_dashboard</a>'
           f'<h1>easy a–h program 뷰어</h1>'
           f'<p class="hs">solve 실행 → WM 의 PAIR.program 을 통일 body(실행형)·단일 box-flow 로 렌더.'
           f' 하단 코드 실행기에서 body 를 실행/검증(빌드타임 parity ✓/✗).</p>'
           f'<div class="tabs">{tabs}</div>{secs}'
           f'<script>var RUNNER_DATA={json.dumps(runner_data)};</script>'
           f'{_RUNNER_HTML}{js}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "program_report_all.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p) / 1024:.0f} KB)")
