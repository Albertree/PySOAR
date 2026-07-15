"""Anti-unification view — reads the REAL stored program, no re-derivation:

    input_grid → coloring( in_px[i].coord , <colour> ) → coloring( in_px[j].coord , <colour> ) → output_grid

  ① 재료  : 두 example PAIR 의 실제 PAIR.program(AST-json) — 솔버(_Tracer)를 실제로 돌려 WM 에서
            그대로 읽는다(값 재추출·재계산 없음).
  ② 비교  : 그 두 AST 를 program_ast.antiunify_ast() 로 실제 비교한 결과 — COMM(겹침)/DIFF(어긋남)
            을 overlay(offset+반투명 ghost)로, 실제 슬롯 위치에만 outline.
  ③ TASK  : antiunify_ast() 가 낸 skeleton AST 를 그대로 렌더. COMM 위치는 상수 박스, DIFF 위치는
            실제 slot 변수(?src0 등, pair 별 관측값 포함) 박스. 실행부는 같은 솔버 실행에서 나온
            real attempts(hyp·정오)+제출 — 별도 채점 로직 없음.

각 열 상단에는 render_header(ast, g0) 를 그대로 박스로 띄운다 — 이 뷰가 실제 ARCKG/솔버 산출물과
연결돼 있음을(어떤 DSL accessor 를 썼는지 + 실제 input_grid) 보여준다 (harness P5).

이전 버전은 별도 스크립트가 손으로 재추출한 (fr,fc,H,W,tr,tc,color) 튜플과 자체 표현식 탐색으로
그림을 그렸다(솔버를 아예 돌리지 않음). 이번 버전은 그 재계산을 전부 걷어내고, 솔버가 WM 에 실제로
남긴 AST + program_ast.antiunify_ast() 의 실제 결과만 그린다."""
from __future__ import annotations

import html
import json
import os

from arbor.agent.focus import setup_focus_agent
from arbor.engine.trace import _Tracer
from arbor.env.dataset import list_tasks, load_task
from arbor.reasoning import program_ast as PA

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]

# easy_a 데이터셋 실물 9 태스크(list_tasks("easy_a") 와 일치): a·b = GRID-level 상수해(§ 아래
# task_section 참고), c~h = 단일픽셀 이동(PIXEL coloring AST), i = 격자 크기 변화(6x6→5x5).
TIDS = [f"easy000{c}" for c in "abcdefghi"]

_REF_PREFIX = {"pixel": "in_px", "object": "in_objs"}   # program_ast._LEVEL 표시용 미러(읽기 전용)


