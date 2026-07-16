# -*- coding: utf-8 -*-
"""program 뷰어 — easy000a~h(+i) 각 태스크의 PAIR.program(AST) + TASK.solution 을 한 페이지에서 확인
(스펙 §12 후속 서브프로젝트 ②). 우상단 "이 문제 anti-unification" 버튼의 교체 대상.

솔버(_Tracer+setup_focus_agent)를 실제로 돌려 WM 에 남은 값만 그대로 읽는다(재계산·재해석 없음).
각 태스크의 example(train) pair 마다 PAIR.program 을:

  ① text    — display_source(ast)(뷰어 로컬 통일 실행형 body) + render_header(ast, 그 pair 의 실제
              input_grid); canonical program_ast.to_source(ast)(파싱 계약 원본)는 접힌 <details> 로 참조용 병기
  ② AST 트리 — 원본 typed-arg dict(JSON)을 그대로 nested 렌더 (leaf 값 재해석 없음)
  ③ 시각화  — grid(a/b) = 3-property setter box-flow(G0→set_grid_size∘set_grid_color∘set_grid_contents→G1),
              pixel/object(c–h) = coloring box-flow(easy_antiunify_viz 의 원자 box 헬퍼 재사용)

로 보여주고, 마지막에 TASK.solution(anti-unify 골격 — COMM=상수 유지·DIFF=slot 변수)을 같은 3-뷰로 보여준다.
program 이 없는 태스크(i: 격자 크기 변화 등 미해결)는 플레이스홀더만 표시.

Python 빌드 쪽은 표시만 한다 — eval/exec 없음(program_ast.to_source/display_source 텍스트 그대로,
RUNNER_DATA 는 build 시점에 미리 계산한 값을 JSON 으로 굽는다). 다만 페이지 하단에는 순수 프런트엔드
코드 실행기가 있다 — body 를 JS atom 미러(ATOM, new Function 기반 안전 평가)로 브라우저에서 직접
실행하고, 그 결과를 build 시점에 구운 program_ast.execute 결과와 대조해 parity ✓/✗ 배지로 보여준다
(JS↔Python 드리프트 감시 — §7 honesty 가드).

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
    if "var" in leaf:
        return str(leaf["var"])                       # TASK.solution slot (pair 간 값이 다른 grid property)
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


def _runner_payload(tid, asts, pairs, task):
    """각 example program → 러너용 {tid, pair, body, input, expected}.
    expected = 실제 program_ast.execute(ast, input) (JS 미러 대조 기준 = 정직성 가드).
    pairs[k] = asts[k] 가 실제로 속한 train index(중간 pair 누락 시 리스트 위치 ≠ train index 이므로
    반드시 carry 된 실 index 로 짝짓는다 — T5 index-carry 가드)."""
    items = []
    for ast, p in zip(asts, pairs):
        ex = task["train"][p]
        items.append({
            "tid": tid, "pair": p,
            "body": display_source(ast),
            "input": ex["input"],
            "expected": PA.execute(ast, ex["input"]),
        })
    return items


# ── Step 1: 수집 — 솔버 1 회 실행해 example PAIR.program(AST) 전부 + TASK.solution 을 WM 실측값으로 ──
def _collect(tid, task):
    """(pair_asts, pair_indices, solution_ast, attempts) 반환.
    program/solution 없으면 각각 [] / None(정직하게 미해결).
    pair_indices[k] = asts[k] 가 실제로 속한 train index — 중간 pair 에 program 이 없으면
    asts 의 리스트 위치가 train index 와 어긋나므로, 그 실제 index 를 나란히 carry 한다
    (T5 index-carry 가드 — false-green 방지: 다른 pair 의 input 과 program 이 잘못 짝지어지는 것 방지)."""
    try:
        tr = _Tracer(task, tid, setup=setup_focus_agent)
        tr.run(max_cycles=6000)                       # PIXEL 하강은 픽셀 개별관측으로 cycle 이 큼
    except Exception:                                 # noqa: BLE001 — 리포트 생성용, 한 태스크 예외가 전체를 죽이지 않게
        return [], [], None, []
    T = f"T{tid}"
    asts = []
    pairs = []
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
            pairs.append(k)
    sol_v = next((v for (i, a, v) in tr.ag.wm if i == f"{T}.property" and a == "solution"), None)
    solution = None
    if sol_v not in (None, "{}"):
        try:
            sol = json.loads(sol_v)
        except (ValueError, TypeError):
            sol = None
        if sol and sol.get("body"):
            solution = sol
    return asts, pairs, solution, tr.attempts


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
        return f"{prop or leaf['keep']}(input_grid)"  # size/color/contents(input_grid)
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


def _contents_cell(leaf):
    """set_grid_contents leaf → 시각화 셀. const 2D 배열이면 줄바꿈 matrix(<pre>), 아니면 콤팩트 라벨."""
    if "const" in leaf and _is_grid_literal(leaf["const"]):
        mat = "\n".join(" ".join(str(x) for x in row) for row in leaf["const"])
        return f'<pre class="cmat">{html.escape(mat)}</pre>'
    return EV.colr(_grid_leaf_repr(leaf, "contents"))


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
        f'<div class="row">{EV.opb("set_grid_contents")}<span class="h"></span>{_contents_cell(ct)}</div><div class="v"></div>',
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
            f'<div class="view"><div class="vt">② AST 트리</div>'
            + ('<div class="astnote">grid 스텝은 첫 인자 grid(<code>g</code>)를 파이프라인으로 암묵 전달 — '
               'AST 엔 property arg 만. leaf <code>{"expr":"size(input_grid)"}</code>=ARCKG 식, '
               '<code>{"const":…}</code>=고정값.</div>' if PA._is_grid_body(ast.get("body") or []) else '')
            + f'{ast_tree(ast)}</div>'
            f'<div class="view"><div class="vt">③ 시각화</div>{_viz(ast, ex)}</div>'
            f'</div></div>')


def task_section(tid, task, precomputed=None):
    thumbs = "".join(EV.grid(ex["input"]) + EV.grid(ex["output"]) for ex in task["train"])
    tp = task["test"][0]
    thumbs += EV.grid(tp["input"]) + (EV.grid(tp["output"]) if tp.get("output") else "")

    asts, pairs, solution, attempts = precomputed if precomputed else _collect(tid, task)
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
    ast_ex_pairs = [(a, task["train"][p], p) for a, p in zip(asts, pairs)]
    pairs_html = "".join(_pair_block(f"PAIR {p + 1}", a, ex) for a, ex, p in ast_ex_pairs)
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
.cmat{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 9px;margin:0;
 font:11px/1.35 ui-monospace,monospace;color:#e6c99a;white-space:pre}
.astnote{font-size:10px;color:#8b93a3;background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 8px;margin-bottom:8px;line-height:1.5}
.astnote code{color:#7fb2e0}
.swatch{display:inline-block;width:10px;height:10px;margin-left:2px;border-radius:2px;vertical-align:middle;
 border:1px solid rgba(255,255,255,.25)}
.pair{padding-top:0;margin-top:0}
.pair + .pair{border-top:1px solid #232b36;padding-top:12px;margin-top:12px}
.solblock{border:1px solid #3a5a7a;border-radius:10px;padding:2px 12px 12px;margin-top:16px;background:#131a22}
"""

