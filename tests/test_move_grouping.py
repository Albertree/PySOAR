# tests/test_move_grouping.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as PA


class TestGridBlobAntiunify(unittest.TestCase):
    def _grid_blob(self, cells, col):
        b = [PA.step("coloring", target=PA.cellset(PA.const(cells)), color=PA.const(col))]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_with_blob_contents_recurses(self):
        a = self._grid_blob([7, 8], 3)
        b = self._grid_blob([20, 21], 3)          # 같은 색, cellset DIFF
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        parts = {s["call"]: s["args"] for s in sk["body"]}
        inner = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertEqual(inner[0]["args"]["target"]["ref"], "cellset")
        self.assertTrue(any(k.startswith("?c.cells") for k in slots))
