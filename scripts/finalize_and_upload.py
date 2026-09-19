"""
finalize_and_upload.py — Merge audio into rendered video, then upload to YouTube.
Uses utils/youtube_helper.py for all YouTube API calls.

Usage: python3 scripts/finalize_and_upload.py <video_id>
"""
import json, subprocess, sys, logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.youtube_helper import (
    upload_video, upload_caption,
    get_next_publish_date, update_state_after_upload
)
from scripts.generate_subtitles import generate_subtitles


def merge_audio(video_id: str) -> Path:
    """Merge voice audio into rendered video using FFmpeg (CRF 18, high quality)."""
    out_dir = ROOT / "output" / video_id
    noaudio = out_dir / "video_noaudio.mp4"
    audio   = out_dir / "audio.mp3"
    output  = out_dir / "video.mp4"

    if not noaudio.exists():
        logger.error("%s not found", noaudio); return None
    if not audio.exists():
        logger.error("%s not found", audio); return None

    cmd = [
        "ffmpeg", "-y",
        "-i", str(noaudio),
        "-i", str(audio),
        "-map", "0:v:0",      # video from noaudio
        "-map", "1:a:0",      # audio from audio.mp3 (explicit — prevents silent video)
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-maxrate", "20M",
        "-bufsize", "40M",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg error:\n%s", result.stderr[-500:])
        return None
    size_mb = output.stat().st_size // 1024 // 1024
    logger.info("Merged: %s (%dMB)", output.name, size_mb)
    return output


def upload(video_id: str) -> str:
    """Full upload pipeline: merge → YouTube upload → subtitles → state."""
    out_dir  = ROOT / "output" / video_id
    meta_file = out_dir / "metadata.json"
    is_long  = video_id.startswith("L")

    if not meta_file.exists():
        logger.error("metadata.json not found for %s", video_id); return None

    meta = json.loads(meta_file.read_text())
    title = meta.get("selected_title") or meta.get("title_selected") or meta.get("title", "")
    desc  = meta.get("description", "")
    tags  = meta.get("tags", [])

    # AI disclosure — required by YouTube 2026 algorithm to avoid suppression
    AI_DISCLOSURE = "\n\n🤖 Narration generated with AI voice technology. All facts are verified from official sources."
    if "AI voice" not in desc:
        desc = desc + AI_DISCLOSURE

    # Playlist link — drives session continuation (watch time chain strategy)
    PLAYLIST_URL = "https://youtube.com/playlist?list=PLin03akGsSdYSIoi1NsJNn-FIIv0jl5dJ"
    PLAYLIST_LINE = f"\n▶️ Watch more exposés: {PLAYLIST_URL}"
    if PLAYLIST_URL not in desc:
        desc = desc + PLAYLIST_LINE
    cat   = meta.get("category_id", "27")

    # Determine scheduled publish date
    publish_at = get_next_publish_date("long" if is_long else "short")
    logger.info("Scheduled publish: %s", publish_at)

    # Upload video
    video_path = out_dir / "video.mp4"
    if not video_path.exists():
        logger.error("video.mp4 not found — run render first"); return None

    yt_id = upload_video(
        video_path=video_path,
        title=title,
        description=desc,
        tags=tags,
        category_id=cat,
        publish_at=publish_at,
        privacy="private",
    )
    if not yt_id:
        logger.error("Upload failed"); return None

    # Subtitles — generate if not yet done (needs word_timestamps.json)
    srt_dir = out_dir / "subtitles"
    ts_path = out_dir / "word_timestamps.json"
    if ts_path.exists() and (not srt_dir.exists() or not any(srt_dir.glob("*.srt"))):
        logger.info("Generating subtitles (7 languages)...")
        generate_subtitles(video_id)

    # Subtitles (7 languages if available)
    if srt_dir.exists():
        lang_names = {"en":"English","ar":"Arabic","es":"Spanish","fr":"French",
                      "hi":"Hindi","pt":"Portuguese","tr":"Turkish"}
        for srt_file in sorted(srt_dir.glob("*.srt")):
            lang = srt_file.stem.split("_")[-1]
            if lang in lang_names:
                ok = upload_caption(yt_id, srt_file, lang, lang_names[lang])
                if ok:
                    logger.info("Subtitles %s uploaded", lang)
                else:
                    logger.warning("Subtitles %s upload failed", lang)

    # Update state
    video_type = "long" if is_long else "short"
    update_state_after_upload(video_id, yt_id, publish_at, title, video_type)

    logger.info("%s → https://youtu.be/%s  (publishes %s)", video_id, yt_id, publish_at)
    return yt_id


if __name__ == "__main__":
    video_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not video_id:
        print("Usage: python3 scripts/finalize_and_upload.py <video_id>")
        sys.exit(1)

    is_long = video_id.startswith("L")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    logger.info("=" * 50)
    logger.info("Finalizing %s", video_id)
    logger.info("=" * 50)

    # Merge only if video_noaudio exists (render was done separately)
    out_dir = ROOT / "output" / video_id
    if (out_dir / "video_noaudio.mp4").exists() and not (out_dir / "video.mp4").exists():
        logger.info("[1/2] Merging audio...")
        if not merge_audio(video_id):
            sys.exit(1)

    logger.info("[2/2] Uploading to YouTube...")
    yt_id = upload(video_id)
    if not yt_id:
        sys.exit(1)
