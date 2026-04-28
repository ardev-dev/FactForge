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

PIXABAY_KEY = env.get("PIXABAY_API_KEY", "")

def pixabay_search(query):
    """Pick the highest-quality variant available — large > medium > small.
    Also require min_width=1280 to avoid sub-HD source footage."""
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={urllib.parse.quote(query)}&per_page=5&video_type=film&min_width=1280"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
        for hit in data.get("hits", []):
            # Prefer LARGE (1920+ wide) → MEDIUM (1280) → SMALL (last resort)
            for q in ("large", "medium", "small"):
                v = hit.get("videos", {}).get(q, {})
                u = v.get("url")
                w = v.get("width", 0)
                if u and w >= 1280:
                    return u, w, v.get("height", 0)
        # fallback: any if min_width filter found nothing
        for hit in data.get("hits", []):
            for q in ("large", "medium", "small"):
                u = hit.get("videos", {}).get(q, {}).get("url")
                if u:
                    return u, 0, 0
    except Exception as e:
        logger.warning(f"Pixabay failed '{query}': {e}")
    return None, 0, 0

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
    """Re-encode to 1080x1920 portrait ONLY if dimensions are wrong.
    Pure scale+crop with lanczos (highest-quality scaler). No color filters,
    no sharpening — preserves original colors verbatim. CRF 16 = visually
    lossless threshold.
    """
    w, h = probe_dimensions(path)
    if w == TARGET_W and h == TARGET_H:
        return True
    if not w or not h:
        logger.error(f"  ✗ probe failed: {path.name}")
        return False
    tmp = path.with_suffix(".tmp.mp4")
    # Scale + crop only — no eq, no unsharp, no curves. Preserve source colors.
    vf = f"scale=-2:{TARGET_H}:flags=lanczos,crop={TARGET_W}:{TARGET_H}"
    r = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(path),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "16",            # visually lossless
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-an",
            str(tmp),
        ],
        capture_output=True,
    )
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 5000:
        tmp.replace(path)
        logger.info(f"  ↻ re-scaled {path.name} {w}x{h} → {TARGET_W}x{TARGET_H} (lanczos, no color edits)")
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

    for seg in props["segments"]:
        bg = seg["backgroundVideo"]
        fname = Path(bg).name
        out_path = out_dir / fname
        if out_path.exists() and out_path.stat().st_size > 5000:
            logger.info(f"  skip {fname}")
            continue
        query = seg["scene_query"]
        url = pixabay_search(query)
        if not url:
            alt = " ".join(query.split()[:3])
            url = pixabay_search(alt)
        if url:
            try:
                download(url, out_path)
                ensure_portrait(out_path)
                logger.info(f"  ✓ {fname}: {query[:45]}")
            except Exception as e:
                logger.error(f"  ✗ {fname}: {e}")
        else:
            logger.warning(f"  ⚠ no video: {query[:45]}")
        time.sleep(0.3)

    # Final pass: ensure every existing file is 1080x1920
    for f in out_dir.glob("*.mp4"):
        ensure_portrait(f)

    count = len(list(out_dir.glob("*.mp4")))
    logger.info(f"Done: {count} videos (all 1080x1920)")

if __name__ == "__main__":
    main()
