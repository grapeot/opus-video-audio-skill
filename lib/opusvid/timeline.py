"""Time: easing, named events, a keyframed camera path, and solving for event times.

Put every beat of a film in one module that both the renderer and the cue
generator import. Derived times (when a moving thing crosses a line, when a
counter ticks) are computed from the same motion functions the renderer uses
(:func:`solve_time`), never read off a preview, so a change to the motion moves
the music with it.

Needs numpy and scipy (``scipy.interpolate.PchipInterpolator``).
"""
from __future__ import annotations

import json
import math
from pathlib import Path


# ------------------------------------------------------------------ easing ----

def smooth(a, b, x):
    """Smoothstep from 0 at ``x <= a`` to 1 at ``x >= b``. Scalars or numpy arrays."""
    import numpy as np
    u = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0.0, 1.0)
    r = u * u * (3.0 - 2.0 * u)
    return float(r) if np.ndim(r) == 0 else r


def ease_in_out(u):
    """Cosine ease on ``u`` clamped to [0, 1]: zero velocity at both ends."""
    import numpy as np
    u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    r = 0.5 - 0.5 * np.cos(np.pi * u)
    return float(r) if np.ndim(r) == 0 else r


def log_lerp(a, b, u):
    """Interpolate a scale (field of view, width, zoom) geometrically: equal ratios
    per unit ``u``. Linear interpolation of a scale visibly races at the tight end."""
    return math.exp(math.log(a) + (math.log(b) - math.log(a)) * u)


# ------------------------------------------------------------------ events ----

class Events:
    """Named times and spans in one place.

    ::

        E = Events(title=1.2, title_step=0.12, fade=(2.4, 3.0))
        E.title             # 1.2
        E["fade"]           # (2.4, 3.0)
        E.ramp("fade", t)   # 0 before 2.4, smoothstep across the span, 1 after 3.0

    A value is a time in seconds, a ``(start, end)`` span, or any other scalar
    the timeline needs (a stagger step, a duration). Print :meth:`table` in the
    film's ``plan()``.
    """

    def __init__(self, **items):
        object.__setattr__(self, "_items", {})
        for k, v in items.items():
            self._items[k] = tuple(float(x) for x in v) if isinstance(v, (tuple, list)) \
                else float(v)

    def __getattr__(self, name):
        try:
            return self._items[name]
        except KeyError:
            raise AttributeError(f"no event {name!r}; have {sorted(self._items)}") from None

    def __getitem__(self, name):
        return self._items[name]

    def __setattr__(self, name, value):
        raise AttributeError("Events are fixed once defined; edit the definition instead")

    def __contains__(self, name):
        return name in self._items

    def items(self):
        return self._items.items()

    def span(self, name) -> tuple[float, float]:
        v = self._items[name]
        if not isinstance(v, tuple):
            raise TypeError(f"event {name!r} is a time, not a (start, end) span")
        return v

    def ramp(self, name, t):
        """0 before the span, smoothstep across it, 1 after."""
        return smooth(*self.span(name), t)

    def table(self) -> str:
        """One line per item, in definition order."""
        rows = []
        for k, v in self._items.items():
            rows.append(f"  {k:<18} {v[0]:7.3f} .. {v[1]:.3f}" if isinstance(v, tuple)
                        else f"  {k:<18} {v:7.3f}")
        return "\n".join(rows)


# ------------------------------------------------------------ camera path ----

class CameraPath:
    """A camera moved by keyframes, interpolated with PCHIP.

    ``keys`` is a list of ``(t, value_1, value_2, ...)`` tuples, one value per
    name in ``fields``; the default fields are a 2D view ``(cu, cv, width,
    rot_deg)``: centre in world units, visible width in world units, rotation in
    degrees. Fields named in ``log_fields`` (default: ``width``) are interpolated
    in log space, so a zoom across orders of magnitude moves at an even
    perceived speed instead of racing at the tight end.

    PCHIP (monotone piecewise cubic) passes exactly through every key and never
    overshoots between monotone keys, so a push-in that should settle does not
    bounce past its target. Outside the first/last key the camera holds still.

    ``cam(t)`` returns the values as a tuple in field order; ``cam.at(t)`` as a
    dict.
    """

    def __init__(self, keys, fields=("cu", "cv", "width", "rot_deg"),
                 log_fields=("width",)):
        import numpy as np
        from scipy.interpolate import PchipInterpolator

        keys = sorted(keys, key=lambda k: k[0])
        if len(keys) < 2:
            raise ValueError("a camera path needs at least two keys")
        width = len(fields) + 1
        for k in keys:
            if len(k) != width:
                raise ValueError(f"key {k} has {len(k) - 1} values, fields are {fields}")
        ts = np.array([k[0] for k in keys], float)
        if np.any(np.diff(ts) <= 0):
            raise ValueError("key times must be strictly increasing")
        self.fields = tuple(fields)
        self.log_fields = set(log_fields) & set(fields)
        self.t0, self.t1 = float(ts[0]), float(ts[-1])
        self.keys = keys
        self._f = []
        for j, name in enumerate(self.fields):
            vals = np.array([k[j + 1] for k in keys], float)
            if name in self.log_fields:
                if np.any(vals <= 0):
                    raise ValueError(f"log-interpolated field {name!r} must stay positive")
                vals = np.log(vals)
            self._f.append(PchipInterpolator(ts, vals))

    def __call__(self, t):
        t = min(max(float(t), self.t0), self.t1)
        out = []
        for name, f in zip(self.fields, self._f):
            v = float(f(t))
            out.append(math.exp(v) if name in self.log_fields else v)
        return tuple(out)

    camera = __call__

    def at(self, t) -> dict:
        return dict(zip(self.fields, self(t)))


