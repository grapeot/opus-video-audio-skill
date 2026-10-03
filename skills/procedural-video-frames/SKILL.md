---
name: procedural-video-frames
description: >
  Render short videos as numbered PNG frames from a Python script, then mux them
  with ffmpeg -- the frame-sequence pipeline, not a DAW and not a text-to-video
  model. This entry file holds the rules for every render (framing math in
  angles and the shots that are geometrically impossible, additive linear
  compositing with one tone map, exposure that must fall as the field of view
  widens, verification against stale frames and unlooked-at shots, contact
  sheets, previewing on a phone, ffmpeg assembly) and routes to sub-documents
  for look development with an independent critic, fine detail across a large
  zoom (SDFs, level of detail, anti-aliasing, growth), reflections on water,
  glows/highlights/seams/on-screen text, handing a material layer such as
  cloth to Blender through a coding agent, narrated explainers (timing the
  picture to a voice-over, checking TTS takes by transcription, subtitles,
  illustration plates printed onto the page), explainers that must not read as
  slides (sets on one sheet with a sliding camera, persistent elements,
  element-wise arrivals keyed to words, diagrams drawn in the plates' register),
  and films cut to an existing song
  (measuring and snapping beats and sung lines, drum-driven glow, one-canvas
  reveals, a vector-display look, nested zooms and video feedback, lyrics placed
  where the picture is empty). Use this skill whenever a task
  involves rendering or animating a short video, reel, short, greeting,
  explainer, music video or title sequence programmatically; whenever frames are produced by
  code (numpy, PIL, matplotlib, Blender scripting) and assembled into an mp4;
  whenever a camera has to push in, pan or reframe over time; whenever
  compositing a subject over a background with glow, halo, haze or a
  reflection; or whenever a render looks washed out, too dark, flat, cheap,
  aliased, or has visible seams and edges, or reads as a slideshow. Reach for it even when the animation
  sounds trivial ("just zoom into this image over 10 seconds"), because the
  failure modes here -- inverted exposure laws, off-frame geometry, stale-frame
  review -- are silent and cost whole render passes.
---

# Procedural Video: Frames from Code

> Validated on macOS, September 2026, across several short vertical films
> (10-15s, 24-30fps), a two-minute and a five-minute horizontal narrated explainer
> (1080p30) and one full-length music video (about 3.5 minutes, 1080p24), rendered end to end
> with this pipeline, each taken through multiple full render passes and human
> review. Anything marked **untested** was not exercised on those films.
> For the audio half -- composing a cue, hitting timecodes, loudness, and the
> fact that you cannot hear -- see the sibling skill `video-scoring-audio`.

## Why frames, and not a video model

A frame-sequence pipeline is worth its cost when the shot must be *exact*: a
beat that lands on a specific frame, a subject at a physically correct size, a
camera move that resolves at 6.0s because the music swells there. Generative
video models do not honor that kind of instruction -- the same failure the audio
skill documents for generative music. If the brief has no hard timing or
geometry, a video model is cheaper and you should say so.

The pipeline is small: a Python script writes `f0000.png ... f0239.png`, and
ffmpeg turns them into an mp4. Everything hard lives in the script.

**Reuse before you rebuild.** If the project already has a renderer for this
domain, read its docs and CLI before writing your own; the mode you are about
to reimplement may already be a flag. Check that a cached dataset actually
covers what the shot needs: a cache built for one framing can silently return
an empty or clipped result for a different one, which reads as a rendering bug
and is not.

## Reusable code

The plumbing every film rewrites is in the repository's `lib/opusvid/` (put
`lib/` on `sys.path`; numpy, scipy, Pillow): `runner` (the CLI and worker pool
around one `render_frame(i)`, fresh output directory per run, run start for
`--since`), `timeline` (easing, named `Events`, a PCHIP camera path with
log-space width, `solve_time`, a per-frame camera JSON for Blender) and
`typeset` (glyph masks blended by hand, letter-spaced lines, vertical columns,
timed reveals) and `narration` (voice takes placed on one clock, the film time
of a spoken phrase, subtitle cues, SRT), `placement` (text positioned where
measured ink is lowest, clearing bands), `strokefont` (single-stroke vector
text revealed word by word) and `motion` (a pen tracing a curve by arc length,
plates that ink in, true cross-fades of multiply plates, particles on their own
clocks, rolling counters, a camera sliding between sets on one sheet, sprites cut
out of one generated plate). `music_timing.py` measures a song: stems, snapped
beats, a per-frame drum envelope, vocal onsets, sung lines. `check_frames.py assemble` muxes and
verifies, with `--srt` for a validated soft subtitle track;
`narration_check.py` transcribes voice takes back against the script. Start from
`examples/minimal_film/`, which runs the whole loop in three seconds. Keep the
film's subject, shading and layout in the film's own script.

