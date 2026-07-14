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

from soar import Agent, Cond, Action, Production          # noqa: E402
from arc.expr_solver import build_arckg, _load_value, _tup   # noqa: E402 (reuse, read-only)
from procedural_memory.operators import OPERATOR_BODIES  # 분리된 operator bodies
from procedural_memory.loader import PRODUCTIONS, OP_DOCS  # JSON 실물 규칙
from arbor.agent.focus import inject_focus, setup_focus_agent
from arbor.env.survey import _load_made_and_real, _load_survey, SURVEY_AGI
from debugger.build import (_cycle_tree, _dash_data, _rules_manifest, _safe_dash_data, make_dashboard)  # facade

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












# ---------------------------------------------------------------------------
# input + agent setup (mirrors expr_solver.setup_arc_agent shape so the tracer reuses it)
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------














# 고정 관찰 세트 (사용자 지정 2026-07-09): easy 9 + made 2 + 실제 ARC-AGI 4 = 15