def world_to_pixel(u, v, cu, cv, width, W, H, rot_deg=0.0):
    """Project world ``(u, v)`` through a 2D view to pixel ``(px, py)``.

    ``width`` world units span the frame's ``W`` pixels; ``v`` grows downward
    like pixel rows. With no rotation::

        px = (u - cu) / width * W + W / 2
        py = (v - cv) / width * W + H / 2

    The view is rotated by ``rot_deg``: a screen offset ``(x, y)`` shows world
    ``(cu + x cos a - y sin a, cv + x sin a + y cos a)``. Works on arrays.
    """
    import numpy as np
    a = math.radians(rot_deg)
    du, dv = np.asarray(u, float) - cu, np.asarray(v, float) - cv
    x = du * math.cos(a) + dv * math.sin(a)
    y = -du * math.sin(a) + dv * math.cos(a)
    return x / width * W + W / 2, y / width * W + H / 2


# ------------------------------------------------------------- solve_time ----

def solve_time(f, target, lo, hi, tol=1e-6, samples=256):
    """First time in ``[lo, hi]`` at which ``f(t)`` reaches ``target``.

    Scans ``samples`` points for the first sign change of ``f(t) - target``,
    then bisects inside that bracket to ``tol`` seconds. Use it for "when does
    this motion cross X" -- the upper limb clearing the horizon, a subject
    reaching the frame edge, a counter reaching the next integer -- so the cue
    note lands on the frame where the picture event happens.

    Raises ValueError when ``f`` never reaches ``target`` in the interval.
    """
    g = lambda t: f(t) - target
    if hi <= lo:
        raise ValueError("need lo < hi")
    prev_t, prev_g = lo, g(lo)
    if prev_g == 0:
        return float(lo)
    a = b = None
    for k in range(1, samples + 1):
        t = lo + (hi - lo) * k / samples
        gt = g(t)
        if gt == 0:
            return float(t)
        if (gt > 0) != (prev_g > 0):
            a, b = prev_t, t
            break
        prev_t, prev_g = t, gt
    if a is None:
        raise ValueError(f"f(t) does not reach {target} on [{lo}, {hi}] "
                         f"(f(lo)={g(lo) + target:.6g}, f(hi)={g(hi) + target:.6g})")
    ga = g(a)
    while b - a > tol:
        m = 0.5 * (a + b)
        gm = g(m)
        if gm == 0:
            return float(m)
        if (gm > 0) == (ga > 0):
            a, ga = m, gm
        else:
            b = m
    return float(0.5 * (a + b))


# ---------------------------------------------------------- camera export ----

def export_camera_json(path, frames, camera_fn, extra_fn=None, *, W, H, fps,
                       fields=("cu", "cv", "width", "rot_deg"), digits=6):
    """Write a per-frame camera file for another renderer (e.g. a Blender plate).

    ``camera_fn(t)`` returns the view values in ``fields`` order (a
    :class:`CameraPath` works directly); ``extra_fn(t)``, if given, returns a
    dict of any animated scalars the other layer must match (a light ramp, a
    reveal radius). The file::

        {"W": 1080, "H": 1920, "fps": 30,
         "fields": ["cu", "cv", "width", "rot_deg"],
         "pixel_formula": "px = (u-cu)/width*W + W/2; py = (v-cv)/width*W + H/2",
         "frames": [{"frame": 270, "t": 9.0, "cu": ..., "cv": ..., "width": ...,
                     "rot_deg": 0.0, "light": 0.0}, ...]}

    ``cu, cv`` is the view centre and ``width`` the horizontal extent, both in
    world units, with ``v`` growing downward like pixel rows; see
    :func:`world_to_pixel` for rotation. The receiving side should project a few
    known world points through its actual camera and compare against this
    formula before rendering the sequence.
    """
    rows = []
    for i in frames:
        t = i / fps
        vals = camera_fn(t)
        if len(vals) != len(fields):
            raise ValueError(f"camera_fn returned {len(vals)} values for fields {fields}")
        row = {"frame": int(i), "t": round(t, digits)}
        row.update({k: round(float(v), digits) for k, v in zip(fields, vals)})
        if extra_fn is not None:
            row.update({k: round(float(v), digits) for k, v in extra_fn(t).items()})
        rows.append(row)
    doc = {"W": int(W), "H": int(H), "fps": fps, "fields": list(fields),
           "pixel_formula": "px = (u-cu)/width*W + W/2; py = (v-cv)/width*W + H/2"
                            " (rot_deg = 0; v grows downward)",
           "frames": rows}
    Path(path).write_text(json.dumps(doc, indent=1) + "\n")
    return doc
