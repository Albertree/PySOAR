# -*- coding: utf-8 -*-
"""
pixel_mapping_report -- PIXEL level 매핑 리포트. 각 태스크 P0 의 **G0-pixels ↔ G1-pixels 를
같은 좌표끼리 교차 비교**(cross-grid)한 결과를 시각화한다. PIXEL property 는 color·coord 2개뿐
(ARC-solver/ARCKG/pixel.py). 비교는 kg_compare 로 **COMM/DIFF 만**(뺄셈·delta·크기비교 없음).

각 태스크 섹션: (1) G0·G1 격자, (2) **diff 맵** — 색이 바뀐 셀(color DIFF)을 빨강 테두리로 강조,
(3) 셀 호버 → 그 pixel 쌍의 comparison receipt(color·coordinate COMM/DIFF). 이게 object mapping 이
실패한(=object 대응으로 변환 못 찾은) 태스크의 pixel 수준 변환 스펙이다. G0·G1 크기가 다르면(크기변화)
같은좌표 비교가 성립 안 해 그 사유를 표시.

    python3 arc/pixel_mapping_report.py     # -> arc/pixel_mapping_report.html
"""
from __future__ import annotations

import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pixel_mapping_report.html")

PALETTE = {0: "#1b1b1b", 1: "#0074D9", 2: "#FF4136", 3: "#2ECC40", 4: "#FFDC00",
           5: "#AAAAAA", 6: "#F012BE", 7: "#FF851B", 8: "#7FDBFF", 9: "#870C25"}


def _load():
    """대시보드와 **동일한 survey** (easy·made·ARC-AGI) 를 순서대로 반환."""
    from arc.make_made_tasks import write_all
    write_all()
    from arc.focus_solver import _load_survey, SURVEY_AGI
    return _load_survey(agi_ids=SURVEY_AGI)


def _grid(grid, diffs=None, receipts=None, gid=""):
    """격자를 inline-grid div 로 (셀 항상 정사각). diffs=변화 셀 집합이면 빨강 테두리 + 호버 receipt."""
    diffs = diffs or set()
    receipts = receipts or {}
    ncol = len(grid[0]) if grid and grid[0] else 1
    cells = []
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            bg = PALETTE.get(v, "#333")
            if (r, c) in diffs:
                pop = receipts.get((r, c), "")
                cells.append(f"<div class='px d' style='background:{bg}'>"
                             f"<span class=pop>{pop}</span></div>")
            else:
                cells.append(f"<div class=px style='background:{bg}'></div>")
    return f"<div class=mg style='grid-template-columns:repeat({ncol},15px)'>{''.join(cells)}</div>"


def _receipt(kg_compare, p0node, p1node):
    """두 pixel 노드의 comparison receipt(dict) → 사람용 축약 문자열 (color·coord COMM/DIFF, delta 없음)."""
    rel = kg_compare(p0node, p1node)["result"]
    cat = rel.get("category", {})
    col = cat.get("color", {})
    crd = cat.get("coordinate", {}).get("category", {}) if isinstance(cat.get("coordinate"), dict) else {}
    j0, j1 = p0node.to_json(), p1node.to_json()
    lines = [f"G0: color={j0['color']} @({j0['coordinate']['row_index']},{j0['coordinate']['col_index']})",
             f"G1: color={j1['color']} @({j1['coordinate']['row_index']},{j1['coordinate']['col_index']})",
             f"color: {col.get('type', '?')}   coordinate: {cat.get('coordinate', {}).get('type', '?')}"]
    return html.escape("\n".join(lines))


