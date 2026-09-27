#!/usr/bin/env python3
"""Measure an existing song so picture can be cut to it: stems, beats, drums, syllables, sung lines.

    python scripts/music_timing.py separate song.m4a --out stems/          # needs demucs
    python scripts/music_timing.py analyze song.m4a --fps 24 --out timing.json \\
        [--vocals stems/vocals.wav --accomp stems/no_vocals.wav] [--lrc lines.lrc]
    python scripts/music_timing.py audit timing.json

`analyze` writes one JSON the renderer imports:
  beats        beat-tracker times snapped to the nearest percussive onset (fallback: median offset)
  env          per-video-frame percussive envelope in [0, 1] (instant attack, --release decay): bloom, flares
  kicks        low-band percussive peaks: one-off hits (flashes, stamps)
  vocal        onsets of the vocal stem, and a per-10 ms "syllable rate" for pen progress driven by singing
  lines        sung-line onsets from an LRC file, snapped to vocal onsets, with word counts and word times
  audit        how far the raw sources were off (beat offset, line offsets)

Only timestamps and word counts are read from the LRC file; the text is not stored, so the renderer reads it
from its own file at render time.

Needs numpy, scipy, librosa and ffmpeg on PATH; `separate` also needs demucs.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
HOP = 128


def load_mono(path, sr=SR):
    """Decode any ffmpeg-readable file to mono float32 at ``sr``."""
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not found on PATH")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def snap(times, ref, tol, fallback=0.0):
    """Move each time to the nearest ``ref`` time within ``tol`` s; otherwise shift it by ``fallback``."""
    times = np.asarray(times, float)
    ref = np.asarray(ref, float)
    if len(ref) == 0:
        return times + fallback
    idx = np.clip(np.searchsorted(ref, times), 1, max(len(ref) - 1, 1))
    lo, hi = ref[np.maximum(idx - 1, 0)], ref[np.minimum(idx, len(ref) - 1)]
    near = np.where(np.abs(times - lo) <= np.abs(times - hi), lo, hi)
    return np.where(np.abs(near - times) <= tol, near, times + fallback)


def nearest_offsets(times, ref):
    """Signed distance from each time to the nearest ``ref`` time (ref - time)."""
    return snap(times, ref, np.inf) - np.asarray(times, float)


def percussive_onsets(y, sr=SR):
    import librosa
    yp = librosa.effects.percussive(y)
    env = librosa.onset.onset_strength(y=yp, sr=sr, hop_length=HOP)
    return librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=HOP, units="time")


def _norm(x, lo_pct=50, hi_pct=99.5):
    lo, hi = np.percentile(x, lo_pct), np.percentile(x, hi_pct)
    return np.clip((x - lo) / max(hi - lo, 1e-9), 0, 1)


def percussive_envelope(y, fps, sr=SR, release=0.14):
    """Per-video-frame drum envelope: 70% kick band + 30% full band, instant attack, exponential release."""
    import librosa
    hop = 256
    yp = librosa.effects.percussive(y)
    kick = _norm(librosa.onset.onset_strength(y=yp, sr=sr, hop_length=hop, fmax=180, n_mels=32))
    full = _norm(librosa.onset.onset_strength(y=yp, sr=sr, hop_length=hop))
    raw = 0.7 * kick + 0.3 * full
    t = librosa.times_like(raw, sr=sr, hop_length=hop)
    dec = np.exp(-(t[1] - t[0]) / release)
    env = np.zeros_like(raw)
    for i, v in enumerate(raw):
        env[i] = max(v, env[i - 1] * dec if i else 0.0)
    ft = np.arange(0, len(y) / sr, 1.0 / fps)
    peaks = librosa.util.peak_pick(kick, pre_max=6, post_max=6, pre_avg=20, post_avg=20, delta=0.12, wait=8)
    kicks = [float(t[p]) for p in peaks if kick[p] > 0.35]
    return np.interp(ft, t, env), kicks


def vocal_analysis(yv, sr=SR):
    """Vocal onsets (backtracked) and a per-10 ms syllable rate: attacks push, held notes creep."""
    import librosa
    hop = 220
    on_env = librosa.onset.onset_strength(y=yv, sr=sr, hop_length=HOP)
    onsets = librosa.onset.onset_detect(onset_envelope=on_env, sr=sr, hop_length=HOP, units="time", backtrack=True)
    rms = librosa.feature.rms(y=yv, frame_length=1024, hop_length=hop)[0]
    act = np.clip((librosa.amplitude_to_db(rms, ref=np.max) + 38) / 20, 0, 1)
    on2 = _norm(librosa.onset.onset_strength(y=yv, sr=sr, hop_length=hop), 60, 99.5)
    n = min(len(act), len(on2))
    rate = 0.25 * act[:n] + on2[:n]
    return onsets, rate, hop / sr, act[:n]


def phrase_starts(onsets, act, dt, before=(0.3, 0.05), quiet=0.3):
    """Onsets preceded by a quiet stretch of the vocal stem: where a sung line can begin."""
    out = []
    for t in onsets:
        a, b = int(max(t - before[0], 0) / dt), int(max(t - before[1], 0) / dt)
        if b <= a or float(np.mean(act[a:b])) < quiet:
            out.append(float(t))
    return np.array(out)


def snap_line(t, starts, onsets, tol):
    """Snap a sung-line time to the nearest phrase start within ``tol``, else to the nearest onset.

    Nearest-onset alone is wrong when the line's time is late: inside a dense line the second syllable can
    be nearer than the first."""
    for ref in (starts, onsets):
        if len(ref):
            s_ = float(snap([t], ref, tol)[0])
            if s_ != t or np.min(np.abs(np.asarray(ref) - t)) == 0:
                return s_
    return float(t)


LRC_RE = re.compile(r"\s*\[(\d+):(\d+(?:\.\d+)?)\](.*)")


def parse_lrc(path):
    """(time, word_count) per LRC line. The text itself is discarded."""
    out = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = LRC_RE.match(raw)
        if m:
            out.append((int(m.group(1)) * 60 + float(m.group(2)), len(m.group(3).split())))
    return out


def word_times(t0, t1, onsets, n):
    """Spread ``n`` word starts over the vocal onsets in [t0, t1); the first word starts at the line onset."""
    if n <= 0:
        return []
    on = np.asarray([x for x in onsets if t0 - 0.02 <= x < t1], float)
    if len(on) == 0 or on[0] > t0 + 0.1:
        on = np.r_[t0, on]
    if len(on) >= n:
        return [float(x) for x in on[np.round(np.linspace(0, len(on) - 1, n)).astype(int)]]
    if len(on) > 1:
        return [float(x) for x in np.interp(np.arange(n), np.linspace(0, n - 1, len(on)), on)]
    step = min(0.35, (t1 - t0) / n)
    return [float(t0 + k * step) for k in range(n)]


def analyze(song, fps, vocals=None, accomp=None, lrc=None, release=0.14, beat_tol=0.07, line_tol=0.35):
    import librosa
    y = load_mono(song)
    ya = load_mono(accomp) if accomp else y
    yv = load_mono(vocals) if vocals else None
    tempo, beats = librosa.beat.beat_track(y=y, sr=SR, units="time")
    perc = percussive_onsets(ya)
    off = nearest_offsets(beats, perc)
    matched = np.abs(off) < beat_tol
    med = float(np.median(off[matched])) if matched.any() else 0.0
    beats2 = snap(beats, perc, beat_tol, med)
    env, kicks = percussive_envelope(ya, fps, release=release)
    out = dict(fps=fps, duration=len(y) / SR, tempo=float(np.atleast_1d(tempo)[0]),
               beats_raw=[round(float(b), 4) for b in beats], beats=[round(float(b), 4) for b in beats2],
               perc_onsets=[round(float(x), 4) for x in perc], env=[round(float(v), 4) for v in env],
               kicks=[round(k, 4) for k in kicks],
               audit=dict(beat_offset_ms=round(med * 1000, 1), beats_matched=round(float(matched.mean()), 3)))
    if yv is not None:
        von, rate, dt, act = vocal_analysis(yv)
        out["vocal"] = dict(onsets=[round(float(x), 4) for x in von], rate_dt=dt,
                            rate=[round(float(r), 4) for r in rate])
        if lrc:
            rows = parse_lrc(lrc)
            times = np.array([r[0] for r in rows])
            starts = phrase_starts(von, act, dt)
            snapped = [snap_line(t, starts, von, line_tol) if n > 0 else float(t) for t, n in rows]
            lines = []
            for k, ((t, n), ts) in enumerate(zip(rows, snapped)):
                nxt = snapped[k + 1] - 0.08 if k + 1 < len(snapped) else ts + 3.0
                lines.append(dict(t_lrc=round(float(t), 3), t=round(ts, 4), words=n,
                                  word_times=[round(w, 4) for w in word_times(ts, nxt, von, n)]))
            d = np.array([a["t"] - a["t_lrc"] for a in lines if a["words"] > 0])
            out["lines"] = lines
            if len(d):
                out["audit"].update(line_offset_median_ms=round(float(np.median(d)) * 1000, 1),
                                    line_offset_abs_p75_ms=round(float(np.percentile(np.abs(d), 75)) * 1000, 1),
                                    line_offset_abs_max_ms=round(float(np.abs(d).max()) * 1000, 1))
    elif lrc:
        print("warning: --lrc without --vocals: line onsets are not snapped", file=sys.stderr)
        out["lines"] = [dict(t_lrc=t, t=t, words=n, word_times=[]) for t, n in parse_lrc(lrc)]
    return out


def cmd_separate(a):
    try:
        import demucs  # noqa: F401
    except ImportError:
        sys.exit("demucs is not installed: pip install demucs")
    out = Path(a.out)
    subprocess.run([sys.executable, "-m", "demucs", "-n", a.model, "--two-stems=vocals", "-o", str(out), str(a.song)], check=True)
    stem = out / a.model / Path(a.song).stem
    print(f"vocals:    {stem / 'vocals.wav'}\naccomp:    {stem / 'no_vocals.wav'}")


def cmd_analyze(a):
    res = analyze(a.song, a.fps, a.vocals, a.accomp, a.lrc, a.release)
    Path(a.out).write_text(json.dumps(res))
    print(json.dumps(res["audit"], indent=1))
    print(f"wrote {a.out}: {len(res['beats'])} beats, {len(res['kicks'])} kicks, {len(res['env'])} env frames"
          + (f", {len(res['lines'])} lines" if "lines" in res else ""))


def cmd_audit(a):
    res = json.loads(Path(a.timing).read_text())
    print(json.dumps(res.get("audit", {}), indent=1))
    lines = [x for x in res.get("lines", []) if x["words"] > 0]
    big = [(x["t_lrc"], round((x["t"] - x["t_lrc"]) * 1000)) for x in lines if abs(x["t"] - x["t_lrc"]) > 0.1]
    if big:
        print(f"{len(big)} lines moved more than 100 ms (t_lrc, ms): {big[:20]}")
    v = res.get("vocal")
    if v and lines:
        on = np.array(v["onsets"])
        gaps = [(a["t"], b["t"]) for a, b in zip(lines, lines[1:]) if b["t"] - a["t"] > 4.0]
        print(f"long gaps between sung lines (candidate instrumental passages): {[(round(a, 2), round(b, 2)) for a, b in gaps]}")
        print(f"vocal onsets: {len(on)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("separate", help="split a song into vocals / accompaniment with demucs")
    s.add_argument("song"); s.add_argument("--out", default="stems"); s.add_argument("--model", default="htdemucs")
    s.set_defaults(func=cmd_separate)
    s = sub.add_parser("analyze", help="beats, drum envelope, vocal onsets, sung lines -> JSON")
    s.add_argument("song"); s.add_argument("--fps", type=float, default=24); s.add_argument("--out", required=True)
    s.add_argument("--vocals"); s.add_argument("--accomp"); s.add_argument("--lrc")
    s.add_argument("--release", type=float, default=0.14, help="envelope release in seconds")
    s.set_defaults(func=cmd_analyze)
    s = sub.add_parser("audit", help="print how far the raw timing sources were off")
    s.add_argument("timing"); s.set_defaults(func=cmd_audit)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
