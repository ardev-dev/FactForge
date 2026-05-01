import "@fontsource/bebas-neue";
import "@fontsource/dm-sans/700.css";
import "@fontsource/space-mono/700.css";
import "@fontsource/anton";
import "@fontsource/oswald/700.css";
import "@fontsource/bangers";
import "@fontsource/inter/700.css";

import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Video,
} from "remotion";
import { z } from "zod";

import { AccentLine, CategoryBadge, Watermark } from "../components/AccentLine";
import { CountUpNumber } from "../components/CountUpNumber";
import { ImpactFlash, ScalePunch } from "../components/ImpactFlash";
import { KaraokeCaption, WordTimestamp } from "../components/KaraokeCaption";
import { Particles } from "../components/Particles";
import { StickmanScene, StickmanType } from "../components/StickmanScene";
import { SegmentBackground } from "../components/SegmentBackground";
import { TopProgressBar } from "../components/TopProgressBar";
import { WordByWordReveal } from "../components/WordByWordReveal";
import { COLORS, ColorTheme, getAccentColor } from "../constants/colors";
import { FONT_SIZES, FONTS } from "../constants/typography";

// ─────────────────────────── Schema ────────────────────────────────────────

export const segmentSchema = z.object({
  text: z.string(),
  startFrame: z.number(),
  endFrame: z.number(),
  // visual treatment
  type: z.enum([
    "hero",       // frame-0 thumbnail trap — sharp, static, high-contrast (12-18 frames)
    "flash",      // rapid-cut intro shot — bg only, no captions
    "hook",       // opening line — massive, accent
    "fact",       // normal fact sentence
    "impact",     // level-3 shock — punch + flash
    "number",     // count-up statistic
    "cta",        // call to action
  ]),
  // per-segment background video (staticFile key, e.g. "bg_videos/scene_call.mp4")
  backgroundVideo: z.string().optional(),
  kenBurns: z.enum(["zoom-in", "zoom-out", "pan-left", "pan-right"]).optional(),
  // for type==="number"
  numberValue: z.number().optional(),
  numberPrefix: z.string().optional(),
  numberSuffix: z.string().optional(),
  numberLabel: z.string().optional(),
  // optional words to highlight in accent color
  highlightWords: z.array(z.string()).optional(),
  // optional stickman character
  stickman: z.object({
    type: z.string(),
    label: z.string().optional(),
    x: z.number().optional(),
    y: z.number().optional(),
    flip: z.boolean().optional(),
  }).optional().nullable(),
});

const wordTimestampSchema = z.object({
  word:     z.string(),
  start_ms: z.number(),
  end_ms:   z.number(),
});

export const shortVideoSchema = z.object({
  videoId:             z.string(),
  categoryLabel:       z.string(),
  colorTheme:          z.enum(["wealth","power","history","science","comparison","shocking","geo"]),
  segments:            z.array(segmentSchema),
  audioFile:           z.string().nullable(),
  backgroundVideoUrl:  z.string().nullable(),
  totalDurationFrames: z.number(),
  wordTimestamps:      z.array(wordTimestampSchema).optional(),
  scale:               z.number().optional(), // 1 = 1080p, 2 = 4K
});

export type ShortVideoProps = z.infer<typeof shortVideoSchema>;

// ─────────────────────── Background gradient (per theme) ───────────────────

const BG_GRADIENTS: Record<ColorTheme, string> = {
  wealth:     "radial-gradient(ellipse at 30% 70%, #1a1000 0%, #0A0A0F 70%)",
  power:      "radial-gradient(ellipse at 70% 30%, #1a0000 0%, #0A0A0F 70%)",
  history:    "radial-gradient(ellipse at 20% 80%, #001230 0%, #0A0A0F 70%)",
  science:    "radial-gradient(ellipse at 50% 50%, #001a1a 0%, #0A0A0F 70%)",
  comparison: "radial-gradient(ellipse at 80% 20%, #120020 0%, #0A0A0F 70%)",
  shocking:   "radial-gradient(ellipse at 40% 60%, #1a0800 0%, #0A0A0F 70%)",
};

// ─────────────────────────── Vignette ──────────────────────────────────────

const Vignette: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(ellipse at 50% 50%, transparent 40%, rgba(0,0,0,0.7) 100%)",
      pointerEvents: "none",
    }}
  />
);

// ─────────────────────── Segment renderer ──────────────────────────────────
// Design principle: FULL-SCREEN cinematic video — NO text overlays in center.
// Text is handled exclusively by KaraokeCaption at the bottom of the screen.
// Each segment only controls: background video + Ken Burns + subtle effects.

interface SegmentViewProps {
  seg: z.infer<typeof segmentSchema>;
  accentColor: string;
  globalBgGradient: string;
}

