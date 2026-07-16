# -*- coding: utf-8 -*-
"""program 뷰어 — easy000a~h(+i) 각 태스크의 PAIR.program(AST) + TASK.solution 을 한 페이지에서 확인
(스펙 §12 후속 서브프로젝트 ②). 우상단 "이 문제 anti-unification" 버튼의 교체 대상.

솔버(_Tracer+setup_focus_agent)를 실제로 돌려 WM 에 남은 값만 그대로 읽는다(재계산·재해석 없음).
각 태스크의 example(train) pair 마다 PAIR.program 을:

  ① text    — display_source(ast)(뷰어 로컬 통일 실행형 body) + _render_header_safe(ast, 그 pair 의
              실제 input_grid; body 가 실제 쓰는 호출 형태와 시그니처를 맞춘 헤더)
  ② AST 트리 — 원본 typed-arg dict(JSON)을 그대로 nested 렌더 (leaf 값 재해석 없음)
  ③ 시각화  — grid(3-property) = input_grid→set_grid_size∘set_grid_color∘set_grid_contents→output_grid
              box-flow(easy_antiunify_viz 의 원자 box 헬퍼 재사용), pixel/object(c–h) = coloring box-flow

로 보여주고, 마지막엔 TASK.solution(anti-unify 골격 — COMM=상수 유지·DIFF=slot 변수)을 pair0/pair1
program(세로 stack) → 그 둘의 ③ overlay(반투명 겹침) → TASK.solution 순의 가로 레이아웃으로 보여준다.
program 이 없는 태스크(i: 격자 크기 변화 등 미해결)는 플레이스홀더만 표시.

Python 빌드 쪽은 표시만 한다 — eval/exec 없음(program_ast.to_source/display_source 텍스트 그대로,
RUNNER_DATA 는 build 시점에 미리 계산한 값을 JSON 으로 굽는다). 다만 페이지 하단에는 순수 프런트엔드
코드 실행기가 있다 — body 를 JS atom 미러(ATOM, new Function 기반 안전 평가)로 브라우저에서 직접
실행하고, 그 결과를 build 시점에 구운 program_ast.execute 결과와 대조해 parity ✓/✗ 배지로 보여준다
(JS↔Python 드리프트 감시 — §7 honesty 가드).

── ①②③ 공통소스 원칙(2026-07-16 정리 — 이 파일을 고칠 때 반드시 지킬 것) ──────────────────
① text(display_source) · ② AST 트리(ast_tree) · ③ 시각화(_viz)는 서로 다른 산출물이 아니라
"같은 AST"의 세 표현이다. 유일한 물질은 AST 그 자체 — ①은 그 AST 의 canonical 코드 텍스트
(진짜 실행형 body, 줄 단위 statement), ②는 그 AST 를 재해석 없이 그대로 펼친 원본 트리,
③은 ①과 "같은 statement 시퀀스"를 박스로 그린 것이다. 예: set_grid_contents 의 coloring 합성을
①이 g0 = g.contents; g1 = coloring(g0,…); …; result = gN 순차 대입으로 풀어 쓰면, ③도 같은 개수·
같은 순서·같은 g_i 이름의 노드로 그린다 — 이 매핑을 손으로 두 번(①에 한 번, ③에 한 번) 구현하지
않고, _coloring_steps() 하나가 그 공통 재료(어느 target/accessor/color 인지)를 뽑아내면 ①(텍스트
포매팅)과 ③(박스 포매팅)은 그 결과를 포맷만 다르게 소비한다 — 그래야 ①③ 이 구조적으로 드리프트할
수 없다. 새 표현 계열을 추가하거나 표시 방식을 고칠 때도 이 원칙(추출은 한 곳, 포맷팅만 갈래)을
유지할 것 — ①②를 보고 ③을 손으로 새로 그리거나, 그 반대로 하지 말 것.

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
    """grid-property leaf → 실행형 소스. const=실값,
    expr=식 그대로(forward). prop ∈ {size,color,contents}. (leaf 가 `program`(coloring 합성)인
    경우는 _display_grid 가 _coloring_seq_lines 로 별도 처리 — 여기로는 들어오지 않는다.)"""
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


def _coloring_steps(body):
    """set_grid_contents 의 contents leaf 가 `program`(하강 coloring 합성, c–h)일 때의 순차 스텝
    재료 — ①(_coloring_seq_lines, 텍스트) 과 ③(_coloring_flow_rows, 시각화)가 이 SAME 리스트를
    소비한다(모듈 docstring §①②③ 공통소스 원칙). 각 스텝 = {g_from, g_to, ref, label, color}.
    label 은 두 표현 모두에서 문자 그대로 재사용되는 target 텍스트(accessor 식 또는 cellset)."""
    steps = []
    prev = "g0"
    for j, s in enumerate(body, start=1):
        tgt = s["args"]["target"]
        ref = tgt.get("ref")
        cur = f"g{j}"
        if ref in _ACCESSOR:
            idx = _disp_leaf(tgt["index"])
            label = f"{_ACCESSOR[ref]}(input_grid)[{idx}].coord"
        elif ref == "cellset":                        # a-h 밖(정직 표기 — 러너 미지원, coloring 은 단일좌표만)
            label = f"cellset={_disp_leaf(tgt['cells'])}"
        else:
            label = f"? /* 해석 불가 target: {json.dumps(tgt)} */"
        steps.append({"g_from": prev, "g_to": cur, "ref": ref, "label": label,
                      "color": s["args"]["color"]})
        prev = cur
    return steps


def _coloring_seq_lines(body):
    """_coloring_steps(공통 재료) → 순차 대입 텍스트 라인들. g0 = g.contents(하강 전 원본 contents)
    로 시작해, 각 coloring 스텝을 gN = coloring(gN-1, label, color) 로 threading(∘ 합성 폐기 —
    사고 단위를 한 줄씩 순차 statement 로). 빈 body(0 스텝)도 러너-안전한 identity(g0→result)로 남긴다."""
    lines = ["g0 = g.contents"]
    steps = _coloring_steps(body)
    for st in steps:
        col = _disp_leaf(st["color"])
        suffix = ("  # 해석 불가(다중좌표 — 러너 미지원)" if st["ref"] == "cellset" else "")
        lines.append(f"{st['g_to']} = coloring({st['g_from']}, {st['label']}, {col}){suffix}")
    lines.append(f"result = {steps[-1]['g_to'] if steps else 'g0'}")
    return lines


def _display_grid(body):
    """grid body → Grid 객체 3속성 개별 대입 형태(정직: size/color 는 완성 contents 와
    일관해야 valid). contents leaf 가 `program`(하강 coloring 합성, c–h)이면 g.color 뒤에 빈 줄을
    두고 순차 coloring statement 블록(g0..gN, result)을 삽입한 뒤 맨 아래에서
    g.contents = set_grid_contents(result) 로 마무리한다(∘ 한줄 압축 폐기). const/expr/var contents
    는 기존처럼 단일 줄. 실행 의미는 러너가 Grid 객체 모델로 재현."""
    parts = {s["call"]: s["args"] for s in body}
    sz = _disp_grid_leaf(parts["set_grid_size"]["size"], "size")
    co = _disp_grid_leaf(parts["set_grid_color"]["color"], "color")
    ct = parts["set_grid_contents"]["contents"]
    lines = ["g = input_grid",
             f"g.size = set_grid_size({sz})",
             f"g.color = set_grid_color({co})"]
    if "program" in ct:
        lines.append("")
        lines.extend(_coloring_seq_lines(ct["program"]["body"]))
        lines.append("g.contents = set_grid_contents(result)")
    else:
        lines.append(f"g.contents = set_grid_contents({_disp_grid_leaf(ct, 'contents')})")
    lines.append("output_grid = g")
    return "\n".join(lines)


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
    """grid-arg leaf → 시각화 박스 라벨(정직화). contents const→실 2D 배열."""
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


def _contents_cell(leaf, cls=""):
    """set_grid_contents leaf → 시각화 셀. const 2D 배열이면 줄바꿈 matrix(<pre>), 아니면 콤팩트 라벨.
    cls(선택) = Step B overlay COMM/DIFF outline class(§_compare_asts)."""
    if "const" in leaf and _is_grid_literal(leaf["const"]):
        mat = "\n".join(" ".join(str(x) for x in row) for row in leaf["const"])
        cls_attr = f" {cls}" if cls else ""
        return f'<pre class="cmat{cls_attr}">{html.escape(mat)}</pre>'
    return EV.colr(_grid_leaf_repr(leaf, "contents"), cls)


def _swatches(colors):
    return "".join(f'<i class="swatch" style="background:{EV.PAL[c % 10]}"></i>' for c in colors)


# ── §11 grid 썸네일 크리스프니스: 이 파일 로컬 렌더러 (EV.grid 는 다른 리포트와 공유 — 수정 금지) ──
# 근본원인: EV.grid 는 CSS grid(각 셀 = <i>, gap:1px+border)로 그린다 — 브라우저가 비정수
# device-pixel-ratio/줌(예: 133%)에서 grid-template-columns:repeat(W,6px) 의 각 컬럼 트랙을
# *독립적으로* 정수 물리픽셀에 반올림한다. 칸 수(W)가 많을수록(=큰 grid 일수록) 컬럼별 반올림
# 오차가 누적돼 칸 폭이 들쭉날쭉해지고(어떤 칸은 넓고 어떤 칸은 좁음) "stretched/sparse" 하게
# 보인다(재현: headless Chrome --force-device-scale-factor=1.33 로 실측). 고정 fix: 여러 개의
# 독립 레이아웃 박스 대신 SVG <rect> 를 한 장의 벡터로(shape-rendering=crispEdges) 그려 — 전체가
# 하나의 좌표계로 균일 스케일되므로 반올림이 누적되지 않는다(칸 수·줌 배율과 무관하게 크리스프).
def _thumb(gr, cell=9, gap=1):
    H, W = len(gr), len(gr[0])
    fill = cell - gap
    w, h = W * cell, H * cell
    rects = "".join(
        f'<rect x="{c * cell}" y="{r * cell}" width="{fill}" height="{fill}" fill="{EV.PAL[v % 10]}"/>'
        for r, row in enumerate(gr) for c, v in enumerate(row))
    return (f'<svg class="vthumb" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">{rects}</svg>')


def _endpoint_rows(ex):
    """공통 끝점: (input_grid 행, output_grid 행) — input/output 썸네일 인라인(G0/G1 개념 없음 —
    ①③ 이 실제로 쓰는 이름 그대로 input_grid/output_grid). 썸네일은 EV.grid(다른 리포트와 공유,
    수정 금지) 대신 이 파일 로컬 _thumb(§11 grid crispness)."""
    g0 = (f'<div class="row"><span class="bx grid">input_grid</span>{_thumb(ex["input"])}'
          f'</div><div class="v"></div>')
    g1 = f'<div class="row"><span class="bx grid">output_grid</span>{_thumb(ex["output"])}</div>'
    return g0, g1


def _coloring_flow_rows(body, outline=None):
    """③ 중첩 coloring 시각화 — ①(_coloring_seq_lines)과 정확히 같은 _coloring_steps(공통 재료)를
    소비해, 각 coloring 스텝을 op box + target label + color value(+swatch) 노드로 그린다
    (§①②③ 공통소스 원칙 — 모듈 docstring 참고). g0/result 캡션과 g_from/g_to 변수 라벨은 ①(텍스트)
    전용 배관(순차 대입 threading)이라 ③(시각화)에는 굳이 필요 없어 표시하지 않는다 — ①③ 이 같은
    _coloring_steps 재료를 소비하는 사실 자체는 그대로 유지, 포맷팅만 이 계층에서 덜어낸다.
    outline(선택) = Step B anti-unification overlay 용 포지션별 {'idx','col'} outline class
    (§Step B COMM/DIFF — _compare_asts 가 만든 결과를 그대로 소비, 여기서 새로 판정하지 않는다)."""
    steps = _coloring_steps(body)
    rows = []
    for i, st in enumerate(steps):
        col_leaf = st["color"]
        col = col_leaf.get("const")
        sw = _swatches([col]) if isinstance(col, int) else ""
        o = outline[i] if (outline and i < len(outline)) else {}
        rows.append(
            f'<div class="row">{EV.opb("coloring")}<span class="h"></span>'
            f'{EV.dest_box(st["label"], o.get("idx", ""))}<span class="h"></span>'
            f'{EV.colr(_disp_leaf(col_leaf), o.get("col", ""))}{sw}</div><div class="v"></div>')
    return rows


def _grid_step_rows(ast, outline=None):
    """set_grid_size→set_grid_color→set_grid_contents 3-property box-flow. 중첩 coloring(있으면)은
    .nestedflow 로 더 오른쪽에 들여쓰되(§5), 메인 세로선(.gflow::before)은 끊기지 않고 한 줄로
    이어진다 — 서로 다른 CSS 요소가 아니라 같은 .gflow 컨테이너 높이 전체를 덮는 절대배치 선.
    outline(선택) = {'size','color','contents'} — Step B overlay 용 COMM/DIFF class(§_compare_asts).
    """
    parts = {s["call"]: s["args"] for s in ast["body"]}
    sz, co, ct = (parts["set_grid_size"]["size"], parts["set_grid_color"]["color"],
                  parts["set_grid_contents"]["contents"])
    color_sw = (_swatches(co["const"]) if isinstance(co.get("const"), list)
                and not _is_grid_literal(co["const"]) else "")
    size_cls = outline["size"] if outline else ""
    color_cls = outline["color"] if outline else ""
    top = [
        f'<div class="row">{EV.opb("set_grid_size")}<span class="h"></span>{EV.colr(_grid_leaf_repr(sz, "size"), size_cls)}</div>',
        f'<div class="row">{EV.opb("set_grid_color")}<span class="h"></span>{EV.colr(_grid_leaf_repr(co, "color"), color_cls)}{color_sw}</div>',
    ]
    if "program" in ct:                        # contents = 하강 coloring 합성 → 중첩 box-flow(①과 같은 재료)
        top.append(f'<div class="row">{EV.opb("set_grid_contents")}</div>')
        step_outline = outline["contents"]["steps"] if outline else None
        inner_rows = _coloring_flow_rows(ct["program"]["body"], step_outline)
        body_html = "".join(top) + f'<div class="nestedflow">{"".join(inner_rows)}</div>'
    else:
        contents_cls = outline["contents"]["cls"] if outline else ""
        top.append(f'<div class="row">{EV.opb("set_grid_contents")}<span class="h"></span>'
                    f'{_contents_cell(ct, contents_cls)}</div>')
        body_html = "".join(top)
    return [f'<div class="gflow">{body_html}</div><div class="v"></div>']


def _pixel_step_rows(ast, outline=None):
    """outline(선택) = {'steps':[{'idx','col'},...]} — top-level pixel/object body 가 실제로 쓰일
    경우를 위한 Step B COMM/DIFF 대응(현 a-h 데이터는 전부 grid body — §확인됨 — 이지만 스키마상
    가능한 형태이므로 _grid_step_rows 와 대칭으로 지원)."""
    steps_outline = outline.get("steps") if outline else None
    rows = []
    for i, s in enumerate(ast["body"]):
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
        o = steps_outline[i] if (steps_outline and i < len(steps_outline)) else {}
        rows.append(f'<div class="row">{EV.opb("coloring")}<span class="h"></span>'
                    f'{EV.dest_box(label, o.get("idx", ""))}<span class="h"></span>'
                    f'{EV.colr(_disp_leaf(col_leaf), o.get("col", ""))}{sw}</div>'
                    f'<div class="v"></div>')
    return rows


def _viz(ast, ex, ghost=False, outline=None):
    """두 계열 공통 box-flow: input_grid 썸네일 → 스텝들 → output_grid 썸네일.
    ghost=True 면 overlay(§8 TASK.solution 가로 레이아웃 중간 열)용 반투명 사본
    (easy_antiunify_viz.flow(ghost=True) 와 같은 클래스 이름 재사용 — .ovl/.ghost CSS 는 EV.CSS 것).
    outline(선택) = _compare_asts() 가 낸 Step B COMM/DIFF class dict — 끝점(input_grid/output_grid)
    행에는 적용하지 않는다(§Step B — 끝점은 비교/표기 대상 밖)."""
    g0, g1 = _endpoint_rows(ex)
    steps = (_grid_step_rows(ast, outline) if PA._is_grid_body(ast.get("body") or [])
             else _pixel_step_rows(ast, outline))
    cls = "flow ghost" if ghost else "flow"
    return f'<div class="{cls}">{g0}{"".join(steps)}{g1}</div>'


# ── Step B COMM/DIFF: pair0 vs pair1 program 을 step-by-step 비교(끝점 grid 는 비교 대상 밖) ──────
def _eq_json(x, y):
    return json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)


def _compare_step_lists(body0, body1):
    """coloring step 리스트(program contents 하강, 또는 top-level pixel/object body) 를 포지션별로
    target/color 비교 → [{'idx':'comm'|'diff','col':'comm'|'diff'}, ...]. 개수가 다르면 넘치는
    포지션은 diff(다른 pair 에 대응 스텝 자체가 없음 = 어긋남)."""
    n = max(len(body0), len(body1))
    out = []
    for i in range(n):
        if i >= len(body0) or i >= len(body1):
            out.append({"idx": "diff", "col": "diff"})
            continue
        t0, t1 = body0[i]["args"]["target"], body1[i]["args"]["target"]
        c0, c1 = body0[i]["args"]["color"], body1[i]["args"]["color"]
        out.append({"idx": "comm" if _eq_json(t0, t1) else "diff",
                     "col": "comm" if _eq_json(c0, c1) else "diff"})
    return out


def _compare_asts(a0, a1):
    """pair0/pair1 의 실제 PAIR.program(AST) 을 step-by-step 비교(json.dumps(sort_keys=True) 값
    비교 — antiunify_ast() 를 재구현하는 게 아니라 Step B overlay 전용 순수 표시 비교, §근거=compare
    COMM/DIFF). grid body(a-h 전부 해당 — 확인됨): set_grid_size leaf, set_grid_color leaf,
    set_grid_contents content(program 이면 coloring 스텝별 target+color, const 면 값 그대로) 비교.
    pixel/object top-level body(현재 데이터엔 없으나 스키마상 가능)는 {'steps':[...]} 만 반환.
    반환 shape 은 항상 a0(렌더 대상=pair0 solid layer)의 실제 구조를 따른다."""
    b0, b1 = a0.get("body") or [], a1.get("body") or []
    if not (PA._is_grid_body(b0) and PA._is_grid_body(b1)):
        return {"steps": _compare_step_lists(b0, b1)}
    p0 = {s["call"]: s["args"] for s in b0}
    p1 = {s["call"]: s["args"] for s in b1}
    out = {
        "size": "comm" if _eq_json(p0["set_grid_size"]["size"], p1["set_grid_size"]["size"]) else "diff",
        "color": "comm" if _eq_json(p0["set_grid_color"]["color"], p1["set_grid_color"]["color"]) else "diff",
    }
    ct0 = p0["set_grid_contents"]["contents"]
    ct1 = p1["set_grid_contents"]["contents"]
    if "program" in ct0:
        body1 = ct1["program"]["body"] if "program" in ct1 else []
        out["contents"] = {"kind": "steps", "steps": _compare_step_lists(ct0["program"]["body"], body1)}
    else:
        out["contents"] = {"kind": "const",
                            "cls": "comm" if ("program" not in ct1 and _eq_json(ct0, ct1)) else "diff"}
    return out


# program_ast.render_header 는 pixel/object body(step.args.target.ref)만 가정 — grid(3-property)
# body 는 target 이 없어(set_grid_* 는 size/color/contents 인자) KeyError('target'). program_ast.py
# 는 solver 쪽 파일이라 수정하지 않고(하네스: 표시 전용, arbor/reasoning/* read-only), 여기서만
# grid body 를 위한 동등한 헤더를 만든다 — 단 PA._sig(n) 의 2-인자 구식(grid,size)이 아니라, 실제
# body 가 쓰는 1-인자 object-model 호출 형태(g.size = set_grid_size(size(input_grid)) 등)와
# "형태가 일치"하는 시그니처를 직접 적는다(§1 — 헤더가 body 와 다른 문법을 보이면 안 됨).
_GRID_SIG = {
    "set_grid_size": "set_grid_size(size) -> size   (g.size 에 대입; size=ARCKG GRID.size)",
    "set_grid_color": "set_grid_color(color) -> color   (g.color 에 대입; color=ARCKG GRID.color)",
    "set_grid_contents": "set_grid_contents(contents) -> contents   (g.contents 에 대입; contents=ARCKG GRID.contents)",
}
_COLORING_SIG = "coloring(grid, position, color) -> grid   (contents 합성 시)"


def _render_header_safe(ast, g0):
    body = ast.get("body") or []
    if not PA._is_grid_body(body):
        return PA.render_header(ast, g0)
    parts = {s["call"]: s["args"] for s in body}
    lines = ["# --- DSL (used) ---"]
    for name in ("set_grid_size", "set_grid_color", "set_grid_contents"):
        if name in parts:
            lines.append(f"# {_GRID_SIG[name]}")
    ct = parts.get("set_grid_contents", {}).get("contents", {})
    if "program" in ct:                        # contents 가 하강 coloring 합성일 때만(§1) 병기
        lines.append(f"# {_COLORING_SIG}")
    lines += ["# --- input (this pair) ---", f"input_grid = {json.dumps(g0)}"]
    return "\n".join(lines)


# ── 3-뷰 한 pair(또는 TASK.solution) 블록 (①②③ 은 같은 AST 의 세 표현 — 모듈 docstring 참고) ──
def _pair_block(label, ast, ex):
    g0 = ex["input"]
    return (f'<div class="pair">'
            f'<div class="lab">{html.escape(str(label))}</div>'
            f'<div class="views">'
            f'<div class="view"><div class="vt">① text (통일 body · 실행형)</div>'
            f'<pre class="hdr">{html.escape(_render_header_safe(ast, g0))}</pre>'
            f'<pre class="src">{html.escape(display_source(ast))}</pre></div>'
            f'<div class="view"><div class="vt">② AST 트리</div>{ast_tree(ast)}</div>'
            f'<div class="view"><div class="vt">③ 시각화</div>{_viz(ast, ex)}</div>'
            f'</div></div>')


# ── Step A/B/C 카드 레이아웃(2026-07-17 재구성): Step A(PAIR.program — pair 별 ①②③ 를 세로
#    stack, top-aligned) → Step B(anti-unification — ①과 같은 ③ overlay, 카드 안에서 수직 중앙)
#    → Step C(TASK.solution — 카드 안에서 박스 자체는 수직 중앙, 박스 내부 ①②③ 은 top-aligned
#    그대로). 셋을 색으로 구분된 카드에 담아 한 컨테이너(가로 스크롤)에 나란히 놓는다. overlay 는
#    easy_antiunify_viz.flow(ghost=True)/.ovl·.ghost 와 같은 기법 재사용(반투명 겹침) — EV.CSS 에
#    이미 있는 .ovl/.ghost 를 그대로 쓴다(중복 정의 안 함).
def _solution_row(ast_ex_pairs, solution):
    pair_boxes = "".join(
        f'<div class="innerbox">{_pair_block(f"PAIR {p + 1}", a, ex)}</div>'
        for a, ex, p in ast_ex_pairs)
    steps = [f'<div class="stepcard stepA"><div class="stepttl">Step A · PAIR.program</div>{pair_boxes}</div>']

    if len(ast_ex_pairs) >= 2:
        a0, ex0, _p0 = ast_ex_pairs[0]
        a1, ex1, _p1 = ast_ex_pairs[1]
        # pair0(solid layer) vs pair1(ghost) 을 step-by-step 비교(끝점 grid 는 비교 밖 — _viz 의
        # outline 은 gflow/nestedflow 스텝에만 적용되고 _endpoint_rows 는 outline 인자를 받지 않는다)
        # → COMM(녹색 .comm)/DIFF(빨강 .diff) outline 을 solid layer 에 입힌다(EV.CSS 재사용, 신규
        # 색 정의 없음). solid+ghost 겹침 자체는 기존 .ovl/.ghost 그대로.
        outline = _compare_asts(a0, a1)
        overlay = (f'<div class="ovl">{_viz(a0, ex0, outline=outline)}{_viz(a1, ex1, ghost=True)}</div>'
                   f'<div class="legend"><span class="lg comm">COMM(일치) = 녹색</span>'
                   f'<span class="lg diff">DIFF(어긋남) = 빨강</span></div>')
        box = f'<div class="innerbox"><div class="lab">PROGRAM COMPARISON</div>{overlay}</div>'
        steps.append(f'<div class="stepcard stepB"><div class="stepttl">Step B · Anti-unification</div>'
                     f'<div class="stepBcontent">{box}</div></div>')

    if solution is not None:
        sol_ex = ast_ex_pairs[0][1]
        sol_box = f'<div class="innerbox">{_pair_block("TASK.solution (anti-unify 골격)", solution, sol_ex)}</div>'
        steps.append(f'<div class="stepcard stepC"><div class="stepttl">Step C · TASK.solution</div>'
                      f'<div class="stepCcontent">{sol_box}</div></div>')
    else:
        steps.append('<div class="stepcard stepC"><div class="stepttl">Step C · TASK.solution</div>'
                      '<p class="note">TASK.solution 미물질화(generalize 미도달)'
                      ' — per-pair program 만 표시.</p></div>')

    arrow = '<div class="steparrow">→</div>'
    return f'<div class="stepsrow">{arrow.join(steps)}</div>'


def _thumb_unit(label, inner):
    return f'<div class="tunit"><span class="tlab">{html.escape(label)}</span>{inner}</div>'


def _pair_unit(title_html, row_html):
    """상단 task 시각화 한 PAIR 유닛: 대문자 헤더 + 그 아래 grid 행(input→output 등). example/test
    를 나눈 두 그룹(.tgroup) 대신, 모든 pair(example + test)를 같은 형태의 카드로 한 가로 행에
    나란히 놓기 위한 공통 단위(§4 top-viz restructure). title_html 은 이미 안전한(고정 포맷,
    사용자 입력 아님) 헤더 마크업 그대로 삽입한다 — .phead 가 text-transform:uppercase 라 test
    유닛의 "PAIR a" 처럼 일부러 소문자로 남길 글자는 <span class="lc"> 로 감싸 그 상속을
    되돌린다(§2 PAIR a 표기)."""
    return f'<div class="punit"><div class="phead">{title_html}</div><div class="prow">{row_html}</div></div>'


def _top_thumbs(task):
    """상단 task 시각화: example(train) pair 들 + test pair 를 한 가로 행(PAIR 유닛들)으로 나란히
    보여준다. 각 유닛 = 대문자 헤더("PAIR 0","PAIR 1",…, test 는 "PAIR a") + input →(화살표)→
    output 행. test pair 는 output 이 아직 미지 → '?' 빈 박스(캡션 "output", "output?" 아님)로
    그리고, 실제 정답(tp['output'])이 있으면 그 뒤에 "Ground Truth" 라벨(정답 아님)로 이어 붙인다
    (grid 는 §11 크리스프 SVG _thumb 그대로 — 별도 렌더러 만들지 않음). 가로로 스크롤되는 Step
    카드들과는 별개로 이 영역은 위쪽에 고정 — 한눈에 읽히게 한다.
    example 유닛들과 test 유닛은 각각 "EXAMPLE"/"TEST" 섹션 라벨을 얹은 .tgroup 으로 묶고, 그 둘
    사이에 얇은 세로 구분선(.tdivider)을 둔다 — 유닛 자체(.punit/.phead/.prow)는 그대로, 상위에
    그룹 레이어 하나만 추가(§ EXAMPLE/TEST 라벨링)."""
    example_units = [
        _pair_unit(html.escape(f"PAIR {i}"),
                   f'{_thumb_unit("input", _thumb(ex["input"]))}'
                   f'<span class="tarrow">→</span>{_thumb_unit("output", _thumb(ex["output"]))}')
        for i, ex in enumerate(task["train"])
    ]
    tp = task["test"][0]
    qbox = '<div class="tqbox">?</div>'
    test_row = (f'{_thumb_unit("input", _thumb(tp["input"]))}'
                f'<span class="tarrow">→</span>{_thumb_unit("output", qbox)}')
    if tp.get("output"):
        test_row += f'<span class="tsep"></span>{_thumb_unit("Ground Truth", _thumb(tp["output"]))}'
    # "PAIR a" — PAIR 는 대문자, 꼬리 a 는 소문자 그대로(§2). .phead 의 text-transform:uppercase 를
    # 그 글자에서만 되돌려야 하므로 <span class="lc"> 로 감싼다(순수 텍스트로 두면 CSS 가 "PAIR A"
    # 로 강제 대문자화해버려 시각적으로 §2 요구를 못 지킴).
    test_unit = _pair_unit('PAIR <span class="lc">a</span>', test_row)
    example_group = (f'<div class="tgroup"><div class="tglabel">EXAMPLE</div>'
                      f'<div class="tgrow">{"".join(example_units)}</div></div>')
    test_group = (f'<div class="tgroup"><div class="tglabel">TEST</div>'
                   f'<div class="tgrow">{test_unit}</div></div>')
    return f'<div class="tunits">{example_group}<div class="tdivider"></div>{test_group}</div>'


def task_section(tid, task, precomputed=None):
    thumbs = _top_thumbs(task)

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

    ast_ex_pairs = [(a, task["train"][p], p) for a, p in zip(asts, pairs)]
    solrow = _solution_row(ast_ex_pairs, solution)

    return (f'<section class="task" id="{tid}"><h2>{tid}</h2>'
            f'<div class="thumbs">{thumbs}</div>{solrow}</section>')


CSS = """
.views{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin:6px 0 14px}
.view{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;flex:1 1 300px;min-width:240px;overflow-x:auto}
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
.swatch{display:inline-block;width:10px;height:10px;margin-left:2px;border-radius:2px;vertical-align:middle;
 border:1px solid rgba(255,255,255,.25)}
