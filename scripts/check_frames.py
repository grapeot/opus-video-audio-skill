#!/usr/bin/env python3
"""check_frames.py - verify a rendered frame sequence before you ship it.

An agent cannot judge a shot by looking at parameters, and it is prone to two
specific mistakes: reviewing frames left over from a previous run, and trusting
numbers that cannot see composition problems. This script covers the part that
IS mechanical -- freshness, exposure, halo boxes, seams, and stream integrity --
so the human's attention (and yours) goes to the part that is not.

Subcommands
-----------
  frames   exposure / freshness / halo-box / seam checks on a PNG sequence
  sheet    contact sheet of the frames at given timestamps, each labelled
  plan     angular-size table: is the subject the size you think, and on-frame?
  stream   ffprobe geometry + full decode of a finished mp4

Examples
--------
  python check_frames.py frames frames_v4 --expect 240 --since 1727300000
  python check_frames.py frames frames_v4 --ignore-region 180,760,830,790
  python check_frames.py sheet frames_v4 --fps 24 --times 0.5,2,4,6,9.5 --out sheet.png
  python check_frames.py plan --angular-size 0.52 --height 1920 --fov 100,20,3.1
  python check_frames.py stream out.mp4 --expect-duration 10 --expect-fps 24
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- frames ----

def _luma(path):
    return np.asarray(Image.open(path).convert("RGB"), float).mean(-1)


def _profile_steps(L, keep, axis):
    """|change in mean luminance| between adjacent columns (axis=0) or rows (axis=1),
    measured only over pixel pairs where both pixels are outside the ignored boxes.
    With nothing ignored this is exactly |diff| of the column/row means."""
    if axis == 1:                           # rows: transpose so we always step along axis 1
        L, keep = L.T, keep.T
    d = L[:, 1:] - L[:, :-1]
    k = keep[:, 1:] & keep[:, :-1]
    n = k.sum(0)
    tot = np.where(k, d, 0.0).sum(0)
    out = np.zeros(n.shape)
    np.divide(tot, n, out=out, where=n > 0)
    return np.abs(out)


def _region(text):
    try:
        x0, y0, x1, y1 = (int(round(float(v))) for v in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected x0,y0,x1,y1, got {text!r}")
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError(f"empty region {text!r}: need x0<x1 and y0<y1")
    return x0, y0, x1, y1


def cmd_frames(a):
    d = Path(a.directory)
    files = sorted(d.glob("*.png"))
    if not files:
        print(f"FAIL  no PNG frames in {d}")
        return 1

    problems = []
    print(f"{len(files)} frames in {d}")

    # --- freshness: are these from THIS run? -------------------------------
    mtimes = [f.stat().st_mtime for f in files]
    newest, oldest = max(mtimes), min(mtimes)
    print(f"  mtime span  {time.strftime('%H:%M:%S', time.localtime(oldest))}"
          f" .. {time.strftime('%H:%M:%S', time.localtime(newest))}")
    if a.since is not None and oldest < a.since:
        stale = sum(1 for m in mtimes if m < a.since)
        problems.append(f"{stale} frame(s) older than --since: reviewing a previous run")
    if newest - oldest > a.max_span_s:
        problems.append(f"mtime span {newest - oldest:.0f}s exceeds --max-span-s "
                        f"({a.max_span_s}s): frames may be mixed across runs")

    if a.expect and len(files) != a.expect:
        problems.append(f"expected {a.expect} frames, found {len(files)}")

    # --- sample a spread of frames ----------------------------------------
    idx = sorted({0, len(files) // 4, len(files) // 2, 3 * len(files) // 4, len(files) - 1})
    rows = []
    for i in idx:
        L = _luma(files[i])
        H, W = L.shape
        c = a.corner
        corner = float(np.mean([L[:c, :c].mean(), L[:c, -c:].mean(),
                                L[-c:, :c].mean(), L[-c:, -c:].mean()]))
        rows.append(dict(frame=i, name=files[i].name, corner=corner,
                         p10=float(np.percentile(L, 10)),
                         p50=float(np.percentile(L, 50)),
                         p90=float(np.percentile(L, 90)),
                         peak=float(L.max())))

    print(f"\n  {'frame':>6}  {'corner':>7}  {'p10':>5}  {'p50':>5}  {'p90':>6}  {'peak':>6}")
    for r in rows:
        print(f"  {r['frame']:>6}  {r['corner']:>7.1f}  {r['p10']:>5.0f}"
              f"  {r['p50']:>5.0f}  {r['p90']:>6.0f}  {r['peak']:>6.0f}")

    worst_corner = max(r["corner"] for r in rows)
    if worst_corner > a.max_corner:
        problems.append(f"frame corner luminance {worst_corner:.1f} > {a.max_corner}: "
                        f"light is leaking frame-wide (sky floor too high, or a halo flooding). "
                        f"If the sky is lit by design (moonlit, twilight), raise --max-corner "
                        f"deliberately and say so")
    if all(r["p90"] - r["p10"] < a.min_spread for r in rows):
        problems.append(f"tonal spread below {a.min_spread} in every sampled frame: "
                        f"image is flat (check tone mapping / contrast). A night scene that is "
                        f"mostly dark by design also trips this; judge it by looking")

    # --- halo boxes: look for straight vertical/horizontal steps ----------
    # Pixel pairs touching an --ignore-region box are left out of the step
    # measurement, so the box's own edges do not create new steps.
    L = _luma(files[idx[len(idx) // 2]])
    H, W = L.shape
    keep = np.ones_like(L, dtype=bool)
    for (x0, y0, x1, y1) in a.ignore_region or []:
        keep[max(y0, 0):min(y1, H), max(x0, 0):min(x1, W)] = False
    if a.ignore_region:
        print(f"\n  step check ignores {len(a.ignore_region)} region(s), "
              f"{100 * (1 - keep.mean()):.1f}% of the frame")
    ref = max(float(L[keep].mean()) if keep.any() else 0.0, 1e-6)
    for name, axis in (("column", 0), ("row", 1)):
        d1 = _profile_steps(L, keep, axis)
        if d1.size and d1.max() > a.step_thresh * ref:
            at = int(np.argmax(d1))
            problems.append(f"sharp {name} step at {at} "
                            f"(jump {d1.max():.1f}): possible halo box edge or seam. "
                            f"A straight bright edge or wire in the design is a common "
                            f"false positive; if that is what is there, exclude it with "
                            f"--ignore-region x0,y0,x1,y1 and say so")

    # --- seam: only meaningful for split-screen frames ---------------------
    # A centred subject (a moon, its reflection path) trips this on an
    # ordinary single-camera shot, so it is opt-in.
    if a.seam:
        W = L.shape[1]
        mid = W // 2
        seam = L[:, mid - 1:mid + 2].mean()
        near = np.mean([L[:, mid - 60:mid - 40].mean(), L[:, mid + 40:mid + 60].mean()])
        print(f"\n  seam columns {seam:.1f} vs neighbours {near:.1f}")
        if abs(seam - near) > a.seam_tol:
            problems.append(f"midline luminance {seam:.1f} differs from neighbours "
                            f"{near:.1f} by >{a.seam_tol}: visible seam")

    print()
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    frames pass the mechanical checks")
    print("\n  Numbers cannot see composition. Open the opening frame, each")
    print("  transition beat, and the final frame as images before shipping.")
    return 1 if problems else 0


# ----------------------------------------------------------------- sheet ----

def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                       # Pillow < 10.1: fixed-size bitmap font
        return ImageFont.load_default()


def cmd_sheet(a):
    from PIL import ImageDraw
    d = Path(a.directory)
    files = sorted(d.glob("*.png"))
    if not files:
        print(f"FAIL  no PNG frames in {d}")
        return 1
    try:
        times = [float(t) for t in a.times.split(",") if t.strip()]
    except ValueError:
        print(f"FAIL  --times must be comma-separated seconds, got {a.times!r}")
        return 1
    if not times:
        print("FAIL  --times is empty")
        return 1

    picks, bad = [], []
    for t in times:
        i = int(round(t * a.fps))
        if i < 0 or i >= len(files):
            bad.append(f"t={t:g}s -> frame {i} (sequence has {len(files)} frames, "
                       f"{len(files) / a.fps:.2f}s at {a.fps:g}fps)")
        else:
            picks.append((t, i, files[i]))
    for b in bad:
        print(f"  FAIL  out of range: {b}")
    if bad:
        return 1

    with Image.open(picks[0][2]) as first:
        fw, fh = first.size
    tw = a.width
    th = int(round(fh * tw / fw))
    label_h = max(16, tw // 12)
    font = _font(int(label_h * 0.7))
    cols = a.cols or min(len(picks), 6)
    rows = (len(picks) + cols - 1) // cols
    gap = 4
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap,
                              rows * (th + label_h) + (rows + 1) * gap), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for k, (t, i, f) in enumerate(picks):
        r, c = divmod(k, cols)
        x = gap + c * (tw + gap)
        y = gap + r * (th + label_h + gap)
        with Image.open(f) as src:
            im = src.convert("RGB").resize((tw, th), Image.LANCZOS)
        sheet.paste(im, (x, y + label_h))
        draw.text((x + 4, y + 2), f"t={t:.2f}s  {f.name}", fill=(235, 235, 235), font=font)
        print(f"  t={t:>7.2f}s  frame {i:>5}  {f.name}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"\n  wrote {out} ({sheet.width}x{sheet.height}, {len(picks)} tiles, {cols} per row)")
    print("  Frame index = round(t * fps) into the sorted PNG list; a sequence that")
    print("  does not start at t=0 needs its times shifted accordingly.")
    return 0


# ------------------------------------------------------------------ plan ----

def cmd_plan(a):
    fovs = [float(x) for x in a.fov.split(",")]
    print(f"subject angular size {a.angular_size}deg, frame height {a.height}px\n")
    print(f"  {'fov_v':>8}  {'subject_px':>11}  {'verdict'}")
    bad = False
    for f in fovs:
        px = a.angular_size / f * a.height
        if px < a.min_px:
            verdict = f"too small (<{a.min_px}px): invisible at this field"
            bad = True
        elif px > a.height:
            verdict = "larger than the frame"
        else:
            verdict = "ok"
        print(f"  {f:>8.2f}  {px:>11.0f}  {verdict}")

    if a.subject_alt is not None:
        print(f"\n  subject at {a.subject_alt}deg elevation; row of the 0deg horizon:")
        print(f"  {'fov_v':>8}  {'subject_row':>12}  {'horizon_row':>12}  {'verdict'}")
        for f in fovs:
            # camera aimed at the subject, frame centred on it
            srow = a.height / 2
            hrow = a.height / 2 + a.subject_alt / f * a.height
            ok = 0 <= hrow <= a.height
            if not ok:
                bad = True
            print(f"  {f:>8.2f}  {srow:>12.0f}  {hrow:>12.0f}  "
                  f"{'ok' if ok else 'HORIZON OFF-FRAME: cannot show both'}")

    print("\n  A narrow field aimed high cannot also contain the ground.")
    print("  If both are required, split the shot into two focal segments.")
    return 1 if bad else 0


# ---------------------------------------------------------------- stream ----

def cmd_stream(a):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", a.path],
        capture_output=True, text=True)
    if probe.returncode != 0:
        print("FAIL  ffprobe error:", probe.stderr.strip()[:300])
        return 1
    info = json.loads(probe.stdout)
    problems = []

    dur = float(info.get("format", {}).get("duration", 0))
    print(f"{a.path}\n  duration {dur:.3f}s")
    has_audio = False
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            fps = s.get("r_frame_rate", "0/1")
            n, d = (fps.split("/") + ["1"])[:2]
            fps_v = float(n) / float(d or 1)
            print(f"  video    {s.get('codec_name')} {s.get('width')}x{s.get('height')} @ {fps_v:g}fps")
            if a.expect_fps and abs(fps_v - a.expect_fps) > 0.01:
                problems.append(f"fps {fps_v:g} != expected {a.expect_fps}")
            if s.get("codec_name") == "hevc":
                print("  note     HEVC does not decode in some Chrome builds; "
                      "ship H.264 if the audience is unknown")
        elif s.get("codec_type") == "audio":
            has_audio = True
            print(f"  audio    {s.get('codec_name')}")
    if a.expect_duration and abs(dur - a.expect_duration) > a.duration_tol:
        problems.append(f"duration {dur:.3f}s != expected {a.expect_duration}s "
                        f"(tol {a.duration_tol})")
    if a.require_audio and not has_audio:
        problems.append("no audio stream: the mux dropped the cue")

    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", a.path, "-f", "null", "-"],
                         capture_output=True, text=True)
    if dec.returncode != 0 or dec.stderr.strip():
        problems.append("decode errors: " + dec.stderr.strip()[:200])
    else:
        print("  decode   clean (zero errors)")

    print()
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    stream is intact -- which proves data integrity, not that the shot works")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("frames", help="check a rendered PNG sequence")
    f.add_argument("directory")
    f.add_argument("--expect", type=int, help="expected frame count")
    f.add_argument("--since", type=float,
                   help="unix time this render started; older frames are stale")
    f.add_argument("--max-span-s", type=float, default=3600.0)
    f.add_argument("--corner", type=int, default=150, help="corner sample size px")
    f.add_argument("--max-corner", type=float, default=20.0)
    f.add_argument("--min-spread", type=float, default=25.0)
    f.add_argument("--step-thresh", type=float, default=0.55)
    f.add_argument("--seam", action="store_true",
                   help="split-screen frame: check the midline for a seam")
    f.add_argument("--seam-tol", type=float, default=6.0)
    f.add_argument("--ignore-region", type=_region, action="append", metavar="x0,y0,x1,y1",
                   help="pixel box excluded from the row/column step check "
                        "(repeatable); use for a straight bright element in the design")
    f.set_defaults(func=cmd_frames)

    c = sub.add_parser("sheet", help="labelled contact sheet at given timestamps")
    c.add_argument("directory")
    c.add_argument("--times", required=True, help="comma-separated seconds, e.g. 0.5,2,4")
    c.add_argument("--fps", type=float, required=True)
    c.add_argument("--out", required=True, help="output PNG path")
    c.add_argument("--cols", type=int, help="tiles per row (default: up to 6)")
    c.add_argument("--width", type=int, default=270, help="tile width px (default 270)")
    c.set_defaults(func=cmd_sheet)

    p = sub.add_parser("plan", help="angular-size / framing feasibility table")
    p.add_argument("--angular-size", type=float, required=True, help="subject size in degrees")
    p.add_argument("--height", type=int, default=1920, help="frame height px")
    p.add_argument("--fov", required=True, help="comma-separated vertical FOVs in degrees")
    p.add_argument("--min-px", type=float, default=40.0)
    p.add_argument("--subject-alt", type=float,
                   help="subject elevation in degrees, to test horizon visibility")
    p.set_defaults(func=cmd_plan)

    s = sub.add_parser("stream", help="ffprobe + full decode of a finished file")
    s.add_argument("path")
    s.add_argument("--expect-duration", type=float)
    s.add_argument("--duration-tol", type=float, default=0.1)
    s.add_argument("--expect-fps", type=float)
    s.add_argument("--require-audio", action="store_true")
    s.set_defaults(func=cmd_stream)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
