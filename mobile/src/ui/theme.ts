import { Platform, StyleSheet, TextStyle, ViewStyle } from "react-native";

/** Clean hotel-ops system: charcoal + emerald (not muddy cream cards). */
export const colors = {
  ink: "#12151a",
  inkSoft: "#3a4048",
  muted: "#6b7280",
  faint: "#9ca3af",
  paper: "#eef0f3",
  paperDeep: "#e2e5ea",
  surface: "#ffffff",
  line: "#d8dde5",
  lineSoft: "rgba(18,21,26,0.08)",
  accent: "#0e6b56",
  accentDeep: "#0a5242",
  accentSoft: "#b7e0d4",
  accentFog: "#e6f5f0",
  night: "#111318",
  nightLift: "#1c2028",
  nightFog: "rgba(255,255,255,0.78)",
  nightFogDim: "rgba(255,255,255,0.48)",
  success: "#0e6b56",
  successSoft: "#e6f5f0",
  danger: "#b42318",
  dangerSoft: "#fde8e6",
  warn: "#b54708",
  warnSoft: "#fef0c7",
  info: "#175cd3",
  infoSoft: "#dbe8fe",
  white: "#ffffff",
  // aliases used by older screens
  copper: "#0e6b56",
  copperDeep: "#0a5242",
  copperSoft: "#7dd3be",
} as const;

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
} as const;

export const radius = {
  sm: 10,
  md: 14,
  lg: 18,
  xl: 24,
} as const;

const displayFont = Platform.select({
  ios: "Avenir Next",
  android: "sans-serif-medium",
  default: "System",
});

const uiFont = Platform.select({
  ios: "Avenir Next",
  android: "sans-serif",
  default: "System",
});

export const type = {
  display: {
    fontFamily: displayFont,
    fontSize: 28,
    fontWeight: "700" as const,
    color: colors.ink,
    letterSpacing: -0.4,
  },
  title: {
    fontFamily: displayFont,
    fontSize: 22,
    fontWeight: "700" as const,
    color: colors.white,
    letterSpacing: -0.3,
  },
  titleInk: {
    fontFamily: displayFont,
    fontSize: 22,
    fontWeight: "700" as const,
    color: colors.ink,
    letterSpacing: -0.3,
  },
  eyebrow: {
    fontFamily: uiFont,
    fontSize: 10,
    fontWeight: "700" as const,
    letterSpacing: 1.5,
    color: colors.accentSoft,
    textTransform: "uppercase" as const,
  },
  eyebrowInk: {
    fontFamily: uiFont,
    fontSize: 10,
    fontWeight: "700" as const,
    letterSpacing: 1.5,
    color: colors.accent,
    textTransform: "uppercase" as const,
  },
  body: {
    fontFamily: uiFont,
    fontSize: 15,
    fontWeight: "500" as const,
    color: colors.inkSoft,
  },
  bodyStrong: {
    fontFamily: uiFont,
    fontSize: 16,
    fontWeight: "600" as const,
    color: colors.ink,
  },
  meta: {
    fontFamily: uiFont,
    fontSize: 13,
    fontWeight: "500" as const,
    color: colors.muted,
  },
  caption: {
    fontFamily: uiFont,
    fontSize: 12,
    fontWeight: "600" as const,
    color: colors.muted,
  },
  label: {
    fontFamily: uiFont,
    fontSize: 12,
    fontWeight: "600" as const,
    color: colors.muted,
    letterSpacing: 0.2,
  },
  button: {
    fontFamily: uiFont,
    fontSize: 15,
    fontWeight: "700" as const,
    color: colors.white,
  },
  room: {
    fontFamily: displayFont,
    fontSize: 24,
    fontWeight: "700" as const,
  },
};

export const roomState = {
  vacant: {
    bg: colors.surface,
    fg: colors.ink,
    accent: colors.accent,
    pillBg: colors.accentFog,
    pillFg: colors.accentDeep,
  },
  occupied: {
    bg: colors.accent,
    fg: colors.white,
    accent: colors.accentSoft,
    pillBg: "rgba(255,255,255,0.2)",
    pillFg: colors.white,
  },
  dirty: {
    bg: colors.warnSoft,
    fg: colors.ink,
    accent: colors.warn,
    pillBg: "#fde68a",
    pillFg: colors.warn,
  },
  ooo: {
    bg: colors.paperDeep,
    fg: colors.muted,
    accent: colors.faint,
    pillBg: colors.line,
    pillFg: colors.muted,
  },
  cleaning: {
    bg: colors.infoSoft,
    fg: colors.info,
    accent: colors.info,
    pillBg: "#bfdbfe",
    pillFg: colors.info,
  },
} as const;

export const ui = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.paper,
  } as ViewStyle,
  header: {
    backgroundColor: colors.night,
    paddingTop: 56,
    paddingBottom: space.lg,
    paddingHorizontal: space.xl,
  } as ViewStyle,
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: space.md,
  } as ViewStyle,
  back: {
    ...type.meta,
    color: colors.accentSoft,
    fontWeight: "600",
    marginBottom: space.sm,
  } as TextStyle,
  section: {
    ...type.caption,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginTop: space.lg,
    marginBottom: space.sm,
    color: colors.muted,
  } as TextStyle,
  surface: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
  } as ViewStyle,
  surfaceLined: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  } as ViewStyle,
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: 13,
    fontSize: 16,
    fontFamily: uiFont,
    fontWeight: "500",
    color: colors.ink,
    backgroundColor: colors.surface,
    marginBottom: space.sm,
  } as ViewStyle,
  primaryBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 15,
    alignItems: "center",
  } as ViewStyle,
  primaryBtnText: {
    ...type.button,
  } as TextStyle,
  ghostBtn: {
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: 8,
  } as ViewStyle,
  ghostBtnText: {
    color: colors.white,
    fontWeight: "600",
    fontSize: 13,
    fontFamily: uiFont,
  } as TextStyle,
  copperBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: 8,
  } as ViewStyle,
  copperBtnText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 13,
    fontFamily: uiFont,
  } as ViewStyle,
  error: {
    color: colors.danger,
    fontFamily: uiFont,
    fontWeight: "600",
    fontSize: 14,
  } as TextStyle,
  empty: {
    ...type.meta,
    textAlign: "center",
    marginTop: space.xxl,
    paddingHorizontal: space.xl,
  } as TextStyle,
  listPad: {
    padding: space.lg,
    paddingBottom: 48,
  } as ViewStyle,
  rowItem: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingVertical: space.lg,
    paddingHorizontal: space.lg,
    marginBottom: space.sm,
  } as ViewStyle,
  rowTitle: {
    ...type.bodyStrong,
  } as TextStyle,
  rowMeta: {
    ...type.meta,
    marginTop: 3,
  } as TextStyle,
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.sm,
    backgroundColor: colors.paperDeep,
  } as ViewStyle,
  chipOn: {
    backgroundColor: colors.accent,
  } as ViewStyle,
  chipText: {
    fontFamily: uiFont,
    fontWeight: "600",
    fontSize: 13,
    color: colors.inkSoft,
  } as TextStyle,
  chipTextOn: {
    color: colors.white,
  } as TextStyle,
});

export const fontUi = uiFont;
export const fontDisplay = displayFont;
