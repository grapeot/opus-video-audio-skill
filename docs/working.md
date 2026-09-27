# Working notes

## Changelog

### 2026-09-27 — explainers that do not read as slides (`motion.md`, `lib/opusvid/motion.py`)

From a five-minute horizontal narrated explainer (1080p30, 23 lines, 13 scenes in 6 sets, ~110 subtitle cues) whose owner's brief was, above all, "not a slideshow; many drawn visuals with fine element-by-element motion". New sub-document `motion.md`, routed from `SKILL.md` with a checklist line: scenes grouped into sets on one long sheet with a sliding camera and pan blur instead of cuts; elements that outlive their line and change in place (one logged curve drawn, phased, squeezed for its derivative, annotated; a variable tree grown, then locked two sets later); a push-in during long holds (the critic called a 25 s static hold "a slide with a pointer"); the vocabulary of word-keyed arrivals; state-driven colour; drawing diagrams in the plates' register (the critic's top finding on round one was "two visual languages": flat vector diagrams and UI icons next to engraved plates; fixed with hatched walls and columns, sprites cropped from one generated progression plate and a bowl cropped from a scene plate, brass tags for locks); traps (multiply cross-fade darkening mid-fade, colour progressions that contradict the message, dead zones, 10% ghosts, recovering a curve from a matplotlib SVG when the source API returned 401 — start/minimum/end matched the original analysis's numbers); an element-wise title card. `lookdev.md` points to it; `narration.md` gained the long-clause split, the subtitle-mux truncation, and linting a grouped view of a voice script.

Code: `lib/opusvid/motion.py` (`pen`, `PrintIn`/`apply_mask`, `InkBlend`, `motes`, `SetPan`/`blur_along_x`, `crop_sprites`, `back_out`/`roll`/`stagger`), numpy/scipy only and backend-agnostic (the film drew with skia). Two fixes: `check_frames.py assemble --srt` muxed the subtitle track in the same command as `-shortest`, so a track ending before the picture cut the film at its last cue (297.1 s came out 293.8 s); subtitles are now muxed in a separate stream-copy pass. `narration.chunk` left a punctuation-free clause of 38 characters as one cue; it now splits such clauses at CJK boundaries, leaving numbers (`30,204`, `10.3%`) and Latin phrases whole. Tests: `tests/test_motion.py` (9 cases), a chunk hard-split case, and an assemble case where the only cue ends at 0.8 s of a 3.0 s film (duration now 3.0 s); all 66 tests pass. `examples/minimal_film` re-run end to end: 90 frames, cue render, `assemble` 3.000 s with a clean decode, and the same with an SRT ending at 0.9 s also 3.000 s.

### 2026-09-27 — films cut to an existing song

New sub-document `music_video.md` (measure the song first, snap beats and sung lines to onsets, one event per sung line, drum-driven glow and pen, one-canvas reveals and continuity, only perceptible cleverness, vector-display persistence drawn with the current camera, nested zooms and video feedback, a per-stroke warp hook, lyrics written with a single-stroke font and placed by measurement, operational traps), routed from `SKILL.md` with a checklist line and a "assert every scripted patch" rule under verification; two agent-operation notes in `blender_handoff.md` (close stdin when backgrounding, stop child processes). New `scripts/music_timing.py` (`separate` / `analyze` / `audit`; stores timings and word counts, never lyric text; lines snapped to phrase starts), `lib/opusvid/placement.py`, `lib/opusvid/strokefont.py`, and `tests/test_music.py` (16 cases on synthetic audio and ink maps; skipped without librosa / Hershey-Fonts); all 56 tests pass. Details in the "full-length music video" section below. Reviewed against the workspace's skill-writing rules: `music_video.md` got a "Done when" list an agent can check without listening, degraded modes (no demucs, no synced lyrics, no librosa, no Hershey-Fonts), and an unobserved bookend suggestion was cut; a precaution that never failed (trails not crossing a hard cut) is labelled as such.

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

## 2026-09-27 — narrated explainers

`narration.md`, `lib/opusvid/narration.py`, `scripts/narration_check.py`,
`check_frames.py assemble --srt`, a `score_cue.py measure` fix, and new sections
in `lookdev.md`, `sprites_text.md`, `SKILL.md` and the audio skill.

Distilled from a two-minute horizontal explainer of a written article (1080p30,
16 narrated lines on a ledger-page design), voiced with two cloned-voice TTS
engines, rewritten once by an external writer, and re-timed from the takes each
time. What cost the most:

**The voice has to be the clock.** Every beat was keyed to a phrase in a take
through recogniser character timestamps. That paid off twice: when the second
voice engine read the same text 15% faster, and when the script was rewritten,
the whole film re-timed from the new takes; only the handful of anchors whose
words the rewrite had moved needed editing, and missing anchors failed loudly.
`lib/opusvid/narration.Narration` reproduces the film's hand-written timeline
exactly (43 anchors and 46 subtitle cues, zero difference).

