# Working notes

## Changelog

### 2026-09-27 — `lib/opusvid`, `check_frames.py assemble`, and a minimal end-to-end example

Across the films so far the same plumbing was written four or five times almost line for line: an argparse block with `--out/--frames/--jobs/--plan` around a `multiprocessing.Pool` with a per-worker initializer; `smooth()`; a PCHIP camera path with width interpolated in log space; bisection for "when does this motion cross X"; a per-frame camera JSON for a Blender layer; and the text helpers (glyph coverage mask, letter-spaced line, one-glyph-per-cell vertical column, blend into the float image, per-character timed reveal, a blurred dark bed under text). That code now lives in `lib/opusvid/` (`runner`, `timeline`, `typeset`), kept deliberately thin: nothing about any film's subject, shading or layout moved in. Two behaviours are new rather than extracted, both answering failures documented in the skill: `runner` refuses to render into a non-empty output directory unless `--overwrite` (stale frames were reviewed more than once), and it records the run start in `run_start.txt` and prints the matching `check_frames.py frames --since` command. `solve_time` scans for the first sign change before bisecting, so it returns the *first* crossing of a non-monotone motion.

`check_frames.py assemble` replaces the hand-typed ffmpeg line: H.264, yuv420p, CRF 18, faststart, explicit `-framerate`/`-r`, optional `--scale`, audio as AAC with `-shortest`, then the `stream` check with the expected duration (frame count / fps), fps, size and audio stream. It fails before encoding on a numbered sequence with gaps (ffmpeg's image2 demuxer would stop at the first gap and silently shorten the film) and on odd output dimensions; a cue shorter than the picture fails the duration check. `stream` gained `--expect-size WxH`.

`examples/minimal_film/` exercises all of it in 3 s at 360x640/30 fps, with the dot's centre crossing solved from its motion and fed to both the flash and the cue. Verified end to end on macOS with MuseScore_General.sf2, running the README's commands verbatim: 90 frames in ~1.5 s on 32 workers; `frames --since ... --min-spread 0` ok (corners 14.8/255; the default tonal-spread check fails on this mostly dark frame, as documented, and is relaxed deliberately); crossing solved at 1.170 s; `score_cue.py render` 3.0 s, peak 0.579, raw peak 0.80 at `-g 4`, all three storyboard checks ok; `assemble` wrote `h264 360x640 @ 30fps` + `aac`, duration 3.000 s, clean decode, exit 0. A second render into the same directory exits 2 and assembling a preview subset exits 1. `tests/test_opusvid.py` adds 14 cases (PCHIP through keys without overshoot, log-space width, first-crossing `solve_time`, camera JSON against the pixel formula including rotation, frame-spec parsing, the non-empty-directory guard, a pooled subset render, glyph masks, letter spacing, vertical column extent, clipped blending, reveal and bed, and `assemble` on tiny generated frames with audio, scale, start number, gap, short cue and odd size); all 26 tests pass.

### 2026-09-27 — video skill split into an entry file plus sub-documents; new lessons and tools

`procedural-video-frames/SKILL.md` had grown past 500 lines, too long to read reliably in one pass. It is now the entry file: frontmatter, overview, a routing table, the rules that apply to every render (framing in angles, linear compositing with one tone map, exposure vs field of view, verification, assembly with one shared timeline) and the checklist. Everything else moved, tightened and with film-specific narration replaced by general rules, into `lookdev.md`, `detail.md`, `reflections.md`, `sprites_text.md` and `blender_handoff.md`; `critic_prompt.md` is a new reusable prompt for the independent critic. No guidance was dropped.

New lessons, each stated as a general rule: an orthographic top-down camera cannot show height, so elements riding a waving cloth were invisible until height was mapped to screen displacement (`seen_y = y - K*z`, shared by both layers; perspective is noted as an untested alternative); two crossing wave systems read as latex, so one travelling wave should dominate, and a wrong shared plate means checking the shared motion module first; detail density is judged at on-screen size (fine motifs on small objects read as dirt or crowding), so level of detail simplifies small objects deliberately; a change of representation is a cross-fade of two independently shaded layers, not a growth mask; anti-aliasing specifics (0.7 px Gaussian pre-filter before normals, SDF-based edge coverage); a blown specular with bloom can read as a different object (remedies marked untested); the critic runs on every round; and coding-agent operations (run parameter changes yourself once a script works, tell the agent not to call other agents).

Tools: `check_frames.py sheet` (labelled contact sheet at given timestamps); `check_frames.py frames --ignore-region x0,y0,x1,y1` (repeatable; step measured only over pixel pairs outside the boxes, so a box's own border does not create a new step); `scripts/serve_video.py` (serves only the listed files on the LAN with Range/HEAD for iOS Safari; binding to all interfaces is documented as a privacy exposure); `tests/test_scripts.py` (9 unittest cases). Verified against a real 450-frame 1080x1920 sequence: without regions `frames` exits 1 on a column step at 504 and a row step at 776, both straight bright edges of the design; a tight box around the row edge removes only the row failure, a box around the column edge removes only the column failure, both together exit 0. `sheet` at 10 timestamps (30 fps) wrote a 1104x816 sheet with the expected frame indices, and a timestamp one frame past the end exits 1. `serve_video.py` on a spare port returned 206 with the right `Content-Range` for `bytes=0-1023` and a suffix range, 200 for HEAD with `Accept-Ranges: bytes`, a byte-identical full download, 416 past the end, 302 from `/`, and 404 for an unlisted file in the same directory and for `..` paths.

### 2026-09-27 — look development, critique loop, Blender hand-off

From a 15 s National Day film that went through several rejected versions (fireworks over a CG city: realistic but "not recognisably the holiday", then "kitschy, not expensive"; a flag of ten thousand tiles: trypophobic) to an accepted direction (one gold filigree star grown under a macro lens, pulled back, threads tracing the flag's construction lines, silk revealed by light). Added to `procedural-video-frames`: references + rubric + look-dev stills + an independent critic sub-agent before the human sees anything; compose symbols rather than display them; avoid dense tile grids; SDF per-pixel rendering across a two-order zoom with real helix geometry, level of detail, per-motif layout (circle packing per facet), arc-length glints, per-element growth, PCHIP log-width camera; handing the material layer (silk) to Blender through Codex with an explicit contract (shared coordinates, per-frame camera file, orthographic projection verified through Blender's camera matrix to <0.001 px, lighting as a formula, 16-bit Standard-view PNG, linearise before compositing) and the operational findings (Blender segfaults in the agent's write sandbox; the agent inherits workspace rules; first Metal compile ~2 min, then ~2.5 s/frame). GPT Image is mentioned for concept frames and plates but marked untested. Added to `video-scoring-audio`: instrument choice (GM brass/timpani read cheap) and a numpy-synthesised sound-design layer (FM bells, bloom, shimmer, synthetic-IR hall) mixed under a sparse MIDI score.

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
