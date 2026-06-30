"""
chunk -- explanation-based chunking (backtracing) for PySOAR.

Oracle reference: SoarGroup/Soar `explanation_based_chunking/`
  - get_results_for_instantiation (ebc_build.cpp:218): a preference is a RESULT
    if its identifier's level is ABOVE (less than) the firing instantiation's
    match goal level -- i.e. it lands on a superstate.
  - backtrace_through_instantiation (ebc_backtrace.cpp:104): scan the result
    instantiation's conditions; a condition matching a WME at or above the goal
    level is a GROUND (-> chunk LHS), otherwise it is a LOCAL and we recurse into
    the instantiation that produced that WME (until everything bottoms out at
    grounds). Architectural substate WMEs (^impasse/^superstate/...) have no
    producing instantiation and contribute nothing.

The chunk: LHS = variablized grounds, RHS = variablized result. Variablization
follows the original instantiation -- a symbol matched by a VARIABLE in the
source production variablizes (consistently, same WM symbol -> same chunk var);
a constant stays constant. This reproduces Soar's learned rule, e.g.

    (state <s1> ^a <a1> ^b <b1>) --> (<s1> ^result computed)

The full EBC (identity graph, NCC handling, constraint repair) is out of scope;
this is the backtracing core that the ARC/ARBOR work needs (and the seam where
anti-unification will later replace exact variablization). NOTE: negated
conditions in the backtraced rules are not yet carried into chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .elaborate import Instantiation
from .production import Action, Cond, Production, Support, is_var

# attributes the architecture installs on a substate (no producing instantiation)
ARCHITECTURAL_ATTRS = frozenset({
    "type", "superstate", "impasse", "choices", "attribute",
    "quiescence", "item", "item-count",
})


@dataclass
class _GroundCond:
    """A backtraced ground condition, carrying var/const provenance."""
    id_sym: Any
    id_var: bool
    attr: str
    val_sym: Any
    val_var: bool


def _bind(elem: Any, binding: dict) -> Any:
    return binding.get(elem, elem) if is_var(elem) else elem


def _cond_wmes(inst: Instantiation):
    """Yield (Cond, matched_triple) for each positive condition of inst."""
    for c in inst.prod._pos:
        i = _bind(c.id, inst.binding)
        v = _bind(c.value, inst.binding)
        yield c, (i, c.attr, v)


def _result_actions(inst: Instantiation, match_level: int, level_of):
    """Yield (Action, bound_triple) for actions that land on a superstate
    (id level < this instantiation's match goal level) -- i.e. results."""
    for a in inst.prod.actions:
        i = _bind(a.id, inst.binding)
        if level_of(i) < match_level:
            v = _bind(a.value, inst.binding)
            yield a, (i, a.attr, v)


def match_goal_level(inst: Instantiation, level_of) -> int:
    """The deepest goal the instantiation touches = where it 'fired'."""
    lvls = [level_of(i) for (i, _, _) in inst.matched]
    return max(lvls) if lvls else 0


def backtrace(result_inst: Instantiation, superstate_level: int,
              provenance: dict, level_of) -> list[_GroundCond]:
    """Collect ground conditions for the chunk by backtracing from the result
    instantiation (ebc_backtrace.cpp:104)."""
    grounds: list[_GroundCond] = []
    seen_inst: set[int] = set()
    seen_ground: set = set()
    stack = [result_inst]
    while stack:
        inst = stack.pop()
        if id(inst) in seen_inst:
            continue
        seen_inst.add(id(inst))
        for cond, (i, a, v) in _cond_wmes(inst):
            if level_of(i) <= superstate_level:
                key = (i, a, v)
                if key in seen_ground:
                    continue
                seen_ground.add(key)
                grounds.append(_GroundCond(i, is_var(cond.id), a, v, is_var(cond.value)))
            else:
                # local: architectural -> drop; else recurse into its producer
                if a in ARCHITECTURAL_ATTRS:
                    continue
                producer = provenance.get((i, a, v))
                if producer is not None:
                    stack.append(producer)
    return grounds


class _Variablizer:
    def __init__(self) -> None:
        self.map: dict[Any, str] = {}
        self._n = 1

    def vz(self, sym: Any, was_var: bool) -> Any:
        if not was_var:
            return sym                      # constant stays constant
        if sym not in self.map:
            self.map[sym] = f"<v{self._n}>"
            self._n += 1
        return self.map[sym]


def build_chunk(name: str, grounds: list[_GroundCond], result_action: Action,
                binding: dict, support: Support = Support.UNDECLARED) -> Production:
    """Variablize grounds + result into a new production (the chunk)."""
    vz = _Variablizer()
    conds = []
    for g in grounds:
        conds.append(Cond(vz.vz(g.id_sym, g.id_var), g.attr, vz.vz(g.val_sym, g.val_var)))
    ref = None
    if result_action.referent is not None:
        ref = vz.vz(_bind(result_action.referent, binding), is_var(result_action.referent))
    action = Action(
        vz.vz(_bind(result_action.id, binding), is_var(result_action.id)),
        result_action.attr,
        vz.vz(_bind(result_action.value, binding), is_var(result_action.value)),
        result_action.pref,
        ref,
    )
    return Production(name, conds, [action], support=support)
