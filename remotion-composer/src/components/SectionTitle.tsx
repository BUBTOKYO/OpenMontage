import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface SectionTitleProps {
  title: string;
  subtitle?: string;
  accentColor?: string;
  /** Title color. Defaults to near-white; pass the theme's textColor on light themes. */
  textColor?: string;
  position?: "top-left" | "bottom-left" | "center";
  /** Optional overrides for formats that need larger or localized labels. */
  fontSize?: number;
  fontFamily?: string;
  /** When set, the title sits on a rounded pill of this color. */
  backgroundColor?: string;
  /** Edge padding in px (vertical formats need room for platform UI). */
  padding?: number;
}

export const SectionTitle: React.FC<SectionTitleProps> = ({
  title,
  subtitle,
  accentColor = "#22D3EE",
  textColor = "#F8FAFC",
  position = "top-left",
  fontSize = 28,
  fontFamily = "Space Grotesk, Inter, system-ui, sans-serif",
  backgroundColor,
  padding = 60,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Entrance spring
  const slideIn = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  // Exit fade
  const exitStart = durationInFrames - 15;
  const fadeOut = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = Math.min(slideIn, fadeOut);

  const positionStyles: React.CSSProperties =
    position === "center"
      ? { justifyContent: "center", alignItems: "center" }
      : position === "bottom-left"
      ? { justifyContent: "flex-end", alignItems: "flex-start", padding }
      : { justifyContent: "flex-start", alignItems: "flex-start", padding };

  return (
    <AbsoluteFill style={positionStyles}>
      <div
        style={{
          opacity,
          transform: `translateX(${interpolate(slideIn, [0, 1], [-40, 0])}px)`,
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            width: interpolate(slideIn, [0, 1], [0, 60]),
            height: 4,
            backgroundColor: accentColor,
            marginBottom: 12,
            borderRadius: 2,
          }}
        />
        <div
          style={{
            fontSize,
            fontWeight: 700,
            color: textColor,
            fontFamily,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            textShadow: backgroundColor ? "none" : "0 2px 8px rgba(0,0,0,0.6)",
            ...(backgroundColor
              ? { backgroundColor, borderRadius: 999, padding: "10px 28px", maxWidth: 900 }
              : {}),
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: 18,
              fontWeight: 400,
              color: accentColor,
              fontFamily,
              marginTop: 4,
              opacity: spring({
                frame: frame - 8,
                fps,
                config: { damping: 20 },
              }),
              textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
