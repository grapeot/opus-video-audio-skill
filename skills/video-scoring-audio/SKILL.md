---
name: video-scoring-audio
description: >
  Compose, render and objectively verify short music cues and sound effects for
  video, programmatically and without a DAW. Covers the MIDI + fluidsynth +
  soundfont pipeline for music that has to hit specific timecodes, the Google
  Lyria generative-music API (endpoint shape, the copyright filter, and its
  verified inability to honor timing instructions), loudness normalization and
  tail trimming with ffmpeg, and the measurement techniques an agent must use
  because it cannot hear audio. Use this skill whenever a task involves scoring
  or adding music, a soundtrack, a background track, a sting, an SFX bed, or any
  generated audio to a video, animation, reel, short, or slideshow -- and also
  whenever audio needs to line up with a storyboard or specific timestamps, when
  choosing between a generative music API and synthesizing it yourself, when
  normalizing loudness or fixing clipping in a rendered cue, or when comparing
  several instrument or arrangement variants. Reach for it even if the request
  sounds simple ("just add some music to this clip"), because the timing,
  clipping and cannot-hear-it failure modes here are silent and ship broken
  output.
---

# Scoring Audio for Short Video

> Validated: the audio half of a short-video pipeline, on macOS, September 2026.
> For the video half -- rendering frames from code, framing geometry, exposure,
> and ffmpeg assembly -- see the sibling skill `procedural-video-frames`.

## Scope

This skill covers producing a finished audio cue: composing it, rendering it,
normalizing it, and proving it has the properties you claim. It was extracted
from building a 10-second vertical video's music and SFX bed.

The video side lives in `procedural-video-frames` (rendering frames from code,
camera and framing math, compositing, and ffmpeg assembly). Text-to-video
generation models, non-linear editors and colour-managed delivery remain
untested by either skill; if a task needs them, work from primary sources rather
than extrapolating. Guessing and writing it down as if tested is how a skill
becomes actively harmful.

## The one constraint that shapes everything

**You cannot hear audio.** Never tell a user a cue "sounds good", "sounds warm",
or "works nicely" -- you have no access to the only channel where that claim
could be true. What you can do is measure, and then hand the file to the human
for the aesthetic verdict.

This is not a disclaimer to append at the end. It changes the engineering:
because your feedback loop is numeric, you should choose techniques whose output
is *predictable from the input* rather than techniques you would need ears to
steer. That single consideration is why the MIDI route below beats the
generative route for scored-to-picture work, and it is why measurement is built
into the helper script rather than left as an optional last step.

Phrase deliverables like this: "10.00s, peak 0.94 (no clipping), envelope shows
the sparse opening and the swell at 6.0s as specified -- have a listen and tell
me if the instrument is right."

## Decision: generate it, or synthesize it?

Pick by asking whether the music must hit specific timecodes.

**Use MIDI + a soundfont when timing matters.** Scoring to picture means a swell
at 6.0s because that is where the reveal cuts. In MIDI you write the onset time,
velocity and duration of every note, so the thing you specify is the thing you
get. This is the route that worked; it is also free and runs locally.

**Consider a generative API only for atmosphere** where any 10-second window
would do, or when you need timbres a General MIDI bank cannot produce. Expect to
resample and audition rather than to direct.

The deciding evidence: asked for "two isolated notes, then low strings entering
at 6 seconds", Lyria returned a cue whose measured per-second RMS was flat and
fully loud across the whole 0-12s span -- no sparse opening, no entry at 6s. It
took the timbre and tempo hints and discarded the dynamics entirely. **You cannot
command a generative music model to do a specific thing at a specific timestamp.**
You can only generate again and hope. When the same storyboard was written out as
MIDI note events, the envelope came back matching it exactly.

## Route A: MIDI + fluidsynth (the one that works)

### Toolchain

```bash
brew install fluid-synth          # verified: 2.6.1
pip install mido numpy            # mido authors the MIDI, numpy does the measuring
# ffmpeg is also required, for normalization and for decoding during measurement
```

### Soundfonts, and why the gain is not portable

Two banks worth knowing, both verified:

| Bank | Path / source | Size | Gain | Notes |
|---|---|---|---|---|
| macOS built-in GM | `/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls` | 1.9MB | `-g 4.5` | Always present, no download. fluidsynth reads `.dls` fine. Renders **very** quiet -- raw peak 0.015 at default gain -- and sounds cheap. |
| MuseScore General | `https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2` | 206MB | `-g 6` | MIT licensed, much better samples. Worth the download for anything delivered. |

