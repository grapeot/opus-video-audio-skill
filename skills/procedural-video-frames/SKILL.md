---
name: procedural-video-frames
description: >
  Render short videos as numbered PNG frames from a Python script, then mux them
  with ffmpeg -- the frame-sequence pipeline, not a DAW and not a text-to-video
  model. Covers settling the concept before building, camera and framing math
  (why a subject's real angular size dictates the focal length, and why some
  shots are geometrically impossible), additive linear compositing with tone
  mapping, exposure that has to change as the field of view changes, glow and
  sprite artifacts, reflections, on-screen text, one timeline shared with the
  music, and the verification discipline that keeps you from reviewing stale
  frames or shipping a shot you never actually looked at. Use this skill
  whenever a task involves rendering or animating a short video, reel, short,
  greeting, explainer or title sequence programmatically; whenever frames are
  produced by code (numpy, PIL, matplotlib, Blender scripting) and assembled
  into an mp4; whenever a camera has to push in, pan or reframe over time;
  whenever compositing a subject over a background with glow, halo, haze or a
  reflection; or whenever a render looks washed out, too dark, flat, or has
  visible seams and edges. Reach for it even when the animation sounds trivial
  ("just zoom into this image over 10 seconds"), because the failure modes here
  -- inverted exposure laws, off-frame geometry, stale-frame review -- are
  silent and cost whole render passes.
---

# Procedural Video: Frames from Code

> Validated on macOS, September 2026, across several short vertical films
> (10-15s, 24-30fps) rendered end to end with this pipeline, each taken through
> multiple full render passes and human review.
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

## Settle the concept before writing the renderer

The most expensive miss is not a rendering bug but a clean render of the wrong
film. A technically correct piece built around one subject on an empty
background tends to come back as "fine, but monotonous", and a piece that only
implies its occasion tends to come back as "I can't tell what this is for".
Neither is fixable with parameters.

Before code, write two or three concepts in a few sentences each -- what is on
screen, what moves, what the viewer should feel, and the main risk of each --
and let the human choose. It is cheap, and the choice usually changes the scene
graph, not just the colours.

When the brief is for something that looks polished or "expensive", that rarely
means more symbols. What reliably reads as high production value in procedural
work:

- **Depth.** At least three layers -- far (haze-dimmed), middle, near -- so a
  slow camera move produces parallax. One subject on an empty field reads as a
  tech demo.
- **Light interacting with matter.** Reflections, glow through haze, rim light
  on cloud or mist, emitters lighting their surroundings. These are computations
  you can get right, and they carry the look.
- **Restraint in the finish.** Considered typography, generous negative space,
  a single closing element.
- **Say the message.** If the film is for an occasion or a greeting, put the
  words on screen; allusion alone is not enough for most viewers.

Avoid procedurally drawn figurative characters (people, animals, mascots). They
are the fastest route to looking cheap, and a silhouette traced onto data
rarely holds up. Suggest them through context instead.

## Test every physical detail for perceptibility

Accurate detail earns its place only if a viewer perceives it as intended. Time
compression is the usual trap: a slow real motion squeezed into seconds changes
meaning. A real, few-degree oscillation that takes weeks, played back in a few
seconds, reads as the subject **wobbling**, and a viewer will ask whether it is
a bug. Before adding a physically true effect, ask what it will look like at the
film's time scale and on a phone screen, and cut it if the honest answer is
"like an error" or "like nothing".

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

## Glows and sprites: force every falloff to zero

The classic artifact is a **visible rectangle** around a glowing element: a
radial falloff computed over a local box never reaches zero at the box edge, so
the box shows. Size the box from the falloff (about 4.5 sigma for a Gaussian),
and multiply by a term that hits exactly zero inside it:

```python
glow *= np.clip(1.0 - r / (4.0 * sigma), 0, 1) ** 2   # hard zero before the box edge
```

This applies to **every** local sprite -- particles, small lights, secondary
elements -- not only the hero subject. Fixing it on the main element does not
fix it on the twenty small ones drawn by a different function. Verify by
sampling a row through a sprite: values should fall off smoothly with no step.

Two related shading traps:

- **Directional weights must not reach zero.** Making a glow lopsided toward a
  light with `((1 + dot) / 2) ** k` drives it to exactly zero on the far side,
  and with a small `k` that zero shows as a thin **dark ray**. Use
  `exp(-k * (1 - dot))`, which is smooth everywhere.
- **Occlude only what is behind the object.** When a foreground body hides
  background elements (stars behind a planet, lights behind a building), apply
  the mask to those background layers only. Masking the whole canvas also
  removes haze and glow that sit *in front* of the body, and its dark side comes
  out darker than the sky around it.

## Map extents between spaces through the right Jacobian

