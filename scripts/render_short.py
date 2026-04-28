"""
render_short.py — Render a ShortVideo composition (1080x1920, 30fps)
Usage: python3 scripts/render_short.py S01220
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REMOTION_DIR = ROOT / "video/remotion-project"

def render(video_id: str):
    out_dir = ROOT / "output" / video_id
    props_file = out_dir / "remotion_props.json"

    if not props_file.exists():
        print(f"❌ No remotion_props.json found for {video_id}")
        sys.exit(1)

    with open(props_file) as f:
        props = json.load(f)

    total_frames = props["totalDurationFrames"]
    print(f"Rendering {video_id}: {total_frames} frames @ 60fps ({total_frames/60:.1f}s)")

    noaudio_path = out_dir / "video_noaudio.mp4"
    final_path   = out_dir / "video.mp4"
    audio_path   = out_dir / "audio.mp3"

    # Step 1: Remotion render (no audio)
    print("\n[1/2] Remotion render (ShortVideo)...")
    render_cmd = [
        "npx", "remotion", "render",
        "ShortVideo",
        str(noaudio_path),
        f"--props={props_file}",
        f"--frames=0-{total_frames - 1}",
        "--codec=h264",
        "--crf=18",
        "--pixel-format=yuv420p",
        "--concurrency=1",
    ]

    result = subprocess.run(render_cmd, cwd=REMOTION_DIR, capture_output=False, timeout=1800)
    if result.returncode != 0:
        print("❌ Remotion render failed")
        sys.exit(1)

    print("\n[2/2] FFmpeg audio merge + cinematic color grade...")
    # Color grade chain (vivid, broadcast-style):
    #   eq:        +5% saturation, +3% contrast, +2% brightness
    #   vibrance:  push under-saturated colors without crushing skin tones
    #   unsharp:   recover detail lost in any prior re-encoding
    #   curves:    slight S-curve for cinematic punch
    color_chain = (
        "eq=saturation=1.15:contrast=1.06:brightness=0.02,"
        "vibrance=intensity=0.25,"
        "unsharp=5:5:0.8:5:5:0.0,"
        "curves=master='0/0 0.25/0.22 0.75/0.78 1/1'"
    )
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(noaudio_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", color_chain,
        "-c:v", "libx264",
        "-crf", "17",            # was 18 — slightly higher quality
        "-preset", "slow",
        "-profile:v", "high",
        "-level", "4.2",
        "-pix_fmt", "yuv420p",
        "-maxrate", "20M",
        "-bufsize", "40M",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        str(final_path),
    ]

    result = subprocess.run(ffmpeg_cmd, capture_output=False, timeout=600)
    if result.returncode != 0:
        print("❌ FFmpeg failed")
        sys.exit(1)

    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(final_path)],
        capture_output=True, text=True
    )
    info = json.loads(r.stdout)
    dur = float(info["format"]["duration"])
    size_mb = int(info["format"]["size"]) // (1024 * 1024)
    vstream = next(s for s in info["streams"] if s["codec_type"] == "video")
    print(f"\n✅ {final_path.name}")
    print(f"   Duration: {dur:.1f}s")
    print(f"   Size: {size_mb} MB")
    print(f"   Resolution: {vstream['width']}×{vstream['height']}")
    print(f"   Bitrate: {int(info['format']['bit_rate'])//1000} kbps")

if __name__ == "__main__":
    vid = sys.argv[1] if len(sys.argv) > 1 else "S01220"
    render(vid)
