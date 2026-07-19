# -*- coding: utf-8 -*-
import unittest
from arbor.reasoning import program_ast as PA
from debugger.reports.program_report import display_source


class TestDisplaySource(unittest.TestCase):
    def test_grid_object_form(self):
        ast = PA.grid_program(PA.expr("size(input_grid)"),
                              PA.const([0, 2]),
                              PA.const([[0, 0], [0, 2]]))
        src = display_source(ast)
        self.assertIn("g = input_grid", src)
        self.assertIn("g.size = set_grid_size(size(input_grid))", src)
        self.assertIn("g.color = set_grid_color([0, 2])", src)
        self.assertIn("g.contents = set_grid_contents([[0, 0], [0, 2]])", src)
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
