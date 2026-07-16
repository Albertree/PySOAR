"""Easy tasks → simple CONCEPTS via AST anti-unification (easy000c–i, single-pixel move).

Each task: one coloured pixel moves; colour is kept. The per-pair program is a 2-step AST
(erase at coord_of(p) → draw at DEST with color_of(p)). Anti-unifying the pairs keeps the
skeleton COMM and leaves DEST as a hole; the hole is resolved by a small generate-and-test
expression search (harness §1-3/§4-1: never hand-compute (H-1,W-1) — generate candidates
{const, r0±Δ, c0±Δ, H-1, W-1, 0} → keep those COMM across pairs). The resolved DEST is the
task solution = a reusable CONCEPT: fixed-position / relative-shift / grid-corner.

Honest note: with only 2 train pairs whose input row is constant (r0=1 in both), the ROW
component can be under-determined — several expressions fit train (a VERSION SPACE, see
[[version-space]]); test disambiguates. We show the version space and pick a representative.
"""
from __future__ import annotations

import html
import json
import os

from arbor.env.dataset import list_tasks, load_task

PAL = ["#101010", "#1E93FF", "#F93C31", "#4FCC30", "#FFDC00",
       "#999999", "#E53AA3", "#FF851B", "#87D8F1", "#921231"]
CELL = 16
TIDS = ["easy000c", "easy000d", "easy000e", "easy000f", "easy000g", "easy000h"]


