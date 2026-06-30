"""
WM-driven general-operator ARC solver (arc/soar_solver.py): solves data/ARC_easy_a
through observe->compare->generalize->compose->submit on real ARCKG, driven by
the PySOAR decision cycle. Skips if dataset / ARCKG aren't present.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_soar_solver -v
"""

import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
ARCKG_OK = os.path.isdir(os.path.expanduser("~/Desktop/ARC-solver/ARCKG"))


@unittest.skipUnless(os.path.isdir(DATA) and ARCKG_OK, "dataset/ARCKG not present")
class TestSoarSolver(unittest.TestCase):
    def _solve(self, name):
        from arc.soar_solver import solve
        return solve(json.load(open(os.path.join(DATA, f"{name}.json"))))

    def test_solves_all_easy_a(self):
        from arc.soar_solver import solve
        failed = []
        for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
            name = os.path.basename(f).replace(".json", "")
            if not solve(json.load(open(f)))["correct"]:
                failed.append(name)
        self.assertEqual(failed, [])

    def test_uses_general_operators_in_order(self):
        # the solve runs the general SOAR operators, not task-specific hypotheses
        r = self._solve("easy000e")
        self.assertEqual(r["ops"], ["observe", "compare", "generalize", "compose", "submit"])

    def test_rule_is_derived_not_hardcoded(self):
        # easy000e: translate by (+1,-1), copy color -- derived by generalize
        r = self._solve("easy000e")
        self.assertEqual(r["rule"]["position"], ("delta", (1, -1)))
        self.assertEqual(r["rule"]["color"], ("copy", None))

    def test_same_operators_different_rules(self):
        # the SAME operator sequence yields DIFFERENT rules per task -- generality
        const = self._solve("easy000a")["rule"]["position"][0]
        delta = self._solve("easy000f")["rule"]["position"][0]
        diag = self._solve("easy000g")["rule"]["position"][0]
        self.assertEqual((const, delta, diag), ("const", "delta", "diag"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