## Where to read next

This file holds the rules that apply to every render. Read a sub-document when
its trigger applies; they live next to this file.

| Read | When |
|------|------|
| `lookdev.md` | Before writing any renderer: settling the concept, references and a rubric, look-dev stills, the independent critic loop, illustration plates for explainers (a generated set printed onto the page), sources and consistent numbers on data frames, composing symbols rather than displaying them, density judged at on-screen size, perceptibility of physical effects. Also when a clean render is called cheap, kitsch, monotonous, unclear, or "all text". |
| `narration.md` | Any voice-over: order of work (script, takes, picture), keying visual beats to spoken phrases, checking takes by transcription, subtitles (burned-in, soft track, SRT), rewriting a script without breaking the sync. |
| `motion.md` | Any explainer longer than a minute, or a render called "a slideshow" or static: one sheet with a camera and sets instead of cuts, elements that persist and change in place, the vocabulary of element-wise arrivals keyed to words, drawing diagrams in the plates' register (hatching, sprites cut from plates), multiply cross-fade and other traps, the title card. |
| `music_video.md` | Picture cut to an existing song: measuring and snapping beats and sung lines, one event per sung line, drum-driven glow and pen, what reads as remarkable (one-canvas reveals, continuity, perceptible cleverness only), a vector-display look (persistence with the current camera), nested zooms and video feedback, a per-stroke warp hook, lyrics written with the pen and placed where the picture is empty. |
| `critic_prompt.md` | Every revision round, before the human sees frames: the prompt for the independent art-director sub-agent. |
| `detail.md` | Crafted detail (wire, filigree, ornament) at very different screen sizes; zooms across orders of magnitude; SDF per-pixel rendering; level of detail; anti-aliasing a height field; motif layout; growth and cross-fades between representations. |
| `reflections.md` | Water or glossy reflections of a light source; any size carried from one space to another (angular extent, pixel footprint, blur radius). |
| `sprites_text.md` | Glows, particles, bloom, highlights that read as the wrong thing, rectangles/rays/seams, split-screen panels, and any on-screen text (mixed-script runs, counters, CJK punctuation). |
| `blender_handoff.md` | Cloth or another material a height field cannot sell; elements that must ride a moving surface; showing a surface's height under an orthographic camera; dispatching a coding agent to drive Blender. |

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
telephoto photographs of a high subject have no landscape in them. If a brief
asks for both a filled subject and the foreground, the honest answers are to
split the shot into two focal segments, keep the subject low (near the horizon
a telephoto can hold both), or change the brief -- not to fake it.
`check_frames.py plan` prints this table.

When a shot does need two focal lengths, interpolate in **log focal space**, or
the push visibly races at the tight end:

```python
fov = exp(log(fov_wide) + (log(fov_tele) - log(fov_wide)) * ease(k))
```

Before rendering, print a small table of time, fov, subject pixel size, and the
frame row of anything that must stay visible. Off-frame values (negative rows,
rows past the frame height) are the geometry telling you the shot does not work.

**The projection decides which motions are visible.** An orthographic camera
looking straight down cannot show height: a surface waving up and down moves
nothing on screen. If the story depends on a motion, confirm the projection
turns it into screen displacement before rendering (`blender_handoff.md` has
the parallel-oblique fix).

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
parameter twiddling fixes. Layers rendered elsewhere (a Blender plate, a
photograph) are linearised (inverse sRGB) before they join the canvas.

**Check your background floor in isolation.** A "faint" ambient level is easy to
set an order of magnitude too high: a floor of `0.012` tone-mapped to luminance
27/255 -- a grey sky, not a night one. Run the floor through the tone map alone
and look at the number before blaming anything else.