The gain figures are per-bank and do not transfer. Switching banks without
re-measuring peak gives you either a near-silent cue or a clipped one. Re-measure
after any bank change; treat a remembered gain number as a hypothesis.

### Render and post-process

```bash
fluidsynth -ni -g 6 -F out_raw.wav -r 48000 MuseScore_General.sf2 cue.mid

ffmpeg -y -i out_raw.wav \
  -af "afade=t=in:st=0:d=0.3,afade=t=out:st=9:d=1,loudnorm=I=-19:TP=-3:LRA=11" \
  -t 10 out.wav
```

Two things in that command earn their place:

**`-t 10` is mandatory, not tidying.** fluidsynth keeps writing samples until
reverb and note releases decay, so a MIDI file of nominal length 10.00s rendered
to 12.83s in testing (and 13.25s with the larger bank). Hand that to a video edit
and the audio overruns the cut. Trim explicitly to the cue length.

**`loudnorm` targets need verifying, not trusting.** `I=-16` clipped at peak
1.092 on the first attempt. `I=-19:TP=-3:LRA=11` is a reasonable starting point
for a short cue, but the peak is an output to check, not an input you control.

### Composing against a storyboard

The payoff of MIDI is that the storyboard becomes the score. A verified example,
a 10s cue with a reveal at 6s:

- 0 to 5.5s: sparse isolated single notes, low velocity
- 6.0s: low strings enter under a three-note chord -- the reveal beat
- from 9.0s: fade out

Measured envelope confirming it: **-13.8 dB** at the opening attack, **-31.7 dB**
in the gap at 2.5s, **-13.1 dB** at the 6.0s swell, **-40 dB** by 9.5s. That is
the shape that was asked for, verifiable without ears.