.pair{padding-top:0;margin-top:0}
.pair + .pair{border-top:1px solid #232b36;padding-top:12px;margin-top:12px}
/* §11 grid crispness: SVG 썸네일(사각 <i> 그리드 아님) — 줌/DPR 비정수배에서도 균일 스케일 */
.vthumb{display:inline-block;vertical-align:middle;background:#2a2e38;border:1px solid #2a2e38;
 image-rendering:pixelated;image-rendering:crisp-edges}
/* §5/§6/§7/§8 grid 3-property flow: 메인 세로선(::before, 절대배치)이 gflow 전체 높이를 관통해서
   set_grid_size→color→contents 사이가 끊기지 않는다. 중첩 coloring(.nestedflow)은 그 선 오른쪽으로
   더 들여써(margin-left) 겹치지 않는다 — 별도 CSS 요소가 아니라 "같은 선이 배경에서 이어지고,
   중첩 박스가 그 위에 오른쪽으로 얹힌다"는 하나의 레이아웃. */
.flow{width:max-content}
.gflow{position:relative;display:flex;flex-direction:column;align-items:flex-start}
.gflow::before{content:"";position:absolute;left:48px;top:6px;bottom:6px;width:2px;background:#3b4657}
.gflow>.row{margin-bottom:12px}
.gflow>.row:last-of-type{margin-bottom:6px}
.nestedflow{display:flex;flex-direction:column;align-items:flex-start;border-left:2px solid #3a5a7a;
 padding:6px 0 6px 12px;margin:0 0 0 82px;background:#101319;border-radius:0 6px 6px 0;width:max-content}
.nestedflow .row{margin-bottom:8px}
.nestedflow .row:last-child{margin-bottom:0}
.gvar{font:11px ui-monospace,monospace;color:#7fb2e0;background:#132030;border:1px solid #22384d;
 border-radius:5px;padding:2px 6px;margin-right:6px}
.gvar-out{margin-right:0;margin-left:6px;color:#e6c99a;background:#241b12;border-color:#3a2c1a}
.gnote{font-size:10.5px;color:#8fb0a0;font-style:italic}
/* Step A/B/C 카드 레이아웃(2026-07-17): 한 컨테이너(가로 스크롤)에 색으로 구분된 3 카드.
   .stepsrow 는 align-items:stretch(기본값) 라 세 카드가 전부 가장 높은 카드(대개 Step A, pair0+
   pair1 세로 stack)와 같은 높이로 맞춰진다 — Step B/C 는 그 안에서 "카드 안 수직 중앙"을 flex
   column + justify-content:center 로 구현(내용은 1개뿐이라 그게 곧 카드 중앙점). Step A 는
   stepttl 다음에 innerbox 들이 기본 top-aligned 순서로 그냥 쌓인다(별도 wrapper 불필요). */
.stepsrow{display:flex;gap:0;overflow-x:auto;padding-bottom:6px;margin-top:10px}
.stepcard{flex:0 0 auto;display:flex;flex-direction:column;border-radius:12px;padding:14px 16px;min-width:280px}
.stepttl{font-size:12px;font-weight:700;letter-spacing:.02em;margin-bottom:10px;white-space:nowrap}
.innerbox{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;width:max-content}
.innerbox + .innerbox{margin-top:12px}
.stepA{background:#1a2036;border:1px solid #3a4a78}
.stepA .stepttl{color:#9fb4e0}
.stepB{background:#241a36;border:1px solid #4c3a78}
.stepB .stepttl{color:#c8a8f0}
.stepBcontent{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;align-items:center}
.stepC{background:#14271f;border:1px solid #2e5a44}
.stepC .stepttl{color:#8fdcb8}
.stepCcontent{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;align-items:center}
.steparrow{align-self:center;display:flex;align-items:center;justify-content:center;
 font-size:22px;color:#5a6577;flex:0 0 auto;padding:0 10px}
/* 상단 task 시각화(thumbs, §4 재구성): example pair + test pair 를 모두 같은 형태의 PAIR 유닛
   (.punit = 대문자 헤더 .phead + 그 아래 grid 행 .prow) 카드로 한 가로 행(.tunits)에 나란히 놓는다
   (더 이상 example/test 두 그룹으로 분리하지 않음 — 한 레이어). test 유닛은 output 미지 → [?]
   빈 박스(캡션 "output"), 실제 정답(tp.output)이 있으면 그 옆에 "Ground Truth" 라벨로 표시.
   가로 스크롤되는 Step 카드(.stepsrow)와는 별개 — 이 영역은 그 위에 고정, 한눈에 읽힌다. */
.thumbs{margin:8px 0 14px}
.tunits{display:flex;gap:0;flex-wrap:wrap;align-items:stretch}
/* EXAMPLE/TEST 그룹핑: example pair 유닛들과 test pair 유닛을 각각 섹션 라벨(.tglabel) 을 얹은
   .tgroup 으로 묶고, 그 사이에 얇은 세로 구분선(.tdivider) 을 둔다 — .punit/.phead/.prow(개별
   유닛 렌더)는 그대로, 상위에 그룹 레이어 하나만 추가. */
.tgroup{display:flex;flex-direction:column;gap:8px}
.tglabel{font-size:10px;color:#6c7688;text-transform:uppercase;letter-spacing:.12em;font-weight:700}
.tgrow{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start}
.tdivider{width:1px;align-self:stretch;background:#2a3038;margin:0 18px}
.punit{display:flex;flex-direction:column;gap:8px;background:#12151b;border:1px solid #232a35;
 border-radius:9px;padding:9px 12px}
.phead{font-size:10.5px;color:#8b93a3;text-transform:uppercase;letter-spacing:.05em;font-weight:700}
.phead .lc{text-transform:lowercase}
.prow{display:flex;align-items:flex-end;gap:8px}
.tunit{display:flex;flex-direction:column;align-items:center;gap:3px}
.tlab{font-size:9px;color:#7a8698}
.tarrow{color:#5a6577;font-size:16px;margin-bottom:14px}
.tsep{width:10px}
.tqbox{width:40px;height:40px;display:flex;align-items:center;justify-content:center;
 background:#161b24;border:1px dashed #3a4150;border-radius:4px;color:#5a6577;font-size:18px;font-weight:700}
/* Step B "PROGRAM COMPARISON" overlay — 로컬 오버라이드(easy000g 겹침 버그 수정). EV.CSS 의
   .ovl/.ghost(다른 리포트와 공유, 수정 금지)를 그대로 두고, 여기서는 더 구체적인 선택자
   (.stepB .ovl 등, .ovl 단독보다 specificity 가 높아 순서와 무관하게 이긴다)로만 위에 얹는다.
   버그였던 것: ghost 를 inset:0 으로 solid 박스(.ovl) 크기에 강제로 늘리면(=absolute 요소가
   top/right/bottom/left 를 모두 갖고 width/height 는 auto → 크기가 컨테이너로 stretch),
   pair0/pair1 두 viz 의 총 높이가 다른 태스크(예: easy000g — 두 pair 의 grid 썸네일 크기가 달라
   viz 높이가 다름)에서 ghost 가 solid 와 완전히 같은 폭/높이로 눌려 붙어 텍스트가 같은 칸에
   포개진다(대각선 오프셋이 안 보임). 고정: ghost 는 top/left 만 고정하고 right/bottom 은 auto 로
   풀어 자기 콘텐츠 크기 그대로(shrink-to-fit) 두고, 더 큰 대각선 translate 만 적용 — 그러면 두
   레이어의 높이가 서로 달라도 항상 벌어진 대각선으로 읽힌다. .ovl 컨테이너는 그 벌어진 ghost 를
   잘리지 않게 담을 만큼 넉넉한 padding(우/하)을 준다. */
.stepB .ovl{position:relative;padding:6px 30px 30px 6px;width:max-content;min-width:max-content}
.stepB .ovl .ghost{position:absolute;top:0;left:0;right:auto;bottom:auto;width:auto;height:auto;
 transform:translate(22px,22px);opacity:.4;pointer-events:none;filter:saturate(.7)}
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
/* §11 grid crispness: 러너의 expected/출력 그리드도 _thumb 와 같은 SVG <rect> 렌더(JS gridHTML) */
.rgridsvg{display:inline-block;vertical-align:middle;background:#2a2e38;border:1px solid #3a4150;
 image-rendering:pixelated;image-rendering:crisp-edges}
.rout{align-items:flex-start}.rlab{font-weight:700}
"""

_RUNNER_HTML = r"""
<section id="runner"><h2>코드 실행기</h2>
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
// Grid 객체 헬퍼: size/color 는 contents 로부터 파생 — valid 검사(§ run())의 근거.
function _arr(x){ return (x && x.contents) ? x.contents : x; }          // Grid 객체→2D array
function _dims(c){ return {height:c.length, width:c[0].length}; }
function _colorset(c){ var s={}; for(var r=0;r<c.length;r++)for(var k=0;k<c[r].length;k++)s[c[r][k]]=true; return s; }
function _cloneObj(o){ return {size:o.size, color:o.color, contents:_arr(o).map(function(r){return r.slice();})}; }
function _sameDims(a,b){ return a && b && a.height===b.height && a.width===b.width; }
function _normColors(x){ // 배열[0,2] | present-set{0:true} → 정렬된 존재색 리스트
  var ks = Array.isArray(x) ? x.slice() : Object.keys(x).filter(function(k){return x[k];}).map(Number);
  return ks.map(Number).sort(function(a,b){return a-b;});
}
// 선언 색집합 == 완성 contents 의 '존재 색' 집합(엄격 일치, superset 팔레트는 의도적으로 불일치=모순).
// 솔버는 _color_leaf 가 출력의 존재색으로 const 를 굽기에 항상 일치 — 이 검사는 러너 편집 시 모순을 잡는다.
function _sameColors(a,b){ return JSON.stringify(_normColors(a))===JSON.stringify(_normColors(b)); }
var ATOM = {
  input_grid: null,
  make_grid: function(size){var o=[];for(var r=0;r<size.height;r++){var row=[];for(var c=0;c<size.width;c++)row.push(0);o.push(row);}return o;},
  set_grid_size: function(s){ return s; },        // 객체 모델: 속성값 반환(size==dims(contents) 여부는 run() 이 검사)
  set_grid_color: function(c){ return c; },
  set_grid_contents: function(z){ return z; },
  size: function(g){ return _dims(_arr(g)); },     // 2D array | Grid 객체 모두 처리
  color: function(g){ return _colorset(_arr(g)); },
  height: function(g){ return _arr(g).length; },
  width: function(g){ return _arr(g)[0].length; },
  contents: function(g){ return _arr(g).map(function(r){return r.slice();}); },
  objects_of: function(g){throw new Error("objects_of: 러너 미지원(pixel/ grid 만)");},
  pixels_of: function(g){ var c=_arr(g),w=c[0].length,out=[]; for(var i=0;i<c.length*w;i++) out.push({coord:[Math.floor(i/w),i%w]}); return out; },
  coloring: function(g,pos,color){ var o=_arr(g).map(function(r){return r.slice();}); o[pos[0]][pos[1]]=color; return o; },
  divmod: function(a,b){return [Math.floor(a/b),a%b];}
};
// body 실행: display_source 문법 — grid 객체형('g.prop = fn(…)') + pixel형('g = fn(g,…)') + for-loop 1종 해석. 미지원 구문 → 예외.
function runBody(code, input){
  var INPUT = {size:_dims(input), color:_colorset(input), contents:input.map(function(r){return r.slice();})};
  ATOM.input_grid = INPUT;
  var g = INPUT, output = null;
  function evalExpr(e){
    // 안전 평가: ATOM/g/input_grid/숫자/배열/객체 리터럴만. new Function 은 로컬 스코프에 바인딩.
    return (new Function("ATOM","g","input_grid","divmod",
      "with(ATOM){return ("+e+");}"))(ATOM, g, INPUT, ATOM.divmod);
  }
  // 순차 대입 body(g0 = g.contents; gN = coloring(gN-1, pos, color); …; result = gN) 는 아래 generic
  // '이름 = 식' 처리(∘ 합성 폐기 이후 특수 분기 불필요 — name→ATOM[name], g→g, output_grid→output 만
  // 구분하면 됨)와 g.prop = 식(mDot) 만으로 충분히 재현된다.
  var lines = code.split("\n");
  for(var i=0;i<lines.length;i++){
    var ln = lines[i].trim();
    if(!ln || ln[0]==="#") continue;
    var mDot = ln.match(/^g\.(size|color|contents)\s*=\s*(.+)$/);   // 객체 속성 대입
    if(mDot){
      if(g===INPUT) g=_cloneObj(INPUT);
      g[mDot[1]] = evalExpr(mDot[2]);
      continue;
    }
    var mFor = ln.match(/^for\s+(\w+)\s+in\s+(.+):$/);              // pixel cellset 루프
    if(mFor){ var it=evalExpr(mFor[2]); var b=lines[i+1].trim(); var mb=b.match(/^g\s*=\s*(.+)$/); i++;
      for(var k=0;k<it.length;k++){ ATOM[mFor[1]]=it[k];
        g=(new Function("ATOM","g","input_grid","divmod","with(ATOM){return ("+mb[1]+");}"))(ATOM,g,INPUT,ATOM.divmod); }
      continue; }
    var m = ln.match(/^(\w+)\s*=\s*(.+)$/);
    if(!m) throw new Error("해석 불가: "+ln);
    var val = evalExpr(m[2]);
    if(m[1]==="g") g=val; else if(m[1]==="output_grid") output=val; else ATOM[m[1]]=val;
  }
  return output!==null ? output : g;
}
// §11 grid crispness(Python _thumb 와 같은 근본원인/같은 픽스 — 모듈 상단 주석 참고): CSS-grid
// 기반 렌더(<i> 셀 + grid-template-columns)는 비정수 DPR/줌에서 컬럼별 반올림이 누적돼 오른쪽
// 열 경계선이 사라지는 경우가 있다. SVG <rect> 를 한 장의 벡터로(shape-rendering=crispEdges)
// 그리면 전체가 하나의 좌표계로 스케일되어 반올림이 누적되지 않는다 — #rgrid/#regrid 공용.
function gridHTML(g){ if(!g||!g.length) return '<span class="rerr">–</span>';
  var cell=20, gap=1, fill=cell-gap;
  var H=g.length, W=g[0].length, w=W*cell, h=H*cell, rects="";
  for(var r=0;r<H;r++){ for(var c=0;c<W;c++){
    var v=((g[r][c]%10)+10)%10;
    rects += '<rect x="'+(c*cell)+'" y="'+(r*cell)+'" width="'+fill+'" height="'+fill+'" fill="'+PAL_JS[v]+'"/>';
  } }
  return '<svg class="rgridsvg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'" '
    +'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">'+rects+'</svg>';
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
      var arr=_arr(out);
      document.getElementById("rgrid").innerHTML=gridHTML(arr);
      document.getElementById("regrid").innerHTML=gridHTML(d.expected);
      // (a) Grid 객체면 일관성(valid) 먼저
      var invalid="";
      if(out && out.contents){
        if(out.size && !_sameDims(out.size,_dims(arr))) invalid="size";
        else if(out.color && !_sameColors(out.color,_colorset(arr))) invalid="color";
      }
      if(invalid){ badge.textContent="✗ 모순("+invalid+")"; badge.className="rbadge rno";
        err.textContent=invalid+" 선언이 완성 contents 와 불일치 — invalid grid"; return; }
      // (b) 정답(contents==expected)
      var ok=eqGrid(arr,d.expected); badge.textContent=ok?"✓ parity":"✗ 불일치";
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
