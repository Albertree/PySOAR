import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import procedural_memory.dsl as d

EXPECT = {  # name -> (kind, verb|None)
    "fill": ("transformation", "fill"), "cover": ("transformation", "fill"),
    "crop": ("transformation", "crop"), "upscale": ("transformation", "upscale"),
    "downscale": ("transformation", "downscale"), "hconcat": ("transformation", "concat"),
    "canvas": ("transformation", "create"),
    "objects": ("selection", None), "colorfilter": ("selection", None),
    "hmatching": ("relation", None), "manhattan": ("relation", None),
}


class TestBatch(unittest.TestCase):
    def test_registered(self):
        for name, (kind, verb) in EXPECT.items():
            self.assertIn(name, d.SPECS, name)
            self.assertEqual(d.SPECS[name]["kind"], kind, name)
            eff = d.SPECS[name]["effect"]
            self.assertEqual(eff["verb"] if eff else None, verb, name)


if __name__ == "__main__":
    unittest.main()
