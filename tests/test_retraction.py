"""
Unit tests for milestone 2: i/o-support classification and truth-maintained
retraction. Executable spec derived from instantiation.cpp:545 (o-support) and
:1431 (retraction). Each test names the SOAR behaviour it pins down.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_retraction -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import (  # noqa: E402
    Action, Cond, Elaborator, Production, Support, WorkingMemory,
    calculate_o_support, elaborate_to_quiescence, match,
)


def state_wm(*triples):
    wm = WorkingMemory()
    wm.mark_goal("S1", level=1)
    wm.load(triples)
    return wm


class TestOSupportClassification(unittest.TestCase):
    def test_operator_proposal_is_i_support(self):
        # (S1 ^flag x) --> (S1 ^operator <o> +)  : proposing an operator
        p = Production(
            "propose",
            [Cond("S1", "flag", "x")],
            [Action("S1", "operator", "<o>", "+"), Action("<o>", "name", "foo")],
        )
        wm = state_wm(("S1", "flag", "x"))
        (binding, matched), = match(p, wm)
        self.assertFalse(calculate_o_support(p, binding, matched, wm))

    def test_operator_application_is_o_support(self):
        # tests selected operator on LHS, writes a non-operator WME -> o-support
        p = Production(
            "apply",
            [Cond("S1", "operator", "<o>"), Cond("<o>", "name", "foo")],
            [Action("S1", "result", "done")],
        )
        wm = state_wm(("S1", "operator", "O7"), ("O7", "name", "foo"))
        (binding, matched), = match(p, wm)
        self.assertTrue(calculate_o_support(p, binding, matched, wm))

    def test_operator_elaboration_is_i_support(self):
        # tests selected operator but only elaborates the operator itself
        p = Production(
            "op-elab",
            [Cond("S1", "operator", "<o>"), Cond("<o>", "name", "foo")],
            [Action("<o>", "param", "5")],
        )
        wm = state_wm(("S1", "operator", "O7"), ("O7", "name", "foo"))
        (binding, matched), = match(p, wm)
        self.assertFalse(calculate_o_support(p, binding, matched, wm))

    def test_plain_elaboration_is_i_support(self):
        # no operator tested at all -> i-support
        p = Production(
            "elab",
            [Cond("S1", "a", "<v>")],
            [Action("S1", "b", "<v>")],
        )
        wm = state_wm(("S1", "a", "1"))
        (binding, matched), = match(p, wm)
        self.assertFalse(calculate_o_support(p, binding, matched, wm))

    def test_declared_support_overrides(self):
        p_i = Production("x", [Cond("S1", "operator", "<o>")],
                         [Action("S1", "r", "1")], support=Support.I_SUPPORT)
        p_o = Production("y", [Cond("S1", "a", "1")],
                         [Action("S1", "b", "1")], support=Support.O_SUPPORT)
        wm = state_wm(("S1", "operator", "O7"), ("S1", "a", "1"))
        (b1, m1), = match(p_i, wm)
        (b2, m2), = match(p_o, wm)
        self.assertFalse(calculate_o_support(p_i, b1, m1, wm))
        self.assertTrue(calculate_o_support(p_o, b2, m2, wm))


class TestRetraction(unittest.TestCase):
    def test_i_support_present_while_condition_holds(self):
        elab = Production("elab", [Cond("S1", "a", "<v>")], [Action("S1", "b", "<v>")])
        wm = state_wm(("S1", "a", "1"))
        elaborate_to_quiescence(wm, [elab])
        self.assertTrue(wm.contains("S1", "b", "1"))

    def test_i_support_retracts_when_condition_removed(self):
        # the heart of milestone 2: remove the support -> the derived WME vanishes
        elab = Production("elab", [Cond("S1", "a", "<v>")], [Action("S1", "b", "<v>")])
        wm = state_wm(("S1", "a", "1"))
        el = Elaborator([elab])
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "b", "1"))

        # now retract the base support WME and re-settle the SAME elaborator
        wm.remove("S1", "a", "1")
        el.settle(wm)
        self.assertFalse(wm.contains("S1", "b", "1"),
                         "i-supported WME should have retracted (ghost WME bug)")

    def test_o_support_persists_when_condition_removed(self):
        # operator-application result is o-supported -> survives support removal
        apply_op = Production(
            "apply",
            [Cond("S1", "operator", "<o>"), Cond("<o>", "name", "foo")],
            [Action("S1", "result", "done")],
        )
        wm = state_wm(("S1", "operator", "O7"), ("O7", "name", "foo"))
        el = Elaborator([apply_op])
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "result", "done"))

        # operator changes (condition gone) -> o-supported result must persist
        wm.remove("S1", "operator", "O7")
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "result", "done"),
                        "o-supported WME must persist after its instantiation retracts")

    def test_chained_i_support_retracts_transitively(self):
        # a -> b -> c, all i-support; remove a, both b and c should vanish
        r1 = Production("r1", [Cond("S1", "a", "1")], [Action("S1", "b", "1")])
        r2 = Production("r2", [Cond("S1", "b", "1")], [Action("S1", "c", "1")])
        wm = state_wm(("S1", "a", "1"))
        el = Elaborator([r1, r2])
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "b", "1") and wm.contains("S1", "c", "1"))

        wm.remove("S1", "a", "1")
        el.settle(wm)
        self.assertFalse(wm.contains("S1", "b", "1"))
        self.assertFalse(wm.contains("S1", "c", "1"))

    def test_negated_condition_blocks_firing(self):
        # (S1 ^a 1) -(S1 ^stop *) --> (S1 ^b 1)
        r = Production(
            "guarded",
            [Cond("S1", "a", "1"), Cond("S1", "stop", "<x>", negated=True)],
            [Action("S1", "b", "1")],
        )
        wm = state_wm(("S1", "a", "1"))
        el = Elaborator([r])
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "b", "1"))

        # add the stop WME -> condition no longer matches -> b retracts
        wm.add("S1", "stop", "yes")
        el.settle(wm)
        self.assertFalse(wm.contains("S1", "b", "1"))

    def test_multiple_support_one_removed_keeps_wme(self):
        # two rules both assert (S1 ^b 1); removing one rule's support keeps b
        r1 = Production("r1", [Cond("S1", "a", "1")], [Action("S1", "b", "1")])
        r2 = Production("r2", [Cond("S1", "x", "1")], [Action("S1", "b", "1")])
        wm = state_wm(("S1", "a", "1"), ("S1", "x", "1"))
        el = Elaborator([r1, r2])
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "b", "1"))

        wm.remove("S1", "a", "1")  # r1's support gone, r2 still holds
        el.settle(wm)
        self.assertTrue(wm.contains("S1", "b", "1"),
                        "WME with remaining support must not retract")


if __name__ == "__main__":
    unittest.main(verbosity=2)
