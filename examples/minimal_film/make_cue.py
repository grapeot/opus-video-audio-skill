"""Write the minimal film's cue spec from the same timeline the picture uses.

    python examples/minimal_film/make_cue.py out/minimal_film/cue.json
    python scripts/score_cue.py render out/minimal_film/cue.json --outdir out/minimal_film/audio

A harp note lands on the solved moment the dot crosses the centre (the frame
that flashes), strings swell under it, and each title character gets one rising
celesta note on the time it starts to write.
"""
import json
import sys
from pathlib import Path

from shot import DUR, E, TITLE
from opusvid.typeset import char_onsets

PENTA = [74, 76, 78, 81, 83, 86, 88]        # D major pentatonic, one per character


def build():
    x = E.cross
    harp = [{"at": 0.10, "note": 50, "vel": 34, "dur": 1.2, "why": "the dot in the dark"},
            {"at": round(x, 3), "note": 62, "vel": 60, "dur": 2.0, "why": "dot crosses centre"},
            {"at": round(x + 0.03, 3), "note": 69, "vel": 54, "dur": 2.0}]
    strings = [{"at": round(x, 3), "note": n, "vel": v, "dur": DUR - x, "why": "swell" if k == 0 else ""}
               for k, (n, v) in enumerate([(38, 44), (45, 38), (54, 32)])]
    celesta = [{"at": round(t, 3), "note": n, "vel": 46 + 2 * j, "dur": 1.0, "why": TITLE[j]}
               for j, (t, n) in enumerate(zip(char_onsets(len(TITLE), E.title, E.title_step), PENTA))]
    fade0, fade1 = E.span("fade")
    return {
        "name": "minimal_film",
        "duration": DUR,
        "bpm": 60,
        "tracks": [
            {"name": "harp", "program": 46, "channel": 0, "reverb": 100, "notes": harp},
            {"name": "strings", "program": 48, "channel": 1, "reverb": 120, "notes": strings},
            {"name": "celesta", "program": 8, "channel": 2, "reverb": 110, "notes": celesta},
        ],
        "render": {"gain": 4.0, "sample_rate": 48000, "fade_in": 0.05,
                   "fade_out_start": fade0, "fade_out_dur": fade1 - fade0,
                   "loudnorm": "I=-19:TP=-3:LRA=11"},
        "storyboard": [
            {"at": 0.5, "expect": "quiet", "why": "one low note decaying before the cross"},
            {"at": round(E.title + 0.2, 2), "expect": "loud", "why": "cross swell + title"},
            {"at": 2.9, "expect": "quiet", "why": "faded out before the cut"},
        ],
    }


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "cue.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    cue = build()
    out.write_text(json.dumps(cue, indent=1) + "\n")
    n = sum(len(t["notes"]) for t in cue["tracks"])
    print(f"wrote {out}: {n} notes, cross at {E.cross:.3f}s, title from {E.title}s")
