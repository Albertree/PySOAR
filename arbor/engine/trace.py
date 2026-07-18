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

from soar import Agent  # noqa: E402
from soar.decide import run_preference_semantics  # noqa: E402
from soar.preference import SYMBOL_TO_TYPE, PreferenceType  # noqa: E402
from debugger.dashboard import _kg_detail  # noqa: E402

_TYPE_TO_SYM = {v: k for k, v in SYMBOL_TO_TYPE.items()}


def _wstr(t):
    """Format a WME triple for the trace. A grid/array value (the apply_solution ^answer,
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
    def __init__(self, task, tid="0a", setup=None, sink=None):
        if setup is None:
            from arbor.expr_solver import setup_arc_agent as setup
        self.ag = setup(task, tid)             # io + the solver's input function
        from arbor.engine.sink import JournalSink
        self.sink = sink if sink is not None else JournalSink(self.ag)
        self._rendered = None                       # (events, wm_states) 캐시 — 최초 접근 시 1회 render
        self.task = task
        self.cycle = 0
        self._cands: set = set()               # materialised ^operator + WMEs
        # A안(2-사이클 충실 ONC): operator 가 적용됐으나 무변화면 여기에 (name, kind) 를 기록하고
        # 이 사이클은 apply-fail 로 깨끗이 닫는다. no-change impasse 는 **다음 사이클 DECIDE** 에서
        # 감지(원본 SOAR: no-change 는 한 사이클 뒤에 드러남). kind: 'arg'(observe/compare) | 'descend'(solve).
        self._pending_onc: dict = {}            # goal_id -> (op_name, kind)
        # ARC-AGI 3회 재시도 환경 (submit → 채점 → 오답이면 다음 후보로 retry)
        from arbor.env.environment import ARCEnvironment
        self.env = ARCEnvironment([(tid, task)])
        self.env.reset()
        self.attempts: list = []               # [{answer, correct, hyp}] — 대시보드 후보

    def _render(self):
        if self._rendered is None:
            from arbor.engine.renderer import render
            self._rendered = render(self.sink)      # journal → (events, wm_states), 1회 memoize
        return self._rendered

    @property
    def events(self):
        return self._render()[0]

    @property
    def _wm_states(self):
        return self._render()[1]

    def emit(self, phase, kind, label, highlight=None, detail=None, rule=None, wave=None):
        self.sink.event(phase, kind, label, self.cycle, [g.id for g in self.ag.stack],
                        highlight=highlight, detail=detail, rule=rule, wave=wave)

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
        from soar.production import match
        from soar.elaborate import instantiate
        el, wm = self.ag.elaborator, self.ag.wm
        desired = {}
        for prod in el.productions:
            for binding, matched in match(prod, wm):
                inst = instantiate(prod, binding, matched, wm, gensym=el._gensym_id)
                desired[inst.key] = inst
        new_keys = [k for k in desired if k not in el.active]
        gone_keys = [k for k in el.active if k not in desired]
        return new_keys, gone_keys, desired

    def elaborate(self, phase, body=None, op_name=None):
        # body/op_name: in APPLY, the operator's body is the RHS-FUNCTION of its
        # apply*<name> production -- it runs WHEN that rule fires, so the structure it
        # loads and the rule's o-support flag appear together in ONE wm-update (one
        # application). SOAR: the operator's effect is produced BY the apply rule firing.
        apply_rule = f"apply*{op_name}" if op_name else None
        body_ran = False
        wave = 0
        while True:
            wave += 1
            # (1) MATCH -- recompute the match set; wm not yet touched.
            new_keys, gone_keys, desired = self._match_preview()
            before = set(self.ag.wm)
            run_body = (body is not None and not body_ran and apply_rule is not None
                        and any(k[0] == apply_rule for k in new_keys))
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
                    if run_body and k[0] == apply_rule:
                        lbl = f"{k[0]} → RHS-function({op_name} body) + {', '.join(prefs)}"
                    else:
                        lbl = f"{k[0]} → {', '.join(prefs)}"
                    self.emit(phase, "rule-fire", lbl, highlight=prefs, rule=k[0], wave=wave)
                for k in gone_keys:
                    self.emit(phase, "rule-retract", f"{k[0]} (LHS 미충족)",
                              rule=k[0], wave=wave)
            # RHS-function: run the operator body NOW (as apply*<name> fires), so its
            # structure joins THIS wave's wm-update -- not a separate pre-apply step.
            if run_body:
                body(self.ag)
                body_ran = True
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
                det = _kg_detail(self.ag.kg, op_name) if run_body else None
                self.emit(phase, "wm-update", f"{' '.join(parts)} WME",
                          highlight=[_wstr(t) for t in added] + [_wstr(t) for t in removed],
                          detail=det, wave=wave)
            if er.quiescent:
                break
        self.emit(phase, "quiescence", "no more rules match")

    # -- output-link (^io.output-link = I3) ----------------------------------
    def _outlink(self):
        """WMEs sitting on the output-link this cycle (id == I3). apply_solution writes
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
        back to INPUT. The link stays empty until apply_solution writes the answer."""
        self.emit("output", "phase", f"cycle {self.cycle} — OUTPUT (do_output_cycle)")
        out = self._outlink()
        if out:
            attrs = ", ".join(f"^{a}" for (_i, a, _v) in out)
            op_name = "apply_solution" if self.ag.kg.get("_focus") else "compose"
            self.emit("output", "output",
                      f"output-link: {attrs} → sent to environment",
                      highlight=[_wstr(t) for t in out],
                      detail=_kg_detail(self.ag.kg, op_name))
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
            # H-space(가설공간)가 synthesize 를 마쳤으면(hspace-done) 제거하고 부모로 복귀.
            top = self.ag.stack[-1]
            if self.ag.wm.contains(top.id, "hspace-done", "yes"):
                self.emit("decide", "substate",
                          f"hypothesis-space {top.id} 완료(가설 확정) → 제거, 부모 복귀",
                          highlight=[f"({top.id} ^hspace-done yes)"])
                self.ag.remove_substates_below(max(len(self.ag.stack) - 2, 0))
                self._emit_output()
                continue
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
            from soar.decide import ImpasseType
            # ── A안: 2-사이클 충실 ONC 감지 ────────────────────────────────────
            # 지난 사이클에 이 operator 를 적용했으나 무변화였다면(pending) → 이번 사이클 DECIDE 가
            # operator-no-change impasse 를 감지한다(원본 SOAR: no-change 는 한 사이클 뒤에 드러남).
            # substate 생성/하강 후 **빈 apply phase → output**. 재적용하지 않는다.
            pend = self._pending_onc.get(goal.id)
            if (pend and imp.name == "NONE" and len(cands) == 1
                    and self.ag.operator_name(cands[0]) == pend[0]):
                name, kind = pend
                del self._pending_onc[goal.id]
                self.emit("decide", "op-select",
                          f"({goal.id} ^operator {cands[0]}) [name={name}] — 지속·무진전")
                ended = False
                if kind == "arg":
                    self.emit("decide", "substate",
                              f"operator no-change impasse @ {goal.id} "
                              f"(op={name} 지속·무진전 → arg-선택 substate)")
                    self._open_arg_substate(goal, name)
                else:  # 'descend' — 미구현(solve)
                    self.emit("decide", "substate",
                              f"operator no-change impasse @ {goal.id} (op={name} 미구현 → 한 계층 하강)")
                    ended = not self._do_descend(goal, ImpasseType.ONC, "operator", name)
                # 새 substate 는 아직 operator 가 없음 → 이 사이클 APPLY 는 비어 있음 → OUTPUT
                self.emit("apply", "phase", f"cycle {self.cycle} — APPLY (비어 있음 · 새 substate)")
                self.emit("apply", "op-apply", "새 substate — 이 사이클 apply 는 비어 있음")
                self._emit_output()
                if ended:
                    break
                continue

            if imp.name == "NONE" and len(cands) == 1:
                op = cands[0]
                self.ag._install_operator(goal, op)      # architecture installs bare WME
                name = self.ag.operator_name(op)
                self.emit("decide", "op-select",
                          f"({goal.id} ^operator {op}) [name={name}]", highlight=[str(op)])
                st = self._apply_operator(goal, op, name)
                if st == "onc_arg":
                    # CYCLE 1 (apply-fail): observe/compare 가 arg 없이 적용→무변화. no-change 는
                    # **다음 사이클** DECIDE 에서 감지(위 pending 분기). 이 사이클은 I→P→D→A→O 로 닫는다.
                    self._pending_onc[goal.id] = (name, "arg")
                    self._emit_output()
                elif st == "onc_descend":
                    self._pending_onc[goal.id] = (name, "descend")
                    self._emit_output()
                elif not self._after_apply(st):
                    break
            elif imp.name == "NONE" and len(cands) == 0:
                selfor = next((v for (i, a, v) in self.ag.wm
                               if i == goal.id and a == "select-for"), None)
                if selfor is not None:
                    # ── A안 FOLD: arg 확보로 super 의 impasse 해소 → substate 제거(DECIDE)하고
                    #     **같은 사이클**에 super operator 를 재선택·적용(APPLY). 독립 pop 사이클 없음
                    #     (원본 SOAR: 제거는 부모 슬롯이 풀리는 DECIDE 에 folded, 부모 apply 는 그 사이클). ──
                    sup = self.ag.stack[-2] if len(self.ag.stack) >= 2 else None
                    self.emit("decide", "substate",
                              f"impasse 해소(arg 확보) → substate {goal.id} 제거(folded) · "
                              f"superstate {sup.id if sup else '?'} 재개")
                    self.ag.remove_substates_below(max(len(self.ag.stack) - 2, 0))
                    if sup is None:
                        self.emit("apply", "phase", f"cycle {self.cycle} — APPLY (비어 있음)")
                        self._emit_output()
                        continue
                    slot2 = self.ag.collect_operator_prefs(sup.id)
                    imp2, cands2 = run_preference_semantics(slot2)
                    if imp2.name == "NONE" and len(cands2) == 1:
                        op2 = cands2[0]
                        self.ag._install_operator(sup, op2)
                        n2 = self.ag.operator_name(op2)
                        self.emit("decide", "op-select",
                                  f"({sup.id} ^operator {op2}) [name={n2}] — arg 확보 후 재개",
                                  highlight=[str(op2)])
                        st = self._apply_operator(sup, op2, n2)
                        if st == "onc_arg":
                            self._pending_onc[sup.id] = (n2, "arg")
                            self._emit_output()
                        elif st == "onc_descend":
                            self._pending_onc[sup.id] = (n2, "descend")
                            self._emit_output()
                        elif not self._after_apply(st):
                            break
                    else:
                        self.emit("apply", "phase", f"cycle {self.cycle} — APPLY (비어 있음)")
                        self._emit_output()
                    continue
                # arg-substate 아님 = 이 레벨 정보로 진전 불가 → STATE NO-CHANGE → 한 계층 하강.
                self.emit("decide", "substate",
                          f"state no-change impasse @ {goal.id} (이 레벨 정보로 진전 불가)")
                ended = not self._do_descend(goal, ImpasseType.SNC, "state", None)
                self.emit("apply", "phase", f"cycle {self.cycle} — APPLY (비어 있음 · 새 substate)")
                self._emit_output()
                if ended:
                    break
            else:
                # tie/conflict/etc -- not expected in this (single-candidate) solver
                self.emit("decide", "substate",
                          f"impasse {imp.name} (candidates={list(cands)}) — 미처리, 종료")
                self._emit_output()
                break
        return self.events

    def _submit_and_maybe_retry(self):
        """submit 후: ARC 환경(3회 프로토콜)으로 답을 채점하고 피드백을 emit.
        오답 ∧ 재시도 가능 ∧ 다음 후보 있으면 → 현재 가설 reject 하고 다음 후보로
        재시도(True 반환=계속). 정답/소진/후보없음이면 종료(False)."""
        ans = self.ag.kg.get("answer")
        grid = [list(r) for r in ans] if ans else None
        _reward, _ctx, _done, info = self.env.step(grid)      # 환경이 채점 (env 살아있음)
        S = self.ag.kg.get("solve", {})
        if S.get("mode") == "relational":
            hypname = "relational (size/color/contents)"
        else:
            hyp = (S.get("verified") or {})
            hypname = f"{hyp.get('position', '')} | {hyp.get('color', '')}" if hyp else "—"
        n = len(self.attempts) + 1
        self.attempts.append({"answer": grid, "correct": info["correct"], "hyp": hypname})
        has_next = bool(S.get("hyps")) and (S.get("idx", 0) + 1) < len(S["hyps"])
        retry = (not info["correct"]) and info["can_retry"] and has_next
        verdict = "정답 ✓" if info["correct"] else "오답 ✗"
        tail = (f" → reject, 다음 후보로 재시도 (남은 {info['attempts_left']}회)"
                if retry else (" → 재시도 소진" if not info["correct"] else ""))
        self.emit("output", "feedback",
                  f"제출 #{n}/{self.env._max}: {verdict}{tail}",
                  highlight=[f"attempt {n}: {'correct' if info['correct'] else 'wrong'}"])
        if not retry:
            return False                                       # 종료
        self._reject_and_retry(S)
        return True                                            # 계속

    def _reject_and_retry(self, S):
        """현재 가설을 reject: 다음 후보(idx+1)로 넘기고, 풀이 substate 의 결과
        플래그(consistent/verified/answer-ready/done/predicted/hyps-exhausted)와
        output-link 답을 지워 apply_solution→submit(또는 predict→…→submit)이 다음 후보로 재발화."""
        S["idx"] = S.get("idx", 0) + 1
        S["verified"] = None

        def _drop(i, a, v):
            self.ag.wm.remove(i, a, v)
            # o-support(apply 규칙이 assert 한 ^done 등)는 persistent 집합에도 있어 WM 에서만
            # 지우면 다음 settle 에 재확립된다 → elaborator.o_support_wmes 에서도 제거(명시 reject 상당).
            elab = getattr(self.ag, "elaborator", None)
            if elab is not None:
                elab.o_support_wmes.discard((i, a, v))

        for attr in ("consistent", "verified", "answer-ready", "done",
                     "predicted", "hyps-exhausted"):
            for (i, a, v) in list(self.ag.wm.matching(attr=attr)):
                _drop(i, a, v)
        for (i, a, v) in list(self.ag.wm.matching(identifier="I3", attr="answer")):
            _drop(i, a, v)
        self.ag.kg["answer"] = None
        self.ag._clear_operator(self.ag.stack[-1])            # 현재 선택 해제 → 재결정

    def _goal_focus(self, gid):
        return next((v for (i, a, v) in self.ag.wm if i == gid and a == "focus"), None)

    def _goal_group(self, gid):
        """이 goal 의 ^focus 값들 = 현재 계층의 노드 그룹(관측 대상 = 하강 스코프). 없으면
        (top goal) ^arckg 루트로 폴백 — legacy(expr_solver) 는 focus 를 안 쓰고 이 경로로 하강."""
        g = [v for (i, a, v) in self.ag.wm if i == gid and a == "focus"]
        if g:
            return g
        root = next((v for (i, a, v) in self.ag.wm if i == gid and a == "arckg"), None)
        return [root] if root else []

    def _do_descend(self, goal, imp_type, attr, opname=None):
        """impasse → 한 ARCKG 계층 하강. next 그룹 = 현재 ^focus 그룹의 자식 전부(focus_solver;
        kg['_focus']) / 첫 자식(legacy). substate 에:
          ^level  = ARCKG 5계층명 대문자(TASK/PAIR/GRID/OBJECT/PIXEL) — 지금 어느 계층인지
          ^focus  = 그 계층의 노드 그룹 (관측 대상 = operator arg 후보 목록)
          ^cursor = 현재 관측 커서(한 노드) — observe 가 이걸 하나씩 옮기며 훑는다."""
        idx = self.ag.kg.get("idx") if hasattr(self.ag, "kg") else None
        srcs = self._goal_group(goal.id)
        # PIXEL 하강: OBJECT 레벨에서 hypothesize 가 실패(^hypothesized failed)했으면, object 의 자식이 아니라
        # **부모 GRID 의 pixels** 로 하강한다 (사용자 2026-07-10: 되올라감 없이 그냥 descend → PIXEL, focus=GRID.pixels).
        level_now = (idx["level"].get(srcs[0], "") if (idx and srcs) else "")
        to_pixel = (idx is not None and srcs and level_now == "object"
                    and self.ag.wm.contains(goal.id, "hypothesized", "failed"))
        if to_pixel:
            grids = []
            for o in srcs:                          # object → 그 부모 GRID (G0·G1)
                g = idx["parent"].get(o)
                if g and g not in grids:
                    grids.append(g)
            kids = [px for g in grids for px in idx.get("pixels", {}).get(g, [])]
            self.ag.wm.add(goal.id, "pixel-open", "yes")     # 재하강 방지 마커
        else:
            kids = [c for src in srcs
                    for c in (idx["children"].get(src, []) if idx else [])] if idx else []
        if not kids:
            self.emit("decide", "substate", f"자식 없음 (from {srcs}) — 더 하강 불가, 종료")
            return None
        focusmode = bool(getattr(self.ag, "kg", None) and self.ag.kg.get("_focus"))
        lv = kids if focusmode else kids[:1]
        layer = (idx["level"].get(lv[0], "") if idx else "").upper()   # TASK/PAIR/GRID/OBJECT/PIXEL
        sub = self.ag.create_substate(goal, imp_type, attr, [])
        self.ag.wm.add(sub.id, "level", layer)        # ARCKG 계층명(대문자)
        for c in lv:
            self.ag.wm.add(sub.id, "focus", c)        # 계층 노드 그룹 (관측 대상)
        self.ag.wm.add(sub.id, "to-observe", "yes")   # 관측할 게 있음 → observe(arg 없이) → arg-선택 substate
        short = [str(c).split('.')[-1] for c in lv]
        self.emit("decide", "substate",
                  f"substate {sub.id} 생성 · {opname or 'descend'} 하강 → level={layer} focus={short}",
                  highlight=[f"({sub.id} ^superstate {goal.id})", f"({sub.id} ^level {layer})"]
                            + [f"({sub.id} ^focus {c})" for c in lv]
                            + [f"({sub.id} ^to-observe yes)"])
        return sub

    def _open_arg_substate(self, goal, opname):
        """arg-선택 substate 를 **생성만** 한다 (impasse-detect 사이클의 DECIDE 에서 호출).
        apply-fail 방출은 앞선 apply-fail 사이클이, 빈 apply·output 은 호출부가 담당한다(A안).
        select 가 super 의 ^cursor/^cmp-active 를 정하면 impasse 가 풀려 fold 로 제거된다."""
        from soar.decide import ImpasseType
        # super 의 operator 선택 해제 — 안 지우면 select 이 super 커서를 세우는 순간 apply*{opname}
        # 규칙이 elaboration 에서 발화해 body 없이 flag 만 세운다. 지우면 fold 에서 새로 선택·apply.
        for (i, a, v) in list(self.ag.wm):
            if i == goal.id and a == "operator":
                self.ag.wm.remove(i, a, v)
        goal.selected = None
        sub = self.ag.create_substate(goal, ImpasseType.ONC, "operator", [])
        self.ag.wm.add(sub.id, "select-for", opname)
        self.ag.wm.add(sub.id, "superstate", goal.id)
        self.emit("decide", "substate",
                  f"substate {sub.id} 생성 · {opname} 의 arg 선택 (superstate={goal.id})",
                  highlight=[f"({sub.id} ^select-for {opname})", f"({sub.id} ^superstate {goal.id})"])
        return sub

    def _apply_operator(self, goal, op, name):
        """APPLY phase 를 실행하고 상태 문자열을 반환한다 (main 루프와 fold 가 공용):
           'onc_arg'     — observe/compare 적용했으나 무변화(arg 미정) → 호출부가 pending 기록
           'onc_descend' — 미구현(solve) 적용, 규칙 없음 → 호출부가 pending 기록
           'submit'      — submit 적용됨(채점은 호출부)
           'done'        — (S1 ^done yes)
           'ok'          — 정상 적용(WM 변화)."""
        self.emit("apply", "phase", f"cycle {self.cycle} — APPLY ({name})")
        body = self.ag.body_for(op)
        has_apply = any(p.name == f"apply*{name}" for p in self.ag.elaborator.productions)
        if body is None and not has_apply:
            self.emit("apply", "op-apply", f"{name}: 적용 규칙 없음(미구현) → WM 변화 없음")
            return "onc_descend"
        if body is not None and not has_apply:
            before = set(self.ag.wm)
            body(self.ag)
            after = set(self.ag.wm)
            added, removed = sorted(after - before), sorted(before - after)
            if added or removed:
                parts = ([f"+{len(added)}"] if added else []) + ([f"−{len(removed)}"] if removed else [])
                self.emit("apply", "wme-add", f"{name} (apply) · {' '.join(parts)} WME",
                          highlight=[_wstr(t) for t in added] + [_wstr(t) for t in removed],
                          detail=_kg_detail(self.ag.kg, name), rule=name, wave=None)
            self.elaborate("apply")
            return "submit" if name == "submit" else \
                   ("done" if self.ag.wm.contains("S1", "done", "yes") else "ok")
        # has_apply(+body): apply 규칙 발화 = 적용
        before = set(self.ag.wm)
        self.elaborate("apply", body=body, op_name=name)
        if before == set(self.ag.wm) and name in ("observe", "compare"):
            return "onc_arg"
        return "submit" if name == "submit" else \
               ("done" if self.ag.wm.contains("S1", "done", "yes") else "ok")

    def _after_apply(self, st):
        """_apply_operator 반환값 처리 공용부. output 방출 + submit/done 시 종료 여부 반환
        (True=계속, False=run 루프 break)."""
        self._emit_output()
        if st == "submit":
            return self._submit_and_maybe_retry()
        if st == "done":
            return False
        return True


def fine_trace(task, tid="0a", setup=None, max_cycles=10):
    return _Tracer(task, tid, setup=setup).run(max_cycles=max_cycles)
