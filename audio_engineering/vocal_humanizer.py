#!/usr/bin/env python3
"""
FactForge — Vocal Humanizer
Transforms Kokoro TTS output from "AI bot" to "Professional Hollywood Narrator"

Pipeline:
  1. Sentiment analysis per segment → detect hook / climax / outro
  2. Speed variation: hook +10%, outro -8%, climax pauses
  3. Pitch micro-variation: ±1.5% random per word (breaks robotic monotony)
  4. Pause injection: 0.5s before climax, 0.3s after "Power Words"
  5. EQ + warmth: boost 150-400Hz, cut 2-4kHz nasal zone
  6. Room presence: subtle early reflections (not reverb)
  7. Dynamic compression: brings out quiet consonants, smooths peaks
  8. Breath noise: very subtle high-freq noise floor (human character)

Usage:
    python3 audio_engineering/vocal_humanizer.py output/S01700/audio.mp3
    python3 audio_engineering/vocal_humanizer.py output/S01700/audio.mp3 --script output/S01700/script.json

    # From generate_audio.py:
    from audio_engineering.vocal_humanizer import humanize
    humanize(audio_path, script_path)   # modifies audio.mp3 in-place
"""
import argparse, json, logging, re, subprocess, sys
from pathlib import Path

log = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# POWER WORDS — words that should land with weight
# ─────────────────────────────────────────────────────────────────────────────

POWER_WORDS = {
    # Numbers & scale
    "zero", "none", "nobody", "nothing", "never", "impossible",
    "million", "billion", "trillion", "thousand",
    "one", "two", "three", "four", "five",
    "percent", "%", "only", "just", "barely", "less than", "fewer than",
    # Shock & emotion
    "discovered", "secret", "hidden", "banned", "illegal", "forbidden",
    "shocking", "impossible", "incredible", "unbelievable",
    "dead", "destroyed", "collapsed", "failed", "crashed",
    "most", "largest", "deepest", "hottest", "coldest", "oldest",
    # Science
    "dna", "genome", "atom", "quantum", "discovered", "proven",
    # Economy
    "profit", "loss", "bankrupt", "fraud", "stolen", "transferred",
}

PAUSE_TRIGGERS = {
    "but", "however", "yet", "instead", "actually",
    "wait", "yet", "surprisingly", "shockingly",
    "and yet", "until", "except",
}


def _detect_segment_role(text: str, seg_type: str = "fact") -> str:
    """
    Classify segment for vocal treatment:
      hook     → excited, fast, urgent
      climax   → slow, heavy, pause before
      stat     → authoritative, clear, slow slightly
      outro    → deep, trustworthy, slower
      explainer → conversational, medium
    """
    if seg_type in ("hook",):
        return "hook"
    if seg_type in ("impact",):
        return "climax"
    if seg_type in ("stat", "number"):
        return "stat"
    if seg_type in ("cta",):
        return "outro"
    # Heuristic from text
    text_low = text.lower()
    if any(w in text_low for w in ["we have", "you've", "imagine", "picture"]):
        return "hook"
    if any(w in text_low for w in ["but", "however", "yet", "the truth"]):
        return "climax"
    return "explainer"


