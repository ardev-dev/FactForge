"""
youtube_helper.py — Centralized YouTube API interactions for FactForge.

Replaces duplicated auth/upload logic scattered across:
  - scripts/finalize_and_upload.py
  - scripts/schedule_uploads.py
  - agents/publish_agent.py

Usage:
    from utils.youtube_helper import get_youtube_client, upload_video, set_thumbnail, ...
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ─── Quota constants ─────────────────────────────────────────────────────────
DAILY_QUOTA_LIMIT = 10_000
UPLOAD_COST       = 1_600
THUMBNAIL_COST    = 50
CAPTION_COST      = 400

# ─── A/B Testing constants ────────────────────────────────────────────────────
AB_CTR_THRESHOLD    = 3.5   # % — rotate title if CTR below this after 48h
AB_MIN_IMPRESSIONS  = 200   # minimum impressions before judging CTR
AB_WAIT_HOURS       = 48    # hours to wait before evaluating

from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
TOKEN_PATH = BASE_DIR / "config" / "youtube_token.json"
STATE_DIR  = BASE_DIR / "state"

# ─── Schedule constants ───────────────────────────────────────────────────────
SCOPES             = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl"]
SHORT_EVERY_N_DAYS = 2
LONG_EVERY_N_DAYS  = 7
PUBLISH_TIME       = "18:00:00Z"   # 18:00 UTC = 1pm EST (peak Shorts feed) = 21:00 Riyadh
PUBLISH_HOUR       = 18


# ─── Quota helpers ────────────────────────────────────────────────────────────

def _read_quota() -> dict:
    """Read state/quota_usage.json; reset if date changed."""
    quota_path = STATE_DIR / "quota_usage.json"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if quota_path.exists():
        data = json.loads(quota_path.read_text())
        if data.get("date") == today:
            return data
    # Missing or stale — start fresh
    return {"date": today, "used": 0}


def _write_quota(data: dict) -> None:
    quota_path = STATE_DIR / "quota_usage.json"
    quota_path.write_text(json.dumps(data, indent=2))


def check_quota_before_upload(n_captions: int = 7) -> bool:
    """
    Return True if there is enough quota left for one full upload operation.
    Prints a warning and returns False if the 90% safety threshold would be exceeded.
    """
    data = _read_quota()
    cost = UPLOAD_COST + THUMBNAIL_COST + (n_captions * CAPTION_COST)
    if data["used"] + cost > DAILY_QUOTA_LIMIT * 0.90:
        print(
            f"  [quota] ⚠️  Quota warning: {data['used']} used + {cost} needed "
            f"> {int(DAILY_QUOTA_LIMIT * 0.90)} (90% of {DAILY_QUOTA_LIMIT}). "
            "Skipping upload to protect daily quota."
        )
        return False
    return True


def record_quota_usage(cost: int) -> None:
    """Add `cost` units to today's quota tally in state/quota_usage.json."""
    data = _read_quota()
    data["used"] += cost
    _write_quota(data)
    print(f"  [quota] Used {cost} units → {data['used']}/{DAILY_QUOTA_LIMIT} today")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_youtube_client() -> Resource:
    """
    Load credentials from config/youtube_token.json, refresh if expired,
    and return an authenticated YouTube API resource.

    Saves refreshed token back to TOKEN_PATH automatically.
    """
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"YouTube token not found: {TOKEN_PATH}")

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist refreshed token
            TOKEN_PATH.write_text(creds.to_json())
        else:
            raise RuntimeError(
                "YouTube credentials are invalid and cannot be refreshed. "
                "Re-run the OAuth flow to generate a new token."
            )

    return build("youtube", "v3", credentials=creds)


# ─── Upload ───────────────────────────────────────────────────────────────────

