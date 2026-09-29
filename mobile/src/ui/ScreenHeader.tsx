import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, fontUi, radius, space, type } from "./theme";

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
      <View style={styles.glow} />
      {onBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={12}
          style={({ pressed }) => [styles.backBtn, pressed && { opacity: 0.7 }]}
        >
          <Text style={styles.backChevron}>‹</Text>
          <Text style={styles.backText}>Orqaga</Text>
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
    // leave room for Expo/devtools gear on simulator
    paddingRight: space.xl + 8,
  },
  glow: {
    position: "absolute",
    right: -40,
    top: -30,
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: "rgba(196,92,38,0.28)",
  },
  backBtn: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    marginBottom: space.sm,
    paddingVertical: 4,
    paddingRight: 10,
    gap: 2,
  },
  backChevron: {
    color: colors.accentSoft,
    fontSize: 22,
    fontWeight: "500",
    lineHeight: 24,
    marginTop: -1,
  },
  backText: {
    color: colors.accentSoft,
    fontFamily: fontUi,
    fontSize: 14,
    fontWeight: "600",
  },
  top: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: space.md,
  },
  copy: { flex: 1, minWidth: 0, paddingRight: 4 },
  title: {
    ...type.title,
    marginTop: 4,
    fontSize: 24,
    lineHeight: 30,
  },
  sub: {
    marginTop: 5,
    color: colors.nightFogDim,
    fontSize: 13,
    fontWeight: "500",
    fontFamily: fontUi,
    lineHeight: 18,
  },
  right: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexShrink: 0,
    paddingBottom: 2,
  },
});
