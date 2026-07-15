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


class TestGridExecute(unittest.TestCase):
    def test_const_contents_produces_that_grid(self):
        out_grid = [[0, 2, 0], [2, 0, 2]]
        ast = P.grid_program(P.const({"height": 2, "width": 3}), P.const([0, 2]), P.const(out_grid))
        self.assertEqual(P.execute(ast, [[9, 9, 9], [9, 9, 9]]), out_grid)   # 입력 무관 상수출력

    def test_keep_contents_is_identity(self):
        g0 = [[1, 0], [0, 1]]
        ast = P.grid_program(P.keep("size"), P.keep("color"), P.keep("contents"))
        self.assertEqual(P.execute(ast, g0), g0)

    def test_keep_size_const_contents(self):   # size=keep(=G0 dims), contents=const 같은 크기
        g0 = [[0, 0], [0, 0]]
        ast = P.grid_program(P.keep("size"), P.const([0, 5]), P.const([[5, 0], [0, 5]]))
        self.assertEqual(P.execute(ast, g0), [[5, 0], [0, 5]])


class TestGridBuilder(unittest.TestCase):
    def test_constant_output_task_ab_shape(self):
        # a/b 형: size DECIDE(KEEP), color DECIDE(CONST set), contents DECIDE(상수출력, value=고정 grid)
        fixed = [[0, 2, 0], [2, 0, 2]]
        dec = {
            "size":     {"decision": "DECIDE", "value": (2, 3), "within": [True, True], "cands": [("KEEP", (2, 3), True)]},
            "color":    {"decision": "DECIDE", "value": frozenset({0, 2}), "cands": [("CONST", frozenset({0, 2}), True)]},
            "contents": {"decision": "DECIDE", "value": fixed, "note": "상수출력", "cands": [("CONST", "상수출력", True)]},
        }
        ast = P.grid_program_from_decide(dec)
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual(ast["body"][2]["args"]["contents"], {"const": fixed})   # 상수출력 → const grid
        self.assertEqual(P.execute(ast, [[9, 9, 9], [9, 9, 9]]), fixed)          # 실행하면 그 grid

    def test_descend_returns_none(self):
        dec = {"size": {"decision": "DECIDE", "value": (2, 2)},
               "color": {"decision": "DECIDE", "value": frozenset({0})},
               "contents": {"decision": "DESCEND", "value": None}}
        self.assertIsNone(P.grid_program_from_decide(dec))


class TestGridDSLRegistered(unittest.TestCase):
    def test_three_setters_in_specs(self):
        from procedural_memory.dsl.registry import SPECS
        for name in ("set_gridsize", "set_gridcolor", "set_gridcontents"):
            self.assertIn(name, SPECS)
            self.assertEqual(SPECS[name]["kind"], "transformation")
    def test_frozen_atoms_still_two(self):   # make_grid·coloring 동결 불변
        from procedural_memory.dsl.registry import SPECS
        self.assertIn("make_grid", SPECS); self.assertIn("coloring", SPECS)
