"""Tests for the video-side helper CLIs (check_frames.py sheet/--ignore-region, serve_video.py).

    python -m unittest discover -s tests -v

Synthetic frames only; nothing is written inside the repository.
"""
import http.client
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import serve_video  # noqa: E402


def run_check(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "check_frames.py"), *map(str, args)],
                          capture_output=True, text=True)


def write_frames(d, n=8, bar=None, box=None, h=240, w=320):
    """Smooth vertical gradient; optional bright full-width bar (row y) and bright box."""
    base = np.linspace(5, 70, h)[:, None].repeat(w, 1)
    for i in range(n):
        L = base.copy()
        if bar is not None:
            L[bar:bar + 2, :] = 230
        if box is not None:
            x0, y0, x1, y1 = box
            L[y0:y1, x0:x1] += 120
        img = np.clip(L, 0, 255).astype(np.uint8)
        Image.fromarray(np.stack([img] * 3, -1)).save(Path(d) / f"f{i:04d}.png")


COMMON = ["--corner", "20", "--max-corner", "255"]


class FramesIgnoreRegion(unittest.TestCase):
    def test_bar_is_flagged_and_can_be_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, bar=100)
            r = run_check("frames", d, *COMMON)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("sharp row step", r.stdout)
            self.assertIn("--ignore-region", r.stdout)
            r = run_check("frames", d, *COMMON, "--ignore-region", "0,95,320,106")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_partial_region_does_not_create_its_own_edge(self):
        # A box covering only part of each row must not introduce a step at its border.
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, box=(100, 80, 220, 160))
            self.assertEqual(run_check("frames", d, *COMMON).returncode, 1)
            r = run_check("frames", d, *COMMON, "--ignore-region", "100,80,220,160")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_problem_outside_region_is_still_caught(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, bar=100, box=(100, 170, 220, 230))
            r = run_check("frames", d, *COMMON, "--ignore-region", "0,95,320,106")
            self.assertEqual(r.returncode, 1, r.stdout)

    def test_bad_region_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d)
            self.assertEqual(run_check("frames", d, "--ignore-region", "5,5,1").returncode, 2)
            self.assertEqual(run_check("frames", d, "--ignore-region", "9,0,3,4").returncode, 2)


class Sheet(unittest.TestCase):
    def test_sheet_layout_and_labels(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, n=30)
            out = Path(d) / "out" / "sheet.png"
            r = run_check("sheet", d, "--fps", "10", "--times", "0,0.5,1.2,2.9",
                          "--out", out, "--cols", "3", "--width", "100")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("frame    12", r.stdout)          # 1.2s at 10fps
            self.assertIn("frame    29", r.stdout)
            with Image.open(out) as im:
                self.assertEqual(im.width, 3 * 100 + 4 * 4)     # 3 tiles + gaps
                self.assertGreater(im.height, 2 * 75)            # 2 rows of 100x75 tiles + labels

    def test_out_of_range_time_fails(self):
        with tempfile.TemporaryDirectory() as d:
            write_frames(d, n=10)
            r = run_check("sheet", d, "--fps", "10", "--times", "0.5,1.0",
                          "--out", Path(d) / "s.png")
            self.assertEqual(r.returncode, 1)
            self.assertIn("out of range", r.stdout)
            self.assertFalse((Path(d) / "s.png").exists())


class ParseRange(unittest.TestCase):
    def test_ranges(self):
        p = serve_video.parse_range
        self.assertIsNone(p(None, 100))
        self.assertEqual(p("bytes=0-9", 100), (0, 9))
        self.assertEqual(p("bytes=90-", 100), (90, 99))
        self.assertEqual(p("bytes=50-500", 100), (50, 99))
        self.assertEqual(p("bytes=-10", 100), (90, 99))
        self.assertEqual(p("bytes=-500", 100), (0, 99))
        self.assertEqual(p("bytes=100-", 100), "unsatisfiable")
        self.assertIsNone(p("bytes=0-1,5-6", 100))          # multi-range: whole file
        self.assertIsNone(p("items=0-1", 100))


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = os.urandom(5000)
        self.video = Path(self.tmp.name) / "clip.mp4"
        self.video.write_bytes(self.data)
        (Path(self.tmp.name) / "secret.txt").write_text("not listed")
        files = serve_video.build_file_map([str(self.video)])
        self.httpd = serve_video.ThreadingHTTPServer(("127.0.0.1", 0),
                                                     serve_video.make_handler(files))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def req(self, method, path, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request(method, path, headers=headers or {})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r, body

    def test_range_suffix_head_redirect_and_404(self):
        r, b = self.req("GET", "/clip.mp4", {"Range": "bytes=100-199"})
        self.assertEqual((r.status, b), (206, self.data[100:200]))
        self.assertEqual(r.getheader("Content-Range"), "bytes 100-199/5000")
        r, b = self.req("GET", "/clip.mp4", {"Range": "bytes=-50"})
        self.assertEqual((r.status, b), (206, self.data[-50:]))
        r, b = self.req("GET", "/clip.mp4")
        self.assertEqual((r.status, b), (200, self.data))
        self.assertEqual(r.getheader("Content-Type"), "video/mp4")
        r, b = self.req("HEAD", "/clip.mp4")
        self.assertEqual((r.status, b, r.getheader("Content-Length")), (200, b"", "5000"))
        self.assertEqual(r.getheader("Accept-Ranges"), "bytes")
        r, _ = self.req("GET", "/clip.mp4", {"Range": "bytes=5000-"})
        self.assertEqual(r.status, 416)
        r, _ = self.req("GET", "/")
        self.assertEqual((r.status, r.getheader("Location")), (302, "/clip.mp4"))
        for path in ("/secret.txt", "/../secret.txt", "/%2e%2e/secret.txt", "/clip.mp4/x"):
            r, _ = self.req("GET", path)
            self.assertEqual(r.status, 404, path)

    def test_duplicate_names_rejected(self):
        other = Path(self.tmp.name) / "sub"
        other.mkdir()
        (other / "clip.mp4").write_bytes(b"x")
        with self.assertRaises(SystemExit):
            serve_video.build_file_map([str(self.video), str(other / "clip.mp4")])


if __name__ == "__main__":
    unittest.main()
