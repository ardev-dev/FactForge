#!/usr/bin/env python3
"""
production_audit_long.py — Quality gate for long videos (S02902-grade adapted).

Same philosophy as scripts/production_audit.py for shorts, but with thresholds
adapted to documentary format:
  • 1920×1080 @ 30fps (instead of 1080×1920 @ 60fps)
  • 8-15 minute duration
  • Chapter-based structure (5-12 chapters)
  • AI-generated images (no bg_videos)
  • Custom thumbnail SUPPORTED (long videos can have one — different from shorts)

Usage:
  python3 scripts/production_audit_long.py L00600
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPEC = {
    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        # 6 min minimum is YouTube's documentary sweet spot. Earlier 8min was
        # too restrictive — a tight 6-7min video outperforms a padded 8-9min one.
        "duration_min_s": 6 * 60,
        "duration_max_s": 16 * 60,
        # Long-form with static AI images produces lower bitrate at same quality
        # (less motion = better compression). 2500 kbps at CRF 18 = visually clean.
        "bitrate_min_kbps": 2500,
        "codec": "h264",
    },
    "audio": {
        "codec": "aac",
        "bitrate_min_kbps": 192,
        "lufs_min": -16,
        "lufs_max": -12,
        "true_peak_max_db": -0.5,
        "drift_max_ms": 200,
        "silence_max_ms": 800,   # natural breathing room in long-form is OK
    },
    "structure": {
        "chapter_min": 5,
        "chapter_max": 12,
        "chapter_dur_max_s": 180,   # any chapter > 3 minutes = pacing issue
    },
    "script": {
        "shock_words": [
            "banned", "only", "never", "billion", "million", "trillion",
            "died", "killed", "hidden", "secret", "nobody", "every",
            "first", "last", "zero", "discovered", "shocking", "warned",
            "impossible", "rejected", "failed", "wrong", "stole", "exposed",
            "buried", "lied", "poison", "toxic", "contaminated", "fraud",
            "scam", "addicted", "deadly",
        ],
        "subscribe_required": True,
        "comment_cta_required": True,
        "content_score_min": 80,
        "min_words": 900,         # ~6 minutes of speech at 1.05 speed
        "max_words": 2400,        # ~15 minutes of speech
    },
    "metadata": {
        "title_min_chars": 40,
        "title_max_chars": 100,
        "shorts_hashtag_banned": True,   # #shorts MUST NOT appear in long-video titles
        "subscribe_in_description": True,
        "source_citation_required": True,
        "tags_min": 8,
        "tags_max": 20,
    },
}


def ffprobe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    return json.loads(r.stdout) if r.returncode == 0 else None


def measure_loudness(path):
    r = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", "loudnorm=I=-14:TP=-1.0:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    out = r.stderr
    if "{" not in out:
        return None, None
    js = "{" + out.split("{", 1)[1].rsplit("}", 1)[0] + "}"
    try:
        d = json.loads(js)
        return float(d["input_i"]), float(d["input_tp"])
    except Exception:
        return None, None


def detect_silences(path, threshold_db=-40, min_duration=0.5):
    r = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    silences, cs = [], None
    for line in r.stderr.split("\n"):
        if "silence_start" in line:
            try: cs = float(line.split("silence_start: ")[1].split()[0])
            except: pass
        elif "silence_end" in line and cs is not None:
            try:
                e = float(line.split("silence_end: ")[1].split("|")[0].strip())
                d = float(line.split("silence_duration: ")[1].split()[0])
                silences.append((cs, e, d))
                cs = None
            except: pass
    return silences


def has_shock_word(text):
    t = text.lower()
    for w in SPEC["script"]["shock_words"]:
        if re.search(rf"\b{re.escape(w)}\b", t):
            return w
    return None


def audit(vid):
    out_dir = ROOT / "output" / vid
    issues, warnings, metrics = [], [], {}

    video_path = out_dir / "video.mp4"
    if not video_path.exists():
        return False, [f"video.mp4 missing"], [], {}

    info = ffprobe(video_path)
    if not info:
        return False, ["ffprobe failed"], [], {}
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v or not a:
        return False, ["missing video or audio stream"], [], {}

    fmt = info["format"]
    width, height = int(v["width"]), int(v["height"])
    fps = eval(v["r_frame_rate"])
    duration = float(fmt["duration"])
    vbitrate = int(v.get("bit_rate", fmt.get("bit_rate", 0))) // 1000
    abitrate = int(a.get("bit_rate", 0)) // 1000

    metrics.update({
        "width": width, "height": height, "fps": fps,
        "duration_s": round(duration, 1), "duration_min": round(duration/60, 1),
        "video_bitrate_kbps": vbitrate, "audio_bitrate_kbps": abitrate,
        "video_codec": v["codec_name"], "audio_codec": a["codec_name"],
    })

    sv = SPEC["video"]; sa = SPEC["audio"]
    if width != sv["width"] or height != sv["height"]:
        issues.append(f"resolution {width}x{height} ≠ {sv['width']}x{sv['height']}")
    if abs(fps - sv["fps"]) > 0.5:
        issues.append(f"fps {fps:.1f} ≠ {sv['fps']}")
    if duration < sv["duration_min_s"] or duration > sv["duration_max_s"]:
        issues.append(f"duration {duration/60:.1f}min outside [{sv['duration_min_s']/60:.0f},{sv['duration_max_s']/60:.0f}] min")
    if vbitrate and vbitrate < sv["bitrate_min_kbps"]:
        issues.append(f"video bitrate {vbitrate}k < {sv['bitrate_min_kbps']}k")
    if v["codec_name"] != sv["codec"]:
        issues.append(f"video codec {v['codec_name']} ≠ {sv['codec']}")
    if a["codec_name"] != sa["codec"]:
        issues.append(f"audio codec {a['codec_name']} ≠ {sa['codec']}")
    if abitrate < sa["bitrate_min_kbps"]:
        issues.append(f"audio bitrate {abitrate}k < {sa['bitrate_min_kbps']}k")

    lufs, tp = measure_loudness(video_path)
    if lufs is not None:
        metrics["lufs"] = round(lufs, 1)
        metrics["true_peak_db"] = round(tp, 1) if tp else None
        if lufs < sa["lufs_min"] or lufs > sa["lufs_max"]:
            issues.append(f"LUFS {lufs:.1f} outside [{sa['lufs_min']},{sa['lufs_max']}]")
        if tp is not None and tp > sa["true_peak_max_db"]:
            issues.append(f"true peak {tp:.1f} dBTP > {sa['true_peak_max_db']}")

    a_dur = float(a.get("duration", 0))
    drift_ms = abs(a_dur - duration) * 1000
    metrics["drift_ms"] = round(drift_ms, 0)
    if drift_ms > sa["drift_max_ms"]:
        issues.append(f"A/V drift {drift_ms:.0f}ms > {sa['drift_max_ms']}ms")

    sils = detect_silences(video_path)
    metrics["silences"] = len(sils)
    for s, e, d in sils:
        if d * 1000 > sa["silence_max_ms"]:
            issues.append(f"silence {s:.1f}s-{e:.1f}s ({d*1000:.0f}ms) > {sa['silence_max_ms']}ms")

    # ── Structure ─────────────────────────────────────────────────────
    props_path = out_dir / "remotion_props.json"
    if props_path.exists():
        props = json.loads(props_path.read_text())
        sections = props.get("sections") or props.get("segments", [])
        ss = SPEC["structure"]
        metrics["chapters"] = len(sections)
        if len(sections) < ss["chapter_min"] or len(sections) > ss["chapter_max"]:
            issues.append(f"chapters {len(sections)} outside [{ss['chapter_min']},{ss['chapter_max']}]")
        max_ch_s = max((s["endFrame"] - s["startFrame"]) / fps for s in sections)
        metrics["max_chapter_s"] = round(max_ch_s, 0)
        if max_ch_s > ss["chapter_dur_max_s"]:
            issues.append(f"single chapter {max_ch_s:.0f}s > {ss['chapter_dur_max_s']}s")

    # ── Script ────────────────────────────────────────────────────────
    script_path = out_dir / "script.json"
    if script_path.exists():
        scr = json.loads(script_path.read_text())
        ssc = SPEC["script"]
        tts = scr.get("tts_script", "")
        word_count = len(tts.split())
        metrics["word_count"] = word_count
        metrics["content_score"] = scr.get("content_score", 0)
        if word_count < ssc["min_words"]:
            issues.append(f"script {word_count} words < {ssc['min_words']}")
        if word_count > ssc["max_words"]:
            warnings.append(f"script {word_count} words > {ssc['max_words']}")
        # Hook check: scan entire first chapter (not just first sentence) — long-form
        # builds the shock over 30-60s. As long as chapter 1 contains a shock word,
        # the hook is doing its job.
        first_ch = (scr.get("chapters") or [{}])[0]
        sw = has_shock_word(first_ch.get("tts_script", ""))
        metrics["hook_shock_word"] = sw
        if not sw:
            warnings.append("first chapter has no shock word — strengthen the hook")
        if ssc["subscribe_required"] and "subscribe" not in tts.lower():
            issues.append("script missing 'Subscribe' ask")
        if ssc["comment_cta_required"] and "comment" not in tts.lower():
            warnings.append("script missing 'Comment' CTA")
        if scr.get("content_score", 0) < ssc["content_score_min"]:
            issues.append(f"content_score {scr.get('content_score',0)} < {ssc['content_score_min']}")

    # ── Metadata ──────────────────────────────────────────────────────
    md_path = out_dir / "metadata.json"
    if md_path.exists():
        md = json.loads(md_path.read_text())
        sm = SPEC["metadata"]
        title = md.get("title_selected") or md.get("selected_title") or md.get("title", "")
        desc = md.get("description", "")
        tags = md.get("tags", [])
        metrics.update({
            "title_length": len(title),
            "tag_count": len(tags),
        })
        if len(title) < sm["title_min_chars"] or len(title) > sm["title_max_chars"]:
            issues.append(f"title length {len(title)} outside [{sm['title_min_chars']},{sm['title_max_chars']}]")
        if sm["shorts_hashtag_banned"] and "#shorts" in title.lower():
            issues.append("title contains #shorts (long videos must NOT use this tag)")
        if sm["subscribe_in_description"] and "subscribe" not in desc.lower():
            issues.append("description missing 'Subscribe'")
        if sm["source_citation_required"]:
            if not re.search(r"sources?:|reuters|bbc|ap |ntsb|cdc|epa|who |un |world bank|forbes|bloomberg|nejm|fda|doj", desc, re.I):
                warnings.append("description has no clear source citation")
        if len(tags) < sm["tags_min"] or len(tags) > sm["tags_max"]:
            issues.append(f"tags {len(tags)} outside [{sm['tags_min']},{sm['tags_max']}]")

    # ── Assets (AI images) ────────────────────────────────────────────
    img_dir = out_dir / "images"
    if img_dir.exists():
        imgs = list(img_dir.glob("*.jpg"))
        metrics["images_count"] = len(imgs)
        # Each chapter should have A + B
        if props_path.exists():
            expected = len(json.loads(props_path.read_text()).get("sections", [])) * 2
            if len(imgs) < expected:
                issues.append(f"only {len(imgs)}/{expected} chapter images present")

    return len(issues) == 0, issues, warnings, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    passed, issues, warnings, metrics = audit(args.video_id)
    if args.json:
        print(json.dumps({
            "video_id": args.video_id, "passed": passed,
            "issues": issues, "warnings": warnings, "metrics": metrics,
        }, indent=2, ensure_ascii=False))
    else:
        icon = "✅" if passed else "❌"
        print(f"{icon} {args.video_id} — {'PASSED' if passed else 'FAILED'} long-video baseline")
        print("\n📊 Metrics:")
        for k, val in metrics.items():
            print(f"   {k}: {val}")
        if issues:
            print(f"\n🚨 Issues ({len(issues)}):")
            for i in issues: print(f"   • {i}")
        if warnings:
            print(f"\n⚠️  Warnings ({len(warnings)}):")
            for w in warnings: print(f"   • {w}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
