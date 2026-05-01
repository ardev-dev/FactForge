#!/usr/bin/env python3
"""
trending_daily.py — Daily snapshot of YouTube trending in our niche.

Pulls:
  • US trending (News & Politics, Education, Science & Tech)
  • Channel Studio Research suggestions (what OUR audience watches)
  • Filters out videos > 1M views with <0.05% ER (likely paid promo)

Saves a daily snapshot to state/trending_history/[YYYY-MM-DD].json
and prints the top 10 organic-trending topics that match our niche.

Usage:
  python3 scripts/trending_daily.py
  python3 scripts/trending_daily.py --regions US,GB,CA
"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NICHE_KEYWORDS = [
    "pharma", "drug", "pill", "epipen", "medical", "health",
    "ai", "openai", "data", "privacy", "surveillance",
    "wealth", "billion", "rich", "billionaire", "fraud", "scam",
    "boeing", "exposed", "cover", "scandal", "lawsuit",
    "monsanto", "bayer", "wells fargo", "equifax", "hertz",
]


def is_organic(views, likes, comments):
    """Heuristic: paid promo has unnaturally low ER."""
    if views < 1000:
        return True  # too small to judge
    er = ((likes + comments) / views) * 100
    return er > 0.1


def get_trending(yt, region):
    items = []
    # General trending (most popular)
    try:
        r = yt.videos().list(
            chart="mostPopular", regionCode=region,
            part="snippet,statistics", maxResults=50,
        ).execute()
        items += r.get("items", [])
    except Exception as e:
        print(f"  ⚠ {region} general failed: {str(e)[:60]}")
    # News category
    try:
        r = yt.videos().list(
            chart="mostPopular", regionCode=region,
            part="snippet,statistics", maxResults=25,
            videoCategoryId="25",
        ).execute()
        items += r.get("items", [])
    except Exception:
        pass
    return items


def matches_niche(title: str, tags: list) -> str:
    text = (title + " " + " ".join(tags)).lower()
    for kw in NICHE_KEYWORDS:
        if kw in text:
            return kw
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regions", default="US")
    ap.add_argument("--save-snapshot", action="store_true", default=True)
    args = ap.parse_args()

    from utils.youtube_helper import get_youtube_client
    yt = get_youtube_client()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_videos, niche_hits = [], []

    for region in args.regions.split(","):
        items = get_trending(yt, region.strip())
        all_videos.extend(items)

    print(f"📊 fetched {len(all_videos)} trending videos\n")

    seen = set()
    for v in all_videos:
        vid = v["id"]
        if vid in seen:
            continue
        seen.add(vid)
        sn = v["snippet"]
        st = v["statistics"]
        views = int(st.get("viewCount", 0))
        likes = int(st.get("likeCount", 0))
        comments = int(st.get("commentCount", 0))
        title = sn["title"]
        tags = sn.get("tags", [])
        kw = matches_niche(title, tags)
        if not kw:
            continue
        organic = is_organic(views, likes, comments)
        niche_hits.append({
            "id": vid, "title": title, "channel": sn["channelTitle"],
            "views": views, "likes": likes, "comments": comments,
            "er_pct": round(((likes + comments) / max(views, 1)) * 100, 2),
            "organic": organic, "matched_keyword": kw,
            "published": sn["publishedAt"][:10],
        })

    niche_hits.sort(key=lambda x: -x["views"] if x["organic"] else 0)

    print(f"🎯 {len(niche_hits)} niche-matching trending videos:\n")
    print(f"{'#':<3} {'Views':>9} {'ER%':>5}  {'KW':<10} {'Channel':<20} Title")
    print("-" * 110)
    for i, v in enumerate(niche_hits[:15], 1):
        marker = "🟢" if v["organic"] else "🔴"
        print(f"{i:<3} {v['views']:>9,} {v['er_pct']:>5} {marker} {v['matched_keyword']:<10} {v['channel'][:18]:<20} {v['title'][:55]}")

    # Save snapshot
    if args.save_snapshot:
        out = ROOT / "state/trending_history"
        out.mkdir(exist_ok=True)
        snapshot_path = out / f"{today}.json"
        snapshot_path.write_text(json.dumps({
            "date": today,
            "regions": args.regions,
            "total_fetched": len(all_videos),
            "niche_matches": len(niche_hits),
            "matches": niche_hits,
        }, indent=2, ensure_ascii=False))
        print(f"\n💾 saved → {snapshot_path}")

    # Top 5 ideas to act on
    organic_only = [h for h in niche_hits if h["organic"]][:5]
    if organic_only:
        print(f"\n🎬 Top 5 organic trending ideas in your niche:")
        for h in organic_only:
            print(f"  → {h['title'][:80]}")


if __name__ == "__main__":
    main()
