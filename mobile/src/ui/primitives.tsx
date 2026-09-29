import { Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fontDisplay, fontUi, radius, space, type, ui } from "./theme";

export function SectionLabel({ children }: { children: string }) {
  return <Text style={ui.section}>{children}</Text>;
}

export function FieldLabel({ children }: { children: string }) {
  return <Text style={styles.fieldLabel}>{children}</Text>;
}

export function PrimaryButton({
  label,
  onPress,
  disabled,
  tone = "copper",
  loading,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
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
      style={({ pressed }) => [
        styles.btn,
        { backgroundColor: bg },
        tone === "ghost" && styles.ghost,
        (disabled || loading) && styles.disabled,
        pressed && !disabled && !loading && { opacity: 0.88, transform: [{ scale: 0.99 }] },
      ]}
      onPress={onPress}
      disabled={disabled || loading}
    >
      <Text
        style={[
          ui.primaryBtnText,
          tone === "ghost" && { color: colors.inkSoft },
        ]}
      >
        {loading ? "…" : label}
      </Text>
    </Pressable>
  );
}

export function StatusBadge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "success" | "warn" | "danger" | "info" | "accent";
}) {
  const map = {
    neutral: { bg: colors.paperDeep, fg: colors.inkSoft },
    success: { bg: colors.successSoft, fg: colors.success },
    warn: { bg: colors.warnSoft, fg: colors.warn },
    danger: { bg: colors.dangerSoft, fg: colors.danger },
    info: { bg: colors.infoSoft, fg: colors.info },
    accent: { bg: colors.accentFog, fg: colors.accentDeep },
  }[tone];
  return (
    <View style={[styles.badge, { backgroundColor: map.bg }]}>
      <Text style={[styles.badgeText, { color: map.fg }]}>{label}</Text>
    </View>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <View style={styles.emptyWrap}>
      <View style={styles.emptyMark} />
      <Text style={styles.emptyTitle}>{title}</Text>
      {hint ? <Text style={styles.emptyHint}>{hint}</Text> : null}
    </View>
  );
}

export function SegmentedTabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <View style={styles.segTrack}>
      {tabs.map((t) => {
        const on = t.id === value;
        return (
          <Pressable
            key={t.id}
            style={[styles.segItem, on && styles.segItemOn]}
            onPress={() => onChange(t.id)}
          >
            <Text style={[styles.segText, on && styles.segTextOn]} numberOfLines={1}>
              {t.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function MenuSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.menuSection}>
      <Text style={styles.menuSectionTitle}>{title}</Text>
      <View style={styles.menuCard}>{children}</View>
    </View>
  );
}

export function MenuRow({
  title,
  hint,
  onPress,
  mark,
  last,
}: {
  title: string;
  hint: string;
  onPress: () => void;
  mark?: string;
  last?: boolean;
}) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.menu,
        !last && styles.menuBorder,
        pressed && styles.menuPressed,
      ]}
      onPress={onPress}
    >
      {mark ? (
        <View style={styles.mark}>
          <Text style={styles.markText}>{mark}</Text>
        </View>
      ) : null}
      <View style={styles.menuCopy}>
        <Text style={styles.menuTitle}>{title}</Text>
        <Text style={styles.menuHint}>{hint}</Text>
      </View>
      <Text style={styles.chev}>›</Text>
    </Pressable>
  );
}

export function ActionCard({
  title,
  hint,
  cta,
  onPress,
  busy,
  tone = "surface",
}: {
  title: string;
  hint: string;
  cta: string;
  onPress: () => void;
  busy?: boolean;
  tone?: "surface" | "accent" | "night";
}) {
  const isAccent = tone === "accent";
  const isNight = tone === "night";
  return (
    <Pressable
      style={({ pressed }) => [
        styles.actionCard,
        isAccent && styles.actionCardAccent,
        isNight && styles.actionCardNight,
        pressed && !busy && { opacity: 0.92 },
        busy && { opacity: 0.7 },
      ]}
      onPress={onPress}
      disabled={busy}
    >
      <View style={{ flex: 1 }}>
        <Text
          style={[
            styles.actionTitle,
            (isAccent || isNight) && { color: colors.white },
          ]}
        >
          {title}
        </Text>
        <Text
          style={[
            styles.actionHint,
            isAccent && { color: "rgba(255,255,255,0.75)" },
            isNight && { color: colors.nightFogDim },
          ]}
        >
          {hint}
        </Text>
      </View>
      <View
        style={[
          styles.actionCta,
          isAccent && { backgroundColor: "rgba(255,255,255,0.2)" },
          isNight && { backgroundColor: "rgba(255,255,255,0.12)" },
        ]}
      >
        <Text
          style={[
            styles.actionCtaText,
            (isAccent || isNight) && { color: colors.white },
          ]}
        >
          {busy ? "…" : cta}
        </Text>
      </View>
    </Pressable>
  );
}

