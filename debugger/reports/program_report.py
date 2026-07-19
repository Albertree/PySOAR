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

    python -m debugger.reports.program_report   # -> debugger/reports/program_report.html
"""
from __future__ import annotations

import html
import json
import os
import re

from arbor.agent.focus import setup_focus_agent
from arbor.engine.trace import _Tracer
from arbor.env.dataset import list_tasks, load_task
from arbor.reasoning import program_ast as PA
from debugger.reports import solution_expr as SE

# easy_a 8 태스크(a-h). (easy000i=격자 크기 변화 미해결은 데이터셋에서 제거됨.)
TIDS = [f"easy000{c}" for c in "abcdefgh"]


# ── (옛 easy_antiunify_viz 에서 인라인 — 그 모듈은 삭제됨) 원자 box 렌더 헬퍼 + CSS ─────────────
PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]


def grid(gr):
    W = len(gr[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in gr for v in row)
    return f'<div class="thumb" style="grid-template-columns:repeat({W},6px)">{cells}</div>'


def opb(name, cls=""):
    return f'<span class="bx op {cls}">{html.escape(name)}</span>'


def colr(v, cls=""):
    return f'<span class="bx cv {cls}">{html.escape(str(v))}</span>'


def dest_box(v, cls=""):
    return f'<span class="bx tv {cls}">{html.escape(v)}</span>'


def _attempts_block(attempts, tp):
    if not attempts:
        return '<div class="note">제출 없음 — cycle 한도 내 submit 미도달.</div>'
    correct_i = next((i for i, at in enumerate(attempts) if at["correct"]), None)
    rows = "".join(
        f'<div class="att {"aok" if at["correct"] else "ano"}">attempt {i}: {html.escape(at["hyp"])} '
        f'→ {"✅" if at["correct"] else "✗"}</div>'
        for i, at in enumerate(attempts, 1))
    chosen = attempts[correct_i] if correct_i is not None else attempts[-1]
    pred, ok_test = chosen["answer"], bool(chosen["correct"])
    submit = ""
    if pred:
        submit = (f'<div class="submit"><span class="slab">제출 (test, real)</span>{grid(tp["input"])}'
                  f'<span class="ag">→</span><span class="pwrap">{grid(pred)}<span class="pcap">예측</span></span>'
                  f'<span class="sv {"sok" if ok_test else "sno"}">{"✅ 정답" if ok_test else "✗ 오답"}</span>'
                  + (f'<span class="pwrap">{grid(tp["output"])}<span class="pcap">정답</span></span>'
                     if tp.get("output") else "") + '</div>')
    return (f'<div class="attempts"><div class="ahead">실행 attempts (real, n={len(attempts)})'
            f'</div>{rows}</div>{submit}')


_EV_CSS = """
body{background:#14161b;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,sans-serif;margin:0;padding:20px}
a.back{color:#5fb0ff;text-decoration:none;font-size:13px}
h1{font-size:18px;margin:10px 0 4px}.hs{color:#8b93a3;margin:0 0 14px;font-size:12px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px}
.tabs a{color:#cdd6e4;text-decoration:none;background:#1b1f27;border:1px solid #2a3038;border-radius:6px;padding:4px 10px;font-size:12px}
.tabs a.on{background:#243b52;color:#bcd8f5;border-color:#3a5a7a}
.task{background:#1a1d24;border:1px solid #262b34;border-radius:10px;padding:16px 18px;margin:0 0 18px}
.task h2{font-size:16px;margin:0 0 14px}.tag2{font-size:11px;background:#243b52;color:#bcd8f5;padding:2px 9px;border-radius:6px;margin-left:8px}
.na{font-size:11px;background:#463619;color:#ffcf9a;padding:2px 9px;border-radius:6px;margin-left:8px}
.cols{display:flex;gap:6px;align-items:stretch}
.col{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px}
.c1,.c2{flex:0 0 auto}.c3{flex:1 1 auto}
.ct{font-size:11px;color:#8b93a3;text-transform:uppercase;letter-spacing:.03em;margin-bottom:10px}
.lab{font-size:10px;color:#7a8698;margin:6px 0 4px;font-weight:700}
.sep{display:flex;align-items:center;justify-content:center;min-width:46px;color:#8b93a3;font-size:10px;font-weight:700;text-align:center}
.sep span{background:#161b24;border:1px solid #2a3340;border-radius:6px;padding:6px 8px}
.flow{display:flex;flex-direction:column;align-items:flex-start}
.row{display:flex;align-items:center}
.v{width:2px;height:12px;background:#3b4657;margin-left:48px}
.c3 .v{height:42px}
.h{width:11px;height:2px;background:#3b4657}
.args{display:flex;gap:5px;align-items:center}
.bx{position:relative;border-radius:6px;padding:4px 9px;font-size:11.5px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.grid{background:#fff;color:#222;border-color:#cdd3db;min-width:78px;text-align:center;font-family:ui-monospace,monospace;font-weight:500}
.op{background:#f6cccd;color:#7a2b2c;border-color:#e0a3a4;min-width:78px;text-align:center}
.tv{background:#fbe6c9;color:#7a5320;border-color:#e6c99a;font-family:ui-monospace,monospace;font-weight:500}
.cv{background:#fbe6c9;color:#7a5320;border-color:#e6c99a;font-family:ui-monospace,monospace;font-weight:500;min-width:20px;text-align:center}
.dvar{background:#211830;color:#c79bf0;border-color:#a06be0}
.comm{outline:2px solid #3fae6a;outline-offset:1px}
.diff{outline:2px solid #e23b3b;outline-offset:1px}
/* overlay */
.ovl{position:relative}
.ovl .ghost{position:absolute;inset:0;transform:translate(9px,9px);opacity:.4;pointer-events:none;filter:saturate(.7)}
.legend{display:flex;gap:12px;margin-top:14px;font-size:10px}
.lg{display:inline-flex;align-items:center;gap:5px;color:#9aa3b2}
.lg::before{content:"";width:14px;height:0;border-top:2px solid}
.lg.comm::before{border-color:#3fae6a}.lg.diff::before{border-color:#e23b3b}
/* header(render_header) 자동 표시 + slots(antiunify_ast 실제 결과) */
.hdr{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:7px 10px;font:10.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#8fb0a0;white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 8px}
.slots{margin-top:10px;font-size:11px}
.slotrow{padding:4px 0;display:flex;align-items:center;gap:8px;color:#9aa3b2;flex-wrap:wrap}
.slotmeta{color:#7a8698}
.thumbs{display:flex;gap:5px;margin-top:8px}
.thumb{display:inline-grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}.thumb i{width:6px;height:6px;display:block}
.note{margin-top:10px;font-size:11px;color:#9aa3b2;display:flex;align-items:center;gap:4px}
.attempts{margin-top:10px;font-size:11px}
.ahead{color:#9aa3b2;margin-bottom:5px;font-weight:700}
.att{padding:3px 8px;border-radius:5px;margin:3px 0;font-family:ui-monospace,monospace}
.aok{background:#12281c;color:#a9e6c1;border:1px solid #2f5a41}
.ano{background:#241417;color:#e0a3a4;border:1px solid #5a2f34}
.submit{margin-top:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:#0f141b;border:1px solid #2a3242;border-radius:8px;padding:8px 10px}
.slab{font-size:10px;color:#8b93a3;font-weight:700;text-transform:uppercase}
.pwrap{display:inline-flex;flex-direction:column;align-items:center;gap:2px}.pcap{font-size:9px;color:#8b93a3}
.sv{font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px}
.sok{background:#12281c;color:#a9e6c1;border:1px solid #2f5a41}.sno{background:#241417;color:#e0a3a4;border:1px solid #5a2f34}
"""


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
        v = leaf["const"]
        if prop == "size" and isinstance(v, dict) and "height" in v:
            return f"({v['height']}, {v['width']})"  # 리터럴 크기값 (사용자: '(8,8) 같은 값')
        return json.dumps(v)                         # color list / contents 2D 배열 실값
    if "expr" in leaf:
        return str(leaf["expr"])                     # (forward: H/W 어휘 번역은 별건)
    if "delta" in leaf:
        d = leaf["delta"]
        return f"delta(remove={d['remove']}, add={d['add']})"
    if "var" in leaf:
        return str(leaf["var"])                       # TASK.solution slot (pair 간 값이 다른 grid property)
    return json.dumps(leaf)


def _pretty_move(expr):
    """resolved cellset 슬롯식(`move[ROW,COL]@SEL`)을 사람이 읽는 명확한 이동 표현으로.
    각 축 토큰을 라벨링: keep(제자리)·=v(절대)·0(끝)·H-h/W-w(코너)·BR→v(우하코너)·src±Δ(상대Δ).
    선택자(@color=2 등)는 ⟨…⟩ 로. 파싱 실패 시 원문 그대로(정직)."""
    m = re.match(r"^move\[(.+?),(.+?)\](?:@(.+))?$", expr)
    if not m:
        return expr
    row, col, sel = m.group(1), m.group(2), (m.group(3) or "")

    def _ax(tok):
        md = re.match(r"^[rc]0([+-]\d+)$", tok)
        if md:
            return "keep(제자리)" if md.group(1) in ("+0", "-0") else f"src{md.group(1)}(상대Δ)"
        if tok.startswith("BR="):
            return f"BR→{tok[3:]}(우하코너)"
        if tok.startswith("="):
            return f"={tok[1:]}(절대)"
        if tok == "0":
            return "0(끝)"
        if tok in ("H-h", "W-w"):
            return f"{tok}(코너)"
        return tok
    sel_txt = f"⟨{sel}⟩" if sel else ""
    return f"move{sel_txt} → row:{_ax(row)}, col:{_ax(col)}"


def _coloring_steps(body, slot_exprs=None, cell_w=None):
    """set_grid_contents 의 contents leaf 가 `program`(하강 coloring 합성, c–h)일 때의 순차 스텝
    재료 — ①(_coloring_seq_lines, 텍스트) 과 ③(_coloring_flow_rows, 시각화)가 이 SAME 리스트를
    소비한다(모듈 docstring §①②③ 공통소스 원칙). 각 스텝 = {g_from, g_to, ref, label, color, resolved}.
    label 은 두 표현 모두에서 문자 그대로 재사용되는 target 텍스트(accessor 식 또는 cellset).
    slot_exprs(선택) = {`?c.cellsN` → resolved 이동식} — TASK.solution 렌더 시, cellset 변수를
    raw(`cellset=?c.cellsN`) 대신 명확한 move 표현식으로 치환한다(§사용자 2026-07-20)."""
    steps = []
    prev = "g0"
    for j, s in enumerate(body, start=1):
        tgt = s["args"]["target"]
        ref = tgt.get("ref")
        cur = f"g{j}"
        resolved = False
        if ref in _ACCESSOR:
            idx = _disp_leaf(tgt["index"])
            label = f"{_ACCESSOR[ref]}(input_grid)[{idx}].coord"
        elif ref == "coord":                          # 리터럴 좌표 직접
            r, c = tgt["index"]["const"]
            label = f"({r}, {c})"
        elif ref == "cellset":                        # blob: resolved 이동식이 있으면 ①과 같은 표현식, 없으면 raw
            cl = tgt["cells"]
            var = cl.get("var") if isinstance(cl, dict) else None
            if slot_exprs and var in slot_exprs:      # ③ 을 ① text(render_solution_lines)와 같은 함수식으로
                rt, ct, _sel = SE._split_move(slot_exprs[var])
                label = SE.move_to_vector(rt, ct, "obj0") if rt else "coordinate(obj0)"
                resolved = True
            else:                                     # 구체 blob(compress 객체 program 등): flat idx → (row,col)
                cells = cl.get("const") if (isinstance(cl, dict) and "const" in cl) else cl
                if cell_w and isinstance(cells, list) and cells and all(isinstance(x, int) for x in cells):
                    label = str([(i // cell_w, i % cell_w) for i in cells])   # "cellset" 제거, 좌표로
                else:
                    label = f"cellset={_disp_leaf(cl)}"
        else:
            label = f"? /* 해석 불가 target: {json.dumps(tgt)} */"
        steps.append({"g_from": prev, "g_to": cur, "ref": ref, "label": label,
                      "color": s["args"]["color"], "resolved": resolved})
        prev = cur
    return steps


def _coloring_seq_lines(body, slot_exprs=None):
    """_coloring_steps(공통 재료) → 순차 대입 텍스트 라인들. g0 = g.contents(하강 전 원본 contents)
    로 시작해, 각 coloring 스텝을 gN = coloring(gN-1, label, color) 로 threading(∘ 합성 폐기 —
    사고 단위를 한 줄씩 순차 statement 로). 빈 body(0 스텝)도 러너-안전한 identity(g0→result)로 남긴다.
    slot_exprs(선택) = TASK.solution cellset 변수 → resolved 이동식(명확 표현)."""
    lines = ["g0 = g.contents"]
    steps = _coloring_steps(body, slot_exprs)
    for st in steps:
        col = _disp_leaf(st["color"])
        if st["ref"] != "cellset":
            suffix = ""
        elif st.get("resolved"):
            suffix = "  # move 표현식(resolved slot)"
        else:
            suffix = "  # 해석 불가(다중좌표 — 러너 미지원)"
        lines.append(f"{st['g_to']} = coloring({st['g_from']}, {st['label']}, {col}){suffix}")
    lines.append(f"result = {steps[-1]['g_to'] if steps else 'g0'}")
    return lines


def _display_grid(body, slot_exprs=None):
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
        lines.extend(_coloring_seq_lines(ct["program"]["body"], slot_exprs))
        lines.append("g.contents = set_grid_contents(result)")
    else:
        lines.append(f"g.contents = set_grid_contents({_disp_grid_leaf(ct, 'contents')})")
    lines.append("output_grid = g")
    return "\n".join(lines)


_ACCESSOR = {"pixel": "pixels_of", "object": "objects_of"}


def _display_pixel(body, slot_exprs=None):
    lines = ["g = input_grid"]
    for s in body:
        tgt = s["args"]["target"]
        col = _disp_leaf(s["args"]["color"])
        ref = tgt.get("ref")
        if ref in _ACCESSOR:                          # pixel/object: 단일 좌표 채색
            idx = _disp_leaf(tgt["index"])
            lines.append(f"g = coloring(g, {_ACCESSOR[ref]}(input_grid)[{idx}].coord, {col})")
        elif ref == "coord":                          # 리터럴 좌표 직접
            r, c = tgt["index"]["const"]
            lines.append(f"g = coloring(g, ({r}, {c}), {col})")
        elif ref == "cellset":                        # blob: 셀 집합. resolved 이동식 있으면 명확화
            cl = tgt["cells"]
            var = cl.get("var") if isinstance(cl, dict) else None
            if slot_exprs and var in slot_exprs:
                lines.append(f"g = move_recolor(g, {_pretty_move(slot_exprs[var])}, {col})")
            else:
                cells = _disp_leaf(cl)
                lines.append(f"for ix in {cells}:\n    g = coloring(g, divmod(ix, width(input_grid)), {col})")
        else:
            lines.append(f"# 해석 불가 target: {json.dumps(tgt)}")
    lines.append("output_grid = g")
    return "\n".join(lines)


def display_source(ast, slot_exprs=None):
    """AST → 통일 body 소스(뷰어 로컬). grid/pixel 계열 모두 실행형 'g = fn(g, …)'.
    to_source(파싱 계약) 와 독립 — 같은 AST 를 일관 프레이밍만(표현 계열은 그대로 드러남).
    slot_exprs(선택) = TASK.solution cellset 변수 → resolved 이동식(명확 표현). PAIR program 은
    slot_exprs=None(러너-안전 유지) — solution 렌더에서만 명확화한다."""
    body = (ast or {}).get("body") or []
    if not body:
        return "g = input_grid\noutput_grid = g"
    if PA._is_grid_body(body):
        return _display_grid(body, slot_exprs)
    return _display_pixel(body, slot_exprs)


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
    """(pair_asts, pair_indices, solution_ast, attempts, slot_exprs, slots, groupings) 반환.
    program/solution 없으면 각각 [] / None(정직하게 미해결).
    pair_indices[k] = asts[k] 가 실제로 속한 train index — 중간 pair 에 program 이 없으면
    asts 의 리스트 위치가 train index 와 어긋나므로, 그 실제 index 를 나란히 carry 한다
    (T5 index-carry 가드 — false-green 방지: 다른 pair 의 input 과 program 이 잘못 짝지어지는 것 방지).
    slot_exprs = {`?c.cellsN` → resolved 이동식} — WM 의 `T.property ^resolved` 에서 수집,
    solution 의 cellset 변수를 명확한 move 표현식으로 렌더하는 데 쓴다(§사용자 2026-07-20).
    slots = {`?c.X` → [pair0_cells, pair1_cells, ...]} — WM 의 `T.property ^slot` 에서 수집,
    shape# 선택자의 실제 mover shape 를 재구성(_shapes_for)하는 데 쓴다(Task 5).
    groupings[k] = asts[k]/pairs[k] 와 같은 위치의 객체(blob) program AST(WM `P{k}.property ^grouping`,
    compress operator 가 남김 — procedural_memory/operators/compress.py:247) — 없으면 None(정직).
    pixel program(asts[k])과 groupings[k]는 같은 grid-body AST 형태(§_viz 가 이미 다루는 형태)이고,
    차이는 nested coloring target(pixel index 다건 vs cellset 소수건)뿐이라 새 파서 없이 그대로
    _viz 로 렌더할 수 있다(Task 6 — Step B compress 단계 시각화)."""
    try:
        from debugger.solve_cache import run_solve
        r = run_solve(tid, task, max_cycles=500)      # 1회 solve(+캐시) — dashboard 와 공유(재실행 X)
    except Exception:                                 # noqa: BLE001 — 리포트 생성용, 한 태스크 예외가 전체를 죽이지 않게
        return [], [], None, [], {}, {}, []
    wm, attempts = r["wm"], r["attempts"]
    T = f"T{tid}"
    asts = []
    pairs = []
    groupings = []
    for k in range(len(task["train"])):
        v = next((v for (i, a, v) in wm if i == f"{T}.P{k}.property" and a == "program"), None)
        if v in (None, "{}"):
            continue
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
            pairs.append(k)
            gv = next((v for (i, a, v) in wm if i == f"{T}.P{k}.property" and a == "grouping"), None)
            g_ast = None
            if gv not in (None, "{}"):
                try:
                    g = json.loads(gv)
                except (ValueError, TypeError):
                    g = None
                if g and g.get("body"):
                    g_ast = g
            groupings.append(g_ast)
    sol_v = next((v for (i, a, v) in wm if i == f"{T}.property" and a == "solution"), None)
    solution = None
    if sol_v not in (None, "{}"):
        try:
            sol = json.loads(sol_v)
        except (ValueError, TypeError):
            sol = None
        if sol and sol.get("body"):
            solution = sol
    slot_exprs = {}                                   # `?c.cellsN` → resolved 이동식 (명확 표현용)
    for (i, a, v) in wm:
        if a == "resolved" and isinstance(v, str) and v.startswith("?c.") and "=" in v:
            var, _, rhs = v.partition("=")            # 첫 '=' 기준 (rhs 의 BR=2·color=2 는 보존)
            slot_exprs[var.strip()] = rhs.strip()
    slot_vals = {}                                    # {?c.X: [pair0_cells, pair1_cells, ...]}
    for (i, a, v) in wm:
        if a == "slot" and isinstance(v, str) and v.startswith("?c."):
            nm = v.split("[", 1)[0]
            mm = re.search(r"=(?:DIFF|COMM)?(\[.*\])$", v)
            if mm:
                try:
                    slot_vals[nm] = json.loads(mm.group(1))
                except (ValueError, TypeError):
                    pass
    return asts, pairs, solution, attempts, slot_exprs, slot_vals, groupings


# ── Step 2a: ② AST 트리 — 원본 dict/list(JSON) 를 그대로 nested 렌더 ──────────────────────────
def _is_matrix(v):
    """grid 리터럴(정수 2차원 리스트) 판별 — 이 경우만 셀 하나하나를 <li> 로 안 풀고 컴팩트 행렬로."""
    return isinstance(v, list) and bool(v) and all(
        isinstance(row, list) and all(isinstance(x, int) for x in row) for row in v)


def _slot_expr_leaf(rv):
    """resolved 슬롯값 → ①③과 같은 함수식 (move[..]→벡터식, color@..→color(obj0))."""
    if rv.startswith("move["):
        rt, ct, _sel = SE._split_move(rv)
        return SE.move_to_vector(rt, ct, "obj0") if rt else "coordinate(obj0)"
    if rv.startswith("color@"):
        return "color(obj0)"
    return rv


def ast_tree(node, slot_exprs=None):
    """② AST 트리. slot_exprs(선택) 있으면 TASK.solution 의 cellset/color 슬롯 var 노드를 ①③과 같은
    함수식 leaf 로 치환한다(사용자 2026-07-20: ②도 ①에 맞춰 표현식으로)."""
    if slot_exprs and isinstance(node, dict):
        if "var" in node and node["var"] in slot_exprs:               # ?c.colorN 등 직접 var
            return f'<span class="leaf">{html.escape(_slot_expr_leaf(slot_exprs[node["var"]]))}</span>'
        if node.get("ref") == "cellset":                              # cellset target 통째
            cv = (node.get("cells") or {}).get("var")
            if cv in slot_exprs:
                return f'<span class="leaf">{html.escape(_slot_expr_leaf(slot_exprs[cv]))}</span>'
    if isinstance(node, dict):
        lis = []
        for k, v in node.items():
            if slot_exprs and str(k) in slot_exprs:                   # slots 딕셔너리 키(?c.cellsN) → 표현식
                lis.append(f'<li><span class="leaf">{html.escape(_slot_expr_leaf(slot_exprs[str(k)]))}</span></li>')
            else:
                lis.append(f'<li><span class="k">{html.escape(str(k))}</span>{ast_tree(v, slot_exprs)}</li>')
        return f'<ul class="astree">{"".join(lis)}</ul>'
    if _is_matrix(node):
        mat = "\n".join(" ".join(str(x) for x in row) for row in node)
        return f'<pre class="astmat">{html.escape(mat)}</pre>'
    if isinstance(node, list):
        if not node:
            return '<span class="leaf">[]</span>'
        rows = "".join(f'<li>{ast_tree(v, slot_exprs)}</li>' for v in node)
        return f'<ul class="astree astlist">{rows}</ul>'
    return f'<span class="leaf">{html.escape(json.dumps(node))}</span>'


# ── TASK.solution 표현식 코드 → 트리(②)/박스(③) — 하나의 코드를 구조로 렌더(사용자 2026-07-20) ──
def _expr_tree_html(node):
    """expr AST 노드 → 중첩 트리 <li>(SE.node_label_children 소비)."""
    label, children = SE.node_label_children(node)
    lab = f'<span class="etn">{html.escape(str(label))}</span>'
    if not children:
        return f'<li>{lab}</li>'
    inner = "".join(_expr_tree_html(c) for c in children)
    return f'<li>{lab}<ul class="et">{inner}</ul></li>'


def _program_tree_html(lines, box=False):
    """표시줄(코드) 전체 → 문장별 중첩 트리. ②=AST 트리, ③=박스형(progbox) — 같은 파싱, CSS 로만 구분."""
    lis = []
    for st in SE.parse_program(lines):
        if st["k"] == "assign":
            lis.append(f'<li><span class="asn">{html.escape(st["lhs"])} =</span>'
                       f'<ul class="et">{_expr_tree_html(st["rhs"])}</ul></li>')
        else:
            lis.append(_expr_tree_html(st["e"]))
    return f'<ul class="astree prog{" progbox" if box else ""}">{"".join(lis)}</ul>'


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
            return f"({v['height']}, {v['width']})"        # 리터럴 크기값 (사용자: '(8,8) 같은 값')
        return json.dumps(v)                          # color list / contents 2D 배열 실값(grid[NxN] 폐기)
    return str(leaf)


def _contents_cell(leaf, cls=""):
    """set_grid_contents leaf → 시각화 셀. const 2D 배열이면 줄바꿈 matrix(<pre>), 아니면 콤팩트 라벨.
    cls(선택) = Step B overlay COMM/DIFF outline class(§_compare_asts)."""
    if "const" in leaf and _is_grid_literal(leaf["const"]):
        mat = "\n".join(" ".join(str(x) for x in row) for row in leaf["const"])
        cls_attr = f" {cls}" if cls else ""
        return f'<pre class="cmat{cls_attr}">{html.escape(mat)}</pre>'
    return colr(_grid_leaf_repr(leaf, "contents"), cls)


def _swatches(colors):
    return "".join(f'<i class="swatch" style="background:{PAL[c % 10]}"></i>' for c in colors)


def _colorval(colr_html, swatch_html):
    """색값 박스 + 색 스와치를 항상 한 줄에 붙는 non-breaking 단위로 묶는다 — flex-wrap 에서 스와치가
    다음 줄로 갈라지지 않고 늘 색값 박스 우측에 붙도록(§색스와치 우측 고정 통일)."""
    return f'<span class="cvwrap">{colr_html}{swatch_html}</span>'


# ── §11 grid 썸네일 크리스프니스: 이 파일 로컬 렌더러 (grid 는 다른 리포트와 공유 — 수정 금지) ──
# 근본원인: grid 는 CSS grid(각 셀 = <i>, gap:1px+border)로 그린다 — 브라우저가 비정수
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
        f'<rect x="{c * cell}" y="{r * cell}" width="{fill}" height="{fill}" fill="{PAL[v % 10]}"/>'
        for r, row in enumerate(gr) for c, v in enumerate(row))
    return (f'<svg class="vthumb" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">{rects}</svg>')


def _endpoint_rows(ex):
    """공통 끝점: (input_grid 행, output_grid 행) — input/output 썸네일 인라인(G0/G1 개념 없음 —
    ①③ 이 실제로 쓰는 이름 그대로 input_grid/output_grid). 썸네일은 grid(다른 리포트와 공유,
    수정 금지) 대신 이 파일 로컬 _thumb(§11 grid crispness)."""
    g0 = (f'<div class="row"><span class="bx grid">input_grid</span>{_thumb(ex["input"])}'
          f'</div><div class="v"></div>')
    g1 = f'<div class="row"><span class="bx grid">output_grid</span>{_thumb(ex["output"])}</div>'
    return g0, g1


def _coloring_flow_rows(body, outline=None, slot_exprs=None, cell_w=None):
    """③ 중첩 coloring 시각화 — ①(_coloring_seq_lines)과 정확히 같은 _coloring_steps(공통 재료)를
    소비해, 각 coloring 스텝을 op box + target label + color value(+swatch) 노드로 그린다
    (§①②③ 공통소스 원칙 — 모듈 docstring 참고). g0/result 캡션과 g_from/g_to 변수 라벨은 ①(텍스트)
    전용 배관(순차 대입 threading)이라 ③(시각화)에는 굳이 필요 없어 표시하지 않는다 — ①③ 이 같은
    _coloring_steps 재료를 소비하는 사실 자체는 그대로 유지, 포맷팅만 이 계층에서 덜어낸다.
    outline(선택) = Step B anti-unification overlay 용 포지션별 {'idx','col'} outline class
    (§Step B COMM/DIFF — _compare_asts 가 만든 결과를 그대로 소비, 여기서 새로 판정하지 않는다).
    slot_exprs(선택) = TASK.solution cellset 변수 → resolved 이동식(①과 같은 명확 표현)."""
    steps = _coloring_steps(body, slot_exprs, cell_w)
    rows = []
    for i, st in enumerate(steps):
        col_leaf = st["color"]
        col = col_leaf.get("const")
        sw = _swatches([col]) if isinstance(col, int) else ""
        o = outline[i] if (outline and i < len(outline)) else {}
        cvar = col_leaf.get("var")                    # ?c.colorN(slot) → color(obj0) (①과 일치)
        col_txt = "color(obj0)" if (slot_exprs and cvar in slot_exprs) else _disp_leaf(col_leaf)
        rows.append(
            f'<div class="row">{opb("coloring")}<span class="h"></span>'
            f'{dest_box(st["label"], o.get("idx", ""))}<span class="h"></span>'
            f'{_colorval(colr(col_txt, o.get("col", "")), sw)}</div><div class="v"></div>')
    return rows


def _grid_step_rows(ast, outline=None, slot_exprs=None, cell_w=None):
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
        f'<div class="row">{opb("set_grid_size")}<span class="h"></span>{colr(_grid_leaf_repr(sz, "size"), size_cls)}</div>',
        f'<div class="row">{opb("set_grid_color")}<span class="h"></span>{_colorval(colr(_grid_leaf_repr(co, "color"), color_cls), color_sw)}</div>',
    ]
    if "program" in ct:                        # contents = 하강 coloring 합성 → 중첩 box-flow(①과 같은 재료)
        top.append(f'<div class="row">{opb("set_grid_contents")}</div>')
        step_outline = outline["contents"]["steps"] if outline else None
        inner_rows = _coloring_flow_rows(ct["program"]["body"], step_outline, slot_exprs, cell_w)
        body_html = "".join(top) + f'<div class="nestedflow">{"".join(inner_rows)}</div>'
    else:
        contents_cls = outline["contents"]["cls"] if outline else ""
        top.append(f'<div class="row">{opb("set_grid_contents")}<span class="h"></span>'
                    f'{_contents_cell(ct, contents_cls)}</div>')
        body_html = "".join(top)
    return [f'<div class="gflow">{body_html}</div><div class="v"></div>']


def _pixel_step_rows(ast, outline=None, slot_exprs=None, cell_w=None):
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
        elif ref == "coord":
            r, c = tgt["index"]["const"]
            label = f"({r}, {c})"
        elif ref == "cellset":
            cl = tgt["cells"]
            var = cl.get("var") if isinstance(cl, dict) else None
            label = (_pretty_move(slot_exprs[var]) if slot_exprs and var in slot_exprs
                     else f"cells {_disp_leaf(cl)}")
        else:
            label = "?"
        o = steps_outline[i] if (steps_outline and i < len(steps_outline)) else {}
        rows.append(f'<div class="row">{opb("coloring")}<span class="h"></span>'
                    f'{dest_box(label, o.get("idx", ""))}<span class="h"></span>'
                    f'{_colorval(colr(_disp_leaf(col_leaf), o.get("col", "")), sw)}</div>'
                    f'<div class="v"></div>')
    return rows


def _viz(ast, ex, ghost=False, outline=None, slot_exprs=None, endpoints=True):
    """두 계열 공통 box-flow: input_grid 썸네일 → 스텝들 → output_grid 썸네일.
    ghost=True 면 overlay(§8 TASK.solution 가로 레이아웃 중간 열)용 반투명 사본
    (easy_antiunify_viz.flow(ghost=True) 와 같은 클래스 이름 재사용 — .ovl/.ghost CSS 는 _EV_CSS 것).
    outline(선택) = _compare_asts() 가 낸 Step B COMM/DIFF class dict — 끝점(input_grid/output_grid)
    행에는 적용하지 않는다(§Step B — 끝점은 비교/표기 대상 밖).
    slot_exprs(선택) = TASK.solution cellset 변수 → resolved 이동식(①과 같은 명확 표현).
    endpoints=False 면 input/output grid 썸네일을 뺀다 — Step B overlay 에서 두 겹치는 flow 의 크기가
    격자(납작/세로긴) 차이로 어긋나 열이 안 맞던 문제 해결(사용자 2026-07-20: 겹치는 두 그림은 완전히
    같은 크기여야 한다 → 끝단 grid 제외, step 박스만 정렬 비교)."""
    g0, g1 = _endpoint_rows(ex) if endpoints else ("", "")
    cw = len(ex["input"][0]) if ex.get("input") else None      # flat cellset idx → (row,col) 변환용
    steps = (_grid_step_rows(ast, outline, slot_exprs, cw) if PA._is_grid_body(ast.get("body") or [])
             else _pixel_step_rows(ast, outline, slot_exprs, cw))
    cls = "flow ghost" if ghost else "flow"
    return f'<div class="{cls}">{g0}{"".join(steps)}{g1}</div>'


# ── Step B compress 단계: pair0 픽셀 program → 4-인접 동색 그룹핑(compress) → 객체 program ────────
def _compress_stages(pixel_ast, group_ast, ex):
    """pair0 의 픽셀 program(WM `P{k}.property ^program`)과 그 compress 결과 객체 program
    (WM `P{k}.property ^grouping`)을 가로로 이어 그린다. 새 렌더러를 만들지 않고 둘 다 같은
    grid-body AST 형태라 기존 _viz(①②③ 공통소스 원칙과 같은 취지 — box-flow 렌더는 한 곳)를
    그대로 재사용, 사이에 라벨 붙은 화살표 연결 노드(.cconn)만 추가한다."""
    pixel_viz = _viz(pixel_ast, ex)
    group_viz = _viz(group_ast, ex)
    conn = ('<div class="cconn"><span class="cconnarrow">→</span>'
            '<span class="cconnlab">4-인접 동색 그룹핑<br>(compress)</span></div>')
    return (f'<div class="compressbox"><div class="lab">COMPRESS · 픽셀 → 객체</div>'
            f'<div class="compressscroll"><div class="compressrow">'
            f'<div class="cstage"><div class="cstagelab">픽셀 program</div>{pixel_viz}</div>'
            f'{conn}'
            f'<div class="cstage"><div class="cstagelab">객체 program</div>{group_viz}</div>'
            f'</div></div></div>')


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


def _solution_comm(pair_asts):
    """pair0/pair1 program 의 set_grid_size/color COMM(값 동일) 여부. pair<2 면 전부 COMM 취급."""
    if len(pair_asts) < 2:
        return {"size": True, "color": True}
    p0 = {s["call"]: s["args"] for s in pair_asts[0].get("body", [])}
    p1 = {s["call"]: s["args"] for s in pair_asts[1].get("body", [])}

    def _same(call, key):
        a = p0.get(call, {}).get(key); b = p1.get(call, {}).get(key)
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return {"size": _same("set_grid_size", "size"), "color": _same("set_grid_color", "color")}


def _shapes_for(resolved, slots, train_inputs):
    """shape# 선택자 참조 → mover(pair0) 객체 shape 2d array(1=채움,-1=빈칸). 없으면 {}.
    §검증(2026-07-20): `_obj_atoms`(arbor/reasoning/antiunify.py) 는 bbox 좌표 원자(r0,c0,r1,c1,h,w,…)
    만 반환하고 'shape' 키가 없다 — ARCKG object 클래스를 거치지 않는 여기서는 mover cells 로부터
    직접 bbox 2D array 를 만든다(ARCKG object.py::to_json()['shape'] 와 동일 컨벤션: bbox, 채움=1,
    빈칸=-1 — arbor/perception/arckg/object.py 라인 137-141 확인)."""
    from arbor.reasoning.antiunify import _components
    refs = {}
    for val in resolved.values():
        sel = SE._sel_of(val)
        if not (sel and sel.startswith("shape#")):
            continue
        ref = f"shape{sel[len('shape#'):]}"
        if ref in refs:
            continue
        # mover(pair0): resolved cellset DIFF pair0 셀 인덱스가 속한 객체
        cell_slot = next((n for n, v in resolved.items() if v == val and n.startswith("?c.cells")), None)
        p0cells = (slots.get(cell_slot) or [[]])[0] if cell_slot else []
        if not (p0cells and train_inputs):
            continue
        g0 = train_inputs[0]; W = len(g0[0])
        want = {(i // W, i % W) for i in p0cells}
        for cells, _col in _components(g0):
            if want & set(cells):
                rs = [r for r, _ in cells]; cs = [c for _, c in cells]
                r0, c0, r1, c1 = min(rs), min(cs), max(rs), max(cs)
                cset = set(cells)
                shape = [[1 if (r, c) in cset else -1 for c in range(c0, c1 + 1)]
                         for r in range(r0, r1 + 1)]
                refs[ref] = shape
                break
    return refs


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


def _grid_2d_literal(grid, var="input_grid"):
    """2D 정수격자 리터럴을 행마다 줄바꿈해 직사각형으로 렌더('var = [' 여는 괄호 아래로 각 행 정렬).
    <pre class=hdr>(white-space:pre-wrap) 안이라 개행·공백이 그대로 보인다 — 한 줄로 주욱 늘어지던
    것 방지(사용자 2026-07-19). 격자(2D 리스트)가 아니면(1D·스칼라) 기존대로 한 줄 json."""
    prefix = f"{var} = "
    if not (isinstance(grid, list) and grid and all(isinstance(r, list) for r in grid)):
        return prefix + json.dumps(grid)
    indent = " " * (len(prefix) + 1)                    # 여는 '[' 다음 열에 각 행을 정렬(직사각형)
    return prefix + "[" + (",\n" + indent).join(json.dumps(r) for r in grid) + "]"


def _render_header_safe(ast, g0):
    body = ast.get("body") or []
    if not PA._is_grid_body(body):
        # program_ast(read-only)의 헤더 문자열에서 한 줄 input_grid literal 만 2D 모양으로 후처리
        # (grid_in==g0, 양쪽 json.dumps 기본 separators 동일 → 문자열 일치; 불일치 시 no-op).
        txt = PA.render_header(ast, g0)
        return txt.replace(f"input_grid = {json.dumps(g0)}", _grid_2d_literal(g0))
    parts = {s["call"]: s["args"] for s in body}
    lines = ["# --- DSL (used) ---"]
    for name in ("set_grid_size", "set_grid_color", "set_grid_contents"):
        if name in parts:
            lines.append(f"# {_GRID_SIG[name]}")
    ct = parts.get("set_grid_contents", {}).get("contents", {})
    if "program" in ct:                        # contents 가 하강 coloring 합성일 때만(§1) 병기
        lines.append(f"# {_COLORING_SIG}")
    lines += ["# --- input (this pair) ---", _grid_2d_literal(g0)]
    return "\n".join(lines)


# ── 3-뷰 한 pair(또는 TASK.solution) 블록 (①②③ 은 같은 AST 의 세 표현 — 모듈 docstring 참고) ──
def _pair_block(label, ast, ex, slot_exprs=None, sol_lines=None):
    """sol_lines(선택) = SE.render_solution_lines 결과. 있으면 TASK.solution 이므로 ①=그 텍스트,
    ②=그 코드의 AST 트리, ③=그 코드의 박스형 시각화(하나의 코드를 세 표현으로 — 사용자 2026-07-20).
    없으면(PAIR program) 기존대로 ①=display_source(러너-안전)·②=raw AST·③=grid box-flow."""
    g0 = ex["input"]
    if sol_lines is not None:
        src_text = "\n".join(sol_lines)
        tree2 = _program_tree_html(sol_lines)
        viz3 = _program_tree_html(sol_lines, box=True)
    else:
        src_text = display_source(ast, slot_exprs)
        tree2 = ast_tree(ast, slot_exprs)
        viz3 = _viz(ast, ex, slot_exprs=slot_exprs)
    return (f'<div class="pair">'
            f'<div class="lab">{html.escape(str(label))}</div>'
            f'<div class="views">'
            f'<div class="view"><div class="vt">① text (통일 body · 실행형)</div>'
            f'<pre class="hdr">{html.escape(_render_header_safe(ast, g0))}</pre>'
            f'<pre class="src">{html.escape(src_text)}</pre></div>'
            f'<div class="view"><div class="vt">② AST 트리</div>{tree2}</div>'
            f'<div class="view viz"><div class="vt">③ 시각화</div>{viz3}</div>'
            f'</div></div>')


# ── Step A/B/C 카드 레이아웃(2026-07-17 재구성): Step A(PAIR.program — pair 별 ①②③ 를 세로
#    stack, top-aligned) → Step B(anti-unification — ①과 같은 ③ overlay, 카드 안에서 수직 중앙)
#    → Step C(TASK.solution — 카드 안에서 박스 자체는 수직 중앙, 박스 내부 ①②③ 은 top-aligned
#    그대로). 셋을 색으로 구분된 카드에 담아 한 컨테이너(가로 스크롤)에 나란히 놓는다. overlay 는
#    easy_antiunify_viz.flow(ghost=True)/.ovl·.ghost 와 같은 기법 재사용(반투명 겹침) — _EV_CSS 에
#    이미 있는 .ovl/.ghost 를 그대로 쓴다(중복 정의 안 함).
def _solution_row(ast_ex_pairs, solution, slot_exprs=None, sol_lines=None, groupings=None):
    pair_boxes = "".join(
        f'<div class="innerbox">{_pair_block(f"PAIR {p + 1}", a, ex)}</div>'
        for a, ex, p in ast_ex_pairs)
    steps = [f'<div class="stepcard stepA"><div class="stepttl">Step A · PAIR.program</div>{pair_boxes}</div>']

    if len(ast_ex_pairs) >= 2:
        a0, ex0, _p0 = ast_ex_pairs[0]
        a1, ex1, _p1 = ast_ex_pairs[1]
        # pair0(solid layer) vs pair1(ghost) 을 step-by-step 비교(끝점 grid 는 비교 밖 — _viz 의
        # outline 은 gflow/nestedflow 스텝에만 적용되고 _endpoint_rows 는 outline 인자를 받지 않는다)
        # → COMM(녹색 .comm)/DIFF(빨강 .diff) outline 을 solid layer 에 입힌다(_EV_CSS 재사용, 신규
        # 색 정의 없음). solid+ghost 겹침 자체는 기존 .ovl/.ghost 그대로.
        outline = _compare_asts(a0, a1)
        overlay = (f'<div class="ovl">{_viz(a0, ex0, outline=outline, endpoints=False)}'
                   f'{_viz(a1, ex1, ghost=True, endpoints=False)}</div>'
                   f'<div class="legend"><span class="lg comm">COMM(일치) = 녹색</span>'
                   f'<span class="lg diff">DIFF(어긋남) = 빨강</span></div>')
        box = f'<div class="innerbox"><div class="lab">PROGRAM COMPARISON</div>{overlay}</div>'
        # compress 단계(Task 6): pair0 픽셀 program → 4-인접 그룹핑 → 객체 program. groupings[0] 이
        # 있는 태스크(compress 가 실제로 돈 태스크 — arc_human/move 전체)에서만 표시(정직 — 없는
        # 태스크에 임의로 지어내지 않는다). PROGRAM COMPARISON 박스 오른쪽에 나란히(.stepBrow).
        compress_html = _compress_stages(a0, groupings[0], ex0) if (groupings and groupings[0]) else ""
        steps.append(f'<div class="stepcard stepB"><div class="stepttl">Step B · Anti-unification</div>'
                     f'<div class="stepBcontent"><div class="stepBrow">{box}{compress_html}</div></div></div>')

    if solution is not None:
        sol_ex = ast_ex_pairs[0][1]
        sol_box = f'<div class="innerbox">{_pair_block("TASK.solution (anti-unify 골격)", solution, sol_ex, slot_exprs, sol_lines)}</div>'
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

    asts, pairs, solution, attempts, slot_exprs, slot_vals, groupings = (
        precomputed if precomputed else _collect(tid, task))
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
        extra = _attempts_block(attempts, tp) if attempts else ""
        return (f'<section class="task" id="{tid}"><h2>{tid}<span class="na">미합성/크기변화</span></h2>'
                f'<div class="thumbs">{thumbs}</div><p class="note">{html.escape(why + done)}</p>{extra}</section>')

    ast_ex_pairs = [(a, task["train"][p], p) for a, p in zip(asts, pairs)]
    sol_lines = None
    if solution is not None and PA._is_grid_body(solution.get("body") or []):
        comm = _solution_comm(asts)
        shapes = _shapes_for(slot_exprs, slot_vals, [task["train"][p]["input"] for p in pairs])
        sol_lines = SE.render_solution_lines(solution, slot_exprs, comm, shapes)
    solrow = _solution_row(ast_ex_pairs, solution, slot_exprs, sol_lines, groupings)

    return (f'<section class="task" id="{tid}"><h2>{tid}</h2>'
            f'<div class="thumbs">{thumbs}</div>{solrow}</section>')


CSS = """
/* 영역 폭 고정(2026-07-17 반전 — 사용자 요청): 이전엔 max-width:100% 로 각 박스(.view/.stepcard/
   .innerbox/.gflow/.nestedflow 등)를 뷰포트 폭에 맞춰 축소/줄바꿈시켰다(§2026-07-17 "가로스크롤
   제거"). 사용자가 그 반대를 원함 — 뷰포트를 좁혀도(줌 축소·창 좁힘) 각 영역이 줄어들거나 reflow
   되지 않고 원래(자연) 폭을 유지해야 하며, 대신 전체 폭이 넘치면 가로 스크롤바가 나타나는 편이
   낫다. 그래서 그 max-width:100%/min-width:0(축소 훅)들을 여기서 되돌린다 — flex-shrink:0(=고정
   폭, 줄어들지 않음)로 바꾸고, 넘친 폭은 페이지 레벨 가로 스크롤 하나로 받는다(중첩 스크롤바
   방지 — 안쪽 .flow 의 개별 overflow-x:auto 도 함께 제거). box-sizing:border-box 는 자연폭 계산에
   영향 없어 그대로 둔다. _EV_CSS(옛 easy_antiunify_viz.CSS 인라인분)는 그대로 두고(수정 금지) —
   이 CSS(program_report local)는 build() 가 만드는 style 태그 안에서 _EV_CSS 뒤에 이어붙는 부분에만
   적용된다.
   (주의: 이 주석/CSS 텍스트 안에 리터럴 "style 닫는 태그" 문자열을 쓰지 말 것 — HTML 파서는 <style>
   요소를 raw-text 로 취급해 그 문자열이 나오면 안의 내용이 주석이든 아니든 그 자리에서 즉시 스타일
   블록을 끝내버려, 그 뒤 CSS 전부가 화면에 그냥 텍스트로 노출되는 사고가 난다 — 실제로 한 번 냈던
   실수라 여기 남겨 재발 방지.) */
*,*::before,*::after{box-sizing:border-box}
/* 최상단 문제 리스트 박스: 풀림=초록·안풀림=빨강 테두리(§2-5 풀이상태 가시화). _EV_CSS(.tabs a.on)
   뒤에 와서 우선 → 현재 선택 탭(.on 파란 배경)에서도 풀이상태 테두리가 유지된다. */
.tabs a.solved{border-color:#3fb950}
.tabs a.unsolved{border-color:#f85149}
.views{display:flex;gap:10px;align-items:flex-start;flex-wrap:nowrap;margin:6px 0 14px}
.view{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;flex:0 0 auto}
/* ③ 시각화 pane 만 폭을 더 넓게: 색값 박스가 한 줄에서 안 밀려나려면 ③ pane 자체가 coloring
   스텝 한 줄(op+target+color+swatch)을 담을 만큼 넓어야 한다. ①②(텍스트/AST 트리)는 원래 폭
   그대로 — 그쪽은 이미 잘 줄바꿈되므로 건드릴 필요 없다. */
.view.viz{flex-basis:480px}
.vt{font-size:11px;color:#8b93a3;text-transform:uppercase;letter-spacing:.03em;margin-bottom:8px;font-weight:700}
.src{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:8px 10px;
 font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#dfe3ea;white-space:pre-wrap;
 overflow-wrap:anywhere;margin:0}
.bind{background:#131a24;border:1px solid #2a3446;border-left:3px solid #4a83c0;border-radius:6px;
 padding:6px 9px;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:#bcd8f5;
 white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 8px}
.astree{list-style:none;margin:0;padding-left:14px;font:11.5px/1.6 ui-monospace,monospace}
.view>.astree{padding-left:0}
.astree li{border-left:1px dashed #2a3038;padding-left:10px;margin:2px 0}
.k{color:#7fb2e0;margin-right:6px}
.leaf{color:#e6c99a}
/* TASK.solution 코드 트리(② prog)·박스형(③ progbox) — 하나의 코드를 구조로 */
.prog{list-style:none;margin:0;padding-left:0}
.prog .et{list-style:none;margin:0;padding-left:13px}
.prog>li{border-left:none;padding:3px 0;margin:3px 0}
.prog .asn{color:#e0a552;font-weight:600;margin-right:6px}
.prog .etn{color:#bcd8f5}
.prog .et>li>.etn{color:#7fd0c0}          /* 함수/연산자 노드 */
.progbox{padding-left:0}
.progbox .etn{display:inline-block;border:1px solid #33506e;border-radius:5px;padding:0 6px;
 background:#16202c;color:#cfe3f5;margin:1px 0}
.progbox .et{padding-left:16px;border-left:2px solid #24384c}
.progbox .asn{display:inline-block;border:1px solid #6a5220;border-radius:5px;padding:0 6px;
 background:#2a2313;color:#e0a552}
.astmat{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 8px;margin:2px 0 2px 14px;
 font:11px/1.4 ui-monospace,monospace;color:#e6c99a}
.cmat{background:#0d1014;border:1px solid #232a35;border-radius:6px;padding:6px 9px;margin:0;
 font:11px/1.35 ui-monospace,monospace;color:#e6c99a;white-space:pre}
.swatch{display:inline-block;width:10px;height:10px;margin-left:2px;border-radius:2px;vertical-align:middle;
 border:1px solid rgba(255,255,255,.25)}
.cvwrap{display:inline-flex;align-items:center;flex:0 0 auto}
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
/* 폭 고정 반전(2026-07-17): _EV_CSS 의 .bx(공유·수정 금지) 기본값은 white-space:nowrap — 라벨을
   한 줄로 고정하는 자연폭 그대로가 이제 원하는 동작이라(pixels_of(input_grid)[35].coord 같은 긴
   accessor 라벨이 박스를 넓혀도 그게 정상 — §요구사항: 축소·줄바꿈 금지), 이전에 여기서 걸었던
   white-space:normal/overflow-wrap/word-break/min-width:0 override(라벨을 강제로 줄바꿈해 박스를
   좁게 유지하던 훅)를 제거한다 — 즉 이 문서도 _EV_CSS 기본값(.bx nowrap)을 그대로 쓴다. */
/* .row(coloring 한 줄 = op box+target box+색값 박스+스와치)는 pane 폭에 눌려도 다음 줄로 접히지
   않고 한 줄을 유지한다(KEEP — 색값 박스가 다음 줄로 떨어지던 버그의 고정, §사용자 리포트).
   폭 자체는 이제 pane(.view/.view.viz)이 축소되지 않으므로(위 .view flex:0 0 auto) 이 한 줄이
   pane 보다 넓어질 일이 거의 없고, 설령 넓어져도 .flow 안에서 자체 가로 스크롤을 열지 않는다 —
   중첩(이중) 스크롤바 대신 문서 전체를 담는 바깥 스크롤 하나로만 받는다(§한 개의 outer scroll). */
.flow .row{flex-wrap:nowrap}
/* Step A/B/C 카드 레이아웃(2026-07-17 재반전 — 사용자 요청): 셋을 색으로 구분된 카드에 담아
   한 행에 나란히 두고, 뷰포트가 좁아져도 카드를 다음 줄로 감싸거나(flex-wrap) 축소하지 않는다
   (flex-wrap:nowrap + .stepcard flex:0 0 auto = 고정폭) — 카드 내부(①②③ views, viz row)도 위의
   .view/.flow 폭 수정으로 자연폭 그대로다. 그 결과 항상 A→B→C 3 카드가 한 줄로 나란히 있고,
   전체 폭이 뷰포트를 넘치면 그 초과분은 카드가 줄어드는 대신 문서 전체의 가로 스크롤로 받는다
   (§한 개의 outer scroll — 카드 안에 개별 스크롤바를 새로 만들지 않음).
   .stepsrow 는 align-items:stretch(기본값) 라 같은 줄의 카드들은 그 줄에서 가장 높은 카드와 같은
   높이로 맞춰진다 — Step B/C 는 그 안에서 "카드 안 수직 중앙"을 flex column + justify-content:
   center 로 구현. Step A 는 stepttl 다음에 innerbox 들이 top-aligned 순서로 그냥 쌓인다. */
/* 회색 박스(.task)는 _EV_CSS 에서 block(폭=뷰포트)이라 가로스크롤 시 넘친 Step 을 안 감싼다.
   내용(Step A/B/C 전체) 폭에 맞게 늘려 세 Step 을 다 감싸도록 override(최소 뷰포트 폭 보장). */
.task{width:max-content;min-width:100%}
.stepsrow{display:flex;flex-wrap:nowrap;gap:14px;margin-top:10px}
.stepcard{flex:0 0 auto;display:flex;flex-direction:column;border-radius:12px;padding:14px 16px;
 box-sizing:border-box}
.stepttl{font-size:12px;font-weight:700;letter-spacing:.02em;margin-bottom:10px;white-space:nowrap}
.innerbox{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;
 box-sizing:border-box}
.innerbox + .innerbox{margin-top:12px}
/* Step A/C(각 ①②③ views 3열 또는 PAIR 세로 stack)는 Step B(overlay 하나, 컨텐츠가 원래 좁음)보다
   여분 폭을 더 받아야 같은 줄에서 ①②③ 이 세로로 다 눌리지 않고 최대한 나란히 남는다(flex-grow 만
   다르게 — 기본 배분이면 Step B 도 필요 이상으로 넓어지고 A/C 는 좁아져 뷰가 1열로 눌린다). */
.stepA,.stepC{flex-grow:3}
.stepB{flex-grow:1}
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
/* Step B "PROGRAM COMPARISON" overlay — 로컬 오버라이드(easy000g 겹침 버그 수정). _EV_CSS 의
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
.stepB .ovl{position:relative;padding:6px 30px 30px 6px;width:max-content}
.stepB .ovl .ghost{position:absolute;top:0;left:0;right:auto;bottom:auto;width:auto;height:auto;
 transform:translate(22px,22px);opacity:.4;pointer-events:none;filter:saturate(.7)}
/* Step B compress 단계(Task 6, 2026-07-20): PROGRAM COMPARISON 박스 오른쪽에 픽셀→객체 compress
   진행을 가로로 이어 보여준다(.stepBrow). 이 서브블록만 자체 max-width+overflow-x:auto 로 감싸
   (.compressscroll) — 픽셀 program 은 coloring 스텝이 많아 폭이 쉽게 넓어지므로, 이 새 블록이
   .stepB/.task/문서 전체의 가로폭을 계속 밀어 넓히는 대신 이 서브블록 안에서만 스크롤되게 한다
   (§Task 6 제약: 문서 body 는 가로 스크롤하지 않는다 — 넓은 내용은 자기 컨테이너 안에서). */
.stepBrow{display:flex;align-items:flex-start;gap:14px}
.compressbox{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px;
 max-width:640px;flex:0 1 auto;min-width:0}
.compressscroll{overflow-x:auto;max-width:100%}
.compressrow{display:flex;align-items:flex-start;gap:12px;width:max-content}
.cstage{display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.cstagelab{font-size:10px;color:#7a8698;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.cconn{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;
 min-width:96px;color:#c8a8f0;padding-top:34px;flex:0 0 auto}
.cconnarrow{font-size:20px;line-height:1}
.cconnlab{font-size:10px;text-align:center;line-height:1.35}
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
  // 구분하면 됨)와 g.prop = 식(mDot) 만으로 충분히 재현된다. 단, coord 타깃은 display_source 가
  // Python 튜플 표기 `(r, c)` 를 그대로 찍기 때문에 evalExpr(new Function 의 콤마연산자)로 넘기면
  // "(2, 8)" 이 배열이 아니라 콤마연산자로 평가돼(마지막 값 8) coloring 이 깨진다 — mCoord 로 그
  // 좌표 리터럴만 별도 파싱해 [r,c] 배열로 만들어 넘긴다(mDot/mFor 와 같은 급의 특수 분기).
  var lines = code.split("\n");
  for(var i=0;i<lines.length;i++){
    var ln = lines[i].trim();
    if(!ln || ln[0]==="#") continue;
    var mDot = ln.match(/^g\.(size|color|contents)\s*=\s*(.+)$/);   // 객체 속성 대입
    if(mDot){
      if(g===INPUT) g=_cloneObj(INPUT);
      // size 리터럴 (H, W): display 가 Python 튜플 표기를 찍으므로 evalExpr(new Function)로 넘기면
      // 콤마연산자로 붕괴(마지막 값 W)해 size 가 숫자가 됨 → mCoord 와 같은 급의 특수 파싱으로 방지.
      var mSz = (mDot[1]==="size") && mDot[2].match(/^set_grid_size\(\((\d+),\s*(\d+)\)\)$/);
      if(mSz){ g.size = {height:parseInt(mSz[1],10), width:parseInt(mSz[2],10)}; continue; }
      g[mDot[1]] = evalExpr(mDot[2]);
      continue;
    }
    var mFor = ln.match(/^for\s+(\w+)\s+in\s+(.+):$/);              // pixel cellset 루프
    if(mFor){ var it=evalExpr(mFor[2]); var b=lines[i+1].trim(); var mb=b.match(/^g\s*=\s*(.+)$/); i++;
      for(var k=0;k<it.length;k++){ ATOM[mFor[1]]=it[k];
        g=(new Function("ATOM","g","input_grid","divmod","with(ATOM){return ("+mb[1]+");}"))(ATOM,g,INPUT,ATOM.divmod); }
      continue; }
    var mCoord = ln.match(/^(\w+)\s*=\s*coloring\((\w+),\s*\((-?\d+),\s*(-?\d+)\),\s*(.+)\)$/);  // 좌표 리터럴 (r,c)
    if(mCoord){
      var _src = (mCoord[2]==="g") ? g : ATOM[mCoord[2]];
      var _pos = [parseInt(mCoord[3],10), parseInt(mCoord[4],10)];
      var _col = evalExpr(mCoord[5]);
      var _res = ATOM.coloring(_src, _pos, _col);
      if(mCoord[1]==="g") g=_res; else if(mCoord[1]==="output_grid") output=_res; else ATOM[mCoord[1]]=_res;
      continue;
    }
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


def _tab_label(tid):
    """탭 라벨: 접두 소문자+0 제거한 꼬리(easy000a→A · move000aa→AA). 없으면 전체 대문자."""
    i = 0
    while i < len(tid) and tid[i].isalpha() and tid[i].islower():
        i += 1
    while i < len(tid) and tid[i] == "0":
        i += 1
    return (tid[i:] or tid).upper()


def build(tids=None, dataset="easy", out_name="program_report.html",
          title="easy a–h program 뷰어", back_href="dashboard.html", back_label="dashboard"):
    """program 뷰어 HTML 생성(동일 구성 — 데이터셋만 갈아끼움). tids=None 이면 dataset 의 전 태스크."""
    paths = dict(list_tasks(dataset))
    if tids is None:
        tids = [t for t, _ in list_tasks(dataset)]
    tids = [t for t in tids if t in paths]                 # 존재하는 것만
    tasks = {t: load_task(paths[t]) for t in tids}
    runner_data = []
    secs_list = []
    solved = {}
    for t in tids:
        asts, pairs, solution, attempts, slot_exprs, slot_vals, groupings = _collect(t, tasks[t])
        solved[t] = bool(attempts) and any(a["correct"] for a in attempts)   # 정답 attempt 존재 = 풀림(task_section:606 과 동일)
        runner_data.extend(_runner_payload(t, asts, pairs, tasks[t]))
        secs_list.append(task_section(t, tasks[t], precomputed=(
            asts, pairs, solution, attempts, slot_exprs, slot_vals, groupings)))
    secs = "".join(secs_list)
    # 최상단 문제 리스트: solved 판정으로 초록/빨강 테두리 클래스 부여(§2-5). collect 뒤라 solved 확정됨.
    tabs = "".join(
        f'<a href="#{t}" data-t="{t}" class="{"solved" if solved[t] else "unsolved"}">{_tab_label(t)}</a>'
        for t in tids)
    js = ("<script>var TIDS=%s;function sh(){var h=location.hash.slice(1);"
          "if(!document.getElementById(h))h=TIDS[0];"
          "document.querySelectorAll('section.task').forEach(function(s){s.style.display=(s.id===h)?'':'none'});"
          "document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.t===h)});}"
          "addEventListener('hashchange',sh);sh();</script>") % json.dumps(tids)
    doc = (f'<!doctype html><meta charset="utf-8"><title>program 뷰어</title><style>{_EV_CSS}{CSS}</style>'
           f'<a class="back" href="{back_href}">← {back_label}</a>'
           f'<h1>{html.escape(title)}</h1>'
           f'<p class="hs">solve 실행 → WM 의 PAIR.program 을 통일 body(실행형)·단일 box-flow 로 렌더.'
           f' 하단 코드 실행기에서 body 를 실행/검증(빌드타임 parity ✓/✗).</p>'
           f'<div class="tabs">{tabs}</div>{secs}'
           f'<script>var RUNNER_DATA={json.dumps(runner_data)};</script>'
           f'{_RUNNER_HTML}{js}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_name)
    with open(out, "w") as f:
        f.write(doc)
    return out


def build_move():
    """arc_human/move 전 태스크 → move_program_report.html (동일 구성)."""
    return build(dataset="move", out_name="move_program_report.html",
                 title="move program 뷰어 (arc_human/move)",
                 back_href="move_dashboard.html", back_label="move_dashboard")


def build_objc():
    """object_coloring 전 태스크 → objc_program_report.html (동일 구성)."""
    return build(dataset="object_coloring", out_name="objc_program_report.html",
                 title="object_coloring program 뷰어",
                 back_href="objc_dashboard.html", back_label="objc_dashboard")


if __name__ == "__main__":
    import sys
    _arg = sys.argv[1] if len(sys.argv) > 1 else None
    if _arg == "move":
        p = build_move()
    elif _arg == "objc":
        p = build_objc()
    else:
        p = build()
    print("wrote", p, f"({os.path.getsize(p) / 1024:.0f} KB)")
