import unittest
from debugger.reports.solution_expr import selector_to_condition, move_to_vector


class TestSelectorToCondition(unittest.TestCase):
    def test_color(self):
        self.assertEqual(selector_to_condition("color=2"), ("color(o) == 2", None))

    def test_size(self):
        self.assertEqual(selector_to_condition("size=4"), ("area(o) == 4", None))

    def test_bounded_is_color_not_zero(self):
        self.assertEqual(selector_to_condition("bounded"), ("color(o) != 0", None))

    def test_shape_returns_ref(self):
        self.assertEqual(selector_to_condition("shape#0"), ("shape(o) == shape0", "shape0"))
        self.assertEqual(selector_to_condition("shape#3"), ("shape(o) == shape3", "shape3"))

    def test_none_or_unknown_faithful(self):
        self.assertEqual(selector_to_condition(None), ("true", None))
        self.assertEqual(selector_to_condition("weird"), ("weird", None))


class TestMoveToVector(unittest.TestCase):
    def test_keep_is_bare_coordinate(self):
        self.assertEqual(move_to_vector("r0+0", "c0+0", "obj0"), "coordinate(obj0)")

    def test_relative_delta(self):
        self.assertEqual(move_to_vector("r0+1", "c0+1", "obj0"),
                         "coordinate(obj0) + (1, 1)")
        self.assertEqual(move_to_vector("r0-2", "c0+3", "obj0"),
                         "coordinate(obj0) + (-2, 3)")

    def test_br_both_axes(self):
        self.assertEqual(move_to_vector("BR=2", "BR=2", "obj0"),
                         "coordinate(obj0) - bottom_right(obj0) + (2, 2)")

    def test_absolute_both_axes(self):
        self.assertEqual(move_to_vector("=1", "=1", "obj0"),
                         "coordinate(obj0) - top_left(obj0) + (1, 1)")

    def test_edge_both_axes(self):
        self.assertEqual(move_to_vector("0", "0", "obj0"),
                         "coordinate(obj0) - top_left(obj0) + (0, 0)")

    def test_grid_corner(self):
        self.assertEqual(move_to_vector("H-h", "W-w", "obj0"),
                         "coordinate(obj0) - bottom_right(obj0) + bottom_right(input_grid)")

    def test_mixed_abs_row_br_col(self):
        # 축별 다른 모델: row 절대=1, col BR=2 → 성분별 anchor/target
        self.assertEqual(move_to_vector("=1", "BR=2", "obj0"),
                         "coordinate(obj0) - (top_left(obj0).r, bottom_right(obj0).c) + (1, 2)")


if __name__ == "__main__":
    unittest.main()
