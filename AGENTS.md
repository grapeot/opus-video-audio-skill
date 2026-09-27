# AGENTS.md — agent operating rules for this repository

## Role

Repository `opus-video-audio-skill`, designed for and validated with Claude Opus. Contains two agent-facing skills and tested helper CLIs for producing short videos programmatically: the **audio** (composing timed music cues, rendering, normalizing, and verifying them objectively) and the **video** (frames rendered from code, verified, and muxed with ffmpeg). Working language: English.

## Exact commands

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install mido numpy pillow scipy
brew install fluid-synth ffmpeg

# the full loop
python scripts/score_cue.py init cue.json
python scripts/score_cue.py render cue.json --outdir out
python scripts/score_cue.py measure out/cue.wav --storyboard cue.json
python scripts/score_cue.py fingerprint out/*.wav

# smoke test against the checked-in example (must exit 0)
python scripts/score_cue.py render examples/cue_reveal.json --outdir /tmp/score_cue_smoke

# video helpers
python scripts/check_frames.py frames frames/ --expect 240 [--ignore-region x0,y0,x1,y1]
python scripts/check_frames.py sheet frames/ --fps 24 --times 0.5,2,4,9.5 --out sheet.png
python scripts/check_frames.py assemble frames/ --fps 24 --audio out/cue.wav --out out.mp4 [--scale 360x640]
python scripts/check_frames.py assemble frames/ --fps 30 --audio mix.wav --srt subs.srt --srt-lang chi --out out.mp4
python scripts/serve_video.py out.mp4 --port 8765     # LAN preview; stop it after review
python scripts/narration_check.py script.json takes/ --out takes/chars.json   # needs mlx-whisper
python scripts/music_timing.py separate song.m4a --out stems/                 # needs demucs
python scripts/music_timing.py analyze song.m4a --fps 24 --out timing.json --vocals V.wav --accomp A.wav [--lrc lines.lrc]
python scripts/music_timing.py audit timing.json                              # needs librosa

# tests for check_frames.py, serve_video.py and lib/opusvid (must pass)
python -m unittest discover -s tests -v

# end-to-end smoke test of lib/opusvid + both CLIs: run the commands in
# examples/minimal_film/README.md (outputs under out/, which is gitignored)
```

## Structure

- `skills/video-scoring-audio/SKILL.md` — the audio skill
- `skills/procedural-video-frames/SKILL.md` — the video skill's entry: core rules for every render, a routing table, the checklist
  - `lookdev.md` — concept, references and rubric, look-dev stills, the independent critic loop, composing symbols, density at on-screen size
  - `critic_prompt.md` — prompt template for the independent art-director critic
  - `detail.md` — SDF per-pixel detail across a large zoom, level of detail, anti-aliasing, motif layout, growth and cross-fades
  - `reflections.md` — water/glitter reflections and mapping extents through the right Jacobian
  - `sprites_text.md` — glows and sprites, highlights that read as the wrong object, seams, on-screen text
  - `blender_handoff.md` — handing a material layer to Blender through a coding agent, the contract, elements riding a shared moving surface
  - `narration.md` — voice-over films: takes before picture, beats keyed to spoken phrases, transcription checks, subtitles, script rewrites
  - `music_video.md` — films cut to an existing song: measuring and snapping timing, visible beat, one-canvas reveals, vector-display look, nested zooms, video feedback, lyrics placed by measurement
- `scripts/score_cue.py` — compose → render → normalize → verify CLI
- `scripts/check_frames.py` — plan / frames / sheet / stream verification CLI, plus `assemble` (mux + stream check)
- `scripts/serve_video.py` — serve only the listed video files on the LAN, with HTTP Range, for phone preview
- `scripts/narration_check.py` — transcribe voice takes, diff them against the script, write per-character timestamps
- `scripts/music_timing.py` — separate a song's stems, snap beats and sung lines to onsets, per-frame drum envelope, vocal syllable rate; stores timings and word counts, never lyric text
- `lib/opusvid/` — reusable film plumbing, imported by adding `lib/` to `sys.path` (not installed)
  - `runner.py` — frame-render CLI + worker pool around `render_frame(i)`; fresh output dirs; run start for `--since`
  - `timeline.py` — easing, `Events`, PCHIP `CameraPath` (log-space width), `solve_time`, `world_to_pixel`, `export_camera_json`
  - `typeset.py` — glyph masks, letter-spaced lines, vertical columns, float blending, timed reveals, soft bed
  - `narration.py` — `speech_extent`, `Narration` (placement, `at`, `char_times`, `subtitles`), `chunk`, `srt`, `chars_by_position` (no-recogniser fallback)
  - `placement.py` — `ink_integral`, `box_ink`, `candidates`, `choose` (text placed where measured ink is lowest, screen anchoring on big zooms), `clearing_band`
  - `strokefont.py` — Hershey single-stroke text: `layout`, `word_times`, `reveal`, `bbox`
- `tests/test_scripts.py` — unittest coverage for `check_frames.py sheet`, `--ignore-region`, and `serve_video.py`
- `tests/test_opusvid.py` — unittest coverage for `lib/opusvid` and `check_frames.py assemble` (including `--srt`)
- `tests/test_music.py` — `music_timing.py` on synthetic audio (beat and line snapping, envelope, CLI), `placement`, `strokefont`; skipped without librosa / Hershey-Fonts
- `tests/test_narration.py` — `lib/opusvid/narration`, `narration_check.py`'s pure helpers, and `score_cue.py measure` on correlated stereo
- `examples/cue_reveal.json` — annotated 10s cue spec with a reveal beat at 6.0s
- `examples/minimal_film/` — 3 s, 360x640 end-to-end example and smoke test (shared timeline → frames → cue → mp4)
- `docs/working.md` — changelog and lessons learned

## Invariants

- **Scope discipline.** Only what has been exercised on a real job is validated: the audio half and the frame-rendering half. Do not add text-to-video generation, NLE editing, or colour-managed delivery guidance unless it has been tested in this repository, and mark anything speculative as such. Untested pipeline advice presented as tested is the main way this skill could become harmful.
- **Every claim in the skill is measured or cited.** No assertion about audio quality, no remembered gain or loudness numbers. If a figure changes, re-measure and update it with the new measurement.
- **`score_cue.py` must exit non-zero on clipping, a duration mismatch, or a missed storyboard beat.** The script's value is that it fails loudly; silent success on broken output defeats the purpose.
- Never claim a cue sounds good. The script's report ends by saying so explicitly — keep that line.
- Dependencies are split and stay split: `score_cue.py` is standard-library plus `mido` and `numpy` only; `check_frames.py` adds Pillow; `serve_video.py` is standard-library only; `narration_check.py` is standard-library plus `mlx-whisper`, imported only when transcribing; `lib/opusvid` may use numpy, scipy and Pillow. Scripts under `scripts/` never import `lib/`. `fluidsynth` and `ffmpeg` are external binaries invoked as subprocesses.
- `lib/opusvid` stays a thin toolkit: only code that real films rewrote nearly identically belongs there. Domain content (a particular subject, its shading, its layout) stays in the film's own script. Font paths are always parameters; never hard-require a font file.
- Run the smoke test above after touching `score_cue.py`, the unit tests after touching `check_frames.py`, `serve_video.py` or `lib/opusvid`, and the `examples/minimal_film` commands after touching `lib/opusvid` or `check_frames.py assemble`.
- Skill text states reusable rules, not a diary of the films they came from: a general rule, a real-world sanity check where possible, and at most a half-sentence of example. Anything not exercised on a real job is marked **untested**.
- Keep `procedural-video-frames/SKILL.md` short enough to read in one pass: core rules plus routing. New topic-specific material goes into the matching sub-document, and the routing table is updated when a sub-document's scope changes.
- This repository's default branch is `master`.

## Public-repo hygiene

- No real API keys, emails, phone numbers, internal paths, server addresses, or 1Password item references in any tracked file. The skill documents the `op run` pattern using a placeholder reference (`op://vault/item/FIELD`) — keep it generic.
- Run a privacy scan before pushing and treat zero matches as the bar (the pattern uses the `[U]sers`-style bracket trick so the scan does not match its own command text):

  ```bash
  rg -n --glob '!.venv' \
    "o[p]://|/[U]sers/[a-z]|AIza[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{16,}|BEGIN [A-Z ]*PRIVATE KEY|grapeot[@]" .
  ```

  The only expected hit is the placeholder `op://vault/item/FIELD` in the skill's
  secrets section. Anything else is a finding.

- Do not commit rendered audio or video, frames, contact sheets, soundfonts, or `out/` directories. They are large and are reproducible from the specs.
- Version control: only commit when explicitly asked; small, independently reviewable commits.