**Coloured emitters lose their hue when pushed bright.** A saturated warm light
driven high enough to "glow" comes out pale yellow-white after a Reinhard-style
curve, because every channel saturates. Keep coloured emitters in the range where
the curve still preserves hue, and let a soft halo carry the sense of brightness.

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
any subject should be near-black (luminance ~10) unless the sky is lit by
design, and the subject should show real spread (e.g. p10≈22, p90≈125). If the
corner is bright and you did not intend it, something is leaking light into the
whole frame.

## Verification: the part that actually costs render passes

An agent reviewing its own render is prone to two specific mistakes, and each
costs a full pass.

**Confirm the frames you are looking at are from this run.** Waiting on a *file
count* is a race: the previous pass's frames are still on disk, so the wait
returns instantly and you review stale images -- concluding your fix "didn't
work" when it was never tested. Wait for the **process** to exit, or render into
a fresh per-run directory:

```bash
python render_film.py --out frames_r2 & PID=$!
while kill -0 "$PID" 2>/dev/null; do sleep 15; done     # wait on the PID you started
```

**Do not wait on a name with `pgrep -f`.** It matches every process whose command
line contains the name, and agent harnesses leave long-lived shells around whose
command lines mention the script: the shell that launched a render with `&`, and
other waiters. On macOS `pgrep` excludes its own ancestors, so a waiter does not
match itself, but two waiters watching each other's script names, or one waiter
and a lingering launcher shell, never see "no match": two queued Blender passes
sat idle for about seven hours that way, and a probe confirmed that a waiter loops
for as long as a sibling shell mentioning the name is alive. To run passes in
order, put them in one backgrounded command (`a && b && c`) instead of separate
waiters, and pair any long pass with a heartbeat check about every 30 minutes
that compares frame counts, so a stalled or never-started pass is caught early.

When a frame contradicts the code, check its modification time before changing
anything.

**Assert every scripted patch.** A search-and-replace edit that matches nothing
changes nothing and still "succeeds"; check the match count before spending a
render pass on it.

**Keep the preview path and the production path the same code.** A preview
script that reimplements the render loop will drift from it, and then you have
validated a program you are not shipping. Import the real functions; if that is
awkward, that awkwardness is a signal the render loop should be factored so both
can call it.

**Look at the images.** Many defects are invisible in every number: two
subjects reading as a pair instead of one, a subject bisected by a divider line,
an outline that never faded, a ray or box artifact, a reflection narrower than
its source, a highlight that reads as a flame. Numbers catch exposure and
geometry; only looking catches composition. Check at least the opening, each
transition beat, and the final frame, and crop to full resolution around
anything small. A labelled contact sheet at the beat timestamps makes this one
image:

```bash
python scripts/check_frames.py sheet frames/ --fps 30 \
  --times 0.5,2,4,6,8,10,12,14.5 --out sheet.png
```

**Get an independent critic every round.** Every revision round goes to a
critic sub-agent (`critic_prompt.md`) before the human sees it; see `lookdev.md`.

**Watch it where it will be watched.** Detail density, text size and motion
speed are judged at delivery size. For a phone audience, play the actual file on
a phone: `scripts/serve_video.py out.mp4` serves only the listed files on the
local network with the HTTP Range support iOS Safari needs, and prints the URL.
It binds to all interfaces, so anyone on the same network can fetch the file
while it runs; stop it (Ctrl-C) as soon as the review is done. If the machine is on
a private overlay network such as Tailscale, bind to that address instead
(`--host <tailscale IPv4>`): only the reviewer's own devices can reach it, from
anywhere. If the default port is taken by something else, pass `--port` with a
free one (check with `lsof -iTCP:<port> -sTCP:LISTEN`; never stop a server you did
not start).

**Treat the checker's thresholds as defaults, not verdicts.** Generic checks
(corner brightness, tonal spread, a midline seam, a sharp row or column step)
fire on intentional choices -- a lit sky, a paper-coloured page (every
explainer on a light background fails the corner check), a night scene that is
mostly dark, a centred subject, a long straight bright edge or wire in the design. When that
happens, confirm by looking, then relax the check deliberately and say so
(`--max-corner`, or `--ignore-region x0,y0,x1,y1` around the straight element),
rather than tuning the image to satisfy the check. Keep each ignored box tight
around the element: the box's own border does not create a step, but nothing
inside it is checked any more.

