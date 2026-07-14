# -*- coding: utf-8 -*-
"""ARBOR agent.focus — ARBOR 에이전트 조립: 지각 주입(inject_focus)
+ SOAR 에이전트 셋업(setup_focus_agent). PRODUCTIONS/OPERATOR_BODIES 는 procedural memory 에서."""
from __future__ import annotations
import json, os, sys
from pysoar import Agent
from procedural_memory.loader import PRODUCTIONS
from procedural_memory.operators import OPERATOR_BODIES
from arbor.perception.nav import index_arckg
from arc.expr_solver import build_arckg


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
