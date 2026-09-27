#!/usr/bin/env python3
"""narration_check.py - transcribe voice takes, show where they differ from the script,
and write the per-character timestamps a narration timeline is keyed to.

An agent cannot hear a TTS take. Transcribing it back is the closest thing to
listening: it catches skipped words, a wrong reading of a polyphonic character,
a number read the wrong way. It is a review aid, not a verdict -- a recogniser
also writes homophones and digits where the script has words, which look like
differences and are not errors. Every reported span needs a human-style judgement:
same sound (ignore) or different sound (retake, or rewrite the text around it).

  python narration_check.py script.json takes/ --out takes/chars.json
  python narration_check.py script.json takes/ --only s02 s11 --suffix _b   # compare retakes

script.json is either a list or {"segments": [...]}, each segment {"id", "say"};
takes/<id><suffix>.wav are the takes. --out writes
{id: {"text": transcript, "chars": [[char, start, end], ...]}}, times in seconds
within the take, merged into the file if it exists.

Requires the mlx-whisper package (Apple Silicon); tested with
mlx-community/whisper-large-v3-mlx. Other recognisers with word timestamps work
the same way but are untested here.
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

PUNCT = set("，。；：？！、,.;:?!\"'“”‘’（）()·—-…《》 \t\n")


def norm(s):
    return "".join(c for c in s if c not in PUNCT).lower()


def similarity(script, heard):
    """Character similarity of the normalised texts, 0..1."""
    return difflib.SequenceMatcher(None, norm(script), norm(heard), autojunk=False).ratio()


def diff_spans(script, heard, join_gap=1):
    """``[(script_span, heard_span)]`` where the transcript differs, on normalised text.
    Differences separated by at most ``join_gap`` matching characters are merged, so
    "重读病历" vs "中毒病例" is reported as one span, not three."""
    a, b = norm(script), norm(heard)
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()]
    spans = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        if spans and i1 - spans[-1][1] <= join_gap and j1 - spans[-1][3] <= join_gap:
            spans[-1][1], spans[-1][3] = i2, j2
        else:
            spans.append([i1, i2, j1, j2])
    return [(a[i1:i2], b[j1:j2]) for i1, i2, j1, j2 in spans]


def chars_from_words(words):
    out = []
    for w in words:
        tok = "".join(c for c in str(w["word"]) if c not in PUNCT)
        a, b = float(w["start"]), float(w["end"])
        for k, ch in enumerate(tok):
            out.append([ch.lower(), round(a + (b - a) * k / len(tok), 4),
                        round(a + (b - a) * (k + 1) / len(tok), 4)])
    return out


def transcribe(path, model, language, prompt):
    import mlx_whisper
    r = mlx_whisper.transcribe(str(path), path_or_hf_repo=model, language=language,
                               word_timestamps=True, initial_prompt=prompt or None)
    words = [w for s in r["segments"] for w in s.get("words", [])]
    return r["text"].strip(), chars_from_words(words)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", help="script JSON: a list or {'segments': [...]}, each {'id', 'say'}")
    ap.add_argument("takes", help="directory holding <id><suffix>.wav")
    ap.add_argument("--out", help="write per-character timestamps JSON here (merged if it exists)")
    ap.add_argument("--only", nargs="*", default=None, help="segment ids to check (default: all)")
    ap.add_argument("--suffix", default="", help="take file suffix, e.g. _b for alternates")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-mlx")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--prompt", default="", help="initial prompt: domain words help the recogniser")
    a = ap.parse_args()

    spec = json.loads(Path(a.script).read_text())
    segs = spec["segments"] if isinstance(spec, dict) else spec
    want = set(a.only) if a.only else None
    out = json.loads(Path(a.out).read_text()) if a.out and Path(a.out).exists() else {}
    review = 0
    for s in segs:
        if want and s["id"] not in want:
            continue
        take = Path(a.takes) / f"{s['id']}{a.suffix}.wav"
        if not take.exists():
            print(f"FAIL  {take} not found")
            return 1
        text, chars = transcribe(take, a.model, a.language, a.prompt)
        spans = diff_spans(s["say"], text)
        sim = similarity(s["say"], text)
        mark = "ok    " if not spans else "REVIEW"
        review += bool(spans)
        print(f"{mark} {s['id']}{a.suffix}  similarity {sim:.2f}")
        print(f"         script: {s['say']}")
        print(f"         heard:  {text}")
        for x, y in spans:
            print(f"         differs: {x or '∅'} -> {y or '∅'}")
        out[f"{s['id']}{a.suffix}"] = {"text": text, "chars": chars}
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False))
        print(f"\nwrote character timestamps for {len(out)} take(s) to {a.out}")
    print(f"\n{review} take(s) to review. For each span decide: same sound (a homophone, or"
          f"\ndigits for words) -> ignore; different sound -> retake, or rewrite the text"
          f"\naround a polyphonic character. An agent cannot hear the takes; a human should"
          f"\nstill listen before the voice ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
