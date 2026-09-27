# opus-video-audio-skill

Two agent skills for producing short videos programmatically — the **audio** (music cues that land on specific timecodes) and the **video** (frames rendered from code, then muxed with ffmpeg).

Built from real jobs: several short vertical films, scored and rendered end to end.

## Built for Claude Opus

These skills were written by, and validated with, Claude Opus. They lean on capabilities the pipeline cannot supply by itself: reasoning about framing geometry before rendering, composing a score as explicit note events against a storyboard, and actually reading rendered frames back as images to judge composition. Nothing here has been tested with other models. Another agent can follow the same instructions, but there is no evidence it will reach comparable results, so treat Opus as the supported configuration.

## Scope, honestly stated

**Validated and covered:** music cue composition, local synthesis, loudness normalization, tail trimming, objective audio verification, the generative-music API route with its failure modes — and on the video side, camera/framing geometry, linear compositing and tone mapping, field-dependent exposure, halo and seam artifacts, look development with an independent critic, per-pixel detail across a large zoom, reflections, a Blender material layer driven through a coding agent, frame-sequence verification, and ffmpeg assembly. Individual suggestions that were not exercised are marked **untested** in the skill text.

**Not covered:** text-to-video generation models, non-linear editors, and colour-managed delivery pipelines. Nothing here was tested against those, so this repository says nothing about them. That gap is deliberate — untested pipeline advice presented as tested is worse than no advice.

## The central problem these skills solve

An agent cannot hear audio, and it is unreliable at judging its own renders. It therefore cannot steer any technique that requires ears to evaluate, and it must never claim a cue "sounds good".

Two consequences drive the whole design:

**Prefer techniques whose output is predictable from the input.** Generative music models do not reliably honor timing instructions — asked for "two isolated notes, then low strings entering at 6 seconds", Google's Lyria returned a cue whose measured RMS envelope was flat and fully loud across the entire span. Writing the same structure as MIDI note events produced an envelope matching the storyboard exactly, because in MIDI the onset you specify is the onset you get.

**Measurement is part of the deliverable.** Duration, peak (clipping), the per-window RMS envelope, and spectral centroid are computable and are the only properties worth asserting. The aesthetic verdict belongs to the human.

On the video side the analogous trap is subtler: the numbers can all be right while the shot is wrong. Coordinates converged correctly through a pass in which two subjects read as a pair instead of one, a subject was bisected by a divider line, and an outline never faded — none of it visible in any metric. So the video skill pairs mechanical checks with an explicit instruction to open the frames.

## What is here

**Audio**
- `skills/video-scoring-audio/SKILL.md` — the MIDI + fluidsynth + soundfont pipeline, the Google Lyria API (endpoint shape, the copyright filter, the timing limitation), ffmpeg normalization and the mandatory tail trim, measurement code, and the variant-fingerprinting discipline.
- `scripts/score_cue.py` — cue spec → MIDI → render → normalize → measure. Exits non-zero on clipping, a duration mismatch, or an envelope that misses a storyboard beat.
- `examples/cue_reveal.json` — an annotated 10-second cue spec with a reveal beat at 6.0s.

**Video**
- `skills/procedural-video-frames/SKILL.md` — the entry file: the rules for every render (framing math in angles and the shots that are geometrically impossible, linear compositing with a single tone map, the inverted exposure law for a changing field of view, verification discipline, ffmpeg assembly), a routing table, and the checklist. It routes to:
  - `lookdev.md` — settling the concept, references and a rubric, look-dev stills, an independent critic on every revision round, composing symbols rather than displaying them, judging detail density at on-screen size.
  - `critic_prompt.md` — a reusable prompt for the independent art-director critic.
  - `detail.md` — crafted detail across a large continuous zoom: SDF per-pixel rendering, level of detail, anti-aliasing a height field, motif layout, growth, and cross-fading between representations.
  - `reflections.md` — reflections on water and mapping extents through the right Jacobian.
  - `sprites_text.md` — glow and sprite artifacts, highlights that read as a different object, seams, on-screen text.
  - `blender_handoff.md` — handing a material-heavy layer to Blender through a coding agent: the contract, elements riding a shared moving surface (and making its height visible to an orthographic camera), and operating the agent.
