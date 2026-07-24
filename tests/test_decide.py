"""
Unit tests for preference semantics -- the executable spec derived directly
from decide.cpp:run_preference_semantics. Each test names the canonical SOAR
behaviour it pins down.

Run: cd ~/Desktop/PySOAR && python -m pytest -q
(or: python -m unittest discover -s tests)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.soar import ImpasseType, Slot, decide_context_slot, run_preference_semantics  # noqa: E402


def rps(slot):
    return run_preference_semantics(slot)


class TestTrivial(unittest.TestCase):
    def test_no_preferences(self):
        self.assertEqual(rps(Slot()), (ImpasseType.NONE, []))

    def test_single_acceptable_selected(self):
        s = Slot().acceptable("O1")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_duplicate_acceptable_is_one_candidate(self):
        s = Slot().acceptable("O1", "O1")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))


class TestRequire(unittest.TestCase):
    def test_single_require_wins(self):
        s = Slot().acceptable("O1", "O2").require("O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O2"]))

    def test_two_requires_constraint_failure(self):
        s = Slot().require("O1", "O2")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.CONSTRAINT_FAILURE)
        self.assertEqual(set(cands), {"O1", "O2"})

    def test_required_and_prohibited_constraint_failure(self):
        # The one difference between prohibit and reject: require+prohibit fails.
        s = Slot().require("O1").prohibit("O1")
        self.assertEqual(rps(s), (ImpasseType.CONSTRAINT_FAILURE, ["O1"]))

    def test_required_and_rejected_still_wins(self):
        # require beats reject (reject does NOT cause constraint failure)
        s = Slot().require("O1").reject("O1")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))


class TestAcceptableRejectProhibit(unittest.TestCase):
    def test_reject_removes_candidate(self):
        s = Slot().acceptable("O1", "O2").reject("O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_prohibit_removes_candidate(self):
        s = Slot().acceptable("O1", "O2").prohibit("O1")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O2"]))

    def test_all_rejected_no_candidates(self):
        s = Slot().acceptable("O1", "O2").reject("O1", "O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, []))

    def test_two_acceptables_tie(self):
        s = Slot().acceptable("O1", "O2")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"O1", "O2"})


class TestBetterWorse(unittest.TestCase):
    def test_better_prunes_worse(self):
        s = Slot().acceptable("O1", "O2").better("O1", "O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_worse_is_symmetric_to_better(self):
        s = Slot().acceptable("O1", "O2").worse("O2", "O1")  # O2 worse than O1
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_transitive_chain(self):
        s = Slot().acceptable("A", "B", "C").better("A", "B").better("B", "C")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["A"]))

    def test_two_cycle_conflict(self):
        s = Slot().acceptable("O1", "O2").better("O1", "O2").better("O2", "O1")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.CONFLICT)
        self.assertEqual(set(cands), {"O1", "O2"})

    def test_three_cycle_conflict(self):
        s = (Slot().acceptable("A", "B", "C")
             .better("A", "B").better("B", "C").better("C", "A"))
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.CONFLICT)
        self.assertEqual(set(cands), {"A", "B", "C"})

    def test_unrelated_better_leaves_tie(self):
        # A>B but C unrelated -> A and C survive -> tie
        s = Slot().acceptable("A", "B", "C").better("A", "B")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"A", "C"})


class TestBestWorst(unittest.TestCase):
    def test_best_selects(self):
        s = Slot().acceptable("O1", "O2", "O3").best("O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O2"]))

    def test_best_on_noncandidate_is_noop(self):
        # best references O9 which is not a candidate -> ignored -> tie remains
        s = Slot().acceptable("O1", "O2").best("O9")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"O1", "O2"})

    def test_two_bests_tie(self):
        s = Slot().acceptable("O1", "O2", "O3").best("O1").best("O2")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"O1", "O2"})

    def test_worst_dropped(self):
        s = Slot().acceptable("O1", "O2").worst("O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_all_worst_has_no_effect(self):
        # every candidate worst -> worst ignored -> tie
        s = Slot().acceptable("O1", "O2").worst("O1").worst("O2")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"O1", "O2"})

    def test_best_beats_worst_ordering(self):
        # best stage runs before worst: O1 best, O2 worst -> O1
        s = Slot().acceptable("O1", "O2").best("O1").worst("O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))


class TestIndifferent(unittest.TestCase):
    def test_unary_indifferent_resolves_first(self):
        s = Slot().acceptable("O1", "O2").indifferent("O1").indifferent("O2")
        # fully indifferent -> deterministic first (insertion order)
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_binary_indifferent_resolves(self):
        s = Slot().acceptable("O1", "O2").indifferent("O1", "O2")
        self.assertEqual(rps(s), (ImpasseType.NONE, ["O1"]))

    def test_partial_indifferent_still_tie(self):
        # O1=O2 but O3 not indifferent to anything -> tie
        s = Slot().acceptable("O1", "O2", "O3").indifferent("O1", "O2")
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.TIE)
        self.assertEqual(set(cands), {"O1", "O2", "O3"})

    def test_numeric_indifferent_resolves(self):
        s = (Slot().acceptable("O1", "O2")
             .numeric_indifferent("O1", 1.0).numeric_indifferent("O2", 2.0))
        # numeric indifferents are mutually indifferent -> single winner
        imp, cands = rps(s)
        self.assertEqual(imp, ImpasseType.NONE)
        self.assertEqual(len(cands), 1)


class TestContextSlotMapping(unittest.TestCase):
    def test_selection(self):
        s = Slot().acceptable("O1")
        self.assertEqual(decide_context_slot(s), (ImpasseType.NONE, ["O1"]))

    def test_no_candidates_is_state_no_change(self):
        s = Slot().acceptable("O1").reject("O1")
        self.assertEqual(decide_context_slot(s), (ImpasseType.SNC, []))

    def test_tie_passthrough(self):
        s = Slot().acceptable("O1", "O2")
        imp, _ = decide_context_slot(s)
        self.assertEqual(imp, ImpasseType.TIE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
