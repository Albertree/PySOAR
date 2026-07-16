import unittest
from arbor.reasoning import program_ast as PA


class TestNestedContents(unittest.TestCase):
    def test_program_contents_executes_like_pixel_body(self):
        # pixel body: recolor cell idx1 → 5
        pbody = [PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(5))]
        pixel_prog = PA.program(pbody)
        inp = [[0, 0], [0, 0]]
        pixel_out = PA.execute(pixel_prog, inp)                 # 현행 pixel 실행
        # hybrid grid program: size/color leaves + contents = program(pbody)
        hybrid = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 5]),
                                  PA.contents_program(pbody))
        hybrid_out = PA.execute(hybrid, inp)
        self.assertEqual(hybrid_out, pixel_out)                # nested == pixel (정답 불변)
        self.assertEqual(hybrid_out, [[0, 5], [0, 0]])

    def test_const_contents_unchanged(self):
        g = PA.grid_program(PA.expr("size(input_grid)"), PA.const([0, 2]), PA.const([[0, 0], [0, 2]]))
        self.assertEqual(PA.execute(g, [[9, 9], [9, 9]]), [[0, 0], [0, 2]])


if __name__ == "__main__":
    unittest.main()
