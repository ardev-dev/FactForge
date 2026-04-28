"""
FactForge Audio Generator
Generates TTS audio + word-level timestamps using:
  - Kokoro TTS (am_echo, Apache 2.0 — commercial safe) ← DEFAULT
  - faster-whisper (base model) for word timestamps
  - Procedural SFX (numpy) — whoosh, tick, heartbeat — mixed into final audio

Usage:
  python3 scripts/generate_audio.py <video_id>
  python3 scripts/generate_audio.py <video_id> --no-sfx   # skip SFX mixing
  e.g.: python3 scripts/generate_audio.py S01220

Voice: am_echo (American male, Kokoro v1.0)
Model files: models/kokoro/kokoro-v1.0.onnx + voices-v1.0.bin
"""

import os, json, sys, shutil, argparse, logging
from pathlib import Path
import soundfile as sf
import numpy as np

# Fix espeak-ng path for kokoro_onnx/phonemizer on macOS
os.environ["PHONEMIZER_ESPEAK_PATH"] = "/opt/homebrew/bin/espeak-ng"
os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = "/opt/homebrew/lib/libespeak-ng.dylib"
try:
    import espeakng_loader
    os.environ["ESPEAK_DATA_PATH"] = espeakng_loader.get_data_path()
except ImportError:
    pass
import requests

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent

# ── Kokoro config ─────────────────────────────────────────────────────────────
KOKORO_MODEL  = BASE / "models/kokoro/kokoro-v1.0.onnx"
KOKORO_VOICES = BASE / "models/kokoro/voices.json"
KOKORO_VOICE  = "am_echo"    # chosen voice — clear, authoritative, commercial safe
KOKORO_SPEED  = 1.08         # slightly faster for Shorts energy (1.0 = normal)

# ── Whisper config ────────────────────────────────────────────────────────────
WHISPER_MODEL = "base"       # base is more accurate than tiny for word timestamps

_kokoro  = None
_whisper = None


def get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        logger.info("Loading Kokoro model...")
        _kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    return _kokoro


def get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper base model...")
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper


def generate_tts(text: str, out_path: Path, voice: str = KOKORO_VOICE, speed: float = KOKORO_SPEED) -> float:
    """Generate audio with Kokoro TTS. Returns duration in seconds."""
    k = get_kokoro()
    samples, sr = k.create(text, voice=voice, speed=speed, lang="en-us")

    # Save as WAV first, then convert to MP3 via ffmpeg for compatibility
    wav_path = out_path.with_suffix(".wav")
    sf.write(str(wav_path), samples, sr)

    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-i", str(wav_path),
        "-b:a", "192k", str(out_path)
    ], capture_output=True)
    wav_path.unlink()

    duration = len(samples) / sr
    logger.info("Audio: %s (%.1fs, voice=%s)", out_path.name, duration, voice)
    return duration


def get_word_timestamps(audio_path: Path) -> list:
    """Extract word-level timestamps using faster-whisper."""
    model = get_whisper()
    segments, _ = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language="en",
        beam_size=5,
    )
    words = []
    for seg in segments:
        for w in seg.words:
            word = w.word.strip()
            if not word:
                continue
            words.append({
                "word": word,
                "start_ms": round(w.start * 1000),
                "end_ms":   round(w.end   * 1000),
            })
    logger.info("Word timestamps: %d words, last at %.1fs", len(words), words[-1]['end_ms'] / 1000)
    return words


# ── Context-Aware SFX Engine ─────────────────────────────────────────────────

SFX_CONFIG_PATH = BASE / "audio_engineering" / "sfx_config.json"
SFX_ASSETS_DIR  = BASE / "audio_engineering" / "assets" / "sfx"
_sfx_config = None
_sfx_cache: dict = {}  # topic/name → np.ndarray


def _load_sfx_config() -> dict:
    global _sfx_config
    if _sfx_config is None and SFX_CONFIG_PATH.exists():
        with open(SFX_CONFIG_PATH) as f:
            _sfx_config = json.load(f)
    return _sfx_config or {}


