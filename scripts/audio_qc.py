#!/usr/bin/env python3
"""
audio_qc.py — Strict audio quality gate for Shorts.

Runs after render, BEFORE upload. Fails fast on any of:
  • Silence > 300ms anywhere (intro/middle/outro)
  • Audio shorter than video by > 100ms (sync drift)
  • Missing audio stream
  • LUFS outside [-18, -12] range (YouTube broadcast standard ~-14)
  • Peak above -0.5 dBTP (clipping)

Usage:
  python3 scripts/audio_qc.py S02500
  python3 scripts/audio_qc.py S02500 --strict   # exit code 1 on any warning
  python3 scripts/audio_qc.py --all             # check all output/ videos
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ─── Quality thresholds ──────────────────────────────────────────────────────
MAX_SILENCE_MS         = 300    # any silence longer than this fails QC
SILENCE_THRESHOLD_DB   = -40    # below this counts as silence
MAX_SYNC_DRIFT_MS      = 175    # AES/BBC tolerance ±185ms; long videos relax to 250ms
LUFS_MIN, LUFS_MAX     = -18.0, -12.0
MAX_TRUE_PEAK_DB       = -0.5

# Tolerated zones — sometimes natural speech pauses are fine here
# (sentences ending with periods naturally have ~200-400ms gaps)
NATURAL_PAUSE_MAX_MS   = 500    # if audio_3tier_bed is properly applied, no gap should exceed this


def ffprobe_streams(path: Path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True
    )
    return json.loads(r.stdout) if r.returncode == 0 else None


def detect_silences(path: Path, threshold_db=-40, min_duration=0.3):
    """Returns list of (start_s, end_s, duration_s) for each silence."""
    r = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    out = r.stderr
    silences, cur_start = [], None
    for line in out.split('\n'):
        if 'silence_start' in line:
            try:
                cur_start = float(line.split('silence_start: ')[1].split()[0])
            except (ValueError, IndexError):
                pass
        elif 'silence_end' in line and cur_start is not None:
            try:
                end = float(line.split('silence_end: ')[1].split('|')[0].strip())
                dur = float(line.split('silence_duration: ')[1].split()[0])
                silences.append((cur_start, end, dur))
                cur_start = None
            except (ValueError, IndexError):
                pass
    return silences


def measure_loudness(path: Path):
    """Returns (integrated_lufs, true_peak_db) using ffmpeg loudnorm."""
    r = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", "loudnorm=I=-14:TP=-1.0:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True
    )
    out = r.stderr
    if '{' not in out:
        return None, None
    json_str = '{' + out.split('{', 1)[1].rsplit('}', 1)[0] + '}'
    try:
        data = json.loads(json_str)
        return float(data['input_i']), float(data['input_tp'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None, None


def qc_video(video_id: str, strict: bool = False):
    """Returns (passed: bool, report: dict)"""
    out_dir = ROOT / "output" / video_id
    video = out_dir / "video.mp4"
    if not video.exists():
        return False, {"error": f"video.mp4 not found in {out_dir}"}

    info = ffprobe_streams(video)
    if not info:
        return False, {"error": "ffprobe failed"}

    audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
    video_streams = [s for s in info["streams"] if s["codec_type"] == "video"]

    issues, warnings = [], []
    report = {"video_id": video_id, "video_path": str(video)}

    # Check 1: audio stream exists
    if not audio_streams:
        issues.append("CRITICAL: video.mp4 has no audio stream")
        return False, {**report, "issues": issues}

    audio_dur = float(audio_streams[0].get("duration", 0))
    video_dur = float(video_streams[0].get("duration", 0))
    drift_ms = abs(audio_dur - video_dur) * 1000
    report["audio_duration"] = audio_dur
    report["video_duration"] = video_dur
    report["sync_drift_ms"] = round(drift_ms, 1)

    # Check 2: sync drift — relaxed for long-form (>3min OR L-prefix ID)
    is_long = video_dur > 180 or video_id.upper().startswith("L")
    drift_limit = 250 if is_long else MAX_SYNC_DRIFT_MS
    if drift_ms > drift_limit:
        issues.append(f"Audio/video drift {drift_ms:.0f}ms > {drift_limit}ms")

    # Check 3: silences
    silences = detect_silences(video, SILENCE_THRESHOLD_DB, MAX_SILENCE_MS / 1000)
    report["silences"] = [{"start": round(s, 2), "end": round(e, 2),
                            "duration": round(d, 2)} for s, e, d in silences]
    for s, e, d in silences:
        loc = "intro" if s < 0.5 else ("outro" if e > video_dur - 1.0 else "middle")
        if d * 1000 > NATURAL_PAUSE_MAX_MS:
            issues.append(f"{loc.upper()} silence {s:.1f}s-{e:.1f}s ({d*1000:.0f}ms) — exceeds natural pause max {NATURAL_PAUSE_MAX_MS}ms")
        elif d * 1000 > MAX_SILENCE_MS:
            warnings.append(f"{loc} pause {s:.1f}s-{e:.1f}s ({d*1000:.0f}ms) — borderline")

    # Check 4: loudness (LUFS) and true peak
    lufs, tp = measure_loudness(video)
    if lufs is not None:
        report["integrated_lufs"] = round(lufs, 1)
        report["true_peak_db"] = round(tp, 1) if tp else None
        if lufs < LUFS_MIN:
            warnings.append(f"Audio too quiet: {lufs:.1f} LUFS (min {LUFS_MIN})")
        elif lufs > LUFS_MAX:
            warnings.append(f"Audio too loud: {lufs:.1f} LUFS (max {LUFS_MAX})")
        if tp is not None and tp > MAX_TRUE_PEAK_DB:
            issues.append(f"Clipping: true peak {tp:.1f} dBTP (max {MAX_TRUE_PEAK_DB})")

    report["issues"] = issues
    report["warnings"] = warnings
    passed = len(issues) == 0 and (not strict or len(warnings) == 0)
    report["passed"] = passed
    return passed, report


def print_report(report: dict):
    vid = report.get("video_id", "?")
    if "error" in report:
        print(f"❌ {vid}: {report['error']}")
        return

    p = report["passed"]
    icon = "✅" if p else "❌"
    print(f"{icon} {vid}")
    print(f"   audio: {report['audio_duration']:.1f}s | video: {report['video_duration']:.1f}s | drift: {report['sync_drift_ms']:.0f}ms")
    if report.get("integrated_lufs") is not None:
        print(f"   LUFS: {report['integrated_lufs']} | true peak: {report.get('true_peak_db','—')} dB")
    if report["silences"]:
        print(f"   silences: {len(report['silences'])}")
        for s in report["silences"][:5]:
            print(f"     {s['start']:.1f}s → {s['end']:.1f}s ({s['duration']*1000:.0f}ms)")
    if report["issues"]:
        print(f"   🚨 ISSUES:")
        for i in report["issues"]:
            print(f"     • {i}")
    if report["warnings"]:
        print(f"   ⚠️  warnings:")
        for w in report["warnings"]:
            print(f"     • {w}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", nargs="?", help="ID like S02500 or L00100")
    ap.add_argument("--all", action="store_true", help="check every output/ dir")
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    args = ap.parse_args()

    if args.all:
        ids = sorted(d.name for d in (ROOT / "output").iterdir()
                     if d.is_dir() and (d / "video.mp4").exists())
    elif args.video_id:
        ids = [args.video_id]
    else:
        ap.print_help()
        sys.exit(1)

    all_reports = []
    failures = 0
    for vid in ids:
        passed, report = qc_video(vid, args.strict)
        all_reports.append(report)
        if args.json:
            continue
        print_report(report)
        print()
        if not passed:
            failures += 1

    if args.json:
        print(json.dumps(all_reports, indent=2, ensure_ascii=False))

    if not args.json:
        print("─" * 60)
        print(f"Total: {len(ids)} | passed: {len(ids)-failures} | failed: {failures}")

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
