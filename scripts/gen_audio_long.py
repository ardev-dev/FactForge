#!/usr/bin/env python3
"""Generate audio for long-form documentary videos."""
import json, sys, shutil, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent
KOKORO_MODEL  = BASE / "models/kokoro/kokoro-v1.0.onnx"
KOKORO_VOICES = BASE / "models/kokoro/voices-v1.0.bin"
VOICE = "am_echo"
SPEED = 1.08

def generate_audio(video_id: str):
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    output_dir = BASE / "output" / video_id
    script_path = output_dir / "script.json"
    audio_path  = output_dir / "audio.mp3"

    with open(script_path) as f:
        script = json.load(f)

    # Build full TTS text from chapters
    chapters = script.get("chapters", [])
    if chapters:
        full_text = "\n\n".join(ch["tts_script"] for ch in chapters)
    else:
        full_text = script.get("tts_script") or script.get("full_text", "")

    logger.info("Loading Kokoro model...")
    k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    logger.info(f"Generating TTS for {video_id} ({len(full_text)} chars)...")

    # Generate in chunks (sentences) to avoid long-text issues
    import re
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    # Combine into chunks of ~500 chars
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) < 500:
            current += " " + s if current else s
        else:
            if current:
                chunks.append(current.strip())
            current = s
    if current:
        chunks.append(current.strip())

    logger.info(f"Generating {len(chunks)} chunks...")
    audio_parts = []
    for i, chunk in enumerate(chunks):
        logger.info(f"  Chunk {i+1}/{len(chunks)}: {chunk[:60]}...")
        samples, sr = k.create(chunk, voice=VOICE, speed=SPEED, lang="en-us")
        audio_parts.append(samples)
        # Add 0.3s silence between chunks
        silence = np.zeros(int(sr * 0.3), dtype=np.float32)
        audio_parts.append(silence)

    full_audio = np.concatenate(audio_parts)
    duration = len(full_audio) / 24000
    logger.info(f"Total audio duration: {duration:.1f}s")

    # Save as WAV first, then convert to MP3
    wav_path = output_dir / "audio_voice.wav"
    sf.write(str(wav_path), full_audio, 24000)
    logger.info("Saved voice WAV, mixing ambient music...")

    import subprocess

    # Download ambient music if not cached
    music_path = BASE / "assets/ambient_documentary.mp3"
    music_path.parent.mkdir(exist_ok=True)
    if not music_path.exists():
        logger.info("Downloading ambient music (Kevin MacLeod — Perspectives, CC BY 4.0)...")
        music_url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Perspectives.mp3"
        try:
            import urllib.request
            urllib.request.urlretrieve(music_url, str(music_path))
            logger.info(f"  Downloaded: {music_path.stat().st_size//1024}KB")
        except Exception as e:
            logger.warning(f"  Music download failed ({e}), skipping music mix")
            music_path = None

    if music_path and music_path.exists():
        # Mix: voice at 100%, ambient music at 8% volume, looped to match duration
        logger.info("Mixing voice + ambient music (8% volume)...")
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(wav_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume=0.08,aresample=24000[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[out]",
            "-map", "[out]",
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            "-t", str(duration),
            str(audio_path)
        ], capture_output=True)
        if result.returncode != 0:
            logger.warning("Music mix failed, saving voice only: " + result.stderr.decode()[-400:])
            # Fallback: voice only
            subprocess.run([
                "ffmpeg", "-y", "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                str(audio_path)
            ], capture_output=True)
    else:
        # No music — convert voice only
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(wav_path),
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            str(audio_path)
        ], capture_output=True)
        if result.returncode != 0:
            logger.error("ffmpeg error: " + result.stderr.decode())
            sys.exit(1)

    wav_path.unlink(missing_ok=True)
    logger.info(f"✅ Audio saved: {audio_path}")

    # Extract word timestamps with faster-whisper
    logger.info("Extracting word timestamps with Whisper...")
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({
                "word": w.word.strip(),
                "start_ms": int(w.start * 1000),
                "end_ms":   int(w.end   * 1000)
            })
    ts_path = output_dir / "word_timestamps.json"
    with open(ts_path, "w") as f:
        json.dump(words, f, indent=2)
    logger.info(f"✅ {len(words)} word timestamps saved")

    # Copy to Remotion public
    public_dir = BASE / "video/remotion-project/public" / video_id
    public_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(audio_path, public_dir / "audio.mp3")
    logger.info(f"✅ Copied to public/{video_id}/audio.mp3")

    return duration, words

if __name__ == "__main__":
    vid = sys.argv[1] if len(sys.argv) > 1 else "L00300"
    dur, words = generate_audio(vid)
    print(f"\n✅ Audio complete: {dur:.1f}s, {len(words)} words")
