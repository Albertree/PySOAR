import unittest
from debugger.reports.solution_expr import selector_to_condition, move_to_vector, render_solution_lines


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
                         "coordinate(obj0) - (top_left(obj0).row, bottom_right(obj0).col) + (1, 2)")


class TestRenderSolutionLines(unittest.TestCase):
    def _sol(self):
        return {"body": [
            {"call": "set_grid_size", "args": {"size": {"const": {"height": 8, "width": 8}}}},
            {"call": "set_grid_color", "args": {"color": {"expr": "color(input_grid)"}}},
            {"call": "set_grid_contents", "args": {"contents": {"program": {"body": [
                {"call": "coloring", "args": {"target": {"ref": "cellset", "cells": {"var": "?c.cells0"}},
                                              "color": {"const": 0}}},
                {"call": "coloring", "args": {"target": {"ref": "cellset", "cells": {"var": "?c.cells1"}},
                                              "color": {"var": "?c.color1"}}},
            ]}}}}]}

    def test_move000a_shape_relative(self):
        resolved = {"?c.cells0": "move[r0+0,c0+0]@shape#0",
                    "?c.cells1": "move[r0+1,c0+1]@shape#0",
                    "?c.color1": "color@shape#0"}
        lines = render_solution_lines(self._sol(), resolved,
                                      {"size": True, "color": False},
                                      {"shape0": [[1, -1], [1, 1]]})
        text = "\n".join(lines)
        self.assertIn("shape0 = [[1, -1], [1, 1]]", text)
        self.assertIn("obj0 = select(object, shape(o) == shape0)", text)
        self.assertIn("set_grid_size = (8, 8)", text)                 # COMM → 리터럴
        self.assertIn("?var1 = color(input_grid)", text)              # DIFF color → 변수
        self.assertIn("set_grid_color = ?var1", text)
        self.assertIn("?var2 = coordinate(obj0)", text)               # cells0 제자리
        self.assertIn("coloring(?var2, 0)", text)                     # 지우기(색0 리터럴)
        self.assertIn("?var3 = coordinate(obj0) + (1, 1)", text)      # cells1 상대이동
        self.assertIn("?var4 = color(obj0)", text)                    # color1
        self.assertIn("coloring(?var3, ?var4)", text)
        self.assertNotIn("cellset", text)                            # raw cellset 제거
        self.assertNotIn("?c.", text)                                # 내부 슬롯명 노출 안 함

    def test_bounded_br_uses_color_not_zero(self):
        resolved = {"?c.cells0": "move[r0+0,c0+0]@bounded",
                    "?c.cells1": "move[BR=2,BR=2]@bounded",
                    "?c.color1": "color@bounded"}
        text = "\n".join(render_solution_lines(self._sol(), resolved,
                        {"size": True, "color": False}, {}))
        self.assertIn("obj0 = select(object, color(o) != 0)", text)
        self.assertIn("coordinate(obj0) - bottom_right(obj0) + (2, 2)", text)

    def test_size_comm_no_const_falls_back_to_expr(self):
        # 실제 move000a 솔루션처럼 set_grid_size 가 const 없이 expr 만 갖는 경우(§Task 5 CRITICAL fix
        # — comm["size"]=True 인데 sz.get("const") 가 없으면 (None, None) 을 렌더하던 버그).
        sol = self._sol()
        sol["body"][0] = {"call": "set_grid_size", "args": {"size": {"expr": "size(input_grid)"}}}
        resolved = {"?c.cells0": "move[r0+0,c0+0]@bounded",
                    "?c.cells1": "move[BR=2,BR=2]@bounded",
                    "?c.color1": "color@bounded"}
        text = "\n".join(render_solution_lines(sol, resolved,
                        {"size": True, "color": False}, {}))
        self.assertIn("set_grid_size = size(input_grid)", text)
        self.assertNotIn("(None, None)", text)


if __name__ == "__main__":
    unittest.main()
