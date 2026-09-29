import { Platform, StyleSheet, TextStyle, ViewStyle } from "react-native";

/** Web `static/css/app.css` :root — warm linen + brass hospitality. */
export const colors = {
  ink: "#1c1814",
  inkSoft: "#3a322a",
  muted: "#6f675e",
  faint: "#a8947c",
  paper: "#ebe6df",
  paperDeep: "#ddd5cb",
  surface: "#ffffff",
  panel: "#f7f4ef",
  line: "#d4cbc0",
  lineSoft: "rgba(28,24,20,0.07)",
  accent: "#c45c26",
  accentMid: "#d4783a",
  accentDeep: "#9a3f14",
  accentSoft: "#e8a86a",
  accentFog: "#f3e6dc",
  accentInk: "#fff8f0",
  brass: "#b86a2e",
  night: "#12100e",
  nightLift: "#1c1814",
  nightFog: "#f5efe6",
  nightFogDim: "#a8947c",
  success: "#2a7a55",
  successSoft: "#e6f2ec",
  danger: "#a83a30",
  dangerSoft: "#fff6f6",
  warn: "#b87820",
  warnSoft: "#fff8eb",
  info: "#3a6280",
  infoSoft: "#e8eef3",
  white: "#ffffff",
  // aliases
  copper: "#c45c26",
  copperDeep: "#9a3f14",
  copperSoft: "#e8a86a",
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
  ios: "Palatino",
  android: "serif",
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
    color: colors.accentInk,
  },
  room: {
    fontFamily: displayFont,
    fontSize: 24,
    fontWeight: "700" as const,
  },
};

/** Room tiles — match web --status-* tokens. */
export const roomState = {
  vacant: {
    bg: colors.surface,
    fg: colors.ink,
    accent: colors.success,
    pillBg: colors.successSoft,
    pillFg: colors.success,
  },
  occupied: {
    bg: colors.accent,
    fg: colors.accentInk,
    accent: colors.accentSoft,
    pillBg: "rgba(255,255,255,0.22)",
    pillFg: colors.white,
  },
  dirty: {
    bg: colors.dangerSoft,
    fg: colors.ink,
    accent: colors.danger,
    pillBg: "#f5d4d1",
    pillFg: colors.danger,
  },
  ooo: {
    bg: colors.paperDeep,
    fg: colors.muted,
    accent: "#6a6460",
    pillBg: colors.line,
    pillFg: "#6a6460",
  },
  cleaning: {
    bg: colors.accentFog,
    fg: colors.accentDeep,
    accent: colors.accent,
    pillBg: "rgba(196,92,38,0.18)",
    pillFg: colors.accentDeep,
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
    borderColor: "rgba(245,239,230,0.22)",
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: 8,
  } as ViewStyle,
  ghostBtnText: {
    color: colors.nightFog,
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
    color: colors.accentInk,
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
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
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
    color: colors.accentInk,
  } as TextStyle,
});

export const fontUi = uiFont;
export const fontDisplay = displayFont;
