import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, space, type, ui } from "./theme";

export function SectionLabel({ children }: { children: string }) {
  return <Text style={ui.section}>{children}</Text>;
}

export function PrimaryButton({
  label,
  onPress,
  disabled,
  tone = "copper",
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  tone?: "copper" | "ink" | "success" | "danger" | "ghost";
}) {
  const bg =
    tone === "ink"
      ? colors.night
      : tone === "success"
        ? colors.success
        : tone === "danger"
          ? colors.danger
          : tone === "ghost"
            ? "transparent"
            : colors.copper;
  return (
    <Pressable
      style={[
        styles.btn,
        { backgroundColor: bg },
        tone === "ghost" && styles.ghost,
        disabled && styles.disabled,
      ]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text
        style={[
          ui.primaryBtnText,
          tone === "ghost" && { color: colors.inkSoft },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export function MenuRow({
  title,
  hint,
  onPress,
}: {
  title: string;
  hint: string;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.menu} onPress={onPress}>
      <View style={styles.menuCopy}>
        <Text style={styles.menuTitle}>{title}</Text>
        <Text style={styles.menuHint}>{hint}</Text>
      </View>
      <Text style={styles.chev}>›</Text>
    </Pressable>
  );
}

export function StatPill({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string | number;
  emphasis?: boolean;
}) {
  return (
    <View style={[styles.stat, emphasis && styles.statOn]}>
      <Text style={[styles.statVal, emphasis && styles.statValOn]}>{value}</Text>
      <Text style={[styles.statLbl, emphasis && styles.statLblOn]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  btn: {
    borderRadius: radius.md,
    paddingVertical: 15,
    alignItems: "center",
    marginTop: space.md,
  },
  ghost: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  disabled: { opacity: 0.65 },
  menu: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 16,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  menuCopy: { flex: 1 },
  menuTitle: {
    ...type.bodyStrong,
    fontSize: 17,
  },
  menuHint: {
    ...type.meta,
    marginTop: 3,
  },
  chev: {
    fontSize: 22,
    color: colors.faint,
    fontWeight: "300",
    marginLeft: space.md,
  },
  stat: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: 10,
    paddingHorizontal: 6,
    alignItems: "center",
  },
  statOn: {
    backgroundColor: colors.night,
  },
  statVal: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.ink,
  },
  statValOn: { color: colors.white },
  statLbl: {
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
    fontWeight: "600",
  },
  statLblOn: { color: colors.nightFogDim },
});
