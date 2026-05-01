import "@fontsource/bebas-neue";
import "@fontsource/dm-sans/700.css";
import "@fontsource/anton";
import "@fontsource/oswald/700.css";
import "@fontsource/inter/700.css";

import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";
import { KaraokeCaption, WordTimestamp } from "../components/KaraokeCaption";
import { StickmanComparison, StickmanScene, StickmanType } from "../components/StickmanScene";
import { FONTS } from "../constants/typography";

// ─── Schema ────────────────────────────────────────────────────────────────

const stickmanConfigSchema = z.object({
  mode: z.enum(["single", "comparison"]).optional(),
  type: z.string().optional(),           // StickmanType for single
  label: z.string().optional(),
  x: z.number().optional(),
  y: z.number().optional(),
  flip: z.boolean().optional(),
  // comparison fields
  leftType: z.string().optional(),
  rightType: z.string().optional(),
  leftLabel: z.string().optional(),
  rightLabel: z.string().optional(),
  centerText: z.string().optional(),
}).optional().nullable();

const docSectionSchema = z.object({
  id: z.string(),
  type: z.enum(["hook", "explainer", "deep_dive", "solution", "cta"]),
  chapter_num: z.number(),
  title: z.string(),
  startFrame: z.number(),
  endFrame: z.number(),
  imageA: z.string().optional().nullable(),   // primary AI image
  imageB: z.string().optional().nullable(),   // secondary AI image (crossfade)
  stickman: stickmanConfigSchema,             // optional stickman animation
});

const wordTimestampSchema = z.object({
  word: z.string(),
  start_ms: z.number(),
  end_ms: z.number(),
});

export const documentaryVideoSchema = z.object({
  videoId: z.string(),
  title: z.string(),
  colorTheme: z.enum(["islamic", "wealth", "military", "science", "general", "ancient"]),
  sections: z.array(docSectionSchema),
  audioFile: z.string().nullable(),
  wordTimestamps: z.array(wordTimestampSchema).optional(),
  totalDurationFrames: z.number().optional(),
  fps: z.number().optional(),
});

type DocVideoProps = z.infer<typeof documentaryVideoSchema>;

// ─── Themes ─────────────────────────────────────────────────────────────────

const THEMES = {
  islamic:  { bg: "#0a1628", accent: "#d4af37", text: "#ffffff", secondary: "#a09060" },
  wealth:   { bg: "#080808", accent: "#00e676", text: "#ffffff", secondary: "#007740" },
  military: { bg: "#1a0000", accent: "#ff3232", text: "#ffffff", secondary: "#802020" },
  science:  { bg: "#0d0021", accent: "#00e5ff", text: "#ffffff", secondary: "#007080" },
  general:  { bg: "#0f0f1a", accent: "#ff6b35", text: "#ffffff", secondary: "#804020" },
  ancient:  { bg: "#281400", accent: "#ffa500", text: "#ffffff", secondary: "#804000" },
};

// ─── Progress Bar ───────────────────────────────────────────────────────────

const ProgressBar: React.FC<{ accent: string; total: number }> = ({ accent, total }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 5, zIndex: 200, background: "rgba(0,0,0,0.3)" }}>
      <div style={{
        height: "100%", width: `${(frame / total) * 100}%`,
        background: `linear-gradient(90deg, ${accent}cc, ${accent})`,
        boxShadow: `0 0 14px ${accent}`,
        transition: "width 0.1s",
      }} />
    </div>
  );
};

// ─── Chapter Transition Flash ────────────────────────────────────────────────

const ChapterTransition: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  // Frame 0–6: white flash; 6–18: accent color fade out; 18–28: vignette wipe
  const flashOp = interpolate(frame, [0, 4, 14, 22], [0.9, 0.6, 0.15, 0], {
    extrapolateRight: "clamp",
  });
  const accentOp = interpolate(frame, [0, 3, 16, 26], [0.5, 0.3, 0.08, 0], {
    extrapolateRight: "clamp",
  });
  if (frame > 28) return null;
  return (
    <>
      <AbsoluteFill style={{ background: `rgba(255,255,255,${flashOp})`, pointerEvents: "none", zIndex: 99 }} />
      <AbsoluteFill style={{ background: `${accent}${Math.round(accentOp * 255).toString(16).padStart(2,"0")}`, pointerEvents: "none", zIndex: 98 }} />
    </>
  );
};

// ─── Chapter Overlay ─────────────────────────────────────────────────────────