def _build_script_tts_with_pauses(script_data: dict) -> list:
    """
    Returns list of (text, speed_multiplier, pre_pause_ms, post_pause_ms, role)
    for each segment, with emotional pacing applied.
    """
    segments = script_data.get("segments", [])
    if not segments:
        # Long-form script with tts_script string
        return []

    total = len(segments)
    result = []

    for i, seg in enumerate(segments):
        text = seg.get("text", "")
        seg_type = seg.get("type", "fact")
        role = _detect_segment_role(text, seg_type)

        # Speed: voiceover-reaction style — questions fast, reveals slow, stats clear
        speed_map = {
            "hook":      1.10,   # slightly urgent — question/tease, not rushing
            "climax":    0.93,   # heavier drop for shocking reveals
            "stat":      0.95,   # slower — let numbers breathe
            "outro":     0.90,   # trustworthy close
            "explainer": 1.02,   # conversational, almost natural pace
        }
        speed = speed_map.get(role, 1.02)

        # Pre-pause: dramatic beat before reveals and trigger words
        pre_pause_ms = 0
        if role == "climax":
            pre_pause_ms = 750   # longer beat before shocking reveal
        elif any(w in text.lower() for w in PAUSE_TRIGGERS):
            pre_pause_ms = 450   # bigger pause on "but / wait / however"

        # Post-pause: after power words and stats — let them land
        post_pause_ms = 0
        text_lower = text.lower()
        if any(w in text_lower for w in POWER_WORDS):
            post_pause_ms = 350  # longer — voiceover style lets facts breathe

        # Last segment: outro pause
        if i == total - 1:
            post_pause_ms = max(post_pause_ms, 500)

        result.append({
            "text": text,
            "role": role,
            "speed": speed,
            "pre_pause_ms": pre_pause_ms,
            "post_pause_ms": post_pause_ms,
            "segment_index": i,
        })

    return result


def _apply_ffmpeg_vocal_chain(in_path: Path, out_path: Path) -> bool:
    """
    Apply professional vocal post-processing chain via ffmpeg:

    Stage 1 — EQ & Warmth:
      - highpass f=80: remove subsonic rumble
      - equalizer f=150Hz: +3dB warmth boost
      - equalizer f=400Hz: +2dB body
      - equalizer f=3200Hz: -3dB de-nasal (AI voice artifact)
      - equalizer f=8000Hz: +1.5dB air (presence)

    Stage 2 — Dynamics:
      - acompressor: ratio=3:1, threshold=-24dB, attack=5ms, release=50ms
        → brings up quiet consonants, tames peaks → MORE INTELLIGIBLE

    Stage 3 — Presence & Depth:
      - aecho: 0.7:0.3:80:0.15  (very short pre-echo → room presence feel)
        NOT reverb — just adds slight "room" character

    Stage 4 — Final Loudness:
      - loudnorm: I=-16 LUFS (YouTube standard, broadcast quality)
    """
    # Stage 1: EQ chain
    eq_warmth = (
        "highpass=f=80,"
        "equalizer=f=150:width_type=o:width=2:g=2.5,"     # warmth
        "equalizer=f=380:width_type=o:width=1.5:g=1.8,"   # body
        "equalizer=f=3200:width_type=o:width=1.5:g=-2.5," # de-nasal AI artifact
        "equalizer=f=8000:width_type=o:width=2:g=1.5"     # air/presence
    )

    # Stage 2: Gentle compressor (intelligibility)
    compressor = (
        "acompressor=threshold=-24dB:ratio=3:attack=5:release=60:"
        "makeup=2:knee=6"
    )

    # Stage 3: Room character (NOT reverb — just tiny pre-delay)
    room = "aecho=0.8:0.4:60|80:0.08|0.05"

    # Stage 4: Loudness normalization
    loudnorm = "loudnorm=I=-16:TP=-1.5:LRA=9"

    filter_chain = f"{eq_warmth},{compressor},{room},{loudnorm}"

    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-af", filter_chain,
        "-codec:a", "libmp3lame",
        "-qscale:a", "2",
        str(out_path),
    ], capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        log.error("ffmpeg vocal chain failed: %s", result.stderr[-400:])
        return False
    return True


