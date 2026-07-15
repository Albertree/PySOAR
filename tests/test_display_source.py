# -*- coding: utf-8 -*-
import unittest
from arbor.reasoning import program_ast as PA
from debugger.reports.program_viewer import display_source


class TestDisplaySource(unittest.TestCase):
    def test_grid_keep_and_const(self):
        ast = PA.grid_program(PA.keep("size"),
                              PA.const([0, 2]),
                              PA.const([[0, 0], [0, 2]]))
        src = display_source(ast)
        self.assertIn("g = input_grid", src)
        self.assertIn("set_grid_size(g, size(input_grid))", src)   # keep -> ARCKG size
        self.assertIn("set_grid_color(g, [0, 2])", src)
        self.assertIn("set_grid_contents(g, [[0, 0], [0, 2]])", src)  # 실 2D 배열
        self.assertIn("output_grid = g", src)
        for banned in ("keep", "grid[", "∘", "tfg", "apply_DSL"):
            self.assertNotIn(banned, src)

    def test_pixel_coloring(self):
        ast = PA.program([
            PA.step("coloring", target=PA.ref("pixel", PA.const(7)), color=PA.const(0)),
            PA.step("coloring", target=PA.ref("pixel", PA.const(35)), color=PA.const(2)),
        ])
        src = display_source(ast)
        self.assertIn("coloring(g, pixels_of(input_grid)[7].coord, 0)", src)
        self.assertIn("coloring(g, pixels_of(input_grid)[35].coord, 2)", src)
        for banned in ("tfg", "apply_DSL", "in_px", "∘"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
