# Look development: concept, references, critique, density

Part of the `procedural-video-frames` skill. Read this before writing a
renderer, whenever a brief asks for something "premium", "expensive" or "for an
occasion", and whenever a technically clean render comes back as cheap, kitsch,
monotonous or unclear.

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

When the brief asks for something that looks polished or "expensive", that
rarely means more symbols. What reliably reads as high production value in
procedural work:

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

## References, a rubric, stills, and an independent critic

"Premium" is not something you can verify by checking your own code. The loop
that worked, after several technically clean versions were rejected as kitsch
or cheap:

1. **Research references before designing.** Have a sub-agent collect 8-12
   high-end references for the genre (broadcast, museum, brand work, and a few
   exemplars of the technique you plan from outside the local tradition) and
   distil them into a rubric of 6-10 concrete criteria plus the genre's common
   kitsch traps. The first page of search results for a genre is often mostly
   templates; their average is exactly what a first attempt converges to, and
   exactly what reads as cheap.
2. **Render look-development stills at final quality before animating.** Three
   frames (opening, turning point, final) cost seconds to revise; an animation
   pass costs minutes. Show them to the human and settle the look first.
3. **Run an independent critic on every revision round, before the human sees
   it.** A sub-agent with the rubric, the references and the keyframes (named by
   timestamp) scores each criterion and ranks the top problems with a concrete
   fix each; on the next round it checks its previous items as fixed / partly /
   not fixed. Use `critic_prompt.md` in this directory as the template. The
   critic reliably catches what the author has rationalised (a reflection
   narrower than its source, a straight wire that reads as an aliasing artifact,
   an opening frame that reads as the wrong occasion). The rule is *every*
   round: a round that went to the human without the critic was a process gap,
   and the human then spent attention on problems the critic would have caught.
4. **Spend the revision on material and light, not on new elements.** When
   something feels "not expensive enough", the tempting fix is to add a symbol;
   the effective fix is usually better geometry, a lighting event in a held
   beat, or a truer material.

An image model (for example GPT Image 2.5) can make quick concept frames for
step 2 while the concept is still open. **Untested** in that role; its use for
illustration plates inside a film is covered below and was exercised.

## Explainers: give the eye something to look at

For structure and motion (sets on one sheet, elements that persist, element-wise
arrivals, drawing diagrams in the plates' register) read `motion.md`; this section
covers the plates themselves.

A narrated explainer built only from typography and charts reads as dull, however
clean. The request that came back on one was, in effect, "it is all text; find or
generate some visuals". Plan figurative plates from the start: the places, objects
and people-at-work the narration talks about, one per scene where a scene would
otherwise be type on an empty page.

**Generate one consistent set rather than searching for images.** News and stock
photos carry licensing problems and never share a look. A set generated in one
style that matches the film's palette reads as part of the page:

- Lock the style on one plate before generating the rest, then generate the rest
  in parallel with the same style paragraph: medium and technique (for example
  steel engraving, cross-hatching in near-black ink), the paper colour, where a
  spot colour is allowed, and "no text, no border, isolated subject, plain paper
  background".
- **Print the plates onto the page instead of pasting them.** Normalise each plate
  so its paper becomes exactly white (divide by the median border colour), feather
  the edges to white, and composite with a multiply blend. Only the ink lands; the
  film's own paper, grain and ruling stay continuous under it.
- **Resize with a good filter before drawing.** Fine hatching aliases badly when a
  1024 px plate is drawn at half size with plain bilinear sampling; resize to the
  exact on-screen size with Lanczos once, at load.
- **Small plates must be strictly monochrome line work.** At around 100-150 px, the
  same style prompt produced tinted, glossy, soft-shaded objects that read as app
  icons in an engraving costume. Ask explicitly for no colour, no gloss, no soft
  shading, one bold simple subject.
- **Plates obey the page's fixed geometry.** A plate crossing a fixed margin rule
  or overlapping the subtitle band reads as a layout error; paired plates (two
  buildings facing each other) share one ground line; plates on the same page
  share a period and a technique.
- The independent critic (above) is the check: it flagged the tinted icons, a plate
  from a different period and a guilloche competing with the number printed over it.

**Data frames carry their source.** Put one fixed, legible source line on every
frame that shows a number, and label anything illustrative as illustrative (a
"schematic" tag on a curve that has no data behind it). Quantities that the film
compares across scenes must agree numerically: when one scene showed a stack of
3 costly rounds against 38 cheap ones and the next showed the same bill as an area,
the first version implied x1.2 in one and x1.6 in the other, and the critic caught
it. Derive both from the same numbers.

**Colours keep one meaning.** Once red and blue stand for the two sides of a
conflict, do not reuse either for an unrelated series (a price curve drawn in the
"insurer" blue read as the insurer's).

## Compose the symbol; do not display it

A symbol drawn by the action of the film (threads tracing the emblem's own
construction lines, light revealing a surface) reads as crafted. The same symbol
shown on a screen or billboard inside the scene reads as a template. When an
occasion needs its emblem, look for a way the film's motion can *construct* it.

## Density: judge detail at its on-screen size

Detail is perceived at the size it ends up on the viewer's screen, not at the
size you designed it. Two failure modes, both observed:

- **Dense regular grids of small repeated units** used as a reveal (a picture
  resolving out of thousands of identical tiles) trigger a crowding or
  trypophobic reaction. A single element that grows, plus light that spreads,
  carries the same idea without it.
- **Fine repeated motifs on small objects** read as dirt or noise, and at high
  density trigger the same crowding reaction -- even when the same motif looks
  exquisite on the large hero object (it happened with fine scrolls on small
  secondary stars). Give small objects clean, simple forms deliberately; see
  the level-of-detail section in `detail.md`.

Sanity check: view the frame at the delivery size (a phone held at arm's
length, or the frame scaled to ~1/3), not zoomed in at 100%. If a textured area
reads as "speckled" or "dirty" there, simplify it; if the texture only becomes
visible at 100%, it is not contributing.

## Test every physical detail for perceptibility

Accurate detail earns its place only if a viewer perceives it as intended. Time
compression is the usual trap: a slow real motion squeezed into seconds changes
meaning (a few-degree oscillation that really takes weeks, played back in
seconds, reads as the subject **wobbling**, and a viewer asks whether it is a
bug). Before adding a physically true effect, ask what it will look like at the
film's time scale and on a phone screen, and cut it if the honest answer is
"like an error" or "like nothing".

The same question applies to highlights: check what a bright spot *reads as*,
not only whether it clips (see "A highlight can read as a different object" in
`sprites_text.md`).
