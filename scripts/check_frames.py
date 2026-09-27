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
  assemble frames (+ optional audio) -> H.264 mp4, then the stream check

Examples
--------
  python check_frames.py frames frames_v4 --expect 240 --since 1727300000
  python check_frames.py frames frames_v4 --ignore-region 180,760,830,790
  python check_frames.py sheet frames_v4 --fps 24 --times 0.5,2,4,6,9.5 --out sheet.png
  python check_frames.py plan --angular-size 0.52 --height 1920 --fov 100,20,3.1
  python check_frames.py stream out.mp4 --expect-duration 10 --expect-fps 24
  python check_frames.py assemble frames_v4 --fps 24 --audio cue.wav --out out.mp4
  python check_frames.py assemble frames_v4 --fps 24 --scale 360x640 --out small.mp4
  python check_frames.py assemble frames_v4 --fps 30 --audio mix.wav --srt subs.srt --srt-lang chi --out out.mp4
"""
import argparse
import json
import os
import re
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
    has_audio = has_subs = False
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            fps = s.get("r_frame_rate", "0/1")
            n, d = (fps.split("/") + ["1"])[:2]
            fps_v = float(n) / float(d or 1)
            print(f"  video    {s.get('codec_name')} {s.get('width')}x{s.get('height')} @ {fps_v:g}fps")
            if a.expect_size and (s.get("width"), s.get("height")) != a.expect_size:
                problems.append(f"size {s.get('width')}x{s.get('height')} != expected "
                                f"{a.expect_size[0]}x{a.expect_size[1]}")
            if a.expect_fps and abs(fps_v - a.expect_fps) > 0.01:
                problems.append(f"fps {fps_v:g} != expected {a.expect_fps}")
            if s.get("codec_name") == "hevc":
                print("  note     HEVC does not decode in some Chrome builds; "
                      "ship H.264 if the audience is unknown")
        elif s.get("codec_type") == "audio":
            has_audio = True
            print(f"  audio    {s.get('codec_name')}")
        elif s.get("codec_type") == "subtitle":
            has_subs = True
            print(f"  subtitle {s.get('codec_name')}")
    if a.expect_duration and abs(dur - a.expect_duration) > a.duration_tol:
        problems.append(f"duration {dur:.3f}s != expected {a.expect_duration}s "
                        f"(tol {a.duration_tol})")
    if a.require_audio and not has_audio:
        problems.append("no audio stream: the mux dropped the cue")
    if getattr(a, "require_subtitles", False) and not has_subs:
        problems.append("no subtitle stream: the mux dropped the SRT")

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


# -------------------------------------------------------------- assemble ----

_SEQ = re.compile(r"^(.*?)(\d+)\.png$")


def _size(text):
    try:
        w, h = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected WxH, got {text!r}")
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError(f"expected a positive WxH, got {text!r}")
    return w, h


def frame_sequence(d):
    """Describe a numbered PNG sequence: (ffmpeg pattern, first index, count).

    Fails loudly on anything ffmpeg would silently get wrong: mixed prefixes or
    digit widths, and gaps in the numbering (a preview subset, a crashed
    worker) -- ffmpeg's image2 demuxer stops at the first gap, which would cut
    the film short and shift every later beat.
    """
    files = sorted(Path(d).glob("*.png"))
    if not files:
        raise ValueError(f"no PNG frames in {d}")
    parsed = []
    for f in files:
        m = _SEQ.match(f.name)
        if not m:
            raise ValueError(f"{f.name} is not a numbered frame (expected e.g. f0000.png)")
        parsed.append((m.group(1), len(m.group(2)), int(m.group(2))))
    kinds = {(p, w) for p, w, _ in parsed}
    if len(kinds) != 1:
        raise ValueError(f"mixed frame names in {d}: {sorted(kinds)[:4]}")
    prefix, width = kinds.pop()
    nums = sorted(n for _, _, n in parsed)
    missing = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
    if missing:
        shown = ", ".join(map(str, missing[:8])) + (" ..." if len(missing) > 8 else "")
        raise ValueError(f"{len(missing)} frame(s) missing from the sequence "
                         f"{nums[0]}..{nums[-1]}: {shown}")
    return str(Path(d) / f"{prefix}%0{width}d.png"), nums[0], len(nums)


_SRT_TIME = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$")


def parse_srt(path, duration=None, tol=0.5):
    """Validate an SRT file strictly; return [(start, end, text)] or raise ValueError.

    Catches what players silently mangle: a millisecond field rounded up to four
    digits (",1000"), cues out of order, a cue that ends before it starts, and cues
    running past the end of the picture."""
    blocks = [b for b in Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").split("\n\n")
              if b.strip()]
    cues, last = [], -1.0
    for k, b in enumerate(blocks, 1):
        lines = b.strip("\n").split("\n")
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError(f"cue {k}: expected an index line, a time line and text")
        m = _SRT_TIME.match(lines[1].strip())
        if not m:
            raise ValueError(f"cue {k}: bad time line {lines[1].strip()!r} "
                             f"(HH:MM:SS,mmm --> HH:MM:SS,mmm, milliseconds 000-999)")
        g = [int(v) for v in m.groups()]
        if g[1] > 59 or g[2] > 59 or g[5] > 59 or g[6] > 59:
            raise ValueError(f"cue {k}: minutes/seconds above 59 in {lines[1].strip()!r}")
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        if e <= a:
            raise ValueError(f"cue {k}: ends at {e:.3f}s, not after its start {a:.3f}s")
        if a < last:
            raise ValueError(f"cue {k}: starts at {a:.3f}s, before the previous cue")
        if duration is not None and e > duration + tol:
            raise ValueError(f"cue {k}: ends at {e:.3f}s, past the picture ({duration:.3f}s)")
        last = a
        cues.append((a, e, "\n".join(lines[2:])))
    if not cues:
        raise ValueError("no cues")
    return cues


def cmd_assemble(a):
    try:
        pattern, first, n = frame_sequence(a.directory)
    except ValueError as e:
        print(f"FAIL  {e}")
        return 1
    if a.audio and not Path(a.audio).exists():
        print(f"FAIL  audio file not found: {a.audio}")
        return 1
    if a.srt and not Path(a.srt).exists():
        print(f"FAIL  subtitle file not found: {a.srt}")
        return 1
    with Image.open(pattern % first) as im:
        fw, fh = im.size
    ow, oh = a.scale or (fw, fh)
    if ow % 2 or oh % 2:
        print(f"FAIL  output size {ow}x{oh} is odd; yuv420p needs even dimensions "
              f"(pass --scale with even numbers)")
        return 1
    duration = n / a.fps
    print(f"{n} frames {fw}x{fh} from {pattern} (first {first}) at {a.fps:g}fps "
          f"= {duration:.3f}s -> {a.out} ({ow}x{oh})")
    if a.srt:
        try:
            cues = parse_srt(a.srt, duration)
        except ValueError as e:
            print(f"FAIL  {a.srt}: {e}")
            return 1
        print(f"{len(cues)} subtitle cues from {a.srt} -> soft track ({a.srt_lang})")

    # Subtitles are muxed in a second, stream-copy pass: with -shortest in the
    # same command, a subtitle track whose last cue ends before the picture cuts
    # the whole film at that cue (a 297 s film came out 293.8 s).
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    av_out = str(Path(a.out).with_suffix(".av.tmp.mp4")) if a.srt else a.out
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-framerate", f"{a.fps:g}", "-start_number", str(first), "-i", pattern]
    if a.audio:
        cmd += ["-i", a.audio]
    if a.scale:
        cmd += ["-vf", f"scale={ow}:{oh}:flags=lanczos"]
    cmd += ["-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
            "-pix_fmt", "yuv420p", "-r", f"{a.fps:g}"]
    if a.audio:
        # -shortest ends the file with the picture if the cue runs long; a cue that
        # is too SHORT then shows up as a duration mismatch in the stream check
        cmd += ["-c:a", "aac", "-b:a", a.audio_bitrate, "-shortest"]
    cmd += ["-movflags", "+faststart", av_out]
    enc = subprocess.run(cmd, capture_output=True, text=True)
    if enc.returncode != 0:
        print("FAIL  ffmpeg:", enc.stderr.strip()[-600:])
        return 1
    if a.srt:
        mux = ["ffmpeg", "-v", "error", "-y", "-i", av_out, "-i", a.srt,
               "-map", "0:v:0"] + (["-map", "0:a:0"] if a.audio else []) + \
              ["-map", "1:s:0", "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
               "-metadata:s:s:0", f"language={a.srt_lang}", "-movflags", "+faststart", a.out]
        enc = subprocess.run(mux, capture_output=True, text=True)
        Path(av_out).unlink(missing_ok=True)
        if enc.returncode != 0:
            print("FAIL  ffmpeg (subtitle mux):", enc.stderr.strip()[-600:])
            return 1

    print()
    check = argparse.Namespace(path=a.out, expect_duration=duration,
                               duration_tol=a.duration_tol, expect_fps=a.fps,
                               require_audio=bool(a.audio), expect_size=(ow, oh),
                               require_subtitles=bool(a.srt))
    return cmd_stream(check)


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
    s.add_argument("--expect-size", type=_size, metavar="WxH")
    s.set_defaults(func=cmd_stream)

    m = sub.add_parser("assemble", help="frames (+ audio) -> H.264 mp4, then verify it")
    m.add_argument("directory", help="directory of numbered PNG frames (f0000.png ...)")
    m.add_argument("--fps", type=float, required=True, help="frame rate (explicit, always)")
    m.add_argument("--out", required=True, help="output .mp4 path")
    m.add_argument("--audio", help="audio file to mux (e.g. the cue .wav)")
    m.add_argument("--crf", type=int, default=18, help="x264 quality (default 18)")
    m.add_argument("--preset", default="medium", help="x264 preset (default medium)")
    m.add_argument("--scale", type=_size, metavar="WxH",
                   help="resize on encode, e.g. 360x640 for a small preview")
    m.add_argument("--audio-bitrate", default="192k")
    m.add_argument("--srt", help="SRT to validate and mux as a soft subtitle track (mov_text); "
                                 "burned-in subtitles belong in the frames themselves")
    m.add_argument("--srt-lang", default="und", help="ISO 639-2 language of the SRT, e.g. chi, eng")
    m.add_argument("--duration-tol", type=float, default=0.1)
    m.set_defaults(func=cmd_assemble)

    a = ap.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
