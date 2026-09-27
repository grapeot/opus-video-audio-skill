"""Element-wise motion for explainers that must not read as slides.

Backend-agnostic helpers (numpy/scipy/Pillow only): they return positions, masks,
alphas and blended ink, and the film's own renderer draws them with whatever it
uses (skia, PIL, cairo). See ``motion.md`` in the procedural-video-frames skill.

    from opusvid.motion import (back_out, pen, PrintIn, InkBlend, motes, roll,
                                SetPan, crop_sprites)

    pts_so_far, tip = pen(curve_pts, eo(t0, t1, t))       # a pen tracing a curve
    mask = printer.mask(progress)                         # a plate inking in
    ink = blend.at(stage)                                 # true cross-fade of multiply plates
    x, y, r, a = motes(t, t0, n=80, origin=(900, 400)).T  # aroma/steam motes, own clocks
    label = roll(0, 30204, t0, t0 + 1.5, t, "${:,.0f}")   # a rolling counter
    pos = pan(t)                                          # camera between sets on one sheet
"""
from __future__ import annotations

import math

import numpy as np


# ------------------------------------------------------------------ easing ----

def _u(a, b, t):
    if b <= a:
        return 1.0 if t >= a else 0.0
    return min(max((t - a) / (b - a), 0.0), 1.0)


def ease_out(a, b, t, p=3):
    """0 before ``a``, 1 after ``b``, decelerating in between."""
    return 1 - (1 - _u(a, b, t)) ** p


def back_out(a, b, t, s=1.7):
    """Ease-out with a small overshoot past 1: things that *pop* into place.
    Use it on scale (0.85 + 0.15 * back_out) rather than on position, so the
    overshoot reads as a settle, not a bounce."""
    u = _u(a, b, t) - 1
    return 1 + u * u * ((s + 1) * u + s)


def stagger(t0, n, step):
    """Start times for ``n`` elements that arrive one after another."""
    return [t0 + step * j for j in range(n)]


def roll(v0, v1, a, b, t, fmt="{:,.0f}", p=3):
    """A counter rolling from ``v0`` to ``v1`` over [a, b], formatted.
    It lands exactly on ``v1`` at ``b``; draw it with fixed-advance digits
    (typeset/tab figures) so the width does not jitter while it rolls."""
    return fmt.format(v0 + (v1 - v0) * ease_out(a, b, t, p))


# ---------------------------------------------------------------- pen ----

