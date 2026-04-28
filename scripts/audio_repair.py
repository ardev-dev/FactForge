#!/usr/bin/env python3
"""
audio_repair.py — Rescue videos with silent gaps by re-mixing audio.

For each existing video.mp4:
  1. Extract original audio track
  2. Loop BGM bed (ambient_documentary.mp3) at -28 dB throughout
  3. Add intro SFX swell (tension_build) at -10 dB during first 3s if intro is silent
  4. Apply 800ms outro fadeout to BGM
  5. Mix BGM bed UNDER original voice (BGM never ducks below -30 dB)
  6. Re-mux fixed audio with original video

Usage:
  python3 scripts/audio_repair.py S02500
  python3 scripts/audio_repair.py --all-failed   # repair every video that fails QC
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BGM = ROOT / "assets/ambient_documentary.mp3"
SFX_INTRO = ROOT / "audio_engineering/assets/sfx_real/universal/tension_build.wav"
SFX_OUTRO = ROOT / "audio_engineering/assets/sfx_real/universal/reveal_sting.wav"

# Mixing parameters
BGM_VOL_DB     = -28   # BGM constant level (audible but unobtrusive)
INTRO_SFX_DB   = -12   # Intro SFX during silent flash period
OUTRO_FADE_S   = 0.8
INTRO_FADE_S   = 0.4
INTRO_SILENT_S = 3.0   # If intro is silent for this long, fill with SFX swell


def video_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_format", str(path)], capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def has_silent_intro(path: Path, threshold_s: float = 2.0) -> bool:
    """True if first 2+ seconds are silent."""
    r = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", "silencedetect=noise=-40dB:d=1.5",
         "-t", "5", "-f", "null", "-"],
        capture_output=True, text=True
    )
    out = r.stderr
    for line in out.split('\n'):
        if 'silence_start' in line:
            try:
                start = float(line.split('silence_start: ')[1].split()[0])
                if start < 0.5:
                    return True
            except (ValueError, IndexError):
                pass
    return False


def repair(video_id: str, dry_run: bool = False) -> bool:
    out_dir = ROOT / "output" / video_id
    src = out_dir / "video.mp4"
    if not src.exists():
        print(f"❌ {video_id}: video.mp4 not found")
        return False

    bak = out_dir / "video_pre_repair.mp4"
    if not bak.exists():
        # Backup original once
        subprocess.run(["cp", str(src), str(bak)], check=True)
        print(f"  💾 backup: video_pre_repair.mp4")

    dur = video_duration(bak)
    silent_intro = has_silent_intro(bak)
    print(f"  duration: {dur:.1f}s | silent intro: {silent_intro}")

    if dry_run:
        return True

    # Build filter graph:
    #   [0:a] = original audio from video
    #   [1:a] = BGM, looped + volume + faded
    #   [2:a] = intro SFX (if needed)
    # Mix all three.
    out = out_dir / "video_repaired.mp4"
    inputs = ["-i", str(bak), "-stream_loop", "-1", "-i", str(BGM)]

    # BGM louder than originally planned — must fill all silent gaps.
    # -22 dB instead of -28 dB so it's audible even during vocal pauses.
    bgm_db = -22
    if silent_intro and SFX_INTRO.exists():
        # Loop tension_build to cover full 3s intro
        inputs += ["-stream_loop", "-1", "-i", str(SFX_INTRO)]
        fc = (
            # BGM constant -22 dB throughout, with intro/outro fades
            f"[1:a]atrim=0:{dur},asetpts=PTS-STARTPTS,volume={bgm_db}dB,"
            f"afade=t=in:st=0:d={INTRO_FADE_S},"
            f"afade=t=out:st={dur-OUTRO_FADE_S}:d={OUTRO_FADE_S}[bgm];"
            # Looped tension_build covers full intro period
            f"[2:a]atrim=0:{INTRO_SILENT_S - 0.2},asetpts=PTS-STARTPTS,"
            f"volume={INTRO_SFX_DB}dB,"
            f"afade=t=out:st={INTRO_SILENT_S - 0.7}:d=0.5[introsfx];"
            f"[0:a][bgm][introsfx]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[a]"
        )
    else:
        fc = (
            f"[1:a]atrim=0:{dur},asetpts=PTS-STARTPTS,volume={bgm_db}dB,"
            f"afade=t=in:st=0:d={INTRO_FADE_S},"
            f"afade=t=out:st={dur-OUTRO_FADE_S}:d={OUTRO_FADE_S}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
        )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart",
        str(out)
    ]
    print(f"  🔧 mixing audio...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ ffmpeg failed:\n{r.stderr[-500:]}")
        return False

    # Replace
    out.replace(src)
    print(f"  ✅ {video_id} repaired")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", nargs="?")
    ap.add_argument("--all-failed", action="store_true",
                    help="repair every output video that currently fails audio_qc")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.all_failed:
        # Find all failing
        ids = []
        for d in sorted((ROOT / "output").iterdir()):
            if d.is_dir() and (d / "video.mp4").exists():
                r = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/audio_qc.py"), d.name],
                    capture_output=True, text=True
                )
                if r.returncode != 0:
                    ids.append(d.name)
        print(f"Found {len(ids)} failing videos: {ids}")
    elif args.video_id:
        ids = [args.video_id]
    else:
        ap.print_help()
        sys.exit(1)

    success = 0
    for vid in ids:
        print(f"\n📁 {vid}")
        if repair(vid, args.dry_run):
            success += 1

    print(f"\n{'─'*60}")
    print(f"Repaired: {success}/{len(ids)}")


if __name__ == "__main__":
    main()
