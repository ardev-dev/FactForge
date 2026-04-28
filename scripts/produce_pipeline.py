#!/usr/bin/env python3
"""
produce_pipeline.py — End-to-end short video production pipeline.

Glues together every step that was previously manual:
  1. generate_audio.py        (TTS via Kokoro)
  2. inject 2.75s intro silence  (aligns audio with hero+flash visuals)
  3. build remotion_props.json  (segments + word_timestamps)
  4. fetch_bg_all.py            (download + portrait + lossless re-encode)
  5. copy assets to public/
  6. render_short.py            (Remotion + ffmpeg copy — original colors)
  7. audio_repair.py            (BGM bed + intro SFX swell)
  8. LUFS normalize to -14
  9. audio_qc.py                (final QC gate — exits non-zero on fail)

Pre-conditions:
  • output/[id]/script.json exists (with hero + flash + narration segments)
  • output/[id]/research.json exists

Post-conditions:
  • output/[id]/video.mp4 ready to upload
  • passes audio_qc.py with no issues

Usage:
  python3 scripts/produce_pipeline.py S02901
"""
import argparse, json, math, re, subprocess, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTRO_SILENCE_S = 2.75   # 165 frames at 60fps = hero(15) + 5 flashes(150)
FPS = 60


def run(cmd, **kwargs):
    """Run command, raise if it fails."""
    r = subprocess.run(cmd, **kwargs)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(str(c) for c in cmd[:3])}...")
    return r


def step(label):
    print(f"\n{'━'*70}\n▶  {label}\n{'━'*70}")


def step_audio(vid):
    step("[1/9] Generating audio (Kokoro TTS + humanizer)")
    run([sys.executable, str(ROOT / "scripts/generate_audio.py"), vid])


def step_intro_silence(vid):
    step("[2/9] Prepending 2.75s intro silence")
    out = ROOT / "output" / vid
    audio = out / "audio.mp3"
    bak = out / "audio_no_intro.mp3"
    if not audio.exists():
        raise FileNotFoundError(f"audio.mp3 missing for {vid}")
    shutil.copy(audio, bak)
    tmp = out / "audio_with_intro.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", str(INTRO_SILENCE_S), "-i", "anullsrc=r=24000:cl=mono",
        "-i", str(bak),
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
        "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", str(tmp),
    ], capture_output=True, check=True)
    tmp.replace(audio)
    # Shift word_timestamps
    wt_path = out / "word_timestamps.json"
    if wt_path.exists():
        words = json.loads(wt_path.read_text())
        shift = int(INTRO_SILENCE_S * 1000)
        for w in words:
            w["start_ms"] += shift
            w["end_ms"] += shift
        wt_path.write_text(json.dumps(words, indent=2, ensure_ascii=False))
    print(f"  ✓ intro silence prepended, word_timestamps shifted")


