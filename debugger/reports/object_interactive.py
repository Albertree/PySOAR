# -*- coding: utf-8 -*-
"""
object_interactive — 여러 문제의 4개 그리드에서 object 를 하나씩 클릭 선택하고,
선택이 바뀔 때마다 **1차·2차 비교가 실시간 갱신**되는 인터랙티브 HTML. 상단 드롭다운으로 문제 전환.

정확성: 모든 within-pair object 쌍의 1차 compare(flat verdict 맵)를 Python 에서 미리 계산해 embed.
JS 는 선택된 두 1차 맵을 조회 표시하고, **2차는 verdict 끼리 같음/다름**을 그 자리에서 계산.

    python3 -m legacy.compare_viz.object_interactive     # -> arc/object_interactive.html
"""
from __future__ import annotations

import json
import os

from debugger.reports.comparison_orders import _flat, _sv

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "object_interactive.html")
TASKS = ["08ed6ac7", "0ca9ddb6"]


def _objs(idx, grid_node):
    from arbor.solver import _obj_cc
    out = []
    for oid in idx["children"].get(grid_node.node_id, []):
        node = idx["nodes"][oid]
        cells, col = _obj_cc(node)
        out.append({"id": oid.split(".")[-1], "nid": oid, "color": col, "area": len(cells),
                    "cells": [[r, c] for (r, c) in cells], "json": node.to_json()})
    out.sort(key=lambda o: -o["area"])
    return out


def _flatmap(idx, a_nid, b_nid):
    from ARCKG.comparison import compare as kg
    r = kg(idx["nodes"][a_nid], idx["nodes"][b_nid])["result"]
    return {p: [t, _sv(a), _sv(b)] for p, (t, a, b) in _flat(r).items()}


def _task_data(tid, task):
    from arbor.solver import build_arckg, index_arckg
    root = build_arckg(tid, task)
    idx = index_arckg(root)
    p0, p1 = root.example_pairs[0], root.example_pairs[1]
    H, W = len(task["train"][0]["input"]), len(task["train"][0]["input"][0])
    G = {"P0G0": p0.input_grid, "P0G1": p0.output_grid, "P1G0": p1.input_grid, "P1G1": p1.output_grid}
    RAW = {"P0G0": task["train"][0]["input"], "P0G1": task["train"][0]["output"],
           "P1G0": task["train"][1]["input"], "P1G1": task["train"][1]["output"]}
    OBJS = {g: _objs(idx, node) for g, node in G.items()}
    FIRST = {"pair0": {}, "pair1": {}}
    for a in OBJS["P0G0"]:
        for b in OBJS["P0G1"]:
            FIRST["pair0"][f"{a['id']}|{b['id']}"] = _flatmap(idx, a["nid"], b["nid"])
    for a in OBJS["P1G0"]:
        for b in OBJS["P1G1"]:
            FIRST["pair1"][f"{a['id']}|{b['id']}"] = _flatmap(idx, a["nid"], b["nid"])
    objs_lite = {g: [{k: o[k] for k in ("id", "color", "area", "cells", "json")} for o in lst]
                 for g, lst in OBJS.items()}
    return {"H": H, "W": W, "raw": RAW, "objs": objs_lite, "first": FIRST}


