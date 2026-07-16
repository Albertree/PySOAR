# -*- coding: utf-8 -*-
"""Task 2: _antiunify_ast_grid 가 contents=program(nested coloring) 를 재귀적으로
anti-unify 하고, inner pixel slot 을 top-level 로 승격(prefix ?c.)하는지 검증."""
import unittest
from arbor.reasoning import program_ast as PA


class TestNestedAntiunify(unittest.TestCase):
    def test_grid_with_program_contents_recurses(self):
        def hyb(idx, col):
            b = [PA.step("coloring", target=PA.ref("pixel", PA.const(idx)), color=PA.const(col))]
            return PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, col]), PA.contents_program(b))
        a, b = hyb(7, 0), hyb(35, 2)                      # 같은 size, color DIFF, contents(coloring) DIFF
        sk, slots = PA.antiunify_ast([a, b])
        self.assertIsNotNone(sk)
        parts = {s["call"]: s["args"] for s in sk["body"]}
        ct = parts["set_grid_contents"]["contents"]
        self.assertIn("program", ct)                       # contents 는 여전히 program(합성)
        # inner coloring 의 src/color 가 slot 으로 승격됨
        self.assertTrue(any(k.startswith("?c.") for k in slots))

    def test_promoted_slot_names_match_skeleton_var_names(self):
        """CRITICAL: slots dict 의 키가 skeleton inner body 에 남은 var 이름과 byte-identical 해야
        resolve/apply_solution 이 bind 할 수 있다."""
        def hyb(idx, col):
            b = [PA.step("coloring", target=PA.ref("pixel", PA.const(idx)), color=PA.const(col))]
            return PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, col]), PA.contents_program(b))
        a, b = hyb(7, 0), hyb(35, 2)
        sk, slots = PA.antiunify_ast([a, b])
        parts = {s["call"]: s["args"] for s in sk["body"]}
        inner_body = parts["set_grid_contents"]["contents"]["program"]["body"]
        found_vars = set()
        for s in inner_body:
            tgt = s["args"]["target"]
            idx_leaf = tgt["index"]
            if "var" in idx_leaf:
                found_vars.add(idx_leaf["var"])
            col_leaf = s["args"]["color"]
            if "var" in col_leaf:
                found_vars.add(col_leaf["var"])
        self.assertTrue(found_vars)
        promoted_slot_names = {k for k in slots if k.startswith("?c.")}
        self.assertEqual(found_vars, promoted_slot_names)

    def test_grid_program_without_program_contents_unchanged(self):
        """const/expr contents leaf 는 여전히 기존 로직(전체 leaf 를 하나의 var 로 승격)."""
        a = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 1]), PA.const([[0]]))
        b = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 2]), PA.const([[1]]))
        sk, slots = PA.antiunify_ast([a, b])
        parts = {s["call"]: s["args"] for s in sk["body"]}
        ct = parts["set_grid_contents"]["contents"]
        self.assertEqual(ct, {"var": "?contents"})
        self.assertIn("?contents", slots)
        self.assertFalse(any(k.startswith("?c.") for k in slots))


if __name__ == "__main__":
    unittest.main()
