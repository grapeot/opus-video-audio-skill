# Narrated films: the voice is the clock

Part of the `procedural-video-frames` skill. Read this when a film has a voice-over:
an explainer, a narrated data story, a walkthrough. It covers timing picture to
speech, checking takes you cannot hear, subtitles, and rewriting a script without
breaking the sync.

> Validated on a two-minute horizontal narrated explainer (1080p30, 16 lines,
> about 45 subtitle cues), voiced twice with two different cloned-voice TTS
> engines and re-timed each time from the takes alone, and on a five-minute one
> (23 lines, about 110 cues, one cloned voice, two lines re-voiced after the
> transcript check). Code: `lib/opusvid/narration.py`,
> `scripts/narration_check.py`, `check_frames.py assemble --srt`.

## Done when

A narrated film is finished only when all of these hold; each can be checked
without having heard it:

- Every line has a take whose transcript (`narration_check.py`) was compared with
  its script, and every reported difference was judged as recogniser noise (same
  sound) or fixed (a retake or reworded line) -- recorded as a short list.
- Every visual beat that illustrates a word is placed with `Narration.at` on a
  phrase that exists in that line's script; a full render with the final takes
  raises no missing-anchor error.
- The film's duration comes from the placed takes plus lead and tail, and matches
  the target within the tolerance the brief set.
- Every line is subtitled; the SRT passes `check_frames.py assemble --srt`, and the
  mp4 has video, audio and subtitle streams with a clean decode.
- Voice and music loudness are measured (see the audio skill), and the deliverable
  message says a human still has to listen for the delivery.

## Order of work: script, takes, then picture

A narrated film is timed by its voice. Write the script, synthesize or record the
takes, measure them, and only then lay out the picture. Timing a picture to an
estimated reading speed and fitting the voice afterwards wastes a render pass
every time a line is rewritten.

**One take per line, one line per picture beat.** A retake then replaces one
file, and the picture beat it drives moves with it. Lay takes end to end with
deliberate gaps (about 0.35 s inside a scene, 0.5-0.9 s at a scene change or
before a line that should land), not with whatever silence the files carry: TTS
takes start and end with a few hundred milliseconds of silence that differ per
take, so trim each take to its measured speech (`speech_extent`) plus a small pad.

**Measure the speaking rate before budgeting the script.** Rates differ a lot
between engines and settings: the same 598-character Chinese script took 121 s
of speech from one engine (asked for a medium pace) and 106 s from another, a
15% difference. Voice one line, measure characters per second, then set the
script's length from the target duration. When the film runs long, shorten the
script rather than time-stretching the voice.

**No recogniser available.** `chars_by_position(say, extent)` spreads a line's
characters evenly over its measured speech. On a real narration it put 43 anchors
within a median 0.12 s of the recogniser timestamps (90th percentile 0.42 s, worst
0.51 s): fine for a scene cue, visibly early or late for a per-character reveal.
Takes then go unchecked, so say so in the delivery.

## Key every visual beat to a spoken phrase

Each visual event should land on the word it illustrates. Get per-character
timestamps for each take from a speech recogniser (`narration_check.py --out`
writes them from Whisper word timestamps), and ask for the film time of a phrase
rather than computing it from character counts:

```python
N = Narration(segments, extents, chars, lead=0.9, tail=3.6)
t_count = N.at("s04", "just from these cases")     # counter starts rolling
t_land  = N.at("s04", "dollars", end=True)          # ... and lands on the last word
```

Rules that kept the sync honest across rewrites and a change of voice:

- **Anchors must exist in the script, and a missing one must fail.** The recogniser
  often writes a homophone or digits where the script has words; the lookup then
  falls back to the phrase's position in the script text, which is close enough
  for a visual cue. A phrase that is not in the script at all raises, so a
  rewritten line cannot silently drift its beat.
- **Keep the anchor list derivable from the code.** When the script is rewritten,
  extract every anchor phrase the renderer and the mix use, hand them to the
  writer as must-include phrases per line, and check the new script mechanically
  (every anchor present, every line within its character cap) before voicing it.
  A few anchors will still need moving by hand where the new wording changes
  the order of ideas inside a line; renders fail on a missing anchor, so the
  first preview finds them.
