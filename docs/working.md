# Working notes

## Changelog

### 2026-09-26 — lessons from two more films

Two films made with the renamed skill: a 12s lunar-phase piece and a 15s moonrise over the sea (sky lanterns, calligraphy, seal). Added to `procedural-video-frames`: decide the concept before rendering (the first film was clean but read as monotonous and not as the holiday; the second concept was picked by the human from three written options); physically true effects that read as glitches at the film's time scale (compressed libration looked like wobble); mapping a source's size through the right Jacobian (the moon path came out ~20x too narrow in azimuth, first misread as physics) with the Cox-Munk glitter recipe and footprint filtering of waves; glow boxes recurring on small sprites; directional weights that hit zero draw a dark ray; occluding only the layers behind an object; coloured emitters losing hue in the tone map; hard-cutting changing labels (a crossfade overlaid two characters into a third); one shared timeline module for picture and music. Added to `video-scoring-audio`: generate the cue from the picture's timeline; check that no early accent competes with the intended peak.

`check_frames.py frames`: the midline seam check is now opt-in (`--seam`), because a centred subject such as a moon's reflection path trips it on an ordinary shot. Re-verified: the known-bad split-screen pass from the first film still exits 1 without `--seam` (column step at 541), the good first-film render and the moonrise render exit 0 (the latter with a deliberately raised `--max-corner 35` for its lit sky). Corner and tonal-spread messages now say when a lit sky or a dark night scene is the likely cause.

### 2026-09-26 — renamed to opus-video-audio-skill

Renamed from `video-audio-skill` to make the supported configuration explicit: both skills were authored and validated with Claude Opus and have not been tested with other models. Skill names (`video-scoring-audio`, `procedural-video-frames`) are unchanged.

### 2026-09-25 — initial extraction

Repository created from a real job: the music and SFX bed for a 10-second vertical video on macOS. Contents scoped to the audio half of the pipeline, which is the only half that was validated.

- `skills/video-scoring-audio/SKILL.md` — the skill.
- `scripts/score_cue.py` — compose → render → normalize → verify CLI, with `init`, `render`, `measure`, and `fingerprint` subcommands.
- `examples/cue_reveal.json` — 10s cue spec, reveal beat at 6.0s.

Verified during authoring: `fluidsynth` 2.6.1 and `ffmpeg` on PATH; both soundfont banks present; `render` passes all four storyboard checks at 10.00s / peak 0.7359 with MuseScore_General.sf2 at `-g 6`; `fingerprint` correctly separates three real instrument variants (harp 757.6 Hz, music box 951.9 Hz, celesta 1205.6 Hz) and correctly fails a deliberately duplicated file; the macOS DLS bank at `-g 1.0` produces raw peak 0.1529 and triggers the low-gain warning.

## Lessons learned

These are the failures the skill exists to prevent. Each one was observed, not anticipated.

### Generative music models ignore timing instructions

Asked Google Lyria (`lyria-3-clip-preview`) for "two isolated notes, then low strings entering at 6 seconds". The returned clip's measured per-second RMS envelope was flat and fully loud (-9 to -13 dB) across 0-12s — no sparse opening, no entry at 6s. The model absorbed the timbre and tempo hints and discarded the dynamics.

This is the decisive finding of the whole project: a generative model cannot be directed to do a specific thing at a specific timestamp. Rewriting the same structure as MIDI note events produced an envelope matching the storyboard exactly. Anything scored to picture goes through MIDI.

### The Lyria copyright filter blocks genre and tradition names

A prompt containing "in the East Asian tradition" returned `finishReason: "OTHER"` with a `finishMessage` about content resembling existing copyrighted works. No audio was produced, but the call still consumed quota. Describing timbre, instrumentation and structure instead — plus "original composition" — generated successfully on the next attempt with the same musical intent.

### fluidsynth output is longer than the MIDI file

A MIDI file of nominal length 10.00s rendered to 12.83s with the macOS DLS bank and 13.25s with MuseScore_General.sf2 — reverb and note-release tails keep the writer going past the last note-off. Without an explicit `-t 10` trim this overruns a video cut. The trim is in the pipeline for that reason, and `score_cue.py` treats a duration mismatch beyond 0.1s as a failure.

### Loudness targets are hypotheses, peaks are measurements

