# YouTube Automation System — Permanent Brain
# Read this file at the START of every Claude Code session.
#
# ⚡ AI ENGINE: Claude Code (this session) — NO Anthropic API key needed.
# Claude Code handles all intelligence. Python handles automation only.

---

## What This Project Is

An automated YouTube channel producing English-language educational and factual short and long videos.

**Channel name on YouTube: "The Fact Drop"** (internal codename: FactForge)
**Channel ID:** UC2sASpaQ0lMbQkWW6AOLsqw

**🎯 PRIMARY NICHE (chosen 2026-04-28):** "Big Industry Exposed"
   = Big Pharma scams + Tech surveillance + Corporate fraud + Hidden history
   Channel description: "We expose what big pharma, tech giants, and governments don't want you to know."
   Stay within this lane — it's where the channel's content already clusters (22/43 videos).
   Three official playlists: Big Pharma Exposed, Tech Surveillance & Privacy Theft, Corporate Greed Files.

Six content domains (SAFE TRACKS ONLY — no pre-made lists, ideas are generated fresh per session):

1. 🤖 **AI & Technology** — GPT, robots, future of work, tech breakthroughs
2. 💊 **Big Corporations & Monopoly** — Big Pharma, price manipulation, Apple/Google/Amazon scandals
3. 🧬 **Science & Medicine** — discoveries, diseases, genetics, space, human body
4. 💰 **Economics & Wealth** — richest people, wealth gap, price shocks, financial fraud
5. 🏛️ **Shocking History** (non-political) — inventions, ancient civilizations, scientific events
6. 🌍 **Stunning Statistics** — shocking global numbers, country comparisons by data only

Target audience: Global English speakers curious about science, economics, and history.

### PERMANENTLY BANNED TOPICS (never produce, never queue):
- Religion of ANY kind (Islam, Christianity, Judaism, Hinduism, Buddhism — no exceptions)
- Jerusalem, Al-Aqsa, Dome of the Rock, Israel, Palestine, Gaza — any Middle East conflict
- Guns, gun control, firearms, mass shootings
- Living politicians by name (Trump, Biden, Putin, Netanyahu, Erdogan, Bukele, etc.)
- Elections, voting, political parties, abortion, LGBTQ as political topics
- Terrorism, ISIS, Al-Qaeda, Taliban, any extremist group
- Military conflicts, wars (ongoing or framed politically), nuclear weapons
- Racial justice framing, apartheid, occupation, ethnic cleansing language
- Any topic that requires taking a political or religious side

---

## How to Resume Any Session

At the START of every session (or when user says "resume", "status", or opens a new chat):

1. Read `state/progress.json`
2. Read `state/pending_uploads.json`
3. Read `state/published_videos.json`
4. Read `state/queue.json` (first 3 ideas only)
4. Output EXACTLY this dashboard format — nothing else, no preamble:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺  The Fact Drop — لوحة التحكم
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 قيد الإنتاج
   [id] — [title]
   الخطوة: [current step] | النتيجة: [script_score if available]/100

⏳ في انتظار الإكمال  ([count] مقاطع)
   • [id] — [title]  →  [pending_tasks بالعربي]