def build():
    import sys
    arc = os.path.expanduser("~/Desktop/ARC-solver")
    if arc not in sys.path:
        sys.path.insert(0, arc)
    from arbor.solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=sorted(set(SURVEY_AGI + TASKS))))
    data = {tid: _task_data(tid, tasks[tid]) for tid in TASKS}
    with open(OUT, "w") as f:
        f.write(_HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    return OUT


_HTML = r"""<!doctype html><meta charset='utf-8'><title>object interactive</title>
<style>
body{background:#0d1117;color:#d0d7de;font:13px/1.5 ui-monospace,monospace;margin:0;padding:18px}
h1{font-size:16px;margin:0 0 3px} .lead{color:#8b949e;margin:0 0 12px;max-width:900px}
select{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font:13px ui-monospace}
.grids{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0 14px}
.gp{border:1px solid #30363d;border-radius:8px;padding:8px 10px;background:#161b22}
.gp h3{margin:0 0 6px;font-size:12px;color:#adbac7}
table.g{border-collapse:collapse} table.g td{border:1px solid #1c1c1c;cursor:pointer}
table.g td.hl{outline:2px solid #fff;outline-offset:-2px}
.obtn{display:inline-block;margin:3px 3px 0 0;padding:2px 7px;border:1px solid #30363d;border-radius:5px;
 background:#0d1117;cursor:pointer;font-size:11px;color:#c9d1d9}
.obtn:hover{border-color:#539bf5} .obtn.sel{background:#1f6feb;border-color:#1f6feb;color:#fff}
.sw{display:inline-block;width:9px;height:9px;border:1px solid #333;margin-right:4px;vertical-align:middle}
.obtns{margin-top:6px;max-width:260px}
.panel{border:1px solid #30363d;border-radius:8px;padding:10px 12px;background:#161b22;margin-bottom:14px}
.panel h2{font-size:14px;margin:0 0 8px;color:#e6edf3}
.row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.card{border:1px solid #30363d;border-radius:7px;padding:8px 10px;background:#0d1117;max-width:440px}
.card.wide{max-width:100%;flex:1 1 100%} .lbl{font-size:12px;margin-bottom:6px;color:#d2a8ff}
table.t{border-collapse:collapse;width:100%;font-size:12px}
table.t th,table.t td{border:1px solid #30363d;padding:2px 7px;text-align:left}
table.t th{background:#1c2128;color:#adbac7;font-weight:normal}
tr.comm td{background:#0f1f13} tr.comm .v{color:#3fb950;font-weight:bold}
tr.diff td{background:#2a1416} tr.diff .v{color:#f85149;font-weight:bold}
tr.grp td{background:#21262d;color:#f0b72f;font-weight:bold} td.sub{color:#8b949e;padding-left:16px}
.note{margin-top:6px;color:#d29922} .hint{color:#8b949e;font-style:italic}
pre{background:#010409;border:1px solid #30363d;border-radius:6px;padding:6px 8px;margin:6px 0 0;
 overflow:auto;max-height:150px;font-size:10.5px;color:#c9d1d9;white-space:pre}
</style>
<h1>object 인터랙티브 비교</h1>
<p class=lead>문제 선택 후, 각 그리드에서 object 를 <b>하나씩</b> 클릭(셀 또는 버튼). 4개가 다 선택되면
아래 <b>1차·2차</b>가 갱신되고, 선택을 바꿀 때마다 다시 계산된다. (1차=미리계산 · 2차=verdict 정렬)</p>
문제: <select id=task></select>
<div class=grids id=grids></div>
<div class=panel><h2>선택된 객체 0차 property</h2><div class=row id=zero></div></div>
<div class=panel><h2>1차 — compare(G0obj, G1obj)</h2><div class=row id=first></div></div>
<div class=panel><h2>2차 — compare(1차_P0, 1차_P1) <span class=hint>[verdict 정렬]</span></h2><div class=row id=second></div></div>
<script>
const ALL=__DATA__;
const PAL=["#000000","#0074D9","#FF4136","#2ECC40","#FFDC00","#AAAAAA","#F012BE","#FF851B","#7FDBFF","#870C25"];
const CN=["검정","파랑","빨강","초록","노랑","회색","자홍","주황","하늘","갈색"];
const GRIDS=["P0G0","P0G1","P1G0","P1G1"];
const OPRI={area:0,size:1,shape:2,color:3,coordinate:4,position:5,method:6,symmetry:7,contents:8};
let TID=Object.keys(ALL)[0], D=ALL[TID];
let sel={P0G0:null,P0G1:null,P1G0:null,P1G1:null};
function cell(){return Math.max(9,Math.min(16,Math.floor(320/Math.max(D.H,D.W))));}

function objOf(g,id){return D.objs[g].find(o=>o.id===id);}
function renderGrid(g){
  const raw=D.raw[g], o=sel[g]?objOf(g,sel[g]):null, CELL=cell();
  const hl=new Set(o?o.cells.map(c=>c[0]+","+c[1]):[]);
  let h="<table class=g>";
  for(let r=0;r<D.H;r++){h+="<tr>";
    for(let c=0;c<D.W;c++){const cls=hl.has(r+","+c)?" class=hl":"";
      h+=`<td${cls} style="width:${CELL}px;height:${CELL}px;background:${PAL[raw[r][c]]||'#333'}" data-r=${r} data-c=${c}></td>`;}
    h+="</tr>";}
  h+="</table><div class=obtns>";
  for(const ob of D.objs[g]){const s=sel[g]===ob.id?" sel":"";
    h+=`<span class="obtn${s}" data-id="${ob.id}"><span class=sw style="background:${PAL[ob.color]}"></span>${CN[ob.color]}·${ob.area}칸</span>`;}
  return h+"</div>";
}
function renderGrids(){
  const box=document.getElementById('grids'); box.innerHTML="";
  for(const g of GRIDS){const d=document.createElement('div'); d.className='gp';
    d.innerHTML=`<h3>${g}</h3>`+renderGrid(g); box.appendChild(d);
    d.querySelectorAll('td[data-r]').forEach(td=>{td.onclick=()=>{const r=+td.dataset.r,c=+td.dataset.c;
      const ob=D.objs[g].find(o=>o.cells.some(x=>x[0]===r&&x[1]===c)); if(ob){sel[g]=ob.id; refresh();}};});
    d.querySelectorAll('.obtn').forEach(bt=>{bt.onclick=()=>{sel[g]=bt.dataset.id; refresh();};});}
}
function ordered(paths){return paths.sort((a,b)=>{const ta=a.split('.')[0],tb=b.split('.')[0];
  const pa=OPRI[ta]??9,pb=OPRI[tb]??9; if(pa!==pb)return pa-pb; if(ta!==tb)return ta<tb?-1:1; return a<b?-1:1;});}
function grouped(paths){const g={}; for(const p of ordered(paths)){const t=p.split('.')[0]; (g[t]=g[t]||[]).push(p);} return g;}
function firstTable(m){const g=grouped(Object.keys(m));
  let h="<table class=t><tr><th>property</th><th>verdict</th><th>값1</th><th>값2</th></tr>";
  for(const top in g){h+=`<tr class=grp><td colspan=4>${top}</td></tr>`;
    for(const p of g[top]){const [t,a,b]=m[p]; const sub=p.slice(top.length+1)||"(전체)";
      h+=`<tr class=${t==='COMM'?'comm':'diff'}><td class=sub>${sub}</td><td class=v>${t}</td><td>${a}</td><td>${b}</td></tr>`;}}
  return h+"</table>";}
function secondTable(m0,m1){const paths=new Set([...Object.keys(m0),...Object.keys(m1)]);
  const g=grouped([...paths]); let same=true;
  let h="<table class=t><tr><th>property</th><th>1차_P0</th><th>1차_P1</th><th>관계 같음?</th></tr>";
  for(const top in g){h+=`<tr class=grp><td colspan=4>${top}</td></tr>`;
    for(const p of g[top]){const v0=(m0[p]||['∅'])[0],v1=(m1[p]||['∅'])[0]; const ag=v0===v1; same=same&&ag;
      const sub=p.slice(top.length+1)||"(전체)";
      h+=`<tr class=${ag?'comm':'diff'}><td class=sub>${sub}</td><td>${v0}</td><td>${v1}</td><td class=v>${ag?'COMM':'DIFF'}</td></tr>`;}}
  return h+"</table><div class=note>⇒ "+(same?"두 pair 의 object 변환이 <b>구조적으로 동일</b>":"두 pair 의 object 변환이 <b>일부 property 에서 다름</b>")+"</div>";}
function refresh(){
  renderGrids();
  const done=GRIDS.every(g=>sel[g]);
  const zero=document.getElementById('zero'),first=document.getElementById('first'),second=document.getElementById('second');
  if(!done){zero.innerHTML="<div class=hint>각 그리드에서 object 를 하나씩 선택하세요.</div>"; first.innerHTML=""; second.innerHTML=""; return;}
  zero.innerHTML=GRIDS.map(g=>{const o=objOf(g,sel[g]);
    return `<div class=card><div class=lbl>${g} · ${CN[o.color]}·${o.area}칸</div><pre>${JSON.stringify(o.json,null,1)}</pre></div>`;}).join("");
  const m0=D.first.pair0[sel.P0G0+"|"+sel.P0G1], m1=D.first.pair1[sel.P1G0+"|"+sel.P1G1];
  first.innerHTML=`<div class=card><div class=lbl>compare(P0G0·${CN[objOf('P0G0',sel.P0G0).color]}, P0G1·${CN[objOf('P0G1',sel.P0G1).color]})</div>${firstTable(m0)}</div>`
    +`<div class=card><div class=lbl>compare(P1G0·${CN[objOf('P1G0',sel.P1G0).color]}, P1G1·${CN[objOf('P1G1',sel.P1G1).color]})</div>${firstTable(m1)}</div>`;
  second.innerHTML=`<div class=card wide>${secondTable(m0,m1)}</div>`;
}
// 문제 드롭다운
const tsel=document.getElementById('task');
for(const t of Object.keys(ALL)){const o=document.createElement('option'); o.value=t; o.textContent=t; tsel.appendChild(o);}
tsel.onchange=()=>{TID=tsel.value; D=ALL[TID]; sel={P0G0:null,P0G1:null,P1G0:null,P1G1:null}; refresh();};
refresh();
</script>"""


if __name__ == "__main__":
    print("wrote", build())