const ChapterBadge: React.FC<{
  num: number;
  title: string;
  accent: string;
  startFrame?: number;
}> = ({ num, title, accent, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const rel = Math.max(0, frame - startFrame);
  const ent = spring({ frame: rel, fps: 30, config: { damping: 14, stiffness: 160 } });
  const showDur = 90; // show for 3 seconds then fade
  const opacity = interpolate(rel, [0, 8, showDur - 12, showDur], [0, interpolate(ent, [0, 1], [0, 1]), 1, 0], { extrapolateRight: "clamp" });
  const x = interpolate(ent, [0, 1], [-80, 0]);

  if (rel > showDur) return null;

  return (
    <div style={{
      position: "absolute", top: 52, left: 72,
      opacity, transform: `translateX(${x}px)`, zIndex: 50,
      display: "flex", alignItems: "center", gap: 18,
    }}>
      {/* Accent bar entering from left */}
      <div style={{
        width: interpolate(ent, [0, 1], [0, 6]), height: 58,
        background: accent, borderRadius: 3,
        boxShadow: `0 0 18px ${accent}`, flexShrink: 0,
        transition: "width 0.1s",
      }} />
      <div style={{
        width: 52, height: 52, borderRadius: "50%",
        background: accent, display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: FONTS.DISPLAY, fontSize: 24, color: "#000", fontWeight: 900,
        boxShadow: `0 0 20px ${accent}88`,
      }}>{num}</div>
      <div>
        <div style={{
          fontFamily: FONTS.DISPLAY, fontSize: 32, color: accent,
          letterSpacing: "0.1em", textTransform: "uppercase",
          textShadow: `0 0 16px ${accent}66, 0 2px 8px rgba(0,0,0,0.9)`,
        }}>{title}</div>
        <div style={{ height: 3, background: accent, marginTop: 6, width: "100%", boxShadow: `0 0 8px ${accent}` }} />
      </div>
    </div>
  );
};

// ─── Cinematic Image Background with Ken Burns ──────────────────────────────

type KenBurnsMode = "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "tilt_up";

const CinematicBackground: React.FC<{
  imageA?: string | null;
  imageB?: string | null;
  duration: number;
  theme: (typeof THEMES)["general"];
  mode?: KenBurnsMode;
}> = ({ imageA, imageB, duration, theme, mode = "zoom_in" }) => {
  const frame = useCurrentFrame();

  // Ken Burns transform
  const progress = frame / Math.max(duration, 1);
  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  switch (mode) {
    case "zoom_in":
      scale = interpolate(progress, [0, 1], [1.0, 1.12]);
      break;
    case "zoom_out":
      scale = interpolate(progress, [0, 1], [1.12, 1.0]);
      break;
    case "pan_left":
      scale = 1.08;
      translateX = interpolate(progress, [0, 1], [0, -4]);
      break;
    case "pan_right":
      scale = 1.08;
      translateX = interpolate(progress, [0, 1], [-4, 0]);
      break;
    case "tilt_up":
      scale = 1.08;
      translateY = interpolate(progress, [0, 1], [2, -2]);
      break;
  }

  // Crossfade to imageB halfway through (if provided)
  const crossfadeStart = Math.floor(duration * 0.55);
  const crossfadeDur = 18; // 0.6s
  const imageBOpacity = imageB
    ? interpolate(frame, [crossfadeStart, crossfadeStart + crossfadeDur], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const transform = `scale(${scale}) translate(${translateX}%, ${translateY}%)`;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {/* Image A */}
      {imageA ? (
        <AbsoluteFill style={{ transform, transformOrigin: "center center" }}>
          <Img
            src={staticFile(imageA)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      ) : (
        <AbsoluteFill style={{ background: `radial-gradient(ellipse at 40% 60%, #1a2a50 0%, ${theme.bg} 70%)` }} />
      )}

      {/* Image B crossfade */}
      {imageB && imageBOpacity > 0 && (
        <AbsoluteFill
          style={{
            transform,
            transformOrigin: "center center",
            opacity: imageBOpacity,
          }}
        >
          <Img
            src={staticFile(imageB)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}

      {/* Dark vignette overlay */}
      <AbsoluteFill style={{
        background: "radial-gradient(ellipse at 50% 50%, transparent 40%, rgba(0,0,0,0.55) 100%)",
        pointerEvents: "none",
      }} />

      {/* Bottom gradient for captions */}
      <AbsoluteFill style={{
        background: "linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.45) 30%, transparent 60%)",
        pointerEvents: "none",
      }} />

      {/* Top gradient for progress bar / chapter badge */}
      <AbsoluteFill style={{
        background: "linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, transparent 25%)",
        pointerEvents: "none",
      }} />
    </AbsoluteFill>
  );
};

// ─── Hook Section ────────────────────────────────────────────────────────────

const HookSection: React.FC<{
  sec: z.infer<typeof docSectionSchema>;
  theme: (typeof THEMES)["general"];
  videoTitle?: string;
}> = ({ sec, theme, videoTitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dur = sec.endFrame - sec.startFrame;

  const titleEnt = spring({ frame, fps, config: { damping: 10, stiffness: 120 } });
  const titleScale = interpolate(titleEnt, [0, 1], [0.88, 1]);
  const titleOp = interpolate(titleEnt, [0, 1], [0, 1]);

  // Exit fade
  const exitOp = interpolate(frame, [dur - 20, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Animated underline width
  const lineW = interpolate(titleEnt, [0, 1], [0, 700]);

  // Use dynamic title from props, fallback to sec.title
  const displayTitle = videoTitle || sec.title;

  return (
    <AbsoluteFill>
      <CinematicBackground imageA={sec.imageA} imageB={sec.imageB} duration={dur} theme={theme} mode="zoom_in" />
      <ChapterTransition accent={theme.accent} />

      {/* Hero title card — shown only for first 5 seconds */}
      {frame < 150 && (
        <AbsoluteFill style={{
          justifyContent: "center", alignItems: "center", opacity: exitOp * titleOp,
        }}>
          <div style={{ textAlign: "center", padding: "0 100px" }}>
            {/* FACTFORGE label */}
            <div style={{
              fontFamily: FONTS.DISPLAY, fontSize: 22, color: theme.accent,
              letterSpacing: "0.35em", textTransform: "uppercase",
              opacity: interpolate(titleEnt, [0, 1], [0, 0.8]),
              marginBottom: 20,
              transform: `translateY(${interpolate(titleEnt, [0, 1], [-12, 0])}px)`,
            }}>FACTFORGE PRESENTS</div>

            {/* Main title */}
            <div style={{
              fontFamily: FONTS.DISPLAY, fontSize: 78,
              color: theme.accent,
              letterSpacing: "0.06em", textTransform: "uppercase",
              lineHeight: 1.12,
              transform: `scale(${titleScale})`,
              textShadow: `0 0 60px ${theme.accent}66, 0 0 120px ${theme.accent}33, 0 4px 24px rgba(0,0,0,0.98)`,
              marginBottom: 24,
            }}>
              {displayTitle}
            </div>

            {/* Animated accent line */}
            <div style={{
              height: 5, background: theme.accent,
              width: `${lineW}px`, maxWidth: "80%",
              margin: "0 auto", borderRadius: 3,
              boxShadow: `0 0 24px ${theme.accent}, 0 0 48px ${theme.accent}55`,
            }} />

            {/* Subtitle */}
            <div style={{
              fontFamily: FONTS.DISPLAY, fontSize: 32,
              color: "rgba(255,255,255,0.72)", marginTop: 28,
              letterSpacing: "0.16em", textTransform: "uppercase",
              transform: `translateY(${interpolate(titleEnt, [0, 1], [24, 0])}px)`,
              opacity: interpolate(titleEnt, [0, 1], [0, 0.72]),
            }}>
              {sec.title}
            </div>
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

// ─── Standard Section ────────────────────────────────────────────────────────

const KEN_BURNS_MODES: KenBurnsMode[] = ["zoom_in", "zoom_out", "pan_left", "pan_right", "tilt_up"];

const StandardSection: React.FC<{
  sec: z.infer<typeof docSectionSchema>;
  theme: (typeof THEMES)["general"];
  index: number;
}> = ({ sec, theme, index }) => {
  const frame = useCurrentFrame();
  const dur = sec.endFrame - sec.startFrame;
  const mode = KEN_BURNS_MODES[index % KEN_BURNS_MODES.length];
  const sm = sec.stickman;

  // Exit fade for smooth transition to next section
  const exitOp = interpolate(frame, [dur - 12, dur], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity: exitOp }}>
      <CinematicBackground imageA={sec.imageA} imageB={sec.imageB} duration={dur} theme={theme} mode={mode} />
      {/* Cinematic flash transition on entry */}
      <ChapterTransition accent={theme.accent} />
      {sec.chapter_num > 0 && (
        <ChapterBadge num={sec.chapter_num} title={sec.title} accent={theme.accent} startFrame={0} />
      )}
      {/* Stickman overlay */}
      {sm && sm.mode === "comparison" ? (
        <StickmanComparison
          leftType={(sm.leftType as StickmanType) ?? "idle"}
          rightType={(sm.rightType as StickmanType) ?? "idle"}
          leftLabel={sm.leftLabel}
          rightLabel={sm.rightLabel}
          accentLeft={theme.accent}
          accentRight="#ffffff"
          centerText={sm.centerText ?? "vs"}
        />
      ) : sm && sm.type ? (
        <StickmanScene
          type={(sm.type as StickmanType)}
          accentColor={theme.accent}
          label={sm.label}
          x={sm.x ?? 75}
          y={sm.y ?? 78}
          flip={sm.flip ?? false}
          delayFrames={20}
        />
      ) : null}
    </AbsoluteFill>
  );
};

// ─── CTA Section ─────────────────────────────────────────────────────────────

const CtaSection: React.FC<{
  sec: z.infer<typeof docSectionSchema>;
  theme: (typeof THEMES)["general"];
}> = ({ sec, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dur = sec.endFrame - sec.startFrame;
  const ent = spring({ frame, fps, config: { damping: 10, stiffness: 120 } });
  const pulse = 1 + Math.sin(frame / 14) * 0.03;

  return (
    <AbsoluteFill>
      <CinematicBackground imageA={sec.imageA} imageB={null} duration={dur} theme={theme} mode="zoom_in" />
      <AbsoluteFill style={{
        justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 36,
        opacity: interpolate(ent, [0, 1], [0, 1]),
        transform: `scale(${interpolate(ent, [0, 1], [0.94, 1])})`,
      }}>
        <div style={{
          fontFamily: FONTS.DISPLAY, fontSize: 100, color: theme.accent,
          textShadow: `0 0 60px ${theme.accent}`, letterSpacing: "0.06em",
          transform: `scale(${pulse})`,
        }}>
          SUBSCRIBE
        </div>
        <div style={{ height: 6, background: theme.accent, width: 160, borderRadius: 3, boxShadow: `0 0 20px ${theme.accent}` }} />
        <div style={{ fontFamily: FONTS.DISPLAY, fontSize: 34, color: "rgba(255,255,255,0.75)", textAlign: "center", maxWidth: 900, lineHeight: 1.5 }}>
          More untold history, science, and data
        </div>
        <div style={{ fontFamily: FONTS.DISPLAY, fontSize: 28, color: theme.accent, opacity: 0.9, letterSpacing: "0.2em" }}>
          ▶ FACTFORGE
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ─── Main Composition ────────────────────────────────────────────────────────

export const DocumentaryVideo: React.FC<DocVideoProps> = ({
  sections,
  audioFile,
  wordTimestamps,
  colorTheme,
  totalDurationFrames,
  title,
}) => {
  const theme = THEMES[colorTheme] ?? THEMES.general;
  const { durationInFrames } = useVideoConfig();
  const totalFrames = totalDurationFrames ?? durationInFrames;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      {/* Render sections */}
      {sections.map((sec, i) => {
        const dur = sec.endFrame - sec.startFrame;
        let content: React.ReactNode;

        if (sec.type === "hook") {
          content = <HookSection sec={sec} theme={theme} videoTitle={title} />;
        } else if (sec.type === "cta") {
          content = <CtaSection sec={sec} theme={theme} />;
        } else {
          content = <StandardSection sec={sec} theme={theme} index={i} />;
        }

        return (
          <Sequence key={sec.id} from={sec.startFrame} durationInFrames={dur}>
            {content}
          </Sequence>
        );
      })}

      {/* Karaoke captions — always at bottom */}
      {wordTimestamps && wordTimestamps.length > 0 && (
        <KaraokeCaption
          words={wordTimestamps as WordTimestamp[]}
          accentColor={theme.accent}
          fontSize={58}
          wordsPerLine={5}
          bottomOffset={90}
          pillPadding="18px 32px"
        />
      )}

      {/* Progress bar */}
      <ProgressBar accent={theme.accent} total={totalFrames} />

      {/* Watermark */}
      <div style={{
        position: "absolute", bottom: 32, right: 52,
        fontFamily: FONTS.DISPLAY, fontSize: 24, color: "rgba(255,255,255,0.28)",
        letterSpacing: "0.14em",
      }}>
        FACTFORGE
      </div>

      {/* Audio */}
      {audioFile && <Audio src={staticFile(audioFile)} />}
    </AbsoluteFill>
  );
};
