# Explainers that do not read as slides

Part of the `procedural-video-frames` skill. Read this before laying out a narrated
explainer longer than a minute, and whenever a render comes back as "a slideshow",
"a deck with a pointer", or "static". It covers the structure (one sheet, a camera,
persistent elements), the vocabulary of element-wise motion, pulling drawn diagrams
into the same visual register as generated plates, and the traps that cost a pass.

> Validated on one five-minute horizontal narrated explainer (1080p30, 23 voice lines,
> 13 scenes in 6 sets, about 110 subtitle cues), rendered with skia and reviewed by an
> independent critic sub-agent and the owner. Code: `lib/opusvid/motion.py`.
> Anything marked **untested** was not exercised on that film.

## Done when

- No keyframe at a beat time reads as a static bullet slide: at every beat something
  is being drawn, arriving, rolling, growing or moving on its own clock.
- Scenes that belong together share one canvas: an element that is still relevant stays
  on screen and changes in place instead of being cut away and redrawn.
- Every procedural diagram has been looked at next to the illustration plates on one
  contact sheet, and a critic did not call them two visual languages.
- The frame has no large dead zone next to a crowded one at any beat.
- Every data frame carries a source line from its first frame; every illustrative
  curve says so.

## Structure: one sheet, a camera, no cuts

**Group scenes into sets and lay the sets side by side on one long sheet.** A set is a
run of lines that share a subject (the bean and what happens inside it; the roast
curve and how to read it; the machine). Inside a set nothing cuts: the camera stays,
and elements are added, recoloured, moved or retired as the narration advances.
Between sets the camera slides sideways to the next set, with a blur along the pan
(`SetPan`, `blur_along_x`). A page that slides reads as one publication; a cut to a new
layout every twelve seconds reads as a deck.

**Let an element outlive the line that introduced it.** The strongest moments were
callbacks: the same logged curve drawn by a pen, then shaded into phases, then squeezed
upward to make room for its derivative, then annotated with the narrator's numbers; a
tree of variables grown in one set and returned to, locked branch by branch, two sets
later. Changing a thing in place costs the viewer nothing to re-read and shows cause
and effect.

**Move the camera inside a set while a detail is discussed.** A slow push-in (about 15%)
onto the part being described, then a pull back, keeps a long hold alive without new
elements. The critic flagged a 25-second hold on one diagram as "a slide with a pointer"
before the push-in was added.

## Vocabulary: every element arrives by an action tied to a word

Key each arrival to the phrase that names it (`Narration.at`, `narration.md`). The
actions that carried the film, all in `lib/opusvid/motion.py` or `typeset`:

- **A pen traces it**: curves, branches, routes, brackets and axes are drawn at constant
  speed along their arc length (`pen`), with a small glowing tip while moving. Parametrise
  by arc length: a logged curve sampled in time has uneven point spacing, and drawing by
  index makes the pen lurch.
- **A plate inks in** instead of fading: pixels arrive where a smooth radial-plus-noise
  field falls below the progress (`PrintIn`), so an engraving appears as if printed.
  This is for an *arrival*. For an object *changing* state (a colour, a form) use a
  cross-fade (`InkBlend`); a mask sweeping from one state to another reads as
  mechanical (`detail.md`).
- **It pops** with a small overshoot on scale (`back_out`), for chips and labels, each on
  its own word, never a whole list at once.
- **It types on**, one character at a time settling from a few pixels below, for titles
  and key sentences.
- **A number rolls** to its value on fixed-advance digits and lands exactly on it
  (`roll`); bars grow; a ring timer sweeps. A rolling counter is a hard cut every
  frame; never cross-fade digits (`sprites_text.md`).
- **Particles live on their own clocks** (`motes`): each has its own birth, heading and
  curl, so aroma or steam never moves as one sprite.
- **State drives colour**: an object's appearance follows the quantity being explained
  (a bean sprite cross-fades through roast colours by the logged temperature, a
  cross-section plate is re-tinted as its temperature rises, a dial needle follows the
  pressure). This reads as explanation, not decoration.
- **Idle motion** keeps a hold alive: a slow bob or rotation on the hero object, a fan and
  paddles turning, air parcels flowing, a pulsing sensor.

Stagger siblings (`stagger`): three leaves arriving 0.2 s apart read as growth, three at
once read as a slide build.

## Draw diagrams in the plates' register

A film that mixes engraved illustration plates with flat vector diagrams reads as two
publications pasted together; the critic's top finding on this film was exactly that
(the machine diagram, the variable tree and padlock icons looked like "a generic tech
deck pasted into an atlas"). Pull the drawn layer toward the plates rather than the
other way:

- **Hatch instead of fill**: a drum wall drawn as a ring of short radial hatch strokes,
  darker on the shadow side; a bar chart as an outlined column with diagonal hatching,
  not a solid block.
- **Use sprites cut from the plates** instead of drawn icons: generate one plate that
  contains a whole progression (seven beans from green to dark, in a row) and crop the
  objects out of it (`crop_sprites`), so style, light and scale match exactly; crop a
  single object (one bowl) out of a scene plate to replace an icon. Separate generations
  of each object do not match each other.
- **Materials over symbols**: a brass tag with engraved hatching for "locked" instead of a
  UI padlock glyph; tiny cropped bean sprites tumbling in the drum instead of ellipses.

One register is not one level of richness. Keeping everything in the same
*publication* is compatible with holding a richer passage back as an event
(`music_video.md`); what reads as cheap is an unrelated style, not an escalation.

## Traps that cost a pass

- **Cross-fading two multiply-blended plates darkens the middle.** Drawing plate A, then
  plate B at alpha f, both in multiply, gives A times a partial B: darker than either end.
  A bean fading between two roast colours went near-black mid-fade. Blend the inks first
  and multiply once (`InkBlend`), with the stage quantised and cached.
- **CJK glyphs in a Latin display face** (`sprites_text.md`) came back with single
  characters: a serif set for numbers rendered 一 and 年代 as tofu boxes.
- **Colour progressions must match the message.** A bean mapped to the full green-to-black
  range by temperature ended nearly black for a light roast the film was recommending;
  map the logged range to the colours that roast really reaches.
- **Dead zones next to crowding.** A chart pinned to the left with nothing on the right for
  80 s reads as a spreadsheet; give data sets a fixed annotation column (the live object
  and its readouts) and use it for the whole set.
- **Ghosts.** An element faded to 10% instead of zero reads as dirt; retire things fully.
- **Data when the API is down.** If the source system's API is unavailable but an earlier
  analysis saved a matplotlib SVG, the curve can be recovered: take the `line2d` path
  vertices and map them through the tick positions (`xtick_*`/`ytick_*` `use` elements)
  read against the tick labels. The recovered start, minimum and end values matched the
  numbers in the original analysis. Say "digitised" in the source line.

## Title card

Open with the title built the same way as everything else: a hero object changing state
while the title types on and a rule draws under it, then the whole card lifts away as
the first plate inks in. A static title slide at the start sets the wrong expectation
for the rest.
