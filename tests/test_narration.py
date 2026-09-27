"""Tests for lib/opusvid/narration.py and scripts/narration_check.py's pure helpers.

    python -m unittest discover -s tests -v

Synthetic takes and timestamps only; no speech recognition is run.
"""
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

from opusvid.narration import (Narration, chars_from_words, chunk, norm,  # noqa: E402
                               speech_extent, srt, srt_time)
import narration_check  # noqa: E402


def even_chars(text, start=0.2, step=0.1):
    """Recogniser-style characters: one every ``step`` seconds from ``start``."""
    return [(c, start + k * step, start + (k + 1) * step) for k, c in enumerate(norm(text))]


SEGS = [{"id": "a", "say": "医院用算法重新读病历，保险公司拒赔。", "gap": 0.5},
        {"id": "b", "say": "because it's cheap。因为便宜。", "gap": 0.3,
         "sub": "because it's cheap。因为便宜。"}]
EXT = {"a": (0.2, 1.8, 2.0), "b": (0.2, 2.0, 2.3)}


class Placement(unittest.TestCase):
    def setUp(self):
        self.N = Narration(SEGS, EXT, {k: even_chars(s["say"]) for k, s in
                                       zip("ab", SEGS)}, lead=1.0, tail=2.0)

    def test_segments_are_trimmed_and_laid_end_to_end(self):
        a0, a1 = self.N.seg("a")
        self.assertAlmostEqual(a0, 1.0)
        self.assertAlmostEqual(a1 - a0, (1.8 + 0.12) - (0.2 - 0.06))
        b0, _ = self.N.seg("b")
        self.assertAlmostEqual(b0, a1 + 0.5)
        self.assertAlmostEqual(self.N.duration, self.N.seg("b")[1] + 2.0)

    def test_phrase_time_comes_from_the_recognised_characters(self):
        # "保险公司" is the 11th normalised character of line a: take time 0.2 + 10 * 0.1
        k = norm(SEGS[0]["say"]).find("保险公司")
        t = self.N.at("a", "保险公司")
        self.assertAlmostEqual(t, self.N.seg("a")[0] + (0.2 + k * 0.1) - (0.2 - 0.06))
        self.assertGreater(self.N.at("a", "保险公司", end=True), t)

    def test_latin_phrase_matches_letters(self):
        ts = self.N.char_times("b", "because it's cheap")
        self.assertEqual(len(ts), len("becauseitscheap"))
        self.assertTrue(all(b > a for a, b in zip(ts, ts[1:])))

    def test_homophone_falls_back_to_script_position(self):
        chars = {"a": even_chars("医院用算法重新读病例，保险公司拒赔"), "b": even_chars(SEGS[1]["say"])}
        N = Narration(SEGS, EXT, chars, lead=1.0)
        t = N.at("a", "病历")                                   # recognised as 病例
        exact = N.at("a", "重新读")
        self.assertGreater(t, exact)
        self.assertLess(t, N.at("a", "保险公司"))

    def test_missing_anchor_fails_loudly(self):
        with self.assertRaises(KeyError):
            self.N.at("a", "不存在的词")

    def test_subtitles_cover_every_line_with_hard_cuts(self):
        subs = self.N.subtitles(limit=10)
        self.assertEqual(subs[0][0], self.N.seg("a")[0])
        for (a, b, _), (c, _, _) in zip(subs, subs[1:]):
            self.assertLessEqual(b, c + 1e-9)                  # never overlapping
            self.assertGreater(b, a)
        self.assertIn("because it's cheap", [s for _, _, s in subs])
        self.assertEqual(len(self.N.subtitles(limit=10, skip={"b"})), len([s for s in subs if s[0] < self.N.seg("b")[0]]))


class Text(unittest.TestCase):
    def test_chunk_keeps_decimals_and_splits_sentences(self):
        self.assertEqual(chunk("从 10.2% 一路涨到了 22.7%。"), ["从 10.2% 一路涨到了 22.7%"])
        out = chunk("账单已经出来了，两年里多付了 9.42 亿美元。其中六点五三亿来自次要诊断。", limit=22)
        self.assertTrue(all(len(c) <= 22 for c in out))
        self.assertIn("9.42", "".join(out))
        self.assertFalse(any(c.endswith("。") for c in out))

    def test_srt_time_never_writes_four_digit_milliseconds(self):
        self.assertEqual(srt_time(1.9996), "00:00:02,000")
        self.assertEqual(srt_time(101.9999), "00:01:42,000")
        self.assertEqual(srt_time(3725.5), "01:02:05,500")
        text = srt([(0.9, 2.75, "一"), (2.75, 6.0, "二")])
        self.assertTrue(text.startswith("1\n00:00:00,900 --> 00:00:02,750\n一\n\n2\n"))

    def test_chars_from_words_spreads_each_word(self):
        ch = chars_from_words([{"word": " 保险", "start": 1.0, "end": 1.4},
                               {"word": ",", "start": 1.4, "end": 1.5},
                               {"word": " Cheap", "start": 2.0, "end": 2.5}])
        self.assertEqual("".join(c for c, _, _ in ch), "保险cheap")
        self.assertAlmostEqual(ch[1][1], 1.2)
        self.assertAlmostEqual(ch[-1][2], 2.5)


@unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
class Extent(unittest.TestCase):
    def test_speech_extent_finds_the_voiced_span(self):
        rate = 24000
        x = np.zeros(int(2.0 * rate))
        t = np.arange(int(1.0 * rate)) / rate
        x[int(0.4 * rate):int(1.4 * rate)] = 0.3 * np.sin(2 * np.pi * 220 * t)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "take.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes((x * 32767).astype("<i2").tobytes())
            a, b, n = speech_extent(p)
        self.assertAlmostEqual(a, 0.4, delta=0.02)
        self.assertAlmostEqual(b, 1.4, delta=0.02)
        self.assertAlmostEqual(n, 2.0, delta=0.01)


class Check(unittest.TestCase):
    def test_diff_reports_only_changed_spans(self):
        spans = narration_check.diff_spans("医院用算法重读病历，把普通住院包装成复杂病例",
                                           "医院用算法中毒病例,把普通住院包装成复杂病例")
        self.assertEqual(spans, [("重读病历", "中毒病例")])
        self.assertEqual(narration_check.diff_spans("因为便宜。", "因为便宜"), [])

    def test_similarity_ignores_punctuation(self):
        self.assertEqual(narration_check.similarity("智能越便宜，账单越贵。", "智能越便宜账单越贵"), 1.0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class ScoreCueStereoPeak(unittest.TestCase):
    def test_correlated_stereo_is_not_reported_as_clipping(self):
        rate = 48000
        t = np.arange(rate) / rate
        x = 0.84 * np.sin(2 * np.pi * 440 * t)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "stereo.wav"
            with wave.open(str(p), "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes((np.repeat(x, 2) * 32767).astype("<i2").tobytes())
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "score_cue.py"), "measure", str(p)],
                               capture_output=True, text=True)
        self.assertNotIn("CLIPPING", r.stdout, r.stdout)
        self.assertIn("peak 0.84", r.stdout)


if __name__ == "__main__":
    unittest.main()
