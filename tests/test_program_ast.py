# tests/test_program_ast.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.reasoning import program_ast as P


class TestToSource(unittest.TestCase):
    def test_two_step_pixel_program_roundtrips_to_exact_legacy_string(self):
        ast = P.program([
            P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3)),
            P.step("coloring", target=P.ref("pixel", P.const(12)), color=P.const(3)),
        ])
        expected = (
            "in_px = pixels_of(input_grid)\n"
            "P0 = in_px[5]\n"
            "P1 = in_px[12]\n"
            "\n"
            "tfg0 = input_grid\n"
            "tfg1 = apply_DSL(tfg0, coloring, P0.coord, 3)\n"
            "tfg2 = apply_DSL(tfg1, coloring, P1.coord, 3)\n"
            "output_grid = tfg2"
        )
        self.assertEqual(P.to_source(ast), expected)

    def test_object_level_uses_in_objs(self):
        ast = P.program([P.step("coloring", target=P.ref("object", P.const(3)), color=P.const(4))])
        src = P.to_source(ast)
        self.assertIn("in_objs = objects_of(input_grid)", src)
        self.assertIn("O0 = in_objs[3]", src)
        self.assertIn("apply_DSL(tfg0, coloring, O0.coord, 4)", src)

    def test_slot_variable_renders_name_not_value(self):
        ast = P.program(
            [P.step("coloring", target=P.ref("pixel", P.var("?src0")), color=P.var("?color0"))],
            slots={"?src0": {"kind": "src", "pos": 0}, "?color0": {"kind": "color", "pos": 0}},
        )
        src = P.to_source(ast)
        self.assertIn("P0 = in_px[?src0]", src)
        self.assertIn("apply_DSL(tfg0, coloring, P0.coord, ?color0)", src)

    def test_empty_program_is_none_source(self):
        self.assertEqual(P.to_source(None), "{}")


class TestExecute(unittest.TestCase):
    def test_concrete_pixel_program_recolors_cell(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        # 2x2 grid, index 1 = (0,1)
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[0, 3], [0, 0]])

    def test_two_steps_apply_in_order(self):
        ast = P.program([
            P.step("coloring", target=P.ref("pixel", P.const(0)), color=P.const(5)),
            P.step("coloring", target=P.ref("pixel", P.const(3)), color=P.const(7)),
        ])
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[5, 0], [0, 7]])

    def test_slot_index_uses_choice_fn(self):
        ast = P.program(
            [P.step("coloring", target=P.ref("pixel", P.var("?src0")), color=P.var("?color0"))],
            slots={"?src0": {"kind": "src", "pos": 0}, "?color0": {"kind": "color", "pos": 0}},
        )
        choice = {"?src0": (lambda g: 2), "?color0": (lambda g: 9)}
        out = P.execute(ast, [[0, 0], [0, 0]], choice=choice)
        self.assertEqual(out, [[0, 0], [9, 0]])   # index 2 = (1,0)

    def test_out_of_range_index_skipped(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(99)), color=P.const(3))])
        out = P.execute(ast, [[0, 0], [0, 0]])
        self.assertEqual(out, [[0, 0], [0, 0]])


class TestBlobCellset(unittest.TestCase):
    def test_to_source_const_cells_compress_defform(self):
        ast = P.program([
            P.step("coloring", target=P.cellset(P.const([7, 8, 13, 14])), color=P.const(3)),
            P.step("coloring", target=P.cellset(P.const([20])), color=P.const(5)),
        ])
        expected = (
            "B0 = [7, 8, 13, 14]\n"
            "B1 = [20]\n"
            "\n"
            "tfg0 = input_grid\n"
            "tfg1 = apply_DSL(tfg0, coloring, B0, 3)\n"
            "tfg2 = apply_DSL(tfg1, coloring, B1, 5)\n"
            "output_grid = tfg2"
        )
        self.assertEqual(P.to_source(ast), expected)

    def test_to_source_var_cells_inline_form(self):
        ast = P.program(
            [P.step("coloring", target=P.cellset(P.var("?cells0")), color=P.const(3))],
            slots={"?cells0": {"kind": "cellset", "pos": 0}},
        )
        src = P.to_source(ast)
        self.assertIn("tfg1 = apply_DSL(tfg0, coloring, ?cells0, 3)  # 객체 덩어리", src)
        self.assertNotIn("B0 =", src)                       # var → def 없음(inline)

    def test_execute_cellset_colors_all_cells(self):
        ast = P.program([P.step("coloring", target=P.cellset(P.const([0, 1, 2])), color=P.const(4))])
        out = P.execute(ast, [[0, 0, 0], [0, 0, 0]])        # W=3; idx 0,1,2 = (0,0),(0,1),(0,2)
        self.assertEqual(out, [[4, 4, 4], [0, 0, 0]])

    def test_execute_cellset_var_uses_choice(self):
        ast = P.program(
            [P.step("coloring", target=P.cellset(P.var("?cells0")), color=P.const(7))],
            slots={"?cells0": {"kind": "cellset", "pos": 0}},
        )
        out = P.execute(ast, [[0, 0], [0, 0]], choice={"?cells0": (lambda g: [3])})
        self.assertEqual(out, [[0, 0], [0, 7]])             # idx 3 = (1,1)


class TestAntiunify(unittest.TestCase):
    def test_common_index_common_color_no_slots(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertEqual(slots, {})
        self.assertEqual(P.ops_of_ast(sk), [(5, 3)])

    def test_diff_color_becomes_color_slot(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(5)), color=P.const(8))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?color0", slots)
        self.assertEqual(slots["?color0"]["kind"], "color")
        self.assertEqual(slots["?color0"]["values"], [3, 8])
        # skeleton 의 color 는 var 로 승격
        self.assertEqual(sk["body"][0]["args"]["color"], {"var": "?color0"})

    def test_diff_index_becomes_src_slot(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(9)), color=P.const(3))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?src0", slots)
        self.assertEqual(slots["?src0"]["values"], [1, 9])
        self.assertEqual(sk["body"][0]["args"]["target"]["index"], {"var": "?src0"})

    def test_different_op_count_returns_none(self):
        a = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3)),
                       P.step("coloring", target=P.ref("pixel", P.const(2)), color=P.const(4))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIsNone(sk)

    def test_blob_diff_cellset_becomes_cellset_slot(self):
        a = P.program([P.step("coloring", target=P.cellset(P.const([1, 2])), color=P.const(3))])
        b = P.program([P.step("coloring", target=P.cellset(P.const([5, 6])), color=P.const(3))])
        sk, slots = P.antiunify_ast([a, b])
        self.assertIn("?cells0", slots)
        self.assertEqual(slots["?cells0"]["kind"], "cellset")
        self.assertEqual(slots["?cells0"]["values"], [[1, 2], [5, 6]])
        self.assertEqual(sk["body"][0]["args"]["target"], {"ref": "cellset", "cells": {"var": "?cells0"}})


class TestHeader(unittest.TestCase):
    def test_header_lists_used_op_and_input_grid(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        h = P.render_header(ast, [[0, 0], [0, 0]])
        self.assertIn("coloring", h)                       # 사용한 op 시그니처
        self.assertIn("pixels_of", h)                      # pixel ref → pixels_of accessor
        self.assertIn("input_grid = [[0, 0], [0, 0]]", h)  # 현 grid 스냅샷

    def test_header_omits_unused_object_accessor(self):
        ast = P.program([P.step("coloring", target=P.ref("pixel", P.const(1)), color=P.const(3))])
        h = P.render_header(ast, [[0, 0], [0, 0]])
        self.assertNotIn("objects_of", h)                  # object 미사용 → 생략
