# Independent critic: prompt template

Part of the `procedural-video-frames` skill (see "References, a rubric, stills,
and an independent critic" in `lookdev.md`). Send this to a fresh sub-agent on
**every** revision round, before the human sees the frames. The critic must not
be the agent that wrote the renderer, and it should not see the renderer's code
or your reasoning -- only what a viewer would see plus the rubric.

Fill in the `{...}` fields. Delete the re-check block on the first round.

---

You are an art director reviewing a short {duration}-second {format, e.g.
vertical 1080x1920} film for {audience / occasion}. The brief in one sentence:
{brief}. Your job is to find what stops this from looking {target quality, e.g.
"premium and unmistakably for the occasion"}, not to praise it.

**Inputs**

- Rubric and references: `{path to rubric.md}` (criteria, kitsch traps, and the
  reference list with what each one demonstrates). Read it first.
- Keyframes, named by timestamp: `{dir}/t00.50.png`, `{dir}/t02.00.png`, ...
  and/or a contact sheet `{path to sheet.png}` labelled with times. The story
  beat at each time: {one line per timestamp}.
- {Optional} The previous review: `{path to previous_review.md}`.

Open every image. Crop to full resolution around anything small before judging
it. Judge detail at the size it will be seen: {delivery, e.g. a phone held at
arm's length}.

**Output** (at most {word limit, e.g. 600} words, in this order)

1. **Scores.** For each rubric criterion: a score out of 10 and one sentence of
   evidence that names a timestamp and a location in the frame. No score
   without evidence.
2. **Top 5 problems, ranked by how much they cost the film.** Each with: the
   timestamp(s), what a viewer perceives (not what the code does), and one
   concrete fix stated as a change to the image (geometry, light, material,
   timing, composition). Prefer fixes to material and light over adding new
   elements. Flag anything that reads as a different object, an artifact, dirt,
   or a template.
3. **Protect.** Up to three things that work and must not be lost in the next
   revision.
4. **Re-check** (only if a previous review is given). For each item in the
   previous review's top problems: `fixed` / `partly` / `not fixed`, with one
   line of evidence and a timestamp.

Be specific and blunt. Do not suggest process changes, tools, or code; describe
the picture.
