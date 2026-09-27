"""Tests for scripts/music_timing.py and lib/opusvid placement / strokefont.

    python -m unittest discover -s tests -v

Synthetic audio only. Skipped when librosa / Hershey-Fonts / ffmpeg are not installed.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))

HAVE_LIBROSA = importlib.util.find_spec("librosa") is not None
HAVE_HERSHEY = importlib.util.find_spec("HersheyFonts") is not None
HAVE_FFMPEG = shutil.which("ffmpeg") is not None

from opusvid import placement  # noqa: E402

SR = 22050


def write_wav(path, y, sr=SR):
    y16 = (np.clip(y, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y16.tobytes())


def clicks(times, dur, sr=SR):
    y = np.zeros(int(dur * sr))
    k = np.exp(-np.arange(int(0.03 * sr)) / (0.004 * sr)) * np.sin(2 * np.pi * 70 * np.arange(int(0.03 * sr)) / sr)
    noise = np.random.default_rng(0).normal(0, 1, len(k)) * np.exp(-np.arange(len(k)) / (0.002 * sr))
    for t in times:
        i = int(t * sr)
        y[i:i + len(k)] += 0.8 * k + 0.3 * noise
    return y


def syllables(times, dur, sr=SR, length=0.22):
    y = np.zeros(int(dur * sr))
    n = int(length * sr)
    tt = np.arange(n) / sr
    env = np.minimum(tt / 0.01, 1) * np.exp(-tt / 0.15)
    tone = sum(np.sin(2 * np.pi * f * tt) / (h + 1) for h, f in enumerate((220, 440, 660, 880)))
    for t in times:
        i = int(t * sr)
        y[i:i + n] += 0.3 * env * tone
    return y


@unittest.skipUnless(HAVE_LIBROSA and HAVE_FFMPEG, "needs librosa and ffmpeg")
class MusicTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import music_timing
        cls.mt = music_timing
        cls.tmp = Path(tempfile.mkdtemp())
        cls.beats = np.arange(0.5, 11.5, 0.5)                                   # 120 BPM
        cls.lines = [1.02, 3.03, 5.51, 8.04]                                       # true sung-line onsets
        syl = sorted(set(np.round(np.r_[cls.lines, [l + 0.3 for l in cls.lines], [l + 0.6 for l in cls.lines]], 3)))
        cls.acc = clicks(cls.beats, 12.0)
        cls.voc = syllables(syl, 12.0)
        write_wav(cls.tmp / "accomp.wav", cls.acc)
        write_wav(cls.tmp / "vocals.wav", cls.voc)
        write_wav(cls.tmp / "song.wav", 0.6 * cls.acc + 0.6 * cls.voc)
        # a community LRC with every line 0.18-0.25 s off; the words are placeholders
        shifts = [0.2, -0.18, 0.25, -0.2]
        lrc = "".join(f"[{int((t + s) // 60):02d}:{(t + s) % 60:05.2f}] one two three\n" for t, s in zip(cls.lines, shifts))
        (cls.tmp / "lines.lrc").write_text(lrc)
        cls.res = cls.mt.analyze(cls.tmp / "song.wav", 24, cls.tmp / "vocals.wav", cls.tmp / "accomp.wav", cls.tmp / "lines.lrc")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_snap(self):
        out = self.mt.snap([1.0, 2.0, 3.5], [1.03, 2.2, 3.49], tol=0.05, fallback=-0.01)
        np.testing.assert_allclose(out, [1.03, 1.99, 3.49])

    def test_beats_snap_to_clicks(self):
        b = np.array(self.res["beats"])
        d = self.mt.nearest_offsets(b, self.beats)
        self.assertLess(np.median(np.abs(d)), 0.02)

    def test_lines_snap_to_vocal_onsets(self):
        got = [x["t"] for x in self.res["lines"]]
        np.testing.assert_allclose(got, self.lines, atol=0.04)
        self.assertGreater(self.res["audit"]["line_offset_abs_max_ms"], 150)

    def test_word_times_start_at_line(self):
        for x, t in zip(self.res["lines"], self.lines):
            self.assertEqual(len(x["word_times"]), 3)
            self.assertAlmostEqual(x["word_times"][0], x["t"], places=3)
            self.assertTrue(all(a <= b for a, b in zip(x["word_times"], x["word_times"][1:])))

    def test_lrc_text_not_stored(self):
        self.assertNotIn("one two three", json.dumps(self.res))

    def test_envelope_peaks_on_beats(self):
        env = np.array(self.res["env"])
        # a hit lands on the first frame after its onset: look at the three frames from the beat on
        on = [env[int(np.floor(b * 24)):int(np.floor(b * 24)) + 3].max() for b in self.beats[1:-1]]
        off = [env[int(round((b + 0.25) * 24))] for b in self.beats[1:-1]]
        self.assertGreater(np.mean(on), np.mean(off) + 0.2)

    def test_cli_analyze_and_audit(self):
        out = self.tmp / "t.json"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "music_timing.py"), "analyze", str(self.tmp / "song.wav"),
                            "--vocals", str(self.tmp / "vocals.wav"), "--accomp", str(self.tmp / "accomp.wav"),
                            "--lrc", str(self.tmp / "lines.lrc"), "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "music_timing.py"), "audit", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("lines moved more than 100 ms", r.stdout)


class Placement(unittest.TestCase):
    def setUp(self):
        self.W, self.H = 320, 180
        self.lum = np.zeros((self.H, self.W))

    def test_avoids_ink(self):
        self.lum[int(0.7 * self.H):, :] = 1.0                   # bottom band is full of ink
        ii = placement.ink_integral(self.lum, blur=1)
        best = placement.choose(80, 12, [(ii, (0, 0, 1.0))], placement.candidates(scales=(1.0,)), edge=5)
        self.assertLess(best["y"], 0.5)
        self.assertLess(best["cost"], 0.2)

    def test_screen_anchor_on_big_zoom(self):
        ii = placement.ink_integral(self.lum, blur=1)
        best = placement.choose(80, 12, [(ii, (0, 0, 1.0)), (ii, (0, 0, 4.0))], edge=5)
        self.assertTrue(best["screen"])
        best = placement.choose(80, 12, [(ii, (0, 0, 1.0)), (ii, (0, 0, 1.5))], edge=5)
        self.assertFalse(best["screen"])

    def test_carried_off_screen_is_penalised(self):
        ii = placement.ink_integral(self.lum, blur=1)
        # the camera pans far right during the text's life: text written near the left edge leaves the frame
        s = [(ii, (0, 0, 1.0)), (ii, (200, 0, 1.0))]
        best = placement.choose(60, 12, s, placement.candidates(xs=(0.2, 0.8), ys=(0.5,), scales=(1.0,)), edge=5)
        self.assertEqual(best["x"], 0.8)

    def test_collision_with_other_text(self):
        ii = placement.ink_integral(self.lum, blur=1)
        taken = [(0.5 * self.W - 40, 0.84 * self.H - 6, 0.5 * self.W + 40, 0.84 * self.H + 6)]
        best = placement.choose(80, 12, [(ii, (0, 0, 1.0))], occupied=taken, edge=5)
        self.assertNotEqual((best["x"], best["y"]), (0.5, 0.84))

    def test_clearing_band(self):
        b = np.ones((self.H, self.W))
        placement.clearing_band([b], (100, 80, 200, 100), strength=0.8, feather=10)
        self.assertAlmostEqual(b[90, 150], 0.2, places=5)
        self.assertEqual(b[5, 5], 1.0)
        self.assertTrue(0.2 < b[90, 95] < 1.0)

    def test_box_ink_offscreen(self):
        ii = placement.ink_integral(self.lum, blur=1)
        ink, off = placement.box_ink(ii, -50, 0, 50, 10)
        self.assertAlmostEqual(off, 0.5, places=2)


@unittest.skipUnless(HAVE_HERSHEY, "needs Hershey-Fonts")
class StrokeFont(unittest.TestCase):
    def test_layout_and_reveal(self):
        from opusvid import strokefont
        words, width = strokefont.layout("alpha beta")
        self.assertEqual(len(words), 2)
        self.assertGreater(width, 0)
        x0 = max(p[:, 0].max() for p in words[0])
        x1 = min(p[:, 0].min() for p in words[1])
        self.assertGreater(x1, x0)
        times = strokefont.word_times(1.0, 2.0, [1.0, 1.4, 1.7], 2)
        self.assertEqual(times, [1.0, 1.7])
        self.assertEqual(list(strokefont.reveal(words, times, 0.9)), [])
        early = sum(f for _, _, f in strokefont.reveal(words, times, 1.05))
        late = sum(f for _, _, f in strokefont.reveal(words, times, 3.0))
        self.assertLess(early, late)
        self.assertEqual(len(list(strokefont.reveal(words, times, 3.0))), sum(len(w) for w in words))

    def test_blank(self):
        from opusvid import strokefont
        self.assertEqual(strokefont.layout("   "), ([], 0.0))


if __name__ == "__main__":
    unittest.main()
