# -*- coding: utf-8 -*-
"""
hypothesis_space — 4 구역(이미지·size·color·contents). 동일 크기 카드로 grid 를 2-2-1 배치(pair0/pair1/test).
카드 사이를 **선**으로 잇고 COMM/DIFF(초록/빨강). **PaG0 를 훈련 입력(P1G0)과도 비교**(세로선)해 그 결과를
논리에 쓴다. **2차(relation끼리 비교)도 within 선끼리 잇는 세로선**으로. 예측값은 카드 밖(캡션)에.
DIFF-DIFF = 변화가 같을 수 있어 예측대상 · 갈림(COMM-DIFF) = 예측불가.

    python3 -m arc.compare_viz.hypothesis_space     # -> arc/compare_viz/hypothesis_space.html
"""
from __future__ import annotations

import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "hypothesis_space.html")
PALETTE = ["#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
           "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25"]
TASKS = ["easy000a", "easy000b", "easy000c", "easy000d", "easy000e", "easy000f", "easy000g",
         "easy000h", "easy000i", "made000a", "made000b",
         "08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab", "845d6e51", "868de0fa"]   # dashboard 17
COK, CNO, CAMB, CG = "#3fb950", "#f85149", "#d29922", "#4b5563"


def _sz(g):
    return (len(g), len(g[0]))


def _colors(g):
    return frozenset(v for r in g for v in r)


