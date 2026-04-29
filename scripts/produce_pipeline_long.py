#!/usr/bin/env python3
"""
produce_pipeline_long.py — End-to-end long video pipeline.

Mirrors produce_pipeline.py for shorts, but adapted for long-form:
  • DocumentaryVideo composition (1920×1080 @ 30fps)
  • Chapter-based structure (5-10 chapters of ~1-2min each)
  • AI-generated images from Pollinations Flux (NOT stock bg_videos)
  • 8-15 minute target duration
  • Lossless video stream copy (no color grading — preserves AI image colors)

Steps (10/10):
  1. Generate audio (Kokoro TTS via gen_audio_long.py)
  2. Generate AI images (Pollinations Flux via gen_images_long.py)
  3. Build remotion_props.json (sections + word_timestamps)
  4. Copy assets to public/
  5. Remotion render DocumentaryVideo (CRF 18, lossless audio merge)
  6. Audio repair (BGM bed already in gen_audio_long, but ensures no gaps)
  7. Scene-aware ambient layer (per-chapter foley)
  8. LUFS normalize to -14
  9. Audio QC gate (silences, drift, clipping)
  10. Production audit (long baseline)

Usage:
  python3 scripts/produce_pipeline_long.py L00600
  python3 scripts/produce_pipeline_long.py L00600 --skip-audio --skip-images
"""
import argparse, json, math, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30


def step(label):
    print(f"\n{'━'*70}\n▶  {label}\n{'━'*70}")


def run(cmd, **kwargs):
    r = subprocess.run(cmd, **kwargs)
    if r.returncode != 0:
        raise RuntimeError(f"Failed: {' '.join(str(c) for c in cmd[:3])}...")
    return r


def step_audio(vid):
    step("[1/10] Generating audio (Kokoro TTS + ambient music for long-form)")
    run([sys.executable, str(ROOT / "scripts/gen_audio_long.py"), vid])


def step_images(vid):
    step("[2/10] Generating AI images (Pollinations Flux — 2 per chapter)")
    run([sys.executable, str(ROOT / "scripts/gen_images_long.py"), vid])


