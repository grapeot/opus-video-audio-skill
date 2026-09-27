"""Tests for lib/opusvid (runner, timeline, typeset) and check_frames.py assemble.

    python -m unittest discover -s tests -v

Synthetic data only; everything is written to temporary directories.
"""
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from opusvid import runner, timeline, typeset  # noqa: E402


# ---------------------------------------------------------------- timeline ----

class Timeline(unittest.TestCase):
    KEYS = [(0.0, 0.0, 0.0, 10.0, 0.0),
            (1.0, 0.5, 0.2, 4.0, 0.0),
            (2.5, 2.0, 0.3, 1.0, 5.0),
            (4.0, 2.2, 0.9, 0.5, 5.0)]

    def test_pchip_passes_through_keys_and_stays_monotone(self):
        cam = timeline.CameraPath(self.KEYS)
        for k in self.KEYS:
            got = cam(k[0])
            for g, want in zip(got, k[1:]):
                self.assertAlmostEqual(g, want, places=9)
        ts = np.linspace(0, 4, 801)
        vals = np.array([cam(t) for t in ts])
        # cu, cv rise monotonically through monotone keys: no overshoot
        self.assertTrue(np.all(np.diff(vals[:, 0]) >= -1e-12))
        self.assertTrue(np.all(np.diff(vals[:, 1]) >= -1e-12))
        # width falls monotonically and never leaves the key range
        self.assertTrue(np.all(np.diff(vals[:, 2]) <= 1e-12))
        self.assertTrue(vals[:, 2].min() >= 0.5 - 1e-9 and vals[:, 2].max() <= 10 + 1e-9)
        # the flat rotation hold between keys 2 and 3 stays flat (no bump)
        self.assertTrue(np.allclose(vals[ts >= 2.5, 3], 5.0))
        # outside the keys the camera holds
        self.assertEqual(cam(-1.0), cam(0.0))
        self.assertEqual(cam(9.0), cam(4.0))
        self.assertEqual(set(cam.at(1.0)), {"cu", "cv", "width", "rot_deg"})

    def test_width_is_interpolated_in_log_space(self):
        cam = timeline.CameraPath([(0.0, 0, 0, 1.0, 0), (1.0, 0, 0, 100.0, 0)])
        # two keys: PCHIP is linear, so log-linear width -> geometric mean mid-way
        self.assertAlmostEqual(cam(0.5)[2], 10.0, places=9)
        self.assertAlmostEqual(cam(0.25)[2], 100 ** 0.25, places=9)
        lin = timeline.CameraPath([(0.0, 0, 0, 1.0, 0), (1.0, 0, 0, 100.0, 0)], log_fields=())
        self.assertAlmostEqual(lin(0.5)[2], 50.5, places=9)
        self.assertAlmostEqual(timeline.log_lerp(1.0, 100.0, 0.5), 10.0, places=9)
        with self.assertRaises(ValueError):
            timeline.CameraPath([(0.0, 0, 0, 1.0, 0), (1.0, 0, 0, 0.0, 0)])

    def test_solve_time_finds_first_crossing(self):
        f = lambda t: t * t                                          # noqa: E731
        self.assertAlmostEqual(timeline.solve_time(f, 2.0, 0, 3), math.sqrt(2), places=6)
        # non-monotone: sin crosses 0.5 at pi/6 first, then 5pi/6
        t = timeline.solve_time(math.sin, 0.5, 0, 3.0)
        self.assertAlmostEqual(t, math.pi / 6, places=6)
        # decreasing functions work too
        t = timeline.solve_time(lambda t: 10 - t, 7.5, 0, 10)
        self.assertAlmostEqual(t, 2.5, places=6)
        with self.assertRaises(ValueError):
            timeline.solve_time(f, 50.0, 0, 3)

    def test_smooth_ease_events(self):
        self.assertEqual(timeline.smooth(1, 2, 0.5), 0.0)
        self.assertEqual(timeline.smooth(1, 2, 3.0), 1.0)
        self.assertAlmostEqual(timeline.smooth(1, 2, 1.5), 0.5)
        arr = timeline.smooth(0, 1, np.array([-1.0, 0.5, 2.0]))
        self.assertTrue(np.allclose(arr, [0, 0.5, 1]))
        self.assertAlmostEqual(timeline.ease_in_out(0.5), 0.5)
        E = timeline.Events(title=1.2, step=0.1, fade=(2.4, 3.0))
        self.assertEqual(E.title, 1.2)
        self.assertEqual(E["fade"], (2.4, 3.0))
        self.assertEqual(E.ramp("fade", 2.0), 0.0)
        self.assertEqual(E.ramp("fade", 3.5), 1.0)
        with self.assertRaises(TypeError):
            E.span("title")
        with self.assertRaises(AttributeError):
            E.title = 5
        self.assertIn("fade", E.table())

    def test_export_camera_json_matches_pixel_formula(self):
        cam = timeline.CameraPath(self.KEYS)
        W, H, fps = 360, 640, 30
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "camera.json"
            timeline.export_camera_json(p, range(10, 20), cam, lambda t: {"light": t / 4},
                                        W=W, H=H, fps=fps)
            doc = json.loads(p.read_text())
        self.assertEqual((doc["W"], doc["H"], doc["fps"]), (W, H, fps))
        self.assertEqual(len(doc["frames"]), 10)
        row = doc["frames"][3]
        self.assertEqual(row["frame"], 13)
        self.assertAlmostEqual(row["light"], 13 / 30 / 4, places=5)
        # the documented formula (rot 0) agrees with world_to_pixel
        u, v = row["cu"] + 0.1, row["cv"] - 0.2
        px = (u - row["cu"]) / row["width"] * W + W / 2
        py = (v - row["cv"]) / row["width"] * W + H / 2
        gx, gy = timeline.world_to_pixel(u, v, row["cu"], row["cv"], row["width"], W, H)
        self.assertAlmostEqual(float(gx), px, places=9)
        self.assertAlmostEqual(float(gy), py, places=9)
        # a 90 degree view rotation: world +u appears straight up the screen
        gx, gy = timeline.world_to_pixel(1.0, 0.0, 0.0, 0.0, 2.0, W, H, rot_deg=90)
        self.assertAlmostEqual(float(gx), W / 2, places=9)
        self.assertAlmostEqual(float(gy), H / 2 - W / 2, places=9)


