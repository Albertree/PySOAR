# tests/test_move_grouping.py
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as PA
from procedural_memory.operators import compress as CG


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


class TestGridInnerCounts(unittest.TestCase):
    def _grid_pixel(self, idxs):
        b = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(0)) for i in idxs]
        return PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                               PA.contents_program(b))

    def test_grid_inner_op_counts_reads_contents_length(self):
        self.assertEqual(PA.grid_inner_op_counts(self._grid_pixel([1, 2, 3])), [3])

    def test_grid_inner_op_counts_none_for_nongrid(self):
        flat = PA.program([PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(0))])
        self.assertIsNone(PA.grid_inner_op_counts(flat))


class TestCompressGridWrapped(unittest.TestCase):
    def test_grid_pixel_program_compresses_inner_keeps_wrapper(self):
        # 잔여 4셀(=2셀 객체 이동): W=5. 나간자리 idx 0,1(색0); 들어온자리 idx 12,13(색3)
        inner = [PA.step("coloring", target=PA.ref("pixel", PA.const(i)), color=PA.const(c))
                 for i, c in [(0, 0), (1, 0), (12, 3), (13, 3)]]
        gp = PA.grid_program(PA.expr("size(input_grid)"), PA.expr("color(input_grid)"),
                             PA.contents_program(inner))
        out = json.loads(CG._blob_program(json.dumps(gp), 5))
        parts = {s["call"]: s["args"] for s in out["body"]}
        self.assertIn("set_grid_size", parts)                 # 래퍼 유지
        blob_body = parts["set_grid_contents"]["contents"]["program"]["body"]
        self.assertTrue(all(s["args"]["target"]["ref"] == "cellset" for s in blob_body))
        self.assertEqual(len(blob_body), 2)                   # 2 덩어리(나간/들어온)
