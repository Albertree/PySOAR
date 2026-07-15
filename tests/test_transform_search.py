import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning.transform_search import derive_required_effect

def verbs(train):
    return {e["verb"] for e in derive_required_effect(train)}

class TestRequiredEffect(unittest.TestCase):
    def test_size_preserved_pixels_preserved(self):
        # 회전/반사/이동 후보 — 픽셀 다중집합 보존, 팔레트 보존, 격자는 다름
        t = [{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]}]   # rot90
        self.assertTrue({"rotate","reflect","translate"} <= verbs(t))

    def test_palette_diff_recolor(self):
        t = [{"input": [[1,1],[0,0]], "output": [[2,2],[0,0]]}]   # 1→2
        self.assertIn("recolor", verbs(t))

    def test_dims_swapped(self):
        t = [{"input": [[1,2,3]], "output": [[1],[2],[3]]}]       # (1,3)->(3,1)
        self.assertTrue({"rotate","reflect"} <= verbs(t))

    def test_upscale(self):
        t = [{"input": [[1]], "output": [[1,1],[1,1]]}]           # x2
        self.assertIn("upscale", verbs(t))
