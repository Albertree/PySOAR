"""
ARC environment (3-submit retry) + end-to-end run on REAL data.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_environment -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.env.environment import ARCEnvironment, grids_equal  # noqa: E402

EASY_A = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
ARCKG_OK = os.path.isdir(os.path.expanduser("~/Desktop/ARC-solver/ARCKG"))

TASK = {"train": [{"input": [[0]], "output": [[1]]}],
        "test": [{"input": [[0]], "output": [[1, 1], [1, 1]]}]}
# two test pairs -- each must be solved separately, with its own 3 attempts
TWO_TEST = {"train": [{"input": [[0]], "output": [[2]]}],
            "test": [{"input": [[0]], "output": [[2]]},
                     {"input": [[0]], "output": [[3]]}]}


class TestEnvironment(unittest.TestCase):
    def test_correct_answer_scores_and_advances(self):
        env = ARCEnvironment([("t1", TASK)], max_attempts=3)
        env.reset()
        reward, nxt, done, info = env.step([[1, 1], [1, 1]])
        self.assertEqual(reward, 1.0)
        self.assertTrue(info["correct"])
        self.assertIsNone(nxt)
        self.assertTrue(done)

    def test_wrong_answer_allows_retry_up_to_three(self):
        env = ARCEnvironment([("t1", TASK)], max_attempts=3)
        ctx = env.reset()
        r1, ctx, d1, i1 = env.step([[9]])           # wrong
        self.assertEqual(r1, 0.0)
        self.assertEqual(i1["attempts_left"], 2)
        self.assertTrue(i1["can_retry"])
        self.assertEqual(ctx["test_index"], 0)       # still the SAME test pair
        env.step([[9]])
        r3, ctx, d3, i3 = env.step([[9]])            # attempts exhausted
        self.assertEqual(i3["attempts_left"], 0)
        self.assertFalse(i3["can_retry"])

    def test_each_test_pair_solved_separately_with_fresh_attempts(self):
        # two test pairs: solve pair 0, then pair 1 gets a FRESH 3 attempts
        env = ARCEnvironment([("t", TWO_TEST)], max_attempts=3)
        ctx = env.reset()
        self.assertEqual(ctx["test_index"], 0)
        r, ctx, d, info = env.step([[2]])            # pair 0 correct
        self.assertEqual(r, 1.0)
        self.assertEqual(ctx["test_index"], 1)       # advanced to pair 1
        self.assertEqual(ctx["attempts_left"], 3)    # FRESH attempts for pair 1
        # task not solved until BOTH pairs solved
        self.assertFalse(env.task_solved("t"))
        r, ctx, d, info = env.step([[3]])            # pair 1 correct
        self.assertTrue(env.task_solved("t"))
        self.assertIsNone(ctx)

    def test_one_test_pair_failed_means_task_unsolved(self):
        env = ARCEnvironment([("t", TWO_TEST)], max_attempts=2)
        env.reset()
        env.step([[2]])                              # pair 0 ok
        env.step([[9]]); env.step([[9]])             # pair 1 fails both attempts
        self.assertFalse(env.task_solved("t"))
        self.assertEqual(env.solved_tasks(), 0)

    def test_grids_equal(self):
        self.assertTrue(grids_equal([[1, 2]], [[1, 2]]))
        self.assertFalse(grids_equal([[1, 2]], [[1, 3]]))
        self.assertFalse(grids_equal([[1]], [[1, 1]]))


@unittest.skipUnless(os.path.isdir(EASY_A) and ARCKG_OK, "data/ARCKG not present")
class TestEndToEnd(unittest.TestCase):
    def test_run_easy_a_through_environment(self):
        from legacy.run import run
        r = run("easy_a", quiet=True)
        self.assertEqual(r["solved"], 9)         # all 9 real single-pixel tasks
        self.assertEqual(r["n"], 9)

    def test_unseen_easy_is_honestly_partial(self):
        # the hypothesis space was tuned on easy_a; on unseen 'easy' it is partial,
        # NOT perfect -- this test pins the HONEST baseline (no overclaiming).
        from legacy.run import run
        r = run("easy", quiet=True)
        self.assertLess(r["solved"], r["n"])     # not all solved
        self.assertGreater(r["solved"], 0)       # but some generalize


if __name__ == "__main__":
    unittest.main(verbosity=2)
