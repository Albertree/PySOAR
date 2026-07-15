# -*- coding: utf-8 -*-
"""ARBOR operator body: synthesize (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning.program import _global_recolor_program, _grid_decide, _size_expr_search
from arbor.reasoning import program_ast as PA


def _op_synthesize(ag):
    """**H-space 안의 DSL operator** — 가설을 조합·검증(SOAR 사이클로 이 공간에서 실행). `_grid_decide`
    로 속성별 후보 생성→train 검증→Pa.G0 적용→수렴검사. **H1,H2… 가설**을 이 공간(h)에 물질화하고,
    DECIDE 결과를 **부모(계층 substate)** 슬롯으로 올린 뒤 hspace-done 표시(→ fine_trace 가 공간 제거)."""
    h = ag.stack[-1].id
    parent = next((v for (i, a, v) in ag.wm if i == h and a == "superstate"), None)
    train = ag.task["train"]
    paG0 = ag.task["test"][0]["input"]
    root = ag.kg["arckg_root"]; p0 = root.example_pairs[0]
    g0grid = [list(r) for r in train[0]["input"]]
    dec = _grid_decide(train, paG0)
    miss, slotval, hn = [], {}, [0]
    for prop in ("size", "color", "contents"):
        d = dec[prop]
        hid = f"{h}.slot:{prop}"
        ag.wm.add(h, "slot", hid); ag.wm.add(hid, "prop", prop); ag.wm.add(hid, "type", d["type"])
        ag.wm.add(hid, "within", "/".join("COMM" if v else "DIFF" for v in d["within"]))
        for kind, pred, ok in d["cands"]:                            # 생성된 가설 = H1,H2… (이 공간의 원소)
            hn[0] += 1
            hh = f"{h}.H{hn[0]}"
            ag.wm.add(h, "hypothesis", hh)
            ag.wm.add(hh, "slot", prop); ag.wm.add(hh, "type", d["type"])
            ag.wm.add(hh, "rule", kind); ag.wm.add(hh, "predict", str(pred))
            ag.wm.add(hh, "verdict", "survive" if ok else "reject")
        if prop == "size" and any(v is False for v in d["within"]):   # NUMBER-DIFF brute-force 기각 가설도
            _, tried, _tr = _size_expr_search(train)
            for ax in ("H", "W"):
                for desc, okk in tried[ax][:6]:
                    if not okk:
                        hn[0] += 1
                        hh = f"{h}.H{hn[0]}"
                        ag.wm.add(h, "hypothesis", hh); ag.wm.add(hh, "slot", "size")
                        ag.wm.add(hh, "rule", f"MAP[{ax}1={desc}]"); ag.wm.add(hh, "verdict", "reject")
        ag.wm.add(hid, "decision", d["decision"])
        if d["decision"] == "DECIDE":
            ag.wm.add(hid, "value", str(d["value"])); slotval[prop] = d
        else:
            miss.append(prop)
    # (골조 정정 2026-07-16) dead operator set_grid_size/set_grid_color 제거 → size-ready/color-ready 를
    # 여기서 **직접** 세운다. 옛 handshake(set-size/set-color → set_grid_* operator → slot-grid_* WM 슬롯
    # → size-ready/color-ready)의 slot-grid_* 는 아무도 안 읽던 죽은 슬롯이었고, grid property 설정은 이제
    # hypothesize 가 all-3 일 때 set_grid_* **DSL** 을 program 에 emit 하는 것으로 일원화됐다. size-hyp/
    # color-hyp(예측 표현식)는 대시보드 근거로 남긴다. 하강 게이트 propose*solve*grid 는 size-ready·
    # color-ready 를 요구하므로 값 유무와 무관하게 ready 를 세워 c–h 하강 흐름을 보존한다.
    if slotval.get("size"):
        ag.wm.add(parent, "size-hyp", str(slotval["size"]["value"]))
    ag.wm.add(parent, "size-ready", "yes")
    if slotval.get("color"):
        ag.wm.add(parent, "color-hyp", str(sorted(slotval["color"]["value"])))
    ag.wm.add(parent, "color-ready", "yes")
    if slotval.get("contents"):                                       # contents DECIDE → 부모에서 GRID 종결
        ppid = f"{p0.node_id}.property"; cv = slotval["contents"]
        old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if old in (None, "{}"):
            ag.wm.remove(ppid, "program", old)          # 실제 저장된 sentinel(None 또는 구 "{}") 제거
        cmap = dec["color"].get("map")
        # 전역remap: _global_recolor_program 이 이미 AST-json 반환(Task 7). 항등(output=input): 빈 body
        # AST(execute 가 input 을 그대로 복사) — program_ast.program([]). 상수출력(입력과 무관한 고정
        # grid)은 coloring 조합으로 표현 불가(새 atom 금지 §2) → 기존처럼 미합성 표식 문자열 유지
        # (as_source 가 그대로 통과시킴; GRID-verdict 로만 노출).
        prog = (_global_recolor_program(g0grid, cmap) if (cv["note"] == "전역remap" and cmap)
                else json.dumps(PA.program([])) if cv["note"] == "항등"
                else "output_grid = <상수 출력>")
        ag.wm.add(ppid, "program", prog)
        ag.kg["answer"] = cv["value"]; ag.add_output_wme("answer", tuple(tuple(r) for r in cv["value"]))
        ag.wm.add(parent, "hypothesized", "yes"); ag.wm.add(parent, "answer-ready", "yes")
        ag.wm.add(parent, "grid-verdict", f"GRID 종결(contents {cv['note']})")
    else:
        ag.wm.add(parent, "grid-verdict",
                  f"size={dec['size']['decision']} color={dec['color']['decision']} "
                  f"contents={dec['contents']['decision']} → 미결={miss} 하강")
        gid = f"{parent}.goal"
        ag.wm.add(parent, "grid-descend", gid); ag.wm.add(gid, "produce", ",".join(miss) or "contents")
    ag.wm.add(h, "synthesized", "yes"); ag.wm.add(h, "hspace-done", "yes")   # 이 공간 종료 → 부모 복귀
