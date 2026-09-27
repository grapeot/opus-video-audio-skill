"""The frame-render harness: one CLI and one worker pool around ``render_frame(i)``.

A film script defines ``render_frame(i) -> image`` and hands it to :func:`run`::

    from opusvid.runner import run

    def init():                 # once per worker: fonts, textures, noise fields
        G["font"] = ...

    def render_frame(i):        # the same function renders previews and the film
        ...
        return img              # HxWx3 uint8, float in [0, 1], or a PIL image

    if __name__ == "__main__":
        raise SystemExit(run(render_frame, N_FRAMES, init=init, plan=plan))

The command line it provides::

    python film.py --out frames_run1                     # the whole film
    python film.py --out preview_run1 --frames 0,45,89   # a preview: same code path
    python film.py --out preview_run2 --frames 0:30,60   # a:b is half-open, like a slice
    python film.py --plan                                # print the plan, render nothing
    python film.py --out frames_run1 --overwrite         # reuse a directory, deliberately

Why the rules:

* **Preview and production share ``render_frame``.** A preview script that
  reimplements the loop drifts from it, and then you validate a program you are
  not shipping. ``--frames`` is the preview.
* **Fresh output directory per run.** Waiting on a file count, or opening
  ``f0120.png`` in a directory that already held last run's frames, reviews
  stale images. :func:`run` refuses a non-empty ``--out`` unless ``--overwrite``
  is given; ``--overwrite`` deletes nothing, so a stale frame the new run did not
  replace is still caught by ``check_frames.py frames --since``.
* **The run start is recorded** in ``<out>/run_start.txt`` (unix time) and
  printed with the matching ``check_frames.py frames ... --since`` command.
* **Per-worker resources come from ``init``**, run once in every worker process
  (fonts, loaded textures, precomputed noise), not once per frame.

``render_frame`` and ``init`` must be module-level functions so that worker
processes can import them (macOS starts workers with ``spawn``), and the script
must keep its entry point under ``if __name__ == "__main__":``.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

START_FILE = "run_start.txt"


class FrameSpecError(ValueError):
    pass


def parse_frames(spec: str | None, n_frames: int) -> list[int]:
    """Parse ``--frames``: comma-separated indices and half-open ``a:b`` ranges.

    ``None`` or ``""`` means every frame. ``a:`` runs to the end, ``:b`` from 0,
    and ``a:b:s`` steps by ``s``. Indices must lie in ``[0, n_frames)``. The
    result is sorted with duplicates removed.
    """
    if spec is None or not spec.strip():
        return list(range(n_frames))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if ":" in part:
                bits = part.split(":")
                if len(bits) > 3:
                    raise ValueError
                a = int(bits[0]) if bits[0].strip() else 0
                b = int(bits[1]) if bits[1].strip() else n_frames
                s = int(bits[2]) if len(bits) == 3 and bits[2].strip() else 1
                if s <= 0:
                    raise FrameSpecError(f"step must be positive in {part!r}")
                if a < 0 or b > n_frames or a >= b:
                    raise FrameSpecError(
                        f"range {part!r} is empty or outside 0:{n_frames}")
                out.update(range(a, b, s))
            else:
                i = int(part)
                if not 0 <= i < n_frames:
                    raise FrameSpecError(f"frame {i} is outside 0..{n_frames - 1}")
                out.add(i)
        except FrameSpecError:
            raise
        except ValueError:
            raise FrameSpecError(f"cannot parse frame spec {part!r} "
                                 f"(use e.g. 0,45,89 or 0:30 or 0:90:10)") from None
    if not out:
        raise FrameSpecError(f"frame spec {spec!r} selects no frames")
    return sorted(out)


def check_out_dir(path: str | os.PathLike, overwrite: bool = False) -> str | None:
    """Return an error message if ``path`` holds anything and ``overwrite`` is off."""
    p = Path(path)
    if p.exists() and not p.is_dir():
        return f"--out {p} exists and is not a directory"
    if p.is_dir() and not overwrite:
        entries = sorted(e.name for e in p.iterdir())
        if entries:
            shown = ", ".join(entries[:3]) + (" ..." if len(entries) > 3 else "")
            return (f"--out {p} is not empty ({len(entries)} entries: {shown}). "
                    f"Render each run into a fresh directory so stale frames cannot "
                    f"be reviewed, or pass --overwrite deliberately.")
    return None


def to_uint8(img):
    """Accept HxWx3 uint8, a float image in [0, 1], or a PIL image; return uint8."""
    import numpy as np
    if hasattr(img, "save") and not isinstance(img, np.ndarray):
        return np.asarray(img.convert("RGB"))
    a = np.asarray(img)
    if a.dtype == np.uint8:
        return a
    return (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# ------------------------------------------------------------ worker side ----

_W: dict = {}


def _worker_init(render_frame, out, name_fmt, init, init_args):
    _W.update(render=render_frame, out=out, fmt=name_fmt)
    if init is not None:
        init(*init_args)


def _work(i):
    from PIL import Image
    img = to_uint8(_W["render"](i))
    Image.fromarray(img).save(os.path.join(_W["out"], _W["fmt"].format(i)))
    return i


# ------------------------------------------------------------------- run ----

def build_parser(n_frames: int, default_jobs: int | None = None) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=f"Render frames of this film ({n_frames} in total).")
    ap.add_argument("--out", help="output directory; must be new or empty "
                                  "(one fresh directory per run)")
    ap.add_argument("--frames", default=None,
                    help="subset to render, e.g. 0,45,89 or 0:30,60 (a:b is half-open); "
                         "default: every frame")
    ap.add_argument("--jobs", type=int, default=default_jobs or os.cpu_count() or 1,
                    help="worker processes (1 renders in this process, handy for debugging)")
    ap.add_argument("--plan", action="store_true",
                    help="print the film's plan (camera/event table) and exit")
    ap.add_argument("--overwrite", action="store_true",
                    help="allow a non-empty --out; nothing is deleted, so check "
                         "freshness with check_frames.py frames --since")
    return ap


def run(render_frame, n_frames: int, init=None, plan=None, argv=None, *,
        init_args: tuple = (), name_fmt: str = "f{:04d}.png",
        default_jobs: int | None = None) -> int:
    """Parse the CLI, then render the selected frames. Returns a process exit code.

    render_frame  module-level ``f(i) -> image`` (uint8 / float [0,1] / PIL)
    n_frames      frames in the film; ``--frames`` indexes into ``range(n_frames)``
    init          module-level ``init(*init_args)``, run once per worker process
    plan          ``plan()`` printing the film's table for ``--plan``
    argv          argument list (default: ``sys.argv[1:]``)
    """
    ap = build_parser(n_frames, default_jobs)
    a = ap.parse_args(argv)

    if a.plan:
        if plan is None:
            print("this film defines no plan()", file=sys.stderr)
            return 2
        plan()
        return 0
    if not a.out:
        print("--out is required (a fresh directory for this run)", file=sys.stderr)
        return 2
    try:
        idx = parse_frames(a.frames, n_frames)
    except FrameSpecError as e:
        print(f"--frames: {e}", file=sys.stderr)
        return 2
    err = check_out_dir(a.out, a.overwrite)
    if err:
        print(f"refusing to render: {err}", file=sys.stderr)
        return 2

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    (out / START_FILE).write_text(f"{start:.3f}\n")
    jobs = max(1, min(a.jobs, len(idx)))
    print(f"rendering {len(idx)} frame(s) into {out} with {jobs} worker(s)", flush=True)

    done = 0
    step = max(1, len(idx) // 10)
    if jobs == 1:
        _worker_init(render_frame, str(out), name_fmt, init, init_args)
        it = map(_work, idx)
        pool = None
    else:
        pool = Pool(jobs, initializer=_worker_init,
                    initargs=(render_frame, str(out), name_fmt, init, init_args))
        it = pool.imap_unordered(_work, idx)
    try:
        for _ in it:
            done += 1
            if done % step == 0 or done == len(idx):
                print(f"  {done}/{len(idx)}  {time.time() - start:6.1f}s", flush=True)
    except BaseException:
        if pool is not None:
            pool.terminate()        # a failed frame stops the run; do not finish the rest
        raise
    if pool is not None:
        pool.close()
        pool.join()

    secs = time.time() - start
    print(f"wrote {len(idx)} frame(s) to {out} in {secs:.1f}s")
    expect = f" --expect {n_frames}" if len(idx) == n_frames else ""
    print(f"verify with: python scripts/check_frames.py frames {out}"
          f"{expect} --since {int(start)}")
    return 0
