"""
fine_trace -- break the PySOAR solving process into ATOMIC steps: every single
change in the whole system is its own step, so the cycle structure
(input -> propose -> decide -> apply -> output, with elaboration rounds inside
propose/apply and substates on impasse) is visible one change at a time.

Event kinds (each = one navigable step):
  phase        : a phase begins (input/propose/decide/apply/output)
  rule-fire    : one production fired (elaboration)
  rule-retract : one production retracted (truth maintenance)
  wme-add      : one WME entered working memory
  wme-remove   : one WME left working memory
  op-propose   : one operator was proposed (with its preference)
  decide       : preference resolution result (impasse type + candidates)
  op-select    : the operator was selected
  op-apply     : the operator body ran (ARCKG/DSL work attached)
  quiescence   : elaboration reached a fixpoint
  substate     : a substate was created / removed (impasse)
  output       : the answer was emitted

This drives the SAME agent pieces the solver uses (settle round-by-round,
collect_operator_prefs, run_preference_semantics, operator bodies), so the trace
reflects the real cycle -- just at the finest grain.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent  # noqa: E402
from pysoar.decide import run_preference_semantics  # noqa: E402
from pysoar.preference import SYMBOL_TO_TYPE, PreferenceType  # noqa: E402
from arc.expr_solver import PRODUCTIONS, OPERATOR_BODIES  # noqa: E402
from arc.dashboard import _kg_detail  # noqa: E402

_TYPE_TO_SYM = {v: k for k, v in SYMBOL_TO_TYPE.items()}


def _wstr(t):
    """Format a WME triple for the trace. A grid/array value (the compose ^answer,
    or ARCKG ^contents/^shape) is abbreviated to its SHAPE so the cycle-map row
    stays short -- the WM panel renders the grid itself. Other over-long scalar
    values are truncated with an ellipsis."""
    v = t[2]
    if isinstance(v, (tuple, list)):
        vs = (f"⟨{len(v)}×{len(v[0])} grid⟩"
              if v and isinstance(v[0], (tuple, list)) else f"⟨{len(v)} items⟩")
    else:
        vs = str(v)
        if len(vs) > 44:
            vs = vs[:44] + "…"
    return f"({t[0]} ^{t[1]} {vs})"


class _Tracer:
    def __init__(self, task, tid="0a"):
        from arc.expr_solver import setup_arc_agent
        self.ag = setup_arc_agent(task, tid)   # io + inject_task input function
        self.events = []
        self.cycle = 0
        self._cands: set = set()               # materialised ^operator + WMEs

    def _wm(self):
        # structured triples (so the dashboard can build the ARCKG tree)
        return sorted([list(t) for t in self.ag.wm],
                      key=lambda t: (str(t[0]), str(t[1]), str(t[2])))

    def emit(self, phase, kind, label, highlight=None, detail=None, rule=None, wave=None):
        self.events.append({
            "seq": len(self.events), "phase": phase, "kind": kind, "label": label,
            "cycle": self.cycle, "wave": wave, "highlight": highlight or [],
            "wm": self._wm(), "goal_stack": [g.id for g in self.ag.stack],
            "detail": detail, "rule": rule,   # the responsible rule / operator
        })

    def _sync_candidates(self):
        """Keep the acceptable-preference WMEs (goal ^operator <o> +) in sync with
        the proposals after a settle round, so a CANDIDATE operator appears in WM
        as part of the SAME firing that created its object (<o> ^name ...), and
        disappears the moment its proposal retracts. (SOAR acceptable_preference_
        wmes; the PySOAR kernel keeps the preferences in the Slot, so we mirror
        them here for the trace.)"""
        goal = self.ag.stack[-1]
        want = {(goal.id, "operator", f"{op} +")
                for op in self._acceptable_values(self.ag.collect_operator_prefs(goal.id))}
        for w in want - self._cands:
            self.ag.wm.add(*w)
        for w in self._cands - want:
            if self.ag.wm.contains(*w):
                self.ag.wm.remove(*w)
        self._cands = want

    # -- one elaboration phase, split into atomic MATCH / FIRE / WM-UPDATE -----
    # Each elaboration WAVE (= one settle round) is shown as up to three atomic
    # sub-steps, mirroring the Soar micro-structure (run_soar.cpp PROPOSE loop:
    # do_preference_phase = fire, do_working_memory_phase = wm-update, with the
    # match set kept current by the matcher):
    #   MATCH     -- recompute which instantiations now satisfy their LHS (pending
    #                fire) / lost their match (pending retract). WM is UNCHANGED
    #                here -- matching only READS wm. (In Soar the Rete net keeps
    #                this current incrementally; PySOAR re-matches naively, same
    #                result at quiescence -- see wiki [[rete-network]].)
    #   FIRE      -- each matched instantiation fires, producing PREFERENCES
    #                (e.g. (S1 ^operator O1 +), (O1 ^name observe)). Still NO wm
    #                change: a fired preference is not yet a WME.
    #   WM-UPDATE -- the preferences are materialised into wm (settle reconcile +
    #                _sync_candidates mirrors the acceptable +'s). THIS is where wm
    #                actually changes (green add / red remove). The NEXT wave's
    #                MATCH runs against this new wm.
    # Because MATCH/FIRE are emitted BEFORE settle and WM-UPDATE after, each step's
    # wm snapshot is automatically correct: wm changes exactly at the wm-update.
    def _pref_str(self, r):
        """Render one RHS result (id, attr, value, pref) as the preference it
        produces -- operator-slot results keep their preference symbol."""
        i, a, v, pref = r
        if a == "operator":
            return f"({i} ^operator {v} {pref})"
        return f"({i} ^{a} {v})" if pref == "+" else f"({i} ^{a} {v} {pref})"

    def _match_preview(self):
        """Recompute the match set against the CURRENT wm WITHOUT mutating it
        (mirrors settle's first step). Returns new_keys (instantiations now
        satisfying their LHS -> pending fire), gone_keys (active ones whose LHS
        broke -> pending retract), and the full desired map (for the results each
        firing produces). gensym is the elaborator's own allocator, so the ids it
        mints here are the SAME ones settle will use (no divergence)."""
        from pysoar.production import match
        from pysoar.elaborate import instantiate
        el, wm = self.ag.elaborator, self.ag.wm
        desired = {}
        for prod in el.productions:
            for binding, matched in match(prod, wm):
                inst = instantiate(prod, binding, matched, wm, gensym=el._gensym_id)
                desired[inst.key] = inst
        new_keys = [k for k in desired if k not in el.active]
        gone_keys = [k for k in el.active if k not in desired]
        return new_keys, gone_keys, desired

    def elaborate(self, phase):
        wave = 0
        while True:
            wave += 1
            # (1) MATCH -- recompute the match set; wm not yet touched.
            new_keys, gone_keys, desired = self._match_preview()
            before = set(self.ag.wm)
            if new_keys or gone_keys:
                matched = sorted({k[0] for k in new_keys})
                unmatched = sorted({k[0] for k in gone_keys})
                bits = []
                if matched:
                    bits.append("LHS 충족 → " + ", ".join(matched))
                if unmatched:
                    bits.append("LHS 깨짐 → " + ", ".join(unmatched))
                # label = DETAIL only; the stage name ("match") is its own aligned
                # column in the cycle map, derived from the event kind.
                self.emit(phase, "match", ' / '.join(bits),
                          detail={"matched": matched, "unmatched": unmatched}, wave=wave)
                # (2) FIRE -- matched instantiations fire (produce preferences);
                #     gone instantiations retract. wm STILL unchanged here.
                for k in new_keys:
                    prefs = [self._pref_str(r) for r in desired[k].results]
                    self.emit(phase, "rule-fire", f"{k[0]} → {', '.join(prefs)}",
                              highlight=prefs, rule=k[0], wave=wave)
                for k in gone_keys:
                    self.emit(phase, "rule-retract", f"{k[0]} (LHS 미충족)",
                              rule=k[0], wave=wave)
            # (3) WM-UPDATE -- run the real wave: preferences -> WMEs in wm.
            er = self.ag.elaborator.settle(self.ag.wm, max_rounds=1)
            self._sync_candidates()
            after = set(self.ag.wm)
            added = sorted(after - before)
            removed = sorted(before - after)
            if added or removed:
                parts = []
                if added:
                    parts.append(f"+{len(added)}")
                if removed:
                    parts.append(f"−{len(removed)}")
                self.emit(phase, "wm-update", f"{' '.join(parts)} WME",
                          highlight=[_wstr(t) for t in added] + [_wstr(t) for t in removed],
                          wave=wave)
            if er.quiescent:
                break
        self.emit(phase, "quiescence", "no more rules match")

    # -- output-link (^io.output-link = I3) ----------------------------------
    def _outlink(self):
        """WMEs sitting on the output-link this cycle (id == I3). compose writes
        the answer here via add_output_wme; empty otherwise."""
        return sorted((tuple(t) for t in self.ag.wm if t[0] == "I3"),
                      key=lambda t: (str(t[1]), str(t[2])))

    def _emit_input(self):
        """INPUT phase -- runs EVERY cycle (do_input_cycle). Cycle 1 injects the
        task onto ^io.input-link; later cycles re-run the (idempotent) input
        function, so for a STATIC ARC task nothing new enters -> no-op. Shown
        explicitly (not collapsed) so the full Input->...->Output->Input loop is
        visible -- a dynamic env (ARC-AGI-3) WOULD bring new percepts here."""
        self.emit("input", "phase", f"cycle {self.cycle} — INPUT (do_input_cycle)")
        before = set(self.ag.wm)
        self.ag._do_input_phase()
        new = sorted(set(self.ag.wm) - before)
        if new:
            self.emit("input", "wme-add",
                      f"Task injected onto ^io.input-link ({len(new)} WMEs)",
                      highlight=[_wstr(t) for t in new], rule="inject_task")
        else:
            self.emit("input", "input-noop",
                      "input-link unchanged — static task, no new percept (no-op)")

    def _emit_output(self):
        """OUTPUT phase -- runs EVERY cycle (do_output_cycle). Emits whatever sits
        on ^io.output-link to the environment, EMPTY OR NOT, then the cycle loops
        back to INPUT. The link stays empty until compose writes the answer."""
        self.emit("output", "phase", f"cycle {self.cycle} — OUTPUT (do_output_cycle)")
        out = self._outlink()
        if out:
            attrs = ", ".join(f"^{a}" for (_i, a, _v) in out)
            self.emit("output", "output",
                      f"output-link: {attrs} → sent to environment",
                      highlight=[_wstr(t) for t in out],
                      detail=_kg_detail(self.ag.kg, "compose"))
        elif self.ag.wm.contains("S1", "declined", "yes"):
            self.emit("output", "output",
                      "output-link empty (declined: no answer produced)")
        else:
            self.emit("output", "output",
                      "output-link empty (nothing to send this cycle)")

    def _acceptable_values(self, slot):
        """Distinct operator values proposed with an acceptable/require preference
        (the candidates) -- the ones SOAR mirrors into WM as ^operator <o> +."""
        out = []
        for p in slot.get(PreferenceType.ACCEPTABLE) + slot.get(PreferenceType.REQUIRE):
            if p.value not in out:
                out.append(p.value)
        return out

    # -- the decision cycle, fine-grained ------------------------------------
    def run(self, max_cycles=10):
        for _ in range(max_cycles):
            self.cycle += 1
            # INPUT (every cycle; injects the task on cycle 1, no-op after)
            self._emit_input()
            # PROPOSE -- elaborate(); candidate ^operator +'s are materialised in
            # WM by _sync_candidates() as part of each firing (see elaborate).
            self.emit("propose", "phase", f"cycle {self.cycle} — PROPOSE (elaborate)")
            self.elaborate("propose")
            goal = self.ag.stack[-1]
            slot = self.ag.collect_operator_prefs(goal.id)
            # DECIDE
            self.emit("decide", "phase", f"cycle {self.cycle} — DECIDE")
            imp, cands = run_preference_semantics(slot)
            self.emit("decide", "decide",
                      f"preference resolution → impasse={imp.name}, candidates={list(cands)}")
            if imp.name == "NONE" and len(cands) == 1:
                op = cands[0]
                self.ag._install_operator(goal, op)      # architecture installs bare WME
                name = self.ag.operator_name(op)         # operator object -> its ^name
                # the candidate +'s persist until their proposal retracts (during
                # apply, when the result flag is set) -- _sync_candidates drops them.
                self.emit("decide", "op-select",
                          f"({goal.id} ^operator {op}) [name={name}]",
                          highlight=[str(op)])
                # APPLY -- body (RHS function: ARCKG/DSL compute) THEN the apply-<name>
                # production fires during the apply elaboration and writes the flag.
                self.emit("apply", "phase", f"cycle {self.cycle} — APPLY ({name})")
                before = set(self.ag.wm)
                body = self.ag.body_for(op)
                if body is not None:
                    body(self.ag)
                new = sorted(set(self.ag.wm) - before)
                if new:
                    # the operator body (RHS function) writes ALL its WMEs as ONE
                    # step, so the whole change shows green together -- not only the
                    # first sub-step (item 12).
                    label = (f"{name} body → {len(new)} WMEs added"
                             if len(new) > 1 else _wstr(new[0]))
                    # The operator body (RHS-function compute) is the APPLY phase's
                    # DIRECT effect, not an elaboration wave -- so it carries NO wave
                    # number and sits under the "APPLY (<name>)" phase box. The
                    # elaboration waves (match -> fire -> wm-update of apply*<name>
                    # and the cascade it triggers) start cleanly after, at wave 1.
                    self.emit("apply", "wme-add", label,
                              highlight=[_wstr(t) for t in new],
                              detail=_kg_detail(self.ag.kg, name), rule=name, wave=None)
                self.elaborate("apply")                  # apply*<name> production fires here
                # OUTPUT (every cycle; emits output-link contents, empty or not)
                self._emit_output()
                if name == "submit" or self.ag.wm.contains("S1", "done", "yes"):
                    break
            else:
                # impasse -> substate (general SOAR path; rare for these solvers)
                self.emit("decide", "substate",
                          f"impasse {imp.name} → substate would be created")
                self._emit_output()
                break
        return self.events


def fine_trace(task, tid="0a"):
    return _Tracer(task, tid).run()