def step_props(vid):
    step("[3/9] Building remotion_props.json")
    out = ROOT / "output" / vid
    script = json.loads((out / "script.json").read_text())
    words = json.loads((out / "word_timestamps.json").read_text())

    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(out / "audio.mp3")],
        capture_output=True, text=True, check=True,
    )
    audio_dur = float(json.loads(r.stdout)["format"]["duration"])
    total_frames = math.ceil(audio_dur * FPS)

    intro_segs = [s for s in script["segments"] if s.get("type") in ("hero", "flash")]
    narration_segs = [s for s in script["segments"] if s.get("type") not in ("hero", "flash")]

    def normalize(t):
        return re.sub(r"[^\w\s]", "", t.lower()).split()

    segments_out, cur_frame, flash_idx = [], 0, 0
    for seg in intro_segs:
        df = seg.get("durationFrames", 30)
        bg = (
            f"{vid}/bg_videos/hero_00.mp4" if seg["type"] == "hero"
            else f"{vid}/bg_videos/flash_{flash_idx:02d}.mp4"
        )
        if seg["type"] != "hero":
            flash_idx += 1
        segments_out.append({
            **{k: v for k, v in seg.items() if k != "durationFrames"},
            "startFrame": cur_frame,
            "endFrame": cur_frame + df,
            "backgroundVideo": bg,
        })
        cur_frame += df

    word_idx = 0
    for i, seg in enumerate(narration_segs):
        seg_words = normalize(seg["text"])
        if not seg_words:
            continue
        start_ms = words[word_idx]["start_ms"] if word_idx < len(words) else 0
        for w in seg_words:
            while word_idx < len(words):
                wt = re.sub(r"[^\w]", "", words[word_idx]["word"].lower())
                if wt.startswith(w[:3]) or w.startswith(wt[:3]):
                    break
                word_idx += 1
            if word_idx < len(words):
                word_idx += 1
        end_ms = (
            words[word_idx - 1]["end_ms"]
            if word_idx > 0 and word_idx - 1 < len(words)
            else start_ms + 1500
        )
        start_f = math.floor(start_ms * FPS / 1000)
        end_f = math.ceil(end_ms * FPS / 1000)
        if start_f < cur_frame:
            start_f = cur_frame
        if end_f <= start_f:
            end_f = start_f + 60
        segments_out.append({
            **seg,
            "startFrame": start_f,
            "endFrame": end_f,
            "backgroundVideo": f"{vid}/bg_videos/seg_{i:02d}.mp4",
        })
        cur_frame = end_f

    if segments_out and segments_out[-1]["endFrame"] < total_frames:
        segments_out[-1]["endFrame"] = total_frames

    props = {
        "videoId": vid,
        "categoryLabel": script.get("categoryLabel", "BIG INDUSTRY EXPOSED"),
        "colorTheme": script.get("colorTheme", "shocking"),
        "totalDurationFrames": total_frames,
        "audioFile": f"{vid}/audio.mp3",
        "backgroundVideoUrl": None,
        "segments": segments_out,
        "wordTimestamps": words,
        "scale": 1,
    }
    (out / "remotion_props.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))
    print(f"  ✓ {len(segments_out)} segments | {total_frames} frames ({audio_dur:.1f}s)")


def step_bg(vid):
    step("[4/9] Fetching background videos (Pixabay HD + portrait)")
    run([sys.executable, str(ROOT / "scripts/fetch_bg_all.py"), vid])


def step_copy_public(vid):
    step("[5/9] Copying assets to Remotion public/")
    src_dir = ROOT / "output" / vid
    dst_dir = ROOT / "video/remotion-project/public" / vid
    bg_dst = dst_dir / "bg_videos"
    bg_dst.mkdir(parents=True, exist_ok=True)
    for f in (src_dir / "bg_videos").glob("*.mp4"):
        shutil.copy(f, bg_dst / f.name)
    shutil.copy(src_dir / "audio.mp3", dst_dir / "audio.mp3")
    print(f"  ✓ {len(list(bg_dst.glob('*.mp4')))} bg_videos + audio.mp3")


def step_render(vid):
    step("[6/9] Remotion render (lossless audio merge)")
    run([sys.executable, str(ROOT / "scripts/render_short.py"), vid])


def step_audio_repair(vid):
    step("[7/9] Audio repair — BGM bed + intro SFX swell")
    run([sys.executable, str(ROOT / "scripts/audio_repair.py"), vid])


def step_lufs(vid):
    step("[8/9] LUFS normalize to -14 (YouTube broadcast standard)")
    src = ROOT / "output" / vid / "video.mp4"
    tmp = ROOT / "output" / vid / "video_norm.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", str(tmp),
    ], capture_output=True, check=True)
    tmp.replace(src)
    print(f"  ✓ LUFS normalized")


def step_qc(vid):
    step("[9/9] Audio QC gate")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/audio_qc.py"), vid])
    if r.returncode != 0:
        raise RuntimeError(f"QC FAILED for {vid} — fix before upload")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--skip-audio", action="store_true", help="skip TTS (audio.mp3 already exists)")
    ap.add_argument("--skip-bg", action="store_true", help="skip bg downloads")
    args = ap.parse_args()

    vid = args.video_id
    out = ROOT / "output" / vid
    if not (out / "script.json").exists():
        print(f"❌ output/{vid}/script.json missing")
        sys.exit(1)

    if not args.skip_audio:
        step_audio(vid)
        step_intro_silence(vid)
    step_props(vid)
    if not args.skip_bg:
        step_bg(vid)
    step_copy_public(vid)
    step_render(vid)
    step_audio_repair(vid)
    step_lufs(vid)
    step_qc(vid)

    print(f"\n{'═'*70}\n✅ {vid} ready for upload — output/{vid}/video.mp4\n{'═'*70}")


if __name__ == "__main__":
    main()