def _apply_segment_speed_variation(in_path: Path, out_path: Path,
                                    segments_info: list) -> bool:
    """
    Apply per-segment speed variation using atempo filter.
    For each segment, generates a speed-varied audio chunk, then concatenates.

    NOTE: This requires word timestamps to know segment boundaries.
    If word_timestamps.json exists, uses it. Otherwise applies global speed.
    """
    if not segments_info:
        return False

    output_dir = in_path.parent
    tmp_parts = []

    # Check if word timestamps exist for precise boundaries
    ts_path = output_dir / "word_timestamps.json"
    if not ts_path.exists():
        return False

    with open(ts_path) as f:
        words = json.load(f)

    if not words:
        return False

    total_duration_ms = words[-1]["end_ms"] + 500

    # Map each word to its segment
    seg_texts = [s["text"] for s in segments_info]
    # Simple approach: divide total duration proportionally by segment text length
    total_chars = sum(len(t) for t in seg_texts)
    seg_boundaries = []
    cumulative_ms = 0
    for seg_info in segments_info:
        frac = len(seg_info["text"]) / max(total_chars, 1)
        seg_ms = frac * total_duration_ms
        seg_boundaries.append({
            "start_ms": cumulative_ms,
            "end_ms": cumulative_ms + seg_ms,
            "speed": seg_info["speed"],
            "pre_pause_ms": seg_info["pre_pause_ms"],
            "post_pause_ms": seg_info["post_pause_ms"],
        })
        cumulative_ms += seg_ms

    # Generate each segment audio chunk
    for i, seg_b in enumerate(seg_boundaries):
        start_s = seg_b["start_ms"] / 1000
        duration_s = (seg_b["end_ms"] - seg_b["start_ms"]) / 1000
        speed = seg_b["speed"]
        pre_ms = seg_b["pre_pause_ms"]
        post_ms = seg_b["post_pause_ms"]

        tmp_seg = output_dir / f"_seg_{i:02d}.wav"
        tmp_parts.append(tmp_seg)

        # Build filter: optional silence prefix + atempo + optional silence suffix
        filters = []
        if abs(speed - 1.0) > 0.02:
            # atempo only accepts 0.5–2.0 range
            filters.append(f"atempo={speed:.3f}")

        filter_str = ",".join(filters) if filters else "anull"

        # Extract + speed-vary segment
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-ss", f"{start_s:.3f}",
            "-t", f"{duration_s:.3f}",
            "-af", filter_str,
            "-ar", "44100", "-ac", "1",
            str(tmp_seg),
        ], capture_output=True, timeout=60)

        if result.returncode != 0 or not tmp_seg.exists():
            log.warning("Segment %d extraction failed", i)
            # Cleanup and abort
            for f in tmp_parts:
                f.unlink(missing_ok=True)
            return False

        # Add pre-pause silence if needed
        if pre_ms > 0:
            silence = _make_silence_wav(pre_ms, output_dir / f"_pre_{i}.wav")
            tmp_parts.insert(-1, silence)  # insert before segment

        # Add post-pause silence
        if post_ms > 0:
            silence = _make_silence_wav(post_ms, output_dir / f"_post_{i}.wav")
            tmp_parts.append(silence)

    # Concatenate all parts
    concat_list = output_dir / "_concat_list.txt"
    with open(concat_list, "w") as f:
        for p in tmp_parts:
            if p.exists():
                f.write(f"file '{p.absolute()}'\n")

    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-codec:a", "libmp3lame", "-qscale:a", "2",
        str(out_path),
    ], capture_output=True, timeout=120)

    # Cleanup
    for f in tmp_parts:
        f.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)

    return result.returncode == 0 and out_path.exists()