def _grid_html(g, mx=84):
    n = max(len(g), len(g[0])) if g and g[0] else 1
    cs = max(4, min(11, mx // n))
    rows = "".join("<tr>" + "".join(
        f"<td style='width:{cs}px;height:{cs}px;background:{PALETTE[v] if isinstance(v, int) and 0 <= v < 10 else '#333'}'></td>"
        for v in r) + "</tr>" for r in g)
    return f"<table class=g>{rows}</table>"


def _qgrid(hw):
    return _grid_html([["?"] * hw[1] for _ in range(hw[0])]) if hw else "<div class=q>?</div>"


def _color_inner(cs):
    if cs is None:
        return "<div class=q>?</div>"
    return "<div class=sws>" + "".join(f"<span class=sw style='background:{PALETTE[c]}'></span>" for c in sorted(cs)) + "</div>"


def _inner(kind, g):
    if kind == "size":
        return f"<div class=val>{len(g)}×{len(g[0])}</div>"
    if kind == "color":
        return _color_inner(_colors(g))
    return _grid_html(g)


def _card(inner):
    return f"<div class=cx>{inner}</div>"


def _verdict(prop, a, b):
    if prop == "size":
        return _sz(a) == _sz(b)
    if prop == "color":
        return _colors(a) == _colors(b)
    return a == b


def _hline(kind, a, b, faint=None):
    if faint:
        return f"<div class='ln h' style='--lc:{CG}'><span class=lb style='color:#8b949e'>{faint}</span></div>"
    ok = _verdict(kind, a, b)
    lc = COK if ok else CNO
    return f"<div class='ln h' style='--lc:{lc}'><span class=lb style='color:{lc}'>{'COMM' if ok else 'DIFF'}</span></div>"


def _vline(kind, a, b, faint=None):
    if faint:
        return f"<div class='ln v' style='--lc:#333'><span class=lb style='color:#6e7681'>{faint}</span></div>"
    ok = _verdict(kind, a, b)
    lc = COK if ok else CNO
    return f"<div class='ln v' style='--lc:{lc}'><span class=lb style='color:{lc}'>{'COMM' if ok else 'DIFF'}</span></div>"


def _twoline(kind, A0, A1, B0, B1):
    """2차 = within(P0) 선과 within(P1) 선을 잇는 세로선."""
    v0, v1 = _verdict(kind, A0, A1), _verdict(kind, B0, B1)
    if v0 == v1:
        lab, lc = f"{'COMM' if v0 else 'DIFF'}↔{'COMM' if v1 else 'DIFF'}", (COK if v0 else CAMB)
        tip = "일치(변화 같을 수 있음→예측)" if not v0 else "일치(불변)"
    else:
        lab, lc = "COMM↔DIFF", CNO
        tip = "갈림→예측불가"
    return (f"<div class='ln v two' style='--lc:{lc}' title='{tip}'>"
            f"<span class=lb style='color:{lc}'>{lab}</span></div>")


def _size_transform(train, paG0):
    pairs = [(_sz(e["input"]), _sz(e["output"])) for e in train]
    ops = {"-": lambda x, k: x - k, "+": lambda x, k: x + k, "*": lambda x, k: x * k, "//": lambda x, k: x // k if k else 0}

    def find(axis, own):
        cands = [("H0", lambda H, W: H), ("W0", lambda H, W: W)]
        for nm, fn in list(cands):
            for k in (1, 2, 3):
                for os_, ofn in ops.items():
                    cands.append((f"{nm}{os_}{k}", lambda H, W, fn=fn, ofn=ofn, k=k: ofn(fn(H, W), k)))
        cands.sort(key=lambda d: not d[0].startswith(own))
        for desc, fn in cands:
            if all(fn(i[0], i[1]) == o[axis] for i, o in pairs):
                return desc, fn
        return None, None
    dh, fh = find(0, "H0")
    dw, fw = find(1, "W0")
    if fh and fw and not (dh == "H0" and dw == "W0"):
        H, W = _sz(paG0)
        return f"{dh},{dw}", (fh(H, W), fw(H, W))
    return None, None


def _global_map(train):
    mp = {}
    for e in train:
        i, o = e["input"], e["output"]
        if _sz(i) != _sz(o):
            return None
        for r in range(len(i)):
            for c in range(len(i[0])):
                a, b = i[r][c], o[r][c]
                if a in mp and mp[a] != b:
                    return None
                mp[a] = b
    return mp


def _ck(ok, name, pred=None, reason=None):
    if ok:
        return f"<span class=hy>{name}<b>→{html.escape(str(pred))}</b></span>"
    return f"<span class=rj>{name}✗<span class=rs>{html.escape(reason or '')}</span></span>"


def _pred_size(train, paG0):
    pairs = [(e["input"], e["output"]) for e in train]
    preds, ch = set(), []
    keep = all(_sz(i) == _sz(o) for i, o in pairs)
    ch.append(_ck(keep, "keep", f"{_sz(paG0)}", "크기 안 유지"))
    if keep:
        preds.add(_sz(paG0))
    outs = [_sz(o) for _, o in pairs]
    const = all(s == outs[0] for s in outs)
    ch.append(_ck(const, "const", f"{outs[0]}", "출력 제각각"))
    if const:
        preds.add(outs[0])
    td, tp = _size_transform(train, paG0)
    if td:
        ch.append(_ck(True, f"식[{td}]", f"{tp}"))
        preds.add(tp)
    return (next(iter(preds)) if len(preds) == 1 else None), "".join(ch)


def _pred_color(train, paG0):
    pairs = [(e["input"], e["output"]) for e in train]
    preds, ch = set(), []
    keep = all(_colors(i) == _colors(o) for i, o in pairs)
    ch.append(_ck(keep, "keep", sorted(_colors(paG0)), "색집합 바뀜"))
    if keep:
        preds.add(frozenset(_colors(paG0)))
    outs = [_colors(o) for _, o in pairs]
    const = all(s == outs[0] for s in outs)
    ch.append(_ck(const, "const", sorted(outs[0]), "출력 제각각"))
    if const:
        preds.add(frozenset(outs[0]))
    gm = _global_map(train)
    if gm and any(k != v for k, v in gm.items()):
        pc = frozenset(gm.get(v, v) for v in _colors(paG0))
        ch.append(_ck(True, "map", sorted(pc)))
        preds.add(pc)
    return (next(iter(preds)) if len(preds) == 1 else None), "".join(ch)


def _pred_contents(train, paG0):
    pairs = [(e["input"], e["output"]) for e in train]
    if all(i == o for i, o in pairs):
        return paG0, "항등"
    outs = [o for _, o in pairs]
    if all(o == outs[0] for o in outs):
        return outs[0], "상수출력"
    gm = _global_map(train)
    if gm and any(k != v for k, v in gm.items()):
        return [[gm.get(v, v) for v in row] for row in paG0], "전역recolor"
    return None, "미결→하강"


def _column(kind, task):
    train = task["train"]
    paG0 = task["test"][0]["input"]
    A0, A1 = train[0]["input"], train[0]["output"]
    B0, B1 = train[1]["input"], train[1]["output"]
    img = kind == "img"
    prop = None if img else kind

    def card(g):
        return _card(_inner("img" if img else kind, g))
    psize, sch = _pred_size(train, paG0)
    pcol, cch = _pred_color(train, paG0)
    pg, note = _pred_contents(train, paG0)
    # Pa.G1 예측 카드(시각) — 값/규칙은 카드 밖 캡션으로
    if kind == "size":
        pinner, cap = _qgrid(psize), sch
    elif kind == "color":
        pinner, cap = _color_inner(pcol), cch
    else:  # img / contents
        pinner = _grid_html(pg) if pg is not None else _qgrid(psize)
        cap = f"<span class=nt>{note}</span>"

    def hl(a, b):
        return f"<div class='ln h' style='--lc:{CG}'><span class=lb>→</span></div>" if img else _hline(kind, a, b)

    def vl(a, b):
        return f"<div class='ln v' style='--lc:{CG}'><span class=lb>↓</span></div>" if img else _vline(kind, a, b)
    two = "<div class='ln v' style='--lc:#333'><span class=lb style='color:#6e7681'>2차</span></div>" if img \
        else _twoline(kind, A0, A1, B0, B1)

    kids = [
        card(A0), hl(A0, A1), card(A1),
        vl(A0, B0), two, vl(A1, B1),
        card(B0), hl(B0, B1), card(B1),
        vl(B0, paG0), "<div class=tlab>테스트<br><span class=sub>PaG0↔훈련입력</span></div>",
        f"<div class='ln v' style='--lc:#333'><span class=lb style='color:#6e7681'>예측</span></div>",
        card(paG0),
        (f"<div class='ln h' style='--lc:{CG}'><span class=lb style='color:#8b949e'>가설</span></div>"),
        _card(pinner),
    ]
    hd = {"img": "이미지", "size": "size", "color": "color", "contents": "contents"}[kind]
    predcap = f"<div class=predcap><b>Pa.G1 예측</b> {cap}</div>" if not img else ""
    return f"<div class=colwrap><div class=colhd>{hd}</div><div class=col>{''.join(kids)}</div>{predcap}</div>"


def _num_search(train):
    """NUMBER(크기) DIFF 분석 = brute-force: {H0,W0}×{−,+,×,//}×{1,2,3}. 각 후보를 전 pair 로 검증.
    반환 = {axis: (탐색개수, 생존리스트[(expr,per_pair)], 기각수, 기각샘플[expr])}."""
    pairs = [(_sz(e["input"]), _sz(e["output"])) for e in train]
    ops = [("−", lambda x, k: x - k), ("+", lambda x, k: x + k), ("×", lambda x, k: x * k), ("//", lambda x, k: x // k if k else 0)]
    atoms = [("H0", lambda H, W: H), ("W0", lambda H, W: W)]

    def axis(ti, own):
        cands = list(atoms)
        for nm, fn in atoms:
            for k in (1, 2, 3):
                for osym, ofn in ops:
                    cands.append((f"{nm}{osym}{k}", lambda H, W, fn=fn, ofn=ofn, k=k: ofn(fn(H, W), k)))
        cands.sort(key=lambda d: not d[0].startswith(own))
        surv, rej = [], []
        for desc, fn in cands:
            per = [(i, fn(i[0], i[1]), o[ti]) for i, o in pairs]
            if all(g == e for _, g, e in per):
                surv.append((desc, per))
            else:
                rej.append(desc)
        return (len(cands), surv, len(rej), rej[:3])
    return {"H": axis(0, "H0"), "W": axis(1, "W0")}


def _proc_size(train, paG0):
    pairs = [(e["input"], e["output"]) for e in train]
    within = ["COMM" if _sz(i) == _sz(o) else "DIFF" for i, o in pairs]
    head = f"<b>size</b> <span class=tp>NUMBER</span> · within {'/'.join(within)}"
    if all(v == "COMM" for v in within):
        outs = [_sz(o) for _, o in pairs]
        const = all(s == outs[0] for s in outs)
        val = _sz(paG0)
        extra = "→ KEEP" + (" (+CONST 수렴)" if const and outs[0] == val else (" · CONST✗(출력 제각각)" if not const else ""))
        return head, extra, f"DECIDE size(Pa.G1)={val[0]}×{val[1]}", "ok"
    # DIFF → brute-force
    sr = _num_search(train)
    outs = [_sz(o) for _, o in pairs]
    const = all(s == outs[0] for s in outs)
    parts = []
    for ax in ("H", "W"):
        n, surv, nrej, samp = sr[ax]
        sv = " ".join(f"<span class=hy>{d}✓</span>" for d, _ in surv) or "<span class=rj>생존없음</span>"
        parts.append(f"<div class=bf><b>{ax}축</b> 탐색 {{H0,W0}}×{{−+×//}}×{{1,2,3}} = {n}후보: {sv} "
                     f"· <span class=rj>{'·'.join(samp)}✗ … {nrej}개 기각</span></div>")
    if const:
        parts.append(f"<div class=bf>CONST(출력 일정): <span class=hy>{outs[0]}✓</span></div>")
    ok_h = sr["H"][1]
    ok_w = sr["W"][1]
    H, W = _sz(paG0)
    preds = set()
    if ok_h and ok_w:
        preds.add((ok_h[0][0], ok_w[0][0]))
    if const:
        preds.add(("const", outs[0]))
    # 예측값 (수렴?)
    vals = set()
    if ok_h and ok_w:
        # apply first survivor expr to PaG0 via re-search fn — recompute
        _, tp = _size_transform(train, paG0)
        if tp:
            vals.add(tp)
    if const:
        vals.add(outs[0])
    if len(vals) == 1:
        v = next(iter(vals))
        dec = f"DECIDE size(Pa.G1)={v[0]}×{v[1]}"
        st = "ok"
    elif len(vals) > 1:
        dec = f"AMBIGUOUS {sorted(vals)}"
        st = "amb"
    else:
        dec = "DESCEND (크기식 없음)"
        st = "dn"
    return head, "".join(parts), dec, st


def _proc_color(train, paG0):
    """color(SET) — KEEP/CONST/SET-MAP(추가·삭제)/MAP 를 **다 생성·검증 → Pa.G0 적용 → 수렴 검사**
    (size 로직과 통일; CONST 로 단락하던 결함 수정)."""
    ins = [_colors(e["input"]) for e in train]
    outs = [_colors(e["output"]) for e in train]
    pairs = list(zip(ins, outs))
    within = ["COMM" if i == o else "DIFF" for i, o in pairs]
    head = f"<b>color</b> <span class=tp>SET</span> · within {'/'.join(within)}"
    pa = _colors(paG0)
    cands = []   # (표기, 예측)
    if all(i == o for i, o in pairs):                                   # KEEP
        cands.append(("KEEP", pa))
    if all(o == outs[0] for o in outs):                                 # CONST
        cands.append((f"CONST{sorted(outs[0])}", frozenset(outs[0])))
    add0, rem0 = outs[0] - ins[0], ins[0] - outs[0]                     # SET-MAP(멤버십)
    if (add0 or rem0) and all((ci - rem0) | add0 == co for ci, co in pairs):
        cands.append((f"SET-MAP(−{sorted(rem0)}+{sorted(add0)})", (pa - rem0) | add0))
    gm = _global_map(train)                                            # MAP(전역 재채색)
    if gm and any(k != v for k, v in gm.items()):
        cands.append(("MAP", frozenset(gm.get(v, v) for v in pa)))
    chips = " ".join(f"<span class=hy>{n}<b>→{sorted(p)}</b></span>" for n, p in cands) or "<span class=rj>후보 없음</span>"
    ana = f"<div class=bf>멤버십: 추가{sorted(add0)} 삭제{sorted(rem0)}</div><div class=bf>생존 가설: {chips}</div>"
    preds = {p for _, p in cands}
    if len(preds) == 1:
        return head, ana, f"DECIDE color(Pa.G1)={sorted(next(iter(preds)))}" + (
            " (여러 가설 수렴)" if len(cands) > 1 else ""), "ok"
    if len(preds) > 1:
        return head, ana, f"AMBIGUOUS {[sorted(p) for p in preds]} — Pa.G0 에서 갈림", "amb"
    return head, ana, "DESCEND (일관 규칙 없음 → 값이 객체/순위 의존)", "dn"


def _proc_contents(train, paG0):
    pairs = [(e["input"], e["output"]) for e in train]
    within = ["COMM" if i == o else "DIFF" for i, o in pairs]
    head = f"<b>contents</b> <span class=tp>CLASS</span> · within {'/'.join(within)}"
    pg, note = _pred_contents(train, paG0)
    if all(v == "COMM" for v in within):
        return head, "→ 항등", "DECIDE contents(Pa.G1)=Pa.G0", "ok"
    if pg is not None:
        return head, f"<div class=bf>예외적 GRID표현: {note}</div>", f"DECIDE ({note})", "ok"
    return head, "<div class=bf>class = equality 뿐 → 함수 못 만듦(쪼갤 내부 없음)</div>", "DESCEND (객체/픽셀로 분해)", "dn"


def _process(task):
    rows = ""
    for fn in (_proc_size, _proc_color, _proc_contents):
        head, ana, dec, st = fn(task["train"], task["test"][0]["input"])
        rows += (f"<div class=proc><div class=phead>{head}</div>{('<div class=pana>'+ana+'</div>') if ana else ''}"
                 f"<div class='pdec {st}'>▶ {dec}</div></div>")
    return f"<div class=procwrap><div class=pt>hypothesize 과정 · 결정</div>{rows}</div>"


def _section(tid, task):
    cols = "".join(_column(k, task) for k in ("img", "size", "color", "contents"))
    return f"<div class=task data-task='{tid}'><div class=cols>{cols}</div>{_process(task)}</div>"


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arc.make_made_tasks import write_all
    write_all()
    from arc.focus_solver import _load_survey, SURVEY_AGI
    tasks = {**dict(_load_survey(agi_ids=SURVEY_AGI)), **dict(_load_survey(include_easy=True, include_made=True))}
    secs = "".join(_section(tid, tasks[tid]) for tid in TASKS)
    opts = "".join(f"<option value='{t}'>{t}</option>" for t in TASKS)
    doc = f"""<!doctype html><meta charset='utf-8'><title>hypothesis space — PaG1 예측</title>
<style>{CSS}</style>
<h1>hypothesis space — 카드 2-2-1 · 선으로 COMM/DIFF · PaG0 도 훈련입력과 비교 · Pa.G1 예측</h1>
<p class=lead>문제: <select id=task>{opts}</select> &nbsp;
가로=within(G0→G1) · 세로=cross(G0끼리·G1끼리, <b>PaG0↔훈련입력</b> 포함) · 가운데=2차(within끼리) ·
<span style='color:{COK}'>초록COMM</span>/<span style='color:{CNO}'>빨강DIFF</span> · 예측값은 카드 아래.</p>
{secs}
<script>
const T=document.getElementById('task');
function show(){{document.querySelectorAll('.task').forEach(d=>d.style.display=d.dataset.task===T.value?'block':'none');}}
T.onchange=show; show();
</script>"""
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:15px;margin:0 0 4px} .lead{color:#8b949e;margin:0 0 16px;max-width:1000px}
select{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font:13px ui-monospace}
.cols{display:flex;gap:16px;align-items:flex-start;overflow-x:auto;padding-bottom:6px}
.colwrap{border:1px solid #30363d;border-radius:9px;padding:8px 12px 10px;background:#161b22;width:300px;flex:0 0 300px;box-sizing:border-box}
.colhd{text-align:center;color:#e6edf3;font-size:13px;margin-bottom:8px;border-bottom:1px solid #30363d;padding-bottom:5px}
.col{display:grid;grid-template-columns:96px 84px 96px;justify-items:center;align-items:center}
.cx{width:96px;height:96px;display:flex;align-items:center;justify-content:center;border:1px solid #23272e;border-radius:7px;background:#0d1117;overflow:hidden}
.ln{position:relative;display:flex;align-items:center;justify-content:center}
.ln.h{width:100%;height:96px} .ln.v{width:96px;height:54px}
.ln.h::before{content:'';position:absolute;left:4px;right:4px;top:50%;border-top:2px solid var(--lc)}
.ln.v::before{content:'';position:absolute;top:3px;bottom:3px;left:50%;border-left:2px solid var(--lc)}
.ln.v.two{width:84px}
.lb{position:relative;z-index:1;background:#161b22;padding:1px 5px;border-radius:8px;font-size:10.5px;font-weight:bold;color:#8b949e}
.tlab{width:84px;height:54px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#8b949e;font-size:11px;text-align:center}
.sub{font-size:9px;color:#6e7681}
table.g{border-collapse:collapse} table.g td{border:1px solid #1c1c1c}
.val{font-size:20px;font-weight:bold;color:#79c0ff} .q{font-size:22px;color:#d29922}
.sws{display:flex;flex-wrap:wrap;gap:3px;justify-content:center;max-width:86px} .sw{width:16px;height:16px;border:1px solid #333;border-radius:3px}
.predcap{margin-top:8px;padding-top:6px;border-top:1px dashed #30363d;display:flex;flex-wrap:wrap;gap:4px;align-items:flex-start;font-size:11px;color:#adbac7;width:100%;box-sizing:border-box;word-break:break-word}
.hy{background:#0f2a17;color:#3fb950;border:1px solid #238636;border-radius:9px;padding:1px 6px;font-size:11px;white-space:normal;max-width:100%}
.hy b{color:#7ee787} .rj{color:#6e7681;font-size:11px} .rs{color:#8b6f3a;font-size:10px;margin-left:2px} .nt{color:#d29922;font-size:11px}
.procwrap{margin-top:14px;border:1px solid #30363d;border-radius:9px;background:#12161c;padding:10px 14px;max-width:900px}
.procwrap .pt{color:#e6edf3;font-size:13px;margin-bottom:8px;border-bottom:1px solid #30363d;padding-bottom:5px}
.proc{margin:8px 0;padding:6px 0;border-bottom:1px dashed #23272e}
.phead{color:#adbac7} .tp{background:#1f2937;color:#9ecbff;border-radius:5px;padding:0 6px;font-size:11px;margin:0 4px}
.pana{margin:4px 0 4px 10px} .bf{color:#8b949e;font-size:12px;margin:2px 0}
.bf b{color:#adbac7}
.pdec{margin-left:10px;font-weight:bold;font-size:12px}
.pdec.ok{color:#3fb950} .pdec.amb{color:#d29922} .pdec.dn{color:#f0883e}
"""


if __name__ == "__main__":
    print("wrote", build())
