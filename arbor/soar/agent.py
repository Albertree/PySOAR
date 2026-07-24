"""
agent -- the full SOAR decision cycle: M1 (preference/impasse) + M2 (truth
maintenance) combined into Propose-Select-Apply with automatic substates.

Oracle reference: SoarGroup/Soar `decision_process/decide.cpp`
  - decide_context_slot (2708): run preferences -> install winner OR impasse
  - create_new_impasse (1869) / create_new_context (2536): substate + impasse WMEs
  - attribute_of_impasse (2805): NO_CHANGE with a selected operator -> ONC
    (attribute=operator); with none -> SNC (attribute=state)

This is the milestone that makes the wiki's "tie -> evaluation substate" flow
actually run: a tie installs a substate carrying ^impasse tie ^item ...; rules
in the substate can add a preference to the superstate that resolves the tie;
truth maintenance (M2) then dissolves the substate and the operator is selected.

The cycle (one ``step``):
  1. PROPOSE  : elaborate to quiescence -- i-support elaborations + operator
                proposals fire; operator preferences accumulate.
  2. DECIDE   : top-down over the goal stack, run_preference_semantics on each
                goal's collected operator slot. Winner -> install & dissolve any
                substate below. Impasse -> create/keep a substate.
  3. APPLY    : elaborate again -- operator-application rules (o-support) fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import chunk as _chunk
from .decide import ImpasseType, run_preference_semantics
from .elaborate import Elaborator
from .preference import PreferenceType as PT
from .preference import Slot
from .production import Production, is_var
from .wm import WorkingMemory

# operator preference symbol -> (unary type, binary type)
_PREF_SYMBOL = {
    "+": (PT.ACCEPTABLE, PT.ACCEPTABLE),
    "!": (PT.REQUIRE, PT.REQUIRE),
    "-": (PT.REJECT, PT.REJECT),
    "~": (PT.PROHIBIT, PT.PROHIBIT),
    "=": (PT.UNARY_INDIFFERENT, PT.BINARY_INDIFFERENT),
    ">": (PT.BEST, PT.BETTER),
    "<": (PT.WORST, PT.WORSE),
}

_IMPASSE_WORD = {
    ImpasseType.TIE: "tie",
    ImpasseType.CONFLICT: "conflict",
    ImpasseType.CONSTRAINT_FAILURE: "constraint-failure",
    ImpasseType.NO_CHANGE: "no-change",
    ImpasseType.ONC: "no-change",
    ImpasseType.SNC: "no-change",
}
_CHOICES = {
    ImpasseType.TIE: "multiple",
    ImpasseType.CONFLICT: "multiple",
    ImpasseType.CONSTRAINT_FAILURE: "none",
    ImpasseType.NO_CHANGE: "none",
    ImpasseType.ONC: "none",
    ImpasseType.SNC: "none",
}


@dataclass
class Goal:
    id: str
    level: int
    impasse: Optional[ImpasseType] = None     # impasse this goal was created for
    attribute: Optional[str] = None           # "operator" | "state"
    selected: Optional[Any] = None            # currently selected operator value
    last_signature: Any = None                # for ONC detection


@dataclass
class StepResult:
    cycle: int
    decisions: list = field(default_factory=list)   # human-readable trace


class Agent:
    def __init__(self, productions: list[Production], top: str = "S1",
                 learn: bool = False, operator_bodies: dict | None = None,
                 record: bool = False, io: bool = False) -> None:
        self.wm = WorkingMemory()
        self.prods = productions
        self.elaborator = Elaborator(productions)
        self.stack: list[Goal] = []
        self._next = 2  # S2, S3, ...
        self._hnext = 1  # H1, H2, ... (hypothesis space — 일반 substate 와 구분되는 별도 공간)
        self.learn = learn
        self.chunks: list[Production] = []
        self._chunk_sigs: set = set()
        # computed operators: name -> apply(agent) callable. This is the generic
        # SOAR "operator application via external function" hook (RHS funcs / I/O
        # in real Soar). The decision cycle stays pure; only the apply is Python.
        self.operator_bodies: dict = operator_bodies or {}
        # per-cycle trace for the debugger (opt-in)
        self.recording: bool = record
        self.trace: list = []
        # SOAR I/O (io_link.cpp): ^io.input-link / output-link, input functions run
        # at the INPUT phase, input WMEs maintained by I/O (not retracted).
        self.input_functions: list = []
        self.input_wmes: set = set()
        self._init_top(top)
        if io:
            self._init_io()

    # -- SOAR I/O (faithful to interface/io_link.cpp) ------------------------
    def _init_io(self) -> None:
        """Create the io structure on the top state (do_input_cycle, top created)."""
        self.wm.add("S1", "io", "I1")
        self.add_input_wme("I1", "input-link", "I2")
        self.add_input_wme("I1", "output-link", "I3")

    def add_input_wme(self, ident, attr, value):
        """Add an input WME (io_link.cpp:add_input_wme). Maintained by the I/O
        system -- it is a base WME, never retracted by truth maintenance; the
        environment removes/updates it explicitly."""
        self.wm.add(ident, attr, value)
        self.input_wmes.add((ident, attr, value))
        return (ident, attr, value)

    def remove_input_wme(self, ident, attr, value) -> None:
        self.wm.remove(ident, attr, value)
        self.input_wmes.discard((ident, attr, value))

    def add_output_wme(self, attr, value):
        """Write to ^io.output-link (read by the environment at OUTPUT phase)."""
        self.wm.add("I3", attr, value)
        return ("I3", attr, value)

    def _do_input_phase(self) -> None:
        """INPUT phase: invoke registered input functions (do_input_cycle)."""
        for fn in self.input_functions:
            fn(self)

    def _record(self, wm_before, ers, goal, slot, imp, cands, selected) -> None:
        """Capture one decision cycle for the web debugger. ``ers`` is the list
        of ElaborationResults from this cycle's propose + apply settles."""
        from .preference import SYMBOL_TO_TYPE
        type_to_sym = {v: k for k, v in SYMBOL_TO_TYPE.items()}
        wm_after = set(self.wm)
        fired = sorted({k[0] for er in ers for k in er.fired})
        retracted = sorted({k[0] for er in ers for k in er.retracted})
        props: dict = {}
        for plist in slot.preferences.values():
            for p in plist:
                sym = type_to_sym.get(p.ptype, p.ptype.name)
                props.setdefault(p.value, []).append(
                    sym if p.referent is None else f"{sym} {p.referent}")
        self.trace.append({
            "cycle": len(self.trace) + 1,
            "fired": fired,
            "retracted": retracted,
            "proposed": [{"op": str(op), "prefs": pr} for op, pr in props.items()],
            "goal": goal.id,
            "impasse": imp.name,
            "candidates": [str(c) for c in cands],
            "selected": str(selected) if selected is not None else None,
            "wm_before": sorted(f"({i} ^{a} {v})" for (i, a, v) in wm_before),
            "wm_after": sorted(f"({i} ^{a} {v})" for (i, a, v) in wm_after),
            "wm_added": sorted(f"({i} ^{a} {v})" for (i, a, v) in (wm_after - wm_before)),
            "wm_removed": sorted(f"({i} ^{a} {v})" for (i, a, v) in (wm_before - wm_after)),
        })

    def _init_top(self, top: str) -> None:
        self.wm.mark_goal(top, level=1)
        self.wm.add(top, "type", "state")
        self.wm.add(top, "superstate", "nil")
        self.stack.append(Goal(top, 1))

    # -- operator preference collection -------------------------------------
    def _bind(self, elem: Any, binding: dict) -> Any:
        return binding.get(elem, elem) if is_var(elem) else elem

    def collect_operator_prefs(self, gid: str) -> Slot:
        """Build the operator slot for a goal from the currently-active
        instantiations (the truth-maintained set). Operator proposals are always
        i-supported, so the active set IS the current preference set."""
        slot = Slot()
        for inst in self.elaborator.active.values():
            for a in inst.prod.actions:
                if a.attr != "operator":
                    continue
                idv = self._bind(a.id, inst.binding)
                if idv != gid:
                    continue
                value = self._bind(a.value, inst.binding)
                ref = self._bind(a.referent, inst.binding) if a.referent is not None else None
                unary_t, binary_t = _PREF_SYMBOL[a.pref]
                ptype = binary_t if ref is not None else unary_t
                slot.add_pref(ptype, value, ref)
        return slot

    # -- substate management -------------------------------------------------
    def _new_state_id(self) -> str:
        sid = f"S{self._next}"
        self._next += 1
        return sid

    def create_substate(self, parent: Goal, imp: ImpasseType, attribute: str,
                        items: list) -> Goal:
        sid = self._new_state_id()
        level = parent.level + 1
        self.wm.mark_goal(sid, level)
        # architecture-installed impasse WMEs (create_new_impasse, cpp:1877-1962)
        self.wm.add(sid, "type", "state")
        self.wm.add(sid, "superstate", parent.id)
        self.wm.add(sid, "impasse", _IMPASSE_WORD[imp])
        self.wm.add(sid, "choices", _CHOICES[imp])
        self.wm.add(sid, "attribute", attribute)
        self.wm.add(sid, "quiescence", "t")           # create_new_context, cpp:2549
        for it in items:                               # update_impasse_items, cpp:1987
            self.wm.add(sid, "item", it)
        if items:
            self.wm.add(sid, "item-count", len(items))
        sub = Goal(sid, level, impasse=imp, attribute=attribute)
        self.stack.append(sub)
        return sub

    def create_hspace(self, parent: Goal, for_level: str) -> Goal:
        """**가설공간(H-space)** 생성 — 일반 substate(impasse) 와 구분되는 별도 공간. id 는 H1,H2,…
        기본 WME 도 다르다(impasse/choices 없음): hypothesize logic 이 가설을 조합·검증하는 scratch.
        실제 ARCKG WM 은 건드리지 않는다 — 이 공간 안에서만 synthesize DSL operator 가 돈다."""
        hid = f"H{self._hnext}"
        self._hnext += 1
        level = parent.level + 1
        self.wm.mark_goal(hid, level)
        self.wm.add(hid, "type", "hypothesis-space")   # ← 일반 state('state')와 다른 표기
        self.wm.add(hid, "superstate", parent.id)
        self.wm.add(hid, "for", for_level)             # 어느 계층의 가설을 세우나 (GRID/OBJECT/PIXEL)
        self.wm.add(hid, "synthesize", "yes")          # synthesize operator 발화 씨앗
        sub = Goal(hid, level, impasse=None, attribute="hypothesis")
        self.stack.append(sub)
        return sub

    def remove_substates_below(self, index: int) -> None:
        """Dissolve all substates deeper than stack[index]."""
        while len(self.stack) > index + 1:
            g = self.stack.pop()
            self._purge_state(g.id)

    def _purge_state(self, sid: str) -> None:
        for (i, a, v) in list(self.wm):
            if i == sid:
                self.wm.remove(i, a, v)
        # also clear any operator selection WME on it
        self.wm._goals.discard(sid)  # noqa: SLF001

    def _update_items(self, sub: Goal, items: list) -> None:
        for a in ("item", "item-count"):
            for (i, aa, v) in list(self.wm.matching(identifier=sub.id, attr=a)):
                self.wm.remove(i, aa, v)
        for it in items:
            self.wm.add(sub.id, "item", it)
        if items:
            self.wm.add(sub.id, "item-count", len(items))

    # -- operator install ----------------------------------------------------
    def _install_operator(self, goal: Goal, op: Any) -> None:
        # remove old selection (remove_wmes_for_context_slot, cpp:2780)
        if goal.selected is not None and goal.selected != op:
            self.wm.remove(goal.id, "operator", goal.selected)
        self.wm.add(goal.id, "operator", op)
        goal.selected = op

    def _clear_operator(self, goal: Goal) -> None:
        if goal.selected is not None:
            self.wm.remove(goal.id, "operator", goal.selected)
            goal.selected = None

    def operator_name(self, op: Any) -> Any:
        """The ^name of an operator OBJECT (SOAR style), or ``op`` itself when it
        is a bare-symbol operator with no ^name augmentation."""
        for (_i, _a, v) in self.wm.matching(identifier=op, attr="name"):
            return v
        return op

    def body_for(self, op: Any):
        """The application body (RHS function) for a selected operator: matched by
        value (bare-symbol operator) or, failing that, by its ^name (operator
        object). Returns None if no body is registered (apply is rule-driven)."""
        return self.operator_bodies.get(op) or self.operator_bodies.get(self.operator_name(op))

    # -- the cycle -----------------------------------------------------------
    def step(self) -> StepResult:
        """Run one decision cycle. Returns a StepResult with a small trace.

        Soar decides context slots top-down; the lowest goal whose operator slot
        is *decidable* is where the decision (selection or impasse) happens. A
        goal whose selected operator is still a valid candidate is NOT decidable
        -- the selection persists (it does not re-tie). If every goal is decided
        and the bottom one holds a selected operator with nothing left to do,
        that is an operator no-change impasse (oracle D3 in the tie-resolve run).
        """
        res = StepResult(cycle=0)
        # 0. INPUT phase: environment input functions add WMEs to ^io.input-link
        self._do_input_phase()
        wm_before = set(self.wm) if self.recording else None

        # 1. PROPOSE: elaborate to quiescence (also applies o-support rules)
        er = self.elaborator.settle(self.wm)
        if self.learn:
            self._learn_chunks()

        # 2. DECIDE: top-down over the goal stack
        for i, goal in enumerate(list(self.stack)):
            slot = self.collect_operator_prefs(goal.id)

            # slot not decidable: a still-valid selection persists (no re-tie)
            if goal.selected is not None:
                if self._selection_valid(goal.selected, slot):
                    continue
                self._clear_operator(goal)  # selection lost support -> reconsider

            imp, cands = run_preference_semantics(slot)

            if imp is ImpasseType.NONE and len(cands) == 1:
                # winner -> dissolve any substate below, install, apply
                if i < len(self.stack) - 1:
                    self.remove_substates_below(i)
                self._install_operator(goal, cands[0])
                res.decisions.append(("select", goal.id, cands[0]))
                # 3. APPLY -- a computed operator body runs here (external
                #    application), then elaboration propagates its WM changes.
                body = self.body_for(cands[0])
                if body is not None:
                    body(self)
                er2 = self.elaborator.settle(self.wm)
                if self.recording:
                    self._record(wm_before, [er, er2], goal, slot, imp, cands, cands[0])
                return res

            # impasse at this goal
            if imp is ImpasseType.NONE:                       # 0 candidates
                actual, attr, items = (*self._no_change_kind(goal), [])
            else:                                             # tie/conflict/cf
                actual, attr, items = imp, "operator", list(cands)

            # if a same-type+attr substate already exists below, this goal is
            # already impassed -> refresh its ^item set and decide deeper
            # (this is what produces Soar's no-change cascade S4>S5>S6...).
            if i < len(self.stack) - 1 and self._substate_matches(i + 1, actual, attr):
                self._update_items(self.stack[i + 1], items)
                continue

            if i < len(self.stack) - 1:
                self.remove_substates_below(i)   # wrong-type substate -> replace
            self.create_substate(goal, actual, attr, items)
            label = attr_word(attr) if actual in (ImpasseType.ONC, ImpasseType.SNC) \
                else _IMPASSE_WORD[actual]
            res.decisions.append((label, goal.id, items) if items else (label, goal.id))
            return res

        # 2b. all goals decided & valid; bottom holds a selected operator and
        #     nothing else is decidable -> operator no-change (cpp ONC, oracle D3).
        bottom = self.stack[-1]
        if bottom.selected is not None:
            self.create_substate(bottom, ImpasseType.ONC, "operator", [])
            res.decisions.append(("operator-no-change", bottom.id))
        return res

    def _substate_matches(self, index: int, imp: ImpasseType, attr: str) -> bool:
        """True if stack[index] is a substate for the same impasse word + attr."""
        if index >= len(self.stack):
            return False
        sub = self.stack[index]
        return (sub.impasse is not None
                and _IMPASSE_WORD[sub.impasse] == _IMPASSE_WORD[imp]
                and sub.attribute == attr)

    def _is_bottom(self, index: int) -> bool:
        return index == len(self.stack) - 1

    def _selection_valid(self, op: Any, slot: Slot) -> bool:
        """A selected operator stays selected while it remains a candidate:
        still acceptable/required and not rejected/prohibited."""
        accept = ({p.value for p in slot.get(PT.ACCEPTABLE)}
                  | {p.value for p in slot.get(PT.REQUIRE)})
        blocked = ({p.value for p in slot.get(PT.REJECT)}
                   | {p.value for p in slot.get(PT.PROHIBIT)})
        return op in accept and op not in blocked

    def _no_change_kind(self, goal: Goal) -> tuple[ImpasseType, str]:
        # attribute_of_impasse (cpp:2805): operator selected -> ONC, else SNC
        if goal.selected is not None:
            return ImpasseType.ONC, "operator"
        return ImpasseType.SNC, "state"

    # -- chunking (M4) -------------------------------------------------------
    def _level_of(self, sym: Any) -> int:
        """Goal level of an identifier; non-goal symbols default to 0 (ground).
        Sufficient for goal-rooted conditions (the ARC/ARBOR pattern)."""
        return self.wm._level.get(sym, 0)  # noqa: SLF001

    def _provenance(self) -> dict:
        """Map each i-supported (non-operator) WME to the active instantiation
        that produced it -- used to recurse through locals while backtracing."""
        prov: dict = {}
        for inst in self.elaborator.active.values():
            if inst.o_supported:
                continue
            for (i, a, v, pref) in inst.results:
                if a != "operator" and pref == "+":
                    prov.setdefault((i, a, v), inst)
        return prov

    def _chunk_sig(self, ch: Production):
        conds = tuple(sorted((str(c.id), c.attr, str(c.value)) for c in ch.conditions))
        a = ch.actions[0]
        return (conds, (str(a.id), a.attr, str(a.value), a.pref, str(a.referent)))

    def _learn_chunks(self) -> list:
        """Detect results in the current match set and build chunks for them
        (get_results_for_instantiation + backtrace, ebc_build.cpp:218)."""
        prov = self._provenance()
        learned: list = []
        for inst in list(self.elaborator.active.values()):
            ml = _chunk.match_goal_level(inst, self._level_of)
            for action, triple in _chunk._result_actions(inst, ml, self._level_of):
                superstate_level = self._level_of(triple[0])
                grounds = _chunk.backtrace(inst, superstate_level, prov, self._level_of)
                if not grounds:
                    continue  # nothing operational to test on (e.g. needs
                              # architectural impasse-item backtrace -- not yet)
                ch = _chunk.build_chunk(
                    f"chunk{len(self.chunks) + len(learned) + 1}",
                    grounds, action, inst.binding)
                sig = self._chunk_sig(ch)
                if sig in self._chunk_sigs:
                    continue
                self._chunk_sigs.add(sig)
                learned.append(ch)
        for ch in learned:
            self.chunks.append(ch)
            self.prods.append(ch)
            self.elaborator.productions.append(ch)
        return learned

    # -- convenience ---------------------------------------------------------
    def run(self, max_cycles: int = 50) -> list:
        trace = []
        for _ in range(max_cycles):
            before = (len(self.wm), tuple(g.id for g in self.stack),
                      tuple(g.selected for g in self.stack))
            res = self.step()
            trace.extend(res.decisions)
            after = (len(self.wm), tuple(g.id for g in self.stack),
                     tuple(g.selected for g in self.stack))
            if before == after and not res.decisions:
                break
        return trace

    def state_augs(self, sid: str = "S1") -> dict:
        augs: dict = {}
        for (i, a, v) in self.wm:
            if i == sid:
                augs.setdefault(a, set()).add(v)
        return augs


def attr_word(attr: str) -> str:
    return "operator-no-change" if attr == "operator" else "state-no-change"