**Transcribing takes back finds the errors worth fixing.** Most flagged
differences across both engines were homophones or digits. A few were ambiguous
(a syllable that might carry the wrong tone) and were simply voiced again, keeping
the take with the cleanest transcript. One was unambiguous: a polyphonic character
read with the wrong reading; rewriting the text around it fixed it, and
`narration_check.py` shows it as a single merged span.

**All type reads dull.** The first cut was typography and charts only; the viewer
asked for visuals. A generated set of engraving plates, printed onto the page with
a multiply blend, fixed it. Small plates came back tinted and glossy, like icons,
until regenerated as strictly monochrome line work.

**The critic keeps numbers honest.** It caught a mechanism shown two ways that
disagreed (x1.2 in one scene, x1.6 in the next), missing sources on data frames,
and a colour reused across meanings. Three critic rounds, each finding fewer and
smaller problems.

**Two tooling bugs.** `score_cue.py measure` downmixed with `ffmpeg -ac 1`, which
sums correlated stereo at about +3 dB: a mix peaking at -1.5 dBFS measured 1.19
and was reported as clipping. It now takes the peak over every channel. And an SRT
written by rounding the millisecond fraction on its own produced `,1000`;
`narration.srt` works in integer milliseconds and `assemble --srt` rejects the
malformed form.

### 2026-09-27 — narration.md against the meta-skill

Reviewed `narration.md` against the workspace's skill-writing rules (outcomes over
procedure, testable acceptance, degraded modes, no predicted pitfalls). Added a
"Done when" list an agent can check without listening, and a measured fallback for
machines without a recogniser: `chars_by_position` spreads characters evenly over
the measured speech and landed 43 real anchors within a median 0.12 s of the
recogniser timestamps (90th percentile 0.42 s, worst 0.51 s). The motion-blur rule
in `SKILL.md` now says plainly that the strobing it prevents was not observed.


## 2026-09-27 — a full-length music video (`music_video.md`, `music_timing.py`, `placement`, `strokefont`)

A fan music video for an existing song, 3.5 minutes at 1080p24, about 5,100 frames, single-colour vector-display
look, rendered in numpy with bloom and phosphor trails. The whole first minute is one stroke on one canvas that is
revealed as a single picture (an eye) at a structural beat; later sections reuse it through nested zooms, video
feedback, a rewind, a per-stroke scramble and reassembly, and a CRT-off ending. What the passes taught:

- **The first timeline was built from the beat grid and the energy curve and called the first 15 s an intro.** It
  was the densest singing of the song. The viewer's reaction was that the picture kept showing one point turning
  into two. Rebuilding from per-line onsets, one visible event per line, fixed it. The "point and dimension"
  imagery the first cut had put in the opening belonged to a line sung half a minute later.
- **Timing sources were off.** Beats from the tracker sat a median 29 ms late against percussive onsets across the
  whole song. Community synced-lyric times had a quarter of lines more than 150 ms off and a maximum of about
  0.3 s; snapping to vocal-stem onsets moved several visible hits (a merge flash, a hard cut) by about 0.2 s,
  which the viewer had noticed as "small offsets". The synthetic test then exposed a second error: nearest-onset
  snapping picks the second syllable when the timestamp is late; phrase starts fixed it.
- **Glow from a drum envelope**, not the grid; luminance-envelope correlation over the sparsest passage was 0.59.
  Expanding rings on kicks were removed as stock.
- **Concept round.** The viewer rejected a proposal to drive Lissajous figures with the song's real harmony as
  invisible to anyone watching, questioned the return on a physically modelled phosphor, and accepted the
  one-canvas reveal, continuity and syllable-driven pen. 3D passages were deferred once the flat language was
  argued as the song's own and 3D as a reserved event.
- **Persistence trails first ghosted the whole frame** during camera moves because each past sub-frame used its
  own camera; drawing the past with the current camera left only moving ink trailing.
- **Lyrics.** The first placement rule (upper or lower third,
  alternating) put words over heavy elements repeatedly; stacked lines 30-40 px apart read as overlap; faint
  remnants carried by the camera landed on later scenes. Measured placement (five samples per line, 40 positions,
  three sizes), screen anchoring above a 2.5x zoom ratio, a clearing band, box-overlap wiping and no remnants
  brought the worst-decile placement cost from 0.69 to 0.17; the viewer's complaint was overlap, and review was
  done on the worst-cost lines.
- **Tooling.** A scripted `str.replace` that matched nothing silently cost one full render. A heredoc-fed
  multiprocessing preview failed under spawn. A backgrounded coding agent waited on stdin until started with
  `< /dev/null`; killing it left its Blender children running. librosa segfaulted in `beat_track` after an
  interrupted run until the numba cache was cleared.
