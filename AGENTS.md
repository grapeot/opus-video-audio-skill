# AGENTS.md — agent operating rules for this repository

## Role

Public repository. Contains an agent-facing skill and a tested helper CLI for producing the **audio** of short videos: composing timed music cues, rendering them locally, normalizing them, and verifying them objectively. Working language: English.

## Exact commands

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install mido numpy
brew install fluid-synth ffmpeg

# the full loop
python scripts/score_cue.py init cue.json
python scripts/score_cue.py render cue.json --outdir out
python scripts/score_cue.py measure out/cue.wav --storyboard cue.json
python scripts/score_cue.py fingerprint out/*.wav

# smoke test against the checked-in example (must exit 0)
python scripts/score_cue.py render examples/cue_reveal.json --outdir /tmp/score_cue_smoke
```

## Structure

- `skills/video-scoring-audio/SKILL.md` — the skill; the primary artifact of this repo
- `scripts/score_cue.py` — compose → render → normalize → verify CLI
- `examples/cue_reveal.json` — annotated 10s cue spec with a reveal beat at 6.0s
- `docs/working.md` — changelog and lessons learned

## Invariants

- **Scope discipline.** Only the audio half of the video pipeline is validated. Do not add video generation, editing, muxing, or codec guidance unless it has been tested in this repository, and mark anything speculative as such. Untested pipeline advice presented as tested is the main way this skill could become harmful.
- **Every claim in the skill is measured or cited.** No assertion about audio quality, no remembered gain or loudness numbers. If a figure changes, re-measure and update it with the new measurement.
- **`score_cue.py` must exit non-zero on clipping, a duration mismatch, or a missed storyboard beat.** The script's value is that it fails loudly; silent success on broken output defeats the purpose.
- Never claim a cue sounds good. The script's report ends by saying so explicitly — keep that line.
- Standard-library plus `mido` and `numpy` only. `fluidsynth` and `ffmpeg` are external binaries invoked as subprocesses.
- Run the smoke test above after touching `score_cue.py`.
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

- Do not commit rendered audio, soundfonts, or `out/` directories. They are large and are reproducible from the specs.
- Version control: only commit when explicitly asked; small, independently reviewable commits.
