#!/usr/bin/env python3
"""
generate_thumbnail.py — Generate YouTube thumbnail for long videos.

YouTube allows custom thumbnails for long videos (NOT for Shorts).
This composes:
  • Background image: Pollinations Flux (free, commercial OK per their TOS)
  • Bold text overlay (PIL): two-number contrast title fragment
  • Channel branding strip: small "THE FACT DROP" lower right

Output: output/[id]/thumbnail.jpg (1280x720 YouTube spec)

Usage:
  python3 scripts/generate_thumbnail.py L00800
  python3 scripts/generate_thumbnail.py L00800 --upload   # also push to YouTube
"""
import argparse, json, sys, urllib.request, urllib.parse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent

# YouTube spec: 1280×720, max 2 MB, JPG/PNG
W, H = 1280, 720


def fetch_pollinations(prompt: str, out_path: Path, seed=None):
    """Free, commercial-OK image generation."""
    if seed is None:
        seed = abs(hash(prompt)) % 99999
    enc = urllib.parse.quote(prompt + " cinematic dramatic 4K photorealistic")
    url = f"https://image.pollinations.ai/prompt/{enc}?width={W}&height={H}&nologo=true&model=flux&seed={seed}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if len(data) < 5000:
            return False
        out_path.write_bytes(data)
        return True
    except Exception as e:
        print(f"  ✗ Pollinations failed: {e}")
        return False


def find_font(size, bold=True):
    """Find a bold display font on the system."""
    candidates_bold = [
        # macOS
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Black.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates_bold:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def extract_thumbnail_text(title: str) -> tuple[str, str]:
    """Pick two strong text fragments from title for thumbnail.
    Top line: shock fragment. Bottom line: contrast fragment."""
    # Try two-number split: "X to Make. They Charge $Y"
    if "." in title:
        parts = [p.strip() for p in title.split(".") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1].split("#")[0].strip()
    # Try em-dash split
    if " — " in title:
        a, b = title.split(" — ", 1)
        return a.strip(), b.split("#")[0].strip()
    # Fallback: first half + second half
    words = title.replace("#shorts", "").split()
    half = len(words) // 2
    return " ".join(words[:half]), " ".join(words[half:])


def wrap_text(text: str, font, draw, max_width: int) -> list[str]:
    """Naive word-wrap by measured pixel width."""
    words = text.split()
    lines, line = [], []
    for w in words:
        test = " ".join(line + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and line:
            lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    return lines


def compose(bg_path: Path, top_text: str, bottom_text: str, accent="#FF3366") -> Image.Image:
    """Compose final thumbnail."""
    bg = Image.open(bg_path).convert("RGB")
    bg = bg.resize((W, H), Image.LANCZOS)

    # Darken bottom for text legibility
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Vignette gradient: dark bottom 60%
    for y in range(H):
        alpha = int(180 * max(0, (y - H * 0.4) / (H * 0.6)) ** 1.5)
        od.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(bg)

    # Top text — large, accent-colored
    top_font = find_font(96)
    top_lines = wrap_text(top_text.upper(), top_font, draw, W - 100)
    y = 60
    for line in top_lines:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        # Black stroke + accent fill for impact
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-3,-3),(3,3),(-3,3),(3,-3)]:
            draw.text((x+dx, y+dy), line, fill="black", font=top_font)
        draw.text((x, y), line, fill=accent, font=top_font)
        y += bbox[3] - bbox[1] + 12

    # Bottom text — white, large, centered in lower third
    bot_font = find_font(80)
    bot_lines = wrap_text(bottom_text.upper(), bot_font, draw, W - 100)
    y = H - (len(bot_lines) * 95) - 80
    for line in bot_lines:
        bbox = draw.textbbox((0, 0), line, font=bot_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-3,-3),(3,3),(-3,3),(3,-3)]:
            draw.text((x+dx, y+dy), line, fill="black", font=bot_font)
        draw.text((x, y), line, fill="white", font=bot_font)
        y += bbox[3] - bbox[1] + 8

    # Channel watermark — bottom right
    wm_font = find_font(28)
    wm_text = "THE FACT DROP"
    bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_w = bbox[2] - bbox[0]
    draw.text((W - wm_w - 30, H - 50), wm_text, fill=accent, font=wm_font)

    return bg


def generate(video_id: str, upload: bool = False):
    out_dir = ROOT / "output" / video_id
    md_path = out_dir / "metadata.json"
    if not md_path.exists():
        print(f"❌ {md_path} missing")
        sys.exit(1)
    md = json.loads(md_path.read_text())
    title = md.get("title_selected") or md.get("selected_title") or md.get("title", "")

    # Get bg from images/ if exists, else fetch from Pollinations
    bg_path = out_dir / "thumbnail_bg.jpg"
    if not bg_path.exists():
        # Try to use chapter 1 image first
        ch_a = out_dir / "images/ch1_A.jpg"
        if ch_a.exists():
            bg_path = ch_a
            print(f"  ✓ using existing ch1_A.jpg as background")
        else:
            # Fetch fresh from Pollinations using the topic
            print(f"  🎨 fetching Pollinations background...")
            prompt = title.split("—")[0].split(".")[0][:80] + " dramatic cinematic dark background"
            if not fetch_pollinations(prompt, bg_path):
                print("  ❌ background generation failed")
                sys.exit(1)

    top, bot = extract_thumbnail_text(title)
    print(f"  Top: {top}")
    print(f"  Bot: {bot}")

    img = compose(bg_path, top, bot)
    out_path = out_dir / "thumbnail.jpg"
    img.save(out_path, "JPEG", quality=92)
    size_kb = out_path.stat().st_size // 1024
    print(f"  ✅ {out_path} ({size_kb} KB)")

    if upload:
        # Push to YouTube
        sys.path.insert(0, str(ROOT))
        from utils.youtube_helper import get_youtube_client
        from googleapiclient.http import MediaFileUpload

        # Find youtube_id from state
        state = json.loads((ROOT / "state/pending_uploads.json").read_text())
        item = next((p for p in state["pending"] if p["id"] == video_id), None)
        if not item or not item.get("youtube_id"):
            print(f"  ⚠ no youtube_id for {video_id} — skipping upload")
            return
        yid = item["youtube_id"]
        yt = get_youtube_client()
        try:
            yt.thumbnails().set(
                videoId=yid,
                media_body=MediaFileUpload(str(out_path), mimetype="image/jpeg"),
            ).execute()
            print(f"  📺 thumbnail set on YouTube video {yid}")
        except Exception as e:
            print(f"  ❌ YouTube upload failed: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--upload", action="store_true",
                    help="also push to YouTube via thumbnails.set")
    args = ap.parse_args()
    generate(args.video_id, args.upload)


if __name__ == "__main__":
    main()
