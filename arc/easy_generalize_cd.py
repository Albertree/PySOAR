"""Generalise easy000c & easy000d TASK.solutions into ONE general, situation-agnostic
program (same horizontal visual as easy_antiunify_report).

  c.sol / d.sol : coloring(coord_of(p),bg) ; coloring(<dest>, color_of(p))   dest=(5,5)/(1,2)
  COMPARE       : skeleton COMM, destination DIFF
  GENERALIZE    : destination → `target`, a FREE COORDINATE PARAMETER (a hole you plug per
                  situation). Uses the INPUT grid only — never the output (test has no output).
                  Rendered as a 6-line program with Y-shaped derivations for coord_of(p)/color_of(p).
  VERIFY        : plug target=(5,5) → solves c ; plug target=(1,2) → solves d. One program, both.

Writes arc/easy_generalize_cd_report.html."""
from __future__ import annotations

import html
import os
from collections import Counter

from arc.dataset import list_tasks, load_task

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]


def grid(gr):
    W = len(gr[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in gr for v in row)
    return f'<div class="g" style="grid-template-columns:repeat({W},8px)">{cells}</div>'


def distinct_pixel(gr):
    cnt = Counter(v for row in gr for v in row)
    minority = min(cnt, key=cnt.get)
    for r, row in enumerate(gr):
        for c, v in enumerate(row):
            if v == minority:
                return (r, c, v)
    return None


def task_dest(task):
    ds = [distinct_pixel(e["output"])[:2] for e in task["train"]]
    return ds[0] if len(set(ds)) == 1 else None


def general_solve(test_input, target):
    """G — input grid + a supplied `target` coordinate only. Never touches any output."""
    p = distinct_pixel(test_input)
    bg = Counter(v for row in test_input for v in row).most_common(1)[0][0]
    H, W = len(test_input), len(test_input[0])
    out = [[bg] * W for _ in range(H)]
    if target and p:
        out[target[0]][target[1]] = p[2]
    return out


# ── boxes / flow ─────────────────────────────────────────────────────────────
def bx(label, cls):
    return f'<span class="bx {cls}">{label}</span>'


def fapp(name, arg):
    return f'<span class="fapp">{bx(name, "fn")}<span class="hb"></span>{arg}</span>'


def coordp():
    return fapp("coord_of", bx("p", "pp"))


def colorp():
    return fapp("color_of", bx("p", "pp"))


def _step(target, color, ocls=""):
    return (f'<div class="row"><span class="bx op {ocls}">coloring</span><span class="h"></span>'
            f'<span class="args"><i class="tag">target</i>{target}'
            f'<i class="tag">color</i>{color}</span></div>')


def dval(v):
    return f'<span class="bx dval">{html.escape(v)}</span>'


def pgen(fname, valname):
    # same as easy_antiunify ③: derivation grown ABOVE the value box into a blank gap, I-joined
    return (f'<span class="pgen"><span class="deriv"><span class="pd">'
            f'{bx(fname, "fn")}<span class="hbar"></span>{bx("p", "obj")}</span>'
            f'<span class="ibar"></span></span>{dval(valname)}</span>')


def flow(rows, ghost=False):
    cls = "flow ghost" if ghost else "flow"
    inner = '<div class="row"><span class="bx grid">input_grid</span></div><div class="v"></div>'
    for r in rows:
        inner += r + '<div class="v"></div>'
    inner += '<div class="row"><span class="bx grid">output_grid</span></div>'
    return f'<div class="{cls}">{inner}</div>'


def sol_flow(dest, outl=None):
    o = outl or {}
    t0, c0, t1, c1 = o.get("t0", ""), o.get("c0", ""), o.get("t1", ""), o.get("c1", "")
    return flow([_step(f'<span class="{t0}">{coordp()}</span>', f'<span class="{c0}">{bx("bg", "lit")}</span>'),
                 _step(f'<span class="{t1}">{dest}</span>', f'<span class="{c1}">{colorp()}</span>')])


def build():
    paths = dict(list_tasks("easy_a"))
    tc, td = load_task(paths["easy000c"]), load_task(paths["easy000d"])
    Tc, Td = task_dest(tc), task_dest(td)

    col1 = (f'<div class="lab">easy000c.solution</div>{sol_flow(bx(str(Tc), "lit"))}'
            f'<div class="lab">easy000d.solution</div>{sol_flow(bx(str(Td), "lit"))}')

    outl = {"t0": "comm", "c0": "comm", "t1": "diff", "c1": "comm"}
    col2 = (f'<div class="ovl">{sol_flow(bx(str(Tc), "lit"), outl)}'
            f'<div class="ghostwrap">{sol_flow(bx(str(Td), "lit"))}</div></div>')

    # ③ general program G — same as easy_antiunify ③: the added branch (coord_of/color_of
    #    derivation) rises above its value box into a BLANK GAP, joined by an I-connector.
    col3 = flow([_step(pgen("coordinate_of", "coord1"), bx("bg", "lit")),
                 _step(bx("target", "param"), pgen("color_of", "color1"))])
    note = ('<div class="synth"><div class="slab">target = 자유 좌표 파라미터 (hole)</div>'
            '<div class="note3"><b>target</b> 은 출력·task 와 무관한 <b>빈 좌표 칸</b> — 상황마다 끼워 넣는다. '
            'coord1 = coord_of(p), color1 = color_of(p) 는 <b>입력 픽셀 p</b> 에서 도출(위 가지). '
            '프로그램은 <b>입력 + target</b> 만, <b class="d">output 참조 없음 (P5)</b>.</div></div>')
    col3 += note

    def vrow(tid, task, T):
        tp = task["test"][0]; pred = general_solve(tp["input"], T); ok = pred == tp.get("output")
        return (f'<div class="vrow"><span class="vt">G(input, target={T})</span>'
                f'{grid(tp["input"])}<span class="ar">→</span>'
                f'<span class="pw">{grid(pred)}<span class="cap">예측</span></span>'
                f'<span class="sv {"sok" if ok else "sno"}">{"✅ 정답" if ok else "✗"}</span>'
                f'<span class="pw">{grid(tp["output"])}<span class="cap">정답</span></span></div>')
    verify = f'<div class="verify">{vrow("c", tc, Tc)}{vrow("d", td, Td)}</div>'

    cols = (f'<div class="cols">'
            f'<div class="col"><div class="ct">① 재료 · 두 TASK.solution</div>{col1}</div>'
            f'<div class="sep"><span>COMPARE</span></div>'
            f'<div class="col"><div class="ct">② 비교 (겹침 · COMM/DIFF)</div>{col2}</div>'
            f'<div class="sep"><span>GENERALIZE</span></div>'
            f'<div class="col c3"><div class="ct">③ 일반 프로그램 G (6줄 · target=파라미터)</div>{col3}</div>'
            f'</div>')
    doc = (f'<!doctype html><meta charset="utf-8"><title>generalize c·d</title><style>{CSS}</style>'
           f'<a class="back" href="easy_antiunify_report.html">← anti-unification</a>'
           f'<h1>TASK.solution 일반화 — c · d → 상황-무관 일반 프로그램 G</h1>'
           f'<p class="hs">목적지 상수만 다른 두 solution → 목적지를 자유 파라미터 <b>target</b> 으로 → '
           f'입력만 쓰는 하나의 G. target 좌표를 상황마다 끼워 넣는다.</p>'
           f'<section class="card">{cols}</section>'
           f'<div class="seph">VERIFY — 같은 G 에 target 만 바꿔 끼움</div>'
           f'<section class="card">{verify}</section>')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "easy_generalize_cd_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


CSS = """
body{background:#14161b;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,sans-serif;margin:0;padding:22px}
a.back{color:#5fb0ff;text-decoration:none;font-size:13px}
h1{font-size:19px;margin:10px 0 4px}.hs{color:#8b93a3;margin:0 0 16px;font-size:12px;max-width:820px}
.card{background:#1a1d24;border:1px solid #262b34;border-radius:10px;padding:16px 18px;margin:0 0 10px}
.ct{font-size:11px;color:#8b93a3;text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px}
.cols{display:flex;gap:6px;align-items:stretch}
.col{background:#0f1218;border:1px solid #232c39;border-radius:9px;padding:10px 12px}.c3{flex:1}
.lab{font-size:10px;color:#7a8698;margin:6px 0 4px;font-weight:700}
.sep{display:flex;align-items:center;justify-content:center;min-width:46px;color:#8b93a3;font-size:10px;font-weight:700;text-align:center}
.sep span{background:#161b24;border:1px solid #2a3340;border-radius:6px;padding:6px 8px}
.seph{color:#7a8698;font-weight:700;font-size:11px;margin:6px 0 6px 4px;letter-spacing:.05em}
.flow{display:flex;flex-direction:column;align-items:flex-start}
.row{display:flex;align-items:center;min-height:26px}
.v{width:2px;height:12px;background:#3b4657;margin-left:48px}.h{width:11px;height:2px;background:#3b4657}
.args{display:flex;gap:5px;align-items:center}
.tag{font-style:normal;font-size:9px;color:#7a8698;margin:0 2px 0 4px;text-transform:uppercase}
.bx{border-radius:6px;padding:4px 9px;font-size:11.5px;font-weight:600;white-space:nowrap;border:1px solid transparent}
.grid{background:#fff;color:#222;border-color:#cdd3db;min-width:78px;text-align:center;font-family:ui-monospace,monospace;font-weight:500}
.op{background:#f6cccd;color:#7a2b2c;border-color:#e0a3a4;min-width:78px;text-align:center}
.lit{background:#fbe6c9;color:#7a5320;border-color:#e6c99a;font-family:ui-monospace,monospace;font-weight:500}
.fn{background:#123049;color:#8fc2f0;border-color:#4a7fb5}.pp{background:#132033;color:#8fb8ff;border-color:#35507a}
.var{background:#1b3a57;color:#cfe6ff;border-color:#5a8fc0;font-family:ui-monospace,monospace;font-weight:700}
.param{background:#241a10;color:#ffcf9a;border:1.5px dashed #b5842a;font-family:ui-monospace,monospace;font-weight:700}
.fapp{display:inline-flex;align-items:center}.hb{width:8px;height:2px;background:#4a7fb5}
.comm{box-shadow:0 0 0 2px #3fae6a inset;border-radius:6px}.diff{box-shadow:0 0 0 2px #e23b3b inset;border-radius:6px}
.ovl{position:relative}.ghostwrap{position:absolute;inset:0;transform:translate(9px,9px);opacity:.4;pointer-events:none;filter:saturate(.7)}
/* added-branch derivation rises above its value box into a blank gap (I-connector) */
.pgen{position:relative;display:inline-flex}
.deriv{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center}
.pd{display:flex;align-items:center}.ibar{width:2px;height:9px;background:#4a7fb5}.hbar{width:9px;height:2px;background:#4a7fb5}
.obj{background:#0d1a27;color:#7cc0ff;border-color:#4a7fb5}
.dval{background:#1b3a57;color:#cfe6ff;border-color:#5a8fc0;font-family:ui-monospace,monospace;font-weight:700}
.c3 .v{height:42px}
.synth{margin-top:16px;background:#0f141b;border:1px dashed #3a5273;border-radius:8px;padding:10px 12px}
.slab{font-size:10px;color:#6f88a8;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.note3{color:#9aa3b2;font-size:11.5px;line-height:1.7}.note3 .d{color:#e2726f}
.verify{display:flex;flex-direction:column}
.vrow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:7px 0;border-top:1px solid #232c39}
.vrow:first-child{border-top:none}.vt{font-weight:700;color:#cfd6e2;min-width:190px;font-family:ui-monospace,monospace;font-size:11.5px}
.g{display:inline-grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content;vertical-align:middle}.g i{width:8px;height:8px;display:block}
.pw{display:inline-flex;flex-direction:column;align-items:center;gap:2px}.cap{font-size:9px;color:#8b93a3}.ar{color:#556}
.sv{font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px}
.sok{background:#12281c;color:#a9e6c1;border:1px solid #2f5a41}.sno{background:#241417;color:#e0a3a4;border:1px solid #5a2f34}
"""


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