def _task_section(tid, task):
    from arc.focus_solver import build_arckg, index_arckg
    g0raw = task["train"][0]["input"]
    g1raw = task["train"][0]["output"]
    d0, d1 = (len(g0raw), len(g0raw[0])), (len(g1raw), len(g1raw[0]))
    hdr = f"<h2>{tid} <span class=dim>P0.G0 {d0[0]}×{d0[1]} ↔ P0.G1 {d1[0]}×{d1[1]}</span></h2>"
    if d0 != d1:
        note = ("<div class=note>G0·G1 <b>크기가 달라</b> 같은좌표 pixel 비교가 성립하지 않는다 "
                "(크기변화 — 셀 단위 재채색으로 변환 불가). object/pixel 재채색 대상 아님.</div>")
        return (f"<section>{hdr}<div class=row>"
                f"<div class=gcol><span class=glbl>G0</span>{_grid(g0raw)}</div>"
                f"<div class=gcol><span class=glbl>G1</span>{_grid(g1raw)}</div></div>{note}</section>")
    # 같은 크기 — ARCKG pixels 로 같은좌표 비교
    from ARCKG.comparison import compare as kg_compare
    root = build_arckg(tid, task)
    idx = index_arckg(root)
    g0id, g1id = f"{root.node_id}.P0.G0", f"{root.node_id}.P0.G1"
    px0 = {(idx["nodes"][p].to_json()["coordinate"]["row_index"],
            idx["nodes"][p].to_json()["coordinate"]["col_index"]): p for p in idx["pixels"].get(g0id, [])}
    px1 = {(idx["nodes"][p].to_json()["coordinate"]["row_index"],
            idx["nodes"][p].to_json()["coordinate"]["col_index"]): p for p in idx["pixels"].get(g1id, [])}
    diffs, receipts = set(), {}
    for r in range(d0[0]):
        for c in range(d0[1]):
            if g0raw[r][c] != g1raw[r][c]:                 # color DIFF (같은좌표라 coord COMM)
                diffs.add((r, c))
                p0, p1 = px0.get((r, c)), px1.get((r, c))
                if p0 and p1:
                    receipts[(r, c)] = _receipt(kg_compare, idx["nodes"][p0], idx["nodes"][p1])
    summ = (f"<div class=summ>변화(color DIFF) 셀 <b>{len(diffs)}</b> / 전체 {d0[0] * d0[1]} — "
            f"이 셀들을 G1 색으로 재채색하면 G0→G1. (호버=pixel receipt · delta 없음)</div>")
    return (f"<section>{hdr}<div class=row>"
            f"<div class=gcol><span class=glbl>G0 (input)</span>{_grid(g0raw)}</div>"
            f"<div class=gcol><span class=glbl>G1 (output)</span>{_grid(g1raw)}</div>"
            f"<div class=gcol><span class=glbl>G0 · 변화셀 강조(호버)</span>{_grid(g0raw, diffs, receipts)}</div>"
            f"</div>{summ}</section>")


def _safe_section(tid, task):
    try:
        return _task_section(tid, task)
    except Exception as e:                                  # noqa: BLE001
        return f"<section><h2>{tid}</h2><div class=note>오류: {html.escape(str(e))}</div></section>"


CSS = """
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:22px}
h1{font-size:17px;margin:0 0 4px} .lead{color:#8b949e;margin-bottom:18px;max-width:900px}
section{border:1px solid #30363d;border-radius:9px;padding:12px 16px;margin:0 0 15px;background:#161b22}
h2{font-size:15px;margin:0 0 9px} .dim{color:#8b949e;font-weight:normal;font-size:12px;margin-left:6px}
.row{display:flex;gap:26px;align-items:flex-start;flex-wrap:wrap}
.gcol{display:flex;flex-direction:column;gap:5px;align-items:flex-start}
.glbl{font-size:11px;color:#8b949e}
.mg{display:inline-grid;gap:1px;background:#30363d;border:1px solid #30363d}
.px{width:15px;height:15px}
.px.d{outline:2px solid #f85149;outline-offset:-2px;position:relative;cursor:help;z-index:1}
.px.d:hover{z-index:50}
.px.d .pop{display:none;position:absolute;left:18px;top:0;z-index:60;white-space:pre;background:#08080a;
 border:1px solid #f85149;border-radius:5px;padding:6px 8px;font:10.5px/1.4 ui-monospace;color:#cde;width:max-content}
.px.d:hover .pop{display:block}
.summ{margin-top:9px;color:#adbac7;font-size:12px} .summ b{color:#3fb950}
.note{margin-top:9px;color:#e3b341;font-size:12px} .note b{color:#f0a}
"""


def build():
    tasks = _load()
    sections = "".join(_safe_section(tid, task) for tid, task in tasks)
    doc = (f"<!doctype html><meta charset='utf-8'><title>ARBOR pixel mapping</title>"
           f"<style>{CSS}</style>"
           f"<h1>ARBOR — PIXEL mapping (P0.G0 pixels ↔ P0.G1 pixels)</h1>"
           f"<p class=lead>PIXEL property = <b>color·coord</b> 2개뿐. 같은 좌표끼리 <b>교차 비교</b>(cross-grid)해 "
           f"color <b>COMM/DIFF</b> 만 — <b>뺄셈·delta·크기비교 없음</b>. 빨강 테두리 = 색이 바뀐 셀(color DIFF) "
           f"= pixel 수준 변환 스펙. object mapping 이 대응을 못 찾은 태스크를 GRID 아래 pixel 로 바로 본다.</p>"
           f"{sections}")
    with open(OUT, "w") as f:
        f.write(doc)
    return OUT


if __name__ == "__main__":
    print("wrote", build())
