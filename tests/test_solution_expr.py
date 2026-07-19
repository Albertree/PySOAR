import unittest
from debugger.reports.solution_expr import selector_to_condition


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


if __name__ == "__main__":
    unittest.main()
