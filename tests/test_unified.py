"""
Unified agent (arc/solver.py): ONE operator pool + ONE base production-rule set
solves every task kind; the operator sequence emerges from problem state.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_unified -v
"""

import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EASY = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
MULTI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "arc", "data", "multi")
ARCKG_OK = os.path.isdir(os.path.expanduser("~/Desktop/ARC-solver/ARCKG"))


@unittest.skipUnless(os.path.isdir(EASY) and os.path.isdir(MULTI) and ARCKG_OK,
                     "data/ARCKG not present")
class TestUnified(unittest.TestCase):
    def _solve(self, path):
        from legacy.solver import solve
        return solve(json.load(open(path)))

    def test_one_agent_solves_all(self):
        files = (sorted(glob.glob(os.path.join(EASY, "*.json")))
                 + sorted(glob.glob(os.path.join(MULTI, "*.json"))))
        failed = [os.path.basename(f) for f in files if not self._solve(f)["correct"]]
        self.assertEqual(failed, [])

    def test_single_object_skips_select(self):
        r = self._solve(os.path.join(EASY, "easy000a.json"))
        self.assertNotIn("select", r["ops"])        # no select for single object
        self.assertIn("generalize", r["ops"])        # but it does transform

    def test_select_only_skips_generalize(self):
        r = self._solve(os.path.join(MULTI, "select_color.json"))
        self.assertIn("select", r["ops"])
        self.assertNotIn("generalize", r["ops"])     # pure selection, no transform

    def test_multi_plus_transform_uses_both(self):
        # the task neither old solver could do: select AND transform
        r = self._solve(os.path.join(MULTI, "select_move.json"))
        self.assertTrue(r["correct"])
        self.assertEqual(r["ops"],
                         ["observe", "select", "compare", "generalize", "compose", "submit"])

    def test_branch_is_decided_by_problem_state(self):
        # SAME rule set -> different operator sequences -> emergent, not hardcoded
        single = self._solve(os.path.join(EASY, "easy000a.json"))["ops"]
        sel = self._solve(os.path.join(MULTI, "select_color.json"))["ops"]
        both = self._solve(os.path.join(MULTI, "select_move.json"))["ops"]
        self.assertEqual(len({tuple(single), tuple(sel), tuple(both)}), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