## Fast moves over regular patterns: blur along the motion

A page or camera move of a frame height in under a second moves regular detail
(ruled lines, grids, text) tens of pixels per frame, more than its own spacing.
Blur each frame along the motion by about half its per-frame displacement (a
180-degree shutter); for a pure vertical move a box filter along the rows is
enough. This was used on every page turn of one film and the mid-turn frames were
checked; the unblurred version was not rendered, so the strobing it prevents is
expected from sampling, not observed here (**untested** as a failure).

```python
v = (scroll(t + 0.5 / fps) - scroll(t - 0.5 / fps)) * H * 0.5     # px this frame
if v > 1.5:
    img = uniform_filter1d(img, size=int(round(v)) | 1, axis=0, mode="nearest")
```

Composite anything that should stay sharp through the move (subtitles, a fixed
frame) after the blur.

## Assembly: one timeline, mux, verify the stream

**Share one timeline between picture and music.** Put every beat time in one
small module that both the renderer and the cue generator import. Compute
derived event times (when a moving subject first crosses an edge, when a counter
ticks) by evaluating or solving the same motion function the renderer uses,
never by reading them off a preview. Then a change to the motion moves the
music with it, and each visual event lands on the first frame after its note's
onset without hand-tuning.

Mux with an explicit frame rate, and verify rather than assuming. Prefer
`check_frames.py assemble` (below); by hand, the equivalent is:

```bash
ffmpeg -y -framerate 24 -i frames/f%04d.png -i cue.mp3 \
  -c:v libx264 -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart out.mp4

ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate \
        -show_entries format=duration -of default=nw=1 out.mp4
ffmpeg -v error -i out.mp4 -f null -          # zero output = clean decode
```

`-pix_fmt yuv420p` is what makes the file play outside your own machine. H.264
is the default because **HEVC (libx265, `-tag:v hvc1`) does not decode in some
Chrome builds**; Safari and most players are fine with HEVC, so offer it only
alongside H.264 or when the audience is known. Never add a soft subtitle track in
the same command as `-shortest`: a track whose last cue ends early cuts the film
there (`assemble` muxes subtitles in a second, stream-copy pass). A clean decode proves data integrity, not that the shot is any good.
`check_frames.py stream` runs both checks; `check_frames.py assemble` does
the H.264 mux (refusing a sequence with missing frames) and then runs them.

## Checklist before declaring a render done

- Concept chosen by the human before building (or, if the human delegated the
  choice, chosen by you and stated with its main risk); the message is said on screen
- References and a rubric gathered; look-dev stills approved before animating
- An independent critic reviewed the keyframes against the rubric on *this* round
- Angular-size table printed, and nothing that must be visible is off-frame
- Every motion the story depends on is visible under the chosen projection
- Every physically true effect checked at the film's time scale
- Frame corner dark unless lit by design; subject shows real tonal spread
- No rectangular glow edges on any sprite; no directional weight reaches zero
- Every bright region reads as light on its material, not as another object
- No motif sliced by a boundary; fine detail has a level of detail below ~5 px
- Detail density judged at delivery size; small objects have clean forms
- Reflections at least as wide as their sources; no seam at panel boundaries
- Frames confirmed to be from this run (process exited, or fresh directory)
- Opening, each transition beat, and the final frame looked at as images
  (a contact sheet at the beat times), and the file watched on the target device
- Voice-over: every visual beat keyed to a spoken phrase, every take transcribed
  back and its differences judged, every line subtitled (`narration.md`)
- Explainer: no beat-time keyframe reads as a static slide; related scenes share one
  canvas; drawn diagrams and plates judged together as one register (`motion.md`)
- Music: sections named from where the voice is, beats and sung lines snapped to
  onsets, one event per sung line, on-screen text placed by measurement
  (`music_video.md`)
- Every frame with a number carries its source; illustrative charts say so
- `ffprobe` dimensions/fps/duration match intent; `ffmpeg -f null -` is silent
- Delivery codec matches the audience