`loudnorm=I=-16` produced peak 1.092 — clipping. Lowered to `I=-19:TP=-3:LRA=11`, which holds. The lesson generalizes: the loudness target is an input you choose, the peak is an output you must check.

### Soundfont gain does not transfer between banks

The macOS DLS bank needs roughly `-g 4.5` (raw peak 0.015 at default gain — effectively silent); MuseScore_General.sf2 needs roughly `-g 6`. Carrying a gain value across a bank change yields either a silent or a clipped render. Re-measure after every switch.

### Four "variants" that were the same file — the near-miss

Four different-instrument variants were generated by patching a `program_change` value in the source with `sed`. All four came back with identical duration, peak 0.737, and spectral centroid 722 Hz. The `sed` pattern had silently failed to match, so all four were the same piano — one keystroke from being presented to a user as a four-instrument A/B comparison.

The failure was also retroactive: it revealed that an earlier "vibraphone" render already handed over for review had been piano all along, which invalidated the feedback collected on it.

Two fixes, both now in the skill: parameterize the varying value as a CLI argument rather than rewriting source text (a failed substitution is silent, a missing argument is loud), and fingerprint every variant to assert they differ before calling them choices. `score_cue.py fingerprint` exits non-zero on a collision.

### An agent cannot hear audio, and this is an engineering constraint

Not merely a disclaimer. Because the feedback loop is numeric, techniques whose output is predictable from their input are strictly preferable to techniques that need ears to steer — which is the underlying reason MIDI beat the generative route here. Objective properties worth asserting: duration, peak/clipping, per-window RMS envelope, spectral centroid. The aesthetic verdict is always a handoff to the human.

One measurement subtlety found while testing: a single struck note's attack window reads loud even in a genuinely sparse passage, so "quiet" storyboard checks belong in the gaps between notes rather than on an onset. The starter spec's first check was initially at 0.0s and failed for this reason; moved to 1.0s, where the note is decaying, it reflects what was actually intended.

### GarageBand and Logic cannot be automated

No headless mode, and their instruments are AudioUnit plugins in Apple's proprietary format rather than files a synthesizer can load. A human must drive the GUI. This is the reason the open SF2 + fluidsynth path matters — it is the only route where a script owns the whole compose-render-measure loop.

## 2026-09-26 — video half added

`skills/procedural-video-frames/SKILL.md` + `scripts/check_frames.py`.

Distilled from rendering a 10s vertical film end to end (roughly a dozen full
240-frame passes). The lessons that cost the most:

**Framing is a feasibility question, not a taste question.** The Moon is 0.52°
across; in a 52° field on a 1920px frame that is 11 pixels. Filling the frame
needs ~3.1°, and at that field a camera aimed 50° up puts the horizon thousands
of pixels below the frame — so "subject fills the frame AND the ground is
visible" was geometrically impossible, not badly tuned. Caught only after a
render pass. `check_frames.py plan` now prints this table up front.

**The exposure law runs opposite to intuition.** Per-element gain must fall as
the field widens, because a wide frame packs far more elements into the same
pixels. Written the other way round, the wide shot blew out to grey noise.

**Halos need a hard zero.** A radial falloff computed over the subject's
bounding box never reaches zero at the box edge, so the box shows as a grey
rectangle. Multiply by a term that hits zero well inside the box.

**Two PIL traps.** `ImageDraw.line` on an RGB image silently ignores alpha in
`fill`, so a "fading" divider stayed fully opaque all shot. And an element
composited inside a half-width panel is cropped at the panel edge — once two
panels converge on one subject, composite it on the whole frame.

**Two verification failures, each costing a full pass.** Waiting on a *file
count* is a race against the previous run's frames: the wait returned instantly
and stale images were reviewed, concluding a fix "didn't work" when it was never
tested. Wait for the process to exit, or render to a fresh directory. Separately,
a preview script that reimplemented the render loop drifted from it — validating
a program that was not being shipped.

**Numbers cannot see composition.** Coordinates converged correctly through a
pass where two subjects read as a pair instead of one, a subject was bisected by
a divider, and an outline never faded. None of it appeared in any metric. The
skill therefore pairs mechanical checks with an explicit instruction to open the
frames at the opening, each transition beat, and the end.

`check_frames.py` verified against this project's real output: passes the good
render (exit 0), catches the known-bad pass by its seam and halo step at column
541 (exit 1), validates the finished mp4, and flags stale frames via `--since`.
