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

If an image model is available (for example GPT Image 2.5), it is a natural
tool for step 2 while the concept is still open -- quick concept frames to
choose between directions before any renderer exists -- and for static
background plates that need photographic richness. **Untested:** this use was
not exercised in the films this skill was built from; check its output against
the rubric like anything else.

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
