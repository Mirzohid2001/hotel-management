import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, space, type, ui } from "./theme";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  onBack?: () => void;
  onTitlePress?: () => void;
  right?: React.ReactNode;
  children?: React.ReactNode;
};

export function ScreenHeader({
  eyebrow,
  title,
  subtitle,
  onBack,
  onTitlePress,
  right,
  children,
}: Props) {
  return (
    <View style={styles.wrap}>
      {onBack ? (
        <Pressable onPress={onBack} hitSlop={12}>
          <Text style={ui.back}>← Orqaga</Text>
        </Pressable>
      ) : null}
      <View style={styles.top}>
        <Pressable
          style={styles.copy}
          onPress={onTitlePress}
          disabled={!onTitlePress}
        >
          {eyebrow ? <Text style={type.eyebrow}>{eyebrow}</Text> : null}
          <Text style={styles.title} numberOfLines={2}>
            {title}
          </Text>
          {subtitle ? (
            <Text style={styles.sub} numberOfLines={2}>
              {subtitle}
            </Text>
          ) : null}
        </Pressable>
        {right ? <View style={styles.right}>{right}</View> : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.night,
    paddingTop: 56,
    paddingBottom: space.lg,
    paddingHorizontal: space.xl,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(255,255,255,0.08)",
  },
  top: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: space.md,
  },
  copy: { flex: 1, minWidth: 0 },
  title: {
    ...type.title,
    marginTop: 4,
  },
  sub: {
    marginTop: 4,
    color: colors.nightFogDim,
    fontSize: 13,
    fontWeight: "500",
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexShrink: 0,
  },
});
