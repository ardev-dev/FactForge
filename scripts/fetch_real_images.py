#!/usr/bin/env python3
"""
fetch_real_images.py — Get REAL public-domain images for documentaries.

Pollinations Flux generates plausible images but they're not real photos.
For credibility on factual content, we want actual archival photos when
possible. This fetches from:
  • Wikimedia Commons (public domain or free CC license)
  • Pixabay images API (Pixabay License — free commercial)

Both are commercial-OK without attribution required.

Usage:
  python3 scripts/fetch_real_images.py "John Rockefeller Standard Oil"
  python3 scripts/fetch_real_images.py "Boeing 737 MAX cockpit" --out output/L00800/images/real_01.jpg
"""
import argparse, json, sys, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load Pixabay key (already in .env)
ENV = {}
env_file = ROOT / "config/.env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()


def wikimedia_search(query: str) -> list:
    """Returns list of image URLs from Wikimedia Commons.
    All results are PD or freely licensed — verify per use."""
    api = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size",
        "iiurlwidth": 1920,
    }
    url = api + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "FactForge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        print(f"Wikimedia error: {e}")
        return []

    pages = data.get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        meta = info.get("extmetadata", {})
        license_short = meta.get("LicenseShortName", {}).get("value", "Unknown")
        # Prefer PD, CC0, CC-BY (commercial OK)
        if any(t in license_short.lower() for t in ["public", "cc0", "cc-by", "no rights"]):
            results.append({
                "url": url,
                "title": page.get("title", ""),
                "license": license_short,
                "width": info.get("width", 0),
                "height": info.get("height", 0),
            })
    return results


def pixabay_image_search(query: str) -> list:
    """Pixabay images — Pixabay License (free commercial, no attribution needed)."""
    key = ENV.get("PIXABAY_API_KEY")
    if not key:
        return []
    url = (
        f"https://pixabay.com/api/?key={key}"
        f"&q={urllib.parse.quote(query)}"
        f"&image_type=photo&min_width=1280&safesearch=true&per_page=10"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        print(f"Pixabay error: {e}")
        return []
    return [
        {
            "url": h["largeImageURL"],
            "title": h.get("tags", ""),
            "license": "Pixabay (commercial OK)",
            "width": h.get("imageWidth", 0),
            "height": h.get("imageHeight", 0),
        }
        for h in data.get("hits", [])
    ]


def fetch(query: str, out: Path, prefer="wikimedia") -> bool:
    sources = (
        [wikimedia_search, pixabay_image_search]
        if prefer == "wikimedia"
        else [pixabay_image_search, wikimedia_search]
    )
    for fn in sources:
        results = fn(query)
        for r in results:
            try:
                req = urllib.request.Request(r["url"], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                if len(data) < 5000:
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(data)
                print(f"  ✓ {out.name}: {r['title'][:50]} ({r['license']}) {len(data)//1024}KB")
                return True
            except Exception as e:
                continue
    print(f"  ✗ no results for: {query}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--out", type=Path, default=Path("/tmp/fetched.jpg"))
    ap.add_argument("--source", choices=["wikimedia", "pixabay"], default="wikimedia")
    args = ap.parse_args()

    if fetch(args.query, args.out, prefer=args.source):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
