import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arbor.reasoning.transform_search import derive_required_effect
from arbor.reasoning.transform_search import candidate_transforms, transform_search

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


class TestSearchEngine(unittest.TestCase):
    def test_fanout_by_effect(self):
        req = derive_required_effect([{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]}])
        cands = candidate_transforms(req)
        self.assertIn("rot90", cands)      # rotate
        self.assertIn("hmirror", cands)    # reflect
        self.assertNotIn("make_grid", cands)

    def test_solves_rot90(self):
        t = [{"input": [[1,2],[3,4]], "output": [[3,1],[4,2]]},
             {"input": [[5,6],[7,8]], "output": [[7,5],[8,6]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "rot90")
        self.assertTrue(any(h["verdict"] == "reject" for h in r["hypotheses"]))  # 기각 잔존

    def test_solves_replace(self):
        t = [{"input": [[1,1],[0,0]], "output": [[2,2],[0,0]]},
             {"input": [[1,0],[1,0]], "output": [[2,0],[2,0]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "replace")
        self.assertEqual(r["survivor"]["plan"]["args"], [1, 2])

    def test_solves_move_by_search(self):
        # 단일 obj 를 (H-1,W-1) 코너로 — offset 은 탐색으로 도출
        t = [{"input": [[5,0,0],[0,0,0],[0,0,0]], "output": [[0,0,0],[0,0,0],[0,0,5]]},
             {"input": [[0,0],[3,0]], "output": [[0,0],[0,3]]}]
        r = transform_search(t)
        self.assertEqual(r["survivor"]["rule"], "move")
