import unittest
from arbor.perception.arckg.grid import Grid
from arbor.procedural_memory.dsl.util import pixels_of
from arbor.procedural_memory.dsl.selection import elements_at


class TestPixelsOf(unittest.TestCase):
    def setUp(self):
        self.g = Grid("T0.P0.G0", [[7, 8, 9], [1, 2, 3]])   # 2x3, W=3

    def test_rowmajor_full_length(self):
        px = pixels_of(self.g)
        self.assertEqual(len(px), 6)                          # H*W

    def test_index_coord_convention(self):
        px = pixels_of(self.g)
        for i in range(6):
            self.assertEqual(px[i].coord, (i // 3, i % 3))    # (i//W, i%W)

    def test_color_matches_raw(self):
        px = pixels_of(self.g)
        self.assertEqual(px[0].color, 7)                      # (0,0)
        self.assertEqual(px[5].color, 3)                      # (1,2)

    def test_selection_pixel_level(self):
        sel = elements_at(self.g, "pixel")
        self.assertEqual([p.coord for p in sel],
                         [p.coord for p in pixels_of(self.g)])


if __name__ == "__main__":
    unittest.main()
