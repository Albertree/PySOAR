import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTransformSearchOp(unittest.TestCase):
    def test_body_writes_hypotheses_and_survivor(self):
        from procedural_memory.operators.transform_search import _op_transform_search

        class WM:
            def __init__(self): self.t = []
            def add(self, i, a, v): self.t.append((i, a, v))
        class AG:
            def __init__(self):
                self.wm = WM()
                self.stack = [type("S", (), {"id": "s1"})()]
                self.task = {"train": [
                    {"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]},
                    {"input": [[5,6],[7,8]], "output": [[7,5],[8,6]]}]}
        ag = AG()
        # superstate 없으면 parent=None; 테스트용으로 self-parent 처리
        ag.wm.t.append(("s1", "superstate", "root"))
        _op_transform_search(ag)
        hyps = [v for (i, a, v) in ag.wm.t if a == "hypothesis"]
        self.assertTrue(hyps)                                   # 후보 물질화
        surv = [v for (i, a, v) in ag.wm.t if a == "transform-survivor"]
        self.assertTrue(any("rot90" in s for s in surv))

    def test_json_loads_in_productions(self):
        from procedural_memory.loader import PRODUCTIONS
        names = [p.name for p in PRODUCTIONS]
        self.assertIn("propose*transform_search", names)
        self.assertIn("apply*transform_search", names)
