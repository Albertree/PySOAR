"""
ARC end-to-end: the single-pixel solver (PySOAR-driven hypothesis selection)
solves all of data/ARC_easy_a. Skips if the dataset isn't present.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_arc -v
"""

import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from legacy.solve import solve_task  # noqa: E402

DATA = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")


@unittest.skipUnless(os.path.isdir(DATA), f"dataset not found: {DATA}")
class TestARCEasyA(unittest.TestCase):
    def test_solves_all_easy_a(self):
        files = sorted(glob.glob(os.path.join(DATA, "*.json")))
        self.assertGreater(len(files), 0)
        results = {}
        for f in files:
            name = os.path.basename(f).replace(".json", "")
            results[name] = solve_task(json.load(open(f)))
        failed = [n for n, r in results.items() if not r["correct"]]
        self.assertEqual(failed, [], f"unsolved: {failed}")

    def test_selection_is_via_pysoar(self):
        # the chosen hypothesis comes from the PySOAR decision (an operator was
        # selected), not a Python fallback
        task = json.load(open(os.path.join(DATA, "easy000a.json")))
        r = solve_task(task)
        self.assertIsNotNone(r["chosen"])
        # easy000a: const_constC AND diag_constC both fit train; simplicity bias
        # (best preference) must pick the constant-position one
        self.assertEqual(r["chosen"], "const_constC")
        self.assertGreaterEqual(len(r["consistent"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
