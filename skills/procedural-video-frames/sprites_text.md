# Glows, sprites, highlights, seams, and on-screen text

Part of the `procedural-video-frames` skill. Read this when drawing glows,
particles, small lights or bloom; when a render shows rectangles, rays, seams
or unexpected bright shapes; when assembling a frame from panels; and before
putting any text on screen.

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

## A highlight can read as a different object

A specular highlight that blows out on a narrow facet, then gets bloom, stops
reading as "shiny" and starts reading as a thing: an elongated blown highlight
with a soft bloom around it read as a **flame** on a metal object. Clipping
checks do not catch this, because the problem is the shape of the bright
region, not its value.

- Look at every bright region in the keyframes and name what it reads as. If
  the answer is anything other than "light on this material", fix it.
- Candidate remedies (reasonable, but not individually tested here): cap the
  specular on that facet below clipping, widen the lobe so the highlight follows
  the facet's form, or reduce bloom on thin shapes (bloom turns a thin bright
  line into a soft glowing body).
- Sanity check: real polished metal photographed with a single key shows
  highlights that follow edges and facets; a free-floating soft glow is a light
  source, and viewers will read it as one.

## Seams: draw shared geometry once, across the whole frame

When a frame is assembled from panels (split screen, per-source layers), drawing
the same background element separately per panel produces a seam: the two
copies disagree at the boundary, and padding that overshoots the midline makes
it worse. Draw anything that spans the frame **once**, over the full width, and
place per-panel items on top of it afterwards.

Verify numerically: the mean of the seam columns should equal the mean of
columns well away from it (`check_frames.py frames --seam`). If it does not, the
seam is real and a viewer will see it.

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
  (This is the opposite of the rule for changing an *object's* representation
  in `detail.md`, where a cross-fade is right: text is read, objects are seen.)
- A per-character reveal (each glyph fading in shortly after the previous one)
  reads as writing, and gives the music one onset per character to hit.
