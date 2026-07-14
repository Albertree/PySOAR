# -*- coding: utf-8 -*-
"""
focus_solver -- SLICE 1 of the goal-backward / focus-descent rebuild.

Replaces the hard-coded pipeline (observe->compare->generalize->compose) with the
agreed REFLEX LOOP, applied per node and driven by need/impasse:

solve is an UNDEFINED operator: the agent is given "solve the task" as a GOAL but has
NO knowledge of how. Proposing + selecting solve with no apply rule => OPERATOR
no-change impasse (the canonical SOAR "operator-implementation" subgoal). The substate
that opens exists to FIGURE OUT how to apply solve; focus descends one ARCKG level and
observe/compare gather what implementing it needs:

    S1  ^goal solve, ^focus TASK       -> OBSERVE task first (reveals its pairs P0,P1,Pa)
                                         -> then solve (focus now ^seen) -> ONC -> S2
    S2  ^focus P0                      -> observe P0 + COMPARE peers P0,P1,Pa:
                                             P0,P1 = {input:y, output:y} ; Pa = {input:y, output:n}
                                         -> IMBALANCE discovered HERE: Pa lacks 'output'
                                         -> ^goal DISCOVERED (S2 ^goal G)(G ^node Pa)(G ^produce output)
                                         -> solve (goal + focus seen) -> ONC -> S3
    S3  ^focus P0.G0 ...               -> observe + compare grids -> ^goal -> solve -> ONC -> S4
    ...

Perception->Deliberation->Action: observe (focus-gated) ALWAYS runs before solve
(solve is gated on the focus being ^seen). The GOAL (produce Pa.output) is NOT handed
down -- it is DISCOVERED inside S2 after observing and comparing all peers. solve keys
on ^goal (+ observed focus), so it never encodes "solve by comparing".

Scope (honest): no chunking / result-return is wired yet, so solve never actually
implements -- every level ONC-descends to the bottom, easy000a stays UNSOLVED. What is
verified is the principled control structure (undefined solve -> operator no-change ->
implement-subgoal -> descend, goal discovered in-substate). Wiring result + chunking so
solve produces the grid and is LEARNED is the next slice.

    python3 arc/focus_solver.py        # -> arc/focus_dashboard.html
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production          # noqa: E402
from arc.expr_solver import build_arckg, _load_value, _tup   # noqa: E402 (reuse, read-only)
from procedural_memory.operators import OPERATOR_BODIES  # 분리된 operator bodies

# --- P2c: 아래 지원계층 함수들은 arbor/ 로 분리됨 (re-export 허브) ---
from arbor.perception.nav import (index_arckg, _cursor, _focus_group, _siblings, _receipt_leaves, _lca, _short, _edge_name, _load_props)
from arbor.reasoning.program import (_size_expr_search, _size_apply, _grid_decide, _dec, _color_map_search, _global_recolor_program, _colorset, _grid_prop_value, _grid_property_hypotheses, _materialize_pair_programs, _pixel_residual_program)
from arbor.reasoning.compare_engine import (_store_receipt, _agree, _compare2, _compare, _store_relation)
from arbor.perception.perception import (_obj_cc, objects_of, _fg_correspondence, _score_frac)


# ---------------------------------------------------------------------------
# ARCKG index: id -> node / parent / children / level (so observe/compare/descend
# can walk the hierarchy the lens defines).
# ---------------------------------------------------------------------------


























# ---------------------------------------------------------------------------
# operator bodies (RHS functions): the ARCKG/comparison work
# ---------------------------------------------------------------------------


    # ^seen 표시 + cursor 소비는 apply*observe 규칙이 (body 뒤 settle 에서).
























    # 하강 goal 은 여기서 세우지 않는다 — GRID hypothesize 가 within(G0→G1) 변환을 속성별로 결론지으려
    # 시도한 뒤, 못 내면 그때 goal(produce=미결)을 세운다 (predict↔hypothesize 가 동시에 solve 를
    # 제안해 operator-tie 나는 것 방지; 하강 여부는 hypothesize 의 판정이 주도, 사용자 교정 2026-07-11).








































# ── grid.size / grid.color 를 채우는 두 DSL operator (coloring 과 대등한 기본 DSL 3종의 나머지 둘,
#    사용자 결정 2026-07-12). coloring 이 contents 슬롯을 칠하듯, 이 둘은 **program 의 grid_size /
#    grid_color 슬롯**을 채운다. hypothesize 가 노출한 가설(^size-hyp / ^color-hyp = *표현식*, 리터럴
#    아님 → TASK.solution 일반화 가능)을 읽어 슬롯으로 물질화. 가설이 없거나 'unknown' 이면 슬롯을
#    unknown 으로 남긴다(= 이 level 정보로 못 정함 → 하강 신호, '오류' 아님).
#
#    배선 계약(hypothesize 재작성 때 이걸 세우면 두 operator 가 발화):
#      (sid ^set-size yes)   + (sid ^size-hyp  <expr|unknown>)   → set_grid_size → (sid ^slot-grid_size <expr>)
#      (sid ^set-color yes)  + (sid ^color-hyp <expr|unknown>)   → set_grid_color→ (sid ^slot-grid_color <expr>)
#    지금은 어떤 규칙도 set-size/set-color 를 세우지 않으므로 **휴면**(회귀 0). hypothesize 손볼 때 활성화.




# operator body(RHS 함수) = production 으로 못 하는 원자연산만:
#   observe = to_json 로드 · compare = kg_compare · select = 다음 대상 고르기(§1-3 탐색의 자리).
#   hypothesize = 슬롯(size·color·contents) 예측 open. 기본 DSL 3종 = set_grid_size·set_grid_color·coloring.
# 제어(무엇을 언제)는 전부 propose/apply 규칙 + WM 플래그로. solve 는 미구현(ONC=하강),
# submit 은 apply-only(답은 output-link 에).


# ---------------------------------------------------------------------------
# productions -- FOCUS-SCOPED conditions (not a global flag pipeline). Each operator
# fires because of the gap at the CURRENT focus, and the order emerges from it.
# ---------------------------------------------------------------------------
# STATE-RELATIVE: <s> binds to the current (sub)state (the one holding ^focus). So the
# SAME rules fire in the top state and in every substate as attention descends -- a
# substate's focus (one level deeper) gets observed/compared by these same productions.
def _propose(name, conds):
    return _propose_named(f"propose*{name}", name, conds)


def _propose_named(prod_name, op_name, conds):
    # same RHS as _propose, but an explicit production name -- lets one operator
    # (solve) have TWO proposal variants (Soar's role*operator*variant convention).
    return Production(
        prod_name, conds,
        [Action("<s>", "operator", "<o>", "+"),
         Action("<o>", "name", op_name), Action("<o>", "node", "<f>")])


def _apply(name, attr):
    # writes the result flag ON THE FOCUS NODE the operator targeted (<o> ^node <f>)
    return Production(
        f"apply*{name}",
        [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", name), Cond("<o>", "node", "<f>")],
        [Action("<f>", attr, "yes")])


def _apply_state(name, *acts):
    # solving-pipeline apply: writes result flag(s) ON THE STATE <s> (the goal-holder),
    # not the focus node. ``acts`` = (attr, val[, pref]) tuples. Body (SOLVE_BODIES)
    # runs as this rule fires; the flags here gate the NEXT operator (generate-and-test).
    return Production(
        f"apply*{name}",
        [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", name)],
        [Action("<s>", a[0], a[1], a[2] if len(a) > 2 else "+") for a in acts])


def _propose_nonode(prod_name, op_name, conds):
    # arg(대상)를 붙이지 않고 operator 제안 (^node 없음). 대상은 arg-선택 substate 의 select 가
    # super 의 커서로 정한다 — "propose 에 arg 를 박지 않는다"(사용자 요청)의 실체.
    return Production(prod_name, conds,
                      [Action("<s>", "operator", "<o>", "+"), Action("<o>", "name", op_name)])


PRODUCTIONS = [
    # ── 관측/비교: arg(대상)를 propose 에 **박지 않는다.** super 에 세워진 ^cursor / ^cmp-active
    #    (= arg-선택 substate 의 select 가 정해준 것)가 있어야 apply 된다. 없으면 body·apply 규칙
    #    둘 다 변화 없음 → **ONC impasse → arg-선택 substate** 가 열리고 그 안 select 가 대상을 정함.
    _propose_nonode("propose*observe", "observe",
                    [Cond("<s>", "to-observe", "yes"), Cond("<s>", "observed", "<o>", negated=True)]),
    _propose_nonode("propose*compare", "compare",
                    [Cond("<s>", "to-compare", "yes"), Cond("<s>", "compared", "<x>", negated=True),
                     Cond("<s>", "answer-ready", "<ar>", negated=True)]),   # 답 나오면 compare 멈추고 submit
    # apply: super 커서(^cursor/^cmp-active)로 결과 플래그(^seen/^done) + 커서 **소비**(다음엔 다시 select).
    Production("apply*observe",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "observe"), Cond("<s>", "cursor", "<f>")],
               [Action("<f>", "seen", "yes"), Action("<s>", "cursor", "<f>", "-")]),
    Production("apply*compare",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "compare"), Cond("<s>", "cmp-active", "<f>")],
               [Action("<f>", "done", "yes"), Action("<s>", "cmp-active", "<f>", "-")]),

    # ── select: arg-선택 substate 안에서 한 번 발화 — body 가 super 커서(^cursor/^cmp-active)를
    #    세우고 자기 자신에 ^selected 표시. 그러면 -(^selected) 조건이 깨져 retract → substate 는
    #    더 고를 게 없어 SNC → fine_trace 가 pop → super 의 observe/compare 가 그 arg 로 apply.
    # 하나의 **일반 select** operator — observe·compare 를 이름으로 구분하지 않는다. arg-선택 substate 면
    #   (^select-for <아무값>) 발화하고, **무엇을 고를지는 body 가 WM(미관측 focus 유무·observed·cmp 상태)에서
    #   추론**한다 (사용자 요청 2026-07-10: specific 이름 대신 WM 을 읽어 대상 결정).
    _propose_nonode("propose*select", "select",
                    [Cond("<s>", "select-for", "<sf>"), Cond("<s>", "selected", "<x>", negated=True)]),

    # ── hypothesize: OBJECT 레벨 object mapping 이 끝나면(compared) 발화 — object mapping 을
    #    program(가설)으로 합성·검증(body=시뮬레이션 조립·train 대조). arg-선택 substate 불필요
    #    (대상 object 는 mapping 에 있음). 통과=hypothesized yes(+PAIR.program), 실패=failed.
    # hypothesize = 시뮬레이션 open — body: 시뮬 grid=G0 + 대응→xform 후보(속성별 COMM/DIFF) 노출. 1회.
    _propose_named("propose*hypothesize", "hypothesize",
                   [Cond("<s>", "to-hypothesize", "yes"), Cond("<s>", "compared", "yes"),
                    Cond("<s>", "hyp-open", "<o>", negated=True),
                    Cond("<s>", "answer-ready", "<ar>", negated=True)]),  # 이미 답 남(예:상수출력)→hypothesize 생략
    Production("apply*hypothesize",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "hypothesize")],
               [Action("<s>", "hyp-open", "yes")]),
    # synthesize = **H-space 전용** DSL — 가설공간 안에서만 발화(^type hypothesis-space). 가설을 조합·
    #   검증(body=_grid_decide)해 H1,H2… 물질화 + 부모 슬롯 세팅 + hspace-done. (SOAR 사이클로 이 공간 실행.)
    _propose_named("propose*synthesize", "synthesize",
                   [Cond("<s>", "type", "hypothesis-space"), Cond("<s>", "synthesize", "yes"),
                    Cond("<s>", "synthesized", "<x>", negated=True)]),
    Production("apply*synthesize",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "synthesize")],
               [Action("<s>", "synth-step", "yes")]),
    # coloring DSL = **규칙기반**: color DIFF ∧ coordinate COMM 인 xform 이 있으면 propose →
    #   apply(body=frozen coloring)가 그 object.coordinate 를 g1color 로 시뮬 grid 에 칠함. 하나씩(multi-cycle).
    _propose_named("propose*coloring", "coloring",     # 단일 marker → 한 번만 propose(TIE 방지)
                   [Cond("<s>", "has-recolor", "yes"), Cond("<s>", "colored-all", "<ca>", negated=True)]),
    Production("apply*coloring",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "coloring")],
               [Action("<s>", "color-step", "yes")]),      # body 가 시뮬 recolor + applied 표시
    # set_grid_size / set_grid_color = 기본 DSL 3종의 나머지 둘(coloring 과 대등). hypothesize 가
    #   ^set-size / ^set-color 를 세우면 발화해 body 가 ^size-hyp / ^color-hyp(표현식)을 grid_size /
    #   grid_color 슬롯으로 물질화. 지금은 그 플래그를 아무도 안 세우므로 **휴면**(회귀 0) — hypothesize 재작성 때 활성화.
    _propose_named("propose*set_grid_size", "set_grid_size",
                   [Cond("<s>", "set-size", "yes"), Cond("<s>", "size-set", "<x>", negated=True)]),
    Production("apply*set_grid_size",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "set_grid_size")],
               [Action("<s>", "size-step", "yes")]),        # body 가 grid_size 슬롯 물질화 + ^size-set
    _propose_named("propose*set_grid_color", "set_grid_color",
                   [Cond("<s>", "set-color", "yes"), Cond("<s>", "color-set", "<x>", negated=True),
                    Cond("<s>", "size-ready", "yes")]),    # size 뒤 순차(operator-tie 회피)
    Production("apply*set_grid_color",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "set_grid_color")],
               [Action("<s>", "grid-color-step", "yes")]),  # body 가 grid_color 슬롯 물질화 + ^color-set
    # verify = 시뮬 grid 를 train output 과 대조(원자) → hypothesized yes/failed.
    _propose_named("propose*verify", "verify",
                   [Cond("<s>", "colored-all", "yes"), Cond("<s>", "hypothesized", "<h>", negated=True)]),
    Production("apply*verify",
               [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", "verify")],
               [Action("<s>", "verify-step", "yes")]),          # body 가 ^hypothesized yes/failed 세움

    # submit: predict 가 답을 output-link 에 얹고 ^answer-ready → 제출·채점.
    _propose("submit", [Cond("<s>", "answer-ready", "yes"), Cond("<s>", "done", "<x>", negated=True)]),

    # solve = 미구현(apply·body 없음) → ONC impasse → 한 ARCKG 계층 하강(fine_trace._do_descend).
    _propose_named("propose*solve*bootstrap", "solve",
                   [Cond("<s>", "goal", "solve"), Cond("<s>", "observed", "yes")]),
    _propose_named("propose*solve*fallback", "solve",
                   [Cond("<s>", "goal", "<g>"), Cond("<g>", "produce", "<p>"),
                    Cond("<s>", "compared", "yes"), Cond("<s>", "answer-ready", "<a>", negated=True)]),
    # GRID hypothesize 뒤 하강: set_grid_size/color 가 순차로 슬롯 물질화(size-ready·color-ready) 완료된
    #   **뒤에만** solve → 하강 (set_grid operator 와 동시제안 tie 회피). goal 대신 grid-descend 사용.
    _propose_named("propose*solve*grid", "solve",
                   [Cond("<s>", "grid-descend", "<g>"), Cond("<g>", "produce", "<p>"),
                    Cond("<s>", "size-ready", "yes"), Cond("<s>", "color-ready", "yes"),
                    Cond("<s>", "answer-ready", "<a>", negated=True)]),
    # OBJECT hypothesize 실패 → solve(미구현) → ONC → _do_descend 가 GRID.pixels 로 하강(PIXEL).
    _propose_named("propose*solve*pixel", "solve",
                   [Cond("<s>", "hypothesized", "failed"), Cond("<s>", "pixel-open", "<p>", negated=True)]),

    _apply_state("submit", ("done", "yes")),
    # select·solve 는 apply 규칙 없음: select body 가 super 커서를 세우는 것(=arg 고르기, §1-3 탐색
    # 자리)이 곧 적용이고, solve 는 의도적 미구현(=하강).
]


# ---------------------------------------------------------------------------
# input + agent setup (mirrors expr_solver.setup_arc_agent shape so the tracer reuses it)
# ---------------------------------------------------------------------------
def inject_focus(ag):
    """INPUT: separate PERCEPTION from the agent's parsed MODEL (option a).

      input-link (percept):  I2 -^task-> <percept> -^raw-> {json}   [environment-owned, READ-ONLY]
      state (ARCKG model):   S1 -^arckg-> <root> -^example-> P0 ..  [observe/compare fill this]
      top goal:              S1 -^goal-> solve                      [drives solve; NO ^focus at top]
      attention:             S2 -^focus-> P0 ...                    [^focus lives on substates, descends]

    The environment delivers ONLY the raw, unparsed task onto ^io.input-link -- a
    PERCEPT node (its own id) carrying identity (^type/^name) + the literal ^raw dict.
    Perception is environment-owned and never mutated by the agent's operators.

    The parsed ARCKG is the agent's OWN structure, anchored on the top STATE via
    (S1 ^arckg <root>) -- NOT dangling off the input-link. observe/compare augment
    <root> and its descendants (the model), so a substate whose ^focus points one
    ARCKG level deeper is reading/extending the SUPERSTATE's shared, S1-anchored
    model (the SOAR 'substate reads superstate' regime) -- never the raw percept.

    <percept> and <root> are DISTINCT ids on purpose: if they were the same node,
    observe augmenting the model would still be mutating the input-link's percept.
    Justification for the two new symbols (per the no-free-symbols rule):
      ^arckg  -- anchors the agent-built model on its state, so the parse is a
                 deliberative structure, not part of environment perception.
      percept -- keeps perception a separate, immutable node the operators only read."""
    if ag.kg.get("arckg_root") is not None:
        return
    root = build_arckg(ag.task_id, ag.task)
    ag.kg["arckg_root"] = root
    ag.kg["idx"] = index_arckg(root)
    rid = root.node_id
    # (1) raw perception on the input-link -- a PERCEPT node distinct from the ARCKG
    #     root, so augmenting the model never touches what the environment delivered.
    pid = f"percept-{rid}"
    ag.add_input_wme("I2", "task", pid)              # input-link -> percept node
    ag.add_input_wme(pid, "type", "task")            # identity only
    ag.add_input_wme(pid, "name", ag.task_id)
    ag.add_input_wme(pid, "raw", json.dumps(ag.task))  # the literal task dict
    # (2) the parsed ARCKG root on the STATE + the top GOAL + the attention ^focus on the
    #     task. Perception-Deliberation-Action: observe (focus-gated) fires FIRST and
    #     reveals the task's children (the pairs); ONLY THEN does solve fire (it is gated
    #     on the focus being ^seen -- "look before you attempt", a universal ordering, NOT
    #     a domain method). solve, being UNIMPLEMENTED, then yields an operator no-change
    #     impasse and the substate descends one ARCKG level.
    ag.wm.add("S1", "arckg", rid)                     # ARCKG root lives on the state
    ag.wm.add("S1", "goal", "solve")                  # TOP GOAL: solve the task (bootstrap, under-specified)
    ag.wm.add("S1", "level", "TASK")                  # ARCKG 계층명(대문자)
    ag.wm.add("S1", "focus", rid)                     # 이 계층 노드 그룹 = TASK 하나
    ag.wm.add("S1", "to-observe", "yes")              # 관측할 게 있음 → observe(arg 없이) 제안 → impasse → select


def setup_focus_agent(task, tid="0a", record=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record, io=True)
    ag.task = task
    ag.task_id = tid
    ag.kg = {"_focus": True, "relations": [], "roles": []}     # _focus: dashboard detail 라우팅
    ag.input_functions.append(inject_focus)
    return ag


OP_DOCS = {
    "observe": "arg(대상) **없이** propose → ^cursor(=arg-선택 substate 의 select 가 세워줌)가 있을 때만 관측(property→^property)·^seen. 없으면 no-change → ONC impasse → arg-선택 substate",
    "compare": "arg 없이 propose → ^cmp-active(select 가 세워줌) 있을 때만 그 비교 수행(원자연산 kg_compare). 없으면 impasse. PAIR=peers(불균형→goal), GRID=within×pair→cross(삼중쌍)→predict",
    "select": "arg-선택 substate 안의 operator. observe/compare 가 arg 없이 걸린 impasse 를 푼다 — superstate 의 다음 대상을 preference(순서상 첫 미완료=a안)로 골라 super ^cursor/^cmp-active 세팅 → impasse 해소·pop. §1-3 탐색 자리",
    "submit": "predict 가 output-link 에 얹은 답 제출 → 채점 → ^done",
    "solve": "미구현 operator (apply·body 없음). goal 있고 이 레벨에서 답 못 냄 → 변화 없음 → operator no-change impasse → 한 계층 하강. (bootstrap: TASK 관측 후 PAIR 로)",
    "coloring": "기본 DSL(contents 슬롯). color DIFF ∧ coord COMM xform 을 frozen coloring 으로 시뮬 grid 에 하나씩 칠함(object·pixel level). program 의 grid_contents 를 채운다",
    "set_grid_size": "기본 DSL(grid_size 슬롯). hypothesize 의 ^size-hyp(표현식) 을 grid_size 슬롯으로 물질화. 가설 없으면 unknown(=현재 정보로 못 정함 → 하강). ^set-size 로 발화",
    "set_grid_color": "기본 DSL(grid_color 슬롯). hypothesize 의 ^color-hyp(표현식) 을 grid_color 슬롯으로 물질화. 가설 없으면 unknown. ^set-color 로 발화",
}


# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------
def _cycle_tree(events):
    """git dev-tree 용 **cycle 별 요약 노드** 목록. 각 노드 = 한 decision cycle:
      depth  = substate 깊이(S1=0, 하강할수록 +1) → 그래프의 lane(가로 위치)
      branch = 이 cycle 에 substate 가 생겼나(가지 침 = impasse)
      summary= 한 줄 요약 (무엇이 선택·적용됐나 / 뭐가 안돼 substate 가 났나)
      step   = 이 cycle 의 첫 이벤트 seq (노드 클릭 시 stepper 점프 대상)."""
    import re
    from itertools import groupby
    nodes = []
    for c, grp in groupby(events, key=lambda e: e["cycle"]):
        ec = list(grp)
        stk = ec[-1].get("goal_stack") or ["S1"]              # cycle 끝 시점의 goal 스택(=살아있는 lane 들)
        depth, gid = max(0, len(stk) - 1), stk[-1]
        op = None
        for e in ec:
            if e["kind"] == "op-select":
                m = re.search(r"name=([a-z]+)", e["label"])
                if m:
                    op = m.group(1)
        sub = [e for e in ec if e["kind"] == "substate"]
        applied = any(e["kind"] == "op-apply" and "새 substate" not in e["label"] for e in ec)
        subd = next((e for e in ec if e["kind"] == "substate" and "생성" in e["label"]), None)
        if sub:                                                   # 가지 침 (impasse → substate)
            lab = (subd or sub[-1])["label"]
            lv = re.search(r"level=([A-Z]+)", lab)
            if "하강" in lab:
                summ = f"‹{op or 'solve'}› 미구현 → 하강" + (f" · {lv.group(1)} 관측 시작" if lv else "")
            elif "arg" in lab:
                summ = f"‹{op or 'observe/compare'}› 대상 미정 → 대상 선택 substate"
            elif "자식 없음" in lab:
                summ = "더 하강할 계층 없음 → 종료"
            else:
                summ = lab[:70]
            knd = "branch"
        elif applied:
            summ, knd = f"‹{op}› 선택 → 적용", "apply"
        elif op:
            summ, knd = f"‹{op}› 제안·선택", "select"
        elif any(e["kind"] == "output" and "answer" in e["label"].lower() for e in ec):
            summ, knd = "답 제출(output)", "output"
        else:
            summ, knd = (ec[-1]["label"] or "")[:70], "phase"
        nodes.append({"cycle": c, "depth": depth, "goal": gid, "op": op or "", "kind": knd,
                      "branch": bool(sub), "summary": summ, "step": ec[0]["seq"], "stack": stk})
    return nodes


def _dash_data(task, tid="0a", max_cycles=1000):   # observe+compare+aggregate+find+solve+…×levels
    from arc.fine_trace import _Tracer
    tr = _Tracer(task, tid, setup=setup_focus_agent)
    events = tr.run(max_cycles=max_cycles)
    wm_states = tr._wm_states           # emit 이 연속중복 병합해 이미 축소·인덱싱(events 는 wm_state 보유)
    # 제출 시도(3회 환경)를 대시보드 후보로: 각 시도의 답 격자 + 정답 여부.
    # HTML 은 c.answer 를 *테스트 pair 별 격자들의 리스트* 로 렌더(c.answer.map(grid)) →
    # 단일 test 답을 리스트로 감싼다.
    candidates = [{"answer": [a["answer"]] if a["answer"] else [],
                   "position": f"attempt {i + 1}: {a['hyp']}",
                   "color": "✓" if a["correct"] else "✗"}
                  for i, a in enumerate(tr.attempts)]
    correct_i = next((i for i, a in enumerate(tr.attempts) if a["correct"]), None)
    from arc.dashboard import wm_deltas
    return {
        "id": tid, "events": events, "wm_states": wm_deltas(wm_states),
        "cycle_tree": _cycle_tree(events),                  # git dev-tree(좌측 패널) — cycle 노드 + substate 가지
        "grids": {"train": task["train"],
                  "test": [{"input": tp["input"]} for tp in task["test"]]},
        "candidates": candidates, "correct_attempt": correct_i, "n_steps": len(events),
    }


def _rules_manifest():
    return [{"name": p.name,
             "if": [{"id": c.id, "attr": c.attr, "val": c.value, "neg": c.negated} for c in p.conditions],
             "then": [{"id": a.id, "attr": a.attr, "val": a.value, "pref": a.pref} for a in p.actions]}
            for p in PRODUCTIONS]


def _safe_dash_data(task, tid, timeout_s=180):   # 제출 예산과 동일한 문제당 3분
    """_dash_data 를 **태스크당 타임아웃 + 예외 격리**로 감싼다. 일반 ARC-AGI 태스크는 솔버가
    가정한 구조(2 train + 1 test 등)와 달라 크래시하거나 오래 걸릴 수 있으므로, 한 태스크가
    전체 생성을 죽이지 않게 한다. 실패/초과 시 빈 이벤트 stub + ^error 필드 → 대시보드는 그
    태스크를 '무진행(n_steps=0)'으로 표시한다 (다양성 관찰이 목적이라 실패도 하나의 데이터)."""
    import signal
    class _TO(Exception):
        pass
    def _h(sig, frm):
        raise _TO()
    stub = {"id": tid, "events": [], "wm_states": [],
            "grids": {"train": task.get("train", []),
                      "test": [{"input": tp["input"]} for tp in task.get("test", [])]},
            "candidates": [], "correct_attempt": None, "n_steps": 0, "error": None}
    old = signal.signal(signal.SIGALRM, _h)
    try:
        signal.alarm(timeout_s)
        d = _dash_data(task, tid)
        signal.alarm(0)
        return d
    except _TO:
        stub["error"] = f"timeout>{timeout_s}s"
        return stub
    except Exception as e:                               # noqa: BLE001 (관찰용, 어떤 실패든 stub)
        stub["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return stub
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def make_dashboard(tasks, dataset="focus (slice 1)"):
    """tasks: [(tid, task_dict), ...] — 대시보드 TASK BROWSER 에 카드로 나열."""
    from arc.dashboard import _HTML
    if isinstance(tasks, dict):                        # 단일 태스크 하위호환: make_dashboard(task_dict)
        tasks = [("task", tasks)]
    dash = []
    for i, (tid, t) in enumerate(tasks, 1):
        d = _safe_dash_data(t, tid)
        term = "" if d["n_steps"] == 0 else ("✓풀림" if d.get("correct_attempt") is not None else "종료/중지")
        print(f"  [{i:2}/{len(tasks)}] {tid:12} n_steps={d['n_steps']:6} {d.get('error') or term}", flush=True)
        dash.append(d)
    data = {"dataset": dataset, "tasks": dash,
            "rules": _rules_manifest(), "op_docs": OP_DOCS}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_dashboard.html")
    doc = _HTML.replace("__DATA__", json.dumps(data))
    # 상단 nav 링크(고정): 생성된 per-pair program 이 anti-unify 되어 일반화되는 별도 페이지로 이동
    # (사용자 2026-07-14). 공유 _HTML 를 오염시키지 않으려 focus 출력에만 주입한다.
    nav = ('<a href="easy_antiunify_report.html" onclick="try{location.href=\'easy_antiunify_report.html#\''
           '+D.tasks[ti].id;return false}catch(e){}" style="position:fixed;top:8px;right:12px;'
           'z-index:99999;background:#243b52;color:#bcd8f5;padding:6px 12px;border-radius:7px;'
           'text-decoration:none;font:13px/1 -apple-system,sans-serif;border:1px solid #3a5a7a;'
           'box-shadow:0 2px 8px #0006">▤ 이 문제 anti-unification →</a>')
    doc = doc.replace("<body>", "<body>" + nav, 1)
    with open(out, "w") as f:
        f.write(doc)
    return out


def _load_made_and_real():
    """대시보드에 띄울 태스크: 워크스루의 made000a/b + 실제 08ed6ac7 + easy000a."""
    import glob
    from arc.dataset import list_tasks, load_task
    here = os.path.dirname(os.path.abspath(__file__))
    tasks = []
    for tid in ("made000a", "made000b"):
        p = os.path.join(here, "data", "made", f"{tid}.json")
        if os.path.exists(p):
            tasks.append((tid, load_task(p)))
    real = glob.glob(os.path.join(os.path.dirname(here), "data", "**", "08ed6ac7.json"), recursive=True)
    if real:
        tasks.append(("08ed6ac7", load_task(real[0])))
    etid, epath = list_tasks("easy_a")[0]
    tasks.append((etid, load_task(epath)))
    return tasks


def _load_survey(n_agi=20, area_cap=200, agi_ids=None, include_easy=True, include_made=True):
    """다양성 관찰용 묶음: easy 9 + made 2 + ARC-AGI 문제.
    - agi_ids 지정 시: **그 id 들 정확히** 사용(area 필터 무시) — 서브셋 재생성용.
    - 미지정 시: training 에서 **max(train grid area) ≤ area_cap** (≈≤14x14) 인 것 앞에서 n_agi 개.
      WM 정렬 병목이 격자크기 비례라 시간/크기 예산 보호. 정렬 결정적 — 재현 가능.
    목적은 풀이가 아니라 '현재 로직이 낯선 태스크에 어떻게 적용되나' 관찰(harness §2-4)."""
    import glob
    from arc.dataset import list_tasks, load_task
    here = os.path.dirname(os.path.abspath(__file__))
    tasks = []
    if include_easy:
        tasks += [(tid, load_task(p)) for tid, p in list_tasks("easy_a")]     # easy 9
    if include_made:
        for tid in ("made000a", "made000b"):                                 # made 2
            p = os.path.join(here, "data", "made", f"{tid}.json")
            if os.path.exists(p):
                tasks.append((tid, load_task(p)))
    agi_root = os.path.join(os.path.dirname(here), "data", "ARC_AGI")   # vendored (was ~/Desktop/ARC-solver)
    if agi_ids:                                                              # 명시 id 셋
        for tid in agi_ids:
            hits = glob.glob(os.path.join(agi_root, "**", f"{tid}.json"), recursive=True)
            if hits:
                tasks.append((tid, load_task(hits[0])))
        return tasks
    picked = 0                                                              # 자동 선택
    for p in sorted(glob.glob(os.path.join(agi_root, "training", "*.json"))):
        if picked >= n_agi:
            break
        t = load_task(p)
        try:
            area = max(len(g["input"]) * len(g["input"][0]) for g in t["train"])
        except Exception:                                                    # noqa: BLE001
            continue
        if area > area_cap:
            continue
        tasks.append((os.path.splitext(os.path.basename(p))[0], t))
        picked += 1
    return tasks


# 고정 관찰 세트 (사용자 지정 2026-07-09): easy 9 + made 2 + 실제 ARC-AGI 4 = 15
SURVEY_AGI = ["08ed6ac7", "0ca9ddb6", "009d5c81", "11852cab", "845d6e51", "868de0fa"]

if __name__ == "__main__":
    # 사용자 지정(2026-07-14): dashboard 에는 **easy 문제만** — per-pair program 이 존재하는 모든
    # PAIR 에 물질화되는지(N example pair → N program) easy 이동 태스크로 확인한다.
    from arc.dataset import list_tasks, load_task
    tasks = [(tid, load_task(p)) for tid, p in list_tasks("easy_a")]     # easy000a–i (9)
    print(f"easy only: {len(tasks)} 태스크 ({', '.join(t for t, _ in tasks)}) — max_cycles=1000")
    out = make_dashboard(tasks, dataset="easy_a (single-pixel) — per-pair program ×N")
    sz = os.path.getsize(out) / 1e6
    print(f"wrote {out}  ({sz:.1f} MB)")
    # companion 페이지: per-pair program → anti-unification 3분할 뷰 (nav 링크 대상)
    from arc.easy_antiunify_viz import build as _build_au
    au = _build_au()
    print(f"wrote {au}\nopen it:  open {out}")