const SegmentView: React.FC<SegmentViewProps> = ({ seg, accentColor, globalBgGradient }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const KB_MODES: Array<"zoom-in" | "zoom-out" | "pan-left" | "pan-right"> =
    ["zoom-in", "zoom-out", "pan-left", "pan-right"];
  const kenBurns = seg.kenBurns ?? KB_MODES[seg.startFrame % 4];
  const segDuration = seg.endFrame - seg.startFrame;

  // ── Per-segment background — NO global dark overlay ──────────────────────
  // Clip stays vivid and full-color. Caption readability comes ONLY from a
  // localized gradient pinned to the caption strip at the bottom.
  const bg = seg.backgroundVideo ? (
    <SegmentBackground
      src={seg.backgroundVideo}
      kenBurns={kenBurns}
      overlayOpacity={0}
      accentColor={accentColor}
    />
  ) : (
    <AbsoluteFill style={{ background: globalBgGradient }} />
  );

  // Caption strip: covers ONLY the bottom 480px (≈25% of 1920) where karaoke
  // captions render. Above that strip the clip is 100% pristine.
  // Captions sit at bottomOffset=320, fontSize=76 → strip from y=240 (bottom 240..720)
  // We use a narrow gradient: solid darker behind text, fading up cleanly.
  const captionStrip = (
    <div style={{
      position: "absolute",
      left: 0, right: 0,
      bottom: 0,
      height: 480,
      background: "linear-gradient(to top, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.55) 35%, rgba(0,0,0,0.20) 75%, transparent 100%)",
      pointerEvents: "none",
    }} />
  );

  // ── HERO: frame-0 thumbnail trap — STATIC, sharp, high-contrast ──────────
  // YouTube Shorts auto-picks an early frame as thumbnail. This segment is
  // engineered to BE that frame: no motion, strong vignette, accent rim.
  // Place ONLY at startFrame=0, durationFrames=12-18 (~0.2-0.3s).
  if (seg.type === "hero") {
    return (
      <AbsoluteFill>
        {/* Background frozen — no Ken Burns, no scale animation */}
        {seg.backgroundVideo ? (
          <SegmentBackground
            src={seg.backgroundVideo}
            kenBurns="zoom-in"
            overlayOpacity={0.15}        // less dim — thumbnail must be bright
            accentColor={accentColor}
          />
        ) : (
          <AbsoluteFill style={{ background: globalBgGradient }} />
        )}
        {/* Very soft corner darkening — preserves center brightness */}
        <AbsoluteFill style={{
          background: "radial-gradient(ellipse at 50% 50%, transparent 65%, rgba(0,0,0,0.30) 100%)",
          pointerEvents: "none",
        }} />
      </AbsoluteFill>
    );
  }

  // ── FLASH: rapid-cut intro shot — full-bleed bg, slight scale punch, no caption ──
  if (seg.type === "flash") {
    const punch = interpolate(frame, [0, Math.min(8, segDuration)], [1.05, 1.0], {
      extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill>
        <div style={{ transform: `scale(${punch})`, width: "100%", height: "100%" }}>
          {bg}
        </div>
        {/* brief tint flash on entry to add energy */}
        <ImpactFlash accentColor={accentColor} flashDurationFrames={4} />
      </AbsoluteFill>
    );
  }

  // ── IMPACT: subtle flash, clip stays vivid, caption strip only ─────────────
  if (seg.type === "impact") {
    return (
      <AbsoluteFill>
        {bg}
        <ImpactFlash accentColor={accentColor} flashDurationFrames={8} />
        {captionStrip}
      </AbsoluteFill>
    );
  }

  // ── NUMBER: show stat as a subtle overlay (small, bottom-left area) ────────
  // Still clean — stat appears above captions, not center-screen
  if (seg.type === "number" && seg.numberValue !== undefined) {
    const numEntrance = spring({ frame, fps, config: { damping: 12, stiffness: 200 } });
    const numOpacity = interpolate(numEntrance, [0, 1], [0, 1]);
    const numScale = interpolate(numEntrance, [0, 1], [0.85, 1]);
    return (
      <AbsoluteFill>
        {bg}
        <ImpactFlash accentColor={accentColor} flashDurationFrames={5} />
        {captionStrip}
        {/* Stat badge — sits above captions, small and unobtrusive */}
        <div style={{
          position: "absolute",
          bottom: 320,
          left: 0, right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: numOpacity,
          transform: `scale(${numScale})`,
        }}>
          <ScalePunch peakScale={1.04}>
            <CountUpNumber
              value={seg.numberValue}
              prefix={seg.numberPrefix ?? ""}
              suffix={seg.numberSuffix ?? ""}
              label={seg.numberLabel ?? ""}
              accentColor={accentColor}
              fontSize={120}
              countDurationSeconds={0.8}
            />
          </ScalePunch>
        </div>
      </AbsoluteFill>
    );
  }

  // ── HOOK — pure cinematic video, full color, caption strip only ──────────
  if (seg.type === "hook") {
    const bgScale = interpolate(frame, [0, segDuration], [1.0, 1.08], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
    return (
      <AbsoluteFill>
        <div style={{ transform: `scale(${bgScale})`, width: "100%", height: "100%" }}>
          {bg}
        </div>
        {captionStrip}
      </AbsoluteFill>
    );
  }

  // ── DEFAULT (fact / cta) — full color clip + caption strip only ───────────
  return (
    <AbsoluteFill>
      {bg}
      {captionStrip}
      {/* Stickman character — renders above background, below captions */}
      {seg.stickman && (
        <StickmanScene
          type={(seg.stickman.type as StickmanType)}
          accentColor={accentColor}
          label={seg.stickman.label}
          x={seg.stickman.x ?? 75}
          y={seg.stickman.y ?? 72}
          flip={seg.stickman.flip ?? false}
          scale={0.85}
          delayFrames={10}
        />
      )}
    </AbsoluteFill>
  );

};

// ─────────────────────────── Intro Overlay ────────────────────────────────

const IntroOverlay: React.FC<{ frame: number }> = ({ frame }) => {
  const opacity = interpolate(frame, [0, 17], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "black",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity,
      }}
    >
      <span
        style={{
          color: "white",
          fontFamily: "Impact, sans-serif",
          fontSize: 72,
          letterSpacing: 8,
          textTransform: "uppercase",
        }}
      >
        FACTFORGE
      </span>
    </AbsoluteFill>
  );
};

