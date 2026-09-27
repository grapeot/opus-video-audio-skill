"""Render the minimal film's frames. See README.md for the full loop.

    python examples/minimal_film/render.py --plan
    python examples/minimal_film/render.py --out out/minimal_film/frames_run1
    python examples/minimal_film/render.py --out out/minimal_film/preview_run1 --frames 0,31,60,89
"""
import math

import numpy as np

from shot import CAM, DUR, E, FPS, H, N_FRAMES, TITLE, W, dot_pixel
from opusvid.runner import run
from opusvid.typeset import char_onsets, draw_line, load_font, reveal_alphas

FONT_PATH = None          # None: Pillow's built-in font. Any .ttf/.ttc path works here.
G = {}                    # per-worker resources, filled by init()


def init():
    G["font"] = load_font(FONT_PATH, 44)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    G["yy"], G["xx"] = yy, xx


def glow(cx, cy, sigma, power):
    """A Gaussian glow forced to exactly zero before 4 sigma (no box edge)."""
    r = np.hypot(G["xx"] - cx, G["yy"] - cy)
    g = np.exp(-0.5 * (r / sigma) ** 2) * np.clip(1.0 - r / (4.0 * sigma), 0, 1) ** 2
    return power * g


def render_frame(i):
    t = i / FPS
    cu, cv, width, rot = CAM(t)
    zoom = 3.0 / width                                    # 1 at the start, ~1.9 at the end

    canvas = np.zeros((H, W, 3))                          # linear light
    canvas += np.array([0.0012, 0.0018, 0.0040]) * (1.2 - 0.6 * G["yy"] / H)[..., None]
    px, py = dot_pixel(t)
    flash = math.exp(-(t - E.cross) / 0.25) if t >= E.cross else 0.0
    warm = np.array([1.0, 0.78, 0.45])
    canvas += glow(px, py, 3.0 * zoom, 3.0 + 3.0 * flash)[..., None] * warm
    canvas += glow(px, py, 16.0 * zoom, 0.18 + 0.35 * flash)[..., None] * warm

    img = np.clip(canvas / (1 + canvas), 0, 1) ** (1 / 2.2)   # tone map once

    a = reveal_alphas(len(TITLE), t, E.title, E.title_step, E.title_fade)
    draw_line(img, TITLE, G["font"], W / 2, H * 0.74, (0.93, 0.86, 0.72),
              alpha=0.95, spacing=10, reveal=a, bed=0.45)
    img *= 1 - E.ramp("fade", t)
    return img


def plan():
    print(f"{W}x{H} @ {FPS}fps, {DUR}s = {N_FRAMES} frames\n")
    print(E.table())
    print("\n     t    cu      cv   width   dot_px  dot_py")
    for t in sorted([0, 0.5, 1.0, E.cross, 1.5, 2.0, 2.5, DUR]):
        cu, cv, width, _ = CAM(t)
        px, py = dot_pixel(t)
        print(f"  {t:5.2f} {cu:5.2f} {cv:7.2f} {width:6.2f} {float(px):8.1f} {float(py):7.1f}")
    print("\ntitle onsets:", [round(x, 2) for x in char_onsets(len(TITLE), E.title, E.title_step)])


if __name__ == "__main__":
    raise SystemExit(run(render_frame, N_FRAMES, init=init, plan=plan))