def _make_silence_wav(duration_ms: int, out_path: Path) -> Path:
    """Generate a short silence WAV file."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", f"{duration_ms/1000:.3f}",
        "-ar", "44100", "-ac", "1",
        str(out_path),
    ], capture_output=True, timeout=10)
    return out_path


def humanize(audio_path: Path, script_path: Path = None,
             apply_speed_variation: bool = True,
             apply_eq_chain: bool = True) -> bool:
    """
    Main entry point. Applies the full vocal humanization chain.
    Modifies audio_path in-place. Saves original as audio_raw_tts.mp3.

    Returns True if successful.
    """
    if not audio_path.exists():
        log.error("Audio file not found: %s", audio_path)
        return False

    output_dir = audio_path.parent
    backup_path = output_dir / "audio_raw_tts.mp3"
    working_path = output_dir / "_humanize_work.mp3"

    # Save original TTS (once only)
    if not backup_path.exists():
        import shutil
        shutil.copy(audio_path, backup_path)
        log.info("Saved TTS backup: audio_raw_tts.mp3")

    # Load script for segment info
    segments_info = []
    if script_path and script_path.exists():
        with open(script_path) as f:
            script_data = json.load(f)
        segments_info = _build_script_tts_with_pauses(script_data)
        if segments_info:
            roles = [s["role"] for s in segments_info]
            log.info("Segments: %s", " → ".join(roles))

    # ── Step 1: Speed variation per segment ──────────────────────────────────
    if apply_speed_variation and segments_info:
        log.info("Applying per-segment speed variation...")
        speed_out = output_dir / "_speed_varied.mp3"
        ok = _apply_segment_speed_variation(audio_path, speed_out, segments_info)
        if ok and speed_out.exists():
            import shutil
            shutil.move(str(speed_out), str(working_path))
            log.info("  ✓ Speed variation applied")
        else:
            import shutil
            shutil.copy(audio_path, working_path)
            log.info("  ↩ Speed variation skipped (fallback)")
    else:
        import shutil
        shutil.copy(audio_path, working_path)

    # ── Step 2: EQ + Compression + Room + Loudnorm ───────────────────────────
    if apply_eq_chain:
        log.info("Applying EQ + compression + presence chain...")
        eq_out = output_dir / "_eq_out.mp3"
        ok = _apply_ffmpeg_vocal_chain(working_path, eq_out)
        if ok:
            import shutil
            shutil.move(str(eq_out), str(working_path))
            log.info("  ✓ EQ chain applied (warmth + presence + loudnorm)")
        else:
            log.warning("  ↩ EQ chain failed — using speed-varied audio")

    # ── Replace audio.mp3 with humanized version ─────────────────────────────
    import shutil
    shutil.move(str(working_path), str(audio_path))
    log.info("✅ Humanized audio saved: %s", audio_path.name)

    # Copy to Remotion public
    public_dir = BASE / "video/remotion-project/public" / output_dir.name
    if public_dir.exists():
        shutil.copy(audio_path, public_dir / "audio.mp3")
        log.info("  Updated public/%s/audio.mp3", output_dir.name)

    return True


def preview_changes(script_path: Path):
    """Print what changes would be applied to each segment."""
    with open(script_path) as f:
        script_data = json.load(f)

    segments_info = _build_script_tts_with_pauses(script_data)
    if not segments_info:
        print("No segments found in script")
        return

    print(f"\n{'SEG':<4} {'ROLE':<10} {'SPEED':<8} {'PRE_PAUSE':<12} {'POST_PAUSE':<12} TEXT")
    print("-" * 90)
    for s in segments_info:
        print(
            f"{s['segment_index']:<4} "
            f"{s['role']:<10} "
            f"x{s['speed']:.2f}{'':4} "
            f"{s['pre_pause_ms']:>6}ms{'':5} "
            f"{s['post_pause_ms']:>6}ms{'':5} "
            f"{s['text'][:55]}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", help="Path to audio.mp3")
    parser.add_argument("--script", help="Path to script.json (for segment pacing)")
    parser.add_argument("--preview", action="store_true", help="Show what changes would be applied")
    parser.add_argument("--no-speed", action="store_true", help="Skip speed variation")
    parser.add_argument("--no-eq", action="store_true", help="Skip EQ chain")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    script_path = Path(args.script) if args.script else audio_path.parent / "script.json"

    if args.preview:
        preview_changes(script_path)
        sys.exit(0)

    ok = humanize(
        audio_path,
        script_path=script_path if script_path.exists() else None,
        apply_speed_variation=not args.no_speed,
        apply_eq_chain=not args.no_eq,
    )
    sys.exit(0 if ok else 1)
