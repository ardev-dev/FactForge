#!/usr/bin/env python3
"""
reupload_fixed.py — Re-upload videos that were repaired locally.

For each video flagged with `needs_reupload_audio_fix=true`:
  1. Read its current YouTube ID + scheduled publishAt
  2. Delete the old video from YouTube
  3. Upload the locally-repaired video.mp4
  4. Restore the same metadata (title with hashtags, description, tags)
  5. Restore the same publishAt schedule
  6. Update pending_uploads.json with new YouTube ID

Usage:
  python3 scripts/reupload_fixed.py                  # process all flagged
  python3 scripts/reupload_fixed.py S02500           # one specific
  python3 scripts/reupload_fixed.py --max 2          # only 2 (quota safety)
  python3 scripts/reupload_fixed.py --no-captions    # skip caption uploads (saves 2800 units/video)
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.youtube_helper import get_youtube_client
from googleapiclient.http import MediaFileUpload


def reupload_one(yt, item, upload_captions=True):
    vid = item['id']
    old_yid = item.get('youtube_id')
    if not old_yid:
        print(f"  ⚠ {vid}: no youtube_id")
        return None

    video_path = ROOT / "output" / vid / "video.mp4"
    metadata_path = ROOT / "output" / vid / "metadata.json"
    if not video_path.exists():
        print(f"  ❌ {vid}: video.mp4 missing")
        return None

    # Get current YT metadata so we keep title/description/tags exactly
    cur = yt.videos().list(id=old_yid, part="snippet,status").execute()
    if not cur.get('items'):
        print(f"  ⚠ {vid}: old video {old_yid} not found on YouTube — skipping delete, just uploading")
        snippet, status = None, None
    else:
        snippet = cur['items'][0]['snippet']
        status = cur['items'][0]['status']

    # Delete old
    if snippet:
        try:
            yt.videos().delete(id=old_yid).execute()
            print(f"  🗑  deleted old: {old_yid}")
        except Exception as e:
            print(f"  ⚠ delete failed (proceeding anyway): {str(e)[:100]}")

    # Build snippet for new upload — preserve everything including hashtags
    if snippet:
        new_snippet = {
            'title': snippet['title'],
            'description': snippet.get('description', ''),
            'tags': snippet.get('tags', []),
            'categoryId': snippet.get('categoryId', '24'),
        }
    else:
        # Fallback to local metadata
        md = json.load(open(metadata_path))
        new_snippet = {
            'title': md.get('title_selected') or md.get('title') or vid,
            'description': md.get('description', ''),
            'tags': md.get('tags', []),
            'categoryId': md.get('category_id', '24'),
        }

    new_status = {
        'privacyStatus': 'private',
        'selfDeclaredMadeForKids': False,
    }
    if status and status.get('publishAt'):
        new_status['publishAt'] = status['publishAt']
    elif item.get('publish_at'):
        new_status['publishAt'] = item['publish_at']

    # Upload
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
    body = {'snippet': new_snippet, 'status': new_status}
    print(f"  📤 uploading repaired video.mp4...")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status_, response = req.next_chunk()
    new_yid = response['id']
    print(f"  ✅ uploaded: {new_yid}")

    # Captions
    if upload_captions:
        subs_dir = ROOT / "output" / vid / "subtitles"
        if subs_dir.exists():
            for srt in sorted(subs_dir.glob("*.srt")):
                lang = srt.stem  # e.g. 'en', 'ar'
                try:
                    yt.captions().insert(
                        part="snippet",
                        body={'snippet': {
                            'videoId': new_yid,
                            'language': lang,
                            'name': lang,
                            'isDraft': False,
                        }},
                        media_body=MediaFileUpload(str(srt), mimetype="text/plain")
                    ).execute()
                    print(f"    📝 caption: {lang}")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"    ⚠ caption {lang}: {str(e)[:80]}")

    return new_yid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", nargs="?")
    ap.add_argument("--max", type=int, default=99, help="cap number to process")
    ap.add_argument("--no-captions", action="store_true", help="skip caption re-uploads")
    args = ap.parse_args()

    yt = get_youtube_client()
    state_path = ROOT / "state/pending_uploads.json"
    data = json.loads(state_path.read_text())

    if args.video_id:
        targets = [p for p in data['pending'] if p['id'] == args.video_id]
    else:
        targets = [p for p in data['pending']
                   if p.get('needs_reupload_audio_fix') and p.get('local_video_repaired')]

    targets = targets[:args.max]
    print(f"🎯 سيُعاد رفع {len(targets)} فيديو")
    print()

    success = 0
    for p in targets:
        print(f"─── {p['id']} ───")
        new_yid = reupload_one(yt, p, upload_captions=not args.no_captions)
        if new_yid:
            p['youtube_id'] = new_yid
            p['needs_reupload_audio_fix'] = False
            p['repaired_uploaded_at'] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            success += 1
            # Save state after each upload
            state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print()

    print(f"━━━ {success}/{len(targets)} اكتمل ━━━")


if __name__ == "__main__":
    main()
