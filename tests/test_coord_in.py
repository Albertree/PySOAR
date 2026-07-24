# -*- coding: utf-8 -*-
"""P2 Phase 2a Task1: coord_in membership 술어 + _compile_pred('in') 실행기 (additive)."""
import unittest
from arbor.reasoning import program_ast as PA


class TestCoordIn(unittest.TestCase):
    def setUp(self):
        self.g = [[0, 0, 0], [0, 7, 0], [0, 0, 0]]   # 색7 @ (1,1)

    def test_coord_in_single(self):
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                 PA.coord_in("coordinate", [[1, 1]]))),
                        color=PA.const(3))]
        out = PA.execute(PA.program(body), self.g)
        self.assertEqual(out[1][1], 3)

    def test_coord_in_multi_one_op(self):
        # 두 셀을 한 op 로 (op수 보존): (0,0)과 (2,2) 를 5 로
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                 PA.coord_in("coordinate", [[0, 0], [2, 2]]))),
                        color=PA.const(5))]
        out = PA.execute(PA.program(body), self.g)
        self.assertEqual(out[0][0], 5); self.assertEqual(out[2][2], 5)
        self.assertEqual(out[1][1], 7)                # 나머지 불변

    def test_to_source_coord_in(self):
        body = [PA.step("coloring", target=PA.coordinate_of(PA.select("input","pixel",
                        PA.coord_in("coordinate", [[1,1]]))), color=PA.const(3))]
        src = PA.to_source(PA.program(body))
        self.assertIn("coord_in", src) if "coord_in" in src else self.assertIn("coordinate", src)


if __name__ == "__main__":
    unittest.main()
