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

    def test_fine_trace_is_atomic(self):
        # every system change is its own step: phases, rule fire/retract, and
        # individual WME adds are separate events.
        from arbor.engine.trace import fine_trace
        import os as _os
        easy = _os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a/easy000a.json")
        ev = fine_trace(json.load(open(easy)))
        kinds = {e["kind"] for e in ev}
        self.assertIn("phase", kinds)
        self.assertIn("rule-fire", kinds)
        self.assertIn("wme-add", kinds)
        self.assertIn("op-select", kinds)
        self.assertIn("output", kinds)
        # each wme-add reports exactly the WME(s) it added: 1 normally; the
        # observe step bulk-loads the whole ARCKG hierarchy in one event.
        for e in ev:
            if e["kind"] == "wme-add" and "WMEs" not in e["label"]:    # bulk loads aside
                self.assertEqual(len(e["highlight"]), 1)
        # phases occur in cycle order: input first, output last
        self.assertEqual(ev[0]["phase"], "input")
        self.assertEqual(ev[-1]["phase"], "output")

    def test_dashboard_data_well_formed(self):
        # the dashboard embeds task data with no leftover injection sentinel
        from debugger.dashboard import task_data, build
        import os as _os
        easy = _os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a/easy000a.json")
        td = task_data("easy000a", json.load(open(easy)))
        html = build("easy_a", [td])
        self.assertNotIn("__DATA__", html)         # sentinel replaced
        self.assertIn('"events"', html)            # data embedded
        self.assertIn("renderStep", html)          # stepper JS present
        self.assertGreater(td["n_steps"], 10)      # atomic -> many steps


if __name__ == "__main__":
    unittest.main(verbosity=2)
