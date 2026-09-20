"""Nine placement regions: the place dot sits on a region center and ignores jitter."""

import random
import unittest

import numpy as np

import main as app
from gaze_snap import GazeSnapper


class PlaceGridTests(unittest.TestCase):
    def setUp(self):
        self.s = GazeSnapper(1280, 720, *app.PLACE_GRID)

    def test_nine_regions_with_their_centers(self):
        centers = [tuple(round(v) for v in self.s.center((c, r))) for r in range(3) for c in range(3)]
        self.assertEqual(len(centers), 9)
        self.assertEqual(centers[4], (640, 360))
        self.assertEqual(centers[0], (213, 120))

    def test_gaze_anywhere_in_a_region_places_at_its_center(self):
        rng = random.Random(0)
        out = {self.s.update((1000 + rng.uniform(-150, 150), 600 + rng.uniform(-80, 80))) for _ in range(100)}
        self.assertEqual({tuple(round(v) for v in p) for p in out}, {(1067, 600)})

    def test_border_jitter_does_not_flip_regions(self):
        self.s.update((400, 360))
        outs = {self.s.update((427 + (10 if i % 2 else -10), 360)) for i in range(40)}
        self.assertEqual({tuple(round(v) for v in p) for p in outs}, {(213, 360)})

    def test_grid_drawing(self):
        view = np.zeros((720, 1280, 3), np.uint8)
        self.s.update((640, 360))
        app.draw_place_grid(view, self.s)
        self.assertTrue(view[:, 427].any() and view[240, :].any())


if __name__ == "__main__":
    unittest.main()
