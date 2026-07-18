"""
Multi-object `select` operator: solves the three select-basis tasks
(arc/data/multi) and the trace recorder feeds the web debugger.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_select -v
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "arc", "data", "multi")
ARCKG_OK = os.path.isdir(os.path.expanduser("~/Desktop/ARC-solver/ARCKG"))


@unittest.skipUnless(os.path.isdir(DATA) and ARCKG_OK, "tasks/ARCKG not present")
class TestSelect(unittest.TestCase):
    def _solve(self, name):
        from arbor.perception.select_solver import solve
        return solve(json.load(open(os.path.join(DATA, f"{name}.json"))))

    def test_fixed_attribute(self):
        r = self._solve("select_color")
        self.assertTrue(r["correct"])
        self.assertEqual(r["criterion"]["basis"], "color")
        self.assertEqual(r["criterion"]["value"], 2)

    def test_generalized_attribute(self):
        r = self._solve("select_largest")
        self.assertTrue(r["correct"])
        self.assertEqual(r["criterion"]["basis"], "argmax")
        self.assertEqual(r["criterion"]["attr"], "area")

    def test_relation(self):
        r = self._solve("select_relation")
        self.assertTrue(r["correct"])
        self.assertEqual(r["criterion"]["basis"], "relation")
        self.assertEqual(r["criterion"]["rel"], "same_row")
        self.assertEqual(r["criterion"]["marker"], 1)

    def test_same_operator_sequence(self):
        # the SAME general operators solve all three; only the basis differs
        for name in ("select_color", "select_largest", "select_relation"):
            self.assertEqual(self._solve(name)["ops"],
                             ["observe", "select", "compose", "submit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
