# opus-video-audio-skill

Two agent skills for producing short videos programmatically — the **audio** (music cues that land on specific timecodes) and the **video** (frames rendered from code, then muxed with ffmpeg).

Built from real jobs: several short vertical films, scored and rendered end to end.

## Built for Claude Opus

These skills were written by, and validated with, Claude Opus. They lean on capabilities the pipeline cannot supply by itself: reasoning about framing geometry before rendering, composing a score as explicit note events against a storyboard, and actually reading rendered frames back as images to judge composition. Nothing here has been tested with other models. Another agent can follow the same instructions, but there is no evidence it will reach comparable results, so treat Opus as the supported configuration.

## Scope, honestly stated

**Validated and covered:** music cue composition, local synthesis, loudness normalization, tail trimming, objective audio verification, the generative-music API route with its failure modes — and on the video side, camera/framing geometry, linear compositing and tone mapping, field-dependent exposure, halo and seam artifacts, frame-sequence verification, and ffmpeg assembly.

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
- `skills/procedural-video-frames/SKILL.md` — framing math (angular size → focal length, and the shots that are geometrically impossible), linear compositing with a single tone map, the inverted exposure law for a changing field of view, halo-box and seam artifacts, settling the concept before rendering, glow and sprite artifacts, reflections on water, on-screen text, one shared timeline for picture and music, frame-sequence verification, and ffmpeg assembly with stream checks.
- `scripts/check_frames.py` — three checks: `plan` (is the subject the size you think, and does the shot fit?), `frames` (freshness, exposure, halo boxes; `--seam` adds a midline seam check for split-screen frames), `stream` (ffprobe geometry + full decode). Exits non-zero on failure.

**Shared**
- `docs/working.md` — changelog and the failures these skills were distilled from.

## Requirements

```bash
brew install fluid-synth        # verified with 2.6.1
brew install ffmpeg
pip install mido numpy
```

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

Hand this repository's URL to your coding agent (Claude Code, Codex, Cursor, OpenCode, or similar) and ask it to install the skill. The installing agent should start from the target workspace's `AGENTS.md` or `CLAUDE.md`, follow any routing file it references, and link `skills/video-scoring-audio` into the workspace's skill discovery chain — an index file, or a global skills directory such as `~/.claude/skills/` or `~/.config/opencode/skills/`.

## License

MIT. See `LICENSE`.
