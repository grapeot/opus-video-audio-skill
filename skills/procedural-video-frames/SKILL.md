---
name: procedural-video-frames
description: >
  Render short videos as numbered PNG frames from a Python script, then mux them
  with ffmpeg -- the frame-sequence pipeline, not a DAW and not a text-to-video
  model. Covers camera and framing math (why a subject's real angular size
  dictates the focal length, and why some shots are geometrically impossible),
  additive linear compositing with tone mapping, exposure that has to change as
  the field of view changes, and the verification discipline that keeps you from
  reviewing stale frames or shipping a shot you never actually looked at. Use
  this skill whenever a task involves rendering or animating a short video,
  reel, short, explainer or title sequence programmatically; whenever frames are
  produced by code (numpy, PIL, matplotlib, Blender scripting) and assembled
  into an mp4; whenever a camera has to push in, pan or reframe over time;
  whenever compositing a subject over a background with glow, halo or haze; or
  whenever a render looks washed out, too dark, or has visible seams and edges.
  Reach for it even when the animation sounds trivial ("just zoom into this
  image over 10 seconds"), because the failure modes here -- inverted exposure
  laws, off-frame geometry, stale-frame review -- are silent and cost whole
  render passes.
---

# Procedural Video: Frames from Code

> Validated: the video half of a short-video pipeline, on macOS, September 2026,
> across roughly a dozen full 240-frame render passes of a 10s vertical film.
> For the audio half -- composing a cue, hitting timecodes, loudness, and the
> fact that you cannot hear -- see the sibling skill `video-scoring-audio`.

## Why frames, and not a video model

A frame-sequence pipeline is worth its cost when the shot must be *exact*: a
beat that lands on a specific frame, a subject at a physically correct size, a
camera move that resolves at 6.0s because the music swells there. Generative
video models do not honor that kind of instruction -- the same failure the audio
skill documents for generative music. If the brief has no hard timing or
geometry, a video model is cheaper and you should say so.

The pipeline is small: a Python script writes `f0000.png … f0239.png`, and
ffmpeg turns them into an mp4. Everything hard lives in the script.

## Reason about framing in angles before you write the render loop

This is the single highest-leverage habit, because it catches impossible shots
before you spend a render pass on them.

Work out the subject's real angular size, then what vertical field of view puts
it at the pixel size you want:

```
px_on_screen = angular_size_deg / fov_v_deg * frame_height_px
```

A worked case: the Moon is 0.52° across. In a 52° field on a 1920px-tall frame
that is **11 pixels** -- invisible, no matter how good the texture. Filling the
frame with it (~320px) needs a ~3.1° field, a strong telephoto.

The consequence is a real constraint, not a preference: **a narrow field aimed
high cannot also contain the ground.** With the camera pointed 50° up in a 3.1°
field, the horizon lands thousands of pixels below the frame. That is why real
telephoto moon photographs have no landscape in them. If a brief asks for both a
filled subject and the foreground, the honest answers are to split the shot into
two focal segments, or to change the brief -- not to fake it.

When a shot does need two focal lengths, interpolate in **log focal space**, or
the push visibly races at the tight end:

```python
fov = exp(log(fov_wide) + (log(fov_tele) - log(fov_wide)) * ease(k))
```

Before rendering, print a small table of time, fov, subject pixel size, and the
frame row of anything that must stay visible. Off-frame values (negative rows,
rows past the frame height) are the geometry telling you the shot does not work.

## Composite in linear light, tone map once at the end

Accumulate everything additively into a float canvas, then map to display range
in one place:

```python
canvas = np.zeros((H, W, 3), np.float64)
canvas += sky_floor
add_background_elements(canvas)
add_subject(canvas)
img = np.clip(np.power(canvas / (1 + canvas), 1/1.85), 0, 1)   # Reinhard + gamma
```

Additive accumulation is what makes overlapping glows behave; tone mapping once
is what keeps bright areas from clipping to flat white. If you tone map inside a
helper and then add more light, you get the washed-out look that no amount of
parameter twiddling fixes.

**Check your background floor in isolation.** A "faint" ambient level is easy to
set an order of magnitude too high: a floor of `0.012` tone-mapped to luminance
27/255 -- a grey sky, not a night one. Run the floor through the tone map alone
and look at the number before blaming anything else.

## Exposure has to follow the field of view, and the sign is counterintuitive

When the camera pushes from wide to tight, the per-element gain must **fall as
the field widens**, because a wide frame packs far more elements into the same
pixels. Getting the sign backwards blows the wide shot into grey noise:

```python
exposure = (fov_v / fov_tele) ** -1.35    # ~0.014 at 100 deg, 1.0 at 3.1 deg
```

The same inversion applies to glow. A halo tuned on a small subject will flood
the whole frame once that subject fills it, so scale it down as the subject grows:

```python
small = np.clip(150.0 / diameter_px, 0.12, 6.0)   # prominent when tiny, nearly gone when large
```

Diagnose these by sampling regions, not by squinting: a frame corner far from
any subject should be near-black (luminance ~10), and the subject should show
real spread (e.g. p10≈22, p90≈125). If the corner is bright, something is
leaking light into the whole frame.

## Draw glows over their own generous box, and force them to zero

The classic artifact is a **visible rectangle** around a subject: a radial
falloff computed over the subject's bounding box never reaches zero at the box
edge, so the box shows. Compute the glow over a box several times larger, and
multiply by a term that hits exactly zero inside it:

```python
glow *= np.clip(1.0 - rr / 5.5, 0, 1) ** 2   # hard zero before the box edge
```

Verify by sampling a row through the subject: values should fall off smoothly
with no step.

## Seams: draw shared geometry once, across the whole frame

When a frame is assembled from panels (split screen, per-source layers), drawing
the same background element separately per panel produces a seam — the two
copies disagree at the boundary, and padding that overshoots the midline makes
it worse. Draw anything that spans the frame **once**, over the full width, and
place per-panel items on top of it afterwards.

Verify numerically: the mean of the seam columns should equal the mean of
columns well away from it. If it does not, the seam is real and a viewer will
see it.

Two related traps, both of which look like a rendering bug but are not:

- `PIL.ImageDraw.line` on an **RGB** image silently ignores an alpha value in
  `fill`. A line you believe is fading stays fully opaque for the whole shot.
  Fade by blending the colour toward the background instead.
- An element composited inside a half-width panel gets **cropped at the panel
  edge**. If two panels converge onto one shared subject, composite that subject
  on the whole frame once they have merged, not inside either panel.

## Verification: the part that actually costs render passes

An agent reviewing its own render is prone to two specific mistakes, and both
burned full passes here.

**Confirm the frames you are looking at are from this run.** Waiting on a *file
count* is a race: the previous pass's frames are still on disk, so the wait
returns instantly and you review stale images — concluding your fix "didn't
work" when it was never tested. Wait for the **process** to exit, or render into
a fresh per-run directory:

```bash
until ! pgrep -f render_film.py >/dev/null; do sleep 15; done
```

When a frame contradicts the code, check its modification time before changing
anything.

**Keep the preview path and the production path the same code.** A preview
script that reimplements the render loop will drift from it, and then you have
validated a program you are not shipping. Import the real functions; if that is
awkward, that awkwardness is a signal the render loop should be factored so both
can call it.

**Look at the images.** Several defects here were invisible in every number:
two subjects reading as a pair instead of one, a subject bisected by a divider
line, an outline that never faded. Coordinates converged correctly the whole
time. Numbers catch exposure and geometry; only looking catches composition.
Check at least the opening, each transition beat, and the final frame.

## Assembly and stream verification

Mux with an explicit frame rate, and verify rather than assuming:

```bash
ffmpeg -y -framerate 24 -i frames/f%04d.png -i cue.mp3 \
  -c:v libx265 -tag:v hvc1 -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart out.mp4

ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate \
        -show_entries format=duration -of default=nw=1 out.mp4
ffmpeg -v error -i out.mp4 -f null -          # zero output = clean decode
```

`-pix_fmt yuv420p` is what makes the file play outside your own machine. Note
that **HEVC (libx265) does not decode in some Chrome builds** — Safari and most
players are fine, but if the audience is unknown, ship H.264 or offer it
alongside. A clean decode proves data integrity, not that the shot is any good.

## Reuse before you rebuild

If the project already has a renderer for this domain, read its docs and CLI
before writing your own. In this project the existing tool already supported the
aimed-camera mode being reimplemented from scratch — the flags were there, just
unread. Equally, check that a cached dataset actually covers what the shot
needs: a cache built for one framing silently returned an empty or clipped
result for a different one, which reads as a rendering bug and is not.

## Checklist before declaring a render done

- Angular-size table printed, and nothing that must be visible is off-frame
- Frame corner near-black; subject shows real tonal spread
- No rectangular halo edges; no seam at panel boundaries
- Frames confirmed to be from this run (process exited, or fresh directory)
- Opening, each transition beat, and the final frame looked at as images
- `ffprobe` dimensions/fps/duration match intent; `ffmpeg -f null -` is silent
- Delivery codec matches the audience
