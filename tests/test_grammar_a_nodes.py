# -*- coding: utf-8 -*-
"""P1 Task1: Grammar A 표현 노드 생성자 + to_source 렌더."""
import unittest
from arbor.reasoning import program_ast as PA


class TestGrammarANodes(unittest.TestCase):
    def test_constructors_shape(self):
        pred = PA.eq("pixel_coordinate", [3, 2])
        self.assertEqual(pred, {"eq": {"accessor": "pixel_coordinate", "value": [3, 2]}})
        sel = PA.select("input", "pixel", pred)
        self.assertEqual(sel["select"]["grid"], "input")
        self.assertEqual(sel["select"]["level"], "pixel")
        self.assertEqual(sel["select"]["pred"], pred)
        co = PA.coordinate_of(sel)
        self.assertIn("coordinate_of", co)

    def test_json_serializable(self):
        import json
        sel = PA.coordinate_of(PA.select("input", "pixel", PA.eq("pixel_coordinate", [3, 2])))
        self.assertEqual(json.loads(json.dumps(sel)), sel)   # 순수 dict(람다 없음)

    def test_to_source_renders_select_target(self):
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_coordinate", [3, 2]))),
                        color=PA.const(0))]
        src = PA.to_source(PA.program(body))
        self.assertIn("select(input, pixel, pixel_coordinate==[3, 2])", src)
        self.assertIn("coordinate_of(", src)


if __name__ == "__main__":
    unittest.main()