A pentatonic scale (the example used D major pentatonic: D E F# A B) is a cheap
safeguard -- it contains no semitone pairs, so an arrangement assembled by
picking note numbers cannot produce a half-step clash you would need ears to
catch.

## Route B: Google Lyria via the Gemini API

Use for atmosphere, not for timing. Two things recommend it over text-to-song
services: it is **instrumental only, no vocals by architecture**, which is what
you want for restrained scoring (everything else is text-to-song, where you are
reduced to asking the prompt not to sing); and it is a first-party API with a
clean licensing chain.

Models verified present on a working key by listing
`https://generativelanguage.googleapis.com/v1beta/models` on 2026-09-25:

| Model | Notes |
|---|---|
| `lyria-3-clip-preview` | 30s clips; cheapest, fine for covering a 10s edit |
| `lyria-3.5` | latest, full length |
| `lyria-3-pro-preview` | pro, full length |
| `lyria-realtime-exp` | streaming, raw PCM |

Request shape:

```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/lyria-3-clip-preview:generateContent" \
  -H "x-goog-api-key: $GEMINI_API_KEY" \
  -H "content-type: application/json" \
  -d '{"contents":[{"parts":[{"text":"<prompt>"}]}]}'
```

Audio comes back base64-encoded at
`candidates[].content.parts[].inlineData.data`, with `mimeType: audio/mpeg`.

### The copyright filter, and how to phrase around it

Naming an ethnic or genre tradition in the prompt gets the request blocked. A
prompt containing "in the East Asian tradition" came back with `finishReason:
"OTHER"` and a `finishMessage` saying the content may contain material
resembling existing copyrighted works -- **no audio, but the call still counts
against your quota.**

The fix is to describe what you want rather than name what it resembles: give
timbre, instrumentation, tempo and structure, and add "original composition".
The same musical intent expressed that way generated successfully.

### Suno

No public API. The developer program has been invite-only since July 2026, and
every third-party "Suno API" on offer is an unofficial reseller. Flag the account
and licensing risk rather than quietly routing a user's work through one.

## Measurement: the four numbers you can actually stand behind

These are computable, so they are the only claims to make. The helper script
computes all of them; the code below is what it does, for when you need it inline.

```python
import subprocess, numpy as np, math

def load(path, rate=48000):
    raw = subprocess.run(
        ["ffmpeg","-v","quiet","-i",path,"-f","f32le","-ac","1","-ar",str(rate),"-"],
        check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype="<f4"), rate

x, sr = load("out.wav")

# 1. duration and 2. peak / clipping
print(len(x)/sr, float(np.max(np.abs(x))))          # peak must stay below 1.0

# 3. RMS envelope -- does the music follow the storyboard?
n = sr // 2                                          # half-second windows
for i in range(0, len(x), n):
    c = x[i:i+n]
    rms = float(np.sqrt(np.mean(c.astype(np.float64)**2)))
    print(round(i/sr,2), round(20*math.log10(rms) if rms > 1e-9 else -120, 1))

# 4. spectral centroid -- a brightness fingerprint, in Hz
win, hop = 4096, 2048
f = np.fft.rfftfreq(win, 1/sr); num = den = 0.0
for i in range(0, len(x)-win, hop):
    m = np.abs(np.fft.rfft(x[i:i+win]*np.hanning(win)))
    num += float((f*m).sum()); den += float(m.sum())
print(round(num/den, 1))
```

**Envelope** is the workhorse: it validates structure against a storyboard. One
caveat when placing checks -- a single struck note's attack window is genuinely
loud even in a sparse passage, so verify "quiet" expectations in the gaps between
notes rather than on an onset, or you will chase a failure that is not there.

**Spectral centroid** fingerprints timbre. Its real job is the next section.

## Verify that variants are actually different

Before presenting several options to a human, prove they differ.

This comes from a near-miss worth internalizing. Four "different instrument"
variants were produced by patching a `program_change` value with `sed`. The
pattern silently failed to match, and all four files came back with byte-identical
duration, peak **0.737** and spectral centroid **722 Hz** -- four copies of the
same piano, one keystroke away from being shipped to a user as an A/B comparison
of four instruments. Worse, the failure was retroactive: it revealed that an
earlier "vibraphone" version handed over for review had also been piano all along,
which means the feedback collected on it was meaningless.

Two habits prevent this class of bug:

1. **Parameterize instead of patching.** Pass the varying value as an argument
   (`compose.py --program 46`) rather than rewriting source text. A failed
   substitution is silent; a missing argument is loud.
2. **Fingerprint every variant and assert they differ** before calling them
   choices. `score_cue.py fingerprint out/*.wav` does this and exits non-zero on
   a collision. Identical fingerprints mean your variation step did nothing.

Five verified-distinct variants of one arrangement, as a sense of the spread:

| Instrument | GM program | peak | centroid |
|---|---|---|---|
| harp | 46 | 0.942 | 642 Hz |
| vibraphone | 11 | 0.948 | 675 Hz |
| piano | 0 | 0.737 | 722 Hz |
| music box | 10 | 0.980 | 814 Hz |
| celesta | 8 | 0.900 | 1114 Hz |

## Why not GarageBand or Logic

They have no headless mode, and their instruments are AudioUnit plugins in
Apple's proprietary format -- not files any synthesizer can load. There is no
path to driving them except a human operating the GUI, which forecloses
automation, reproducibility and batch variant generation.

That is the reason the open SF2 + fluidsynth path matters: it is not merely an
alternative, it is the only one where a script can own the whole
compose-render-measure loop. If a user needs a specific Logic instrument, that is
a handoff to them, not a task to attempt.

## Secrets

Inject API keys into the subprocess that needs them, so the value never enters
your context or the shell history:

```bash
GEMINI_API_KEY="op://vault/item/FIELD" op run -- python generate.py
```

Do not assign secrets to shell variables, and do not use
`op item get --format json` -- it dumps every field of the item, far more than the
one value you need.

## The helper script

`scripts/score_cue.py` runs the whole verified loop: cue spec (JSON) -> MIDI ->
fluidsynth -> ffmpeg fade/loudnorm/trim -> measurement report. It exits non-zero
when the output clips, when the duration does not match the requested cue length,
or when the envelope misses a storyboard beat, so it fails loudly instead of
handing you a broken cue.

```bash
python3 scripts/score_cue.py init cue.json            # starter spec, annotated
# edit the note lists so each 'at' is a storyboard timecode
python3 scripts/score_cue.py render cue.json --outdir out
python3 scripts/score_cue.py measure existing.wav --storyboard cue.json
python3 scripts/score_cue.py fingerprint out/*.wav    # before offering choices
```

Generate `cue.json` from the picture's own timeline module instead of typing
timecodes: a script that imports the same beat times the renderer uses and writes
the notes. In the films built with this, one harp note per date change, one
rising note per character of a closing greeting, and a chord on the frame the
moon became full were all placed this way, and later timing changes to the
picture moved the music with them.

When a cue has one intended peak, check that no earlier accent competes with it.
A single harp note marking a moonrise measured -13.2 dB against the chord's
-12.0 dB in the envelope -- nearly as loud as the climax -- and was lowered
until the chord was clearly the peak.

The spec keeps `bpm` at 60 so one beat equals one second and every `at` value is
literally a timecode you can read off a storyboard. Each note carries `at`, `note`
(MIDI number), `vel` and `dur`, plus an optional `why` to record which beat of the
picture it serves -- useful when a human asks why a note is where it is.