def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list,
    category_id: str = "27",
    publish_at: Optional[str] = None,
    privacy: str = "private",
) -> str:
    """
    Upload a video file to YouTube and return the YouTube video ID.

    Args:
        video_path:   Absolute path to the .mp4 file.
        title:        Video title (truncated to 100 chars automatically).
        description:  Video description (non-ASCII stripped, truncated to 4900 chars).
        tags:         List of tag strings.
        category_id:  YouTube category ID. Default "27" = Education.
        publish_at:   RFC3339 string for scheduled auto-publish, e.g.
                      "2026-04-17T14:00:00Z". When supplied, privacyStatus is
                      forced to "private" regardless of `privacy`.
        privacy:      "private" | "public" | "unlisted". Ignored when publish_at
                      is set (always private in that case).

    Returns:
        YouTube video ID string (e.g. "dQw4w9WgXcQ").

    Raises:
        FileNotFoundError: if video_path does not exist.
        RuntimeError:      on upload API failure.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Strip non-ASCII characters from description to avoid YouTube API rejections
    clean_desc = re.sub(r"[^\x20-\x7E\n]", "", description)

    status_body: dict = {
        "privacyStatus": "private" if publish_at else privacy,
        "selfDeclaredMadeForKids": False,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title":           title[:100],
            "description":     clean_desc[:4900],
            "tags":            tags,
            "categoryId":      category_id,
            "defaultLanguage": "en",
        },
        "status": status_body,
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )

    youtube = get_youtube_client()
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Upload progress: {pct}%", end="\r")

    print()  # newline after progress line
    youtube_id: str = response["id"]
    print(f"  Uploaded: https://youtu.be/{youtube_id}")
    record_quota_usage(UPLOAD_COST)
    return youtube_id


# ─── Thumbnail ────────────────────────────────────────────────────────────────

def set_thumbnail(youtube_id: str, thumb_path: Path) -> bool:
    """
    Upload a custom thumbnail for the given video.

    Note: YouTube silently blocks thumbnail uploads for Shorts via the API.
    For Shorts, embed the thumbnail as a freeze-frame and ask the user to
    set it manually in YouTube Studio.

    Args:
        youtube_id: The YouTube video ID.
        thumb_path: Path to the thumbnail file (JPEG recommended, 1280×720).

    Returns:
        True on success, False on any API failure.
    """
    thumb_path = Path(thumb_path)
    if not thumb_path.exists():
        print(f"  [thumbnail] File not found: {thumb_path}")
        return False

    suffix = thumb_path.suffix.lower()
    mimetype = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    try:
        youtube = get_youtube_client()
        youtube.thumbnails().set(
            videoId=youtube_id,
            media_body=MediaFileUpload(str(thumb_path), mimetype=mimetype),
        ).execute()
        print(f"  Thumbnail uploaded for {youtube_id}")
        record_quota_usage(THUMBNAIL_COST)
        return True
    except Exception as exc:
        print(f"  [thumbnail] Upload failed for {youtube_id}: {exc}")
        return False


# ─── Captions ─────────────────────────────────────────────────────────────────

def upload_caption(
    youtube_id: str,
    srt_path: Path,
    language: str,
    name: str,
) -> bool:
    """
    Upload a single SRT caption file to YouTube.

    Args:
        youtube_id: The YouTube video ID.
        srt_path:   Path to the .srt file.
        language:   BCP-47 language code, e.g. "en", "ar", "fr".
        name:       Human-readable caption track name, e.g. "English".

    Returns:
        True on success, False on failure.
    """
    srt_path = Path(srt_path)
    if not srt_path.exists():
        print(f"  [caption] SRT file not found: {srt_path}")
        return False

    try:
        youtube = get_youtube_client()
        body = {
            "snippet": {
                "videoId":  youtube_id,
                "language": language,
                "name":     name,
                "isDraft":  False,
            }
        }
        media = MediaFileUpload(str(srt_path), mimetype="application/octet-stream")
        youtube.captions().insert(part="snippet", body=body, media_body=media).execute()
        print(f"  Caption uploaded: {language} ({name})")
        record_quota_usage(CAPTION_COST)
        return True
    except Exception as exc:
        print(f"  [caption] Upload failed for {language}: {exc}")
        return False


# ─── Scheduling ───────────────────────────────────────────────────────────────

def get_next_publish_date(video_type: str = "short") -> str:
    """
    Calculate the next available publish date for a new video.

    Reads state/pending_uploads.json to find the most recently scheduled
    date for the given type, then adds SHORT_EVERY_N_DAYS (2) or
    LONG_EVERY_N_DAYS (7) days. Returns an RFC3339 string at 14:00 UTC.

    Args:
        video_type: "short" or "long".

    Returns:
        RFC3339 datetime string, e.g. "2026-05-03T14:00:00Z".
    """
    pending_path = STATE_DIR / "pending_uploads.json"

    last_date: Optional[datetime] = None

    if pending_path.exists():
        with open(pending_path) as f:
            data = json.load(f)

        entries = data.get("pending", [])

        for entry in entries:
            # Determine type from the "type" field or by ID prefix
            entry_type = entry.get("type", "")
            if not entry_type:
                entry_type = "long" if entry.get("id", "").startswith("L") else "short"

            if entry_type != video_type:
                continue

            pub_at = entry.get("publish_at")
            if not pub_at:
                continue

            try:
                # Normalise Z suffix so fromisoformat works on Python 3.10
                dt = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
                if last_date is None or dt > last_date:
                    last_date = dt
            except ValueError:
                continue

    interval = LONG_EVERY_N_DAYS if video_type == "long" else SHORT_EVERY_N_DAYS

    if last_date is None:
        # No existing videos of this type — schedule starting tomorrow
        base = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        base = last_date + timedelta(days=interval)

    # Force publish time to 18:00:00 UTC (peak Shorts feed window: 1-4pm EST)
    publish_dt = base.replace(hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    return publish_dt.strftime(f"%Y-%m-%dT{PUBLISH_HOUR:02d}:00:00Z")


# ─── State management ─────────────────────────────────────────────────────────

def update_state_after_upload(
    video_id: str,
    youtube_id: str,
    publish_at: str,
    title: str,
    video_type: str,
) -> None:
    """
    Persist upload result to state/pending_uploads.json and remove the
    video from state/queue.json if it is still listed there.

    - If an entry with `video_id` already exists in pending_uploads.json,
      it is updated in place.
    - If no entry exists, a new one is appended.
    - The entry's status is set to "scheduled" and youtube_id / publish_at
      are recorded.

    Args:
        video_id:   Internal video ID, e.g. "S01220" or "L00200".
        youtube_id: YouTube video ID returned by the upload API.
        publish_at: RFC3339 scheduled publish datetime string.
        title:      Video title (stored for reference).
        video_type: "short" or "long".
    """
    pending_path = STATE_DIR / "pending_uploads.json"
    queue_path   = STATE_DIR / "queue.json"

    # ── Update pending_uploads.json ──────────────────────────────────────────
    if pending_path.exists():
        with open(pending_path) as f:
            pending_data = json.load(f)
    else:
        pending_data = {"pending": []}

    entries = pending_data.setdefault("pending", [])

    # Find existing entry or create a new one
    existing = next((e for e in entries if e.get("id") == video_id), None)
    if existing:
        existing.update({
            "youtube_id": youtube_id,
            "status":     "scheduled",
            "publish_at": publish_at,
            "scheduled":  True,
        })
    else:
        entries.append({
            "id":         video_id,
            "title":      title,
            "youtube_id": youtube_id,
            "status":     "scheduled",
            "publish_at": publish_at,
            "type":       video_type,
            "scheduled":  True,
        })

    with open(pending_path, "w") as f:
        json.dump(pending_data, f, indent=2, ensure_ascii=False)

    print(f"  State updated: {video_id} → {youtube_id} scheduled {publish_at[:10]}")

    # ── Remove from queue.json if present ───────────────────────────────────
    if not queue_path.exists():
        return

    with open(queue_path) as f:
        queue_data = json.load(f)

    # Support both {"ideas": [...]} and flat list structures
    if isinstance(queue_data, list):
        original_len = len(queue_data)
        queue_data = [e for e in queue_data if e.get("id") != video_id]
        changed = len(queue_data) != original_len
        if changed:
            with open(queue_path, "w") as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False)
    elif isinstance(queue_data, dict):
        for key in ("ideas", "queue", "items"):
            if key in queue_data and isinstance(queue_data[key], list):
                original_len = len(queue_data[key])
                queue_data[key] = [e for e in queue_data[key] if e.get("id") != video_id]
                if len(queue_data[key]) != original_len:
                    with open(queue_path, "w") as f:
                        json.dump(queue_data, f, indent=2, ensure_ascii=False)
                break


# ─── A/B Thumbnail Testing ───────────────────────────────────────────────────

AB_THUMBNAILS_PATH = STATE_DIR / "ab_thumbnails.json"


def upload_ab_thumbnails(youtube_id: str, thumb_paths: list) -> dict:
    """
    Upload the first thumbnail variant as the primary, then save all variants
    to state/ab_thumbnails.json for later rotation.

    Args:
        youtube_id:  YouTube video ID.
        thumb_paths: List of Path objects [thumbnail.jpg, thumbnail_b.jpg, thumbnail_c.jpg].

    Returns:
        dict with "status" key ("ok" or "error") and "current" index (0).
    """
    thumb_paths = [Path(p) for p in thumb_paths]

    # Upload variant A as the active thumbnail
    ok = set_thumbnail(youtube_id, thumb_paths[0])
    if not ok:
        return {"status": "error", "message": "Primary thumbnail upload failed"}

    # Persist variant list for rotation
    records: list = []
    if AB_THUMBNAILS_PATH.exists():
        try:
            records = json.loads(AB_THUMBNAILS_PATH.read_text())
        except Exception:
            records = []

    # Remove stale entry for this video if present
    records = [r for r in records if r.get("youtube_id") != youtube_id]

    records.append({
        "youtube_id":  youtube_id,
        "variants":    [str(p) for p in thumb_paths],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "current":     0,
    })

    AB_THUMBNAILS_PATH.write_text(json.dumps(records, indent=2))
    print(f"  [A/B thumb] {len(thumb_paths)} variants saved for {youtube_id}")
    return {"status": "ok", "current": 0, "variants": len(thumb_paths)}


def rotate_ab_thumbnail(youtube_id: str) -> bool:
    """
    Rotate to the next thumbnail variant for the given video (A→B→C→A).

    Reads state/ab_thumbnails.json, uploads the next variant via set_thumbnail,
    and updates the current index.

    Returns True on success, False if no record found or upload fails.
    """
    if not AB_THUMBNAILS_PATH.exists():
        print(f"  [A/B thumb] No ab_thumbnails.json found")
        return False

    records: list = json.loads(AB_THUMBNAILS_PATH.read_text())
    entry = next((r for r in records if r.get("youtube_id") == youtube_id), None)
    if not entry:
        print(f"  [A/B thumb] No record for {youtube_id}")
        return False

    variants = entry.get("variants", [])
    if len(variants) < 2:
        print(f"  [A/B thumb] Only {len(variants)} variant(s) — nothing to rotate")
        return False

    next_index = (entry["current"] + 1) % len(variants)
    next_path  = Path(variants[next_index])

    ok = set_thumbnail(youtube_id, next_path)
    if not ok:
        return False

    entry["current"] = next_index
    AB_THUMBNAILS_PATH.write_text(json.dumps(records, indent=2))
    print(f"  [A/B thumb] Rotated to variant {next_index} ({next_path.name}) for {youtube_id}")
    return True


# ─── A/B Title Testing ────────────────────────────────────────────────────────

def update_video_title(youtube_id: str, new_title: str) -> bool:
    """
    Update the title of a YouTube video via the API.
    Fetches current snippet first (required by YouTube API for partial updates).

    Returns True on success.
    """
    try:
        youtube = get_youtube_client()
        # Fetch current snippet (must include categoryId)
        resp = youtube.videos().list(part="snippet", id=youtube_id).execute()
        items = resp.get("items", [])
        if not items:
            print(f"  [A/B] Video {youtube_id} not found")
            return False

        snippet = items[0]["snippet"]
        snippet["title"] = new_title[:100]

        youtube.videos().update(
            part="snippet",
            body={"id": youtube_id, "snippet": snippet},
        ).execute()
        print(f"  [A/B] Title updated → {new_title[:60]}")
        return True
    except Exception as exc:
        print(f"  [A/B] Title update failed for {youtube_id}: {exc}")
        return False


# ─── Chapters ─────────────────────────────────────────────────────────────────

def generate_chapters_description(sections: list, fps: int = 30) -> str:
    """
    Convert a remotion_props.json sections list into a YouTube chapters string.

    Each section must have:
        startFrame  (int)   — frame number from the start of the video
        title       (str)   — chapter display name

    The first chapter is always forced to 00:00 as required by YouTube.

    Args:
        sections:  List of section dicts from remotion_props.json.
        fps:       Frames per second used when rendering. Default 30 (Long videos).

    Returns:
        Multi-line string ready to be inserted into a video description, e.g.:
            00:00 Introduction
            01:23 The Rise of Baghdad
            ...
    """
    if not sections:
        return ""

    lines = []
    for i, section in enumerate(sections):
        frame = int(section.get("startFrame", 0))
        title = section.get("title", f"Chapter {i + 1}").strip()

        total_seconds = frame // fps
        # First chapter must be 00:00 per YouTube requirements
        if i == 0:
            total_seconds = 0

        minutes = total_seconds // 60
        seconds = total_seconds % 60
        timestamp = f"{minutes:02d}:{seconds:02d}"
        lines.append(f"{timestamp} {title}")

    return "\n".join(lines)


def append_chapters_to_video(youtube_id: str, chapters_text: str) -> bool:
    """
    Append a chapters block to an existing YouTube video description.

    Fetches the current description, appends two newlines + chapters_text,
    then updates the video via videos().update().

    Args:
        youtube_id:    The YouTube video ID.
        chapters_text: Formatted chapters string from generate_chapters_description().

    Returns:
        True on success, False on any API failure.
    """
    if not chapters_text.strip():
        print("  [chapters] No chapters text provided — skipping.")
        return False

    try:
        youtube = get_youtube_client()

        # Fetch current snippet (required for partial update)
        resp = youtube.videos().list(part="snippet", id=youtube_id).execute()
        items = resp.get("items", [])
        if not items:
            print(f"  [chapters] Video {youtube_id} not found")
            return False

        snippet = items[0]["snippet"]
        existing_desc = snippet.get("description", "")

        # Avoid duplicating chapters if already present
        if "00:00" in existing_desc:
            print(f"  [chapters] Description already contains timestamps — skipping append")
            return False

        snippet["description"] = existing_desc.rstrip() + "\n\n" + chapters_text

        youtube.videos().update(
            part="snippet",
            body={"id": youtube_id, "snippet": snippet},
        ).execute()
        print(f"  ✅ Chapters appended to {youtube_id}")
        return True
    except Exception as exc:
        print(f"  [chapters] Update failed for {youtube_id}: {exc}")
        return False


def rotate_title_if_needed(video_id: str, youtube_id: str, ctr_pct: float, impressions: int) -> Optional[str]:
    """
    Check if title needs rotation based on CTR performance.
    - Only rotates if: impressions >= AB_MIN_IMPRESSIONS AND ctr_pct < AB_CTR_THRESHOLD
    - Reads titles from output/[id]/metadata.json (titles array)
    - Tracks rotation index in state/hook_performance.json title_rotations

    Returns new title string if rotated, None if no rotation needed.
    """
    if impressions < AB_MIN_IMPRESSIONS:
        return None
    if ctr_pct >= AB_CTR_THRESHOLD:
        return None

    meta_path = BASE_DIR / "output" / video_id / "metadata.json"
    if not meta_path.exists():
        return None

    with open(meta_path) as f:
        meta = json.load(f)

    titles = meta.get("titles", [])
    if not titles:
        return None

    # Find current title index from hook_performance title_rotations log
    hp_path = STATE_DIR / "hook_performance.json"
    hp_data = {}
    if hp_path.exists():
        with open(hp_path) as f:
            hp_data = json.load(f)

    rotations = hp_data.setdefault("title_rotations", [])
    video_rotations = [r for r in rotations if r.get("video_id") == video_id]
    current_index = len(video_rotations)  # 0 = first title (already used), so try index 1, 2...

    next_index = current_index + 1
    if next_index >= len(titles):
        print(f"  [A/B] {video_id}: all {len(titles)} titles exhausted")
        return None

    new_title = titles[next_index]
    ok = update_video_title(youtube_id, new_title)
    if ok:
        rotations.append({
            "video_id":    video_id,
            "youtube_id":  youtube_id,
            "old_index":   current_index,
            "new_index":   next_index,
            "new_title":   new_title,
            "reason":      f"CTR {ctr_pct:.1f}% < {AB_CTR_THRESHOLD}% threshold (impressions: {impressions})",
            "rotated_at":  datetime.now(timezone.utc).isoformat(),
        })
        with open(hp_path, "w") as f:
            json.dump(hp_data, f, indent=2, ensure_ascii=False)

        # Also update metadata.json selected_title
        meta["selected_title"] = new_title
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        return new_title
    return None
