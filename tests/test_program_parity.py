import unittest
from arbor.reasoning import program_ast as PA
from debugger.reports.program_viewer import _runner_payload


class TestParityPayload(unittest.TestCase):
    def test_expected_equals_execute(self):
        ast = PA.program([
            PA.step("coloring", target=PA.ref("pixel", PA.const(1)), color=PA.const(5)),
        ])
        task = {"train": [{"input": [[0, 0], [0, 0]], "output": [[0, 5], [0, 0]]}]}
        payload = _runner_payload("easy000x", [ast], task)
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item["expected"], PA.execute(ast, task["train"][0]["input"]))
        self.assertEqual(item["expected"], [[0, 5], [0, 0]])   # coloring idx1=(0,1)→5
        self.assertIn("body", item)                            # display_source body 문자열
        self.assertEqual(item["input"], [[0, 0], [0, 0]])


if __name__ == "__main__":
    unittest.main()
