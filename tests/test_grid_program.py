# tests/test_grid_program.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as P


class TestGridSchema(unittest.TestCase):
    def test_grid_program_shape(self):
        ast = P.grid_program(P.keep("size"), P.const([0, 2]), P.const([[0, 2], [2, 0]]))
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual([s["call"] for s in ast["body"]],
                         ["set_gridsize", "set_gridcolor", "set_gridcontents"])
        self.assertEqual(ast["body"][0]["args"]["size"], {"keep": "size"})
        self.assertEqual(ast["body"][2]["args"]["contents"], {"const": [[0, 2], [2, 0]]})

    def test_to_source_grid_renders_setters(self):
        ast = P.grid_program(P.expr("H-1,W-1"), P.delta([5], [1, 2, 3, 4]), P.keep("contents"))
        src = P.to_source(ast)
        self.assertIn("set_gridsize(H-1,W-1)", src)
        self.assertIn("set_gridcolor(-[5]+[1, 2, 3, 4])", src)
        self.assertIn("set_gridcontents(keep)", src)
        self.assertTrue(src.rstrip().endswith("output_grid = G1"))

    def test_pixel_body_still_works(self):   # 회귀: 기존 pixel to_source 불변
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        self.assertIn("apply_DSL(tfg0, coloring, P0.coord, 3)", P.to_source(ast))