Whenever a quantity's size is carried into another space -- a light source's
angular extent into surface-slope space for reflections, a pixel's footprint
into texture or world space, a blur radius into a different projection --
derive the mapping instead of assuming a uniform scale. The two axes often
scale very differently, and the error is silent: the output looks plausible,
and it is easy to rationalise as "that's just the physics".

Pair every such mapping with a sanity check from the real world. For
reflections: **on a calm surface, the reflection of a source is at least as wide
as the source.** A narrower reflection is a modelling error, not an effect.

### Reflections on water

A recipe that holds up for a light source over open water (Cox-Munk glitter):

- For each water pixel, take the half vector between the direction to the
  camera and the direction to the source, and turn it into the facet slope that
  would mirror the source into that pixel.
- Weight by the probability of that slope under the local slope distribution
  (resolved waves as the mean, unresolved roughness as the variance):

  ```python
  L = E_source * fresnel * p(slope_required) / (4 * cos_view * cos_tilt ** 4)
  ```

- Include the source's own extent in the slope variance, **per axis**. An
  azimuth offset `d` needs a slope of `d / (sin(view_depression) + sin(source_elevation))`,
  while an elevation offset needs about `d / 2`. Near grazing the first is an
  order of magnitude larger; using `d / 2` for both collapses the reflection into
  a thin line.
- Filter each wave component by the pixel's footprint on the water
  (`exp(-0.5 * ((kx*fx)**2 + (kz*fz)**2))`) and add the filtered-out slope
  variance to the roughness. Without it distant water aliases into flicker; with
  it far water becomes a smooth band and near water breaks into streaks.
- For sparkle, hand a fraction of the energy to short-lived random points whose
  mean equals the smooth result. The reflection glitters without changing its
  overall brightness.
- Mirror the rest of the scene (sky, distant land, other lights) by sampling a
  reflection buffer rendered from a virtual camera below the surface, at the
  elevation the resolved wave slope sends each ray to. Reflections then wobble
  with the waves for free.
- Blend distance haze into the water so the horizon dissolves instead of
  ending in a hard line.

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

## Text on screen

- Render glyphs to a coverage mask and blend them into the float image
  yourself, rather than relying on PIL alpha on an RGB image.
- Vertical CJK text: place one glyph at a time down a column.
- When a label changes on a beat (a counter, a date, a score), **hard-cut on the
  beat** instead of crossfading. Two different glyphs mid-crossfade can overlay
  into a third, legible, wrong character -- especially in CJK, where similar
  strokes stack convincingly. A hard cut also lands exactly on the music.
- A per-character reveal (each glyph fading in shortly after the previous one)
  reads as writing, and gives the music one onset per character to hit.

## Share one timeline between picture and music

Put every beat time in one small module that both the renderer and the cue
generator import. Compute derived event times (when a moving subject first
crosses an edge, when a counter ticks) by evaluating or solving the same motion
function the renderer uses, never by reading them off a preview. Then a change
to the motion moves the music with it, and each visual event lands on the first
frame after its note's onset without hand-tuning.

## Verification: the part that actually costs render passes

An agent reviewing its own render is prone to two specific mistakes, and each
costs a full pass.

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

**Look at the images.** Many defects are invisible in every number: two
subjects reading as a pair instead of one, a subject bisected by a divider line,
an outline that never faded, a ray or box artifact, a reflection narrower than
its source. Numbers catch exposure and geometry; only looking catches
composition. Check at least the opening, each transition beat, and the final
frame, and crop to full resolution around anything small.

**Treat the checker's thresholds as defaults, not verdicts.** Generic checks
(corner brightness, tonal spread, a midline seam) will fire on intentional
choices -- a lit sky, a night scene that is mostly dark, a centred subject. When
that happens, confirm by looking, then raise the threshold deliberately and say
so, rather than tuning the image to satisfy the check.

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
before writing your own; the mode you are about to reimplement may already be a
flag. Equally, check that a cached dataset actually covers what the shot needs:
a cache built for one framing can silently return an empty or clipped result for
a different one, which reads as a rendering bug and is not.

## Checklist before declaring a render done

- Concept chosen by the human before building; the message is said on screen
- Angular-size table printed, and nothing that must be visible is off-frame
- Every physically true effect checked at the film's time scale
- Frame corner dark unless lit by design; subject shows real tonal spread
- No rectangular glow edges on any sprite; no directional weight reaches zero
- Reflections at least as wide as their sources; no seam at panel boundaries
- Frames confirmed to be from this run (process exited, or fresh directory)
- Opening, each transition beat, and the final frame looked at as images
- `ffprobe` dimensions/fps/duration match intent; `ffmpeg -f null -` is silent
- Delivery codec matches the audience
