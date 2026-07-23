# -*- coding: utf-8 -*-
import unittest, json
from arbor.reasoning import program_ast as PA


def _selstep(coords, col):
    return PA.step("coloring",
        target=PA.coordinate_of(PA.select("input", "pixel", PA.coord_in("pixel_coordinate", coords))),
        color=PA.const(col))


class TestSelectAntiunify(unittest.TestCase):
    def test_diff_coords_become_slot_no_cellset(self):
        a = PA.program([_selstep([[3, 2]], 0), _selstep([[4, 3]], 7)])
        b = PA.program([_selstep([[6, 0]], 0), _selstep([[7, 1]], 7)])
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        blob = json.dumps(sk)
        self.assertNotIn('"cellset"', blob)            # cellset 어디에도 없음
        self.assertIn("select", blob)                  # select 스켈레톤
        self.assertTrue(any(k.startswith("?cells") for k in slots))

    def test_ops_of_ast_select_shape(self):
        a = _selstep([[3, 2], [3, 3]], 5)
        ops = PA.ops_of_ast(PA.program([a]))
        (tgt, col), = ops
        self.assertEqual(col, 5)
        self.assertEqual(set(tgt), {(3, 2), (3, 3)})       # frozenset of coord tuples


if __name__ == "__main__":
    unittest.main()
