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
