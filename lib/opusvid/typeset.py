"""On-screen text for float images: coverage masks, blended by hand.

Why by hand: ``PIL.ImageDraw`` on an RGB image silently ignores the alpha in
``fill``, so text you believe is fading stays fully opaque. Here every glyph is
rendered to a coverage mask (float32 in [0, 1]) and blended into a float image
``img`` (HxWx3, values in [0, 1], display space -- i.e. after the tone map)::

    img[region] = img[region] * (1 - mask * alpha) + colour * mask * alpha

Fonts are always parameters. :func:`load_font` with no path returns Pillow's
built-in scalable font (Latin only, Pillow >= 10.1). For CJK pass a font file;
on macOS, for example, ``/System/Library/Fonts/Hiragino Sans GB.ttc`` or
``/System/Library/Fonts/STHeiti Medium.ttc`` (``.ttc`` collections take an
``index``). Nothing here requires a particular font to exist.

Needs numpy and Pillow; :func:`soft_bed` also needs scipy.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_font(path=None, size=48, index=0):
    """A FreeType font at ``size`` px, or Pillow's built-in font if ``path`` is None."""
    if path is None:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:                   # Pillow < 10.1: fixed-size bitmap font
            return ImageFont.load_default()
    return ImageFont.truetype(str(path), size, index=index)


def glyph_mask(ch, font, pad=4):
    """Coverage mask of one character, tight to its ink plus ``pad`` px each side."""
    l, t, r, b = font.getbbox(ch)
    m = Image.new("L", (max(r - l, 1) + 2 * pad, max(b - t, 1) + 2 * pad), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), ch, font=font, fill=255)
    return np.asarray(m, np.float32) / 255.0


def _advance(ch, font):
    if ch.isspace():
        return max(1, int(round(getattr(font, "size", 12) / 3)))
    l, _, r, _ = font.getbbox(ch)
    return max(r - l, 1)


def text_mask(text, font, spacing=0, pad=10):
    """Mask of a horizontal line with ``spacing`` extra pixels between characters.

    Characters are placed by their ink width, not the font's advance, so the
    tracking is even; a space advances by a third of the font size. All
    characters share one baseline.
    """
    widths = [_advance(ch, font) for ch in text]
    tw = sum(widths) + spacing * max(len(text) - 1, 0)
    _, top, _, bot = font.getbbox(text)
    m = Image.new("L", (tw + 2 * pad, (bot - top) + 2 * pad), 0)
    d = ImageDraw.Draw(m)
    x = pad
    for ch, w in zip(text, widths):
        if not ch.isspace():
            d.text((x - font.getbbox(ch)[0], pad - top), ch, font=font, fill=255)
        x += w + spacing
    return np.asarray(m, np.float32) / 255.0


def char_boxes(text, font, spacing=0, pad=10):
    """Left edge and width (px, within :func:`text_mask`'s mask) of each character,
    for revealing a line character by character."""
    boxes, x = [], pad
    for ch in text:
        w = _advance(ch, font)
        boxes.append((x, w))
        x += w + spacing
    return boxes


def blend_mask(img, mask, x, y, colour, alpha=1.0):
    """Blend ``colour`` through ``mask`` into float ``img`` with its top-left at (x, y).

    ``alpha`` scales the mask. The mask is clipped to the image bounds, so text
    partly off-frame is fine. Modifies ``img`` in place and returns it.
    """
    if alpha <= 0.002:
        return img
    H, W = img.shape[:2]
    h, w = mask.shape
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return img
    m = mask[y0 - y:y1 - y, x0 - x:x1 - x] * float(alpha)
    a = m[..., None]
    col = np.asarray(colour, dtype=img.dtype).reshape(1, 1, -1)
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + col * a
    return img


def soft_bed(mask, sigma=6.0, strength=0.9):
    """A blurred copy of ``mask`` to blend in a dark colour *under* text, so it
    stays legible over bright detail (sparks, highlights). Blend it at a lower
    alpha than the text itself (~0.45 of it)."""
    from scipy.ndimage import gaussian_filter
    pad = int(np.ceil(3 * sigma))
    big = np.pad(mask, pad)
    return np.clip(gaussian_filter(big, sigma) * strength, 0, 1).astype(np.float32), pad


def reveal_alphas(n, t, t0, step, fade=0.5):
    """Per-character opacity for a timed reveal: character ``j`` fades in over
    ``[t0 + j*step, t0 + j*step + fade]``. Reads as writing, and gives the music
    one onset per character (:func:`char_onsets`)."""
    out = []
    for j in range(n):
        a = t0 + j * step
        u = min(max((t - a) / fade, 0.0), 1.0)
        out.append(u * u * (3 - 2 * u))
    return out


def char_onsets(n, t0, step):
    """The time each character starts to appear -- the same numbers the cue uses."""
    return [t0 + j * step for j in range(n)]


def _bed(img, mask, x, y, bed):
    if bed > 0:
        b, pad = soft_bed(mask)
        blend_mask(img, b, x - pad, y - pad, (0.0, 0.0, 0.0), bed)


def draw_line(img, text, font, cx, cy, colour, alpha=1.0, spacing=0, reveal=None, bed=0.0):
    """Draw a horizontal line centred on (cx, cy).

    ``reveal`` is an optional list of per-character alphas (see
    :func:`reveal_alphas`) multiplied into ``alpha``. ``bed`` > 0 first blends a
    soft dark bed under the text at that opacity. Returns the mask's box
    ``(x, y, w, h)``.
    """
    m = text_mask(text, font, spacing)
    h, w = m.shape
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    if reveal is not None:
        # each character owns the columns from its left edge (minus half the
        # spacing, to catch anti-aliased fringes) to the next character's
        weights = np.zeros(w, np.float32)
        boxes = char_boxes(text, font, spacing)
        edges = [0] + [bx - spacing // 2 for bx, _ in boxes[1:]] + [w]
        for j, a in enumerate(reveal[:len(boxes)]):
            weights[edges[j]:edges[j + 1]] = a
        m = m * weights[None, :]
    _bed(img, m, x, y, bed * alpha)
    blend_mask(img, m, x, y, colour, alpha)
    return x, y, w, h


def draw_column(img, text, font, cx, top, step, colour, alpha=1.0, reveal=None, bed=0.0):
    """Vertical text (CJK style): one glyph per ``step`` px, each centred in its cell.

    The column occupies ``[top, top + len(text) * step)`` vertically, centred on
    ``cx``. ``reveal`` and ``bed`` as in :func:`draw_line`. Returns the bottom y.
    """
    for j, ch in enumerate(text):
        a = alpha * (reveal[j] if reveal is not None else 1.0)
        if a <= 0.002 or ch.isspace():
            continue
        m = glyph_mask(ch, font)
        h, w = m.shape
        x, y = cx - w / 2, top + j * step + (step - h) / 2
        _bed(img, m, x, y, bed * a)
        blend_mask(img, m, x, y, colour, a)
    return top + len(text) * step