- **Derive every other time from the same clock.** Sound effects, the music's
  scene changes, stacked-object arrival times: compute them from the narration
  object, never read them off a preview (the shared-timeline rule in `SKILL.md`).

## Checking takes you cannot hear

An agent cannot listen to a take, so transcribe it back and compare it with the
script (`narration_check.py`). The comparison is a review aid, not a verdict:

- **Same sound, different characters is recogniser noise.** Homophones, digits
  for spelled-out numbers, a foreign name spelled oddly: ignore them. An English
  word transcribed strangely may still be pronounced correctly.
- **Different sound is a real error.** In practice this was a polyphonic
  character read with the wrong reading (a Chinese 重 read as *zhòng* instead of
  *chóng*, which the recogniser heard as a different word). Fix it by rewriting
  the text around the character, then voice it again and re-check.
- **Voice two or three takes of a flagged line and keep the one whose transcript
  is cleanest.** Takes of the same text vary; transcripts of the variants were
  enough to choose between them.
- **The same difference in every take is the recogniser, not the voice.** A line
  containing 三分之一 transcribed as "1 3分之一" in three separate takes; the TTS
  varies between takes and the recogniser's number formatting does not, so the
  identical diff marked recogniser noise and no further retakes were needed.
- A clean transcript still does not mean the delivery is right. Say so, and have
  a human listen before the voice ships.

Keep two texts per line: what the voice says (numbers spelled out as they should
be read) and what the subtitle shows (digits, units, proper names as written).

## Subtitles

- **Subtitle every line by default.** Skipping a line because the same words are
  on screen (a title card, an on-screen quote) reads as a gap to viewers; the
  request after such a cut was simply "include subtitles".
- **Chunk at punctuation, at most about 22 CJK characters, never across a sentence
  end,** and hard-cut between chunks (the text rule in `sprites_text.md`). Each
  chunk starts when its first character is spoken. Keep decimals and percentages
  whole when splitting. A clause with no punctuation can still run past the limit
  (38 characters on one line in practice); `narration.chunk` now splits it at CJK
  boundaries, leaving numbers and Latin phrases whole.
- **List the short cues after cutting.** A forced split can still separate a
  date from its unit: a subtitle text without a comma came out as "这是 SDO 卫星在
  2024" followed by a 0.9 s cue "年 5 月 10 日". Print every cue shorter than about
  1.3 s and fix the bad ones by adding commas to the subtitle text (`sub`) only;
  the voice text and its takes stay as they are.
- **Burn them in on a fixed band, composited after any motion blur,** so they stay
  sharp during camera moves and page turns; give them a soft bed so they read
  over detailed plates.
- **Also ship a soft track and an SRT** for platforms that take subtitle files:
  `check_frames.py assemble --srt subs.srt --srt-lang chi` validates the file and
  muxes it as `mov_text`. Write SRT times from integer milliseconds: formatting
  the fraction separately produced `00:01:41,1000` at 101.9996 s. Mux the soft
  track in a separate stream-copy pass (`assemble` does): in one ffmpeg command with
  `-shortest`, a subtitle track whose last cue ends before the picture cut a 297 s
  film to 293.8 s, at the last cue's end.

## Rewriting a script without breaking the picture

When the script is rewritten by another model or a human after the picture exists,
give the writer a packet, not the conversation: the facts it may use with their
sources and strength, a per-line table (what is on screen, what the line must say,
its anchor phrases, a character cap), and a description of the voice ("explaining
something you figured out to a colleague, short sentences for judgements, longer
ones for causes"). Then check, in this order and in separate contexts:

1. Mechanical: anchors and character caps (a script, not a reading).
2. Facts: compare the rewrite against the previous draft and the sources, listing
   every drift in numbers, names, attribution and strength of claims.
3. A cold read by a reader who sees only the narration: can they restate each line
   in plain words after hearing it once, and does the narrator sound like a peer or
   a lecturer? This caught a line that listed four terms the film never explains;
   the fix was upstream (the line's brief asked for a list), not in the wording.

If the writing workflow also runs a prose linter built for articles, it flags every
voice line as a one-sentence paragraph and asks for section headings; lint a view of
the script grouped into acts and paragraphs rather than loosening the linter.

## Mixing the voice with music

Keep the music well under the voice and duck it further while someone speaks; the
audio skill (`video-scoring-audio`) has the numbers and the loudness procedure.
