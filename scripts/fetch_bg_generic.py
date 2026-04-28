#!/usr/bin/env python3
import json, os, sys, time, subprocess, urllib.request, urllib.parse
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VIDEO_ID = sys.argv[1]
BASE = Path(__file__).parent.parent

TARGET_W, TARGET_H = 1080, 1920

dotenv = BASE / "config/.env"
env = {}
for line in dotenv.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

PEXELS_KEY  = env.get("PEXELS_API_KEY", "")
PIXABAY_KEY = env.get("PIXABAY_API_KEY", "")

def pexels_search(query):
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=5&orientation=portrait&size=medium"
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_KEY})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        for v in data.get("videos", []):
            for f in v.get("video_files", []):
                if f.get("quality") in ("hd","sd") and f.get("width",0) <= 1080:
                    return f["link"]
    except Exception as e:
        logger.warning(f"Pexels failed '{query}': {e}")
    return None

def pixabay_search(query):
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={urllib.parse.quote(query)}&per_page=5&video_type=film"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
        for hit in data.get("hits", []):
            for q in ("medium","small","large"):
                u = hit.get("videos",{}).get(q,{}).get("url")
                if u:
                    return u
    except Exception as e:
        logger.warning(f"Pixabay failed '{query}': {e}")
    return None

def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out_path.write_bytes(r.read())


def probe_dimensions(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True,
    )
    try:
        streams = json.loads(r.stdout).get("streams", [])
        v = next(s for s in streams if s["codec_type"] == "video")
        return int(v["width"]), int(v["height"])
    except Exception:
        return None, None


def ensure_portrait(path):
    w, h = probe_dimensions(path)
    if w == TARGET_W and h == TARGET_H:
        return True
    if not w or not h:
        logger.error(f"  ✗ probe failed: {path.name}")
        return False
    tmp = path.with_suffix(".tmp.mp4")
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(path),
            "-vf", f"scale=-2:{TARGET_H}:flags=lanczos,crop={TARGET_W}:{TARGET_H}",
            "-c:v", "libx264", "-crf", "16", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-an",
            str(tmp),
        ],
        capture_output=True,
    )
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 5000:
        tmp.replace(path)
        logger.info(f"  ↻ re-encoded {path.name} {w}x{h} → {TARGET_W}x{TARGET_H}")
        return True
    if tmp.exists():
        tmp.unlink()
    logger.error(f"  ✗ re-encode failed: {path.name}")
    return False

def main():
    with open(BASE / f"output/{VIDEO_ID}/remotion_props.json") as f:
        props = json.load(f)
    out_dir = BASE / f"output/{VIDEO_ID}/bg_videos"
    out_dir.mkdir(exist_ok=True)

    segments = props["segments"]
    used = {}
    for i, seg in enumerate(segments):
        out_path = out_dir / f"seg_{i:02d}.mp4"
        if out_path.exists():
            logger.info(f"  ✓ seg_{i:02d} already exists")
            continue
        query = seg["scene_query"]
        url = pexels_search(query) or pixabay_search(query)
        if url and url in used.values():
            alt = query.split()[0] + " " + query.split()[-1]
            url = pexels_search(alt) or pixabay_search(alt) or url
        if url:
            try:
                download(url, out_path)
                ensure_portrait(out_path)
                used[i] = url
                logger.info(f"  ✓ seg_{i:02d}: {query[:40]}")
            except Exception as e:
                logger.error(f"  ✗ seg_{i:02d} download failed: {e}")
        else:
            logger.warning(f"  ⚠ seg_{i:02d} no video found for: {query}")
        time.sleep(0.3)

    for f in out_dir.glob("*.mp4"):
        ensure_portrait(f)

    logger.info(f"Done. {len(list(out_dir.glob('*.mp4')))} videos in {out_dir} (all 1080x1920)")

if __name__ == "__main__":
    main()
