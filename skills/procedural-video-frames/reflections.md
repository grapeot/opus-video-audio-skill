# Reflections and extent mapping

Part of the `procedural-video-frames` skill. Read this when a scene has water
or any glossy surface reflecting a light source, or whenever a size (a source's
angular extent, a pixel footprint, a blur radius) is carried from one space
into another.

## Map extents between spaces through the right Jacobian

Whenever a quantity's size is carried into another space -- a light source's
angular extent into surface-slope space for reflections, a pixel's footprint
into texture or world space, a blur radius into a different projection --
derive the mapping instead of assuming a uniform scale. The two axes often
scale very differently, and the error is silent: the output looks plausible,
and it is easy to rationalise as "that's just the physics" (a reflection path
came out about 20x too narrow and was first misread that way).

Pair every such mapping with a sanity check from the real world. For
reflections: **on a calm surface, the reflection of a source is at least as wide
as the source.** A narrower reflection is a modelling error, not an effect.

## Reflections on water

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

Sanity checks: the path's width near the horizon is at least the source's
width; far water is a smooth band, not flickering speckle, across consecutive
frames; the mean brightness of the path does not change when sparkle is
switched on.
