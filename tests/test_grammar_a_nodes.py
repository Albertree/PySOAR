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

    def test_render_header_handles_select_target(self):
        """select-target(coordinate_of) 엔 'ref' 키가 없음 — render_header 도 to_source 처럼
        .get('ref') 로 안전해야 한다(KeyError 대신 accessor 스킵)."""
        body = [PA.step("coloring",
                        target=PA.coordinate_of(PA.select("input", "pixel",
                                                          PA.eq("pixel_coordinate", [3, 2]))),
                        color=PA.const(0))]
        ast = PA.program(body)
        grid_in = [[0, 0], [0, 0]]
        header = PA.render_header(ast, grid_in)
        self.assertIsInstance(header, str)


if __name__ == "__main__":
    unittest.main()
