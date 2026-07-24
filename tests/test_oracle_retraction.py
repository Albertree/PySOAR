"""
Differential test for milestone 2: PySOAR truth maintenance vs the real C++
kernel, on a scenario that DISCRIMINATES i-support from o-support.

Scenario (one agent, run in the oracle; replicated by driving the PySOAR
elaborator through the same operator sequence the decision cycle would install):

  apply-go (o-support, tests operator 'go'):  writes ^trophy won, ^marker present
  elab    (i-support, keyed on ^marker):      writes ^derived yes
  apply-clear (o-support, tests operator 'clear'): rejects ^marker

After the run:
  * ^trophy won  -> PRESENT   (o-support persists though operator 'go' is gone)
  * ^marker      -> ABSENT    (explicitly rejected)
  * ^derived     -> ABSENT    (i-support retracted when ^marker vanished)

If PySOAR lacked truth maintenance, ^derived would linger (the ghost-WME bug).

Skips if ~/Desktop/Soar/out/soar is not built.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.soar import Action, Cond, Elaborator, Production, WorkingMemory  # noqa: E402
from tests.oracle.soar_oracle import run_agent_state, soar_available  # noqa: E402

ORACLE_AGENT = r"""
sp {apply-go
   (state <s> ^operator <o> ^superstate nil) (<o> ^name go)
   --> (<s> ^trophy won) (<s> ^marker present) (<s> ^done yes) }
sp {propose-go
   (state <s> ^superstate nil -^done)
   --> (<s> ^operator <o> +) (<o> ^name go) }
sp {elab
   (state <s> ^marker present)
   --> (<s> ^derived yes) }
sp {apply-clear
   (state <s> ^operator <o> ^marker <m>) (<o> ^name clear)
   --> (<s> ^marker <m> -) (<s> ^cleared yes) }
sp {propose-clear
   (state <s> ^superstate nil ^marker present ^done yes -^cleared)
   --> (<s> ^operator <o> +) (<o> ^name clear) }
sp {stop (state <s> ^superstate nil ^cleared yes) --> (halt) }
run 20
print s1
"""

DISCRIMINATING = ("trophy", "marker", "derived", "done", "cleared")


def pysoar_final_state():
    """Drive the PySOAR elaborator through the same operator sequence the Soar
    decision cycle installs, and return {attr: set(values)} for the top state."""
    apply_go = Production(
        "apply-go",
        [Cond("S1", "operator", "<o>"), Cond("S1", "superstate", "nil"),
         Cond("<o>", "name", "go")],
        [Action("S1", "trophy", "won"), Action("S1", "marker", "present"),
         Action("S1", "done", "yes")],
    )
    elab = Production(
        "elab", [Cond("S1", "marker", "present")], [Action("S1", "derived", "yes")],
    )
    apply_clear = Production(
        "apply-clear",
        [Cond("S1", "operator", "<o>"), Cond("<o>", "name", "clear"),
         Cond("S1", "marker", "<m>")],
        [Action("S1", "marker", "<m>", "-"), Action("S1", "cleared", "yes")],
    )

    wm = WorkingMemory()
    wm.mark_goal("S1", level=1)
    wm.add("S1", "superstate", "nil")
    el = Elaborator([apply_go, elab, apply_clear])

    # decision 1: operator 'go' selected -> apply (o-support) + elab (i-support)
    wm.add("S1", "operator", "Ogo"); wm.add("Ogo", "name", "go")
    el.settle(wm)
    # operator 'go' deselected on the next decision
    wm.remove("S1", "operator", "Ogo")
    el.settle(wm)
    # decision 2: operator 'clear' selected -> rejects ^marker
    wm.add("S1", "operator", "Oclear"); wm.add("Oclear", "name", "clear")
    el.settle(wm)
    wm.remove("S1", "operator", "Oclear")
    el.settle(wm)

    augs: dict = {}
    for (i, a, v) in wm:
        if i == "S1":
            augs.setdefault(a, set()).add(v)
    return augs


@unittest.skipUnless(soar_available(), "C++ Soar oracle not built at ~/Desktop/Soar/out/soar")
class TestOracleRetraction(unittest.TestCase):
    def test_truth_maintenance_matches_oracle(self):
        oracle = run_agent_state(ORACLE_AGENT)
        pysoar = pysoar_final_state()
        for attr in DISCRIMINATING:
            self.assertEqual(
                pysoar.get(attr, set()), oracle.get(attr, set()),
                f"[^{attr}] pysoar={pysoar.get(attr, set())} oracle={oracle.get(attr, set())}",
            )

    def test_discriminating_expectations(self):
        # pin the ground truth explicitly too (documents what 'correct' is)
        oracle = run_agent_state(ORACLE_AGENT)
        self.assertEqual(oracle.get("trophy", set()), {"won"})   # o-support persisted
        self.assertEqual(oracle.get("marker", set()), set())     # rejected
        self.assertEqual(oracle.get("derived", set()), set())    # i-support retracted


if __name__ == "__main__":
    unittest.main(verbosity=2)
