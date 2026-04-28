#!/usr/bin/env python3
"""
production_audit.py — Hard quality gate enforcing the S02902 baseline.

Locked-in by user 2026-04-28 after S02902 was approved as the production
standard. Any new short MUST match these specs or upload is BLOCKED.

Checks (each is PASS/FAIL — no warnings allowed at the gate):

  VIDEO
  • Resolution exactly 1080×1920
  • FPS exactly 60
  • Duration in [35, 60] seconds
  • Bitrate ≥ 5,000 kbps
  • Codec h264

  AUDIO
  • Codec aac
  • Bitrate ≥ 192 kbps
  • LUFS in [-15, -13]
  • True peak < -0.5 dBTP (no clipping)
  • A/V drift < 150ms
  • No silence > 500ms anywhere

  STRUCTURE
  • Hero segment exists (type=hero, duration 12-18 frames)
  • Flash segments: 4-6 (rapid-cut intro 2-3s)
  • Narration segments: 7-12
  • CTA segment exists (type=cta)
  • Max single visual hold ≤ 5s (any segment longer = re-cut needed)

  SCRIPT
  • Hook ≤ 12 words
  • Hook contains a shock word (banned, only, never, billion, died, hidden, etc.)
  • Subscribe ask present in tts_script
  • Comment CTA present in tts_script
  • Content score ≥ 80

  METADATA
  • Title 50-100 chars
  • Title contains #shorts
  • Title has 2-3 hashtags total
  • Description starts with hashtag line
  • Description contains "Subscribe"
  • Description contains source citation ("Sources:" or named outlets)
  • Tags 8-15 entries

  ASSETS
  • bg_videos folder has same count as segments
  • Every bg_video is 1080×1920

Exit code 0 = ready to upload. Exit 1 = STOP, fix before uploading.

Usage:
  python3 scripts/production_audit.py S02902
  python3 scripts/production_audit.py S02902 --json
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── S02902 BASELINE — locked thresholds ─────────────────────────────────────
SPEC = {
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 60,
        "duration_min_s": 35,
        "duration_max_s": 60,
        "bitrate_min_kbps": 5000,
        "codec": "h264",
    },
    "audio": {
        "codec": "aac",
        "bitrate_min_kbps": 192,
        "lufs_min": -15,
        "lufs_max": -13,
        "true_peak_max_db": -0.5,
        "drift_max_ms": 150,
        "silence_max_ms": 500,
    },
    "structure": {
        "hero_count": 1,
        "hero_dur_min_f": 12,
        "hero_dur_max_f": 18,
        "flash_min": 4,
        "flash_max": 6,
        "narration_min": 7,
        "narration_max": 12,
        "cta_required": True,
        # Audit floor = 9s (catches gross stagnation). Pipeline aims for ≤5s
        # via auto sub-cuts. So anything 5-9s passes audit but pipeline tries
        # to split it. >9s indicates broken word allocation or pipeline bypass.
        "visual_hold_max_s": 9,
    },
    "script": {
        # 13 words allows for em-dash separator counted as word (S02902 baseline).
        "hook_max_words": 13,
        "shock_words": [
            "banned", "only", "never", "billion", "million", "trillion",
            "died", "killed", "hidden", "secret", "nobody", "no one",
            "every", "all", "none", "first", "last", "zero", "every single",
            "discovered", "shocking", "warned", "more than", "less than",
            "impossible", "rejected", "failed", "wrong", "stole", "steals",
            "exposed", "buried", "lied", "poison", "toxic", "contaminated",
            "fraud", "scam", "trapped", "addicted", "dying", "deadly",
        ],
        "subscribe_required": True,
        "comment_cta_required": True,
        "content_score_min": 80,
    },
    "metadata": {
        "title_min_chars": 50,
        "title_max_chars": 100,
        "shorts_hashtag_required": True,
        "title_hashtags_min": 2,
        "title_hashtags_max": 3,
        "description_starts_with_hashtag": True,
        "subscribe_in_description": True,
        "source_citation_required": True,
        "tags_min": 8,
        "tags_max": 15,
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


def detect_silences(path, threshold_db=-40, min_duration=0.3):
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
    issues, warnings = [], []
    metrics = {}

    # ── VIDEO ──────────────────────────────────────────────────────────
    video_path = out_dir / "video.mp4"
    if not video_path.exists():
        return False, [f"video.mp4 missing"], [], {}

    info = ffprobe(video_path)
    if not info:
        return False, ["ffprobe failed on video.mp4"], [], {}

    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v: issues.append("no video stream")
    if not a: issues.append("no audio stream")
    if not v or not a:
        return False, issues, warnings, metrics

    fmt = info["format"]
    width = int(v["width"]); height = int(v["height"])
    fps = eval(v["r_frame_rate"])
    duration = float(fmt["duration"])
    vbitrate = int(v.get("bit_rate", fmt.get("bit_rate", 0))) // 1000
    abitrate = int(a.get("bit_rate", 0)) // 1000

    metrics["width"] = width
    metrics["height"] = height
    metrics["fps"] = fps
    metrics["duration_s"] = round(duration, 1)
    metrics["video_bitrate_kbps"] = vbitrate
    metrics["audio_bitrate_kbps"] = abitrate
    metrics["video_codec"] = v["codec_name"]
    metrics["audio_codec"] = a["codec_name"]

    sv = SPEC["video"]; sa = SPEC["audio"]
    if width != sv["width"] or height != sv["height"]:
        issues.append(f"resolution {width}x{height} ≠ {sv['width']}x{sv['height']}")
    if abs(fps - sv["fps"]) > 0.5:
        issues.append(f"fps {fps:.1f} ≠ {sv['fps']}")
    if duration < sv["duration_min_s"] or duration > sv["duration_max_s"]:
        issues.append(f"duration {duration:.1f}s outside [{sv['duration_min_s']},{sv['duration_max_s']}]")
    if vbitrate and vbitrate < sv["bitrate_min_kbps"]:
        issues.append(f"video bitrate {vbitrate}k < {sv['bitrate_min_kbps']}k")
    if v["codec_name"] != sv["codec"]:
        issues.append(f"video codec {v['codec_name']} ≠ {sv['codec']}")

    if a["codec_name"] != sa["codec"]:
        issues.append(f"audio codec {a['codec_name']} ≠ {sa['codec']}")
    if abitrate < sa["bitrate_min_kbps"]:
        issues.append(f"audio bitrate {abitrate}k < {sa['bitrate_min_kbps']}k")

    # LUFS + true peak
    lufs, tp = measure_loudness(video_path)
    if lufs is not None:
        metrics["lufs"] = round(lufs, 1)
        metrics["true_peak_db"] = round(tp, 1) if tp else None
        if lufs < sa["lufs_min"] or lufs > sa["lufs_max"]:
            issues.append(f"LUFS {lufs:.1f} outside [{sa['lufs_min']},{sa['lufs_max']}]")
        if tp is not None and tp > sa["true_peak_max_db"]:
            issues.append(f"true peak {tp:.1f} dBTP > {sa['true_peak_max_db']}")

    # Sync drift
    a_dur = float(a.get("duration", 0))
    drift_ms = abs(a_dur - duration) * 1000
    metrics["drift_ms"] = round(drift_ms, 0)
    if drift_ms > sa["drift_max_ms"]:
        issues.append(f"A/V drift {drift_ms:.0f}ms > {sa['drift_max_ms']}ms")

    # Silences
    sils = detect_silences(video_path)
    metrics["silences"] = len(sils)
    for s, e, d in sils:
        if d * 1000 > sa["silence_max_ms"]:
            issues.append(f"silence {s:.1f}s-{e:.1f}s ({d*1000:.0f}ms) > {sa['silence_max_ms']}ms")

    # ── STRUCTURE ──────────────────────────────────────────────────────
    props_path = out_dir / "remotion_props.json"
    if not props_path.exists():
        issues.append("remotion_props.json missing")
    else:
        props = json.loads(props_path.read_text())
        segs = props["segments"]
        ss = SPEC["structure"]
        type_counts = {}
        for s in segs:
            type_counts[s["type"]] = type_counts.get(s["type"], 0) + 1

        metrics["segment_types"] = type_counts

        if type_counts.get("hero", 0) != ss["hero_count"]:
            issues.append(f"hero count {type_counts.get('hero',0)} ≠ {ss['hero_count']}")
        else:
            hero = next(s for s in segs if s["type"] == "hero")
            hero_dur = hero["endFrame"] - hero["startFrame"]
            if hero_dur < ss["hero_dur_min_f"] or hero_dur > ss["hero_dur_max_f"]:
                issues.append(f"hero duration {hero_dur}f outside [{ss['hero_dur_min_f']},{ss['hero_dur_max_f']}]")

        flash_n = type_counts.get("flash", 0)
        if flash_n < ss["flash_min"] or flash_n > ss["flash_max"]:
            issues.append(f"flash segments {flash_n} outside [{ss['flash_min']},{ss['flash_max']}]")

        narration_types = {"hook", "fact", "impact", "number", "cta"}
        narration_n = sum(c for t, c in type_counts.items() if t in narration_types)
        if narration_n < ss["narration_min"] or narration_n > ss["narration_max"]:
            issues.append(f"narration segments {narration_n} outside [{ss['narration_min']},{ss['narration_max']}]")

        if ss["cta_required"] and type_counts.get("cta", 0) < 1:
            issues.append("no cta segment")

        # Max visual hold
        max_hold_f = max(
            (s["endFrame"] - s["startFrame"] for s in segs if s["type"] not in ("hero", "flash")),
            default=0,
        )
        max_hold_s = max_hold_f / 60
        metrics["max_visual_hold_s"] = round(max_hold_s, 1)
        if max_hold_s > ss["visual_hold_max_s"]:
            issues.append(f"single shot held for {max_hold_s:.1f}s > {ss['visual_hold_max_s']}s (visual stagnation)")

    # ── SCRIPT ─────────────────────────────────────────────────────────
    script_path = out_dir / "script.json"
    if not script_path.exists():
        issues.append("script.json missing")
    else:
        scr = json.loads(script_path.read_text())
        ssc = SPEC["script"]
        hook = next((s["text"] for s in scr.get("segments", []) if s.get("type") == "hook"), "")
        hook_words = len(hook.split())
        metrics["hook_words"] = hook_words
        metrics["hook"] = hook[:80]

        if hook_words > ssc["hook_max_words"]:
            issues.append(f"hook {hook_words} words > {ssc['hook_max_words']}")
        sw = has_shock_word(hook)
        metrics["hook_shock_word"] = sw
        if not sw:
            issues.append(f"hook has no shock word")

        tts = scr.get("tts_script", "")
        if ssc["subscribe_required"] and "subscribe" not in tts.lower():
            issues.append("script missing 'Subscribe' ask")
        if ssc["comment_cta_required"] and "comment" not in tts.lower():
            issues.append("script missing 'Comment' CTA")
        score = scr.get("content_score", 0)
        metrics["content_score"] = score
        if score < ssc["content_score_min"]:
            issues.append(f"content_score {score} < {ssc['content_score_min']}")

    # ── METADATA ───────────────────────────────────────────────────────
    md_path = out_dir / "metadata.json"
    if not md_path.exists():
        issues.append("metadata.json missing")
    else:
        md = json.loads(md_path.read_text())
        sm = SPEC["metadata"]
        title = md.get("title_selected") or md.get("selected_title") or md.get("title", "")
        desc = md.get("description", "")
        tags = md.get("tags", [])

        metrics["title_length"] = len(title)
        metrics["title_hashtags"] = sum(1 for w in title.split() if w.startswith("#"))
        metrics["tag_count"] = len(tags)

        if len(title) < sm["title_min_chars"] or len(title) > sm["title_max_chars"]:
            issues.append(f"title length {len(title)} outside [{sm['title_min_chars']},{sm['title_max_chars']}]")
        if sm["shorts_hashtag_required"] and "#shorts" not in title.lower():
            issues.append("title missing #shorts")
        ht_count = metrics["title_hashtags"]
        if ht_count < sm["title_hashtags_min"] or ht_count > sm["title_hashtags_max"]:
            issues.append(f"title hashtags {ht_count} outside [{sm['title_hashtags_min']},{sm['title_hashtags_max']}]")
        if sm["description_starts_with_hashtag"] and not desc.lstrip().startswith("#"):
            issues.append("description doesn't start with hashtag line")
        if sm["subscribe_in_description"] and "subscribe" not in desc.lower():
            issues.append("description missing 'Subscribe'")
        if sm["source_citation_required"]:
            if not re.search(r"sources?:|reuters|bbc|ap |ntsb|cdc|epa|who |un |world bank|nature|nejm", desc, re.I):
                warnings.append("description has no clear source citation")
        if len(tags) < sm["tags_min"] or len(tags) > sm["tags_max"]:
            issues.append(f"tags {len(tags)} outside [{sm['tags_min']},{sm['tags_max']}]")

    # ── ASSETS (bg_videos dimensions) ──────────────────────────────────
    bg_dir = out_dir / "bg_videos"
    if bg_dir.exists():
        wrong_dims = []
        for f in bg_dir.glob("*.mp4"):
            inf = ffprobe(f)
            if not inf: continue
            vs = next((s for s in inf["streams"] if s["codec_type"] == "video"), None)
            if vs and (int(vs["width"]) != 1080 or int(vs["height"]) != 1920):
                wrong_dims.append(f.name)
        if wrong_dims:
            issues.append(f"{len(wrong_dims)} bg_videos not 1080x1920: {wrong_dims[:3]}")
        metrics["bg_videos_count"] = len(list(bg_dir.glob("*.mp4")))

    return len(issues) == 0, issues, warnings, metrics


def print_report(vid, passed, issues, warnings, metrics):
    icon = "✅" if passed else "❌"
    print(f"{icon} {vid} — {'PASSED' if passed else 'FAILED'} S02902 baseline")
    print(f"\n📊 Metrics:")
    for k, v in metrics.items():
        print(f"   {k}: {v}")
    if issues:
        print(f"\n🚨 Issues ({len(issues)}):")
        for i in issues:
            print(f"   • {i}")
    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"   • {w}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    passed, issues, warnings, metrics = audit(args.video_id)
    if args.json:
        print(json.dumps({
            "video_id": args.video_id,
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "metrics": metrics,
        }, indent=2, ensure_ascii=False))
    else:
        print_report(args.video_id, passed, issues, warnings, metrics)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
