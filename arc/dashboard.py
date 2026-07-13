# -*- coding: utf-8 -*-
"""
dashboard -- two-screen keyboard-driven visualizer of the PySOAR solving process.

  Screen 1  TASK BROWSER : task cards. ←/→/↑/↓ to move, Enter to open.
  Screen 2  STEP VIEWER  : every ATOMIC change is one step. ←/→ to step,
                           Esc back, Home/End jump.

Regions (step viewer):
  top    : phase breadcrumb (input → propose → decide → apply → output)
  left   : cycle map (every change; wide)
  c-left : working memory (narrow; changed WME highlighted)
  center : RULES -- which production read which WM and proposed/changed what
           (the responsible rule's IF→THEN, conditions matched against WM)
  right  : problem (example pairs stacked, input→output) · candidates (separate)
  bottom : what this step did (+ ARCKG/DSL detail)

Trace from arc/fine_trace.py (real PySOAR cycle, finest grain).

Usage:  python arc/dashboard.py easy   ->  dashboard.html
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _kg_detail(kg, op):
    # focus_solver 의 kg 는 모양이 다르다(compares/relations/roles). _focus 마커가
    # 있으면 thinking_ops.focus_detail 로 라우팅한다 (expr_solver 경로는 그대로).
    if kg.get("_focus"):
        from arc.thinking_ops import focus_detail
        return focus_detail(kg, op)
    if op == "observe":
        objs = [{"pair": i, "color": pr["tin"]["color"], "cells": sorted(pr["tin"]["cells"])}
                for i, pr in enumerate(kg.get("pairs", [])) if pr.get("tin")]
        return {"kind": "observe", "objects": objs}
    if op == "compare":
        rows = [{"pair": i, "in_coord": list(s["ctx"]["obj_coord"]),
                 "in_color": s["ctx"]["obj_color"], "out_coord": list(s["out_coord"]),
                 "out_color": s["out_color"]} for i, s in enumerate(kg.get("samples", []))]
        return {"kind": "compare", "rows": rows}
    if op == "generalize":
        return {"kind": "generalize",
                "exprs": {k: n for k, (f, n) in (kg.get("args") or {}).items()}}
    if op == "compose":
        return {"kind": "compose", "answer": kg.get("answer")}
    return {"kind": op}


OP_DOCS = {
    "observe": "ARCKG 계층(task→pair→grid→object)을 WM에 적재 → ^observed",
    "compare": "target in→out 비교 → ^compared, 변환 필요 여부",
    "generalize": "각 arg를 일반 표현식으로 resolve → ^schema-ready, ^expr-*",
    "compose": "make_grid + coloring 으로 답 조립 → ^answer-ready",
    "submit": "완료 표시 → ^done",
}


def rules_manifest():
    from arc.expr_solver import PRODUCTIONS
    out = []
    for p in PRODUCTIONS:
        out.append({
            "name": p.name,
            "if": [{"id": c.id, "attr": c.attr, "val": c.value, "neg": c.negated}
                   for c in p.conditions],
            "then": [{"id": a.id, "attr": a.attr, "val": a.value, "pref": a.pref}
                     for a in p.actions],
        })
    return out


def wm_deltas(wm_states):
    """dedupe 된 wm_states(각 원소 = 그 시점 full WM triple 리스트)를 base+delta 로 압축한다.
    각 결과 원소 = {"a":[추가 triple], "r":[삭제 triple]} (직전 state 대비). WM 은 단조 증가라
    큰 relation receipt 가 매 state 반복 저장되는데(→ HTML 수십 MB), delta 면 추가된 그 순간에만
    실린다. JS wmStates() 가 순차 적용해 full WM 을 복원한다 — 표시되는 정보는 100% 동일."""
    deltas, prev, prevset = [], [], set()
    for st in wm_states:
        curset = {tuple(t) for t in st}
        add = [t for t in st if tuple(t) not in prevset]
        rem = [t for t in prev if tuple(t) not in curset]
        deltas.append({"a": add, "r": rem})
        prev, prevset = st, curset
    return deltas


def task_data(tid, task):
    from arc.fine_trace import _Tracer
    from arc.expr_solver import candidates
    # WM 스냅샷은 emit 이 연속중복 병합해 tr._wm_states 로 축소 저장(메모리 폭증 방지) — event 는
    # wm_state 인덱스만 보유. (구 fine_trace() 는 events 만 주어 _wm_states 접근 불가 → _Tracer 직접.)
    tr = _Tracer(task, tid)
    events = tr.run()
    wm_states = tr._wm_states
    cands = candidates(task, 3)
    gt = [tp["output"] for tp in task["test"]]
    correct_i = next((i for i, c in enumerate(cands) if c["grid"] == gt), None)
    return {
        "id": tid, "events": events, "wm_states": wm_deltas(wm_states),
        "grids": {"train": task["train"],
                  "test": [{"input": tp["input"]} for tp in task["test"]]},
        "candidates": [{"answer": c["grid"], "position": c["position"], "color": c["color"]}
                       for c in cands],
        "correct_attempt": correct_i, "n_steps": len(events),
    }


def build(dataset, tasks):
    data = {"dataset": dataset, "tasks": tasks,
            "rules": rules_manifest(), "op_docs": OP_DOCS}
    return _HTML.replace("__DATA__", json.dumps(data))


# ---------------------------------------------------------------------------
_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>PySOAR dashboard</title>
<style>
:root{--bg:#0f1117;--panel:#171a23;--p2:#1d2130;--line:#2a2f3e;--txt:#d7dbe6;
 --muted:#8b93a4;--accent:#5fd97f;--blue:#8ab4f8;--add:#16361f;--addt:#7fe79a;
 --rm:#3a1820;--rmt:#ff8a8a;--gold:#f3c969;}
*{box-sizing:border-box}
body{font:13px/1.45 -apple-system,Segoe UI,sans-serif;margin:0;background:var(--bg);color:var(--txt)}
.hint{color:var(--muted);font-size:11px} .ok{color:var(--accent)} .bad{color:var(--rmt)} b{color:var(--blue)}
#browser{padding:18px 24px}
#browser h1{font-size:17px;margin:0 0 4px} #browser .sub{color:var(--muted);margin-bottom:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.card{background:var(--panel);border:2px solid var(--line);border-radius:10px;padding:12px;cursor:pointer}
.card.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.card .tid{font-family:ui-monospace,monospace;font-size:13px;margin-bottom:6px} .card .meta{font-size:11px;color:var(--muted)}
/* four regions size by RATIO(fr) so the layout always fits the viewport width (no
   horizontal scroll). minmax(0,…) lets columns shrink below content; each panel
   scrolls its own overflow internally. ratios ≈ old 300:600:360:300 = 1:2:1.2:1 */
#stepper{display:none;grid-template-columns:230px minmax(0,1fr) minmax(0,1.9fr) minmax(0,1.15fr) minmax(0,0.95fr);
 grid-template-rows:auto auto 1fr auto;gap:6px;height:100vh;width:100vw;padding:6px}
/* panel = fixed header + scrolling body (header never overlaps content) */
.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 11px;
 min-height:0;display:flex;flex-direction:column;overflow:hidden}
.panel>h3{flex:0 0 auto;margin:0 0 6px;font-size:10px;color:var(--muted);text-transform:uppercase;
 letter-spacing:.6px;background:var(--panel);border-bottom:1px solid var(--line);padding-bottom:4px;position:relative}
.panel>div{flex:1 1 auto;overflow:auto;min-height:0}
.info{float:right;width:14px;height:14px;line-height:12px;text-align:center;border:1px solid var(--line);
 border-radius:50%;color:var(--muted);font-style:italic;font-size:10px;cursor:help;position:relative}
.info .tip{display:none;position:absolute;right:0;top:18px;width:255px;white-space:normal;text-transform:none;
 letter-spacing:0;font-weight:400;background:#0b0e14;border:1px solid var(--line);color:var(--txt);padding:7px 9px;
 border-radius:7px;z-index:99;font-size:11px;line-height:1.55;box-shadow:0 4px 14px rgba(0,0,0,.55)}
.info:hover .tip{display:block} .info .tip b{color:var(--accent)}
.info .g{color:var(--addt)} .info .r{color:var(--rmt)} .info .o{color:#ffb454} .info .bl{color:var(--blue)}
#sbar{grid-column:1/6;grid-row:1;display:flex;gap:14px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:7px 12px}
#phases{grid-column:1/6;grid-row:2;display:flex;gap:6px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
.ph{padding:3px 13px;border-radius:14px;border:1px solid var(--line);color:var(--muted);font-size:12px}
.ph.on{background:#2d4a86;border-color:var(--accent);color:#fff}
#ptree{grid-column:1;grid-row:3} #pmap{grid-column:2;grid-row:3} #pwm{grid-column:3;grid-row:3} #prules{grid-column:4;grid-row:3}
#pright{grid-column:5;grid-row:3;display:flex;flex-direction:column;gap:6px;min-height:0;overflow:hidden}
#pprob{flex:0 0 auto;max-height:42%} #pcand{flex:1 1 auto}
#pevent{grid-column:1/6;grid-row:4;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:9px 13px;max-height:96px;overflow:auto}
/* git dev-tree (좌측): cycle 노드 + substate 가지 */
#tree{overflow:auto} #tree svg{display:block}
.tn{cursor:pointer} .tn:hover circle{stroke:#fff;stroke-width:2}
.tn text{fill:var(--muted);font:10px ui-monospace,monospace} .tn:hover text{fill:var(--txt)}
.tn.cur circle{stroke:#fff;stroke-width:2.5} .tn.cur text{fill:#fff;font-weight:bold}
/* uniform-width rows (no horizontal scroll); the detail column truncates with an
   ellipsis -- click a step to read the full text in the bottom event bar */
.maprow{font-family:ui-monospace,monospace;font-size:11px;padding:2px 6px;border-radius:4px;cursor:pointer;display:flex;align-items:center;overflow:hidden;border-left:3px solid transparent}
#map{overflow-x:hidden}
/* the 5 big phases are the STRUCTURE -> bordered boxes; events sit indented under them */
.maprow.phase{color:var(--gold);font-weight:600;border:1px solid var(--line);background:var(--p2);margin:4px 0 1px;padding:3px 6px}
/* the 3 atoms of an elaboration wave, colour-banded so a wave reads as match -> fire -> wm-update:
   match=orange (detect) · fire/retract=purple (activate, ONE colour for both) · wm-update=green (WM changes) */
.maprow.st-match{border-left-color:#ff9d2e;color:#ff9d2e;background:rgba(255,157,46,.07)}
.maprow.st-fire{border-left-color:#b98aff;color:#b98aff;background:rgba(185,138,255,.07)}
.maprow.st-wm{border-left-color:var(--accent);color:var(--accent);background:rgba(95,217,127,.06)}
/* impasse / substate opened -> distinct red band so a subgoal being pushed stands out */
.maprow.st-impasse{border-left-color:var(--rmt);color:var(--rmt);background:rgba(255,138,138,.10);font-weight:600}
.maprow:hover{filter:brightness(1.25)}
.maprow.on{background:#2d4a86;color:#fff;border-color:#2d4a86}   /* current step wins over the phase box */
/* elaboration wave = SUB-cycle -> plain muted text, no box, NO per-wave indent
   (so a deep cascade of 10+ waves stays a flat, readable list under its phase box) */
/* fixed-width columns so stage name and detail line up across every row:
   [▶ mark][wave N][stage][detail…] */
.maprow .mmark{flex:0 0 1.2em;text-align:center}
.maprow .mwave{flex:0 0 4.4em;color:var(--muted);font-size:10px}
.maprow .mstage{flex:0 0 7em;font-weight:600}
.maprow .mdetail{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.maprow.on .mwave{color:#dfe6f5}
.wme{font-family:ui-monospace,monospace;font-size:12px;padding:1px 6px;border-radius:4px;display:block;margin:1px 0;white-space:nowrap}
.wme.hl{background:var(--add);color:var(--addt);font-weight:600}
/* #wm = panel 폭의 스크롤 컨테이너(overflow:auto from .panel>div). 콘텐츠(.tree)를
   width:max-content 로 넓혀 긴 id/값 줄이 넘치면 #wm 이 **가로 스크롤**을 낸다 (사용자 요청).
   (이전 #wm{min-width:max-content} 는 #wm 자체를 넓혀 panel overflow:hidden 이 잘라 스크롤 불가였음) */
#wm{min-width:0}
/* ARCKG tree (toggle) -- mirrors ARC-solver dashboard */
.tree{font-family:ui-monospace,monospace;font-size:11.5px;line-height:1.55;width:max-content;min-width:100%}
.tree details{margin:0} .tree summary{cursor:pointer;list-style:none;white-space:nowrap;color:#c2c8d4}
.tree summary::-webkit-details-marker{display:none}
.tree summary::before{content:"\25B8";color:var(--muted);display:inline-block;width:1.1em;text-align:center}
.tree details[open]>summary::before{content:"\25BE"}
.tree details>:not(summary){margin-left:9px;border-left:1px solid var(--line);padding-left:6px}
.tree .leaf{padding-left:1.1em;white-space:nowrap;color:#c2c8d4}
/* fixed-width +/-/~ change marker so lines never shift between steps */
.tree .wpre{display:inline-block;width:1em;text-align:center;font-weight:700}
/* ARCKG NODE rows tinted by hierarchy level (node = property/relation 아닌 노드 줄; TASK 제외):
   PAIR=파스텔 오렌지 · GRID=파스텔 노랑 · OBJECT=파스텔 녹색 · PIXEL=파스텔 파랑.
   add/rem(초록/빨강 배경) 규칙을 아래에 둬서 그게 이 색칠을 덮는다(우선순위 낮음).
   modify(글자색 add-t/rem-t/mix-t)와는 배경 vs 글자라 공존. */
.tree summary.lvl-pair,.tree .leaf.lvl-pair{background:rgba(255,164,82,.20);border-radius:3px}
.tree summary.lvl-grid,.tree .leaf.lvl-grid{background:rgba(238,214,92,.17);border-radius:3px}
.tree summary.lvl-object,.tree .leaf.lvl-object{background:rgba(120,214,140,.16);border-radius:3px}
.tree summary.lvl-pixel,.tree .leaf.lvl-pixel{background:rgba(122,176,236,.18);border-radius:3px}
/* relation(비교 edge) 노드 = 파스텔 라벤더 — LCA 노드 아래 cascade (ARC-solver E_*-*.json 미러) */
.tree summary.lvl-rel,.tree .leaf.lvl-rel{background:rgba(190,150,255,.16);border-radius:3px}
/* the line itself changed -> full (text + background) */
.tree .leaf.add,.tree summary.add{background:var(--add);color:var(--addt);border-radius:3px}
.tree .leaf.rem,.tree summary.rem{background:var(--rm);color:var(--rmt);border-radius:3px}
/* only a descendant changed (~) -> text colour only (no background) */
.tree summary.add-t{color:var(--addt)} .tree summary.rem-t{color:var(--rmt)} .tree summary.mix-t{color:#ffb454}
.tree .ntag{color:var(--gold)}
.evbig{font-size:15px;font-family:ui-monospace,monospace;margin-bottom:3px}
.kind-rule-fire{color:var(--addt)} .kind-rule-retract{color:var(--rmt)} .kind-wme-add{color:var(--addt)}
.kind-wme-remove{color:var(--rmt)} .kind-op-select,.kind-op-propose{color:var(--gold)} .kind-decide{color:var(--blue)}
.kind-output{color:var(--accent)} .kind-input-noop{color:var(--muted)}
.kind-match{color:#ff9d2e} .kind-wm-update{color:var(--addt)} .kind-substate{color:var(--rmt)}
/* goal-stack roots in the WM panel: each substate slightly indented with a header */
.gstate{margin-top:5px} .gstate+.gstate{border-top:1px dashed var(--line);padding-top:4px}
.ghdr{color:var(--rmt);font-weight:600;font-size:11px;margin:1px 0 2px}
.rule{border:1px solid var(--line);border-radius:7px;margin:4px 0;background:var(--p2);font-family:ui-monospace,monospace;font-size:11.5px;overflow:hidden}
.rule.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.rule.off{border-color:var(--rmt);box-shadow:0 0 0 1px var(--rmt)}   /* retracted this step */
.rule.pend{border-color:#ff9d2e;border-style:dashed}       /* matched this step, pending fire (orange) */
.rule.pendoff{border-color:#d97676;border-style:dashed}    /* unmatched this step, pending retract (dim red) */
.rule>summary{color:var(--gold);font-weight:600;padding:5px 8px;cursor:pointer;list-style:none;white-space:nowrap}
.rule>summary::-webkit-details-marker{display:none}
.rule>summary::before{content:"\25B8";color:var(--muted);display:inline-block;width:1.1em;text-align:center}
.rule[open]>summary::before{content:"\25BE"}
.rule>summary .firetag{color:var(--accent);font-weight:600;margin-left:6px}
.rule>summary .retracttag{color:var(--rmt);font-weight:600;margin-left:6px}
.rule>summary .pendtag{color:#ff9d2e;font-weight:600;margin-left:6px}
.rule>summary .pendofftag{color:#d97676;font-weight:600;margin-left:6px}
.rule .body{padding:0 8px 6px}
/* IF / THEN each on their own line; every condition starts its own line */
.rule .condline{padding-left:14px;margin:1px 0;white-space:nowrap}
/* expand-all / collapse-all button in a panel header */
.allbtn{float:right;margin-left:6px;background:var(--p2);border:1px solid var(--line);color:var(--muted);
 border-radius:4px;font-size:9px;line-height:1.4;padding:1px 5px;cursor:pointer;text-transform:none;letter-spacing:0}
.allbtn:hover{color:var(--txt);border-color:var(--accent)}
/* condition KIND = faint background tint (positive=blue, negated=amber);
   default text grey; ACTIVATED (satisfied) = saturated kind-colour text (not green) */
.cond{padding:0 3px;border-radius:3px;color:var(--muted)}
.cond.pos{background:rgba(138,180,248,.11)}
.cond.neg{background:rgba(255,138,138,.12)}
.cond.pos.sat{color:var(--blue);font-weight:600}
.cond.neg.sat{color:var(--rmt);font-weight:600}
.cond .nmark{font-weight:700;margin-right:1px}   /* negation marker: inherits cond colour */
.lbl{color:var(--muted);font-weight:600;margin-right:3px} .key{color:var(--gold);font-weight:600}
.rule .txt{color:#c2c8d4} .arrow{color:var(--muted)}
.opcard{border:1px solid var(--accent);border-radius:7px;padding:7px 9px;margin:4px 0;background:var(--p2)}
table.g{border-collapse:collapse;table-layout:fixed;flex:none} table.g td{width:10px;height:10px;min-width:10px;border:1px solid #222}
.pair{display:flex;align-items:center;gap:5px;margin:3px 0;width:max-content} .pair .cap{font-size:10px;color:var(--muted);width:38px;flex:none}
.cand{display:inline-block;text-align:center;margin:0 8px 8px 0;vertical-align:top}
.cand .cap{font-size:11px;color:var(--muted);display:block;margin-bottom:2px}
.exprrow{font-family:ui-monospace,monospace;font-size:12px;margin:2px 0} .exprrow .a{color:var(--blue);min-width:64px;display:inline-block}
/* 조립 패널: 라벨 고정폭 + 값 열 (긴 값은 값 열 안에서만 줄바꿈=hanging indent) */
.srow{display:flex;gap:8px;font-family:ui-monospace,monospace;font-size:12px;margin:2px 0;text-align:left}
.srow .slbl{flex:0 0 72px;color:var(--blue)} .srow .sval{flex:1 1 auto;min-width:0;word-break:break-word}
kbd{background:var(--p2);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:11px}
</style></head><body>
<div id="browser"></div>
<div id="stepper">
 <div id="sbar"></div>
 <div id="phases"></div>
 <div class="panel" id="ptree"><h3>process tree<span class="info">i<div class="tip"><b>결정 사이클을 git 커밋 그래프처럼</b> 세로로. <b>한 점 = 한 cycle</b>. <b>가로 위치(lane) = substate 깊이</b>(왼쪽 S1, 오른쪽으로 갈수록 깊은 substate). <b>오른쪽으로 가지 치는 것 = substate 생성</b>(무언가 안 돼서 impasse → 한 계층 더 들어감), 왼쪽으로 합쳐지는 것 = substate 해소·복귀.<br>점 색: <span style="color:#FF851B">주황=substate 생성(가지)</span> · <span style="color:#2ECC40">초록=operator 적용</span> · <span style="color:#0074D9">파랑=선택</span> · <span style="color:#FFDC00">노랑=출력</span>. <b>점에 호버</b>하면 그 cycle 한 줄 요약(무엇이 선택·적용됐나 / 뭐가 안돼 substate 가 났나). <b>클릭</b>하면 그 cycle 로 이동. ▶=현재.</div></span></h3><div id="tree"></div></div>
 <div class="panel" id="pmap"><h3>cycle map<span class="info">i<div class="tip">시스템의 <b>모든 원자적 변화 1개 = 1스텝</b>. ▶ = 현재 스텝. 클릭하거나 <b>↑↓</b>(한 스텝씩)·<b>←→</b>(다음/이전 wm-update로 점프)로 이동.<br><b>박스 친 줄 = 큰 단계</b>(input → propose → decide → apply → output)가 풀이의 구조. 그 아래 줄들이 그 단계 안에서 일어난 변화.<br><b>wave N</b>(평문) = 그 단계 안의 <b>elaboration sub-cycle</b>. <b>wave 1</b> = 정식 결정에 의한 1차 발화(propose의 operator 제안 / apply의 apply 규칙·body), <b>wave 2·3…</b> = 그 결과로 연쇄된 2차 wave. 같은 wave 번호 = 한 settle 라운드.<br>각 wave는 <b>match → fire → wm-update</b> 3원자단계로, cycle map에서 <b>왼쪽 색 띠</b>로 구분: <b style="color:#ff9d2e">match=주황</b>(LHS 충족/깨짐 검출), <b style="color:#b98aff">fire/retract=보라</b>(발화·철회를 한 색으로; rules 패널에선 초록/빨강 구분), <b class=g>wm-update=녹색</b>(preference가 WME로 들어가 WM 변화). operator <b>body</b>(직접 적용)는 wave가 아니라 APPLY phase의 효과라 색 띠·wave 번호가 없다. <b>WM은 wm-update에서만 바뀐다</b>(match·fire 땐 불변). 발화했는데 뒤에 wm-update가 없으면 = 그 결과가 o-support라 제거할 게 없는 무해한 철회.<br>각 줄은 <b>[wave][stage][detail]</b> 고정폭 컬럼으로 정렬되고, detail이 길면 <b>…</b>로 잘린다 — 줄을 클릭하면 <b>하단 바</b>에서 전체 텍스트를 본다.</div></span></h3><div id="map"></div></div>
 <div class="panel" id="pwm"><h3>working memory<span class="info">i<div class="tip"><b>S1을 루트로 한 단일 WM 트리.</b> 모든 줄 = <b>(id ^attr value)</b> WME 삼중쌍. ▸ 토글로 lazy 하위(pair·grid·object) 펼침. 우측 <b>⇕ all</b> = 전부 열기(일부라도 닫혀 있으면)/전부 닫기. 한 토글의 열림 상태는 다음 step으로 유지되고, 다음 step에서 새로 생긴 토글은 닫힌 채로 시작.<br>색: <span class=g>녹색 바탕</span>=그 줄 추가, <span class=r>빨강 바탕</span>=그 줄 삭제. 하위에서만 바뀐 상위 토글은 <b>글자색만</b> — <span class=g>녹=추가</span>/<span class=r>적=삭제</span>/<span class=o>주황=혼합</span>.<br>한 객체가 두 엣지로 가리켜질 때(예: 선택된 <b>(S1 ^operator O1)</b>와 그 acceptable preference <b>(S1 ^operator O1 +)</b>가 둘 다 O1을 가리킴) 하위는 <b>먼저 나온 엣지 아래에 한 번</b>만 펼치고, 나머지 엣지는 <b>평범한 leaf</b>로 둔다(중복 방지).</div></span><button class=allbtn onclick="toggleAll('wm')" title="전부 열기 / 전부 닫기">⇕ all</button></h3><div id="wm"></div></div>
 <div class="panel" id="prules"><h3>rules<span class="info">i<div class="tip">에이전트의 <b>기본 production 규칙</b> (절차적 지식). 이 step에 <b>발화한 규칙</b> = <span class=g>초록 테두리 ● fired</span>, <b>철회된 규칙</b> = <span class=r>빨강 테두리 ● retracted</span>. <b>match step</b>에선 발화/철회 직전 상태로 <span class=o>◌ matched(주황 점선=LHS 충족, 발화 대기)</span>·<span class=r>◌ unmatched(붉은 점선=LHS 깨짐, 철회 대기)</span> 표시. 철회는 LHS가 더는 만족되지 않아 instantiation이 사라진 것이라, 그 규칙의 조건이 <b>회색(미충족)</b>으로 보이는 게 정상이다. 조건은 <b>종류별 배경색</b>: <span class=bl>긍정(파랑 기)</span> = WM에 있어야 함, <span class=r>부정(빨강 기, 앞에 −)</span> = WM에 없어야 함. 글자색: <b>회색=미충족</b>, 충족되면 <span class=bl>긍정 파랑</span>/<span class=r>부정 빨강</span> 진한색. THEN의 operator = 금색. 한 규칙은 <b>모든 조건이 충족(=진한색)</b>일 때만 발화. 카드는 기본 <b>접힘</b>(WM과 동일) — 클릭해 펼치면 다음 step으로 유지. 우측 <b>⇕ all</b>로 전부 열기/닫기.</div></span><button class=allbtn onclick="toggleAll('rules')" title="전부 열기 / 전부 닫기">⇕ all</button></h3><div id="rules"></div></div>
 <div id="pright">
  <div class="panel" id="pprob"><h3>problem<span class="info">i<div class="tip"><b>train 예제쌍</b>(input → output)과 <b>test 입력</b>. 풀이의 입력 데이터(ARC task).</div></span></h3><div id="prob"></div></div>
  <div class="panel" id="pcand"><h3>answer candidates<span class="info">i<div class="tip"><b>compose/output 단계에서 생성</b>되는 답 후보들. 랭킹 <b>제출 순서대로</b> 내고, 틀리면 다음 후보(최대 3회). <span class=g>✓</span> = 정답.</div></span></h3><div id="cand"></div></div>
 </div>
 <div id="pevent"></div>
</div>
<script>
const D=__DATA__;
const PAL=['#000','#0074D9','#FF4136','#2ECC40','#FFDC00','#AAA','#F012BE','#FF851B','#7FDBFF','#870C25'];
const PHASES=['input','propose','decide','apply','output'];
let view='browser',ti=0,step=0;
// WM tree toggle state, keyed by node id, PERSISTED across steps: open a node
// and step forward -> it stays open (node ids are stable across the trace).
let wmOpen=new Set();
// rule cards default CLOSED (like WM); we remember which the user OPENED, persisted
// across steps (keyed by rule name). New rules next step start closed.
let ruleOpen=new Set();
// expand-all / collapse-all for a panel: any toggle closed -> open all (only the
// CURRENTLY-present toggles, so next step's new toggles stay closed); else close all.
function toggleAll(which){
 const set=which=='wm'?wmOpen:ruleOpen;
 const sel=which=='wm'?'details[data-nid]':'details.rule[data-rule]';
 const ds=[...$(which).querySelectorAll(sel)];
 const open=ds.some(d=>!d.open);
 ds.forEach(d=>{ const k=d.dataset.nid||d.dataset.rule; d.open=open; open?set.add(k):set.delete(k); });
}
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const trunc=(s,n)=>{s=String(s);return s.length>n?s.slice(0,n)+'…':s;};
const isVar=s=>typeof s==='string'&&s[0]==='<'&&s.slice(-1)==='>';
function grid(raw){ if(!raw) return '<span class=hint>·</span>';
 return '<table class=g>'+raw.map(r=>'<tr>'+r.map(v=>'<td style="background:'+(PAL[v]||'#fff')+'"></td>').join('')+'</tr>').join('')+'</table>'; }

function renderBrowser(){
 view='browser'; $('browser').style.display='block'; $('stepper').style.display='none';
 let h=`<h1>PySOAR dashboard — <b>${esc(D.dataset)}</b></h1>
  <div class=sub>← → ↑ ↓ 문제 선택 · <kbd>Enter</kbd> 풀이 (${D.tasks.length} tasks)</div><div class=cards>`;
 D.tasks.forEach((t,i)=>{const a=t.correct_attempt;
   const res=a===null?'<span class=bad>unsolved</span>':`<span class=ok>solved (try ${a+1})</span>`;
   h+=`<div class="card${i==ti?' sel':''}" onclick="ti=${i};openTask()"><div class=tid>${esc(t.id)}</div><div class=meta>${t.n_steps} steps · ${res}</div></div>`;});
 $('browser').innerHTML=h+'</div>';
 const s=document.querySelector('.card.sel'); if(s) s.scrollIntoView({block:'nearest'});
}
function openTask(){view='stepper';step=0;$('browser').style.display='none';$('stepper').style.display='grid';renderStep();}

function condMatched(c,wm){
 // a variable ID or VALUE is a WILDCARD; attr is always literal. Satisfied iff some
 // WME matches the pattern. (Matches against raw triples, so a variable id like <o>
 // is handled -- the old string-compare only handled a variable value and wrongly
 // left variable-id conditions grey.)
 const idVar=isVar(c.id), valVar=isVar(c.val);
 const pres=wm.some(t=>(idVar||String(t[0])===String(c.id))
   && String(t[1])===String(c.attr) && (valVar||String(t[2])===String(c.val)));
 return c.neg?!pres:pres;
}
function condHTML(c,wm,forceSat){
 // background tint = condition KIND (pos/neg), ALWAYS (satisfaction-independent).
 // saturated text colour = SATISFIED only. forceSat: a fired/matched rule has its
 // WHOLE LHS satisfied, so every condition is coloured (positive blue / negative red).
 const sat=forceSat||condMatched(c,wm); const cls=(c.neg?'neg':'pos')+(sat?' sat':'');
 const v=isVar(c.val)?'<i>'+esc(c.val)+'</i>':esc(c.val);
 // SOAR-standard negation: a '-' PREFIX on the pattern (inherits the cond colour)
 const nm=c.neg?'<span class=nmark>-</span>':'';
 return `<span class="cond ${cls}">${nm}(${esc(c.id)} ^${esc(c.attr)} ${v})</span>`;
}
// status: '' (idle) | 'fire' (this step fired it) | 'retract' (this step retracted it).
// FIRE and RETRACT are distinct -- on a retract step the rule's LHS no longer holds
// (that is WHY it retracted), so its conditions read grey/unsatisfied; pairing that
// with a red "● retracted" (not a green "● fired") is what makes the panel honest.
function ruleCard(r,wm,status){
 // FIRED or MATCHED(pending fire) => the entire LHS holds => colour EVERY condition
 // (a fired rule cannot have an unsatisfied condition). retracted/idle => per-condition
 // matching (on a retract the LHS is broken, so grey conditions are correct).
 const lhsHolds=(status==='fire'||status==='pend-fire');
 const ifs=r.if.map(c=>`<div class=condline>${condHTML(c,wm,lhsHolds)}</div>`).join('');
 // THEN: keywords grey, the proposed operator (the key WME value) coloured.
 // The preference symbol is shown ONLY for the operator (context) slot or for a
 // non-default preference -- a plain make like (<o> ^name observe) carries NO '+'
 // in Soar (the '+' is the operator acceptable preference, not an operator augment).
 const th=r.then.map(a=>{
   const pf=(a.attr==='operator'||(a.pref&&a.pref!=='+'))?(' '+esc(a.pref)):'';
   return `<div class=condline><span class=txt>(${esc(a.id)} ^${esc(a.attr)}</span> <span class=key>${esc(a.val)}</span><span class=txt>${pf})</span></div>`;
 }).join('');
 const fired=status==='fire', retr=status==='retract';
 // match-step pre-states: matched (LHS satisfied, pending fire) / unmatched (LHS broke, pending retract)
 const pendF=status==='pend-fire', pendR=status==='pend-retract';
 const cls=fired?' on':(retr?' off':(pendF?' pend':(pendR?' pendoff':'')));
 const tag=fired?'<span class=firetag>● fired</span>'
  :(retr?'<span class=retracttag>● retracted</span>'
  :(pendF?'<span class=pendtag>◌ matched (발화 대기)</span>'
  :(pendR?'<span class=pendofftag>◌ unmatched (철회 대기)</span>':'')));
 const open=ruleOpen.has(r.name);   // default closed; remember opens
 return `<details class="rule${cls}" data-rule="${esc(r.name)}"${open?' open':''}>
   <summary>${esc(r.name)}${tag}</summary>
   <div class=body>
     <div class=lbl>IF</div>${ifs}
     <div class=lbl>THEN</div>${th}
   </div></details>`;
}
function renderRules(e,wm){
 const cur=e.rule;   // pass RAW wm triples to ruleCard/condMatched (wildcard-aware)
 // the responsible rule was FIRED or RETRACTED this step -- one or the other
 const status=e.kind==='rule-retract'?'retract':(e.kind==='rule-fire'?'fire':'');
 // MATCH step: rules ENTERING (pending fire) / LEAVING (pending retract) the match set
 const md=(e.kind==='match'&&e.detail)?e.detail:null;
 const statusOf=name=>{
   if(md){ if((md.matched||[]).includes(name)) return 'pend-fire';
           if((md.unmatched||[]).includes(name)) return 'pend-retract'; return ''; }
   return name===cur?status:'';
 };
 let h='';
 // operator-apply steps are caused by an operator body, not a production rule
 if(cur && !D.rules.find(x=>x.name===cur))
   h+=`<div class=opcard><b>operator ${esc(cur)}</b> apply<div class=hint>${esc(D.op_docs[cur]||'WM을 직접 변경')}</div></div>`;
 D.rules.forEach(r=> h+=ruleCard(r,wm, statusOf(r.name)));
 return h;
}
const STRUCT=new Set(['arckg','example','test','input','output','object']);
function fmtTriple(t){return '('+t[0]+' ^'+t[1]+' '+t[2]+')';}
function ancestors(id){ // Tx.P0.G0.O0 -> [Tx.P0.G0, Tx.P0, Tx]
 const parts=String(id).split('.'); const out=[];
 for(let k=parts.length-1;k>0;k--) out.push(parts.slice(0,k).join('.'));
 return out;
}
// ARCKG 노드 id -> 레벨 클래스 (파스텔 배경용). TASK(T…, 1세그먼트)와 비-ARCKG(S1/O1/percept)
// 는 ''. 마지막 세그먼트 첫 글자로 판별: P=pair,G=grid,O=object,X=pixel.
function arckgLevel(id){
 // NODE 레벨 파스텔만 담당. relation 은 여기서 칠하지 않는다 (body 에서 ^relation edge 인
 // 최상위 노드에만 lvl-rel; 그 하위 receipt(category/속성)는 칠하지 않음 — 사용자 요청).
 const p=String(id).split('.');
 if(p[0][0]!=='T'||p.length<2) return '';
 const last=p[p.length-1];
 return ({P:'lvl-pair',G:'lvl-grid',O:'lvl-object',X:'lvl-pixel'})[last[0]]||'';
}
function renderWM(wm,added,removed,removedTriples){
 // ONE working memory rooted at S1. Every line is a full WME triplet. Toggles
 // are CLOSED by default. A line whose own WME changed -> full (text+bg). A
 // toggle whose only a DESCENDANT changed -> text colour only (add=green,
 // remove=red, mixed=orange).
 // GHOST rows: removedTriples were in WM last step, gone now. They are NOT in the
 // current tree, so we build the tree from (current ∪ removed) -- the removed lines
 // then render in red with a − prefix (via lineMark/`removed`), exactly like adds.
 const ghosts=removedTriples||[];
 const all=ghosts.length?wm.concat(ghosts):wm;
 const nodeIds=new Set(all.map(t=>String(t[0])));
 const nodes={}, parentOf={};
 const ensure=id=>{ if(!nodes[id]) nodes[id]={props:[],kids:[]}; return nodes[id]; };
 // pointer attributes (attention cursor) mark a node but do NOT own it -> render as a
 // leaf marker; the node itself expands under its structural edge (input-link / ARCKG).
 const POINTER=new Set(['focus','level','cursor','cmp-active']);   // 계층명·노드그룹·관측커서·비교커서 = leaf 마커
 all.forEach(t=>{
   const [id,attr,val]=t;
   if(Array.isArray(val)){ ensure(id).props.push([attr,val]); return; }
   if(POINTER.has(attr)){ ensure(id).props.push([attr,val]); return; }   // pointer = leaf marker
   // an operator ACCEPTABLE preference is stored as value "<opid> +"; link it to
   // the operator OBJECT <opid> so its augmentations (e.g. ^name observe) show in
   // the tree during PROPOSE too -- the proposed operator is part of WM, not a leaf.
   const m=String(val).match(/^(\S+) \+$/);
   const bare=(attr==='operator'&&m)?m[1]:String(val);
   if(nodeIds.has(bare)&&bare!==String(id)){
     ensure(id).kids.push([attr,bare,String(val)]); ensure(bare);
     if(!(bare in parentOf)) parentOf[bare]=id;
   } else ensure(id).props.push([attr,val]);
 });
 // propagate change status up the tree (id and all ancestors)
 const sub={};
 const mark=(s,k)=>{ const m=s.match(/^\(([^ ]+) /); if(!m) return; let x=m[1],g=0;
   while(x&&g++<24){ (sub[x]=sub[x]||{})[k]=true; x=parentOf[x]; } };
 added.forEach(s=>mark(s,'a')); removed.forEach(s=>mark(s,'r'));
 const subCls=cid=>{ const s=sub[cid]; if(!s) return ''; return s.a&&s.r?' mix-t':(s.a?' add-t':' rem-t'); };
 // marker for a line: + added, − removed, ~ only-descendant-changed, blank none
 const lineMark=(full,cid)=>{
   if(added.has(full)) return {pre:'+', cls:' add'};
   if(removed.has(full)) return {pre:'−', cls:' rem'};
   const sc=cid?subCls(cid):''; if(sc) return {pre:'~', cls:sc};
   return {pre:' ', cls:''};
 };
 const shown=new Set();   // a node renders its subtree once; further edges = reference
 function body(id){
   const n=nodes[id]; if(!n) return '';
   let h='';
   n.props.forEach(([a,v])=>{ const disp=Array.isArray(v)?trunc(JSON.stringify(v),44):trunc(v,40);
     const mk=lineMark(fmtTriple([id,a,v]),null);
     h+=`<div class="leaf${mk.cls}"><span class=wpre>${mk.pre}</span>${esc('('+id+' ^'+a+' '+disp+')')}</div>`; });
   // 한 노드 아래 자식 순서: property(1토글) → 자식 node 토글들 → 개별 relation 토글들 (사용자 요청)
   const KORD={property:0,example:1,test:1,input:1,output:1,object:1,relation:3};
   n.kids.slice().sort((x,y)=>((KORD[x[0]]??2)-(KORD[y[0]]??2))).forEach(([edge,cid,disp])=>{ const ew=fmtTriple([id,edge,disp||cid]); const mk=lineMark(ew,cid);
     const loaded=nodes[cid]&&(nodes[cid].props.length||nodes[cid].kids.length);
     // 최상위 relation edge 만 라벤더. 그 하위(receipt: category/속성)는 칠하지 않는다 (사용자 요청)
     const lvl=(edge==='relation')?'lvl-rel':arckgLevel(cid);
     if(loaded&&!shown.has(cid)){ shown.add(cid);
       h+=`<details data-nid="${esc(cid)}"${wmOpen.has(String(cid))?' open':''}><summary class="${(lvl+mk.cls).trim()}"><span class=wpre>${mk.pre}</span>${esc(ew)}</summary>${body(cid)}</details>`;
     } else if(loaded){ h+=`<div class="leaf ${lvl}${mk.cls}"><span class=wpre>${mk.pre}</span>${esc(ew)}</div>`;   // dup edge to an already-expanded object -> plain leaf (no marker)
     } else h+=`<div class="leaf ${lvl}${mk.cls}"><span class=wpre>${mk.pre}</span>${esc(ew)} <span class=hint>(lazy)</span></div>`;
   });
   return h;
 }
 // GOAL STACK: render each state (S1, S2, ...) as a root so substates opened by an
 // impasse are visible. Single state -> just S1 (unchanged). Substates show their own
 // ^superstate/^impasse/^focus + derived comm/diff; shared nodes stay leaves.
 const states=[...new Set(wm.filter(t=>t[1]==='type'&&String(t[2])==='state').map(t=>String(t[0])))]
   .sort((a,b)=>(parseInt(String(a).slice(1))||0)-(parseInt(String(b).slice(1))||0));
 if(states.length<=1) return `<div class="tree">${body('S1')}</div>`;
 return states.map((s,i)=>`<div class="tree gstate">${i>0?`<div class=ghdr>↳ ${esc(s)} <span class=hint>substate (impasse)</span></div>`:''}${body(s)}</div>`).join('');
}
// short stage name per event kind -> the aligned "stage" column in the cycle map
const STAGE={match:'match','rule-fire':'fire','rule-retract':'retract','wm-update':'wm-update',
 'wme-add':'add',decide:'decide','op-select':'select','op-apply':'apply',quiescence:'quiescence',
 output:'output','input-noop':'input',substate:'substate'};
// wm_states 는 base+delta({a,r})로 저장됨(용량 축소). 순차 적용해 각 state 의 full WM 을
// 복원하고 task 별로 캐시한다 (표시 정보는 full 저장과 100% 동일).
const _WMC={};
function wmStates(ti){
 if(ti in _WMC) return _WMC[ti];
 const raw=D.tasks[ti].wm_states, out=[];
 for(let i=0;i<raw.length;i++){
   const d=raw[i]||{a:[],r:[]};
   if(i===0){ out.push((d.a||[]).slice()); continue; }
   const rem=new Set((d.r||[]).map(t=>JSON.stringify(t)));
   out.push(out[i-1].filter(t=>!rem.has(JSON.stringify(t))).concat(d.a||[]));
 }
 _WMC[ti]=out; return out;
}
let _treeTi=-1;
function renderTree(){                              // git dev-tree: cycle 노드 + substate 가지
 const ct=D.tasks[ti].cycle_tree||[];
 if(!ct.length){$('tree').innerHTML='<div style="padding:16px;color:var(--muted);font-size:11px">no cycles</div>';return;}
 if(_treeTi!==ti){                                  // 태스크 바뀌면 SVG 새로
  _treeTi=ti;
  const laneW=15,rowH=19,mx=13,my=9; let maxd=0; ct.forEach(n=>{if(n.depth>maxd)maxd=n.depth;});
  const laneX=L=>mx+L*laneW, rowY=i=>my+i*rowH+rowH/2;
  const tx=laneX(maxd)+12, W=tx+185, H=my*2+ct.length*rowH;
  const COL={branch:'#FF851B',apply:'#2ECC40',select:'#0074D9',output:'#FFDC00',phase:'#6b7280'};
  const laneCol=L=>['#5b6472','#FF851B','#2ECC40','#1f8fff','#F012BE','#e3b341','#7FDBFF'][L%7]; // lane0=메인(회색)
  let s='';
  for(let i=1;i<ct.length;i++){                     // ── 가지 그리기: 부모 스택 vs 현재 스택 비교
    const a=ct[i-1].stack||[],b=ct[i].stack||[],y0=rowY(i-1),y1=rowY(i),ym=(y0+y1)/2,cm=Math.min(a.length,b.length);
    for(let L=0;L<cm;L++) if(a[L]===b[L])           // 지속 레인(같은 상태 유지) = 세로선. lane0(S1)=메인 세로선
      s+=`<line x1="${laneX(L)}" y1="${y0}" x2="${laneX(L)}" y2="${y1}" stroke="${laneCol(L)}" stroke-width="1.7"/>`;
    if(b.length>a.length) for(let L=a.length;L<b.length;L++)   // push = substate 생성 → 부모에서 오른쪽으로 갈라짐
      s+=`<path d="M${laneX(L-1)} ${y0}C${laneX(L-1)} ${ym} ${laneX(L)} ${ym} ${laneX(L)} ${y1}" stroke="${laneCol(L)}" stroke-width="1.7" fill="none"/>`;
    if(b.length<a.length) for(let L=b.length;L<a.length;L++)   // pop = substate 해소 → 부모 가지로 합쳐짐
      s+=`<path d="M${laneX(L)} ${y0}C${laneX(L)} ${ym} ${laneX(b.length-1)} ${ym} ${laneX(b.length-1)} ${y1}" stroke="${laneCol(L)}" stroke-width="1.7" fill="none"/>`;
  }
  ct.forEach((n,i)=>{ const x=laneX(n.depth),y=rowY(i);   // ── 노드(점) = 현재 활성 상태의 레인에
    s+=`<g class=tn data-cycle="${n.cycle}" onclick="step=${n.step};renderStep()">`
      +`<circle cx="${x}" cy="${y}" r="3.6" fill="${COL[n.kind]||COL.phase}"/>`
      +`<text x="${tx}" y="${y+3.3}">c${n.cycle} ${esc(trunc(n.summary,24))}</text>`
      +`<title>cycle ${n.cycle} · ${esc(n.goal)} · depth ${n.depth}\n${esc(n.summary)}</title></g>`; });
  $('tree').innerHTML=`<svg width="${W}" height="${H}">${s}</svg>`;
 }
 const cyc=D.tasks[ti].events[step].cycle; let curEl=null;   // 현재 cycle 하이라이트
 $('tree').querySelectorAll('.tn').forEach(g=>{const on=+g.dataset.cycle===cyc;g.classList.toggle('cur',on);if(on)curEl=g;});
 if(curEl)curEl.scrollIntoView({block:'nearest'});
}
function renderStep(){
 const t=D.tasks[ti],ev=t.events,e=ev[step];
 if(!ev.length){$('sbar').innerHTML=`<b>${esc(t.id)}</b> <span class=bad>${esc(t.error||'no steps')}</span> <span class=hint><kbd>Esc</kbd> 목록</span>`;$('phases').innerHTML='';$('map').innerHTML=`<div style="padding:24px;color:var(--muted)">진행 스텝 없음 — ${esc(t.error||'unknown')}</div>`;$('wm').innerHTML='';$('cand').innerHTML='';$('pevent').innerHTML='';return;}
 $('sbar').innerHTML=`<b>${esc(t.id)}</b> <span class=hint>step ${step+1}/${ev.length} · cycle ${e.cycle}</span>
  <span class=hint>↑↓ 스텝 · ←→ wm-update · <kbd>Esc</kbd> 목록 · <kbd>Home/End</kbd></span>
  <span style="margin-left:auto">${t.correct_attempt===null?'<span class=bad>unsolved</span>':'<span class=ok>solved (try '+(t.correct_attempt+1)+')</span>'}</span>`;
 $('phases').innerHTML=PHASES.map(p=>`<div class="ph${p==e.phase?' on':''}">${p}</div>`).join('<span class=hint>→</span>');
 renderTree();                                    // 좌측 git dev-tree (현재 cycle 하이라이트)
 // colour-band the 3 wave atoms: match / fire+retract (one colour) / wm-update
 const stageCls=k=>k=='match'?' st-match':((k=='rule-fire'||k=='rule-retract')?' st-fire':(k=='wm-update'?' st-wm':(k=='substate'?' st-impasse':'')));
 $('map').innerHTML=ev.map((x,i)=>{
   const cur=i==step;
   const mark=`<span class=mmark>${cur?'▶':''}</span>`;
   // phase = header row (mark + title, outdented). others = [mark][wave][stage][detail…]
   if(x.kind=='phase')
     return `<div class="maprow phase${cur?' on':''}" onclick="step=${i};renderStep()">${mark}<span class=mdetail>${esc(x.label)}</span></div>`;
   const wv=`<span class=mwave>${x.wave?'wave '+x.wave:''}</span>`;
   const st=`<span class=mstage>${esc(STAGE[x.kind]||'')}</span>`;
   return `<div class="maprow${cur?' on':''}${stageCls(x.kind)}" onclick="step=${i};renderStep()">${mark}${wv}${st}<span class=mdetail>${esc(x.label)}</span></div>`;
 }).join('');
 const onr=document.querySelector('.maprow.on'); if(onr) onr.scrollIntoView({block:'nearest'});
 const hl=new Set(e.highlight);
 const WMS=wmStates(ti);                 // delta 로 저장된 wm_states 를 full 로 복원(캐시)
 const wm=WMS[e.wm_state];
 // added/removed by diffing this step's WM vs the previous step's
 const prevWm=step>0?WMS[ev[step-1].wm_state]:[];
 const cur=new Set(wm.map(fmtTriple)), prev=new Set(prevWm.map(fmtTriple));
 const added=new Set([...cur].filter(x=>!prev.has(x)));
 const removed=new Set([...prev].filter(x=>!cur.has(x)));
 // removed triples (present LAST step, gone NOW) as GHOST rows -- they are not in the
 // current WM tree, so renderWM re-injects them (red, − prefix) so a removal is as
 // visible as an addition when stepping.
 const removedTriples=prevWm.filter(t=>!cur.has(fmtTriple(t)));
 $('wm').innerHTML=renderWM(wm,added,removed,removedTriples);
 // remember toggle state so it carries to the next step (track user open/close)
 $('wm').querySelectorAll('details[data-nid]').forEach(d=>d.addEventListener('toggle',
   ()=>{ d.open?wmOpen.add(d.dataset.nid):wmOpen.delete(d.dataset.nid); }));
 $('rules').innerHTML=renderRules(e,wm);
 // persist each rule's collapse state to the next step (default open; track collapses)
 $('rules').querySelectorAll('details.rule[data-rule]').forEach(d=>d.addEventListener('toggle',
   ()=>{ d.open?ruleOpen.add(d.dataset.rule):ruleOpen.delete(d.dataset.rule); }));
 $('prob').innerHTML=t.grids.train.map((p,i)=>`<div class=pair><span class=cap>train${i}</span>${grid(p.input)}<span class=arrow>→</span>${grid(p.output)}</div>`).join('')
  +t.grids.test.map((p,i)=>`<div class=pair><span class=cap>test${i}</span>${grid(p.input)}<span class=arrow>→ ?</span></div>`).join('');
 // answer-ready 는 expr 는 S1, focus 는 풀이 substate 에 쓴다 → 어느 state 든 있으면 렌더
 // 조립(target construction) 상태: 목표(무엇을 만드나) + GRID 3속성 관계가 채워지는 과정.
 // task 처음엔 목표 미정 → compare 후 'produce X' → hypothesize 후 size/color/contents 관계.
 const produce=wm.filter(x=>x[1]==='produce').map(x=>x[2]);
 const slot=k=>{const w=wm.find(x=>x[1]==='target-'+k);return w?w[2]:null;};
 const slots=['size','color','contents'].map(k=>[k,slot(k)]);
 const anySlot=slots.some(([_k,v])=>v!==null);
 // 라벨 고정폭 + 값 flex → 열이 가지런히 맞음(왼쪽 정렬; .cand 의 center 를 덮음)
 const row=(lbl,val)=>`<div class=srow><span class=slbl>${esc(lbl)}</span><span class=sval>${val}</span></div>`;
 let build='';
 if(produce.length||anySlot){
   build='<div class=cand style="text-align:left;border-color:var(--gold);display:block">'
    +'<span class=cap>목표 · 조립(construction)</span>'
    +row('목표', produce.length?'produce '+esc(produce.join(', ')):'<span class=hint>미정</span>');
   if(anySlot){ build+='<div class=hint>GRID 3속성 관계 (입력 seed → 관계 적용):</div>'
    +slots.map(([k,v])=>row(k, v?esc(v):'<span class=hint>·</span>')).join(''); }
   else build+='<div class=hint>아직 grid 속성 미분해 (관측/비교 진행 중)</div>';
   build+='</div>';
 }
 const ready=wm.some(x=>x[1]==='answer-ready');
 // 조립 구역은 목표가 생긴 뒤부터 보이고, 답(built/cand)은 answer-ready 후 추가.
 let tail='';
 if(ready){
   tail=detail(e)+t.candidates.map((c,i)=>`<div class=cand><span class=cap>cand${i+1} ${i===t.correct_attempt?'<span class=ok>✓</span>':''}</span>${c.answer.map(grid).join(' ')}<div class=hint>${esc(c.position)}<br>${esc(c.color)}</div></div>`).join('');
 }
 $('cand').innerHTML=(build+tail)||'<span class=hint>목표 미정 (task 관측 전)</span>';
 const chg = e.highlight.length ? (e.highlight.length>4
   ? e.highlight.slice(0,4).map(x=>esc(trunc(x,40))).join(', ')+` <span class=hint>(+${e.highlight.length-4} more)</span>`
   : e.highlight.map(x=>esc(trunc(x,40))).join(', ')) : '';
 // bottom bar shows the FULL detail (cycle map truncates with …); stage name prefixed
 const stg=STAGE[e.kind]||e.kind;
 $('pevent').innerHTML=`<div class="evbig kind-${e.kind}">${e.kind=='phase'?'':'<b>'+esc(stg)+'</b>&nbsp;&nbsp;'}${esc(e.label)}</div>
  <div class=hint>phase=<b>${e.phase}</b> · kind=${e.kind}${e.wave?' · wave='+e.wave:''}${e.rule?' · rule/op='+esc(e.rule):''}${chg?' · changed: '+chg:''}</div>`;
}
function detail(e){
 const d=e.detail; if(!d) return '';
 if(d.kind=='observe'){
   if(d.objects) return '<div class=hint>ARCKG objects:</div>'+d.objects.map(o=>`<div class=exprrow><span class=a>pair ${o.pair}</span> color=${o.color} cells=${esc(JSON.stringify(o.cells))}</div>`).join('')+'<hr style="border-color:var(--line)">';
   return '<div class=hint>observe</div><div class=exprrow>'+esc(d.note||'')+'</div><hr style="border-color:var(--line)">';
 }
 if(d.kind=='compare'){
   if(d.relations!==undefined){ // focus_solver: COMM/DIFF + 도출된 greater 관계
     let h='<div class=hint>property별 비교 → COMM/DIFF</div>';
     h+=`<div class=exprrow><span class=a>COMM</span> ${esc((d.comm||[]).join(', ')||'—')}</div>`;
     h+=`<div class=exprrow><span class=a>DIFF</span> ${esc((d.diff||[]).join(', ')||'—')}</div>`;
     if(d.relations.length){ h+='<div class=hint>refine → 도출된 관계 (greater):</div>';
       h+=d.relations.map(r=>`<div class=exprrow><span class=a>${esc(r.a)} ≻ ${esc(r.b)}</span> on ${esc(r.on)}</div>`).join(''); }
     else h+='<div class=hint>orderable DIFF 없음 → 관계 도출 없음</div>';
     return h+'<hr style="border-color:var(--line)">';
   }
   return '<div class=hint>per-pair in→out:</div>'+d.rows.map(r=>`<div class=exprrow><span class=a>pair ${r.pair}</span> ${esc(JSON.stringify(r.in_coord))} c${r.in_color} → ${esc(JSON.stringify(r.out_coord))} c${r.out_color}</div>`).join('')+'<hr style="border-color:var(--line)">';
 }
 if(d.kind=='aggregate'){ // focus_solver: greater 관계 → role(extremum) 집계
   let h='<div class=hint>aggregate → 도출된 역할 (extremum = 가장 큼/작음):</div>';
   if(!(d.roles||[]).length) h+='<div class=exprrow>—</div>';
   else h+=d.roles.map(r=>`<div class=exprrow><span class=a>${esc(r.node)}</span> ${r.role=='extremum+'?'▲':'▼'} ${esc(r.role)} <span style=opacity:.7>on ${esc(r.on)}</span></div>`).join('');
   return h+'<hr style="border-color:var(--line)">';
 }
 if(d.kind=='hypothesize'){ let h='<div class=hint>랭킹된 변환 가설(predefined DSL 조합):</div>';
   h+=(d.hyps||[]).length?d.hyps.map((n,i)=>`<div class=exprrow><span class=a>#${i}</span> ${esc(n)}</div>`).join(''):'<div class=exprrow>후보 없음 → 하강</div>';
   return h+'<hr style="border-color:var(--line)">'; }
 if(d.kind=='predict'){ const o=d.info||{}; return `<div class=hint>내부 시뮬레이션(train 적용):</div><div class=exprrow>후보 #${o.idx} <span class=a>${esc(o.hyp||'')}</span></div><hr style="border-color:var(--line)">`; }
 if(d.kind=='evaluate'){ return `<div class=hint>train 오라클 대조:</div><div class=exprrow>후보 #${d.idx} <span class=a>${esc(d.hyp||'')}</span> → ${d.ok?'✅ consistent':'❌ 불일치(다음 후보)'}</div><hr style="border-color:var(--line)">`; }
 if(d.kind=='verify'){ const o=d.info||{}; return `<div class=hint>최종 재확인:</div><div class=exprrow><span class=a>${esc(o.hyp||'')}</span> → ${o.ok?'✅ verified':'❌'}</div><hr style="border-color:var(--line)">`; }
 if(d.kind=='find'){ return `<div class=hint>role 로 대상 선택:</div><div class=exprrow>selected: <span class=a>${esc((d.selected||[]).join(', ')||'—')}</span></div><hr style="border-color:var(--line)">`; }
 if(d.kind=='generalize') return '<div class=hint>resolved expressions:</div>'+Object.entries(d.exprs).map(([k,v])=>`<div class=exprrow><span class=a>${esc(k)}</span>= ${esc(v)}</div>`).join('')+'<div class=hint>out=make_grid(size,fill)+coloring(pos,color)</div><hr style="border-color:var(--line)">';
 if(d.kind=='compose') return '<div class=hint>built:</div>'+(d.answer?grid(d.answer):'<div class=exprrow>declined</div>')+'<hr style="border-color:var(--line)">';
 return '';
}
document.addEventListener('keydown',ev=>{
 if(view=='browser'){
   const cols=Math.max(1,Math.floor((window.innerWidth-48)/162));
   if(ev.key=='ArrowRight')ti=Math.min(D.tasks.length-1,ti+1);
   else if(ev.key=='ArrowLeft')ti=Math.max(0,ti-1);
   else if(ev.key=='ArrowDown')ti=Math.min(D.tasks.length-1,ti+cols);
   else if(ev.key=='ArrowUp')ti=Math.max(0,ti-cols);
   else if(ev.key=='Enter'){openTask();return;} else return;
   ev.preventDefault();renderBrowser();
 } else {
   const evs=D.tasks[ti].events, n=evs.length;
   // ↑↓ = 한 스텝씩(원자단계) · ←→ = 다음/이전 wm-update(=실제 WM 변화)로 점프
   if(ev.key=='ArrowDown')step=Math.min(n-1,step+1);
   else if(ev.key=='ArrowUp')step=Math.max(0,step-1);
   else if(ev.key=='ArrowRight'){let j=step+1;while(j<n&&evs[j].kind!='wm-update')j++;step=j<n?j:n-1;}
   else if(ev.key=='ArrowLeft'){let j=step-1;while(j>=0&&evs[j].kind!='wm-update')j--;step=j>=0?j:0;}
   else if(ev.key=='Home')step=0; else if(ev.key=='End')step=n-1;
   else if(ev.key=='Escape'){renderBrowser();return;} else return;
   ev.preventDefault();renderStep();
 }
});
renderBrowser();
</script></body></html>"""


def main():
    from arc.dataset import list_tasks, load_task
    ds = sys.argv[1] if len(sys.argv) > 1 else "easy"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    tasks = [task_data(tid, load_task(p)) for tid, p in list_tasks(ds, limit)]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:   # HTML 템플릿 non-ASCII → Windows(cp949) 크래시 방지
        f.write(build(ds, tasks))
    solved = sum(1 for t in tasks if t["correct_attempt"] is not None)
    print(f"wrote {out}  ({len(tasks)} tasks, {solved} solved)")
    print(f"open it:  open {out}")


if __name__ == "__main__":
    main()