// ─────────────────────────── Outro Overlay ────────────────────────────────

const OutroOverlay: React.FC<{ frame: number; totalFrames: number }> = ({
  frame,
  totalFrames,
}) => {
  const outroStart = totalFrames - 24;
  const localFrame = frame - outroStart;
  const opacity = interpolate(localFrame, [0, 23], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        backgroundColor: `rgba(0,0,0,${opacity * 0.65})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <span
        style={{
          color: "white",
          fontFamily: "Impact, sans-serif",
          fontSize: 48,
          letterSpacing: 6,
          textTransform: "uppercase",
          opacity,
        }}
      >
        FOLLOW FOR MORE
      </span>
    </AbsoluteFill>
  );
};

// ─────────────────────────── Main Composition ──────────────────────────────

export const ShortVideo: React.FC<ShortVideoProps> = ({
  videoId,
  categoryLabel,
  colorTheme,
  segments,
  audioFile,
  backgroundVideoUrl,
  wordTimestamps,
  totalDurationFrames,
  scale = 1,
}) => {
  const frame = useCurrentFrame();
  const accentColor = getAccentColor(colorTheme as ColorTheme);
  const bgGradient = BG_GRADIENTS[colorTheme as ColorTheme] ?? BG_GRADIENTS.shocking;
  const S = scale; // multiply all pixel values by this

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.BG_PRIMARY }}>

      {/* ── Layer 1: Global fallback background (hidden by segment backgrounds) */}
      <AbsoluteFill style={{ background: bgGradient }} />

      {/* ── Layer 2: Ambient particles ───────────────────────────────────── */}
      <Particles count={12} accentColor={accentColor} width={1080} height={1920} />

      {/* ── Layer 3: Top progress bar ────────────────────────────────────── */}
      <TopProgressBar accentColor={accentColor} />

      {/* ── Layer 4: Category badge ──────────────────────────────────────── */}
      <CategoryBadge label={categoryLabel} accentColor={accentColor} />

      {/* ── Layer 5: Content segments (each has own background) ─────────── */}
      {segments.map((seg, i) => (
        <Sequence
          key={i}
          from={seg.startFrame}
          durationInFrames={seg.endFrame - seg.startFrame}
        >
          <SegmentView seg={seg} accentColor={accentColor} globalBgGradient={bgGradient} />
        </Sequence>
      ))}

      {/* ── Layer 6: Karaoke Captions (word-by-word, synced to audio) ────── */}
      {wordTimestamps && wordTimestamps.length > 0 && (
        <KaraokeCaption
          words={wordTimestamps as WordTimestamp[]}
          accentColor={accentColor}
          fontSize={76 * S}
          wordsPerLine={4}
          bottomOffset={320 * S}
          pillPadding={`${18 * S}px ${32 * S}px`}
        />
      )}

      {/* ── Layer 7: Watermark ───────────────────────────────────────────── */}
      <Watermark text="FactForge" />

      {/* ── Layer 8: Intro overlay (first 18 frames = 0.3s) ─────────────── */}
      {frame < 18 && <IntroOverlay frame={frame} />}

      {/* ── Layer 9: Outro overlay (last 24 frames = 0.4s) ──────────────── */}
      {frame > totalDurationFrames - 24 && (
        <OutroOverlay frame={frame} totalFrames={totalDurationFrames} />
      )}

      {/* ── Audio ────────────────────────────────────────────────────────── */}
      {audioFile && <Audio src={staticFile(audioFile)} />}
    </AbsoluteFill>
  );
};
