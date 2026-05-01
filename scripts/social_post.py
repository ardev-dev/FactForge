#!/usr/bin/env python3
"""
social_post.py — Multi-platform social media auto-poster.

Posts a single video promo to all configured platforms in one command.
Per-platform text adaptation. Idempotent (won't double-post).

Configured platforms:
  • Bluesky      (atproto, free, unlimited)
  • Twitter/X    (tweepy, free tier 17/day)
  • Mastodon     (Mastodon.py, federated)
  • Reddit       (praw, requires karma — uses self.text + url, not direct link spam)

Setup:
  1. Create accounts manually on each platform
  2. Generate API tokens (see config/social_credentials.json.template)
  3. Save to config/social_credentials.json (gitignored)
  4. Run: python3 scripts/social_post.py [video_id]

Usage:
  python3 scripts/social_post.py lUTy778x0pg            # post by youtube_id
  python3 scripts/social_post.py S02905                 # post by local id
  python3 scripts/social_post.py S02905 --platforms bluesky,twitter
  python3 scripts/social_post.py S02905 --dry-run        # preview without posting
"""
import argparse, json, sys, time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CREDS_PATH = ROOT / "config/social_credentials.json"
STATE_PATH = ROOT / "state/social_posts.json"


# ─── Per-platform text generators ──────────────────────────────────────────

def _shorten_title_for_url(title: str) -> str:
    """Drop hashtags + truncate."""
    parts = title.split(" #", 1)
    return parts[0].strip()


def _hashtags_from_title(title: str) -> list[str]:
    return [w.lstrip("#") for w in title.split() if w.startswith("#") and w.lower() != "#shorts"]


def make_bluesky_text(title: str, yt_url: str) -> str:
    """Bluesky: 300 char limit, hashtag-friendly."""
    clean = _shorten_title_for_url(title)
    tags = _hashtags_from_title(title) or ["BigPharma", "Exposed", "Documentary"]
    tag_str = " ".join(f"#{t}" for t in tags[:3])
    body = f"{clean}\n\n{yt_url}\n\n{tag_str}"
    return body[:298]


def make_twitter_text(title: str, yt_url: str) -> str:
    """Twitter: 280 char limit, link counts as 23 chars."""
    clean = _shorten_title_for_url(title)
    # Reserve space: link (23) + space (1) = 24
    max_text = 280 - 24
    text = clean[:max_text]
    return f"{text} {yt_url}"


def make_mastodon_text(title: str, yt_url: str) -> str:
    """Mastodon: 500 chars (default), hashtag-friendly."""
    clean = _shorten_title_for_url(title)
    tags = _hashtags_from_title(title) or ["BigPharma", "Documentary"]
    tag_str = " ".join(f"#{t}" for t in tags[:5])
    body = f"{clean}\n\nFull video: {yt_url}\n\n{tag_str}"
    return body[:498]


def make_reddit_post(title: str, yt_url: str, video_topic: str) -> tuple[str, str]:
    """Reddit: returns (post_title, body_text).
    Reddit penalizes direct YouTube links — embed link + add value-add summary."""
    clean = _shorten_title_for_url(title)
    body = (
        f"I dug into this story and made a documentary on it. The numbers are wild:\n\n"
        f"{clean}\n\n"
        f"Full video with sources: {yt_url}\n\n"
        f"Key facts in the description if you don't want to watch."
    )
    return clean, body


# ─── State (avoid duplicates) ──────────────────────────────────────────────

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"posts": {}}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def already_posted(state: dict, yt_id: str, platform: str) -> bool:
    return yt_id in state["posts"] and platform in state["posts"][yt_id]