def _detect_topic(script_data: dict) -> str:
    """Detect video topic from title + script text → return topic key."""
    cfg = _load_sfx_config()
    title = (script_data.get("title", "") + " " + script_data.get("tts_script", "")).lower()
    best_topic = "universal"
    best_count = 0
    for topic, info in cfg.get("topic_detection", {}).items():
        if topic == "universal":
            continue
        count = sum(1 for kw in info.get("keywords", []) if kw in title)
        if count > best_count:
            best_count = count
            best_topic = topic
    logger.info("SFX topic detected: %s (score=%d)", best_topic, best_count)
    return best_topic


def _load_sfx_wav(topic: str, sfx_name: str, sr_target: int = 44100) -> np.ndarray:
    """
    Load an SFX asset. Priority order:
      1. Real asset (mp3) from audio_engineering/assets/sfx_real/{topic}/{name}.mp3
      2. Procedural asset (wav) from audio_engineering/assets/sfx/{topic}/{name}.wav
      3. Universal fallback
    """
    cache_key = f"{topic}/{sfx_name}"
    if cache_key in _sfx_cache:
        return _sfx_cache[cache_key]

    SFX_REAL_DIR = BASE / "audio_engineering" / "assets" / "sfx_real"

    # 1. Real downloaded asset (mp3)
    real_mp3  = SFX_REAL_DIR / topic / f"{sfx_name}.mp3"
    real_wav  = SFX_REAL_DIR / topic / f"{sfx_name}.wav"
    proc_wav  = SFX_ASSETS_DIR / topic / f"{sfx_name}.wav"
    fallback  = SFX_ASSETS_DIR / "universal" / f"{sfx_name}.wav"

    path = None
    for candidate in [real_mp3, real_wav, proc_wav, fallback]:
        if candidate.exists():
            path = candidate
            break

    if path is None:
        logger.warning("SFX not found: %s/%s — regenerating...", topic, sfx_name)
        _ensure_sfx_generated(topic)
        path = proc_wav if proc_wav.exists() else None

    if path is None:
        logger.warning("SFX still missing after regen: %s — using silence", sfx_name)
        _sfx_cache[cache_key] = np.zeros(int(sr_target * 0.1), dtype=np.float32)
        return _sfx_cache[cache_key]

    wav_path = path
    fallback  = SFX_ASSETS_DIR / "universal" / f"{sfx_name}.wav"
    if path is None:
        logger.warning("SFX not found: %s/%s — regenerating...", topic, sfx_name)
        _ensure_sfx_generated(topic)
        path = wav_path if wav_path.exists() else None

    if path is None:
        logger.warning("SFX still missing after regen: %s — using silence", sfx_name)
        _sfx_cache[cache_key] = np.zeros(int(sr_target * 0.1), dtype=np.float32)
        return _sfx_cache[cache_key]

    data, sr = sf.read(str(path))
    data = data.astype(np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)  # stereo → mono

    # Resample if needed (simple linear interpolation)
    if sr != sr_target:
        new_len = int(len(data) * sr_target / sr)
        data = np.interp(
            np.linspace(0, len(data) - 1, new_len),
            np.arange(len(data)), data
        ).astype(np.float32)

    _sfx_cache[cache_key] = data
    return data


def _ensure_sfx_generated(topic: str = None):
    """Run generate_sfx.py if assets don't exist."""
    import subprocess as _sp
    gen_script = BASE / "audio_engineering" / "generate_sfx.py"
    if not gen_script.exists():
        return
    cmd = ["python3", str(gen_script)]
    if topic:
        cmd += ["--topic", topic]
    _sp.run(cmd, capture_output=True)


