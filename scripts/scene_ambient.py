#!/usr/bin/env python3
"""
scene_ambient.py — Per-scene ambient foley layer.

Reads remotion_props.json, matches each segment's scene_query to an ambient
loop, mixes a continuous foley bed beneath the existing audio. Each segment
gets its OWN ambient that crossfades into the next one.

Hollywood / MrBeast principle: every visible action has audible texture.
Walking → footsteps. Rain → rain hiss. Hospital → cardiac beep. Lab →
glassware tinkle. Courtroom → murmur. Etc.

Mixing recipe:
  • Ambient at -28 dB (sits well below dialog/BGM)
  • 250 ms crossfade between adjacent segment ambients (no clicks)
  • Each ambient loops to fill its segment duration
  • Silently skipped if no keyword matches (no random noise)

Usage:
  python3 scripts/scene_ambient.py S02901
"""
import argparse, json, math, re, subprocess, sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
AMBIENT_DIR = ROOT / "audio_engineering/assets/ambient"
AMBIENT_DB = -28          # dB under voice
CROSSFADE_S = 0.25
SR = 24000


# ─── Keyword → ambient mapping ──────────────────────────────────────────────
# Order matters: more specific keywords first so they take priority.
SCENE_MAP = [
    # specific environments
    (["rain", "raining", "rainfall", "downpour", "storm rain"],     "rain"),
    (["wind", "windy", "stormy wind", "gust"],                       "wind"),
    (["ocean", "sea", "wave", "shore", "beach", "coastal"],          "ocean"),
    (["water drop", "drip", "leak", "tap dripping"],                 "water_drops"),
    (["fire", "flame", "burning", "campfire", "torch"],              "fire_crackle"),
    # human actions
    (["walking", "walk ", "marching", "pavement", "street walk"],    "footsteps_pavement"),
    (["walking indoor", "corridor walk", "hallway walk", "footstep"], "footsteps_indoor"),
    # medical / health
    (["hospital", "icu", "medical", "ambulance", "ekg", "heart monitor", "scan", "x-ray", "patient"], "hospital_beeps"),
    (["heart", "blood drop", "cardiac", "pulse", "vein"],            "heartbeat"),
    # corporate / industry
    (["factory", "industrial", "smokestack", "machinery", "production line", "assembly", "plant"], "factory_industrial"),
    (["laboratory", "lab", "petri", "microscope", "test tube", "chemistry", "research papers"], "lab_glassware"),
    (["courtroom", "court", "gavel", "trial", "judge", "settlement document", "legal"], "courtroom_murmur"),
    (["city", "traffic", "street", "downtown", "urban", "intersection", "skyscraper"], "city_traffic"),
    (["office", "keyboard", "computer screen", "typing", "data entry"], "office_keyboard"),
    (["money", "cash", "bills", "dollars", "coins", "wallet", "stack of money"], "money_counting"),
    (["crowd", "people walking", "many people", "audience", "march", "protest"], "crowd_chatter"),
    # data / sci-fi / digital
    (["data", "digital", "screen", "graph", "chart", "matrix", "code", "molecular", "abstract scientific"], "sci_fi_data"),
    (["paper", "document", "manuscript", "files", "archive", "filing cabinet", "old document"], "paper_rustle"),
]


def match_ambient(scene_query: str) -> Optional[str]:
    """Return matching ambient name (no extension) or None.
    Uses WORD-BOUNDARY matching to prevent false positives like
    'sea' matching inside 'research'."""
    if not scene_query:
        return None
    q = scene_query.lower()
    for keywords, ambient in SCENE_MAP:
        for kw in keywords:
            kw = kw.strip().lower()
            # Multi-word phrase: substring with surrounding spaces is fine
            if " " in kw:
                if kw in q:
                    if (AMBIENT_DIR / f"{ambient}.wav").exists():
                        return ambient
            else:
                # Single word: must be a whole word
                if re.search(rf"\b{re.escape(kw)}\b", q):
                    if (AMBIENT_DIR / f"{ambient}.wav").exists():
                        return ambient
    return None


def apply_ambients(video_id: str, fps: int = 60) -> bool:
    """Mix per-segment ambients into the existing video.mp4 audio track."""
    out_dir = ROOT / "output" / video_id
    video = out_dir / "video.mp4"
    props_path = out_dir / "remotion_props.json"
    if not video.exists() or not props_path.exists():
        print(f"❌ {video_id}: missing video.mp4 or remotion_props.json")
        return False

    props = json.loads(props_path.read_text())
    segments = props["segments"]

    # Build per-segment ambient plan
    plan = []
    for i, seg in enumerate(segments):
        ambient = match_ambient(seg.get("scene_query", ""))
        start_s = seg["startFrame"] / fps
        end_s   = seg["endFrame"]   / fps
        plan.append({
            "idx": i,
            "type": seg.get("type"),
            "scene": seg.get("scene_query", "")[:50],
            "ambient": ambient,
            "start": start_s,
            "end": end_s,
        })

    matched = sum(1 for p in plan if p["ambient"])
    print(f"📋 {matched}/{len(plan)} segments matched ambients:")
    for p in plan:
        tag = p["ambient"] or "—"
        print(f"  {p['idx']:>2} {p['type']:<8} {p['start']:>5.1f}s-{p['end']:<5.1f}s  →  {tag:<22} «{p['scene']}»")

    if matched == 0:
        print("⚠ no ambients matched — leaving audio as-is")
        return True

    # ─── Build ffmpeg filter graph ─────────────────────────────────────────
    # We add each ambient as an input, trim/loop it to segment duration,
    # delay it to its start time, fade in/out, and amix everything.
    inputs = ["-i", str(video)]
    chains, mix_labels = [], ["[0:a]"]
    amix_count = 1

    for p in plan:
        if not p["ambient"]:
            continue
        amb_path = AMBIENT_DIR / f"{p['ambient']}.wav"
        inputs += ["-stream_loop", "-1", "-i", str(amb_path)]
        in_idx = amix_count   # ffmpeg input index
        seg_dur = p["end"] - p["start"]
        delay_ms = int(p["start"] * 1000)
        fade_in  = min(CROSSFADE_S, seg_dur / 4)
        fade_out = min(CROSSFADE_S, seg_dur / 4)
        label = f"a{p['idx']}"
        chain = (
            f"[{in_idx}:a]"
            f"atrim=0:{seg_dur:.3f},asetpts=PTS-STARTPTS,"
            f"volume={AMBIENT_DB}dB,"
            f"afade=t=in:st=0:d={fade_in:.3f},"
            f"afade=t=out:st={seg_dur - fade_out:.3f}:d={fade_out:.3f},"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        chains.append(chain)
        mix_labels.append(f"[{label}]")
        amix_count += 1

    if amix_count == 1:
        return True  # nothing to mix

    mix = "".join(mix_labels) + f"amix=inputs={amix_count}:duration=first:dropout_transition=0:normalize=0[aout]"
    fc = ";".join(chains + [mix])

    out_video = out_dir / "video_with_ambient.mp4"
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart",
        str(out_video),
    ]
    print(f"\n🎚  mixing {amix_count - 1} ambient layers via ffmpeg...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ ffmpeg failed:\n{r.stderr[-800:]}")
        return False

    out_video.replace(video)
    print(f"✅ ambient layer mixed → {video.name}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    args = ap.parse_args()
    ok = apply_ambients(args.video_id)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
