"""Narration as the master clock: place voice takes, find when a phrase is spoken, cut subtitles.

A narrated film is timed by its voice, not by a beat grid. Synthesize (or record)
one take per line, measure where the speech actually starts and ends, lay the
takes end to end with deliberate gaps, and key every visual beat to the film time
at which a phrase is *spoken* -- taken from speech-recognition character
timestamps of the take, not guessed from character counts::

    from opusvid.narration import Narration, speech_extent, srt

    segs = [{"id": "s01", "say": "...", "gap": 0.35}, ...]        # the script
    ext = {s["id"]: speech_extent(f"takes/{s['id']}.wav") for s in segs}
    chars = json.load(open("takes/chars.json"))                   # narration_check.py output
    N = Narration(segs, ext, chars, lead=0.9, tail=3.6)

    N.at("s04", "942")                  # film time the phrase starts being spoken
    N.at("s04", "dollars", end=True)    # ... or finishes
    N.subtitles()                       # [(start, end, text)], one hard-cut cue per chunk
    open("subs.srt", "w").write(srt(N.subtitles()))

``chars`` maps a segment id to ``[(char, start, end), ...]`` in the take's own
time (seconds from the start of the file). ``scripts/narration_check.py`` writes
exactly this from Whisper word timestamps. Latin words count letter by letter,
so a phrase is matched on its letters with spaces and punctuation removed.

Phrase lookup first searches the recognised text; recognition often writes a
homophone or digits where the script has words, so on a miss it falls back to
the phrase's relative position in the script text. Either way the phrase must
exist in the script, or :meth:`Narration.at` raises -- a renamed anchor fails
loudly instead of silently drifting a visual beat.

Needs numpy; :func:`speech_extent` also needs the ffmpeg binary.
"""
from __future__ import annotations

import re
import subprocess

PUNCT = set("，。；：？！、,.;:?!\"'“”‘’（）()·—-…《》 \t\n")


def norm(s: str) -> str:
    """Lower-case, with punctuation and whitespace removed: the form phrases are matched in."""
    return "".join(c for c in s if c not in PUNCT).lower()


