# Fine detail across a large zoom: SDFs, level of detail, anti-aliasing, growth

Part of the `procedural-video-frames` skill. Read this when a subject must hold
crafted detail (wire, filigree, engraving, ornament) at very different screen
sizes, when a camera zooms across one or more orders of magnitude, when fine
structure aliases into dashes or stair-steps, or when something must visibly
"be made" on screen.

## Describe the subject as distance fields and evaluate per pixel

A continuous move from a single wire to the whole object (two orders of
magnitude) is a strong "small to grand" reveal, and it can be rendered without
meshes:

- **Evaluate signed distance fields per pixel.** Map each pixel to world
  coordinates for the current view, compute distances to the subject's curves,
  turn them into a height field, and take normals from its gradient. The same
  code then renders one wire filling the frame and the whole object at the far
  end, with exact detail at every zoom.
- **Model the real geometry instead of faking it with a texture.** A twisted
  two-strand wire modelled as two round strands on a helix (pitch about two
  diameters) reads as crafted metal; the same wire as a sinusoidal bump pattern
  reads as a noisy circuit trace. Under a single grazing key each twist gets its
  own highlight. Sanity check: compare against a macro photograph of the real
  material -- every repeated feature there has its own specular.
- **Drive the camera through keyframes with a monotone cubic (PCHIP) in log
  width.** Smoothstep between keys stops at every key; linear width races at the
  tight end.

## Level of detail: for legibility, not only for aliasing

- **Below about 5 px, crossfade a feature to a simpler form** (a smooth tube; a
  whole shaded shape). Otherwise fine structure aliases into dashes and
  stair-steps exactly where the final frame rests.
- **Simplify small objects on purpose, even when they would not alias.** A
  motif that is exquisite on the hero object reads as dirt, or triggers a
  crowding reaction, on a small secondary object (see "Density" in
  `lookdev.md`). Decide the representation of each object from its on-screen
  size: small objects get clean forms (a plain faceted shape, a single outline),
  and the intricate version is reserved for what is large enough to read.

## Anti-aliasing a height-field renderer

Both of these removed visible artifacts in the final frames:

- **Pre-filter the height field before taking gradients.** Normals from a raw
  per-pixel height field alias into dotted lines along creases, especially on
  warped facets. Blur the height with a Gaussian of about 0.7 px (in screen
  pixels) and take the gradient of the blurred field.
- **Compute thin-edge coverage from the distance, not by thresholding height.**
  `height > 0` gives a hard, stair-stepped edge that crawls when the object
  moves or stretches. Use the SDF distance `d` and the pixel size `px` (both in
  world units):

  ```python
  coverage = np.clip(0.5 - d / (1.3 * px), 0, 1)
  ```

  This is a ~1.3 px linear ramp centred on the outline; multiply the object's
  shaded colour by it when compositing.

Sanity check: crop a moving edge at 400% across a few consecutive frames. A
correct edge has one or two intermediate pixels that change smoothly; a
thresholded edge shows pixels flipping fully on and off.

## Lay motifs out so no boundary slices them

Deciding per pixel whether a motif (a spiral, a scroll) may appear leaves
half-arcs wherever a ridge or outline passes, which reads as a boolean error.
Decide per motif instead: pack circles into each region (e.g. the incircle of a
triangular facet plus chains toward its corners, shrunk away from any border
band) and put one whole motif in each. Taper free ends rather than cutting them.

## Measure glints and growth fronts in arc length, not angle

A glint defined as a window in a spiral's angle is a point near the centre and
a long band on the outer turns. Scale by radius so it stays a pinpoint. The
same applies to any front that travels along a curve.

## Growth, reveals, and changes of representation

- **Animate "being made" along each element's own path.** A single circular
  reveal front cuts every wire on one circle and reads as a mask. Letting each
  element wind out from its own start when the front reaches it reads as the
  object being formed.
- **Change an object's representation with a cross-fade of two independently
  shaded layers.** When an object turns from one form into another (intricate
  to plain, open-work to solid), shade both versions completely, each with its
  own normals and lighting, and blend the two results (blend the results, then
  composite once: two multiply-blended layers cross-faded on the page darken the
  middle, see `motion.md`). A growth or reveal mask
  sweeping from one form to the other reads as mechanical, and the human
  reviewer preferred the plain fade. Growth masks are for *making*
  something; cross-fades are for *changing* it.
