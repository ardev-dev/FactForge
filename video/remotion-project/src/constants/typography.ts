export const FONTS = {
  DISPLAY:  "'Anton', 'Bebas Neue', 'Impact', sans-serif",   // bolder than Bebas
  BODY:     "'Inter', 'DM Sans', 'Arial', sans-serif",       // clearer small-size
  MONO:     "'Space Mono', 'Courier New', monospace",
  SHOCK:    "'Bangers', 'Anton', 'Impact', sans-serif",      // hook + CTA emphasis
  HEADLINE: "'Oswald', 'Anton', 'Impact', sans-serif",       // chapter titles
} as const;

export const FONT_SIZES = {
  HOOK:    108,  // Opening hook — massive (max 2 lines, 5-6 words)
  FACT:     82,  // Main fact — max 2 lines, 6-8 words per segment
  SUPPORT:  54,  // Supporting text
  LABEL:    32,  // Labels / categories
  NUMBER:  172,  // Standalone shock numbers
  CTA:      72,  // Call-to-action
} as const;