# ------------------------------------------------------------------ runner ----

def _tiny_frame(i):
    img = np.zeros((16, 24, 3))
    img[:, :, 0] = i / 10.0
    return img


class Runner(unittest.TestCase):
    def test_parse_frames(self):
        p = runner.parse_frames
        self.assertEqual(p(None, 5), [0, 1, 2, 3, 4])
        self.assertEqual(p("", 3), [0, 1, 2])
        self.assertEqual(p("4,0,2,2", 10), [0, 2, 4])
        self.assertEqual(p("0:3,7", 10), [0, 1, 2, 7])
        self.assertEqual(p("8:", 10), [8, 9])
        self.assertEqual(p(":2", 10), [0, 1])
        self.assertEqual(p("0:10:4", 10), [0, 4, 8])
        for bad in ("10", "-1", "3:3", "5:12", "a", "1:2:0", "1:2:3:4", ","):
            with self.assertRaises(runner.FrameSpecError, msg=bad):
                p(bad, 10)

    def _run(self, argv, **kw):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = runner.run(_tiny_frame, 10, argv=argv, **kw)
        return rc, out.getvalue(), err.getvalue()

    def test_refuses_non_empty_output_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "f0000.png").write_bytes(b"stale")
            rc, _, err = self._run(["--out", d, "--jobs", "1"])
            self.assertEqual(rc, 2)
            self.assertIn("not empty", err)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["f0000.png"])
            self.assertEqual((Path(d) / "f0000.png").read_bytes(), b"stale")
            # --overwrite is the deliberate way through; it deletes nothing
            (Path(d) / "keep.txt").write_text("x")
            rc, _, _ = self._run(["--out", d, "--jobs", "1", "--frames", "0,1", "--overwrite"])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "keep.txt").exists())
            with Image.open(Path(d) / "f0000.png") as im:
                self.assertEqual(im.size, (24, 16))

    def test_renders_subset_records_start_and_uses_pool(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "run1"
            rc, stdout, _ = self._run(["--out", str(out), "--jobs", "2", "--frames", "0:3,9"])
            self.assertEqual(rc, 0)
            names = sorted(p.name for p in out.glob("*.png"))
            self.assertEqual(names, ["f0000.png", "f0001.png", "f0002.png", "f0009.png"])
            start = float((out / runner.START_FILE).read_text())
            self.assertLessEqual(start, (out / "f0009.png").stat().st_mtime)
            self.assertIn("--since", stdout)
            px = np.asarray(Image.open(out / "f0009.png"))[0, 0]
            self.assertEqual(px[0], int(0.9 * 255 + 0.5))
            # missing --out and a bad --frames are usage errors, not crashes
            self.assertEqual(self._run([])[0], 2)
            self.assertEqual(self._run(["--out", str(Path(d) / "x"), "--frames", "99"])[0], 2)
            self.assertFalse((Path(d) / "x").exists())

    def test_plan(self):
        called = []
        rc, _, _ = self._run(["--plan"], plan=lambda: called.append(1))
        self.assertEqual((rc, called), (0, [1]))
        self.assertEqual(self._run(["--plan"])[0], 2)


# ----------------------------------------------------------------- typeset ----

class Typeset(unittest.TestCase):
    def setUp(self):
        self.font = typeset.load_font(None, 40)

    def test_glyph_mask_is_non_empty(self):
        m = typeset.glyph_mask("A", self.font)
        self.assertEqual(m.dtype, np.float32)
        self.assertGreater(m.max(), 0.9)
        self.assertGreater((m > 0.5).sum(), 50)
        self.assertEqual(float(m[0].max()), 0.0)            # padding is clear

    def test_letter_spacing_widens_the_line(self):
        a = typeset.text_mask("ABCD", self.font, spacing=0)
        b = typeset.text_mask("ABCD", self.font, spacing=10)
        self.assertEqual(b.shape[1] - a.shape[1], 30)
        self.assertEqual(a.shape[0], b.shape[0])

    def test_vertical_column_height(self):
        img = np.zeros((400, 100, 3), np.float32)
        top, step, text = 20, 60, "ABCDE"
        bottom = typeset.draw_column(img, text, self.font, 50, top, step, (1, 1, 1))
        self.assertEqual(bottom, top + len(text) * step)
        rows = np.where(img[..., 0].max(1) > 0.5)[0]
        self.assertGreaterEqual(rows.min(), top)
        self.assertLessEqual(rows.max(), bottom)
        # the ink spans most of the column: first glyph near the top, last near the bottom
        self.assertLess(rows.min(), top + step)
        self.assertGreater(rows.max(), bottom - step)
        cols = np.where(img[..., 0].max(0) > 0.5)[0]
        self.assertTrue(abs((cols.min() + cols.max()) / 2 - 50) <= 3)

    def test_blend_respects_alpha_and_bounds(self):
        img = np.full((50, 50, 3), 0.2, np.float32)
        m = np.ones((10, 10), np.float32)
        typeset.blend_mask(img, m, 45, 45, (1.0, 1.0, 1.0), alpha=0.5)   # partly off-frame
        self.assertAlmostEqual(float(img[47, 47, 0]), 0.6, places=5)
        self.assertAlmostEqual(float(img[40, 40, 0]), 0.2, places=5)
        typeset.blend_mask(img, m, 200, 200, (1, 1, 1))                   # fully off-frame: no-op

    def test_reveal_and_bed(self):
        a = typeset.reveal_alphas(3, 1.0, 0.5, 0.25, fade=0.5)
        self.assertEqual(a[0], 1.0)
        self.assertTrue(0 < a[1] < 1 and a[2] == 0.0)
        self.assertEqual(typeset.char_onsets(3, 0.5, 0.25), [0.5, 0.75, 1.0])
        img = np.zeros((120, 400, 3), np.float32)
        typeset.draw_line(img, "ABC", self.font, 200, 60, (1, 1, 1), reveal=[1, 0, 0])
        ink = np.where(img[..., 0].max(0) > 0.5)[0]
        full = np.zeros_like(img)
        typeset.draw_line(full, "ABC", self.font, 200, 60, (1, 1, 1))
        ink_full = np.where(full[..., 0].max(0) > 0.5)[0]
        self.assertEqual(ink.min(), ink_full.min())
        self.assertLess(ink.max(), ink_full.max() - 40)       # only "A" is drawn
        lit = np.full((120, 400, 3), 0.8, np.float32)
        typeset.draw_line(lit, "ABC", self.font, 200, 60, (1, 1, 1), bed=0.45)
        self.assertLess(float(lit.min()), 0.8)                # the bed darkens around glyphs


# ---------------------------------------------------------------- assemble ----

def run_check(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "check_frames.py"),
                           *map(str, args)], capture_output=True, text=True)