✅ مرفوعة على يوتيوب  ([count] مقاطع)
   • [id] — [youtube_id]  |  رُفع: [published_at]  |  [إذا cleaned: "🧹 منظّف" وإلا: "📁 يمكن تنظيفه ← clean [id]"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄  Workflow — دورة الإنتاج الكاملة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [User: produce]
       │
       ▼
  ① PROPOSE ── Claude يقترح 3 مواضيع من 6 مجالات آمنة
       │             (يتحقق من used_ideas.json تلقائياً)
       ▼
  [User: يختار رقم]
       │
       ▼
  ② RESEARCH ── بحث ويب + تحقق من الحقائق (≥2 مصادر رسمية)
       │             🚦 Gate: دقة ≥ 18/20  ← يوقف إذا فشل
       ▼
  ③ SCRIPT ── كتابة السكريبت من الحقائق المتحقق منها
       │            🚦 Gate: محتوى ≥ 80/100 ← يعيد كتابة إذا فشل
       ▼
  ④ AUDIO ── Kokoro TTS (am_echo) + SFX + timestamps
       │            python3 scripts/generate_audio.py [id]
       ▼
  ⑤ VIDEO ── تحميل bg_videos (Pexels→Coverr→Pixabay)
       │            Remotion render → ffmpeg merge
       │            🚦 Gate: بصري ≥ 14/16 ← يعيد إذا فشل
       ▼
  ⑥ METADATA ── عنوان×5 + وصف + tags
       │             🚦 Gate: SEO ≥ 18/22 ← يعيد إذا فشل
       ▼
  ⑦ UPLOAD ── python3 scripts/finalize_and_upload.py [id]
       │            (يولّد SRT 7 لغات تلقائياً قبل الرفع)
       │            publish_at: تلقائي via get_next_publish_date()
       ▼
  ⑧ CLEAN ── حذف video.mp4 + audio.mp3 + bg_videos/ تلقائياً
       │
       ▼
  ✅ DONE — مجدول على يوتيوب

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
الأوامر:
  produce        → اقترح 3 مواضيع جديدة واختر للإنتاج
  produce short  → نفسه — مقطع قصير (35–60 ث، 60fps)
  produce long   → نفسه — مقطع طويل (10–15 د، 30fps)
  upload         → ارفع مقاطع اليوم المجدولة
  schedule       → اعرض جدول النشر الكامل
  analytics      → تقرير أداء القناة
  trending       → حدّث الأفكار من Google Trends
  clean [id]     → نظّف ملفات المقطع المرفوع
  status         → حدّث هذه اللوحة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Translate pending_tasks to Arabic:
- subtitles_7_languages → "ترجمات نصية (7 لغات)"

- upload → "رفع على يوتيوب"
- subtitles_uploaded → "✅ ترجمات مرفوعة"

Fill in real values from the state files. If nothing in progress, show "✅ Nothing in progress".
If pending_uploads is empty, show "✅ All videos uploaded".
Always suggest the next idea at the bottom — never wait to be asked.
5. Then STOP and wait for user command.

---

## Session Rules (Follow Every Time)

1. **Always read this file first** — then progress.json
2. **Never restart completed work** — check progress.json before starting anything
3. **Work one idea at a time** — never batch produce without explicit user command
4. **NO PRE-MADE LISTS** — there is no queue to read. Ideas are generated fresh each time.
5. **AUTONOMOUS OPERATION** — do NOT ask for permission at each step. When user approves a topic, execute the full pipeline end-to-end without stopping. Only stop if a quality gate fails or a hard error occurs.
6. **Save state after every major step** — script, audio, video, publish
7. **Verify facts before writing any script** — minimum 2 official sources
8. **If interrupted, resume from last saved checkpoint** — never start over
9. **Auto-choose publish date** — use utils/youtube_helper.get_next_publish_date() — never ask user for dates
10. **Auto-clean after upload** — delete video.mp4, audio.mp3, bg_videos/ automatically after successful upload

## How "produce" Works (NEW WORKFLOW)

When user says "produce" (short or long):

**Step 1 — Generate 3 topic proposals:**
- Think about what is currently trending or evergreen in the 6 domains
- Cross-check `database/used_ideas.json` to avoid repeating topics
- Propose exactly 3 options in this format:

```
اقتراح موضوع للمقطع القادم:

① [عنوان جذاب] — [المجال] — [سبب واحد يجعله ترند الآن]
② [عنوان جذاب] — [المجال] — [سبب واحد يجعله ترند الآن]
③ [عنوان جذاب] — [المجال] — [سبب واحد يجعله ترند الآن]

اختر رقماً أو قل "غيّر" لاقتراحات جديدة.
```

**Step 2 — User picks a number (1, 2, or 3)**
- Immediately begin the full production pipeline without further questions
- Apply all quality gates, scoring, and steps as defined below

**Topic selection criteria:**
- Is it trending NOW or timeless evergreen?
- Does it make someone say "I didn't know that!"?
- Can it be verified with 2+ official sources?
- Does it pass ALL banned topics checks?
- Is the hook shocking enough to stop the scroll?

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     USER COMMAND                        │
│           produce / upload / clean / status             │
└───────────────────────┬─────────────────────────────────┘
                        │
           ┌────────────▼────────────┐
           │    Claude Code (AI)     │  ← كل الذكاء الاصطناعي
           │  • يقترح المواضيع       │
           │  • يتحقق من الحقائق    │
           │  • يكتب السكريبت        │
           │  • يولّد البيانات       │
           │  • يقيّم الجودة (Gates) │
           └────────────┬────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  generate_audio   render_short    finalize_and_upload
  (Kokoro TTS)   (Remotion+ffmpeg)  (YouTube API)
        │               │               │
        ▼               ▼               ▼
  audio.mp3 +    video.mp4 (60fps)  scheduled private
  timestamps     1080×1920           + SRT 7 langs
        │               │               │
        └───────────────┴───────────────┘
                        │
                 output/[id]/
                        │
                        ▼
              ✅ YouTube (auto-publish)

─── Video Sources (3-tier fallback) ───────────────────
  Pexels API → Coverr API → Pixabay API
  (fail-safe: always downloads 18/18 segments)

─── Quality Gates (MUST ALL PASS) ─────────────────────
  🚦 Fact accuracy   ≥ 18/20  (fact_verification.md)
  🚦 Script quality  ≥ 80/100 (content_psychology.md)
  🚦 Visual design   ≥ 14/16  (visual_design.md)
  🚦 SEO score       ≥ 18/22  (youtube_seo.md)

─── Publish Schedule ───────────────────────────────────
  Shorts : كل يومين    @ 14:00 UTC (5 PM Riyadh)
  Long   : كل أسبوع   @ 14:00 UTC (5 PM Riyadh)
```

### How Claude Code gets tasks
Python writes request JSON files → Claude Code reads + fills responses → Python continues

### Key Files
- `state/progress.json` — what is currently being produced
- `state/analytics.json` — performance data from YouTube
- `database/used_ideas.json` — topics already produced (check before proposing new ones)
- `state/pending_uploads.json` — videos waiting to be uploaded or scheduled

---

## Content Rules (NEVER VIOLATE)

- Every statistic must come from minimum 2 official sources
- Never publish an unverified claim
- No copyright music — voice and natural sound effects only
- **ZERO religion** — no mosques, churches, prophets, holy books, religious rulings of any kind
- **ZERO politics** — no living politicians, elections, political parties, geopolitical conflicts
- **ZERO weapons** — no guns, military weapons, nuclear, warfare framing
- No attacks on specific living individuals
- Factual controversy only (prices, corporate behavior, scientific data, historical facts)
- YouTube Community Guidelines compliance at all times — when in doubt, skip the idea
- Always cite sources in video descriptions
- If a topic could trigger a "Limited or no ads" (Yellow $) warning → do not produce it

---

## Pre-Publish Quality Gates (MANDATORY)

BEFORE publishing any video, ALL FOUR must pass in order:
1. `.claude/skills/fact_verification.md` → accuracy score ≥ 18/20 (runs BEFORE script is written)
2. `.claude/skills/content_psychology.md` → script score ≥ 80/100
3. `.claude/skills/visual_design.md` → visual score ≥ 14/16
4. `.claude/skills/youtube_seo.md` → SEO checklist score ≥ 18/22

If any gate fails, revise and re-score before proceeding to the next gate.
Script is written FROM verified facts — never verify after writing.

---

## Production Pipeline (Phase 3)

### Short Videos (Reels/Shorts)

When user says "produce next video" (Short):
1. Read queue.json / propose 3 fresh ideas → user picks one → proceed WITHOUT asking for permission
2. Research: web search → verify facts → save to output/[id]/research.json + sources.json
3. Accuracy gate: score research ≥ 18/20 (fact_verification.md) — stop if fails
4. Script: write TTS-optimized script FROM verified facts → save to output/[id]/script.json
   - Must include: 1 hero segment + 5 flash segments + 8-12 narration segments
5. Content gate: score script ≥ 80/100 (content_psychology.md) — revise if fails
6. **🎬 ONE COMMAND PIPELINE:** `python3 scripts/produce_pipeline.py [id]`
   This runs all 9 steps automatically (no manual gluing):
     1. Kokoro TTS → audio.mp3
     2. Prepend 2.75s intro silence (aligns with hero+flash visuals at 60fps)
     3. Build remotion_props.json (segments + word_timestamps)
     4. Fetch bg_videos (Pixabay HD min 1280, lanczos portrait re-encode, no color filters)
     5. Copy assets to public/
     6. Remotion render + ffmpeg `-c:v copy` (preserves source colors)
     7. audio_repair.py — BGM bed + intro SFX swell (fills all silences)
     8. LUFS normalize to -14
     9. audio_qc.py — exits non-zero on fail (silence > 500ms, drift > 150ms, clipping)
   - Model: models/kokoro/kokoro-v1.0.onnx + voices-v1.0.bin (binary, NOT json)
   - NEVER use Edge TTS — Microsoft TOS prohibits commercial use on free tier
7. Word timestamps: faster-whisper (base model, word_timestamps=True) → saved into remotion_props.json
8. Background: assign backgroundVideo + scene_query per segment in remotion_props.json (see Segment Structure below)
9. Video: Remotion render ShortVideo composition (no audio) → ffmpeg merge audio → output/[id]/video.mp4
   - MANDATORY: totalDurationFrames = ceil(audio_seconds × 60) — Shorts run at 60fps (Root.tsx)
   - MANDATORY: segment frames must be aligned to word timestamps × 60fps (ms × 60 / 1000)
   - Shorts duration: 35–60 seconds (target 45–58s sweet spot)
10. Visual gate: score ≥ 14/16 (visual_design.md) — revise if fails
10.5. **🛡️ AUDIO QC GATE (MANDATORY before metadata)**: `python3 scripts/audio_qc.py [id]`
    - Must exit 0. If fails: regenerate audio with proper BGM bed, re-render, retry.
    - Common failure: silences in middle from vocal_humanizer pauses → fix by ensuring BGM is mixed throughout.
11. Metadata: title × 5 variants + description + tags → output/[id]/metadata.json
12. SEO gate: score metadata ≥ 18/22 (youtube_seo.md) — revise if fails
13. Publish: `python3 scripts/finalize_and_upload.py [id]` — handles upload + state in one step
    - publish date: auto-calculated via utils/youtube_helper.get_next_publish_date() — never ask user
    - **NO custom thumbnail** — YouTube does not allow custom thumbnails for Shorts. We engineer the FIRST FRAME (`hero` segment) to be auto-picked as thumbnail. See "HERO FRAME" rule above.
14. Auto-clean: delete video.mp4, audio.mp3, bg_videos/, public/[id]/ after successful upload
15. Subtitles: generate SRT for 7 languages (EN/AR/ES/FR/HI/PT/TR) → upload via captions().insert()

## Hashtag Strategy — MANDATORY for all Shorts

YouTube uses hashtags as a primary discovery signal for Shorts. Current channel state (verified 2026-04-28): no hashtags in titles, generic hashtags in descriptions = ZERO discovery boost.

**TITLE hashtags (3 max — YouTube ignores everything past the 3rd):**
- ALWAYS include `#shorts` as one of the 3 — required for Shorts feed inclusion
- 2 other hashtags should be SPECIFIC to topic (high-intent, low-saturation)
- Format: `Title text here #shorts #SpecificTopic #NicheTag`
- Title hashtags count toward 100-char title limit

**DESCRIPTION hashtags (10-15, on a single line at the end):**
- First line: `#shorts` always
- Mix of:
  - 3-4 broad topical (e.g. `#science #economy #technology`)
  - 4-5 specific to the video (e.g. `#microplastics #plasticpollution`)
  - 2-3 trending/discoverability (e.g. `#mindblown #didyouknow`) — but NOT saturated like `#facts`
- AVOID forever: `#FactForge` (zero searches), `#viral` (algorithm penalty), `#fyp` (TikTok-only)

**TAGS field (separate from hashtags) — 8-12 tags:**
- 1-3 word phrases, NO `#` symbol
- Mix exact-match (`microplastic in body`) + broad (`science facts`) + entity (`Clearview AI`)

**Verified weak patterns from current videos:**
- ❌ Title with zero hashtags (8/8 of analyzed videos) — losing 30%+ Shorts feed reach
- ❌ Description starting with description text instead of `#shorts` — algorithm reads first line for context
- ❌ Saturated hashtags `#facts #didyouknow` — competing with millions of videos

**Required pattern going forward:**
```
Title: "40 Billion Photos. Scraped Illegally. #shorts #AI #PrivacyAlert"
Description: "#shorts #ai #privacy #clearview #surveillance #mindblown #shocking #technology

Real description text starts here..."
```

### Long Videos (Documentary Format)

When user says "produce next long video" or idea starts with L:
1. Read queue.json / database/ideas_long.json → pick next idea → announce it → proceed WITHOUT asking
2. Research: web search (min 2 official sources) → verify facts → save to output/[id]/research.json
3. Accuracy gate: score ≥ 18/20 — stop if fails
4. Script: write documentary script (10–15 min) with chapters → save to output/[id]/script.json
   - Each chapter has: id, type, chapter_num, title, tts_script, image_prompt
   - Types: hook, explainer, deep_dive, solution, cta
5. Content gate: score ≥ 80/100 — revise if fails
6. Voice: **Kokoro TTS** voice=`am_echo` speed=1.08 → output/[id]/audio.mp3
   - Script: `python3 scripts/generate_audio.py [id]` — handles TTS + timestamps in one step
   - NEVER use Edge TTS — Microsoft TOS prohibits commercial use on free tier
7. Word timestamps: faster-whisper (base model, word_timestamps=True) → output/[id]/word_timestamps.json
8. AI Images: Pollinations Flux (1920×1080) — 2 images per chapter (A + B for crossfade)
   - URL: https://image.pollinations.ai/prompt/{prompt}?width=1920&height=1080&nologo=true&model=flux&seed={seed}
   - Rate limit: 12s delay between requests — use retry with 20s wait on 429
   - Save to output/[id]/images/{chapter_id}_A.jpg and _B.jpg
   - Copy all images AND audio to video/remotion-project/public/[id]/ BEFORE rendering
9. remotion_props.json: distribute frames proportionally by chapter script length
   - totalDurationFrames = ceil(audio_seconds × 30)
   - Each section: startFrame, endFrame, imageA, imageB (paths relative to public/)
   - Include all 1,600+ wordTimestamps
10. Video: Remotion render DocumentaryVideo composition → ffmpeg merge
    - Composition: DocumentaryVideo (NOT LongVideo — that's for Wealth Gap only)
    - Script: python3 scripts/render_documentary.py [id]
    - CRF 18 + preset slow + maxrate 20M → NO PIXELATION
    - Output: output/[id]/video.mp4 (1920×1080, ~200–400 MB)
11. Visual gate: score ≥ 14/16 — revise if fails
12. Metadata: title × 5 + description + tags → output/[id]/metadata.json
13. SEO gate: score ≥ 18/22 — revise if fails
14. Publish: YouTube API upload scheduled private → save youtube_id
    - **NO thumbnail** — YouTube auto-selects for ALL video types
    - Schedule: 7 days after previous long video, at 14:00 UTC (5 PM Riyadh)

---

## Video Design Rules (NEVER VIOLATE)

### 🛡️ STRICT AUDIO QC GATE — verified failure on last 6 videos (Apr 2026)

**Diagnosed defects in S02400–S02900:**
- 600-1000ms dead silences at every impact segment boundary (vocal_humanizer pauses NOT covered by BGM)
- 600-720ms silent OUTRO (no music fade — abrupt cut)
- S02500/S02600: 3-second silent INTRO during flash (BGM never starts)
- Verified by `scripts/audio_qc.py` — ALL 6 videos failed

**MANDATORY GATE — runs after render, blocks upload:**
```bash
python3 scripts/audio_qc.py [video_id]   # exit 1 = block upload
```

Failure conditions (any one = REJECT):
- ❌ Silence > 500ms anywhere (intro / middle / outro)
- ❌ Audio/video sync drift > 100ms
- ❌ Missing audio stream
- ❌ True peak > -0.5 dBTP (clipping)
- ⚠️ LUFS outside [-18, -12] = warning (allowed but flagged)

**No video may be uploaded until `audio_qc.py [id]` exits 0.**

### Audio Engineering — 3-Tier System (MANDATORY for ALL videos):
```
Tier 1 — BGM:    ambient_documentary.mp3 at 8% volume (Kevin MacLeod CC BY 4.0)
                 ⚡ MUST PLAY CONTINUOUSLY from frame 0 to last frame.
                 NEVER muted. NEVER absent. Fades in 500ms at start, fades out 800ms at end.
Tier 2 — SFX:    context-matched, max 5 events/40s, min 3s gap between events
                 During flash intro (frames 0-180): SFX swell MANDATORY (tension_build at 40% volume)
                 NEVER leave the flash intro silent — it's a dead patch viewers exit.
Tier 3 — Ambient: scene-aware foley layer (Hollywood-style, MANDATORY)
                 Built from 18 synthesized loops in audio_engineering/assets/ambient/
                 Mapped via scripts/scene_ambient.py: rain→rain.wav, walking→footsteps,
                 hospital→cardiac beeps, factory→industrial hum, courtroom→murmur, etc.
                 Each segment gets its OWN ambient at -28 dB with 250ms crossfade.
                 RULE: every visible action must have audible texture (foley).
```

**Audio continuity rule (NON-NEGOTIABLE):**
- BGM is the FLOOR — every frame must have audio energy above -40 dB
- Vocal humanizer pauses (600ms pre-impact, 400ms post-outro) MUST be filled by BGM
- If BGM is missing during a vocal pause → silence detected → QC FAIL
- The audio mixing pipeline MUST place BGM on a separate track that never ducks below -30 dB

**SFX is CONTEXT-AWARE — topic determines which sounds fire:**
| Topic | Transition | Stat | Impact | Hook |
|-------|-----------|------|--------|------|
| Ocean/Sea | water_transition | sonar_ping | pressure_boom | bubble_burst |
| Space | space_whoosh | sci_fi_beep | space_thud | radio_static |
| Economy/Money | money_whoosh | coin_drop | market_crash | cash_register |
| Tech/AI | tech_whoosh | keyboard_click | system_alert | digital_glitch |
| History | parchment_rustle | typewriter_click | dramatic_sting | bell_toll |
| Universal | soft_whoosh | reveal_sting | hard_impact | tension_build |

**SFX placement rules (NEVER fire on every transition):**
- Hook (i=0): MANDATORY hook SFX at frame 0
- Stat/number segments: fire stat SFX (coin, ping, beep)
- Impact segments: fire impact SFX
- Scene transitions: MAX 3 across video (at ~25%, 50%, 75% positions)
- Final segment: always reveal_sting (universal)
- MINIMUM 3-second gap between any two SFX events
- Assets: `audio_engineering/assets/sfx/{topic}/{name}.wav` (25 files total)
- Config: `audio_engineering/sfx_config.json`
- Regenerate: `python3 audio_engineering/generate_sfx.py`

**Hook Optimization (First 1.5 Seconds — MANDATORY):**
- Max 12 words in hook sentence
- Must contain a shock word: `never`, `impossible`, `zero`, `only`, `less than`, `billion`, `secret`, `nobody`
- Visual: zoom-in Ken Burns on most shocking frame
- Audio: hook SFX fires at frame 0
- BAD: "Did you know the ocean is deep?" ❌
- GOOD: "We know more about Mars than our own ocean floor." ✅

**Vocal Humanization — Automated Post-Processing (audio_engineering/vocal_humanizer.py):**
Applied automatically in `produce_audio()` after Kokoro TTS. Do NOT skip.

| Segment Role | Speed | Pre-Pause | Post-Pause |
|-------------|-------|-----------|------------|
| hook | ×1.15 (urgent) | 0ms | 0ms |
| climax/impact | ×0.95 (heavy) | 600ms ← dramatic | 250ms |
| stat/number | ×0.97 (clear) | 0ms | 250ms ← let numbers land |
| outro/cta | ×0.92 (trustworthy) | 0ms | 400ms |
| explainer | ×1.05 (normal) | 0ms | 0ms |

EQ Chain (applied every video):
- +2.5dB @ 150Hz — warmth
- +1.8dB @ 380Hz — body/chest  
- -2.5dB @ 3200Hz — removes AI nasal artifact
- +1.5dB @ 8kHz — air/presence
- acompressor ratio=3:1 — brings up quiet consonants
- aecho 60ms — subtle room character (not reverb)
- loudnorm I=-16 LUFS — YouTube broadcast standard

In Script Writing (additional humanization):
- Use em dash (—) for 350ms dramatic pause
- Capitalize shocking words: `ZERO percent`, `FIVE people`
- Add dramatic pause after: `but`, `however`, `yet`, `only`, `wait`
- Example: `"More people walked on the Moon. But — fewer than five reached the ocean floor."`

### Short Videos (Reels/Shorts):
- **NO text overlays in center of screen** — مشاهد حية تملأ الشاشة بالكامل
- **Captions ONLY at bottom** — KaraokeCaption component, word-by-word synced to audio
- **Ken Burns effect** on every background segment (zoom-in / zoom-out / pan) — MUST VARY direction each segment
- **AUTHENTIC COLORS RULE (verified Apr 2026):** preserve source colors verbatim — NO color grading, NO saturation boost, NO curves.
  - SegmentBackground default `overlayOpacity=0` — clip footage stays as-is
  - Caption readability comes from a localized 480px `captionStrip` at the bottom only — NOT a screen-wide dimming
  - render_short.py uses `-c:v copy` on the merge step — ZERO video re-encode, original Remotion frames go directly to YouTube
  - Source bg_videos: Pixabay min_width=1280, prefer `large` quality variant
  - Re-encode (only when changing dimensions): lanczos scaler + CRF 16 + NO color filters
  - WHY: source footage is already graded by its creator; YouTube re-encodes again on upload; double-grading destroys color authenticity
- **Impact flash** on "impact" segments — subtle, no text
- **Number stat badge** — small, positioned above captions (bottom 320px), NOT center screen
- Background: Pexels stock videos via SegmentBackground component
- **Segments: 14–18 per 50s video** (scene change every 2.5–3.5 seconds = cinematic pace)
- **2-second rule**: every segment triggers a visual pattern interrupt (zoom/cut/pan) — no static holds
- Max 6–8 words per caption segment
- **CTA question MANDATORY**: Every Short must end with a direct viewer question in the last/second-to-last segment. Examples: "How many hours do you sleep? Comment below." / "Did you know this? Drop a 🤯" — this boosts Shorts feed visibility via comment engagement
- **SUBSCRIBE-ASK MANDATORY**: Every video (Short and Long) must contain at least ONE explicit subscribe ask — either:
  - In script: a single segment saying "Follow for more" / "Subscribe — one fact every two days" / "Hit follow if this surprised you"
  - In description: first 3 lines must include "🔔 Subscribe for daily shocking facts" or similar
  - Reasoning: channel currently has 0 subscribers (verified 2026-04-28). 9 public videos, 14 views, 0 subs = ZERO conversion. Subscribe-ask is the missing call-to-action.
  - Place subscribe ask BEFORE comment-CTA in the final 2 segments — never replace comment-CTA, add to it.
- **First segment hook rule**: seg_00 MUST use scene_query with maximum visual drama. If narration is abstract, still choose the most cinematic/shocking matching visual available.
- **HERO FRAME (Shorts thumbnail trap) — MANDATORY for every Short:**
  YouTube does NOT allow custom thumbnails for Shorts — it auto-picks an early frame. We engineer frame 0 to BE that thumbnail.
  - First segment MUST be `type: "hero"` with `durationFrames: 15` (0.25s at 60fps)
  - `kenBurns` is ignored (rendered static — no motion blur in thumbnail)
  - Then `flash` segments begin from frame 15 onwards
  - **scene_query rules for hero (DIFFERENT from regular segments):**
    - SINGLE dominant subject (a face, a single object, a clear icon)
    - HIGH contrast: dark background + bright subject (or vice versa)
    - NO crowds, NO text, NO multi-subject scenes
    - Subject must be readable at 200×355px (Shorts feed thumbnail size)
    - Examples GOOD: `"close-up human eye crying single tear dramatic lighting"`, `"single dollar bill burning flames black background"`, `"lone astronaut floating in space dark void"`
    - Examples BAD: `"city aerial view"` (too busy), `"crowd of people"` (no focus), `"abstract pattern"` (low click)
  - audio.mp3 already has 3s silence prepended → hero (15f) + flash (165f) = 180f = 3s of silence-aligned visuals
- **HOOK SCORING (verified weak from 8 published videos — avg 4.9/10):**
  - ≤8 words ideal, ≤12 words max — count strictly
  - MUST contain ≥1 shock word: `never, impossible, zero, only, less than, more than, billion, million, secret, nobody, banned, illegal, hidden, discovered, first, last, every`
  - MUST contain a number when topic allows (numbers boost score 7→8/10)
  - BANNED hook patterns (verified low-performing): `"In Germany, X is free"`, `"36 politicians voted for a law"`, `"A scientist edited DNA"` — flat statements
  - REQUIRED hook patterns: `"40 BILLION photos. Scraped illegally."` / `"$1 to make. $608 to buy."` / `"Zero people survived. Until him."`
- **Every segment MUST have scene_query** — exact English description of what should be visible on screen at that narration moment (NOT a generic category — match the spoken words)
- **No two consecutive segments may share the same backgroundVideo filename**
- **scene_query must match narration**: if voiceover says "medieval Baghdad", scene_query = "ancient Middle Eastern market torchlight" — not "city" or "buildings"

### Segment Structure (remotion_props.json) — MANDATORY FIELDS:
```json
{
  "text": "Four hundred thousand manuscripts. In one building.",
  "startFrame": 0,
  "endFrame": 180,
  "type": "hook",
  "backgroundVideo": "[id]/bg_videos/ancient_library.mp4",
  "scene_query": "ancient library scrolls candlelight medieval scholars",
  "kenBurns": "zoom-in",
  "highlightWords": ["Four hundred thousand"]
}
```

**scene_query rules** (Hollywood visual direction — every segment):
- Must be 3–6 words, specific and visual
- Match the EMOTION of the narration, not just the topic
  - Hook/revelation → "dramatic cinematic reveal" / "aerial sweeping landscape"
  - Fear/dread → "dark shadows empty corridor" / "storm clouds gathering"
  - Money/greed → "gold coins falling" / "stock market crash screen red"
  - History → "[era] [location] [specific detail]" e.g. "Roman soldiers marching colosseum fire"
  - Person → "businessman walking alone city night" / "man looking at screen shocked"
  - Data/stats → "digital numbers screen blue" / "world map glowing data points"
- Never use: "video", "footage", "clip", "scene", "background"
- Never repeat the same scene_query in one video — each must be unique

### Long Videos (Documentary):
- **Composition**: DocumentaryVideo.tsx — full-screen AI images + Ken Burns + crossfade
- **NO hardcoded stat cards** — pure cinematic visuals driven by images
- **Cinematic Ken Burns**: 5 modes cycling — zoom_in, zoom_out, pan_left, pan_right, tilt_up
- **Crossfade**: imageA → imageB at 55% through each section (18-frame fade)
- **Chapter transitions**: ChapterTransition component — white flash + accent color fade (28 frames) between every section
- **Exit fade**: each section fades out in last 12 frames (opacity 1→0) for smooth blend
- **Chapter badge**: animated slide-in at top-left with accent bar, shows for 3s then fades
- **Hook title**: dynamic from `title` prop — "FACTFORGE PRESENTS" + main title + animated underline
- **Karaoke captions**: bottom 90px offset, font 58px, 5 words/line
- **Progress bar**: top of screen showing overall video progress
- **Color themes**: islamic (gold), wealth (green), science (cyan), military (red), ancient (orange)
- **Image resolution**: 1920×1080 ONLY — never render images at wrong size
- **Video quality**: CRF 18 + preset slow + maxrate 20M — MANDATORY for no pixelation
- **Color grading**: applied in ffmpeg step — contrast 1.06, warmth curves, colorbalance warm-shadows/cool-highlights, unsharp 0.4
- **Ambient music**: Kevin MacLeod "Perspectives" (CC BY 4.0) at 8% volume, looped to match audio duration
  - Cached at: assets/ambient_documentary.mp3
  - Attribution required in video description: Music by Kevin MacLeod (incompetech.com)

### Stickman Animation (for both Shorts and Long):
- Use the `StickmanScene` Remotion component for segments that explain a concept or tell a story
- Stickman scenes replace or overlay static images when the content benefits from character motion
- Characters: walking, running, pointing, thinking, falling, celebrating — synced to audio
- Used in: explainer segments, comparison scenes, "before/after" moments, cause-effect demonstrations
- Implementation: `video/remotion-project/src/components/StickmanScene.tsx`
- Trigger words in script that suggest stickman: "imagine", "picture this", "a person", "when someone", "step by step"
- Never use stickman for: historical documentary footage, real-world statistics, breaking news topics

### Word Timestamps (MANDATORY for every video):
- Use faster-whisper "base" model with word_timestamps=True
- Store in remotion_props.json under "wordTimestamps" array
- Format: [{word, start_ms, end_ms}, ...]
- KaraokeCaption reads these for live word-by-word sync

### Audio/Video Sync (CRITICAL):
- Always check actual audio duration: `ffprobe -v quiet -print_format json -show_format audio.mp3`
- Set totalDurationFrames = ceil(audio_duration_seconds × fps) — use 60 for Shorts, 30 for Long docs
- Align segment startFrame/endFrame to word timestamps using keyword matching
- Verify: last segment endFrame == totalDurationFrames

---

## User Commands (Simple)

| Command | ماذا يفعل |
|---------|-----------|
| `produce` | ابدأ الإنتاج الكامل للفكرة التالية — اعرضها أولاً وانتظر الموافقة |
| `upload` | ارفع مقاطع اليوم المجدولة (3 مقاطع) عبر `python3 scripts/schedule_uploads.py` |
| `schedule` | اعرض جدول النشر الكامل مع التواريخ والمواعيد — `python3 scripts/schedule_uploads.py --plan` |
| `queue` | اعرض أفضل 10 أفكار قادمة |
| `skip` | تخطى الفكرة الحالية وانتقل للتالية |
| `add: [موضوع]` | أضف فكرة مخصصة في أعلى القائمة |
| `analytics` | اعرض تقرير أداء القناة — `python3 scripts/analytics_report.py --full` |
| `rotate titles` | شغّل A/B testing — استبدل العناوين ذات الـ CTR المنخفض — `python3 scripts/analytics_report.py --rotate-titles` |
| `trending` | حدّث الأفكار من Google Trends + YouTube — `python3 scripts/trending_refresh.py` |
| `refresh ideas` | استخرج أفكار من قنوات منافسة — `python3 scripts/idea_refresh.py` |
| `repackage` | حلّل فرص إعادة التوظيف (Short→Long, Long→Short) — `python3 scripts/repackage.py --analyze` |
| `auto upload` | ارفع تلقائياً حسب الحصة اليومية — `python3 scripts/auto_upload.py` |
| `status` | اعرض لوحة التحكم |
| `resume` | نفس status — اعرض اللوحة واستمر |
| `clean [id]` | احذف ملفات المقطع المرفوع من الكمبيوتر — احتفظ فقط بـ metadata.json و script.json |
| `clean all` | نظّف كل المقاطع المرفوعة دفعة واحدة |

### قواعد الـ clean (لا تُخالَف):
- احذف فقط إذا كان `status = uploaded` في pending_uploads.json أو youtube_id موجود في progress.json
- الملفات التي تُحذف: video*.mp4، audio*.mp3، video_noaudio*.mp4، bg_videos/، dubbed/، images/، subtitles/
- الملفات التي تُبقى دائماً: metadata.json، script.json، research.json، sources.json، remotion_props.json
- اعرض قائمة ما سيُحذف وحجمه قبل الحذف، واطلب تأكيداً

Any variation of these works: "produce next", "show me the queue", "what's next" etc.
Understand intent, not exact wording.

---

## Token Optimization Rules

- Use templates — never regenerate structure from scratch
- Cache research results — never search the same topic twice in one session
- Batch operations — generate all metadata fields in one Claude call
- Store results locally — never recompute what's already in output/
- Split large generation tasks — max 500 ideas per Claude call
- Summarize completed steps — don't carry full transcripts in context

---

## Publish Schedule

- **وقت النشر الثابت: الساعة 5:00 عصراً (توقيت الرياض) = 14:00 UTC**
- **Shorts (Reels):** مقطع واحد كل يومين (يوم ويوم لا) — `SHORT_EVERY_N_DAYS = 2`
- **Long videos:** مقطع واحد كل أسبوع — `LONG_EVERY_N_DAYS = 7`
- كل رفع يكون `privacyStatus: "private"` مع `publishAt` — ينشر تلقائياً في موعده

---

## Project Created
April 2026
Channel: The Fact Drop (codename: FactForge)
YouTube Channel ID: UC2sASpaQ0lMbQkWW6AOLsqw
Working directory: /Users/ar/Development/projects/FactForge
