import { StyleSheet, Text, View } from "react-native";

import { colors, fontUi, radius, space } from "./theme";

type BarPoint = { label: string; value: number; highlight?: boolean };

export function MiniBarChart({
  title,
  points,
  suffix = "",
  color = colors.accent,
}: {
  title: string;
  points: BarPoint[];
  suffix?: string;
  color?: string;
}) {
  const max = Math.max(...points.map((p) => p.value), 1);
  return (
    <View style={styles.card}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.row}>
        {points.map((p) => {
          const h = Math.max(4, Math.round((p.value / max) * 72));
          return (
            <View key={p.label} style={styles.col}>
              <Text style={styles.val} numberOfLines={1}>
                {Number.isInteger(p.value)
                  ? String(p.value)
                  : p.value.toFixed(0)}
                {suffix}
              </Text>
              <View style={styles.track}>
                <View
                  style={[
                    styles.bar,
                    {
                      height: h,
                      backgroundColor: p.highlight ? colors.accentDeep : color,
                    },
                  ]}
                />
              </View>
              <Text style={styles.label} numberOfLines={1}>
                {p.label}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

export function MiniStatusBars({
  title,
  items,
}: {
  title: string;
  items: { label: string; value: number }[];
}) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <View style={styles.card}>
      <Text style={styles.title}>{title}</Text>
      {items.map((item) => (
        <View key={item.label} style={styles.statusRow}>
          <Text style={styles.statusLbl} numberOfLines={1}>
            {item.label}
          </Text>
          <View style={styles.statusTrack}>
            <View
              style={[
                styles.statusFill,
                { width: `${Math.round((item.value / max) * 100)}%` },
              ]}
            />
          </View>
          <Text style={styles.statusVal}>{item.value}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: space.md,
    gap: space.sm,
  },
  title: {
    fontFamily: fontUi,
    fontSize: 12,
    fontWeight: "700",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 4,
    minHeight: 110,
  },
  col: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  val: {
    fontFamily: fontUi,
    fontSize: 9,
    fontWeight: "700",
    color: colors.ink,
  },
  track: {
    height: 72,
    width: "70%",
    justifyContent: "flex-end",
    alignItems: "center",
  },
  bar: {
    width: "100%",
    borderRadius: 6,
    minHeight: 4,
  },
  label: {
    fontFamily: fontUi,
    fontSize: 10,
    fontWeight: "600",
    color: colors.muted,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 4,
  },
  statusLbl: {
    width: 72,
    fontFamily: fontUi,
    fontSize: 12,
    fontWeight: "600",
    color: colors.ink,
  },
  statusTrack: {
    flex: 1,
    height: 10,
    borderRadius: 999,
    backgroundColor: colors.paperDeep,
    overflow: "hidden",
  },
  statusFill: {
    height: "100%",
    backgroundColor: colors.accent,
    borderRadius: 999,
  },
  statusVal: {
    width: 28,
    textAlign: "right",
    fontFamily: fontUi,
    fontSize: 12,
    fontWeight: "700",
    color: colors.ink,
  },
});