CSS += """
#runner{background:#1a1d24;border:1px solid #262b34;border-radius:10px;padding:16px 18px;margin:18px 0}
.runwrap{display:flex;flex-direction:column;gap:8px;margin-top:8px}
#rsel{background:#0f1218;color:#dfe3ea;border:1px solid #2a3038;border-radius:6px;padding:4px 8px}
#rrun{background:#243b52;color:#bcd8f5;border:1px solid #3a5a7a;border-radius:6px;padding:4px 12px;cursor:pointer;width:max-content}
#rcode{background:#0d1014;color:#dfe3ea;border:1px solid #232a35;border-radius:6px;padding:8px 10px;
 font:11.5px/1.5 ui-monospace,monospace;min-height:120px;white-space:pre;overflow:auto}
.rout{display:flex;gap:18px;margin-top:6px}.rlab{font-size:10px;color:#8b93a3;margin-bottom:4px}
.rbadge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px}
.rok{background:#12281c;color:#a9e6c1;border:1px solid #2f5a41}
.rno{background:#241417;color:#e0a3a4;border:1px solid #5a2f34}
.rerr{color:#e0a3a4;font:11px/1.4 ui-monospace,monospace;white-space:pre-wrap}
.rawsrc summary{color:#7a8698;font-size:10px;cursor:pointer;margin-top:6px}
.rgridbox{display:inline-grid;gap:1px;background:#2a2e38;border:1px solid #3a4150;padding:1px;width:max-content}
.rgridbox i{width:20px;height:20px;display:block}
.rout{align-items:flex-start}.rlab{font-weight:700}
"""

