"""
Differential test for milestone 4: the chunk PySOAR learns vs the chunk the real
C++ kernel learns, on the same agent. Compares the structural signature
(condition (attr, var?/const) set + result), robust to variable names.

Oracle agent (chunk always):
    propose-init -> apply-init writes ^a 1 ^b 2 (o-support)
    propose-solve (needs ^a, not ^result) -> no apply at top -> operator no-change
    compute (in substate) reads superstate ^a/^b -> writes ^result computed
Soar learns:  (state <s1> ^a <a1> ^b <b1>) --> (<s1> ^result computed)

Skips if ~/Desktop/Soar/out/soar is not built.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Action, Agent, Cond, Production  # noqa: E402
from soar.production import is_var  # noqa: E402
from oracle.soar_oracle import learn_chunk_signature, soar_available  # noqa: E402

SOAR_AGENT = r"""
chunk always
sp {propose-init (state <s> ^superstate nil -^a) --> (<s> ^operator <o> +) (<o> ^name init)}
sp {apply-init (state <s> ^operator <o> ^superstate nil) (<o> ^name init) --> (<s> ^a 1) (<s> ^b 2)}
sp {propose-solve (state <s> ^superstate nil ^a <av> -^result) --> (<s> ^operator <o> +) (<o> ^name solve)}
sp {compute (state <s> ^impasse no-change ^superstate <ss>) (<ss> ^a <a> ^b <b>) --> (<ss> ^result computed)}
watch 0
run 10
print --chunks --full
"""

PYSOAR_AGENT = [
    Production("propose-init",
               [Cond("S1", "superstate", "nil"), Cond("S1", "a", "<x>", negated=True)],
               [Action("S1", "operator", "init", "+")]),
    Production("apply-init", [Cond("S1", "operator", "init")],
               [Action("S1", "a", "1"), Action("S1", "b", "2")]),
    Production("propose-solve",
               [Cond("S1", "superstate", "nil"), Cond("S1", "a", "<av>"),
                Cond("S1", "result", "<r>", negated=True)],
               [Action("S1", "operator", "solve", "+")]),
    Production("compute",
               [Cond("<s>", "impasse", "no-change"), Cond("<s>", "superstate", "<ss>"),
                Cond("<ss>", "a", "<a>"), Cond("<ss>", "b", "<b>")],
               [Action("<ss>", "result", "computed")]),
]


def pysoar_chunk_signature():
    ag = Agent(PYSOAR_AGENT, learn=True)
    for _ in range(6):
        ag.step()
    if not ag.chunks:
        return None
    ch = ag.chunks[0]
    cset = frozenset((c.attr, "VAR" if is_var(c.value) else c.value) for c in ch.conditions)
    a = ch.actions[0]
    return (cset, (a.attr, "VAR" if is_var(a.value) else a.value))


@unittest.skipUnless(soar_available(), "C++ Soar oracle not built at ~/Desktop/Soar/out/soar")
class TestOracleChunk(unittest.TestCase):
    def test_learned_chunk_matches_oracle(self):
        oracle = learn_chunk_signature(SOAR_AGENT)
        pysoar = pysoar_chunk_signature()
        self.assertIsNotNone(oracle, "oracle learned no chunk")
        self.assertIsNotNone(pysoar, "pysoar learned no chunk")
        self.assertEqual(pysoar, oracle, f"\n pysoar={pysoar}\n oracle={oracle}")

    def test_oracle_chunk_is_expected(self):
        # pin the ground truth
        oracle = learn_chunk_signature(SOAR_AGENT)
        self.assertEqual(
            oracle,
            (frozenset({("a", "VAR"), ("b", "VAR")}), ("result", "computed")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