def speech_extent(path, thr_db: float = -40.0, rate: int = 24000, hop: float = 0.01):
    """``(start, end, duration)`` in seconds of the audible speech in a take.

    TTS takes carry a few hundred milliseconds of silence at each end, and it
    differs per take; laying files end to end without trimming makes the gaps
    uneven. Threshold is on a 10 ms RMS envelope."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(rate), "-"], stdout=subprocess.PIPE, check=True).stdout
    x = np.frombuffer(raw, "<f4").astype(np.float64)
    n = max(1, int(rate * hop))
    m = len(x) // n
    if m == 0:
        return 0.0, 0.0, len(x) / rate
    env = np.sqrt(np.mean(x[: m * n].reshape(m, n) ** 2, axis=1))
    idx = np.where(env > 10 ** (thr_db / 20))[0]
    if len(idx) == 0:
        return 0.0, 0.0, len(x) / rate
    return idx[0] * hop, (idx[-1] + 1) * hop, len(x) / rate


def chars_from_words(words):
    """Expand recognizer word timestamps ``[{"word", "start", "end"}, ...]`` to per-character
    ``[(char, start, end), ...]``, spreading each word's span evenly over its characters.
    Punctuation and spaces are dropped."""
    out = []
    for w in words:
        tok = "".join(c for c in str(w["word"]) if c not in PUNCT)
        if not tok:
            continue
        a, b = float(w["start"]), float(w["end"])
        for k, ch in enumerate(tok):
            out.append((ch.lower(), a + (b - a) * k / len(tok), a + (b - a) * (k + 1) / len(tok)))
    return out


def chars_by_position(say: str, extent):
    """Fallback character timestamps when no recogniser is available: the script's
    characters spread evenly over the take's measured speech ``(start, end, duration)``.

    Measured against recogniser timestamps on 43 anchors of a real narration: median
    error 0.12 s, 90th percentile 0.42 s, worst 0.51 s. Good enough for a scene cue,
    visibly off for a per-character reveal. Prefer real timestamps."""
    a, b = float(extent[0]), float(extent[1])
    s = norm(say)
    if not s:
        return []
    step = (b - a) / len(s)
    return [(c, a + k * step, a + (k + 1) * step) for k, c in enumerate(s)]


def chunk(text: str, limit: int = 22, sentence_min: int = 6):
    """Split a line into subtitle chunks at punctuation, at most ~``limit`` characters each.

    Clauses are merged greedily up to the limit; a sentence end (。？！.?!) always
    closes a chunk once it holds more than ``sentence_min`` characters, so one cue
    never straddles two sentences. Trailing commas and full stops are dropped."""
    # CJK punctuation always ends a clause; Latin punctuation only when followed by a
    # space or the end, so "9.42" and "10.2%" stay whole
    parts = re.findall(r"(?:[^，。；：？！,;:?!.]|[,;:?!.](?!\s|$))+(?:[，。；：？！]|[,;:?!.](?=\s|$))?\s*",
                       text)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur += p
        if cur and cur.rstrip()[-1:] in ("。", "？", "！", "?", "!", ".") and len(cur) > sentence_min:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return [c.strip().rstrip("，。；：,;:.") for c in out if c.strip()]


def srt_time(t: float) -> str:
    """``HH:MM:SS,mmm`` from integer milliseconds. Rounding the fraction on its own
    produces ``,1000`` at x.9996 s, which some players reject or misplace."""
    ms = int(round(max(t, 0.0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt(subs) -> str:
    """SRT text from ``[(start, end, text), ...]``."""
    return "".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{s}\n\n"
                   for i, (a, b, s) in enumerate(subs, 1))


class Narration:
    """Takes placed end to end on one film clock.

    ``segments``  ``[{"id", "say", "gap", "sub"?}, ...]`` in order; ``say`` is the
                  text the voice speaks, ``sub`` (optional) the subtitle text when it
                  differs (digits instead of spelled-out numbers, say); ``gap`` is the
                  silence after the line in seconds.
    ``extents``   ``{id: (speech_start, speech_end, file_duration)}`` from :func:`speech_extent`
    ``chars``     ``{id: [(char, start, end), ...]}`` in take time, or ``{id: {"chars": ...}}``
    ``lead``      silence before the first line; ``tail`` hold after the last
    ``pad``       seconds of each take kept before and after its measured speech
    """

    def __init__(self, segments, extents, chars, lead=0.9, tail=3.0, pad=(0.06, 0.12)):
        self.segments = list(segments)
        self.by_id = {s["id"]: s for s in self.segments}
        self.chars = {}
        for k, v in chars.items():
            v = v["chars"] if isinstance(v, dict) else v
            self.chars[k] = [(c.lower(), float(a), float(b)) for c, a, b in v
                             if c not in PUNCT and c.strip()]
        self.place = {}             # id -> (film_start, film_end, trim_in, trim_out)
        cur = lead
        for s in self.segments:
            a, b, n = extents[s["id"]]
            ti, to = max(0.0, a - pad[0]), min(n, b + pad[1])
            self.place[s["id"]] = (cur, cur + (to - ti), ti, to)
            cur += (to - ti) + float(s.get("gap", 0.35))
        last = self.segments[-1]["id"]
        self.duration = self.place[last][1] + tail

    def seg(self, sid):
        """``(film_start, film_end)`` of a line."""
        return self.place[sid][:2]

    def _film(self, sid, t_take):
        t0, _, ti, _ = self.place[sid]
        return t0 + (t_take - ti)

    def _locate(self, sid, phrase):
        ch = self.chars.get(sid, [])
        if not ch:
            raise KeyError(f"no character timestamps for {sid}")
        ph = norm(phrase)
        if not ph:
            raise ValueError("empty phrase")
        joined = "".join(c for c, _, _ in ch)
        k = joined.find(ph)
        if k >= 0:
            return ch, k, k + len(ph) - 1
        say = norm(self.by_id[sid]["say"])
        j = say.find(ph)
        if j < 0:
            raise KeyError(f"phrase {phrase!r} is not in the script of {sid}")
        k0 = min(int(round(j / len(say) * len(ch))), len(ch) - 1)
        k1 = min(max(int(round((j + len(ph)) / len(say) * len(ch))) - 1, k0), len(ch) - 1)
        return ch, k0, k1

    def at(self, sid, phrase, end=False):
        """Film time at which ``phrase`` starts (or, with ``end``, finishes) being spoken."""
        ch, k0, k1 = self._locate(sid, phrase)
        return self._film(sid, ch[k1][2] if end else ch[k0][1])

    def char_times(self, sid, phrase):
        """Film start time of each matched character of ``phrase``, for per-character reveals."""
        ch, k0, k1 = self._locate(sid, phrase)
        n = len(norm(phrase))
        if k1 - k0 + 1 == n:
            return [self._film(sid, ch[k][1]) for k in range(k0, k1 + 1)]
        a, b = self._film(sid, ch[k0][1]), self._film(sid, ch[k1][2])
        return [a + (b - a) * j / n for j in range(n)]

    def subtitles(self, limit=22, skip=(), hold=0.3):
        """Hard-cut cues ``[(start, end, text)]`` for every line not in ``skip``.

        Each chunk starts when its first character is spoken (by its relative position
        in the line, mapped through the recognised characters); the last chunk of a line
        holds ``hold`` seconds into the following gap. Subtitle every line by default:
        viewers expect it even where the same words are on screen."""
        cues = []
        for s in self.segments:
            if s["id"] in skip:
                continue
            chunks = chunk(s.get("sub") or s["say"], limit)
            ch = self.chars.get(s["id"], [])
            t0, t1, ti, _ = self.place[s["id"]]
            total = sum(len(norm(c)) for c in chunks) or 1
            starts, acc = [], 0
            for c in chunks:
                if acc == 0 or not ch:
                    starts.append(t0)
                else:
                    k = min(int(round(acc / total * len(ch))), len(ch) - 1)
                    starts.append(self._film(s["id"], ch[k][1]))
                acc += len(norm(c))
            end = t1 + min(float(s.get("gap", 0.35)), hold)
            for j, c in enumerate(chunks):
                cues.append((starts[j], starts[j + 1] if j + 1 < len(chunks) else end, c))
        return cues
