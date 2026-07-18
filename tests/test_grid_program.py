# tests/test_grid_program.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning import program_ast as P


class TestGridSchema(unittest.TestCase):
    def test_grid_program_shape(self):
        ast = P.grid_program(P.expr("size(input_grid)"), P.const([0, 2]), P.const([[0, 2], [2, 0]]))
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual([s["call"] for s in ast["body"]],
                         ["set_grid_size", "set_grid_color", "set_grid_contents"])
        self.assertEqual(ast["body"][0]["args"]["size"], {"expr": "size(input_grid)"})
        self.assertEqual(ast["body"][2]["args"]["contents"], {"const": [[0, 2], [2, 0]]})

    def test_to_source_grid_renders_setters(self):
        ast = P.grid_program(P.expr("H-1,W-1"), P.delta([5], [1, 2, 3, 4]), P.expr("contents(input_grid)"))
        src = P.to_source(ast)
        self.assertIn("set_grid_size(H-1,W-1)", src)
        self.assertIn("set_grid_color(-[5]+[1, 2, 3, 4])", src)
        self.assertIn("set_grid_contents(contents(input_grid))", src)
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
        ast = P.grid_program(P.expr("size(input_grid)"), P.expr("color(input_grid)"), P.expr("contents(input_grid)"))
        self.assertEqual(P.execute(ast, g0), g0)

    def test_keep_size_const_contents(self):   # size=expr(=G0 dims), contents=const 같은 크기
        g0 = [[0, 0], [0, 0]]
        ast = P.grid_program(P.expr("size(input_grid)"), P.const([0, 5]), P.const([[5, 0], [0, 5]]))
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

    def test_descend_returns_partial_skeleton(self):
        # c–h 형: size/color DECIDE, contents DESCEND → 버리지 않고 skeleton(pending contents) 유지.
        dec = {"size": {"decision": "DECIDE", "value": (2, 2), "cands": [("KEEP", (2, 2), True)]},
               "color": {"decision": "DECIDE", "value": frozenset({0}), "cands": [("KEEP", frozenset({0}), True)]},
               "contents": {"decision": "DESCEND", "value": None}}
        ast = P.grid_program_from_decide(dec)
        self.assertIsNotNone(ast)
        self.assertTrue(P._is_grid_body(ast["body"]))
        self.assertEqual(ast["body"][2]["args"]["contents"], {"pending": "contents"})
        self.assertFalse(P.is_full_grid_program(ast))

    def test_all_decide_is_full_grid_program(self):
        # a/b 형: 셋 다 DECIDE → pending 없음 = full.
        fixed = [[0, 2, 0], [2, 0, 2]]
        dec = {
            "size":     {"decision": "DECIDE", "value": (2, 3), "cands": [("KEEP", (2, 3), True)]},
            "color":    {"decision": "DECIDE", "value": frozenset({0, 2}), "cands": [("CONST", frozenset({0, 2}), True)]},
            "contents": {"decision": "DECIDE", "value": fixed, "note": "상수출력", "cands": [("CONST", "상수출력", True)]},
        }
        ast = P.grid_program_from_decide(dec)
        self.assertTrue(P.is_full_grid_program(ast))


class TestGridDSLRegistered(unittest.TestCase):
    def test_setters_in_specs(self):   # set_grid_size 유지(선언형; make_grid 없이). 3 setter 등록.
        from procedural_memory.dsl.registry import SPECS
        for name in ("set_grid_size", "set_grid_color", "set_grid_contents"):
            self.assertIn(name, SPECS)
            self.assertEqual(SPECS[name]["kind"], "transformation")
    def test_frozen_atom_is_coloring_only(self):   # coloring 단독 동결 원자(make_grid 제거)
        from procedural_memory.dsl.registry import SPECS
        self.assertIn("coloring", SPECS); self.assertNotIn("make_grid", SPECS)


class TestGridAntiunify(unittest.TestCase):
    def test_identical_grid_programs_no_slots(self):
        a = P.grid_program(P.expr("size(input_grid)"), P.const([0, 2]), P.const([[0, 2]]))
        b = P.grid_program(P.expr("size(input_grid)"), P.const([0, 2]), P.const([[0, 2]]))
        sk, slots = P.antiunify_ast([a, b])
        self.assertEqual(slots, {})
        self.assertTrue(P._is_grid_body(sk["body"]))

    def test_diff_contents_becomes_slot(self):
        a = P.grid_program(P.expr("size(input_grid)"), P.const([0, 2]), P.const([[0, 2]]))
        b = P.grid_program(P.expr("size(input_grid)"), P.const([0, 2]), P.const([[2, 0]]))
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?contents", slots)
        self.assertEqual(sk["body"][2]["args"]["contents"], {"var": "?contents"})
