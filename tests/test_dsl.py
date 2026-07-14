"""
DSL argument-expression resolution (arc/dsl.py + arc/expr_solver.py): output is
built by make_grid + coloring; each argument is resolved to the most GENERAL
expression over ARCKG properties. Specific value -> general expression.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_dsl -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ARCKG_OK = os.path.isdir(os.path.expanduser("~/Desktop/ARC-solver/ARCKG"))
EASY_A = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")


@unittest.skipUnless(ARCKG_OK, "ARCKG not present")
class TestDSL(unittest.TestCase):
    def test_two_frozen_transformations(self):
        from procedural_memory.dsl.helpers import make_grid, coloring
        g = make_grid({"height": 2, "width": 2}, fill=0)
        g = coloring(g, (1, 1), 5)
        self.assertEqual(g, [[0, 0], [0, 5]])

    def test_specific_value_becomes_general_expression(self):
        # constant (5,5) on 6x6 grids must resolve to corner-br (general),
        # NOT literal (5,5) -- the whole point of expression resolution.
        from procedural_memory.dsl.helpers import context, resolve_arguments

        class O:
            pass
        def obj(r, c, color):
            return {"cells": frozenset({(r, c)}), "color": color}
        # two pairs, same output (5,5), different input objects
        in0 = [[0] * 6 for _ in range(6)]
        samples = []
        for (ir, ic) in [(1, 1), (1, 4)]:
            ctx = context(obj(ir, ic, 2), in0, (6, 6))
            samples.append({"ctx": ctx, "out_coord": (5, 5), "out_color": 2,
                            "out_size": (6, 6), "out_bg": 0})
        args = resolve_arguments(samples)
        self.assertEqual(args["position"][1], "corner-br")  # general, not literal

    def test_translation_resolves_to_coord_plus_delta(self):
        from procedural_memory.dsl.helpers import context, resolve_arguments
        def obj(r, c, color):
            return {"cells": frozenset({(r, c)}), "color": color}
        in0 = [[0] * 6 for _ in range(6)]
        samples = []
        for (ir, ic, orr, occ) in [(1, 1, 2, 0), (1, 4, 2, 3)]:  # delta (+1,-1)
            ctx = context(obj(ir, ic, 2), in0, (6, 6))
            samples.append({"ctx": ctx, "out_coord": (orr, occ), "out_color": 2,
                            "out_size": (6, 6), "out_bg": 0})
        args = resolve_arguments(samples)
        self.assertEqual(args["position"][1], "coord_of(obj)+(1, -1)")

    @unittest.skipUnless(os.path.isdir(EASY_A), "dataset not present")
    def test_easy_a_via_expressions(self):
        from arbor.expr_solver import _bench
        s, n = _bench("easy_a")
        self.assertEqual((s, n), (9, 9))

    def test_relation_expression_coord_of_other(self):
        # position = coord_of(another object) -- a RELATION expression that
        # property-only expressions cannot produce.
        from procedural_memory.dsl.helpers import context, resolve_arguments

        def obj(r, c, color):
            return {"cells": frozenset({(r, c)}), "color": color}
        in0 = [[0] * 6 for _ in range(6)]
        pairs = []
        # target (color 2) ends up where the marker (color 1) was
        for (tr, tc, mr, mc) in [(1, 1, 4, 4), (2, 3, 0, 5)]:
            ctx = context(obj(tr, tc, 2), in0, (6, 6), others=[obj(mr, mc, 1)])
            pairs.append({"ctx": ctx, "out_coord": (mr, mc), "out_color": 2,
                          "out_size": (6, 6), "out_bg": 0})
        args = resolve_arguments(pairs)
        self.assertIn("coord_of(other", args["position"][1])   # relation, not literal

    def test_relation_color_of_other(self):
        from procedural_memory.dsl.helpers import context, resolve_arguments

        def obj(r, c, color):
            return {"cells": frozenset({(r, c)}), "color": color}
        in0 = [[0] * 4 for _ in range(4)]
        pairs = []
        # target recoloured to the marker's colour (position unchanged)
        for (tc, mc) in [(2, 7), (2, 9)]:
            ctx = context(obj(0, 0, 2), in0, (4, 4), others=[obj(3, 3, mc)])
            pairs.append({"ctx": ctx, "out_coord": (0, 0), "out_color": mc,
                          "out_size": (4, 4), "out_bg": 0})
        args = resolve_arguments(pairs)
        self.assertIn("color_of(other", args["color"][1])

    @unittest.skipUnless(os.path.isdir(EASY_A), "dataset not present")
    def test_retry_diversification_beats_single_submit(self):
        # the 3-submit retry (ranked candidates) must solve strictly more than a
        # single submit on the ambiguous 'easy' set -- the wiki's reject->next.
        from arbor.expr_solver import candidates
        from arbor.env.dataset import list_tasks, load_task

        def solved_within(k):
            s = 0
            for _tid, path in list_tasks("easy"):
                t = load_task(path)
                gt = [tp["output"] for tp in t["test"]]
                cs = candidates(t, 3)
                if any(c["grid"] == gt for c in cs[:k]):
                    s += 1
            return s
        one, three = solved_within(1), solved_within(3)
        self.assertGreater(three, one)        # retry helps
        self.assertGreaterEqual(three, 13)    # honest baseline (was 6 single-shot)

    def test_candidate_covers_all_test_pairs(self):
        # a candidate answer is a LIST of grids, one per test pair (the env scores
        # all-or-nothing across test pairs).
        from arbor.expr_solver import candidates
        from arbor.env.dataset import list_tasks, load_task
        t = load_task(list_tasks("easy")[0][1])
        cs = candidates(t, 3)
        self.assertTrue(cs)
        self.assertEqual(len(cs[0]["grid"]), len(t["test"]))

    @unittest.skipUnless(os.path.isdir(EASY_A), "dataset not present")
    def test_declines_on_contradictory_task(self):
        # same input -> different output: no input-based expression exists;
        # the solver must DECLINE (answer None), not crash or guess.
        from arbor.expr_solver import solve
        task = {
            "train": [
                {"input": [[0, 0], [0, 2]], "output": [[2, 0], [0, 0]]},
                {"input": [[0, 0], [0, 2]], "output": [[0, 0], [0, 2]]},  # contradicts
            ],
            "test": [{"input": [[0, 0], [0, 2]], "output": [[2, 0], [0, 0]]}],
        }
        r = solve(task)
        self.assertIsNone(r["answer"])
        self.assertFalse(r["correct"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
