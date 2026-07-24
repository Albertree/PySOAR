"""
Differential test: PySOAR vs the real C++ Soar kernel (the oracle).

For each preference scenario we assert that PySOAR's IMPASSE TYPE matches what
SoarGroup/Soar actually decides. Winner identity is also checked except for
fully-indifferent sets, where Soar's choice depends on internal candidate
ordering / its (default stochastic) exploration policy -- a documented
DESIGN-FREE point, see docs/AUDIT.md.

Skips automatically if ~/Desktop/Soar/out/soar is not built.

Run: cd ~/Desktop/PySOAR && python -m unittest tests.test_oracle_diff -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Slot, decide_context_slot  # noqa: E402
from tests.oracle.soar_oracle import ask_oracle, soar_available  # noqa: E402

# (name, slot, winner_is_determinate)
CASES = [
    ("single", Slot().acceptable("O1"), True),
    ("tie2", Slot().acceptable("O1", "O2"), True),
    ("tie3", Slot().acceptable("O1", "O2", "O3"), True),
    ("reject", Slot().acceptable("O1", "O2").reject("O2"), True),
    ("prohibit", Slot().acceptable("O1", "O2").prohibit("O1"), True),
    ("all-rejected", Slot().acceptable("O1", "O2").reject("O1", "O2"), True),
    ("best", Slot().acceptable("O1", "O2", "O3").best("O2"), True),
    ("two-best-tie", Slot().acceptable("O1", "O2", "O3").best("O1").best("O2"), True),
    ("worst", Slot().acceptable("O1", "O2").worst("O2"), True),
    ("best-over-worst", Slot().acceptable("O1", "O2").best("O1").worst("O2"), True),
    ("better", Slot().acceptable("O1", "O2").better("O1", "O2"), True),
    ("worse", Slot().acceptable("O1", "O2").worse("O2", "O1"), True),
    ("chain", Slot().acceptable("A", "B", "C").better("A", "B").better("B", "C"), True),
    ("conflict2", Slot().acceptable("O1", "O2").better("O1", "O2").better("O2", "O1"), True),
    ("conflict3",
     Slot().acceptable("A", "B", "C").better("A", "B").better("B", "C").better("C", "A"),
     True),
    ("unrelated-better", Slot().acceptable("A", "B", "C").better("A", "B"), True),
    # fully indifferent -> winner is design-free, only impasse type is asserted
    ("indiff-binary", Slot().acceptable("O1", "O2").indifferent("O1", "O2"), False),
]


@unittest.skipUnless(soar_available(), "C++ Soar oracle not built at ~/Desktop/Soar/out/soar")
class TestOracleDifferential(unittest.TestCase):
    pass


def _make(name, slot, determinate):
    def test(self):
        p_imp, p_cand = decide_context_slot(slot)
        o_imp, o_cand = ask_oracle(slot)
        self.assertEqual(
            p_imp, o_imp,
            f"[{name}] impasse type: pysoar={p_imp.name} oracle={o_imp.name}",
        )
        if determinate and o_imp.name == "NONE" and o_cand:
            self.assertEqual(
                p_cand, o_cand,
                f"[{name}] winner: pysoar={p_cand} oracle={o_cand}",
            )
    return test


for _name, _slot, _det in CASES:
    setattr(TestOracleDifferential, f"test_{_name.replace('-', '_')}",
            _make(_name, _slot, _det))


if __name__ == "__main__":
    unittest.main(verbosity=2)
