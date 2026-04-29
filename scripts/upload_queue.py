#!/usr/bin/env python3
"""
upload_queue.py — Auto-uploads any video that has video.mp4 + metadata.json
but no youtube_id yet. Idempotent — runs as many times as you want.

Use after reauth_youtube.py. Run once to clear the backlog.

Usage:
  python3 scripts/upload_queue.py              # process all pending
  python3 scripts/upload_queue.py L00600       # one specific
  python3 scripts/upload_queue.py --dry-run    # show what would be uploaded
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# Niche → playlist mapping
PLAYLISTS = {
    "pharma": "PLin03akGsSdZ582q8ntqxDeROE-7xZZ7r",   # Big Pharma Exposed
    "tech":   "PLin03akGsSdbiKgO4RwTW_dHEq_AVa2tW",   # Tech Surveillance
    "corp":   "PLin03akGsSdb4hduHdgPkZmQ4lXkYlSYP",   # Corporate Greed Files
}

PHARMA_KEYWORDS = ["pill", "drug", "pharma", "epipen", "oxycontin", "sackler",
                    "hospital", "medical", "antibiotic", "fda", "purdue"]
TECH_KEYWORDS = ["ai", "openai", "clearview", "surveil", "spy", "data", "privacy",
                 "encryption", "algorithm", "deepfake"]


def pick_playlists(title: str, tags: list, niche: str = ""):
    text = (title + " " + " ".join(tags) + " " + niche).lower()
    out = ["corp"]  # default — everything goes here
    if any(k in text for k in PHARMA_KEYWORDS):
        out.append("pharma")
    if any(k in text for k in TECH_KEYWORDS):
        out.append("tech")
    seen = set()
    return [PLAYLISTS[p] for p in out if not (p in seen or seen.add(p))]


def find_pending():
    """Find video_id directories with video.mp4 + metadata.json but no youtube_id in state."""
    state = json.loads((ROOT / "state/pending_uploads.json").read_text())
    has_yid = {p["id"] for p in state["pending"] if p.get("youtube_id")}

    pending = []
    for d in sorted((ROOT / "output").iterdir()):
        if not d.is_dir(): continue
        if d.name in has_yid: continue
        if not (d / "video.mp4").exists(): continue
        if not (d / "metadata.json").exists(): continue
        pending.append(d.name)
    return pending


def upload_one(yt, vid):
    from googleapiclient.http import MediaFileUpload
    from utils.youtube_helper import get_next_publish_date

    out = ROOT / "output" / vid
    md = json.loads((out / "metadata.json").read_text())
    is_long = vid.startswith("L")
    video_type = "long" if is_long else "short"

    publish_at = get_next_publish_date(video_type)
    title = md.get("title_selected") or md.get("selected_title") or md.get("title", vid)
    description = md.get("description", "")
    tags = md.get("tags", [])

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": md.get("category_id", "27" if is_long else "25"),
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(out / "video.mp4"), mimetype="video/mp4",
                             chunksize=-1, resumable=True)
    print(f"  📤 uploading {vid} ({(out/'video.mp4').stat().st_size//(1024*1024)} MB)...")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    yid = resp["id"]
    print(f"  ✅ {yid} | https://youtu.be/{yid}")

    # Add to playlists
    pls = pick_playlists(title, tags, md.get("niche", ""))
    for pl_id in pls:
        try:
            yt.playlistItems().insert(part="snippet", body={
                "snippet": {
                    "playlistId": pl_id,
                    "resourceId": {"kind": "youtube#video", "videoId": yid},
                }
            }).execute()
        except Exception as e:
            print(f"     ⚠ playlist {pl_id}: {str(e)[:60]}")
    print(f"  📂 added to {len(pls)} playlists")

    # Update state
    state_path = ROOT / "state/pending_uploads.json"
    data = json.loads(state_path.read_text())
    data["pending"].append({
        "id": vid,
        "title": title,
        "video_file": str((out / "video.mp4").relative_to(ROOT)),
        "metadata_file": str((out / "metadata.json").relative_to(ROOT)),
        "youtube_id": yid,
        "publish_at": publish_at,
        "status": "scheduled",
        "type": video_type,
        "scheduled": True,
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return yid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", nargs="?", help="optional — specific id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.video_id:
        targets = [args.video_id]
    else:
        targets = find_pending()

    print(f"🎯 {len(targets)} pending: {targets}")
    if args.dry_run or not targets:
        return

    from utils.youtube_helper import get_youtube_client
    try:
        yt = get_youtube_client()
    except Exception as e:
        print(f"\n❌ OAuth not ready: {str(e)[:120]}")
        print(f"   Run: ! python3 scripts/reauth_youtube.py")
        sys.exit(1)

    success = 0
    for vid in targets:
        print(f"\n─── {vid} ───")
        try:
            upload_one(yt, vid)
            success += 1
        except Exception as e:
            print(f"  ❌ {str(e)[:200]}")

    print(f"\n━━━ {success}/{len(targets)} uploaded ━━━")


if __name__ == "__main__":
    main()