# ── 원자 box 렌더 헬퍼 (기존 유지/소폭 확장 — 값은 전부 AST 에서 뽑아 채운다) ──────────────
def grid(gr):
    W = len(gr[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in gr for v in row)
    return f'<div class="thumb" style="grid-template-columns:repeat({W},6px)">{cells}</div>'


def opb(name, cls=""):
    return f'<span class="bx op {cls}">{html.escape(name)}</span>'


def tgt(idx, cls="", prefix="in_px"):
    return f'<span class="bx tv {cls}">{prefix}[{idx}].coord</span>'


def colr(v, cls=""):
    return f'<span class="bx cv {cls}">{html.escape(str(v))}</span>'


def dest_box(v, cls=""):
    return f'<span class="bx tv {cls}">{html.escape(v)}</span>'


def dvar(t):
    return f'<span class="bx dvar">{html.escape(t)}</span>'


def flow(rows, thumbs="", ghost=False):
    cls = "flow ghost" if ghost else "flow"
    parts = [f'<div class="{cls}">',
             '<div class="row"><span class="bx grid">input_grid</span></div><div class="v"></div>']
    for r in rows:
        parts.append(f'<div class="row">{r}</div><div class="v"></div>')
    parts.append('<div class="row"><span class="bx grid">output_grid</span></div>')
    if thumbs:
        parts.append(f'<div class="thumbs">{thumbs}</div>')
    parts.append('</div>')
    return "".join(parts)


def _step(op, target, color):
    return f'{op}<span class="h"></span><span class="args">{target}{color}</span>'


def hdr_block(ast, g0):
    """render_header(ast, g0) 를 그대로 — 이 열이 실제 어떤 DSL(op/accessor)·input_grid 로
    만들어졌는지 자동 표시(앞단이 ARCKG/솔버와 연결돼 있음을 보이는 용도, 저장 없음)."""
    return f'<pre class="hdr">{html.escape(PA.render_header(ast, g0))}</pre>'


# ── AST leaf → box: const=구체값, var=실제 slot 변수(antiunify_ast 가 낸 이름 그대로) ─────────
def idx_box(leaf, ref, cls=""):
    if "const" in leaf:
        v = leaf["const"]
        if ref in _REF_PREFIX:
            return tgt(v, cls, prefix=_REF_PREFIX[ref])
        return dest_box(str(sorted(v)), cls)                  # cellset(blob): 셀 리스트 그대로
    prefix = _REF_PREFIX.get(ref)
    name = leaf.get("var", "?")
    return dvar(f"{prefix}[{name}].coord" if prefix else name)


def col_box(leaf, cls=""):
    if "const" in leaf:
        return colr(leaf["const"], cls)
    return dvar(leaf.get("var", "?"))


def _ast_rows(ast, outline=None):
    """concrete 또는 skeleton AST(body) → box-flow 행 리스트. outline[i]={'idx':'comm'|'diff',
    'col':...} 있으면 그 포지션 박스에 outline class 를 입힌다(없으면 무지정=col① 재료처럼 평문).
    idx/col 가 var(slot) 면 outline 과 무관하게 항상 dvar(보라) — COMM/DIFF 여부는 이미 skeleton
    의 const/var 자체가 말하고 있으므로 별도 판정을 재구현하지 않는다."""
    op_cls = "comm" if outline is not None else ""
    rows = []
    for i, s in enumerate(ast.get("body") or []):
        ref = s["args"]["target"]["ref"]
        leaf = s["args"]["target"]["cells"] if ref == "cellset" else s["args"]["target"]["index"]
        o = outline[i] if (outline and i < len(outline)) else {}
        rows.append(_step(opb(s["call"], op_cls),
                           idx_box(leaf, ref, o.get("idx", "")),
                           col_box(s["args"]["color"], o.get("col", ""))))
    return rows


def _slot_outline(skeleton):
    """skeleton(=antiunify_ast 결과) → 포지션별 {'idx','col'} outline class. const=COMM(모든 pair
    에서 값이 같아 상수로 승격됐다는 뜻), var=DIFF(slot 으로 승격). 새로 판정하는 게 아니라
    skeleton 자체가 이미 담고 있는 사실(const/var)을 그대로 읽는다."""
    out = []
    for s in skeleton.get("body") or []:
        tl = s["args"]["target"]
        leaf = tl["cells"] if tl.get("ref") == "cellset" else tl["index"]
        out.append({"idx": "comm" if "const" in leaf else "diff",
                     "col": "comm" if "const" in s["args"]["color"] else "diff"})
    return out


# ── 실 데이터 취득: 솔버를 1회 실행해 (train PAIR.program AST 리스트, real attempts) 를 함께 뽑는다.
#    program_report.py::_run_programs 와 동일 경로(_Tracer + setup_focus_agent)를 재사용한다.
#    attempts 는 같은 tracer 실행에서 공짜로 나오므로(태스크당 solve 를 두 번 돌리지 않으려고) 여기서
#    같이 반환한다 — 브리핑의 _pair_asts 는 리스트만 반환했지만, 그러면 ③ 열의 real attempts 를 보이려
#    할 때 같은 태스크를 또 한 번 풀어야 해서 이렇게 합쳤다.
def _pair_asts(tid, task):
    """example(train) PAIR.program(AST) 을 pair 순서(P0,P1,…)대로. (asts, attempts) 반환.
    program 이 없으면(미합성/실패) 그 자리는 건너뛴다 → asts 길이가 train 개수보다 작을 수 있다."""
    try:
        tr = _Tracer(task, tid, setup=setup_focus_agent)
        tr.run(max_cycles=6000)                      # PIXEL 하강은 픽셀 개별관측으로 cycle 이 큼
    except Exception:                                 # noqa: BLE001 — 리포트 생성용, 한 태스크 예외가 전체를 죽이지 않게
        return [], []
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
    return asts, tr.attempts


# ── ③ 슬롯 · 실행 블록 (전부 실제 antiunify_ast/attempts 값을 그대로 표시) ────────────────────
def _slots_block(slots):
    if not slots:
        return '<div class="note">DIFF 슬롯 없음 — 두 PAIR program 이 전 포지션 COMM(완전 동일).</div>'
    items = sorted(slots.items(), key=lambda kv: kv[1]["pos"])
    rows = "".join(
        f'<div class="slotrow">{dvar(name)}<span class="slotmeta">{html.escape(v["kind"])} · '
        f'pos {v["pos"]} · pair 별 관측값 {html.escape(str(v["values"]))}</span></div>'
        for name, v in items)
    return f'<div class="slots"><div class="ahead">antiunify_ast() 의 실제 slots</div>{rows}</div>'


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


def task_section(tid, task):
    same = all(len(e["input"]) == len(e["output"]) and len(e["input"][0]) == len(e["output"][0])
               for e in task["train"])
    tp = task["test"][0]
    thumbs = ("".join(grid(ex["input"]) + grid(ex["output"]) for ex in task["train"])
              + grid(tp["input"]) + (grid(tp["output"]) if tp.get("output") else ""))

    if not same:                                      # 격자 크기 변화 — pixel coloring(입력=출력 크기 보존) 표현 밖
        return (f'<section class="task" id="{tid}"><h2>{tid}<span class="na">격자 크기 변화</span></h2>'
                f'<div class="thumbs">{thumbs}</div>'
                f'<p class="note">example pair 마다 입·출력 격자 크기가 달라(resize) coloring 재조합'
                f'(pixel/object DSL 은 입력과 같은 크기의 grid 만 재칠함) 표현 범위 밖 — program 미합성.'
                f'</p></section>')

    asts, attempts = _pair_asts(tid, task)
    if len(asts) < 2:
        solved = bool(attempts) and any(at["correct"] for at in attempts)
        if solved:                                    # 실제로 풀렸다(GRID-level) — 다만 coloring AST 자체가 없음
            badge = "GRID-level 해 (coloring AST 밖)"
            note = ("이 태스크는 실제로 풀렸다(아래 real attempts) — 다만 정답이 GRID-level 상수/전역"
                    " 규칙이라 pixel coloring 재조합(PAIR.program AST)이 애초에 생성되지 않는다"
                    "(coloring 은 입력 셀을 재칠할 뿐이라 '입력과 무관한 고정 출력'은 새 atom 없이는"
                    " 이 스키마로 표현 불가).")
        else:
            badge = "program 미합성"
            note = ("solve 가 이 태스크의 example PAIR program 을 다 채우지 못했다(WM 의 program 슬롯이"
                    " 비었거나 hypothesized=failed) — 표시할 실제 AST 없음(정직하게 미해결로 남김).")
        extra = _attempts_block(attempts, tp) if attempts else ""
        return (f'<section class="task" id="{tid}"><h2>{tid}<span class="na">{html.escape(badge)}</span></h2>'
                f'<div class="thumbs">{thumbs}</div><p class="note">{note}</p>{extra}</section>')

    a, b = asts[0], asts[1]
    skeleton, slots = PA.antiunify_ast(asts)
    if skeleton is None:                              # step 수 불일치 등 — antiunify_ast 자체가 포기한 경우
        return (f'<section class="task" id="{tid}"><h2>{tid}<span class="na">compare 실패</span></h2>'
                f'<div class="thumbs">{thumbs}</div>'
                f'<p class="note">antiunify_ast() 가 None 반환(예: pair 간 step 수 불일치) — COMM/DIFF'
                f' 렌더 불가.</p></section>')
    outline = _slot_outline(skeleton)

    dl = skeleton["body"][-1]["args"]["target"]
    dl = dl["cells"] if dl.get("ref") == "cellset" else dl["index"]
    concept = "목적지 고정 (COMM)" if "const" in dl else "목적지 가변 (DIFF slot)"

    # ① 재료 — 실제 PAIR.program(AST) 그대로(재계산 없음), 열 상단에 그 pair 의 실제 header
    col1 = "".join(
        f'<div class="lab">PAIR {k + 1}</div>{hdr_block(ast_k, ex["input"])}'
        f'{flow(_ast_rows(ast_k), grid(ex["input"]) + grid(ex["output"]))}'
        for k, (ast_k, ex) in enumerate(zip(asts, task["train"])))

    # ② 비교 — PAIR1(outline 입힘) 겹침 PAIR2(ghost). outline 은 skeleton(antiunify_ast 실제 결과)이 낸 것.
    col2 = (f'{hdr_block(a, task["train"][0]["input"])}'
            f'<div class="ovl">{flow(_ast_rows(a, outline))}{flow(_ast_rows(b), ghost=True)}</div>'
            f'<div class="legend"><span class="lg comm">COMM 겹침</span>'
            f'<span class="lg diff">DIFF 어긋남</span></div>')

    # ③ TASK — skeleton 자체(COMM=상수 박스, DIFF=실제 slot 변수 박스) + 그 slot 들의 실제 관측값
    #    + 같은 솔버 실행에서 나온 real attempts(hyp·정오)+제출 (별도 채점 로직 없음)
    col3 = (f'{hdr_block(skeleton, task["train"][0]["input"])}'
            f'{flow(_ast_rows(skeleton, outline))}'
            f'{_slots_block(slots)}{_attempts_block(attempts, tp)}')

    return (f'<section class="task" id="{tid}"><h2>{tid}<span class="tag2">{html.escape(concept)}</span></h2>'
            f'<div class="cols">'
            f'<div class="col c1"><div class="ct">① 재료</div>{col1}</div>'
            f'<div class="sep"><span>COMPARE</span></div>'
            f'<div class="col c2"><div class="ct">② 비교 (겹침 · COMM/DIFF)</div>{col2}</div>'
            f'<div class="sep"><span>ANTI-UNIFY<br>(antiunify_ast)</span></div>'
            f'<div class="col c3"><div class="ct">③ TASK program (skeleton)</div>{col3}</div>'
            f'</div></section>')


CSS = """
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


def build():
    tabs = "".join(f'<a href="#{t}" data-t="{t}">{t[-1].upper()}</a>' for t in TIDS)
    paths = dict(list_tasks("easy_a"))
    secs = "".join(task_section(t, load_task(paths[t])) for t in TIDS)
    js = ("<script>function sh(){var h=location.hash.slice(1);"
          "document.querySelectorAll('section.task').forEach(function(s){s.style.display=(!h||s.id===h)?'':'none'});"
          "document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.t===h)});}"
          "addEventListener('hashchange',sh);sh();</script>")
    doc = (f'<!doctype html><meta charset="utf-8"><title>anti-unification</title><style>{CSS}</style>'
           f'<a class="back" href="focus_dashboard.html">← focus_dashboard</a>'
           f'<h1>per-pair program → anti-unification (실물)</h1>'
           f'<p class="hs">solve 를 실제 실행해 WM 의 PAIR.program(AST) 을 읽고 program_ast.antiunify_ast()'
           f' 의 실제 COMM/DIFF·slot 을 그대로 렌더(재계산 없음) · 열 상단 = render_header(ast, 실제'
           f' input_grid)</p>'
           f'<div class="tabs">{tabs}</div>{secs}{js}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "easy_antiunify_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
