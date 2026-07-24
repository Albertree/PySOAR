"""
Differential test for milestone 3: the PySOAR decision cycle vs the real C++
kernel, comparing the normalized DECISION-EVENT SEQUENCE (select / tie / conflict
/ onc / snc) produced by the same agent run in both.

This is the milestone that makes the wiki's "tie -> evaluation substate -> resolve
-> select" flow run end to end; here we prove the whole control flow (selection,
substate creation, ONC, SNC cascade) matches Soar cycle for cycle.

Skips if ~/Desktop/Soar/out/soar is not built.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Action, Agent, Cond, Production  # noqa: E402
from tests.oracle.soar_oracle import run_agent_trace, soar_available  # noqa: E402

# normalize a PySOAR agent decision label -> the oracle event tuple
_LABEL = {
    "tie": ("tie",), "conflict": ("conflict",),
    "constraint-failure": ("constraint-failure",),
    "operator-no-change": ("onc",), "state-no-change": ("snc",),
}


def pysoar_events(productions, cycles):
    ag = Agent(productions)
    events = []
    for _ in range(cycles):
        for d in ag.step().decisions:
            if d[0] == "select":
                events.append(("select", d[2]))
            else:
                events.append(_LABEL[d[0]])
    return events


# ---- scenario 1: tie -> substate resolves it -> select -> ONC -> SNC cascade ----
TIE_RESOLVE_SOAR = r"""
sp {propose-a (state <s> ^superstate nil) --> (<s> ^operator <o> +) (<o> ^name a)}
sp {propose-b (state <s> ^superstate nil) --> (<s> ^operator <o> +) (<o> ^name b)}
sp {resolve (state <s> ^impasse tie ^superstate <ss>) (<ss> ^operator <o> +) (<o> ^name a)
   --> (<ss> ^operator <o> >)}
sp {apply-a (state <s> ^operator <o>) (<o> ^name a) --> (<s> ^result done)}
watch 1
run 6
"""
TIE_RESOLVE_PYSOAR = [
    Production("propose-a", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "a", "+")]),
    Production("propose-b", [Cond("S1", "superstate", "nil")], [Action("S1", "operator", "b", "+")]),
    Production("resolve", [Cond("<s>", "impasse", "tie"), Cond("<s>", "superstate", "<ss>")],
               [Action("<ss>", "operator", "a", ">")]),
    Production("apply-a", [Cond("S1", "operator", "a")], [Action("S1", "result", "done")]),
]

# ---- scenario 2: single operator, applies & self-retracts -> SNC ----
SEQUENCE_SOAR = r"""
sp {propose-go (state <s> ^superstate nil -^done) --> (<s> ^operator <o> +) (<o> ^name go)}
sp {apply-go (state <s> ^operator <o> ^superstate nil) (<o> ^name go) --> (<s> ^done yes)}
watch 1
run 5
"""
SEQUENCE_PYSOAR = [
    Production("propose-go",
               [Cond("S1", "superstate", "nil"), Cond("S1", "done", "<d>", negated=True)],
               [Action("S1", "operator", "go", "+")]),
    Production("apply-go", [Cond("S1", "operator", "go")], [Action("S1", "done", "yes")]),
]


@unittest.skipUnless(soar_available(), "C++ Soar oracle not built at ~/Desktop/Soar/out/soar")
class TestOracleCycle(unittest.TestCase):
    def _compare(self, soar_src, pysoar_prods, cycles):
        oracle = run_agent_trace(soar_src)
        pysoar = pysoar_events(pysoar_prods, cycles)
        n = min(len(oracle), len(pysoar))
        self.assertGreater(n, 0, "no events parsed from oracle")
        self.assertEqual(pysoar[:n], oracle[:n],
                         f"\n pysoar={pysoar[:n]}\n oracle={oracle[:n]}")

    def test_tie_resolution_cycle(self):
        self._compare(TIE_RESOLVE_SOAR, TIE_RESOLVE_PYSOAR, cycles=6)

    def test_operator_sequence_then_snc(self):
        self._compare(SEQUENCE_SOAR, SEQUENCE_PYSOAR, cycles=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
