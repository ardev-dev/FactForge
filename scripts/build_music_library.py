#!/usr/bin/env python3
"""
build_music_library.py — Download Kevin MacLeod CC BY 4.0 tracks for BGM rotation.

License: CC BY 4.0 — commercial use OK with attribution in description.
Attribution string: "Music by Kevin MacLeod (incompetech.com) — CC BY 4.0"

Categories selected to fit Big Industry Exposed niche:
  • dark / cinematic / dramatic   → exposé content
  • investigative / suspense       → corporate fraud / cover-ups
  • inspirational                  → solution chapters
"""
import urllib.request, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/music"
OUT.mkdir(parents=True, exist_ok=True)

# Curated for our niche — all from incompetech.com, all CC BY 4.0
TRACKS = [
    # Dark / Cinematic / Investigative (best for our exposé content)
    "Perspectives.mp3",                        # already have — keep as default
    "Dark Walk.mp3",
    "Hidden Agenda.mp3",
    "Killing Time.mp3",
    "Mystery Sax.mp3",
    "Sneaky Adventure.mp3",
    "Volatile Reaction.mp3",
    "The Path of the Goblin King.mp3",
    "Investigations.mp3",
    "Lurking.mp3",
    # Documentary / informational
    "Cataclysmic Molten Core.mp3",
    "Concentration.mp3",
    "Constance.mp3",
    "Determined Tumbao.mp3",
    "Dramatic Adventure.mp3",
    "Industrial Music Box.mp3",
    "Long Note Two.mp3",
    "Long Note Three.mp3",
    "Severe Tire Damage.mp3",
    "Spy Glass.mp3",
    # Tension / suspense
    "Aggressor.mp3",
    "Crypto.mp3",
    "Heart of the Beast.mp3",
    "Impact Allegretto.mp3",
    "Impact Lento.mp3",
    "Pressure Cooker.mp3",
    "Tension.mp3",
    # Resolution / outro
    "Achievement.mp3",
    "Awake.mp3",
    "Quiet.mp3",
]


def slug(name):
    """Convert track name to URL slug used by incompetech."""
    # incompetech URLs: https://incompetech.com/music/royalty-free/mp3-royaltyfree/Track%20Name.mp3
    return urllib.parse.quote(name) if isinstance(name, str) else name


def download(name):
    out = OUT / name
    if out.exists() and out.stat().st_size > 100_000:
        print(f"  ⏭  {name} (cached)")
        return True
    import urllib.parse
    url = f"https://incompetech.com/music/royalty-free/mp3-royaltyfree/{urllib.parse.quote(name)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if len(data) < 100_000:
            print(f"  ⚠ {name} too small ({len(data)} bytes) — skipping")
            return False
        out.write_bytes(data)
        print(f"  ✓ {name} ({len(data)//1024} KB)")
        return True
    except Exception as e:
        print(f"  ✗ {name}: {str(e)[:80]}")
        return False


def main():
    print(f"📀 Downloading {len(TRACKS)} Kevin MacLeod CC BY 4.0 tracks → {OUT}/")
    print()
    success = 0
    for t in TRACKS:
        if download(t):
            success += 1
        time.sleep(0.5)
    print(f"\n✅ {success}/{len(TRACKS)} tracks ready")
    print(f"\n📜 Required attribution (add to every video description):")
    print(f'   Music by Kevin MacLeod (incompetech.com) — Licensed under CC BY 4.0')
    print(f'   https://creativecommons.org/licenses/by/4.0/')


if __name__ == "__main__":
    main()
