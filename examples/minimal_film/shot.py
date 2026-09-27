"""The minimal film's timeline: one module that picture (render.py) and music
(make_cue.py) both import, so neither can drift from the other.

A glowing dot drifts left to right while the camera pushes in; the moment the
dot crosses the centre of the *screen* is solved from the motion, not read off
a preview. The title then writes itself one character at a time.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from opusvid.timeline import CameraPath, Events, ease_in_out, solve_time, world_to_pixel  # noqa: E402

W, H, FPS, DUR = 360, 640, 30, 3.0
N_FRAMES = int(round(FPS * DUR))
TITLE = "OPUSVID"

# camera keys: t, centre u, centre v, visible width (world units), rotation (deg)
CAM = CameraPath([(0.0, 0.00, 0.00, 3.0, 0.0),
                  (1.5, 0.20, -0.10, 2.2, 0.0),
                  (3.0, 0.40, -0.20, 1.6, 0.0)])


def dot_world(t):
    """The dot's position in world units."""
    u = -1.2 + 2.0 * ease_in_out(t / 1.9)
    return u, -0.35 + 0.12 * math.sin(2.1 * t)


def dot_pixel(t):
    cu, cv, width, rot = CAM(t)
    return world_to_pixel(*dot_world(t), cu, cv, width, W, H, rot)


# the dot crosses the vertical centre line of the frame (screen x = W/2)
_cross = solve_time(lambda t: float(dot_pixel(t)[0]), W / 2, 0.0, DUR)

E = Events(
    cross=round(_cross, 4),     # derived: the flash, and the harp note under it
    title=1.45,                 # first title character starts to write
    title_step=0.10,            # each next character follows this much later
    title_fade=0.40,            # how long one character takes to fade in
    fade=(2.4, 3.0),            # picture and music fade out together
)

if __name__ == "__main__":
    print(E.table())
