"""opusvid -- a thin toolkit for short films rendered frame by frame from Python.

Only the code that every film of this kind ends up rewriting lives here:

  runner    the frame-render harness (CLI, worker pool, fresh output directories)
  timeline  easing, named events, a PCHIP camera path, solve_time, camera export
  typeset   glyph masks, letter-spaced lines, vertical columns, timed reveals
  narration voice takes on one clock, when a phrase is spoken, subtitles, SRT

Everything that makes a film *that* film -- its subject, shading, layout -- stays
in the film's own script. This is a toolkit, not a framework.

Not an installed package: put the repository's ``lib/`` directory on
``sys.path`` (or ``PYTHONPATH=lib``) and ``import opusvid.timeline``.

Dependencies: numpy, scipy (PCHIP, Gaussian blur) and Pillow. The package
import itself pulls in nothing; each module imports what it needs.
"""

__all__ = ["runner", "timeline", "typeset", "narration"]
