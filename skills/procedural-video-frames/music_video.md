# Films cut to an existing song

Part of the `procedural-video-frames` skill. Read this when the picture must follow
a song you did not compose: a music video, a lyric video, a piece cut to a track.
It covers measuring the song, what makes sync visible, what makes such a film
feel remarkable rather than merely correct, a vector-display look, nested and
self-referential shots, and lyrics that belong to the picture.

> Validated on one full-length music video (about 3.5 minutes, 1080p24, roughly
> 5,000 frames, a single-colour vector-display look), rendered end to end several
> times with human review between passes. Code: `scripts/music_timing.py`,
> `lib/opusvid/placement.py`, `lib/opusvid/strokefont.py`.

## Done when

A film cut to a song is finished only when all of these hold; each can be checked
without having heard it:

- `music_timing.py audit` has been run on the timing the renderer imports, and its
  beat offset and line offsets were read. Sections are called instrumental only
  where `audit` lists a gap between sung lines.
- Every sung line has a visible event whose first frame is within one frame after
  the line's snapped onset (sample the frames at the line times on a contact
  sheet). Picture that changes on a beat uses snapped beats or kicks, not the raw
  tracker output.
- Over the sparsest passage, the correlation between mean frame luminance and the
  drum envelope is clearly positive (about 0.6 was convincing; near zero means the
  pulse is not visible).
- If there is on-screen lyric text: it was read from a file the user supplied, no
  lyric text is stored in the timing JSON or committed anywhere, and the lines with
  the highest placement cost were looked at on a contact sheet mid-life.
- The usual stream checks of `SKILL.md` pass on the muxed file.

## Measure the song before drawing anything

The song is the clock, as the voice is in `narration.md`. Separate the stems,
measure them, and lay out the picture from the measurements:

```bash
python scripts/music_timing.py separate song.m4a --out stems/        # demucs, vocals / no_vocals
python scripts/music_timing.py analyze song.m4a --fps 24 --out timing.json \
    --vocals stems/htdemucs/song/vocals.wav --accomp stems/htdemucs/song/no_vocals.wav --lrc lines.lrc
python scripts/music_timing.py audit timing.json
```

- **Find the voice before naming any section.** Energy curves and beat grids do
  not tell you where the singing is. A section that looks like an intro on the
  energy curve can be the densest singing in the song; filling it with one slow
  idea reads as the film not listening. The `audit` output lists the long gaps
  between sung lines: those, and only those, are the instrumental passages.
- **One visible event per sung line, at the moment it is sung.** Lyrics run at
  about one line every two seconds; the picture has to keep that rate where the
  voice does. An image the lyric names belongs where it is sung, not in the
  opening because it seemed like a good start.
- **Every timing source is off; snap it to the audio.** A beat tracker's beats
  can sit consistently tens of milliseconds late; snap each to the nearest
  percussive onset (fall back to the median offset). Community synced-lyric
  timestamps can be off by several hundred milliseconds, which is several
  frames and visible; snap each line to a vocal onset of the separated vocal
  stem. `analyze` does both and `audit` reports how far the sources were off.
- **Snap a line to where a phrase begins, not to the nearest onset.** Inside a
  densely sung line the second syllable can be nearer to a late timestamp than
  the first. Prefer onsets preceded by a short quiet stretch of the vocal stem
  (`phrase_starts`), and fall back to the nearest onset only when there is none.
- **Lyric text is usually copyrighted.** Store timings and word counts, not the
  text (`analyze` discards it). If lyrics appear on screen, the renderer reads
  them from a file the user supplies; do not fetch or transcribe them yourself.

