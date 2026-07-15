import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestParamFree(unittest.TestCase):
    def test_registered_with_effect(self):
        import procedural_memory.dsl as d
        for name, verb in [("rot90","rotate"),("hmirror","reflect"),("vmirror","reflect"),
                           ("rot180","rotate"),("rot270","rotate"),("dmirror","reflect"),
                           ("cmirror","reflect"),("trim","downscale"),("tophalf","crop")]:
            self.assertIn(name, d.SPECS)
            self.assertEqual(d.SPECS[name]["kind"], "transformation")
            self.assertEqual(d.SPECS[name]["effect"], {"verb": verb, "kind": "grid"})

    def test_bodies(self):
        from procedural_memory.dsl.registry import body
        g = [[1,2],[3,4]]
        self.assertEqual(body("rot90")(g), [[3,1],[4,2]])
        self.assertEqual(body("rot180")(g), [[4,3],[2,1]])
        self.assertEqual(body("hmirror")(g), [[3,4],[1,2]])
        self.assertEqual(body("vmirror")(g), [[2,1],[4,3]])
        self.assertEqual(body("dmirror")(g), [[1,3],[2,4]])
        self.assertEqual(body("tophalf")([[1,1],[2,2],[3,3]]), [[1,1]])

if __name__ == "__main__":
    unittest.main()
