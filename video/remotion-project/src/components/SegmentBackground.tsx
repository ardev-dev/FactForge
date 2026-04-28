import React from "react";
import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface SegmentBackgroundProps {
  src: string;          // path to video file (staticFile key)
  kenBurns?: "zoom-in" | "zoom-out" | "pan-left" | "pan-right";
  overlayOpacity?: number;  // 0–1, default 0.65
  accentColor?: string;
}

export const SegmentBackground: React.FC<SegmentBackgroundProps> = ({
  src,
  kenBurns = "zoom-in",
  overlayOpacity = 0,        // NO global dark overlay — clip stays vivid
  accentColor = "#38B2AC",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = frame / Math.max(durationInFrames, 1);

  // Ken Burns transform
  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  if (kenBurns === "zoom-in") {
    scale = interpolate(t, [0, 1], [1.0, 1.12]);
  } else if (kenBurns === "zoom-out") {
    scale = interpolate(t, [0, 1], [1.12, 1.0]);
  } else if (kenBurns === "pan-left") {
    scale = 1.08;
    translateX = interpolate(t, [0, 1], [0, -5]);
  } else if (kenBurns === "pan-right") {
    scale = 1.08;
    translateX = interpolate(t, [0, 1], [0, 5]);
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {/* Video background */}
      <AbsoluteFill
        style={{
          transform: `scale(${scale}) translateX(${translateX}%) translateY(${translateY}%)`,
          transformOrigin: "center center",
        }}
      >
        <OffthreadVideo
          src={staticFile(src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          muted
        />
      </AbsoluteFill>

      {/* Optional dark overlay — only if explicitly requested (impact moments) */}
      {overlayOpacity > 0 && (
        <AbsoluteFill
          style={{
            backgroundColor: `rgba(10,10,15,${overlayOpacity})`,
          }}
        />
      )}
      {/* No accent tint — clip colors must remain pure */}
    </AbsoluteFill>
  );
};