**Degraded modes.** Without demucs there is no vocal stem: `analyze` still snaps
beats to percussive onsets of the mix and builds the drum envelope, but sung
lines stay at their LRC times (it warns), so check the line hits on a contact
sheet and nudge by hand. Without any synced lyrics, the vocal stem's onsets and
the long quiet gaps between them still show where lines start and where the
instrumental passages are. Without librosa, nothing here runs; time from a
hand-tapped list and say so in the delivery. Without Hershey-Fonts, draw text as
glyph masks with `typeset` (it no longer shares the pen's strokes).

## Make the beat visible

- **Drive glow from a drum envelope, not from the beat grid.** A percussive
  envelope with an instant attack and a release of about 0.14 s, sampled per
  frame (`env` in `timing.json`), scaling bloom and halo reads as the picture
  breathing with the drums; heavy hits flare harder than light ones, which a
  uniform grid cannot do. A hit lands on the first frame after its onset.
- **Let the music move the pen.** Where something is being drawn, advance it by
  the cumulative drum envelope in instrumental passages (it lurches on each hit)
  and by syllable onsets of the vocal stem where there is singing (`vocal.rate`):
  the song reads as drawing the picture. Sparse passages, where little is on
  screen, need this most.
- **Check it numerically.** The correlation between mean frame luminance and the
  envelope over a sparse passage should be clearly positive (about 0.6 was
  convincing); near zero means the glow is not visible at that exposure.
- **Generic visualiser devices read as stock.** Rings expanding from the centre
  on every kick were dropped once the drawing itself pulsed.

## What makes it feel remarkable

Illustrating each line literally, however polished, reads as a good explainer.
What made viewers react came from three things:

- **Recontextualisation.** Everything seen so far turns out to be part of
  something else. The strongest version: every scene of a section is drawn on
  one large canvas, the camera stays tight on the pen so the whole is never
  seen, and a single pull-back on a structural beat reveals that the scenes
  compose one picture. Plan it backwards from the final picture: place each
  scene where its lines become part of that picture, at comparable scales (a
  scene nested at a tiny scale inside another cannot also be a visible part of
  a picture that contains the outer one).
- **Impossible continuity.** One stroke from start to finish. A working rule:
  every line comes from an earlier line -- it splits, bends, merges or
  unrolls -- and nothing fades in from nowhere. Instruments (axes, graticules,
  timelines) may fade; the drawing may not.
- **Sync that feels inevitable** (previous section).

Two traps:

- **Cleverness nobody can see is self-indulgence.** Geometry driven by the true
  signal of the song, or colours that carry a private meaning, cost effort and
  are invisible. Keep only the perceptible part (a shape that changes exactly
  when the chord changes needs chord times, not pitch tracking). This is the
  perceptibility rule of `lookdev.md` applied to concepts.
- **Hold the most expensive register back.** When a film mixes a flat language
  with 3D or photoreal passages, make the rich register an event, not the
  baseline; opening with it leaves nothing to escalate to.

## A vector-display look

- **Constant screen-space line width.** Sample each polyline by arc length in
  screen space (about 0.6 px) and splat the samples bilinearly. At extreme
  zooms, sample coarsely first (every ~16 px) and refine only the stretches
  that are on screen, or long remnant lines cost seconds per frame.
- **The beam dwells on corners.** Brighten vertices where the direction turns
  and the ends of open strokes; a moving pen head gets a flare.
- **Phosphor persistence: redraw the past with the current camera.** Draw the
  scene again at two or three earlier sub-frame times and take the maximum with
  decaying weights (about 0.4, 0.16, 0.06). Drawing each past time with its own
  camera ghosts the whole frame whenever the camera moves; with the current
  camera, static ink coincides and only moving ink trails, as on a real screen.
  The film also skipped trail sub-frames that fell in a different scene, so a
  hard cut never smears; that was a precaution, not an observed failure.

## Nested and self-referential shots

- **Compose views.** A child coordinate system `parent = o + s * local` that
  composes with its parent's view lets one drawing function place a scene
  anywhere and at any scale, including inside itself. An infinite zoom is the
  same drawing at scales `R^-k`; draw only the levels that are between a few and
  a few hundred thousand pixels wide, and a simplified version below a few
  hundred.
- **Video feedback is recursion for free.** A tile that shows the previous output
  frame contains itself. It forces those frames to render sequentially; frames
  that show earlier output (thumbnails of the film's own past) need those frames
  to exist first. Order the passes: parallel up to the feedback, sequential
  through it, parallel after.
- **One screen-space warp hook, keyed per stroke.** A function applied to every
  stroke's screen coordinates, keyed by a stable hash of the stroke, turns one
  finished drawing into a glitch, a scramble, an explosion, a reassembly (each
  stroke snapping back on its own hit) and a display switching off (squash to a
  line, shrink to a point) without new geometry.

## Lyrics as part of the picture

The text is supplied by the user (see above). Making it belong to the picture:

- **Write it with the same pen.** A single-stroke vector font
  (`strokefont.layout`, Hershey fonts) draws letters as strokes, so text shares
  the line, glow and trails of everything else. Start each word on its vocal
  onset (`strokefont.word_times`, `reveal`).
- **Measure where it goes.** Render the scene without text at several moments of
  the line's life (five worked), blur the ink by the glow radius, and score
  candidate positions and sizes by covered ink, by how much of the box the
  camera carries off screen, and by collisions with other text
  (`placement.choose`). A fixed "lower third" put text on top of heavy elements
  over and over. After measuring, the worst decile of lines improved about
  fourfold.
- **Anchor to the screen when the camera zooms a lot.** World-anchored text
  written during a fast zoom shrinks to nothing within a second; above a zoom
  ratio of about 2.5 during the line's life, hold it on the screen.
- **Where nothing is clean, clear a band.** Darken a feathered band under the
  words (`placement.clearing_band`), like the beam wiping a strip before
  writing.
- **One line per place.** A newer line whose box, grown by a generous margin,
  meets an older one wipes the older; boxes 30-40 px apart already read as a
  stacked block.
- **No lingering remnants.** Leaving sung lines as faint ink looked organic
  until the camera carried them into later scenes on top of heavy elements.
  Fade them after they are sung. A deliberate exception can work: at a reveal,
  the section's words re-light faintly as engraving on the revealed picture.
- **Review the worst lines, not a random sample.** Contact-sheet the lines with
  the highest placement cost, mid-life.

## Operational traps

- **Assert every scripted patch.** A search-and-replace that matches nothing
  changes nothing and reports success; one such no-op cost a full render pass.
  Check the match count before re-rendering.
- **Run multiprocessing renderers from a file.** A script fed through a heredoc
  or `python -` cannot be re-imported by spawned workers and fails.
- **librosa segfaulting in `beat_track`** after an interrupted run can be a
  corrupted numba cache: delete the `*.nbi` / `*.nbc` files under librosa's
  `__pycache__`, or set `NUMBA_CACHE_DIR` to a fresh directory.
- Dispatching a coding agent headless (for a Blender layer, for instance): see
  `blender_handoff.md`.