export function ListCard({
  title,
  meta,
  onPress,
  badge,
  badgeTone,
  leading,
  children,
}: {
  title: string;
  meta?: string;
  onPress?: () => void;
  badge?: string;
  badgeTone?: "neutral" | "success" | "warn" | "danger" | "info" | "accent";
  leading?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const body = (
    <>
      <View style={styles.listTop}>
        {leading ? <View style={styles.listLeading}>{leading}</View> : null}
        <View style={{ flex: 1, minWidth: 0 }}>
          <View style={styles.listTitleRow}>
            <Text style={styles.listTitle} numberOfLines={2}>
              {title}
            </Text>
            {badge ? <StatusBadge label={badge} tone={badgeTone} /> : null}
          </View>
          {meta ? (
            <Text style={styles.listMeta} numberOfLines={2}>
              {meta}
            </Text>
          ) : null}
        </View>
      </View>
      {children}
    </>
  );
  if (onPress) {
    return (
      <Pressable
        style={({ pressed }) => [styles.listCard, pressed && { opacity: 0.92 }]}
        onPress={onPress}
      >
        {body}
      </Pressable>
    );
  }
  return <View style={styles.listCard}>{body}</View>;
}

export function AvatarMark({
  label,
  tone = "accent",
}: {
  label: string;
  tone?: "accent" | "muted" | "danger";
}) {
  const bg =
    tone === "danger"
      ? colors.dangerSoft
      : tone === "muted"
        ? colors.paperDeep
        : colors.accentFog;
  const fg =
    tone === "danger"
      ? colors.danger
      : tone === "muted"
        ? colors.muted
        : colors.accentDeep;
  return (
    <View style={[styles.avatar, { backgroundColor: bg }]}>
      <Text style={[styles.avatarText, { color: fg }]}>
        {(label || "?").slice(0, 2).toUpperCase()}
      </Text>
    </View>
  );
}

export function FormCard({ children }: { children: React.ReactNode }) {
  return <View style={styles.formCard}>{children}</View>;
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

/** Board-style horizontal stats strip (OCC / counts). */
export function StatsStrip({
  items,
}: {
  items: { label: string; value: string | number; warn?: boolean }[];
}) {
  return (
    <View style={styles.statsStrip}>
      {items.map((it, i) => (
        <View key={it.label} style={styles.statsStripItem}>
          {i > 0 ? <View style={styles.statsStripDivider} /> : null}
          <View style={styles.statsStripBlock}>
            <Text
              style={[
                styles.statsStripValue,
                it.warn ? { color: colors.warn } : null,
              ]}
            >
              {it.value}
            </Text>
            <Text style={styles.statsStripLabel}>{it.label}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

export function SearchField({
  value,
  onChangeText,
  placeholder = "Qidiruv…",
}: {
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
}) {
  return (
    <TextInput
      style={styles.search}
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={colors.faint}
      autoCapitalize="none"
      autoCorrect={false}
      clearButtonMode="while-editing"
    />
  );
}

const styles = StyleSheet.create({
  fieldLabel: {
    ...type.label,
    marginBottom: 6,
    marginTop: 4,
  },
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
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: "flex-start",
  },
  badgeText: {
    fontFamily: fontUi,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  emptyWrap: {
    alignItems: "center",
    paddingVertical: 56,
    paddingHorizontal: space.xl,
  },
  emptyMark: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.accentSoft,
    marginBottom: space.lg,
  },
  emptyTitle: {
    ...type.bodyStrong,
    textAlign: "center",
  },
  emptyHint: {
    ...type.meta,
    textAlign: "center",
    marginTop: 6,
  },
  segTrack: {
    flexDirection: "row",
    flexWrap: "wrap",
    backgroundColor: colors.paperDeep,
    borderRadius: radius.md,
    padding: 4,
    gap: 4,
  },
  segItem: {
    flexGrow: 1,
    flexBasis: "22%",
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: radius.sm,
    alignItems: "center",
  },
  segItemOn: {
    backgroundColor: colors.night,
  },
  segText: {
    fontFamily: fontUi,
    fontSize: 12,
    fontWeight: "700",
    color: colors.inkSoft,
  },
  segTextOn: {
    color: colors.white,
  },
  menuSection: {
    marginTop: space.xl,
  },
  menuSectionTitle: {
    ...type.caption,
    letterSpacing: 0.9,
    textTransform: "uppercase",
    color: colors.muted,
    marginBottom: space.sm,
    marginLeft: 4,
  },
  menuCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  menu: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: space.lg,
    gap: space.md,
  },
  menuBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.lineSoft,
  },
  menuPressed: {
    backgroundColor: colors.accentFog,
  },
  mark: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.accentFog,
    alignItems: "center",
    justifyContent: "center",
  },
  markText: {
    fontFamily: fontUi,
    fontSize: 13,
    fontWeight: "800",
    color: colors.accentDeep,
  },
  menuCopy: { flex: 1, minWidth: 0 },
  menuTitle: {
    ...type.bodyStrong,
    fontSize: 16,
  },
  menuHint: {
    ...type.meta,
    marginTop: 2,
    fontSize: 12,
  },
  chev: {
    fontSize: 22,
    color: colors.faint,
    fontWeight: "300",
  },
  actionCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  actionCardAccent: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  actionCardNight: {
    backgroundColor: colors.night,
    borderColor: colors.night,
  },
  actionTitle: {
    ...type.bodyStrong,
    fontSize: 16,
  },
  actionHint: {
    ...type.meta,
    marginTop: 3,
    fontSize: 12,
  },
  actionCta: {
    backgroundColor: colors.accentFog,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.sm,
  },
  actionCtaText: {
    fontFamily: fontUi,
    fontSize: 12,
    fontWeight: "800",
    color: colors.accentDeep,
  },
  listCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    marginBottom: space.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  listTop: {
    flexDirection: "row",
    gap: space.md,
    alignItems: "flex-start",
  },
  listLeading: { marginTop: 2 },
  listTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  listTitle: {
    ...type.bodyStrong,
    flexShrink: 1,
  },
  listMeta: {
    ...type.meta,
    marginTop: 4,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontFamily: fontUi,
    fontSize: 13,
    fontWeight: "800",
  },
  formCard: {
    marginBottom: space.md,
    padding: space.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    ...Platform.select({
      ios: {
        shadowColor: "#1c1814",
        shadowOpacity: 0.04,
        shadowRadius: 12,
        shadowOffset: { width: 0, height: 4 },
      },
      default: {},
    }),
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
  statsStrip: {
    marginHorizontal: space.lg,
    marginTop: space.md,
    marginBottom: space.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingVertical: 16,
    paddingHorizontal: 4,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  statsStripItem: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
  },
  statsStripDivider: {
    width: StyleSheet.hairlineWidth,
    height: 28,
    backgroundColor: colors.line,
    marginRight: 0,
  },
  statsStripBlock: {
    flex: 1,
    alignItems: "center",
  },
  statsStripValue: {
    fontFamily: fontDisplay,
    fontSize: 20,
    fontWeight: "700",
    color: colors.ink,
  },
  statsStripLabel: {
    marginTop: 2,
    fontFamily: fontUi,
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
  },
  search: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    paddingHorizontal: space.lg,
    paddingVertical: 13,
    fontSize: 16,
    color: colors.ink,
    fontFamily: fontUi,
    fontWeight: "500",
    marginBottom: space.sm,
  },
});
