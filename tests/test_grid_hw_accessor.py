import unittest
from arbor.perception.arckg.grid import Grid
from arbor.procedural_memory.dsl.property import height, width, size


class TestGridHW(unittest.TestCase):
    def test_height_width_project_size(self):
        g = Grid("T0.P0.G0", [[0, 1, 2], [3, 4, 5]])   # 2x3
        self.assertEqual(height(g), 2)
        self.assertEqual(width(g), 3)
        self.assertEqual(height(g), size(g)["height"])
        self.assertEqual(width(g), size(g)["width"])

    def test_registered_in_specs(self):
        from arbor.procedural_memory.dsl.registry import SPECS
        self.assertEqual(SPECS["height"]["in"], ["grid"])
        self.assertEqual(SPECS["width"]["out"], "int")


if __name__ == "__main__":
    unittest.main()