def _mix_sfx_into_audio(audio_path: Path, props_path: Path, script_path: Path = None,
                         sr_target: int = 44100) -> None:
    """
    Context-aware SFX mixer — 3-tier audio design:
      Tier 1: BGM (ambient music, already mixed by caller)
      Tier 2: Precision SFX (topic-matched, max 5 events per 40s, min 3s gap)
      Tier 3: Ambient bed (future enhancement)

    Placement logic:
      - Hook segment (i=0): mandatory SFX for high-impact opening
      - Stat/number segments: coin/ping/beep matching topic
      - Impact segments: heavy impact matching topic
      - Scene transitions: max 3 transition SFX spread across video
      - Final segment: closing sting
      - NEVER fire 2 SFX within 3 seconds of each other
    """
    if not props_path.exists():
        return

    props = json.loads(props_path.read_text())
    segments = props.get("segments", [])
    fps = props.get("fps", 60)
    if not segments:
        return

    # Load script for topic detection
    script_data = {}
    if script_path and script_path.exists():
        with open(script_path) as f:
            script_data = json.load(f)
    elif (audio_path.parent / "script.json").exists():
        with open(audio_path.parent / "script.json") as f:
            script_data = json.load(f)

    # Detect topic and get SFX map
    cfg = _load_sfx_config()
    topic = _detect_topic(script_data)
    topic_cfg = cfg.get("topic_detection", {}).get(topic, cfg["topic_detection"]["universal"])
    sfx_map = topic_cfg["sfx_map"]
    volumes  = topic_cfg["volumes"]
    rules    = cfg.get("placement_rules", {})

    min_gap_samples = int(rules.get("min_gap_between_sfx_ms", 3000) / 1000 * sr_target)
    max_sfx = rules.get("max_sfx_per_40s", 5)

    # Pre-generate SFX assets if missing
    test_path = SFX_ASSETS_DIR / topic / f"{sfx_map['transition']}.wav"
    if not test_path.exists():
        logger.info("Generating SFX assets for topic '%s'...", topic)
        _ensure_sfx_generated(topic)
        _ensure_sfx_generated("universal")

    # Load main audio
    import subprocess as _sp
    tmp_wav = audio_path.with_suffix(".sfx_work.wav")
    _sp.run([
        "ffmpeg", "-y", "-i", str(audio_path),
        "-ar", str(sr_target), "-ac", "1", str(tmp_wav)
    ], capture_output=True)

    if not tmp_wav.exists():
        return

    audio_data, sr = sf.read(str(tmp_wav))
    audio_data = audio_data.astype(np.float32)
    total_samples = len(audio_data)

    def frame_to_sample(frame: int) -> int:
        return min(int(frame / fps * sr), total_samples - 1)

    def mix_at(sfx: np.ndarray, pos: int, volume: float = 1.0):
        end = min(pos + len(sfx), total_samples)
        length = end - pos
        audio_data[pos:end] += sfx[:length] * volume

    # ── Build SFX event list ─────────────────────────────────────────────────
    events = []  # (sample_pos, sfx_name, volume, reason)
    total_segs = len(segments)
    transition_count = 0
    max_transitions = min(3, total_segs // 4)

    # Identify key segments
    allowed_transitions = set()
    if total_segs > 1:
        # Spread transitions: ~25%, ~50%, ~75%
        for frac in [0.25, 0.50, 0.75]:
            idx = max(1, int(total_segs * frac))
            allowed_transitions.add(idx)

    for i, seg in enumerate(segments):
        seg_type = seg.get("type", "fact")
        start_frame = seg.get("startFrame", 0)
        pos = frame_to_sample(start_frame)

        if i == 0:
            # Hook: mandatory high-impact SFX
            sfx_name = sfx_map.get("hook", sfx_map["transition"])
            events.append((pos, topic, sfx_name, volumes.get("hook", 0.25), "hook"))

        elif seg_type in ("impact",) :
            sfx_name = sfx_map.get("impact", sfx_map["transition"])
            events.append((pos, topic, sfx_name, volumes.get("impact", 0.28), "impact"))

        elif seg_type in ("stat", "number"):
            sfx_name = sfx_map.get("stat", sfx_map["transition"])
            events.append((pos, topic, sfx_name, volumes.get("stat", 0.28), "stat"))

        elif i in allowed_transitions and transition_count < max_transitions:
            sfx_name = sfx_map.get("transition")
            events.append((pos, topic, sfx_name, volumes.get("transition", 0.20), "transition"))
            transition_count += 1

        # Final segment: closing sting (universal)
        if i == total_segs - 1:
            sfx_name = rules.get("final_segment_sfx", "reveal_sting")
            vol = rules.get("final_segment_volume", 0.20)
            events.append((pos, "universal", sfx_name, vol, "final"))

    # ── Apply minimum gap filter ──────────────────────────────────────────────
    events.sort(key=lambda e: e[0])
    last_pos = -min_gap_samples
    applied = []
    sfx_log = {}
    for (pos, ev_topic, sfx_name, vol, reason) in events:
        if pos - last_pos < min_gap_samples and reason not in ("hook", "final"):
            continue  # too close — skip
        if len(applied) >= max_sfx and reason not in ("hook", "final"):
            continue  # cap reached
        sfx_data = _load_sfx_wav(ev_topic, sfx_name, sr)
        mix_at(sfx_data, pos, volume=vol)
        last_pos = pos
        applied.append((pos, sfx_name, reason))
        sfx_log[reason] = sfx_log.get(reason, 0) + 1

    # ── Normalize to prevent clipping ────────────────────────────────────────
    peak = np.max(np.abs(audio_data))
    if peak > 0.95:
        audio_data = (audio_data * 0.92 / peak).astype(np.float32)

    # Save backup then overwrite
    clean_backup = audio_path.parent / "audio_clean.mp3"
    if not clean_backup.exists():
        import shutil as _sh
        _sh.copy(audio_path, clean_backup)

    sf.write(str(tmp_wav), audio_data, sr)
    _sp.run(["ffmpeg", "-y", "-i", str(tmp_wav),
             "-b:a", "192k", str(audio_path)], capture_output=True)
    tmp_wav.unlink(missing_ok=True)

    log_str = " | ".join(f"{k}×{v}" for k, v in sfx_log.items())
    logger.info("SFX [%s] applied %d events: %s", topic, len(applied), log_str)


def mix_background_music(video_id: str, volume: float = 0.10) -> None:
    """
    Download a CC0 instrumental track from Pixabay Music and mix it into
    audio.mp3 at `volume` (default 10%).  Saves audio_clean.mp3 as backup.
    The final file is audio.mp3 with vocals loud, music soft in the background.
    """
    import subprocess
    output_dir = BASE / "output" / video_id
    audio_path = output_dir / "audio.mp3"
    if not audio_path.exists():
        logger.warning("[music] audio.mp3 not found for %s — skipping", video_id)
        return

    PIXABAY_MUSIC_KEY = "55448442-b529cb16ef94bcaa210308891"
    music_path = output_dir / "bg_music.mp3"

    # ── Download background track ─────────────────────────────────────────────
    if not music_path.exists():
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_MUSIC_KEY,
                    "q": "background music instrumental",
                    "media_type": "music",
                    "per_page": 10,
                    "category": "music",
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            hits = data.get("hits", [])
            if not hits:
                logger.warning("[music] No tracks found from Pixabay Music — skipping")
                return
            # Try each hit until we get a downloadable URL
            track_url = None
            for hit in hits:
                # Pixabay music API returns audio field or previewURL
                track_url = (
                    hit.get("audio")
                    or hit.get("previewURL")
                    or hit.get("url")
                )
                if track_url:
                    break
            if not track_url:
                logger.warning("[music] No downloadable audio URL found — skipping")
                return

            logger.info("Downloading bg music: %s...", track_url[:60])
            dl = requests.get(track_url, timeout=60, stream=True)
            dl.raise_for_status()
            with open(music_path, "wb") as fh:
                for chunk in dl.iter_content(chunk_size=1024 * 256):
                    fh.write(chunk)
            logger.info("bg_music.mp3 saved (%d KB)", music_path.stat().st_size // 1024)
        except Exception as exc:
            logger.error("[music] Download failed: %s — skipping", exc)
            return

    # ── Backup clean audio ────────────────────────────────────────────────────
    clean_backup = output_dir / "audio_clean.mp3"
    if not clean_backup.exists():
        import shutil as _shutil
        _shutil.copy(audio_path, clean_backup)

    # ── Mix with ffmpeg ───────────────────────────────────────────────────────
    mixed_path = output_dir / "audio_with_music.mp3"
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={volume}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[out]",
            "-map", "[out]",
            "-codec:a", "libmp3lame", "-q:a", "2",
            str(mixed_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("[music] ffmpeg mix failed: %s", result.stderr[-300:])
        return

    # Replace audio.mp3 with mixed version
    import os as _os
    _os.replace(str(mixed_path), str(audio_path))
    logger.info("Background music mixed at %d%% — audio.mp3 updated", int(volume * 100))


def produce_audio(video_id: str, text: str = None, speed: float = KOKORO_SPEED,
                  sfx: bool = True, music: bool = False, humanize: bool = True) -> dict:
    """
    Full pipeline: text → Kokoro TTS → vocal humanization → timestamps → SFX mix.
    Returns {"audio_path": Path, "words": [...], "duration_seconds": float}

    Steps:
      1. Kokoro TTS → raw audio.mp3
      2. Vocal humanizer: EQ warmth + compression + room presence + per-segment speed
      3. Whisper word timestamps
      4. SFX mix (context-aware, topic-matched)
    """
    output_dir = BASE / "output" / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get text from script.json if not provided
    script_path = output_dir / "script.json"
    if text is None:
        if not script_path.exists():
            logger.error("%s not found", script_path)
            sys.exit(1)
        with open(script_path) as f:
            script = json.load(f)
        text = script.get("tts_text_final") or script.get("full_text") or script.get("tts_script", "")

    audio_path = output_dir / "audio.mp3"

    logger.info("[1/4] Kokoro TTS (%s) for %s...", KOKORO_VOICE, video_id)
    duration = generate_tts(text, audio_path, voice=KOKORO_VOICE, speed=speed)

    # ── Step 2: Vocal Humanization ───────────────────────────────────────────
    if humanize:
        logger.info("[2/4] Vocal humanization (EQ + compression + warmth)...")
        try:
            import sys as _sys
            _sys.path.insert(0, str(BASE))
            from audio_engineering.vocal_humanizer import humanize as _humanize
            _humanize(
                audio_path,
                script_path=script_path if script_path.exists() else None,
                apply_speed_variation=True,
                apply_eq_chain=True,
            )
        except Exception as e:
            logger.warning("Vocal humanizer failed (%s) — using raw TTS", e)
    else:
        logger.info("[2/4] Vocal humanization skipped")

    logger.info("[3/4] Word timestamps (Whisper base)...")
    words = get_word_timestamps(audio_path)

    ts_path = output_dir / "word_timestamps.json"
    with open(ts_path, "w") as f:
        json.dump(words, f, indent=2)

    # Mix SFX into audio (context-aware topic-matched SFX)
    if sfx:
        props_path = output_dir / "remotion_props.json"
        if props_path.exists():
            logger.info("[4/4] Mixing SFX...")
            _mix_sfx_into_audio(audio_path, props_path)
        else:
            logger.info("[SFX] No remotion_props.json yet — SFX will be applied after props are built")

        # Mix background music after SFX (bundled with SFX pass)
        if music:
            logger.info("Mixing background music (10%)...")
            mix_background_music(video_id)

    # Copy to Remotion public
    public_dir = BASE / "video/remotion-project/public" / video_id
    public_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(audio_path, public_dir / "audio.mp3")
    logger.info("Copied to public/%s/audio.mp3", video_id)

    logger.info("[3/3] Done — %.1fs, %d words", duration, len(words))
    return {"audio_path": audio_path, "words": words, "duration_seconds": duration}


def apply_sfx(video_id: str) -> None:
    """Apply SFX to existing audio after remotion_props.json is ready. Call after step_props."""
    output_dir = BASE / "output" / video_id
    audio_path = output_dir / "audio.mp3"
    props_path = output_dir / "remotion_props.json"
    clean_path = output_dir / "audio_clean.mp3"

    if not audio_path.exists():
        logger.warning("[SFX] audio.mp3 not found for %s", video_id)
        return
    if not props_path.exists():
        logger.warning("[SFX] remotion_props.json not found for %s", video_id)
        return
    if clean_path.exists():
        logger.info("[SFX] Already applied (audio_clean.mp3 exists) — skipping")
        return

    logger.info("Mixing SFX into %s/audio.mp3...", video_id)
    _mix_sfx_into_audio(audio_path, props_path)

    # Re-copy to Remotion public
    public_dir = BASE / "video/remotion-project/public" / video_id
    public_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(audio_path, public_dir / "audio.mp3")
    logger.info("Updated public/%s/audio.mp3 with SFX", video_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FactForge audio generator")
    parser.add_argument("video_id", help="Video ID e.g. S01220")
    parser.add_argument("--no-sfx", action="store_true", help="Skip SFX mixing")
    parser.add_argument("--sfx-only", action="store_true", help="Apply SFX to existing audio (after props are built)")
    parser.add_argument("--music", action="store_true", help="Mix CC0 background music at 10% (bundled with SFX pass)")
    parser.add_argument("--no-music", action="store_true", help="Disable background music mixing (default)")
    args = parser.parse_args()

    use_music = args.music and not args.no_music

    if args.sfx_only:
        apply_sfx(args.video_id)
    else:
        produce_audio(args.video_id, sfx=not args.no_sfx, music=use_music)
