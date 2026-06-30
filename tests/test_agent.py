"""
Unit tests for milestone 3: the decision cycle (M1 + M2) with automatic
substates. Executable spec for: operator selection, impasse -> substate with the
right ^impasse/^choices/^attribute WMEs, ONC vs SNC, and substate dissolution
when an impasse is resolved.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_agent -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Action, Agent, Cond, ImpasseType, Production  # noqa: E402


def tie_resolve_productions():
    return [
        Production("propose-a", [Cond("S1", "superstate", "nil")],
                   [Action("S1", "operator", "a", "+")]),
        Production("propose-b", [Cond("S1", "superstate", "nil")],
                   [Action("S1", "operator", "b", "+")]),
        Production("resolve",
                   [Cond("<s>", "impasse", "tie"), Cond("<s>", "superstate", "<ss>")],
                   [Action("<ss>", "operator", "a", ">")]),
        Production("apply-a", [Cond("S1", "operator", "a")],
                   [Action("S1", "result", "done")]),
    ]


def labels(trace):
    return [t[0] for t in trace]


class TestSelection(unittest.TestCase):
    def test_single_operator_selected(self):
        prods = [Production("p", [Cond("S1", "superstate", "nil")],
                            [Action("S1", "operator", "go", "+")])]
        ag = Agent(prods)
        ag.step()
        self.assertEqual(ag.stack[0].selected, "go")
        self.assertTrue(ag.wm.contains("S1", "operator", "go"))

    def test_best_breaks_would_be_tie(self):
        prods = [
            Production("pa", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", "+")]),
            Production("pb", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "b", "+")]),
            Production("best-a", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", ">")]),
        ]
        ag = Agent(prods)
        ag.step()
        self.assertEqual(ag.stack[0].selected, "a")


class TestImpasseSubstate(unittest.TestCase):
    def test_tie_creates_substate_with_impasse_wmes(self):
        prods = [
            Production("pa", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", "+")]),
            Production("pb", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "b", "+")]),
        ]
        ag = Agent(prods)
        ag.step()
        self.assertEqual(len(ag.stack), 2)
        sub = ag.stack[1].id
        augs = ag.state_augs(sub)
        self.assertEqual(augs.get("type"), {"state"})
        self.assertEqual(augs.get("superstate"), {"S1"})
        self.assertEqual(augs.get("impasse"), {"tie"})
        self.assertEqual(augs.get("choices"), {"multiple"})
        self.assertEqual(augs.get("attribute"), {"operator"})
        self.assertEqual(augs.get("quiescence"), {"t"})
        self.assertEqual(augs.get("item"), {"a", "b"})
        self.assertEqual(augs.get("item-count"), {2})

    def test_conflict_creates_conflict_substate(self):
        prods = [
            Production("pa", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", "+")]),
            Production("pb", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "b", "+")]),
            Production("ab", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", ">", "b")]),
            Production("ba", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "b", ">", "a")]),
        ]
        ag = Agent(prods)
        ag.step()
        self.assertEqual(ag.state_augs(ag.stack[1].id).get("impasse"), {"conflict"})
        self.assertEqual(ag.state_augs(ag.stack[1].id).get("choices"), {"multiple"})

    def test_no_operator_is_state_no_change(self):
        # top state with elaboration but no operator proposal -> state no-change
        prods = [Production("elab", [Cond("S1", "superstate", "nil")],
                            [Action("S1", "ready", "yes")])]
        ag = Agent(prods)
        ag.step()
        self.assertEqual(len(ag.stack), 2)
        sub = ag.stack[1]
        self.assertEqual(sub.impasse, ImpasseType.SNC)
        self.assertEqual(ag.state_augs(sub.id).get("attribute"), {"state"})
        self.assertEqual(ag.state_augs(sub.id).get("impasse"), {"no-change"})


class TestResolutionAndNoChange(unittest.TestCase):
    def test_tie_resolved_then_operator_no_change_then_snc(self):
        ag = Agent(tie_resolve_productions())
        trace = []
        for _ in range(5):
            trace.extend(ag.step().decisions)
        # the canonical sequence (matches the oracle, see test_oracle_cycle)
        self.assertEqual(
            labels(trace),
            ["tie", "select", "operator-no-change", "state-no-change", "state-no-change"],
        )

    def test_substate_dissolves_on_resolution(self):
        ag = Agent(tie_resolve_productions())
        ag.step()                       # tie -> S2
        self.assertEqual(len(ag.stack), 2)
        ag.step()                       # resolve -> select a, S2 dissolved
        self.assertEqual(ag.stack[0].selected, "a")
        self.assertNotIn("S2", [g.id for g in ag.stack])
        # S2's impasse WMEs are gone from WM
        self.assertEqual(ag.state_augs("S2"), {})

    def test_apply_result_is_o_supported_and_persists(self):
        ag = Agent(tie_resolve_productions())
        for _ in range(5):
            ag.step()
        # ^result done was written by apply-a (o-support) and persists even as
        # the agent descends into the no-change cascade
        self.assertTrue(ag.wm.contains("S1", "result", "done"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
