"""
elaborate -- instantiations, o-support calculation, and the truth-maintaining
elaboration loop (assert / retract to quiescence).

Oracle reference:
  - o-support:   `soar_representation/instantiation.cpp:545`
                 calculate_support_for_instantiation_preferences
  - retraction:  `soar_representation/instantiation.cpp:1412` retract_instantiation
                 ("retract any preferences that are in TM and aren't o-supported")

This is the milestone-2 fidelity core. The bug class it fixes: i-supported WMEs
that should vanish when their support disappears, but linger (ghost WMEs) -- and
its dual, o-supported results that should persist but get wrongly retracted. The
previous ARC ports had no support typing at all, so neither behaviour existed.

Key invariant (Soar truth maintenance):
  * i-support  : a WME exists iff at least one currently-matching instantiation
                 asserts it. Lose the support -> the WME is retracted, same
                 elaboration phase, before quiescence.
  * o-support  : once asserted, the WME persists independently of its creating
                 instantiation; only an explicit reject ('-') removes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .production import Action, Production, Support, is_var
from .wm import Triple, WorkingMemory


@dataclass
class Instantiation:
    prod: Production
    binding: dict
    matched: frozenset            # positive condition WMEs (the support set)
    o_supported: bool = False
    results: list[tuple] = field(default_factory=list)  # (id, attr, value, pref)

    @property
    def key(self) -> tuple:
        # identity = production + exact set of matched WMEs (Soar: one
        # instantiation per distinct match). Two firings with the same bindings
        # but different support WMEs are different instantiations.
        return (self.prod.name, self.matched)


def _bind(elem: Any, binding: dict) -> Any:
    return binding.get(elem, elem) if is_var(elem) else elem


def instantiate(prod: Production, binding: dict, matched: frozenset,
                wm: WorkingMemory, gensym=None) -> Instantiation:
    # RHS variables not bound by the LHS get a fresh identifier (Soar gensym: a
    # rule that builds a new object, e.g. (<o> ^name observe), mints a new id O1
    # for <o>). ``gensym`` is the elaborator's allocator -- it returns the SAME id
    # for the same (production, matched, var), so the WME stays stable across
    # settle rounds (no i-support churn). None -> no minting (bare-symbol rules).
    if gensym is not None:
        extra = None
        for a in prod.actions:
            for elem in (a.id, a.value):
                if is_var(elem) and elem not in binding:
                    if extra is None:
                        extra = dict(binding)
                    if elem not in extra:
                        extra[elem] = gensym(prod.name, matched, elem)
        if extra is not None:
            binding = extra
    results = [
        (_bind(a.id, binding), a.attr, _bind(a.value, binding), a.pref)
        for a in prod.actions
    ]
    inst = Instantiation(prod, binding, matched, results=results)
    inst.o_supported = calculate_o_support(prod, binding, matched, wm)
    return inst


def calculate_o_support(prod: Production, binding: dict, matched: frozenset,
                        wm: WorkingMemory) -> bool:
    """Faithful port of calculate_support_for_instantiation_preferences
    (instantiation.cpp:545). Returns True if the instantiation's results are
    o-supported (persistent), False if i-supported (truth-maintained)."""

    # declared support short-circuits (cpp:559)
    if prod.support is Support.O_SUPPORT:
        return True
    if prod.support is Support.I_SUPPORT:
        return False

    # --- undeclared: the architecture decides (cpp:567) ---

    # (1) Is this instantiation PROPOSING an operator? i.e. an action
    #     (<state> ^operator <o> +) whose id is a goal/state. -> i-support (cpp:571)
    for a in prod.actions:
        if a.attr == "operator" and a.pref == "+":
            idv = _bind(a.id, binding)
            if wm.is_goal(idv):
                return False

    # (2) Otherwise, is the *selected* operator tested on the LHS? Find the
    #     lowest goal among condition WMEs (cpp:623), then look for a condition
    #     (<lowest-goal> ^operator <x>) that is NOT an acceptable preference --
    #     i.e. the operator actually selected for that state. (cpp:647)
    goal_wmes = [w for w in matched if wm.is_goal(w[0])]
    if not goal_wmes:
        return False
    lowest = max(goal_wmes, key=lambda w: wm.goal_level(w[0]))
    op_conds = [w for w in matched if w[0] == lowest[0] and w[1] == "operator"]
    if not op_conds:
        return False

    # (3) op-elab vs application (cpp:649): if every RHS action only elaborates
    #     the operator value, it's an operator *elaboration* -> i-support. If any
    #     action targets something else, it's an application -> o-support. Mixed
    #     -> i-support (cpp:681 warning path).
    op_value = op_conds[0][2]
    o_support = False
    op_elab = False
    for a in prod.actions:
        idv = _bind(a.id, binding)
        if idv == op_value:
            op_elab = True
        else:
            o_support = True
    if o_support and op_elab:
        return False  # mixed elaboration+application -> i-support
    return o_support


# --------------------------------------------------------------------------
# Elaboration to quiescence with truth maintenance.
# --------------------------------------------------------------------------
@dataclass
class ElaborationResult:
    rounds: int
    quiescent: bool
    active: dict           # key -> Instantiation currently in the match set
    fired: list            # keys fired this settle
    retracted: list        # keys retracted this settle


class Elaborator:
    """A persistent elaboration engine over a fixed production set.

    State (match set, o-support set, materialized WMEs) MUST persist across
    settles -- in Soar the elaboration phase is continuous truth maintenance,
    not a fresh computation each time. Removing a base WME and re-settling the
    SAME elaborator is what triggers retraction of everything that depended on
    it. (A fresh elaborator each call cannot know which WMEs it had derived, so
    it could not retract them -- that was the first-cut bug.)
    """

    def __init__(self, productions: list[Production]) -> None:
        self.productions = productions
        self.active: dict[tuple, Instantiation] = {}
        self.o_support_wmes: set[Triple] = set()  # persistent (survive retraction)
        self.engine_added: set[Triple] = set()    # WMEs we materialized (retractable)
        self._gensym: dict[tuple, str] = {}        # (prod, matched, var) -> minted id
        self._gensym_n = 0

    def _gensym_id(self, prod_name: str, matched: frozenset, var: str) -> str:
        """Mint/return a stable identifier for an unbound RHS variable (O1, O2,
        ...). Keyed by the instantiation so it is constant across settle rounds."""
        k = (prod_name, matched, var)
        if k not in self._gensym:
            self._gensym_n += 1
            self._gensym[k] = f"O{self._gensym_n}"
        return self._gensym[k]

    def settle(self, wm: WorkingMemory, max_rounds: int = 200) -> ElaborationResult:
        """Run elaboration to quiescence against the current WM."""
        from .production import match

        fired_all: list = []
        retracted_all: list = []

        for rnd in range(1, max_rounds + 1):
            # 1. recompute desired instantiation set from current WM
            desired: dict[tuple, Instantiation] = {}
            for prod in self.productions:
                for binding, matched in match(prod, wm):
                    inst = instantiate(prod, binding, matched, wm, gensym=self._gensym_id)
                    desired[inst.key] = inst

            new_keys = [k for k in desired if k not in self.active]
            gone_keys = [k for k in self.active if k not in desired]

            # 2. explicit removals ('-') from currently-matching instantiations.
            #    A reject deletes the WME (including o-supported ones).
            # NOTE: actions on the operator context slot (attr == "operator") are
            # PREFERENCES, not WMEs -- they are collected by the decision phase
            # (M3, agent.py) and routed through run_preference_semantics, never
            # materialized here. Only the architecture installs the *selected*
            # operator WME.
            removed_now: set[Triple] = set()
            for inst in desired.values():
                for (i, a, v, pref) in inst.results:
                    if a == "operator":
                        continue
                    if pref == "-":
                        removed_now.add((i, a, v))

            # 3. retract gone instantiations (their i-supported results drop in
            #    the reconcile below; o-supported results were copied to the
            #    persistent o_support set when they fired -- cpp:1431).
            for k in gone_keys:
                retracted_all.append(k)
                self.active.pop(k)

            # 4. fire new instantiations
            for k in new_keys:
                fired_all.append(k)
                self.active[k] = desired[k]
                if desired[k].o_supported:
                    for (i, a, v, pref) in desired[k].results:
                        if a != "operator" and pref == "+":
                            self.o_support_wmes.add((i, a, v))

            # 5. i-supported present-set = union of '+' results over ALL active
            #    i-supported instantiations.
            i_support_now: set[Triple] = set()
            for inst in self.active.values():
                if inst.o_supported:
                    continue
                for (i, a, v, pref) in inst.results:
                    if a != "operator" and pref == "+":
                        i_support_now.add((i, a, v))

            self.o_support_wmes -= removed_now
            supported = (i_support_now | self.o_support_wmes) - removed_now

            # 6. reconcile WM -- retraction happens here. We add/remove only
            #    WMEs the engine materialized; base WMEs are protected unless
            #    explicitly rejected.
            changed = False
            for t in supported:
                if not wm.contains(*t):
                    wm.add(*t)
                    changed = True
                self.engine_added.add(t)
            for t in list(self.engine_added):
                if t not in supported:
                    if wm.remove(*t):
                        changed = True
                    self.engine_added.discard(t)
            for t in removed_now:
                if wm.remove(*t):
                    changed = True
                self.engine_added.discard(t)
                self.o_support_wmes.discard(t)

            if not new_keys and not gone_keys and not changed:
                return ElaborationResult(rnd, True, self.active, fired_all, retracted_all)

        return ElaborationResult(max_rounds, False, self.active, fired_all, retracted_all)


def elaborate_to_quiescence(wm: WorkingMemory, productions: list[Production],
                            max_rounds: int = 200) -> ElaborationResult:
    """One-shot convenience: fresh Elaborator, single settle. For scenarios that
    remove support and re-settle, use a persistent ``Elaborator`` instead."""
    return Elaborator(productions).settle(wm, max_rounds)
