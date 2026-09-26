#!/usr/bin/env python3
"""score_cue.py - compose a timed music cue to MIDI, render it, normalize it, and measure it.

The point of this script is that an agent cannot hear audio. Everything it can
honestly claim about a cue has to be measured, so measurement is not an optional
final step here - it is the deliverable alongside the audio file.

Pipeline: cue spec (JSON) -> .mid -> fluidsynth -> ffmpeg (fade + loudnorm + hard trim)
-> objective report (duration, peak, per-window RMS envelope, spectral centroid).

Usage:
    # write a starter spec you can edit
    python3 scripts/score_cue.py init cue.json

    # compose + render + normalize + measure
    python3 scripts/score_cue.py render cue.json --soundfont ~/.local/share/soundfonts/MuseScore_General.sf2

    # measure any existing audio file (no composing)
    python3 scripts/score_cue.py measure out/cue.wav --storyboard cue.json

    # assert that a set of variants really differ from each other
    python3 scripts/score_cue.py fingerprint out/*.wav

Requires: fluidsynth, ffmpeg on PATH; python packages mido and numpy.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- spec handling

STARTER_SPEC = {
    "name": "cue",
    "duration": 10.0,
    "bpm": 60,
    "_comment": (
        "bpm 60 makes one beat equal one second, so every 'at' below is literally "
        "a timecode you can read off a storyboard. Keep it at 60 unless you need "
        "musical bar math."
    ),
    "tracks": [
        {
            "name": "lead",
            "program": 0,
            "channel": 0,
            "reverb": 110,
            "notes": [
                {"at": 0.30, "note": 69, "vel": 42, "dur": 1.6, "why": "voice A, one place"},
                {"at": 1.70, "note": 74, "vel": 34, "dur": 1.6, "why": "voice B answers"},
                {"at": 3.30, "note": 66, "vel": 38, "dur": 1.4},
                {"at": 4.40, "note": 71, "vel": 32, "dur": 1.3},
                {"at": 5.40, "note": 69, "vel": 36, "dur": 1.2},
                {"at": 6.05, "note": 62, "vel": 52, "dur": 3.9, "why": "reveal beat"},
                {"at": 6.05, "note": 69, "vel": 46, "dur": 3.9},
                {"at": 6.05, "note": 74, "vel": 44, "dur": 3.9},
                {"at": 7.30, "note": 78, "vel": 30, "dur": 2.6},
                {"at": 8.60, "note": 74, "vel": 24, "dur": 1.4},
            ],
        },
        {
            "name": "low_strings",
            "program": 48,
            "channel": 1,
            "reverb": 127,
            "notes": [
                {"at": 5.85, "note": 38, "vel": 30, "dur": 4.1, "why": "swell under the reveal"},
                {"at": 5.95, "note": 50, "vel": 26, "dur": 4.0},
                {"at": 6.60, "note": 57, "vel": 20, "dur": 3.3},
            ],
        },
    ],
    "render": {
        "gain": 6.0,
        "_gain_comment": (
            "Soundfont-specific. MuseScore_General.sf2 wants about 6; the macOS "
            "gs_instruments.dls bank wants about 4.5. Re-measure peak after any "
            "soundfont change instead of trusting a remembered number."
        ),
        "sample_rate": 48000,
        "fade_in": 0.3,
        "fade_out_start": 9.0,
        "fade_out_dur": 1.0,
        "loudnorm": "I=-19:TP=-3:LRA=11",
    },
    "_storyboard_comment": (
        "Each beat is checked against the measured RMS envelope, relative to the "
        "cue's own median level. Place 'quiet' checks in the gaps between notes, "
        "not on an attack: a single struck note's onset window is genuinely loud "
        "even in a sparse passage, so checking at 0.0 where a note starts will "
        "fail for the wrong reason."
    ),
    "storyboard": [
        {"at": 1.0, "expect": "quiet", "why": "sparse opening, single notes decaying"},
        {"at": 2.5, "expect": "quiet"},
        {"at": 6.0, "expect": "loud", "why": "reveal beat - must be the peak of the envelope"},
        {"at": 9.5, "expect": "quiet", "why": "faded out before the cut"},
    ],
}


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.path)
    if out.exists() and not args.force:
        print(f"refusing to overwrite {out} (use --force)", file=sys.stderr)
        return 2
    out.write_text(json.dumps(STARTER_SPEC, indent=2) + "\n")
    print(f"wrote starter spec to {out}")
    print("Edit the note lists so the 'at' times line up with your storyboard, then:")
    print(f"  python3 {sys.argv[0]} render {out}")
    return 0


# ---------------------------------------------------------------------- compose


def compose(spec: dict, mid_path: Path) -> float:
    """Write the MIDI file. Returns its nominal length in seconds.

    Each note carries an absolute onset time in seconds. That is the whole reason
    to go through MIDI rather than a generative model: the onset you write is the
    onset you get, so the music can be cut against picture.
    """
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack

    tpb = 480
    bpm = spec.get("bpm", 60)

    def ticks(sec: float) -> int:
        # at bpm 60 one beat is one second; otherwise scale accordingly
        return int(round(sec * tpb * bpm / 60.0))

    mid = MidiFile(ticks_per_beat=tpb)
    first = True
    for tspec in spec["tracks"]:
        track = MidiTrack()
        mid.tracks.append(track)
        if first:
            track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
            first = False
        ch = int(tspec.get("channel", 0))
        track.append(Message("program_change", program=int(tspec.get("program", 0)), channel=ch))
        if "reverb" in tspec:
            track.append(
                Message("control_change", control=91, value=int(tspec["reverb"]), channel=ch)
            )
        events = []
        for n in tspec["notes"]:
            on = ticks(float(n["at"]))
            off = ticks(float(n["at"]) + float(n["dur"]))
            events.append((on, 1, int(n["note"]), int(n.get("vel", 64))))
            events.append((off, 0, int(n["note"]), 0))
        # sort by tick, and put note_off before note_on at the same tick so a
        # repeated pitch retriggers cleanly instead of being cut by its own off
        events.sort(key=lambda e: (e[0], e[1]))
        prev = 0
        for tick, kind, note, vel in events:
            track.append(
                Message(
                    "note_on" if kind else "note_off",
                    note=note,
                    velocity=vel,
                    channel=ch,
                    time=tick - prev,
                )
            )
            prev = tick

    mid.save(str(mid_path))
    return mid.length


# ----------------------------------------------------------------------- render


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise SystemExit(f"{tool} not found on PATH. Install it first (brew install {tool}).")
    return path


DEFAULT_SOUNDFONTS = [
    Path.home() / ".local/share/soundfonts/MuseScore_General.sf2",
    Path("/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls"),
]


def resolve_soundfont(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise SystemExit(f"soundfont not found: {p}")
        return p
    for cand in DEFAULT_SOUNDFONTS:
        if cand.exists():
            return cand
    raise SystemExit(
        "No soundfont found. Either pass --soundfont, or fetch the MIT-licensed "
        "MuseScore_General.sf2 (206MB) from "
        "https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf2"
    )


def render_wav(mid_path: Path, soundfont: Path, raw_path: Path, gain: float, rate: int) -> None:
    require("fluidsynth")
    subprocess.run(
        [
            "fluidsynth",
            "-ni",
            "-g",
            str(gain),
            "-F",
            str(raw_path),
            "-r",
            str(rate),
            str(soundfont),
            str(mid_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def post_process(raw: Path, out: Path, r: dict, duration: float) -> None:
    """Fade, loudness-normalize, and HARD TRIM.

    The trim is not cosmetic. fluidsynth keeps writing until the reverb and
    release tails decay, so a 10.00s MIDI file routinely renders to 12-13s. If
    you hand that to a video edit it overruns the cut.
    """
    require("ffmpeg")
    fade_out_start = float(r.get("fade_out_start", max(0.0, duration - 1.0)))
    filters = (
        f"afade=t=in:st=0:d={r.get('fade_in', 0.3)},"
        f"afade=t=out:st={fade_out_start}:d={r.get('fade_out_dur', 1.0)},"
        f"loudnorm={r.get('loudnorm', 'I=-19:TP=-3:LRA=11')}"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw),
            "-af",
            filters,
            "-t",
            f"{duration:.3f}",
            str(out),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------- measure


def load_samples(path: Path, rate: int = 48000):
    """Decode any audio file to mono float32 via an ffmpeg pipe."""
    import numpy as np

    require("ffmpeg")
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "quiet",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(proc.stdout, dtype="<f4"), rate


def envelope(x, rate: int, window: float = 0.5):
    """Per-window RMS in dBFS. This is the measurement that tells you whether the
    music actually follows the storyboard - where it is sparse and where it swells."""
    import numpy as np

    n = max(1, int(rate * window))
    out = []
    for i in range(0, len(x), n):
        chunk = x[i : i + n]
        if len(chunk) == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        db = 20 * math.log10(rms) if rms > 1e-9 else -120.0
        out.append((round(i / rate, 2), round(db, 1)))
    return out


def spectral_centroid(x, rate: int) -> float:
    """Brightness fingerprint in Hz. Two renders of the same notes on different
    instruments differ here; two renders of the same instrument do not. That makes
    it the cheapest way to prove a set of 'variants' are actually distinct."""
    import numpy as np

    if len(x) == 0:
        return 0.0
    win = 4096
    hop = 2048
    acc_num = 0.0
    acc_den = 0.0
    freqs = np.fft.rfftfreq(win, 1.0 / rate)
    for i in range(0, max(1, len(x) - win), hop):
        seg = x[i : i + win]
        if len(seg) < win:
            break
        mag = np.abs(np.fft.rfft(seg * np.hanning(win)))
        acc_num += float(np.sum(freqs * mag))
        acc_den += float(np.sum(mag))
    return round(acc_num / acc_den, 1) if acc_den > 0 else 0.0


def measure(path: Path, storyboard: list | None = None) -> dict:
    import numpy as np

    x, rate = load_samples(path)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    env = envelope(x, rate)
    report = {
        "file": str(path),
        "duration_s": round(len(x) / rate, 3),
        "peak": round(peak, 4),
        "clipping": peak >= 1.0,
        "spectral_centroid_hz": spectral_centroid(x, rate),
        "envelope_db_per_0.5s": env,
    }
    if storyboard:
        checks = []
        loud = [db for _, db in env]
        if loud:
            span = max(loud) - min(loud)
        else:
            span = 0.0
        report["dynamic_range_db"] = round(span, 1)
        for beat in storyboard:
            at = float(beat["at"])
            near = min(env, key=lambda e: abs(e[0] - at)) if env else (at, -120.0)
            checks.append(
                {
                    "at": at,
                    "expect": beat.get("expect"),
                    "measured_db": near[1],
                    "why": beat.get("why", ""),
                }
            )
        # relative verdict: 'loud' beats must sit above the median, 'quiet' below
        if checks and env:
            med = sorted(loud)[len(loud) // 2]
            for c in checks:
                if c["expect"] == "loud":
                    c["ok"] = c["measured_db"] >= med
                elif c["expect"] == "quiet":
                    c["ok"] = c["measured_db"] <= med
                else:
                    c["ok"] = None
            report["median_db"] = round(med, 1)
        report["storyboard_checks"] = checks
    return report


def print_report(rep: dict) -> None:
    print(f"\n== {rep['file']}")
    print(f"   duration {rep['duration_s']}s   peak {rep['peak']}", end="")
    print("   *** CLIPPING ***" if rep["clipping"] else "")
    print(f"   spectral centroid {rep['spectral_centroid_hz']} Hz")
    if "dynamic_range_db" in rep:
        print(f"   envelope span {rep['dynamic_range_db']} dB (median {rep.get('median_db')} dB)")
    print("   envelope (s -> dBFS):")
    line = "     "
    for t, db in rep["envelope_db_per_0.5s"]:
        line += f"{t:>5}:{db:>7}  "
        if len(line) > 90:
            print(line)
            line = "     "
    if line.strip():
        print(line)
    for c in rep.get("storyboard_checks", []):
        mark = "ok " if c.get("ok") else ("FAIL" if c.get("ok") is False else "-- ")
        why = f"  ({c['why']})" if c["why"] else ""
        print(f"   [{mark}] {c['at']}s expect {c['expect']}: {c['measured_db']} dB{why}")
    print("\n   An agent cannot hear this file. These numbers say whether the cue")
    print("   has the requested shape; only a human can say whether it sounds good.")


# ------------------------------------------------------------------- subcommands


def cmd_render(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.spec).read_text())
    name = spec.get("name", "cue")
    duration = float(spec.get("duration", 10.0))
    r = spec.get("render", {})
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    mid_path = outdir / f"{name}.mid"
    raw_path = outdir / f"{name}_raw.wav"
    out_path = outdir / f"{name}.wav"

    midi_len = compose(spec, mid_path)
    print(f"composed {mid_path}  nominal length {midi_len:.2f}s")

    sf = resolve_soundfont(args.soundfont or r.get("soundfont"))
    gain = float(args.gain if args.gain is not None else r.get("gain", 6.0))
    rate = int(r.get("sample_rate", 48000))
    render_wav(mid_path, sf, raw_path, gain, rate)
    raw_rep = measure(raw_path)
    print(f"rendered {raw_path} with {sf.name} at -g {gain}")
    print(f"   raw duration {raw_rep['duration_s']}s (tail beyond the {duration}s cue "
          f"is reverb/release and gets trimmed), raw peak {raw_rep['peak']}")
    if raw_rep["peak"] < 0.05:
        print("   WARNING: raw peak is tiny. This soundfont needs more gain "
              "(the macOS DLS bank renders near-silent at default gain).")

    post_process(raw_path, out_path, r, duration)
    rep = measure(out_path, spec.get("storyboard"))
    print_report(rep)

    (outdir / f"{name}_report.json").write_text(json.dumps(rep, indent=2) + "\n")
    print(f"\n   report written to {outdir / (name + '_report.json')}")

    failures = [c for c in rep.get("storyboard_checks", []) if c.get("ok") is False]
    if rep["clipping"]:
        print("\n   Peak >= 1.0. Lower the loudnorm target (e.g. I=-19 -> I=-21) "
              "or the fluidsynth gain, then re-render.")
        return 1
    # 0.1s of slack: codec frame alignment legitimately costs a few tens of ms.
    # Anything larger means the trim did not happen and the reverb tail is still
    # attached, which will overrun a video cut.
    if abs(rep["duration_s"] - duration) > 0.1:
        print(f"\n   Duration {rep['duration_s']}s != requested {duration}s. "
              f"Check that the -t trim is being applied.")
        return 1
    if failures:
        print("\n   The envelope does not match the storyboard at the beats above. "
              "Adjust note velocities/onsets in the spec, not the loudnorm settings.")
        return 1
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    storyboard = None
    if args.storyboard:
        storyboard = json.loads(Path(args.storyboard).read_text()).get("storyboard")
    rc = 0
    for f in args.files:
        rep = measure(Path(f), storyboard)
        print_report(rep)
        if rep["clipping"]:
            rc = 1
    return rc


def cmd_fingerprint(args: argparse.Namespace) -> int:
    """Prove a set of variants are actually different before presenting them as choices.

    This exists because of a real near-miss: four 'different instrument' variants
    were generated by patching a source file with sed, the pattern silently failed
    to match, and all four files came back with identical duration, peak and
    centroid. They were four copies of the same instrument, about to be shipped as
    an A/B comparison. Identical fingerprints mean your variation step did nothing.
    """
    rows = []
    for f in args.files:
        rep = measure(Path(f))
        rows.append((Path(f).name, rep["duration_s"], rep["peak"], rep["spectral_centroid_hz"]))
    print(f"\n{'file':<32}{'dur':>9}{'peak':>9}{'centroid':>11}")
    for name, d, p, c in rows:
        print(f"{name:<32}{d:>9}{p:>9}{c:>11}")
    keys = [(d, p, c) for _, d, p, c in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        print("\nFAIL: these files have identical fingerprints, so they are not")
        print("distinct variants. Your variation step did not take effect.")
        for name, d, p, c in rows:
            if (d, p, c) in dupes:
                print(f"  - {name}")
        return 1
    print("\nok: all variants differ. Safe to present as a comparison.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write a starter cue spec")
    p.add_argument("path")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("render", help="compose, render, normalize, verify")
    p.add_argument("spec")
    p.add_argument("--outdir", default="out")
    p.add_argument("--soundfont", default=None)
    p.add_argument("--gain", type=float, default=None)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("measure", help="measure existing audio files")
    p.add_argument("files", nargs="+")
    p.add_argument("--storyboard", default=None, help="cue spec whose storyboard to check against")
    p.set_defaults(func=cmd_measure)

    p = sub.add_parser("fingerprint", help="assert a set of variants really differ")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_fingerprint)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