def step_props(vid):
    step("[3/10] Building remotion_props.json")
    out = ROOT / "output" / vid
    script = json.loads((out / "script.json").read_text())
    chapters = script["chapters"]

    # Audio duration → totalDurationFrames at 30fps
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(out / "audio.mp3")],
        capture_output=True, text=True, check=True,
    )
    audio_dur = float(json.loads(r.stdout)["format"]["duration"])
    total_frames = math.ceil(audio_dur * FPS)

    # Distribute frames proportionally by chapter word count
    counts = [len(re.findall(r"\b\w+\b", c["tts_script"])) for c in chapters]
    total_words = sum(counts) or 1
    cur_frame = 0
    sections = []
    for i, ch in enumerate(chapters):
        proportion = counts[i] / total_words
        ch_frames = round(total_frames * proportion)
        end_frame = cur_frame + ch_frames
        if i == len(chapters) - 1:
            end_frame = total_frames  # last chapter fills to end
        kb_modes = ["zoom_in", "zoom_out", "pan_left", "pan_right", "tilt_up"]
        sections.append({
            "id": ch["id"],
            "title": ch["title"],
            "type": ch.get("type", "explainer"),
            "chapter_num": ch.get("chapter_num", i + 1),
            "startFrame": cur_frame,
            "endFrame": end_frame,
            "imageA": f"{vid}/images/{ch['id']}_A.jpg",
            "imageB": f"{vid}/images/{ch['id']}_B.jpg",
            "kenBurns": kb_modes[i % len(kb_modes)],
        })
        cur_frame = end_frame

    # Word timestamps from gen_audio_long
    wt_path = out / "word_timestamps.json"
    words = json.loads(wt_path.read_text()) if wt_path.exists() else []

    props = {
        "videoId": vid,
        "title": script["title"],
        "audioFile": f"{vid}/audio.mp3",
        "colorTheme": script.get("colorTheme", "shocking"),
        "totalDurationFrames": total_frames,
        "fps": FPS,
        "sections": sections,
        "wordTimestamps": words,
    }
    (out / "remotion_props.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))
    print(f"  ✓ {len(sections)} sections | {total_frames} frames ({audio_dur/60:.1f} min)")
    # Sanity: sections are not too long (max 2.5 min each is fine for long-form)
    for s in sections:
        d = (s["endFrame"] - s["startFrame"]) / FPS
        if d > 180:
            print(f"  ⚠ section '{s['id']}' is {d:.0f}s (>3 min) — consider splitting")


def step_copy_public(vid):
    step("[4/10] Copying assets to Remotion public/")
    src = ROOT / "output" / vid
    dst = ROOT / "video/remotion-project/public" / vid
    (dst / "images").mkdir(parents=True, exist_ok=True)
    for f in (src / "images").glob("*.jpg"):
        shutil.copy(f, dst / "images" / f.name)
    shutil.copy(src / "audio.mp3", dst / "audio.mp3")
    print(f"  ✓ {len(list((dst/'images').glob('*.jpg')))} images + audio.mp3")


def step_render(vid):
    step("[5/10] Remotion render (DocumentaryVideo, lossless audio merge)")
    run([sys.executable, str(ROOT / "scripts/render_documentary.py"), vid])


def step_audio_repair(vid):
    step("[6/10] Audio QC pre-check (BGM already mixed by gen_audio_long)")
    # Long videos already have BGM mixed via gen_audio_long. Just verify.
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/audio_qc.py"), vid],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout)
        print("  ⚠ pre-check found issues — running audio_repair anyway")
        subprocess.run([sys.executable, str(ROOT / "scripts/audio_repair.py"), vid], check=True)
    else:
        print("  ✓ no repair needed")


def step_scene_ambient(vid):
    step("[7/10] Scene-aware ambient foley layer (per chapter)")
    # scene_ambient.py reads remotion_props.json — works for both shorts and long
    # since both have segments/sections with scene_query OR title we can match.
    # For long, we treat title + image_prompt as the scene query.
    out = ROOT / "output" / vid
    props = json.loads((out / "remotion_props.json").read_text())
    script = json.loads((out / "script.json").read_text())
    # Inject scene_query based on chapter title + image prompts
    ch_by_id = {c["id"]: c for c in script["chapters"]}
    for s in props["sections"]:
        ch = ch_by_id.get(s["id"], {})
        s["scene_query"] = " ".join([
            s.get("title", ""),
            ch.get("image_prompt_A", ""),
            ch.get("image_prompt_B", ""),
        ]).strip()
    # Convert sections -> segments for scene_ambient compatibility
    props["segments"] = props["sections"]
    (out / "remotion_props.json").write_text(json.dumps(props, indent=2, ensure_ascii=False))

    # scene_ambient.py uses 60fps internally — pass fps=30 via env or just call as-is
    # It actually uses `fps` arg with default 60; we need to pass 30 here.
    r = subprocess.run(
        [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{ROOT / 'scripts'}')
from scene_ambient import apply_ambients
ok = apply_ambients('{vid}', fps={FPS})
sys.exit(0 if ok else 1)
"""],
        capture_output=False,
    )
    if r.returncode != 0:
        raise RuntimeError("scene_ambient failed")


def step_lufs(vid):
    step("[8/10] LUFS normalize to -14 (YouTube broadcast standard)")
    src = ROOT / "output" / vid / "video.mp4"
    tmp = ROOT / "output" / vid / "video_norm.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", str(tmp),
    ], capture_output=True, check=True)
    tmp.replace(src)
    print("  ✓ LUFS normalized")


def step_qc(vid):
    step("[9/10] Audio QC gate")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/audio_qc.py"), vid])
    if r.returncode != 0:
        raise RuntimeError(f"QC FAILED for {vid}")


def step_audit(vid):
    step("[10/10] Production audit — long baseline")
    audit_script = ROOT / "scripts/production_audit_long.py"
    if not audit_script.exists():
        print("  ⚠ production_audit_long.py not yet built — skipping")
        return
    r = subprocess.run([sys.executable, str(audit_script), vid])
    if r.returncode != 0:
        raise RuntimeError(f"AUDIT FAILED for {vid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--skip-images", action="store_true")
    args = ap.parse_args()

    vid = args.video_id
    out = ROOT / "output" / vid
    if not (out / "script.json").exists():
        print(f"❌ output/{vid}/script.json missing")
        sys.exit(1)

    if not args.skip_audio:
        step_audio(vid)
    if not args.skip_images:
        step_images(vid)
    step_props(vid)
    step_copy_public(vid)
    step_render(vid)
    step_audio_repair(vid)
    step_scene_ambient(vid)
    step_lufs(vid)
    step_qc(vid)
    step_audit(vid)

    print(f"\n{'═'*70}\n✅ {vid} ready for upload — output/{vid}/video.mp4\n{'═'*70}")


if __name__ == "__main__":
    main()