def pen(pts, k):
    """The part of a polyline a pen has traced at arc-length fraction ``k``.

    Returns ``(points, tip)``: the traced prefix (with an interpolated last
    point) and the pen tip, or ``([], None)`` before it starts. Parametrising by
    arc length, not by point index, keeps the pen speed constant when the
    points are unevenly spaced (a logged curve sampled in time is)."""
    if k <= 0 or len(pts) < 2:
        return [], None
    p = np.asarray(pts, float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    L = cum[-1] * min(k, 1.0)
    j = int(np.searchsorted(cum, L, side="right"))
    out = [tuple(q) for q in p[:j]]
    if j < len(p):
        u = (L - cum[j - 1]) / max(seg[j - 1], 1e-12)
        tip = tuple(p[j - 1] + (p[j] - p[j - 1]) * u)
        out.append(tip)
    else:
        tip = tuple(p[-1])
    return out, tip


# ---------------------------------------------------------- printing in ----

class PrintIn:
    """A plate that inks in instead of fading in.

    Pixels arrive where a smooth field falls below the progress: the field mixes
    distance from a centre (so it grows outward) with blurred noise (so the edge
    is organic). ``mask(p)`` is 0..1 per pixel; apply it to the ink as
    ``1 - (1 - ink) * mask`` and multiply the result onto the page, so paper stays
    paper at every step."""

    def __init__(self, h, w, seed=0, radial=0.55, blur_frac=1 / 40, centre=None):
        from scipy.ndimage import gaussian_filter
        rng = np.random.default_rng(seed)
        n = gaussian_filter(rng.random((h, w)).astype(np.float32), max(min(w, h) * blur_frac, 1.0))
        n = (n - n.min()) / (n.max() - n.min() + 1e-9)
        cy, cx = centre if centre is not None else (h / 2, w / 2)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot(xx - cx, yy - cy) / (0.5 * math.hypot(w, h))
        self.field = radial * r + (1 - radial) * n

    def mask(self, progress, soft=0.08, reach=1.25):
        """Coverage at ``progress`` in [0, 1]; complete (all ones) at 1."""
        if progress >= 1:
            return np.ones_like(self.field)
        return np.clip((progress * reach - self.field) / soft, 0, 1)


def apply_mask(ink, m):
    """Ink (1 = paper) revealed by mask ``m``: unrevealed pixels become paper."""
    m = m[..., None] if ink.ndim == 3 and m.ndim == 2 else m
    return 1 - (1 - ink) * m


# ------------------------------------------------------------ ink blending ----

class InkBlend:
    """A true cross-fade between multiply-blended plates (for example one bean at
    seven roast colours).

    Drawing plate A and then plate B at alpha f, both in multiply, darkens the
    middle of the fade (A * B^f is darker than either). Blend the inks first and
    multiply once. Stages are quantised to ``step`` and cached, so a slow fade
    over hundreds of frames costs a few dozen blends."""

    def __init__(self, inks, step=0.02, max_cache=400):
        self.inks = [np.asarray(i, np.float32) for i in inks]
        self.step = step
        self.max_cache = max_cache
        self.cache = {}

    def at(self, stage):
        s = min(max(stage, 0.0), len(self.inks) - 1.0)
        s = round(round(s / self.step) * self.step, 6)
        if s not in self.cache:
            if len(self.cache) >= self.max_cache:
                self.cache.clear()
            i = min(int(math.floor(s)), len(self.inks) - 2)
            f = s - i
            self.cache[s] = self.inks[i] * (1 - f) + self.inks[i + 1] * f
        return self.cache[s]


# ---------------------------------------------------------------- motes ----

def motes(t, t0, n=80, origin=(0.0, 0.0), seed=3, spread=3.2, life=(2.6, 4.2),
          angle=(-2.4, -0.7), speed=(140, 330), curl=70, lift=90, radius=(1.6, 3.4)):
    """Small particles leaving ``origin`` on their own clocks (aroma, steam, sparks).

    Returns an ``(n, 4)`` array of ``x, y, r, alpha``; alpha is 0 for motes not
    yet born or already gone. Each mote gets its own birth time within
    ``spread`` seconds of ``t0``, its own heading, speed and curl, so the cloud
    never moves as one sprite. Angles are radians in screen coordinates
    (negative = upward)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 4))
    for j in range(n):
        ts = t0 + rng.uniform(0, spread)
        lf = rng.uniform(*life)
        ang = rng.uniform(*angle)
        sp = rng.uniform(*speed)
        cu = rng.uniform(-1, 1) * curl
        rad = rng.uniform(*radius)
        u = (t - ts) / lf
        if u <= 0 or u >= 1:
            continue
        x = origin[0] + math.cos(ang) * sp * u + cu * math.sin(u * 5 + j)
        y = origin[1] + math.sin(ang) * sp * u - lift * u * u
        a = min(u / 0.12, 1.0) * (1 - max(0.0, (u - 0.6) / 0.4))
        out[j] = (x, y, rad * (1 - 0.4 * u), a)
    return out


# ------------------------------------------------------------ set camera ----

class SetPan:
    """Scenes grouped into *sets* laid side by side on one long sheet.

    ``sets`` is ``[(index, start_time), ...]`` in film order; the camera slides
    from one set to the next, arriving ``lead`` seconds before the set's first
    line and taking ``dur`` seconds (smootherstep). ``__call__(t)`` returns the
    camera position in set units: set ``k`` is centred when it equals ``k``.
    Draw set ``k`` translated by ``(k - pos) * W``; ``speed_px`` gives the
    per-frame displacement for a motion blur along the pan."""

    def __init__(self, sets, dur=1.1, lead=0.75):
        self.sets = list(sets)
        self.dur = dur
        self.lead = lead

    def __call__(self, t):
        pos = float(self.sets[0][0]) if self.sets else 0.0
        for j in range(1, len(self.sets)):
            c = self.sets[j][1] - self.lead
            u = min(max((t - c) / self.dur, 0.0), 1.0)
            pos += (self.sets[j][0] - self.sets[j - 1][0]) * u * u * u * (u * (6 * u - 15) + 10)
        return pos

    def speed_px(self, t, fps, width):
        """Half the camera's displacement over one frame (a 180-degree shutter)."""
        return abs(self(t + 0.5 / fps) - self(t - 0.5 / fps)) * width * 0.5


def blur_along_x(img, v):
    """Box blur of an ``(H, W, C)`` float image along x by about ``v`` pixels."""
    if v <= 1.5:
        return img
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(img, size=int(round(v)) | 1, axis=1, mode="nearest")


# ------------------------------------------------------------ sprites ----

def crop_sprites(img, bg=None, thresh=40, min_area=5000, pad=12, close=4):
    """Cut the separate objects out of one generated plate (for example a row of
    beans at seven roast colours, or one bowl from a cupping table).

    ``img`` is an ``(H, W, 3)`` uint8/float array on plain paper. Returns a list of
    ``(x0, y0, x1, y1)`` boxes sorted left to right, each padded. Generating one
    plate that contains the whole progression and cropping it keeps the style,
    lighting and scale identical across the sprites, which separate generations
    do not."""
    from scipy import ndimage
    a = np.asarray(img, np.float32)
    if bg is None:
        bg = np.median(a[: max(4, a.shape[0] // 25)].reshape(-1, 3), axis=0)
    m = np.abs(a - np.asarray(bg, np.float32)).sum(axis=2) > thresh
    m = ndimage.binary_closing(m, iterations=close)
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    boxes = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if sl is None or (lab[sl] == k + 1).sum() < min_area:
            continue
        y0, y1 = max(sl[0].start - pad, 0), min(sl[0].stop + pad, a.shape[0])
        x0, x1 = max(sl[1].start - pad, 0), min(sl[1].stop + pad, a.shape[1])
        boxes.append((x0, y0, x1, y1))
    return sorted(boxes)
