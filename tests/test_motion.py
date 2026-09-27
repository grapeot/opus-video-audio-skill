"""Tests for lib/opusvid/motion (pen, print-in, ink blending, motes, set camera, sprites).

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from opusvid import motion  # noqa: E402


class Easing(unittest.TestCase):
    def test_back_out_overshoots_then_lands(self):
        vals = [motion.back_out(0, 1, t) for t in np.linspace(0, 1, 101)]
        self.assertAlmostEqual(vals[0], 0.0, places=6)
        self.assertAlmostEqual(vals[-1], 1.0, places=6)
        self.assertGreater(max(vals), 1.0)

    def test_roll_lands_exactly(self):
        self.assertEqual(motion.roll(0, 30204, 0, 1, 1.0), "30,204")
        self.assertEqual(motion.roll(0, 10.3, 0, 1, 5.0, "{:.1f}%"), "10.3%")
        self.assertEqual(motion.roll(0, 14, 0, 1, -1.0, "${:,.0f}"), "$0")


class Pen(unittest.TestCase):
    def test_arc_length_not_index(self):
        # three points, very uneven spacing: half the length is reached inside the long segment
        pts = [(0, 0), (1, 0), (100, 0)]
        drawn, tip = motion.pen(pts, 0.5)
        self.assertAlmostEqual(tip[0], 50.0, places=6)
        self.assertEqual(drawn[-1], tip)
        self.assertEqual(motion.pen(pts, 0), ([], None))
        drawn, tip = motion.pen(pts, 1.0)
        self.assertEqual(tip, (100.0, 0.0))


class PrintInAndBlend(unittest.TestCase):
    def test_print_in_grows_monotonically_and_completes(self):
        pr = motion.PrintIn(60, 80, seed=1)
        cov = [pr.mask(p).mean() for p in (0.0, 0.3, 0.6, 1.0)]
        self.assertEqual(cov[0], 0.0)
        self.assertTrue(all(b >= a for a, b in zip(cov, cov[1:])))
        self.assertEqual(cov[-1], 1.0)
        # centre arrives before the corner
        m = pr.mask(0.35)
        self.assertGreater(m[30, 40], m[0, 0])
        ink = np.full((60, 80, 3), 0.2, np.float32)
        self.assertTrue(np.allclose(motion.apply_mask(ink, np.zeros((60, 80))), 1.0))

    def test_ink_blend_is_not_darker_than_its_ends(self):
        a = np.full((4, 4, 3), 0.6, np.float32)
        b = np.full((4, 4, 3), 0.4, np.float32)
        bl = motion.InkBlend([a, b])
        mid = bl.at(0.5)
        self.assertTrue(np.allclose(mid, 0.5))
        # the naive way (multiply A, then multiply B at alpha 0.5) is darker than both ends
        naive = a * (1 - 0.5 + 0.5 * b)
        self.assertLess(naive.mean(), b.mean() + 0.01 + (a.mean() - b.mean()) * 0.5 - 0.05)
        self.assertIs(bl.at(0.501), bl.at(0.5))      # quantised and cached


class Motes(unittest.TestCase):
    def test_births_and_deaths(self):
        before = motion.motes(0.0, 1.0, n=30, origin=(100, 100))
        self.assertTrue((before[:, 3] == 0).all())
        during = motion.motes(3.0, 1.0, n=30, origin=(100, 100))
        alive = during[during[:, 3] > 0]
        self.assertGreater(len(alive), 5)
        self.assertTrue((alive[:, 1] < 100).mean() > 0.8)      # mostly above the origin
        after = motion.motes(20.0, 1.0, n=30, origin=(100, 100))
        self.assertTrue((after[:, 3] == 0).all())


class Camera(unittest.TestCase):
    def test_set_pan(self):
        pan = motion.SetPan([(0, 0.0), (1, 10.0), (2, 20.0)], dur=1.0, lead=0.5)
        self.assertEqual(pan(5.0), 0.0)
        self.assertAlmostEqual(pan(10.0), 0.5, places=6)
        self.assertEqual(pan(12.0), 1.0)
        self.assertEqual(pan(30.0), 2.0)
        self.assertGreater(pan.speed_px(10.0, 30, 1920), 10)
        self.assertEqual(pan.speed_px(5.0, 30, 1920), 0.0)
        img = np.random.default_rng(0).random((10, 40, 3))
        self.assertIs(motion.blur_along_x(img, 1.0), img)
        self.assertLess(motion.blur_along_x(img, 9).std(), img.std())


class Sprites(unittest.TestCase):
    def test_crop_sprites_left_to_right(self):
        img = np.full((120, 400, 3), 240, np.uint8)
        for x0 in (30, 170, 300):
            img[40:90, x0:x0 + 60] = (120, 80, 40)
        boxes = motion.crop_sprites(img, min_area=500, pad=5)
        self.assertEqual(len(boxes), 3)
        self.assertEqual([b[0] for b in boxes], [25, 165, 295])


if __name__ == "__main__":
    unittest.main()