def mark_posted(state: dict, yt_id: str, platform: str, post_url: str):
    state["posts"].setdefault(yt_id, {})
    state["posts"][yt_id][platform] = {
        "url": post_url,
        "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ─── Platform: Bluesky ─────────────────────────────────────────────────────

def post_bluesky(creds: dict, text: str, yt_url: str) -> Optional[str]:
    try:
        from atproto import Client, client_utils
    except ImportError:
        print("    ⚠ atproto not installed")
        return None

    handle = creds.get("handle")
    pw = creds.get("app_password")
    if not handle or not pw:
        print("    ⚠ bluesky credentials missing")
        return None

    try:
        c = Client()
        c.login(handle, pw)
        # build with link facets so URL becomes clickable
        builder = client_utils.TextBuilder()
        # Find URL position in text and split
        if yt_url in text:
            before, after = text.split(yt_url, 1)
            builder.text(before).link(yt_url, yt_url).text(after)
            post = c.send_post(text=builder)
        else:
            post = c.send_post(text=text)
        # post.uri format: at://did:plc:xxx/app.bsky.feed.post/yyy
        # web URL: https://bsky.app/profile/{handle}/post/{rkey}
        rkey = post.uri.split("/")[-1]
        return f"https://bsky.app/profile/{handle}/post/{rkey}"
    except Exception as e:
        print(f"    ❌ bluesky: {str(e)[:120]}")
        return None


# ─── Platform: Twitter/X ───────────────────────────────────────────────────

def post_twitter(creds: dict, text: str) -> Optional[str]:
    try:
        import tweepy
    except ImportError:
        print("    ⚠ tweepy not installed")
        return None

    needed = ["consumer_key", "consumer_secret", "access_token", "access_token_secret"]
    if not all(creds.get(k) for k in needed):
        print("    ⚠ twitter credentials missing")
        return None

    try:
        client = tweepy.Client(
            consumer_key=creds["consumer_key"],
            consumer_secret=creds["consumer_secret"],
            access_token=creds["access_token"],
            access_token_secret=creds["access_token_secret"],
        )
        resp = client.create_tweet(text=text)
        tweet_id = resp.data["id"]
        return f"https://twitter.com/i/web/status/{tweet_id}"
    except Exception as e:
        print(f"    ❌ twitter: {str(e)[:120]}")
        return None


# ─── Platform: Mastodon ────────────────────────────────────────────────────

def post_mastodon(creds: dict, text: str) -> Optional[str]:
    try:
        from mastodon import Mastodon
    except ImportError:
        print("    ⚠ Mastodon.py not installed")
        return None

    instance = creds.get("instance_url")
    token = creds.get("access_token")
    if not instance or not token:
        print("    ⚠ mastodon credentials missing")
        return None

    try:
        m = Mastodon(access_token=token, api_base_url=instance)
        status = m.status_post(text)
        return status["url"]
    except Exception as e:
        print(f"    ❌ mastodon: {str(e)[:120]}")
        return None


# ─── Platform: Reddit ──────────────────────────────────────────────────────

def post_reddit(creds: dict, post_title: str, body: str, yt_url: str) -> Optional[str]:
    try:
        import praw
    except ImportError:
        print("    ⚠ praw not installed")
        return None

    needed = ["client_id", "client_secret", "username", "password", "user_agent"]
    if not all(creds.get(k) for k in needed):
        print("    ⚠ reddit credentials missing")
        return None

    subreddits = creds.get("subreddits", [])
    if not subreddits:
        print("    ⚠ no subreddits configured")
        return None

    try:
        r = praw.Reddit(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            username=creds["username"],
            password=creds["password"],
            user_agent=creds["user_agent"],
        )
        # Post to FIRST subreddit only — multi-sub spam = ban
        sub_name = subreddits[0]
        sub = r.subreddit(sub_name)
        # text post (safer than direct link — reddit penalizes link-only posts)
        submission = sub.submit(title=post_title[:300], selftext=body)
        return f"https://reddit.com{submission.permalink}"
    except Exception as e:
        print(f"    ❌ reddit (r/{subreddits[0] if subreddits else '?'}): {str(e)[:120]}")
        return None


# ─── Main orchestrator ─────────────────────────────────────────────────────

def resolve_video(arg: str) -> tuple[str, str, str]:
    """Returns (yt_id, title, topic). Accepts either local id (S02905) or yt id."""
    state = json.loads((ROOT / "state/pending_uploads.json").read_text())
    # match by local id
    p = next((p for p in state["pending"] if p.get("id") == arg), None)
    # match by youtube_id
    if not p:
        p = next((p for p in state["pending"] if p.get("youtube_id") == arg), None)
    if not p:
        print(f"❌ video '{arg}' not found in pending_uploads.json")
        sys.exit(1)
    if not p.get("youtube_id"):
        print(f"❌ {p.get('id')} has no youtube_id yet — upload first")
        sys.exit(1)
    return p["youtube_id"], p.get("title", ""), p.get("niche", "Big Industry Exposed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="local id (S02905) or YouTube id")
    ap.add_argument("--platforms", default="bluesky,twitter,mastodon,reddit",
                    help="comma-separated subset")
    ap.add_argument("--dry-run", action="store_true",
                    help="preview text without posting")
    args = ap.parse_args()

    # Load creds (or report missing)
    if not CREDS_PATH.exists() and not args.dry_run:
        print(f"❌ {CREDS_PATH} missing")
        print(f"   Copy template: cp {CREDS_PATH}.template {CREDS_PATH}")
        print(f"   Then fill in tokens for the platforms you've set up.")
        sys.exit(1)

    creds = json.loads(CREDS_PATH.read_text()) if CREDS_PATH.exists() else {}
    state = load_state()

    yt_id, title, topic = resolve_video(args.video)
    yt_url = f"https://youtu.be/{yt_id}"
    print(f"🎬 {yt_id}: {title[:70]}")
    print(f"🔗 {yt_url}\n")

    platforms = [p.strip().lower() for p in args.platforms.split(",")]
    handlers = {
        "bluesky": (
            lambda: make_bluesky_text(title, yt_url),
            lambda txt: post_bluesky(creds.get("bluesky", {}), txt, yt_url),
        ),
        "twitter": (
            lambda: make_twitter_text(title, yt_url),
            lambda txt: post_twitter(creds.get("twitter", {}), txt),
        ),
        "mastodon": (
            lambda: make_mastodon_text(title, yt_url),
            lambda txt: post_mastodon(creds.get("mastodon", {}), txt),
        ),
        "reddit": (
            lambda: make_reddit_post(title, yt_url, topic),
            lambda data: post_reddit(creds.get("reddit", {}), data[0], data[1], yt_url),
        ),
    }

    success = 0
    for platform in platforms:
        if platform not in handlers:
            print(f"⚠ unknown platform: {platform}")
            continue

        if already_posted(state, yt_id, platform):
            url = state["posts"][yt_id][platform]["url"]
            print(f"⏭  {platform}: already posted ({url})")
            continue

        text_fn, post_fn = handlers[platform]
        text = text_fn()

        print(f"📝 {platform}:")
        if isinstance(text, tuple):
            print(f"   Title: {text[0]}")
            print(f"   Body: {text[1][:200]}...")
        else:
            print(f"   {text[:200]}{'...' if len(text)>200 else ''}")

        if args.dry_run:
            print("   [DRY RUN — not posted]\n")
            continue

        url = post_fn(text)
        if url:
            print(f"   ✅ {url}")
            mark_posted(state, yt_id, platform, url)
            save_state(state)
            success += 1
        time.sleep(2)
        print()

    if not args.dry_run:
        print(f"━━━ {success}/{len(platforms)} posted ━━━")


if __name__ == "__main__":
    main()
