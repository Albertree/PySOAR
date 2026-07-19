# -*- coding: utf-8 -*-
"""ARBOR operator body: hypothesize (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning.program import _grid_decide
from arbor.reasoning.program_ast import grid_program_from_decide, is_full_grid_program


def pair_cursor(ag):
    """현재 처리 중인 example pair 인덱스 (S1 ^pair-idx k; 기본 0). per-pair 순회의 커서 —
    verify 가 한 pair 의 program 을 완성하면 다음 pair 로 +1 하고, 그 값을 hypothesize/synthesize
    가 읽어 그 pair 의 grid 로 흐름을 다시 탄다 (§1-5: 각 program 이 흐름에서 나오게)."""
    v = next((v for (i, a, v) in ag.wm if i == "S1" and a == "pair-idx"), None)
    return int(v) if v is not None else 0


def _op_hypothesize(ag):
    """**hypothesize = 시뮬레이션 open** (조립·검증은 규칙이!). compare 가 이미 남긴 **pixel** compare
    relation(`{pair}.E_G0Xi-G1Xi`, color DIFF)을 그대로 WM 에 recolor-rel 로 노출한다(coloring 규칙이
    소비). 시뮬 grid 를 G0(input)로 초기화. 조립은 이후 coloring operator 가, 검증은 verify 가 한다.
    (2026-07-19) OBJECT level 은 재채색을 노출하지 않는다 — object 좌표(셀 집합)를 coloring 의 단일
    position arg 로 공급하는 규칙이 없어 재채색은 pixel level 에서만 일어난다(§_op_coloring 주석)."""
    sid = ag.stack[-1].id
    root = ag.kg["arckg_root"]
    k = pair_cursor(ag)                                        # 현재 pair (커서)
    p0 = root.example_pairs[k]
    gid0, gid1 = p0.input_grid.node_id, p0.output_grid.node_id
    ag.wm.add(sid, "sim-pair", p0.node_id)

    g0grid = [list(r) for r in ag.task["train"][k]["input"]]
    g1grid = [list(r) for r in ag.task["train"][k]["output"]]
    if ag.wm.contains(sid, "level", "GRID"):
        # ── (골조 정정 2026-07-16) GRID hypothesize = **관계로 3속성 판정 → program 생성 or 하강**.
        #    compare 가 남긴 within/cross 관계 + `_grid_decide`(후보 생성→train 검증→Pa.G0 적용)로 G1 의
        #    size/color/contents 를 정한다. 셋 다 결정(all-3) → `grid_program_from_decide` 로 3-property
        #    program → 각 example pair 에 물질화 + programs-ready(→ generalize→resolve→apply_solution 로
        #    답이 program 실행에서 나옴). 하나라도 미결(부분) → 별도 가설공간(H-space)을 열어 `synthesize`
        #    가 판정·하강신호를 잇는다(현행 c–h object/pixel 경로). 부분예측 program 은 contents 없이
        #    실행 불가 = "grid 를 예측했다"고 볼 수 없음(§P1 막혀야 하강).
        dec = _grid_decide(ag.task["train"], ag.task["test"][0]["input"])
        gp = grid_program_from_decide(dec)
        hn = 0              # 탐색 후보를 WM 에 노출(spec §13/§1-5 visibility) — synthesize.py:27-44 미러.
        for prop in ("size", "color", "contents"):             # full(a/b)·partial(c-h) 공통 — 결정된 슬롯의
            for kind, pred, ok in dec[prop]["cands"]:          # 근거(H1,H2…)는 부분 하강 때도 버리지 않는다.
                hn += 1
                hh = f"{sid}.H{hn}"
                ag.wm.add(sid, "hypothesis", hh)
                ag.wm.add(hh, "slot", prop)
                ag.wm.add(hh, "rule", kind); ag.wm.add(hh, "predict", str(pred))
                ag.wm.add(hh, "verdict", "survive" if ok else "reject")
        if is_full_grid_program(gp):                           # all-3 결정 → 3-property program
            gpj = json.dumps(gp)
            for k2, pp in enumerate(root.example_pairs):       # per-pair 물질화 (같은 3속성 골격)
                if k2 >= len(ag.task["train"]):
                    break
                ppid = f"{pp.node_id}.property"
                old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
                if old in (None, "{}"):
                    ag.wm.remove(ppid, "program", old)         # sentinel(None/구 "{}") → 실제 program
                ag.wm.add(ppid, "program", gpj)                # PAIR.program (3-property AST-json)
            ag.wm.add(sid, "programs-ready", "yes")            # → generalize→resolve→apply_solution
            ag.wm.add(sid, "grid-verdict",
                      f"GRID 종결(3속성 program: size={dec['size']['decision']}·"
                      f"color={dec['color']['decision']}·contents={dec['contents']['note']})")
            return
        # PARTIAL(주로 contents 미결) → 결정된 슬롯(size/color)을 담은 skeleton 을 parent GRID substate 에
        # stash(버리지 않음). pending 슬롯은 T4(verify)가 하강 coloring 으로 채운다 — 여기선 PAIR.program 미기록.
        ag.wm.add(sid, "grid-skeleton", json.dumps(gp))
        ag.create_hspace(ag.stack[-1], "GRID")                 # 부분 미결 → 하강(현행 synthesize 경로)
        return
    if ag.wm.contains(sid, "level", "PIXEL"):
        # PIXEL 가설 = **잔여(residual) 처리**: 상위(object) substate 가 재채색한 sim·program 을 이어받아,
        # object 로 못 맞춘 셀(그 sim 이 아직 G1 과 다른 셀)만 pixel 로 재채색해 **object 가설에 덧붙인다**.
        # object 로 완결된 문제(845·868·08ed)는 애초에 PIXEL 로 안 내려온다(object verify 통과). object 가
        # 일부만 처리한 문제(예: 009d5c81)는 그 sim 에서 이어받아 잔여만 pixel 이 마감한다.
        # 순회 pair(k>0)는 자기 G0 에서 새로 시작(상위 object sim 이어받지 않음 — 그건 pair0 descent 용).
        sup = ag.stack[-2].id if (k == 0 and len(ag.stack) >= 2) else None
        base_sim = next((v for (i, a, v) in ag.wm if i == sup and a == "sim"), None) if sup else None
        base_prog = next((v for (i, a, v) in ag.wm if i == sup and a == "program-code"), None) if sup else None
        sim0 = [list(r) for r in base_sim] if base_sim else [list(r) for r in g0grid]  # object 재채색 후 상태
        ag.wm.add(sid, "sim", _tup(sim0))                       # pixel sim = object 재채색 결과에서 이어감
        if base_prog:
            ag.wm.add(sid, "base-program", base_prog)           # 덧붙일 object 가설(program)
        # 잔여 변화 = xform 을 손으로 재구성하지 않는다 — compare(pxmatch) 가 이 pair 마다 이미 남긴
        # pixel relation(`{pair}.E_G0Xi-G1Xi`, color DIFF)을 그대로 노출한다(Part B: xform 대체).
        # relation 은 pair 노드(pid) 아래 (pid ^relation E) 로 걸려 있고, 그 E 가 color DIFF 인 것만
        # "칠할 셀"이다(coordinate 는 COMM — pxmatch 가 같은 좌표끼리만 비교하니 자명, §pxmatch).
        pid = p0.node_id
        rels = sorted(v for (i, a, v) in ag.wm if i == pid and a == "relation"
                      and ".E_G0X" in v and ag.wm.contains(v, "type", "DIFF"))
        if rels:
            for E in rels:
                ag.wm.add(sid, "recolor-rel", E)                # coloring body 가 이걸 스캔해 전부 칠함
            # propose*coloring 은 **존재 신호 하나**(recolor-rel-pending)로만 발화한다 —
            # `(<s> ^recolor-rel <e>)` 로 직접 매칭하면 relation 마다 별도 <e> 바인딩 → 매 relation 당
            # 별개의 operator(<o>)가 제안돼 TIE(동일 이름 operator 복수, 미처리)로 run 이 죽음을 실측
            # (move000a 가 score 0/60). "한 operator 가 전부 처리" 모델 유지엔 단일 scalar 게이트가
            # 필요 — object 도 이 신호를 공유한다(Part B: 아래 OBJECT 분기).
            ag.wm.add(sid, "recolor-rel-pending", "yes")
            # H-space 가시화(nice-to-have, §brief-41)는 **생략**: create_hspace 가 ag.stack 에 새
            # goal(H..)을 push 해 이후 decide 가 그 위에서 진행되고, 다음 cycle 에 그 H-space 에서
            # TIE(미처리)로 전체 run 이 조기종료됨도 실측 — 필수 아님(브리프 명시)이라 안전을 위해 뺀다.
        else:
            ag.wm.add(sid, "colored-all", "yes")                # 변화 relation 없음 → 곧장 verify
        return
    else:
        ag.wm.add(sid, "sim", _tup(g0grid))                     # OBJECT: 시뮬 grid = G0
        # (2026-07-19 원천차단) OBJECT 재채색 노출 **제거**. object compare relation(`{pair}.E_G0Oi-G1Oj`)은
        # WM 에 descriptive 로 그대로 있으나, 여기서 recolor-rel 로 노출하지 않는다 — object 좌표(셀 집합)를
        # coloring 의 단일 position arg 로 넣는 **규칙이 없어** 예전엔 body 해킹으로만 재채색이 성립했기 때문.
        # 그 발화원(recolor-rel 노출)을 끊어 object coloring 을 원천 차단한다. OBJECT level 은 재채색을
        # 시도하지 않고 곧장 verify → (변화 있으면) 실패 → PIXEL 하강(move: object 는 원래 no-op → 동일).
        ag.wm.add(sid, "colored-all", "yes")
        return