def write_frames(d, n=12, w=64, h=48, start=0):
    for i in range(start, start + n):
        a = np.zeros((h, w, 3), np.uint8)
        a[:, : (i * 5) % w] = (200, 120, 40)
        Image.fromarray(a).save(Path(d) / f"f{i:04d}.png")


def write_tone(path, secs, rate=48000):
    t = np.arange(int(secs * rate)) / rate
    x = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(x.tobytes())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class Assemble(unittest.TestCase):
    def test_frames_and_audio_to_verified_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            fr = Path(d) / "frames"
            fr.mkdir()
            write_frames(fr, n=12)
            write_tone(Path(d) / "cue.wav", 1.0)
            out = Path(d) / "out" / "film.mp4"
            r = run_check("assemble", fr, "--fps", "12", "--audio", Path(d) / "cue.wav",
                          "--out", out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(out.exists())
            self.assertIn("h264 64x48 @ 12fps", r.stdout)
            self.assertIn("audio    aac", r.stdout)
            self.assertIn("decode   clean", r.stdout)

    def test_scale_and_start_number(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, n=6, start=30)
            out = Path(d) / "small.mp4"
            r = run_check("assemble", d, "--fps", "6", "--scale", "32x24", "--out", out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("h264 32x24 @ 6fps", r.stdout)
            self.assertIn("duration 1.000s", r.stdout)

    def test_gap_short_audio_and_odd_size_fail(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, n=12)
            (Path(d) / "f0005.png").unlink()
            r = run_check("assemble", d, "--fps", "12", "--out", Path(d) / "x.mp4")
            self.assertEqual(r.returncode, 1)
            self.assertIn("missing", r.stdout)
            self.assertFalse((Path(d) / "x.mp4").exists())
        with tempfile.TemporaryDirectory() as d:
            fr = Path(d) / "frames"
            fr.mkdir()
            write_frames(fr, n=12)
            write_tone(Path(d) / "short.wav", 0.5)        # cue shorter than the picture
            r = run_check("assemble", fr, "--fps", "12", "--audio", Path(d) / "short.wav",
                          "--out", Path(d) / "y.mp4")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("duration", r.stdout)
            r = run_check("assemble", fr, "--fps", "12", "--scale", "33x24",
                          "--out", Path(d) / "z.mp4")
            self.assertEqual(r.returncode, 1)
            self.assertIn("even", r.stdout)


if __name__ == "__main__":
    unittest.main()