# ── extract single-pixel move material ──────────────────────────────────────
def _pixel(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v:
                return (r, c, v)
    return None


def samples(task):
    """per pair: (fr, fc, H, W, tr, tc, color)."""
    out = []
    for ex in task["train"]:
        fr, fc, col = _pixel(ex["input"])
        tr, tc, _ = _pixel(ex["output"])
        out.append((fr, fc, len(ex["input"]), len(ex["input"][0]), tr, tc, col))
    return out


# ── candidate expressions for one destination component (generate-and-test) ──
def make_cands(kind):
    base = (lambda fr, fc, H, W: fr) if kind == "r" else (lambda fr, fc, H, W: fc)
    bname = "r0" if kind == "r" else "c0"
    cands = [(f"const {k}", (lambda fr, fc, H, W, k=k: k)) for k in range(0, 7)]
    cands.append((bname, base))
    for d in (1, 2, 3):
        cands.append((f"{bname}+{d}", lambda fr, fc, H, W, d=d, b=base: b(fr, fc, H, W) + d))
        cands.append((f"{bname}-{d}", lambda fr, fc, H, W, d=d, b=base: b(fr, fc, H, W) - d))
    if kind == "r":
        cands += [("H-1", lambda fr, fc, H, W: H - 1), ("0(top)", lambda fr, fc, H, W: 0)]
    else:
        cands += [("W-1", lambda fr, fc, H, W: W - 1), ("0(left)", lambda fr, fc, H, W: 0)]
    return cands, bname


def version_space(sm, kind):
    """ALL candidate expressions COMM across pairs (each reproduces the target on every pair).
    We do NOT dedupe by value: two DIFFERENT expressions that agree on these pairs (e.g.
    `const 2` and `r0+1` when r0 is constant) are kept — that is exactly the few-shot
    ambiguity we want to surface ([[version-space]]). Returns (vs, tried, bname)."""
    idx = 4 if kind == "r" else 5
    cands, bname = make_cands(kind)
    vs, tried = [], []
    for desc, fn in cands:
        ok = all(fn(s[0], s[1], s[2], s[3]) == s[idx] for s in sm)
        tried.append((desc, ok))
        if ok:
            vs.append((desc, fn))
    return vs, tried, bname


def pick(vs, sm, kind):
    """representative from the version space: constant if the target is invariant across
    pairs, else a relative shift, else a grid-corner, else copy."""
    idx = 4 if kind == "r" else 5
    _, bname = make_cands(kind)
    targets = {s[idx] for s in sm}
    if len(targets) == 1:
        for d, f in vs:
            if d.startswith("const"):
                return (d, f)
    for d, f in vs:
        if d.startswith(bname + "+") or d.startswith(bname + "-"):
            return (d, f)
    for d, f in vs:
        if d in ("H-1", "W-1", "0(top)", "0(left)"):
            return (d, f)
    return vs[0] if vs else (None, None)


def concept_label(rdesc, cdesc):
    grid = {"H-1", "W-1", "0(top)", "0(left)"}
    rel = lambda d: d.startswith("r0") or d.startswith("c0")
    if rdesc in grid and cdesc in grid:
        return "격자 코너 (grid-corner)"
    if rdesc.startswith("const") and cdesc.startswith("const"):
        return "고정 위치 (fixed-position)"
    if rel(rdesc) or rel(cdesc):
        return "상대 이동 (relative-shift)"
    return "복합"


def solve(task):
    sm = samples(task)
    # scope guard: our move concept assumes output grid size == input grid size (per pair).
    same_size = all(len(e["input"]) == len(e["output"]) and len(e["input"][0]) == len(e["output"][0])
                    for e in task["train"])
    if not same_size:
        return {"sm": sm, "scope": "grid-resize", "concept": "격자 크기 변화 (개념군 밖)"}
    vr, tr_r, _ = version_space(sm, "r")
    vc, tr_c, _ = version_space(sm, "c")
    (rd, rf), (cd, cf) = pick(vr, sm, "r"), pick(vc, sm, "c")
    return {"sm": sm, "scope": "move", "vr": vr, "vc": vc, "tried_r": tr_r, "tried_c": tr_c,
            "row": (rd, rf), "col": (cd, cf), "concept": concept_label(rd, cd)}


def apply(grid, rf, cf):
    fr, fc, col = _pixel(grid)
    H, W = len(grid), len(grid[0])
    out = [[0] * W for _ in range(H)]
    r, c = rf(fr, fc, H, W), cf(fr, fc, H, W)
    if 0 <= r < H and 0 <= c < W:
        out[r][c] = col
    return out


# ── HTML ────────────────────────────────────────────────────────────────────
def g_grid(grid, label=None):
    W = len(grid[0])
    cells = "".join(f'<i style="background:{PAL[v % 10]}"></i>' for row in grid for v in row)
    lab = f'<div class="glab">{html.escape(label)}</div>' if label else ""
    return (f'<div class="gwrap">{lab}<div class="grid" '
            f'style="grid-template-columns:repeat({W},{CELL}px)">{cells}</div></div>')


def pair_ast(s):
    fr, fc, H, W, tr, tc, col = s
    return {"select": "p = the single non-background pixel",
            "steps": [{"op": "coloring", "target": "coord_of(p)", "value": [fr, fc], "color": 0},
                      {"op": "coloring", "target": "‹DEST›", "value": [tr, tc],
                       "color": "color_of(p)", "color_value": col}]}


def solution_ast(res):
    return {"select": "p = the single non-background pixel",
            "steps": [{"op": "coloring", "target": "coord_of(p)", "color": 0},
                      {"op": "coloring", "target": [res["row"][0], res["col"][0]],
                       "color": "color_of(p)"}]}


def _jscode(obj):
    return html.escape(json.dumps(obj, ensure_ascii=False, indent=2))


def task_card(tid, task):
    res = solve(task)
    sm = res["sm"]
    parts = [f'<section class="card"><h2>{tid} <span class="concept">{res["concept"]}</span></h2>']

    # 재료: per-pair AST
    parts.append('<h3>재료 · per-pair program (AST) — 픽셀 지우고 목적지에 다시 그림</h3>')
    for k, (ex, s) in enumerate(zip(task["train"], sm)):
        grids = g_grid(ex["input"], "G0") + '<span class="arrow">→</span>' + g_grid(ex["output"], "G1")
        parts.append(f'<div class="pair"><div class="ptit">pair {k}  '
                     f'(dest = [{s[4]},{s[5]}])</div><div class="grow">{grids}</div>'
                     f'<pre class="ast">{_jscode(pair_ast(s))}</pre></div>')

    if res["scope"] != "move":
        parts.append('<p class="note">→ 출력 격자 크기가 입력과 달라(격자 크기 변화) 단일-픽셀 이동 개념군 밖. '
                     '정직하게 미해결로 둠 (사용자 승인 범위).</p></section>')
        return "".join(parts), (None, res["concept"])

    # anti-unify: skeleton + DEST hole + expression search
    parts.append('<h3>anti-unify · 뼈대는 COMM, 목적지(DEST)만 DIFF → 표현식 탐색</h3>')
    dr = [(f"[{s[4]},{s[5]}]") for s in sm]
    parts.append(f'<p class="note">DEST 관측값(pair별): {" , ".join(dr)} → 이 값을 재현하는 '
                 f'표현식을 {{const, r0±Δ, c0±Δ, H-1, W-1, 0}} 에서 생성·검증 (§4-1):</p>')
    for axis, key, picked in (("row (r)", "tried_r", res["row"]), ("col (c)", "tried_c", res["col"])):
        chips = "".join(
            f'<span class="{ "ok" if ok else "no" }">{html.escape(d)}{"✓" if ok else "✗"}</span>'
            for d, ok in res[key])
        vs = res["vr"] if key == "tried_r" else res["vc"]
        vspace = " | ".join(html.escape(d) for d, _ in vs)
        parts.append(f'<div class="axis"><b>{axis}</b> 후보: {chips}'
                     f'<div class="vs">version space (train COMM): <code>{vspace}</code>'
                     f' → 채택 <b>{html.escape(picked[0])}</b>'
                     f'{" <span class=amb>⚠ 2개 이상 — 2 예시로 미결정</span>" if len(vs) > 1 else ""}</div></div>')

    # task solution AST + concept
    parts.append('<h3>결과물 · TASK.solution (개념)</h3>')
    parts.append(f'<pre class="sol">{_jscode(solution_ast(res))}</pre>')
    parts.append(f'<div class="note">형성된 개념: <b>{res["concept"]}</b> — '
                 f'DEST = ({html.escape(res["row"][0])}, {html.escape(res["col"][0])})</div>')

    # execution
    parts.append('<h3>실행결과 (예측 vs 정답)</h3><div class="exec">')
    rf, cf = res["row"][1], res["col"][1]
    for k, ex in enumerate(task["train"]):
        pred = apply(ex["input"], rf, cf); ok = pred == ex["output"]
        parts.append(f'<div class="ecase"><div class="etit">train {k} {"✅" if ok else "❌"}</div>'
                     + g_grid(ex["input"], "in") + g_grid(pred, "pred") + g_grid(ex["output"], "exp") + '</div>')
    tp = task["test"][0]; pred = apply(tp["input"], rf, cf); exp = tp.get("output")
    ok = pred == exp if exp is not None else None
    parts.append('<div class="ecase test"><div class="etit">TEST '
                 f'{"✅" if ok else ("❌" if ok is False else "?")}</div>'
                 + g_grid(tp["input"], "in") + g_grid(pred, "pred")
                 + (g_grid(exp, "exp") if exp is not None else "") + '</div></div></section>')
    return "".join(parts), (ok, res["concept"])


CSS = """
body{background:#15171c;color:#dfe3ea;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px}.hsub{color:#8b93a3;margin:0 0 18px}
.card{background:#1c1f26;border:1px solid #2a2e38;border-radius:10px;padding:18px 20px;margin:0 0 22px}
.card h2{font-size:16px;margin:0 0 10px}.concept{font-size:11px;background:#243b52;color:#bcd8f5;padding:2px 8px;border-radius:6px;margin-left:8px}
.card h3{font-size:12.5px;color:#9aa3b2;text-transform:uppercase;letter-spacing:.03em;margin:16px 0 8px;border-top:1px solid #262a34;padding-top:12px}
.grid{display:grid;gap:1px;background:#2a2e38;border:1px solid #2a2e38;width:max-content}.grid i{width:%CELL%px;height:%CELL%px;display:block}
.gwrap{display:inline-flex;flex-direction:column;gap:3px;vertical-align:top}.glab{font-size:10px;color:#8b93a3}
.grow{display:flex;align-items:center;gap:10px}.arrow{color:#8b93a3;font-size:18px;margin:0 6px}
.pair{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:12px;margin:0 0 10px;display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}
.ptit{font-weight:700;color:#cfd6e2;width:100%}
.ast,.sol{background:#0f1116;border:1px solid #262a34;border-radius:6px;padding:10px;font:11.5px/1.45 SFMono-Regular,Menlo,monospace;white-space:pre;overflow-x:auto;color:#b8e0c8;margin:0}
.sol{color:#ffe6a8;border-color:#4a3f1a}
.axis{margin:6px 0;padding:8px;background:#171a20;border:1px solid #262a34;border-radius:6px}
.axis .ok{color:#8fdca8;margin:0 4px}.axis .no{color:#7a6b6b;margin:0 4px}
.vs{margin-top:5px;color:#9aa3b2}.vs code{background:#0f1116;padding:2px 6px;border-radius:4px;color:#9fb4d8}
.amb{color:#ffcf9a}.note{color:#9aa3b2;margin:6px 0}
.exec{display:flex;flex-direction:column;gap:8px}
.ecase{background:#171a20;border:1px solid #262a34;border-radius:8px;padding:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.ecase.test{border-color:#3a5a7a}.etit{font-weight:700;min-width:74px}
.toc{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}.toc a{color:#cfd6e2;text-decoration:none;background:#1c1f26;border:1px solid #2a2e38;border-radius:6px;padding:5px 10px;font-size:12px}
""".replace("%CELL%", str(CELL))


def build():
    cards, toc = [], []
    paths = dict(list_tasks("easy_a"))
    for tid in TIDS:
        task = load_task(paths[tid])
        card, (ok, concept) = task_card(tid, task)
        cards.append(f'<a id="{tid}"></a>' + card)
        mark = "✅" if ok else ("❌" if ok is False else "?")
        toc.append(f'<a href="#{tid}">{tid} · {concept} {mark}</a>')
    doc = (f'<!doctype html><meta charset="utf-8"><title>easy tasks → concepts</title>'
           f'<style>{CSS}</style><h1>easy task로 쉬운 개념 만들기 — AST anti-unification</h1>'
           f'<p class="hsub">per-pair program(AST) 재료 → 뼈대 COMM·목적지 DIFF → 목적지를 표현식 탐색으로 '
           f'anti-unify → TASK.solution(개념: 고정위치·상대이동·격자코너)</p>'
           f'<div class="toc">{"".join(toc)}</div>{"".join(cards)}')
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traces", "easy_concepts_report.html")
    with open(out, "w") as f:
        f.write(doc)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
    print("open it:  open", p)
