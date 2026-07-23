# -*- coding: utf-8 -*-
"""P1 Task2: select-target coloring 실행기 = cellset 과 동치(pixel-level)."""
import unittest
from arbor.reasoning import program_ast as PA


class TestGrammarAExecute(unittest.TestCase):
    def setUp(self):
        # move000a train0 input (8x8, 색7 픽셀 @ (3,2))
        self.g0 = [[0] * 8 for _ in range(8)]
        self.g0[3][2] = 7

    def test_select_pixel_by_coordinate_recolors(self):
        # (3,2) 셀을 0 으로 칠함 = "원위치 비움"
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_coordinate", [3, 2]))),
                        color=PA.const(0))]
        out = PA.execute(PA.program(body), self.g0)
        expect = [[0] * 8 for _ in range(8)]                 # (3,2) 도 0 → 전부 0
        self.assertEqual(out, expect)

    def test_select_paint_matches_cellset(self):
        # (4,3) 셀을 7 로 칠함 — cellset([35]) 프로그램과 동일 결과여야
        W = 8
        sel_prog = PA.program([PA.step("coloring",
                     target=PA.coordinate_of(PA.select("input", "pixel",
                              PA.eq("pixel_coordinate", [4, 3]))), color=PA.const(7))])
        cell_prog = PA.program([PA.step("coloring",
                     target=PA.cellset(PA.const([4 * W + 3])), color=PA.const(7))])
        self.assertEqual(PA.execute(sel_prog, self.g0), PA.execute(cell_prog, self.g0))

    def test_select_pixel_by_color(self):
        # 색7 픽셀을 3 으로 — pixel_color 술어
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_color", 7))),
                        color=PA.const(3))]
        out = PA.execute(PA.program(body), self.g0)
        self.assertEqual(out[3][2], 3)


if __name__ == "__main__":
    unittest.main()
