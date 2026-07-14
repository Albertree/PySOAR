"""Anti-unification view — faithful to the actual generated code:

    input_grid → coloring( in_px[i].coord , <colour> ) → coloring( in_px[j].coord , <colour> ) → output_grid

  ① 재료  : PAIR 1 / PAIR 2 programs (concrete) + grid thumbnails
  ② 비교  : the two programs OVERLAID (offset + translucent) so COMM parts coincide and DIFF
            parts diverge; COMM(green)/DIFF(amber) outlines on the slots
  ③ TASK  : DIFF slots resolved by a NEW BRANCH growing out — coordinate_of(p) / color_of(p);
            COMM slots kept as-is

Reuses arc.easy_concepts (samples / version_space / pick / concept_label)."""
from __future__ import annotations

import html
import os

from arc.dataset import list_tasks, load_task
from debugger.reports.easy_concepts import samples, version_space, concept_label, apply, TIDS


def _rank(d):
    # attempt order prior: input-relative / grid-relative before constant (constants over-fit)
    if d[:2] in ("r0", "c0"):
        return 0
    if d in ("H-1", "W-1", "0(top)", "0(left)"):
        return 1
    return 2

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]


def grid(gr):
    W = len(gr[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in gr for v in row)
    return f'<div class="thumb" style="grid-template-columns:repeat({W},6px)">{cells}</div>'


def opb(cls=""):
    return f'<span class="bx op {cls}">coloring</span>'


def tgt(idx, cls=""):
    return f'<span class="bx tv {cls}">in_px[{idx}].coord</span>'


def colr(v, cls=""):
    return f'<span class="bx cv {cls}">{html.escape(str(v))}</span>'


def dest_box(v, cls=""):
    return f'<span class="bx tv {cls}">{html.escape(v)}</span>'


def dval(v):
    return f'<span class="bx dval">{html.escape(v)}</span>'


def pgen(fname, valname):
    # the value box with its derivation grown ABOVE it (absolutely, so the row height and the
    # chain connector are unaffected), joined by an I bar:  [fname]─[p] │ [valname]
    return (f'<span class="pgen">'
            f'<span class="deriv"><span class="pd"><span class="bx fn">{fname}</span>'
            f'<span class="hbar"></span><span class="bx obj">p</span></span>'
            f'<span class="ibar"></span></span>{dval(valname)}</span>')


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


def concrete(s, outl=None):
    e, d, col = s[0] * s[3] + s[1], s[4] * s[3] + s[5], s[6]
    o = outl or {}
    st0 = _step(opb(o.get("op", "")), tgt(e, o.get("t0", "")), colr(0, o.get("c0", "")))
    st1 = _step(opb(o.get("op", "")), tgt(d, o.get("t1", "")), colr(col, o.get("c1", "")))
    return [st0, st1]


def task_section(tid, task):
    same = all(len(e["input"]) == len(e["output"]) and len(e["input"][0]) == len(e["output"][0])
               for e in task["train"])
    if not same:
        return f'<section class="task" id="{tid}"><h2>{tid}<span class="na">격자 크기 변화</span></h2></section>'
    sm = samples(task)
    a, b = sm[0], sm[1]
    vr, _, _ = version_space(sm, "r"); vc, _, _ = version_space(sm, "c")
    e0, e1 = a[0] * a[3] + a[1], b[0] * b[3] + b[1]
    d0, d1 = a[4] * a[3] + a[5], b[4] * b[3] + b[5]
    c0, c1 = a[6], b[6]
    dest_comm = (a[4], a[5]) == (b[4], b[5])     # draw COORDINATE identical across pairs → 상수(COMM)
    #   (index d0/d1 can differ when grid width differs even if the (r,c) coordinate is the same)
    cands, tried, win = [], [], None
    if dest_comm:                                # COMM slot → 고정 상수, 변수화·시도 없음
        concept = "고정 위치 (fixed-position)"
    else:                                        # DIFF slot → ?dest 변수화 후 version space 를 3회 제출
        rowmap, colmap = dict(vr), dict(vc)
        cands = sorted([(r, c) for r in rowmap for c in colmap], key=lambda x: _rank(x[0]) + _rank(x[1]))
        exp = task["test"][0].get("output")
        tried = [(r, c, apply(task["test"][0]["input"], rowmap[r], colmap[c]) == exp) for r, c in cands[:3]]
        win = next((i for i, t in enumerate(tried) if t[2]), None)
        wr, wc = cands[win] if win is not None else cands[0]
        concept = concept_label(wr, wc)

    # winning solution → predicted test output (the SUBMISSION)
    if dest_comm:
        srf = (lambda fr, fc, H, W, v=a[4]: v); scf = (lambda fr, fc, H, W, v=a[5]: v)
    elif win is not None:
        srf, scf = rowmap[wr], colmap[wc]
    else:
        srf, scf = (rowmap[wr], colmap[wc])
    tp = task["test"][0]
    pred = apply(tp["input"], srf, scf)
    ok_test = (pred == tp.get("output"))

    # ① 재료
    col1 = (f'<div class="lab">PAIR 1</div>'
            f'{flow(concrete(a), grid(task["train"][0]["input"]) + grid(task["train"][0]["output"]))}'
            f'<div class="lab">PAIR 2</div>'
            f'{flow(concrete(b), grid(task["train"][1]["input"]) + grid(task["train"][1]["output"]))}')

    # ② 비교 — overlay: base(pair1) with COMM/DIFF outlines + ghost(pair2) offset/translucent
    outl = {"op": "comm", "t0": "diff" if e0 != e1 else "comm", "c0": "comm",
            "t1": "comm" if dest_comm else "diff", "c1": "diff" if c0 != c1 else "comm"}
    col2 = (f'<div class="ovl">{flow(concrete(a, outl))}{flow(concrete(b), ghost=True)}</div>'
            f'<div class="legend"><span class="lg comm">COMM 겹침</span>'
            f'<span class="lg diff">DIFF 어긋남</span></div>')

    # ③ TASK — DIFF slots resolved by a parameter derivation grown ABOVE the value box and
    #    joined with an I connector (coord1 = coordinate_of(p) rises up into its use).
    fmt = lambda d: d.replace("const ", "")
    st0 = _step(opb(), pgen("coordinate_of", "coord1"), colr(0))
    dest = dest_box(f"({a[4]},{a[5]})") if dest_comm else dvar("?dest")
    st1 = _step(opb(), dest, pgen("color_of", "color1"))
    note = '<div class="note">p = 입력의 단일 픽셀 (OBJECT)</div>'
    if not dest_comm:
        head = ('ARC 3회 시도 · version space ' + str(len(cands)) + '개 → '
                + (f'attempt {win + 1}에 정답 ✅' if win is not None else '3회내 실패 ❌'))
        rows = "".join(
            f'<div class="att {"aok" if ok else "ano"}">attempt {i}: ?dest = ({html.escape(fmt(r))}, '
            f'{html.escape(fmt(c))}) → {"✅" if ok else "✗"}'
            f'{" ⟵ 채택" if (win is not None and i == win + 1) else ""}</div>'
            for i, (r, c, ok) in enumerate(tried, 1))
        note += f'<div class="attempts"><div class="ahead">{head}</div>{rows}</div>'
    submit = (f'<div class="submit"><span class="slab">제출 (test)</span>'
              f'{grid(tp["input"])}<span class="ag">→</span>'
              f'<span class="pwrap">{grid(pred)}<span class="pcap">예측</span></span>'
              f'<span class="sv {"sok" if ok_test else "sno"}">{"✅ 정답" if ok_test else "✗ 오답"}</span>'
              + (f'<span class="pwrap">{grid(tp["output"])}<span class="pcap">정답</span></span>'
                 if tp.get("output") else '') + '</div>')
    col3 = flow([st0, st1]) + submit + note

    return (f'<section class="task" id="{tid}"><h2>{tid}<span class="tag2">{html.escape(concept)}</span></h2>'
            f'<div class="cols">'
            f'<div class="col c1"><div class="ct">① 재료</div>{col1}</div>'
            f'<div class="sep"><span>COMPARE</span></div>'
            f'<div class="col c2"><div class="ct">② 비교 (겹침 · COMM/DIFF)</div>{col2}</div>'
            f'<div class="sep"><span>ABSTRACTION<br>(parameterize)</span></div>'
            f'<div class="col c3"><div class="ct">③ TASK program</div>{col3}</div>'
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
/* ③ parameter derivation grown ABOVE the value box (absolute), joined by an I connector */
.pgen{position:relative;display:inline-flex}
.deriv{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}
.pd{display:flex;align-items:center}
.ibar{width:2px;height:9px;background:#4a7fb5}
.fn{background:#123049;color:#8fc2f0;border-color:#4a7fb5}
.obj{background:#0d1a27;color:#7cc0ff;border-color:#4a7fb5}
.hbar{width:9px;height:2px;background:#4a7fb5}
.dval{background:#1b3a57;color:#cfe6ff;border-color:#5a8fc0;font-family:ui-monospace,monospace;font-weight:700}
.thumbs{display:flex;gap:5px;margin-top:8px}
.thumb{display:inline-grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}.thumb i{width:6px;height:6px;display:block}
.note{margin-top:10px;font-size:11px;color:#9aa3b2;display:flex;align-items:center;gap:4px}
.ex{background:#132033;border:1px solid #35507a;color:#8fb8ff;border-radius:5px;padding:1px 6px;margin:0 2px;font-weight:700;font-family:ui-monospace,monospace}
.amb{color:#ffcf9a}
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
    paths = dict(list_tasks("easy_a"))
    tabs = "".join(f'<a href="#{t}" data-t="{t}">{t[-1].upper()}</a>' for t in TIDS)
    secs = "".join(task_section(t, load_task(paths[t])) for t in TIDS)
    js = ("<script>function sh(){var h=location.hash.slice(1);"
          "document.querySelectorAll('section.task').forEach(function(s){s.style.display=(!h||s.id===h)?'':'none'});"
          "document.querySelectorAll('.tabs a').forEach(function(a){a.classList.toggle('on',a.dataset.t===h)});}"
          "addEventListener('hashchange',sh);sh();</script>")
    doc = (f'<!doctype html><meta charset="utf-8"><title>anti-unification</title><style>{CSS}</style>'
           f'<a class="back" href="focus_dashboard.html">← focus_dashboard</a>'
           f'<h1>per-pair program → anti-unification</h1>'
           f'<p class="hs">coloring 데이터플로우(실제 코드) · 두 프로그램 겹침 COMM/DIFF · DIFF 를 새 가지(함수)로 해소</p>'
           f'<div class="tabs">{tabs}</div>{secs}{js}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "easy_antiunify_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
