# minimal_film — the whole loop in three seconds

A 3 s, 360x640, 30 fps film that exercises every reusable piece once: a glowing
dot drifts across a camera push-in, flashes on the frame it crosses the centre
of the screen, and a title writes itself in one character at a time. The
visuals are deliberately trivial; the point is the plumbing, and it doubles as
a smoke test for `lib/opusvid` and the two CLIs.

| File | Role |
|------|------|
| `shot.py` | The one timeline: sizes, `Events`, the PCHIP camera path, the dot's motion, and the crossing time solved from that motion with `solve_time`. |
| `render.py` | `render_frame(i)` plus `init()` for per-worker resources, handed to `opusvid.runner.run`. Linear canvas, one tone map, then text via `opusvid.typeset`. |
| `make_cue.py` | Writes the cue spec from the same `Events`: a harp note on the solved crossing, one celesta note per title character on its reveal time, a storyboard check on each beat. |

## Run it

From the repository root, with the requirements installed (numpy, scipy,
Pillow, mido; `fluidsynth` and `ffmpeg` on PATH). `out/` is gitignored; every
render goes into a fresh directory.

```bash
OUT=out/minimal_film

python examples/minimal_film/render.py --plan                       # the table, nothing rendered
python examples/minimal_film/render.py --out $OUT/frames_run1       # 90 frames, all cores

# preview = the same render_frame, a subset of frames, a fresh directory
python examples/minimal_film/render.py --out $OUT/preview_run1 --frames 0,35,40:43,89

# frames from this run only; a single dot on a dark sky is dark by design,
# so the tonal-spread default is relaxed deliberately
python scripts/check_frames.py frames $OUT/frames_run1 --expect 90 \
  --since $(cut -d. -f1 $OUT/frames_run1/run_start.txt) --min-spread 0
python scripts/check_frames.py sheet $OUT/frames_run1 --fps 30 \
  --times 0.2,1.0,1.17,1.3,1.6,2.1,2.5,2.9 --out $OUT/sheet.png --width 180 --cols 4

# music from the same timeline; exits non-zero if a storyboard beat is missed
python examples/minimal_film/make_cue.py $OUT/cue.json
python scripts/score_cue.py render $OUT/cue.json --outdir $OUT/audio

# mux + verify (H.264, yuv420p, faststart, explicit fps, then the stream check)
python scripts/check_frames.py assemble $OUT/frames_run1 --fps 30 \
  --audio $OUT/audio/minimal_film.wav --out $OUT/minimal_film.mp4
```

Rendering into `frames_run1` a second time is refused because the directory is
not empty; use `frames_run2`, or `--overwrite` deliberately. Assembling
`preview_run1` fails because frames are missing from the sequence.

`score_cue.py` finds `~/.local/share/soundfonts/MuseScore_General.sf2` first and
falls back to the macOS General MIDI bank; the gain in `make_cue.py` (4.0) was
measured with MuseScore_General (raw peak 0.80). With another bank, re-measure
and pass `--gain`.

## Expected results

Measured on macOS with MuseScore_General.sf2 (one run; your numbers should be
close, not identical):

- `--plan`: the dot crosses the screen centre at 1.170 s; title onsets 1.45 .. 2.05 s.
- `frames`: 90 frames, corners ~15/255, `ok`.
- `score_cue.py render`: 3.0 s, peak 0.579, all three storyboard checks `ok`.
- `assemble`: `h264 360x640 @ 30fps`, `aac`, duration 3.000 s, clean decode, exit 0.

Then open the contact sheet: the checks above cannot tell you whether the flash
lands on the crossing or the title is legible.
