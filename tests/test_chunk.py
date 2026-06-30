"""
Unit tests for milestone 4: explanation-based chunking (backtracing).
Executable spec for: result detection, backtracing grounds vs locals, and
variablization. Mirrors ebc_build.cpp:218 + ebc_backtrace.cpp:104.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_chunk -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Action, Agent, Cond, Production  # noqa: E402


def compute_productions():
    """Top state computes ^a/^b, proposes 'solve' with no apply rule -> operator
    no-change substate -> a substate rule computes a result from the superstate
    data. The classic chunking scenario."""
    return [
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


def chunk_struct(ch):
    """(frozenset{(attr, 'VAR'|const)}, (attr, 'VAR'|const)) for a PySOAR chunk."""
    from pysoar.production import is_var
    cset = frozenset((c.attr, "VAR" if is_var(c.value) else c.value) for c in ch.conditions)
    a = ch.actions[0]
    return (cset, (a.attr, "VAR" if is_var(a.value) else a.value))


class TestChunking(unittest.TestCase):
    def test_learns_one_chunk(self):
        ag = Agent(compute_productions(), learn=True)
        for _ in range(6):
            ag.step()
        self.assertEqual(len(ag.chunks), 1)

    def test_chunk_structure(self):
        ag = Agent(compute_productions(), learn=True)
        for _ in range(6):
            ag.step()
        ch = ag.chunks[0]
        # conditions test the superstate's ^a and ^b (values variablized);
        # action writes ^result computed (constant kept)
        self.assertEqual(
            chunk_struct(ch),
            (frozenset({("a", "VAR"), ("b", "VAR")}), ("result", "computed")),
        )

    def test_chunk_single_identifier(self):
        # all conditions + action share one variablized state identifier
        ag = Agent(compute_productions(), learn=True)
        for _ in range(6):
            ag.step()
        ch = ag.chunks[0]
        ids = {c.id for c in ch.conditions} | {ch.actions[0].id}
        self.assertEqual(len(ids), 1)

    def test_no_chunk_without_learning(self):
        ag = Agent(compute_productions(), learn=False)
        for _ in range(6):
            ag.step()
        self.assertEqual(len(ag.chunks), 0)

    def test_chunk_fires_on_fresh_state(self):
        # the learned chunk should produce the result DIRECTLY (no substate) when
        # the same superstate data appears -- the whole point of chunking.
        ag = Agent(compute_productions(), learn=True)
        for _ in range(6):
            ag.step()
        learned = ag.chunks[0]

        # fresh agent that just has ^a/^b present, plus only the learned chunk.
        # the chunk is the ONLY production, so if the result appears it was
        # produced directly by the chunk -- no original substate path needed.
        fresh = Agent([learned])
        fresh.wm.add("S1", "a", "1")
        fresh.wm.add("S1", "b", "2")
        fresh.elaborator.settle(fresh.wm)        # one elaboration phase
        self.assertTrue(fresh.wm.contains("S1", "result", "computed"))

    def test_constant_condition_stays_constant(self):
        # if the substate rule tests a CONSTANT superstate value, the chunk keeps
        # it constant (not variablized)
        prods = [
            Production("propose-init",
                       [Cond("S1", "superstate", "nil"), Cond("S1", "k", "<x>", negated=True)],
                       [Action("S1", "operator", "init", "+")]),
            Production("apply-init", [Cond("S1", "operator", "init")], [Action("S1", "k", "7")]),
            Production("propose-solve",
                       [Cond("S1", "superstate", "nil"), Cond("S1", "k", "<kv>"),
                        Cond("S1", "result", "<r>", negated=True)],
                       [Action("S1", "operator", "solve", "+")]),
            Production("compute",
                       [Cond("<s>", "impasse", "no-change"), Cond("<s>", "superstate", "<ss>"),
                        Cond("<ss>", "k", "7")],   # CONSTANT test
                       [Action("<ss>", "result", "ok")]),
        ]
        ag = Agent(prods, learn=True)
        for _ in range(6):
            ag.step()
        self.assertEqual(len(ag.chunks), 1)
        self.assertEqual(
            chunk_struct(ag.chunks[0]),
            (frozenset({("k", "7")}), ("result", "ok")),  # k stays constant 7
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
