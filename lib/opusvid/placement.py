"""Place on-screen text where the picture is empty, measured rather than guessed.

Render the frame *without* the text at several moments of the text's life, turn each render into an ink map,
and score candidate positions by how much ink the text box would cover, whether the box leaves the frame (for
world-anchored text the camera carries it), and whether it collides with other text still on screen. When the
camera zooms a lot during the text's life, world-anchored text shrinks to nothing: anchor it to the screen.
Where nothing is clean, `clearing_band` darkens a feathered band under the text so it still reads.

Cameras are ``(cx, cy, px_per_unit)`` in world units with y up; screen origin top-left.

    ii = ink_integral(scene_luma)                 # one per sample time
    best = choose(text_w_px, text_h_px, [(ii0, cam0), (ii1, cam1), (ii2, cam2)],
                  candidates(), occupied=[box_of_other_text])
    ...
    clearing_band([buf], text_box_px, strength=0.85)

Needs numpy and scipy.
"""
from __future__ import annotations

import itertools

import numpy as np


def ink_integral(lum, blur=6.0, full=0.05):
    """Integral image of an ink map: ``lum`` blurred by ``blur`` px (glow), saturating at ``full``."""
    from scipy.ndimage import gaussian_filter
    m = np.clip(gaussian_filter(np.asarray(lum, float), blur) / full, 0, 1)
    return np.pad(m, ((1, 0), (1, 0))).cumsum(0).cumsum(1)


def box_ink(ii, x0, y0, x1, y1):
    """(mean ink inside the box, fraction of the box outside the frame) for an integral image ``ii``."""
    H, W = ii.shape[0] - 1, ii.shape[1] - 1
    xa, ya = int(np.clip(x0, 0, W)), int(np.clip(y0, 0, H))
    xb, yb = int(np.clip(x1, 0, W)), int(np.clip(y1, 0, H))
    area = max((x1 - x0) * (y1 - y0), 1e-9)
    vis = max((xb - xa) * (yb - ya), 0)
    ink = ii[yb, xb] - ii[ya, xb] - ii[yb, xa] + ii[ya, xa] if vis > 0 else 0.0
    return float(ink / area), float(1 - vis / area)


def candidates(xs=(0.5, 0.3, 0.7, 0.2, 0.8), ys=(0.84, 0.16, 0.74, 0.26, 0.92, 0.08, 0.62, 0.38),
               scales=(1.0, 0.8, 0.65)):
    """Candidate (x, y, scale) as fractions of the frame; the first entries are preferred on ties."""
    return list(itertools.product(scales, ys, xs))


def carried_box(X, Y, w, h, cam0, cam, W, H):
    """Box (x0, y0, x1, y1) at camera ``cam`` of text written centred at screen (X, Y) under ``cam0``."""
    wx = cam0[0] + (X - W / 2) / cam0[2]
    wy = cam0[1] - (Y - H / 2) / cam0[2]
    sx = W / 2 + (wx - cam[0]) * cam[2]
    sy = H / 2 - (wy - cam[1]) * cam[2]
    s = cam[2] / cam0[2]
    return sx - w * s / 2, sy - h * s / 2, sx + w * s / 2, sy + h * s / 2


def choose(text_w, text_h, samples, cands=None, occupied=(), prefs=None, zoom_limit=2.5, off_weight=3.0,
           collide_weight=2.0, collide_margin=(40, 70), pad=(12, 10), edge=30, scale_cost=0.03):
    """Pick the best placement for a text of ``text_w`` x ``text_h`` px (at scale 1).

    samples   list of (integral image, camera) over the text's life, first = when it is written.
              camera None means the shot has no camera (screen anchoring is implied).
    occupied  boxes (x0, y0, x1, y1) of other text on screen during this text's life.
    prefs     {(x, y): cost} small bonuses/penalties per position; unlisted positions cost 0.04.
    Returns dict(x, y, scale, screen, cost).
    """
    cands = cands or candidates()
    prefs = prefs if prefs is not None else {(0.5, 0.84): 0.0, (0.5, 0.16): 0.01}
    H, W = samples[0][0].shape[0] - 1, samples[0][0].shape[1] - 1
    cams = [c for _, c in samples if c is not None]
    screen = not cams or max(max(a[2] / b[2], b[2] / a[2]) for a in cams for b in cams) > zoom_limit
    best = None
    for sc, fy, fx in cands:
        w, h = text_w * sc, text_h * sc
        X, Y = fx * W, fy * H
        if X - w / 2 < edge or X + w / 2 > W - edge:
            continue
        cost = prefs.get((fx, fy), 0.04) + (scale_cost if sc < 1 else 0) + (scale_cost if sc < 0.7 else 0)
        for ii, cam in samples:
            if screen or cam is None:
                x0, y0, x1, y1 = X - w / 2, Y - h / 2, X + w / 2, Y + h / 2
            else:
                x0, y0, x1, y1 = carried_box(X, Y, w, h, samples[0][1], cam, W, H)
            ink, off = box_ink(ii, x0 - pad[0], y0 - pad[1], x1 + pad[0], y1 + pad[1])
            cost += ink + off_weight * off
        mx, my = collide_margin
        for b in occupied:
            if not (b[2] + mx < X - w / 2 or b[0] - mx > X + w / 2 or b[3] + my < Y - h / 2 or b[1] - my > Y + h / 2):
                cost += collide_weight
        if best is None or cost < best["cost"]:
            best = dict(x=fx, y=fy, scale=sc, screen=bool(screen), cost=float(cost))
    return best


def clearing_band(bufs, box, strength=0.85, feather=24):
    """Darken a feathered band under text box (x0, y0, x1, y1) in each float buffer, in place."""
    x0, y0, x1, y1 = box
    H, W = bufs[0].shape[:2]
    xa, xb = int(max(x0 - feather, 0)), int(min(x1 + feather, W))
    ya, yb = int(max(y0 - feather, 0)), int(min(y1 + feather, H))
    if xa >= xb or ya >= yb:
        return
    gx, gy = np.arange(xa, xb), np.arange(ya, yb)
    fx = np.clip(np.minimum(gx - (x0 - feather), (x1 + feather) - gx) / feather, 0, 1)
    fy = np.clip(np.minimum(gy - (y0 - feather), (y1 + feather) - gy) / feather, 0, 1)
    m = np.outer(fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)) * strength
    for b in bufs:
        sl = b[ya:yb, xa:xb]
        sl *= (1 - m) if sl.ndim == 2 else (1 - m)[..., None]


def boxes_overlap(a, b, margin=(0, 0)):
    """True if boxes (x0, y0, x1, y1) intersect after growing ``b`` by ``margin``."""
    mx, my = margin
    return not (b[2] + mx < a[0] or b[0] - mx > a[2] or b[3] + my < a[1] or b[1] - my > a[3])
