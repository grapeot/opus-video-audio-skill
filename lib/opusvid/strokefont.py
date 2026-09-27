"""Single-stroke vector text: letters as polylines a pen or beam can draw, revealed word by word.

Uses the public-domain Hershey fonts (``pip install Hershey-Fonts``). Font units have y pointing down; the
``futural`` cap height is about 21 units (y from -12 to 9). Draw each polyline with your own line renderer
(``frac`` is how much of it is drawn), so text shares the stroke, glow and trails of everything else.

    words, width = layout("some words")
    times = word_times(line_start, next_line_start, vocal_onsets, len(words))
    for wi, poly, frac in reveal(words, times, t):
        draw(origin + poly * scale * [1, -1], frac)
"""
from __future__ import annotations

import numpy as np

CAP = 21.0
_FONTS = {}


def font(name="futural"):
    if name not in _FONTS:
        from HersheyFonts import HersheyFonts
        f = HersheyFonts()
        f.load_default_font(name)
        _FONTS[name] = f
    return _FONTS[name]


def strokes(text, name="futural"):
    """(list of polylines in font units, advance width) for one word."""
    out = [np.asarray(s, float) for s in font(name).strokes_for_text(text)]
    width = max((p[:, 0].max() for p in out), default=0.0)
    return out, float(width)


def layout(text, name="futural", space=12.0):
    """Words laid out left to right: (list per word of polylines, total width). Blank text gives ([], 0)."""
    words, x = [], 0.0
    for w in text.split():
        st, ww = strokes(w, name)
        words.append([p + [x, 0.0] for p in st])
        x += ww + space
    return words, max(x - space, 0.0)


def word_times(t0, t1, onsets, n):
    """``n`` word start times over the onsets in [t0, t1); the first word starts at ``t0``."""
    if n <= 0:
        return []
    on = np.asarray([x for x in onsets if t0 - 0.02 <= x < t1], float)
    if len(on) == 0 or on[0] > t0 + 0.1:
        on = np.r_[t0, on]
    if len(on) >= n:
        return [float(x) for x in on[np.round(np.linspace(0, len(on) - 1, n)).astype(int)]]
    if len(on) > 1:
        return [float(x) for x in np.interp(np.arange(n), np.linspace(0, n - 1, len(on)), on)]
    step = min(0.35, (t1 - t0) / n)
    return [float(t0 + k * step) for k in range(n)]


def reveal(words, times, t, base=0.05, per_stroke=0.03):
    """Yield (word index, polyline, frac) for everything visible at time ``t``: each word is written stroke by
    stroke starting at its time, over ``base + per_stroke * strokes`` seconds."""
    for wi, st in enumerate(words):
        if wi >= len(times) or t < times[wi]:
            break
        n_show = np.clip((t - times[wi]) / (base + per_stroke * len(st)), 0, 1) * len(st)
        for si, p in enumerate(st):
            f = float(np.clip(n_show - si, 0, 1))
            if f <= 0:
                break
            yield wi, p, f


def bbox(words):
    """(x0, y0, x1, y1) of laid-out words in font units."""
    pts = [p for w in words for p in w]
    if not pts:
        return (0.0, 0.0, 0.0, 0.0)
    a = np.vstack(pts)
    return float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max())