_RUNNER_HTML = r"""
<section id="runner"><h2>코드 실행기 <span class="tag2">순수 프런트엔드 · frozen atom JS 미러</span></h2>
<p class="hs">아래 body 를 실행(공통 ARCKG atom 은 러너에 로드). 결과를 빌드타임 expected(=실제
program_ast.execute)와 대조 — JS↔Python 드리프트가 ✓/✗ 로 드러남.</p>
<div class="runwrap">
  <select id="rsel"></select>
  <button id="rrun">▶ Run</button>
  <span id="rbadge" class="rbadge"></span>
  <textarea id="rcode" spellcheck="false"></textarea>
  <div class="rout"><div><div class="rlab">출력(JS 실행)</div><div id="rgrid"></div></div>
    <div><div class="rlab">expected(Python execute)</div><div id="regrid"></div></div></div>
  <div id="rerr" class="rerr"></div>
</div></section>
<script>
// ── frozen atom JS 미러 (program_ast/transformation DSL 의 직역; parity 로 드리프트 감시) ──
function _clone(g){return g.map(function(r){return r.slice();});}
function W(g){return g[0].length;} function H(g){return g.length;}
var ATOM = {
  input_grid: null,
  make_grid: function(size){var o=[];for(var r=0;r<size.height;r++){var row=[];for(var c=0;c<size.width;c++)row.push(0);o.push(row);}return o;},
  coloring: function(g,pos,color){var o=_clone(g);o[pos[0]][pos[1]]=color;return o;},
  set_grid_size: function(g,size){return ATOM.make_grid(size);},
  set_grid_color: function(g,color){return g;},
  set_grid_contents: function(g,contents){return contents==null?g:contents.map(function(r){return r.slice();});},
  size: function(g){return {height:H(g),width:W(g)};},
  height: function(g){return H(g);}, width: function(g){return W(g);},
  color: function(g){var s={};for(var r=0;r<H(g);r++)for(var c=0;c<W(g);c++)s[g[r][c]]=true;return s;},
  contents: function(g){return _clone(g);},
  objects_of: function(g){throw new Error("objects_of: 러너 미지원(pixel/ grid 만)");},
  pixels_of: function(g){var w=W(g),out=[];for(var i=0;i<H(g)*w;i++){out.push({coord:[Math.floor(i/w),i%w]});}return out;},
  divmod: function(a,b){return [Math.floor(a/b),a%b];}
};
// body 실행: display_source 문법('g = fn(g,…)' 순차, for-loop 1종)만 해석. 미지원 구문 → 예외.
function runBody(code, input){
  ATOM.input_grid = input; var g = input;
  var lines = code.split("\n"); var i=0;
  function evalExpr(e){
    // 안전 평가: ATOM/g/input_grid/숫자/배열/객체 리터럴만. new Function 은 로컬 스코프에 바인딩.
    return (new Function("ATOM","g","input_grid","divmod",
      "with(ATOM){return ("+e+");}"))(ATOM,g,ATOM.input_grid,ATOM.divmod);
  }
  for(i=0;i<lines.length;i++){
    var ln = lines[i].trim();
    if(!ln || ln[0]==="#") continue;
    var mFor = ln.match(/^for\s+(\w+)\s+in\s+(.+):$/);
    if(mFor){
      var it = evalExpr(mFor[2]); var body = lines[i+1].trim();
      var mb = body.match(/^g\s*=\s*(.+)$/); i++;
      for(var k=0;k<it.length;k++){ (function(ix){ ATOM[mFor[1]]=ix; })(it[k]);
        // 루프 변수는 ATOM 에 잠깐 얹어 with 로 참조
        g = (new Function("ATOM","g","input_grid","divmod","with(ATOM){return ("+mb[1]+");}"))(ATOM,g,ATOM.input_grid,ATOM.divmod);
      }
      continue;
    }
    var m = ln.match(/^(\w+)\s*=\s*(.+)$/);
    if(!m) throw new Error("해석 불가: "+ln);
    var val = evalExpr(m[2]);
    if(m[1]==="g"||m[1]==="output_grid") g=val; else ATOM[m[1]]=val;
  }
  return g;
}
function gridHTML(g){ if(!g||!g.length) return '<span class="rerr">–</span>';
  var w=g[0].length, cells=g.map(function(r){return r.map(function(v){
    return '<i style="background:'+PAL_JS[((v%10)+10)%10]+'"></i>';}).join("");}).join("");
  return '<div class="rgridbox" style="grid-template-columns:repeat('+w+',20px)">'+cells+'</div>';
}
var PAL_JS=["#101010","#1E93FF","#F93C31","#4FCC30","#FFDC00","#999999","#E53AA3","#FF851B","#87D8F1","#921231"];
function eqGrid(a,b){return JSON.stringify(a)===JSON.stringify(b);}
(function(){
  var sel=document.getElementById("rsel");
  RUNNER_DATA.forEach(function(d,i){var o=document.createElement("option");
    o.value=i; o.text=d.tid+" · pair "+(d.pair+1); sel.appendChild(o);});
  function load(){var d=RUNNER_DATA[sel.value]; document.getElementById("rcode").value=d.body;
    document.getElementById("regrid").innerHTML=gridHTML(d.expected); run();}   // load 후 즉시 실행
  function run(){var d=RUNNER_DATA[sel.value]; var err=document.getElementById("rerr");
    var badge=document.getElementById("rbadge"); err.textContent="";
    try{ var out=runBody(document.getElementById("rcode").value, d.input);
      document.getElementById("rgrid").innerHTML=gridHTML(out);
      document.getElementById("regrid").innerHTML=gridHTML(d.expected);
      var ok=eqGrid(out,d.expected); badge.textContent=ok?"✓ parity":"✗ 불일치";
      badge.className="rbadge "+(ok?"rok":"rno");
    }catch(e){ document.getElementById("rgrid").innerHTML='<span class="rerr">실행 불가</span>';  // stale 제거
      err.textContent=String(e.message||e); badge.textContent="✗ 실행오류"; badge.className="rbadge rno"; }}
  var _t; document.getElementById("rcode").oninput=function(){clearTimeout(_t);_t=setTimeout(run,250);}; // 편집즉시(debounce)
  sel.onchange=load; document.getElementById("rrun").onclick=run;
  if(RUNNER_DATA.length){ load(); }
})();
</script>
"""


def build():
    tabs = "".join(f'<a href="#{t}" data-t="{t}">{t[-1].upper()}</a>' for t in TIDS)
    paths = dict(list_tasks("easy_a"))
    tasks = {t: load_task(paths[t]) for t in TIDS}
    runner_data = []
    secs_list = []
    for t in TIDS:
        asts, pairs, solution, attempts = _collect(t, tasks[t])
        runner_data.extend(_runner_payload(t, asts, pairs, tasks[t]))
        secs_list.append(task_section(t, tasks[t], precomputed=(asts, pairs, solution, attempts)))
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