- `scripts/check_frames.py` — five subcommands: `plan` (is the subject the size you think, and does the shot fit?), `frames` (freshness, exposure, halo boxes; `--seam` adds a midline seam check for split-screen frames, `--ignore-region` excludes a deliberate straight bright element from the step check), `sheet` (a contact sheet of frames at given timestamps, each labelled with its time), `stream` (ffprobe geometry + full decode), and `assemble` (frames + optional audio → H.264/yuv420p/faststart mp4 at an explicit fps, optionally scaled, refusing a sequence with missing frames, then the `stream` check). Exits non-zero on failure.
- `scripts/serve_video.py` — serves only the listed video files over the local network with HTTP Range support, so a film meant for phones can be watched on one. It binds to all interfaces, which exposes the files to everyone on the network while it runs; stop it after the review.

**Reusable code**
- `lib/opusvid/` — a thin toolkit for the plumbing every film rewrote, not a framework: `runner.py` (the CLI — `--out`, `--frames 0,45,80:90`, `--jobs`, `--plan`, `--overwrite` — and worker pool around one `render_frame(i)`, a per-worker `init`, refusal to write into a non-empty output directory, the run start recorded for `check_frames.py frames --since`), `timeline.py` (`smooth`, `ease_in_out`, named `Events`, a PCHIP `CameraPath` with width in log space, `solve_time`, `world_to_pixel`, `export_camera_json` for a Blender layer), `typeset.py` (glyph coverage masks, letter-spaced lines, vertical CJK columns, blending into a float image, timed per-character reveals, a soft dark bed). Not installed: add the repository's `lib/` to `sys.path` (or `PYTHONPATH=lib`) and `import opusvid.timeline`.
- `examples/minimal_film/` — a 3 s, 360x640 film that runs the whole loop (runner, timeline, typeset, a cue generated from the same events, `assemble`); its README lists the commands and the expected results. It is also the smoke test.

**Shared**
- `docs/working.md` — changelog and the failures these skills were distilled from.
- `tests/` — `python -m unittest discover -s tests` covers the contact sheet, `--ignore-region`, the preview server, `assemble`, and `lib/opusvid`.

## Requirements

```bash
brew install fluid-synth        # verified with 2.6.1
brew install ffmpeg
pip install mido numpy pillow scipy
```

Dependencies are split on purpose: `score_cue.py` needs only the standard library, `mido` and `numpy`; `check_frames.py` adds Pillow; `serve_video.py` is standard-library only; `lib/opusvid` uses numpy, scipy and Pillow. Nothing under `scripts/` imports `lib/`.

A soundfont is also needed. macOS ships a General MIDI bank at `/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls` that fluidsynth can read with no download, though it is small and renders quiet. For anything delivered, the MIT-licensed [MuseScore_General.sf2](https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2) (206MB) is substantially better. Gain settings differ between banks and do not transfer — re-measure the peak after switching.

## Quick start

```bash
python3 scripts/score_cue.py init cue.json      # writes an annotated starter spec
# edit the note lists so each "at" value is a timecode from your storyboard
python3 scripts/score_cue.py render cue.json --outdir out
```

The render step prints a report like this, and writes it alongside the audio:

```
   duration 10.0s   peak 0.7359
   spectral centroid 783.5 Hz
   envelope span 26.2 dB (median -20.3 dB)
   [ok ] 1.0s expect quiet: -30.0 dB  (sparse opening, single notes decaying)
   [ok ] 2.5s expect quiet: -39.1 dB
   [ok ] 6.0s expect loud: -12.9 dB  (reveal beat)
   [ok ] 9.5s expect quiet: -31.0 dB  (faded out before the cut)
```

Before offering a human several arrangements to choose between, prove they are actually different:

```bash
python3 scripts/score_cue.py fingerprint out/*.wav
```

This exists because of a real near-miss: four "different instrument" variants generated by patching a source file with `sed` all came back with identical duration, peak and spectral centroid. The substitution had silently failed, and four copies of the same piano were one keystroke from being shipped as an instrument comparison.

## Installing the skill

Hand this repository's URL to your coding agent (Claude Code, Codex, Cursor, OpenCode, or similar) and ask it to install the skill. The installing agent should start from the target workspace's `AGENTS.md` or `CLAUDE.md`, follow any routing file it references, and link `skills/video-scoring-audio` and `skills/procedural-video-frames` into the workspace's skill discovery chain — an index file, or a global skills directory such as `~/.claude/skills/` or `~/.config/opencode/skills/`. Link the directories, not only the `SKILL.md` files: the video skill's sub-documents live next to its entry file.

## License

MIT. See `LICENSE`.
