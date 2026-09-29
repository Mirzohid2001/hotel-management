import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FormCard, StatsStrip } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, fontUi, space, type, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenFlash?: () => void;
  onOpenBoard?: () => void;
  onOpenHousekeeping?: () => void;
  onOpenInquiries?: () => void;
  onOpenCityLedger?: () => void;
};

function shiftDay(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

function fmtDelta(v: unknown): string {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n}%`;
}

export function DashboardScreen({
  onBack,
  onOpenFlash,
  onOpenBoard,
  onOpenHousekeeping,
  onOpenInquiries,
  onOpenCityLedger,
}: Props) {
  const { fetchDashboard } = useAuth();
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchDashboard(day));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchDashboard, day]
  );

  useEffect(() => {
    load();
  }, [load]);

  const flash = (data?.flash || {}) as Record<string, unknown>;
  const stats = (flash.stats || {}) as Record<string, unknown>;
  const kpis = (data?.kpis || {}) as Record<string, unknown>;
  const insights = (data?.insights || {}) as Record<string, unknown>;

  const chips = [
    onOpenBoard && { label: "Doska", hint: "Xonalar", onPress: onOpenBoard },
    onOpenHousekeeping && {
      label: "Toza",
      hint: `${kpis.hk_tasks ?? 0} vazifa`,
      onPress: onOpenHousekeeping,
    },
    onOpenInquiries && {
      label: "So‘rov",
      hint: `${kpis.inquiries ?? 0}`,
      onPress: onOpenInquiries,
    },
    onOpenCityLedger && {
      label: "AR",
      hint: String(kpis.open_folio_balance ?? "—"),
      onPress: onOpenCityLedger,
    },
    onOpenFlash && { label: "Flash", hint: "Batafsil", onPress: onOpenFlash },
  ].filter(Boolean) as { label: string; hint: string; onPress: () => void }[];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Bosh sahifa"
        title="Dashboard"
        subtitle={day}
        onBack={onBack}
        right={
          <View style={styles.dayNav}>
            <Pressable onPress={() => setDay((d) => shiftDay(d, -1))} hitSlop={8}>
              <Text style={styles.dayBtn}>‹</Text>
            </Pressable>
            <Pressable
              onPress={() => setDay(new Date().toISOString().slice(0, 10))}
              hitSlop={8}
            >
              <Text style={styles.today}>Bugun</Text>
            </Pressable>
            <Pressable onPress={() => setDay((d) => shiftDay(d, 1))} hitSlop={8}>
              <Text style={styles.dayBtn}>›</Text>
            </Pressable>
          </View>
        }
      />

      {error ? <Text style={[ui.error, { padding: space.lg }]}>{error}</Text> : null}
      {loading && !data ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.body}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
        >
          <StatsStrip
            items={[
              {
                label: "OCC",
                value: `${stats.occupancy_percent ?? stats.occupancy ?? "—"}%`,
              },
              { label: "ADR", value: String(stats.adr ?? "—") },
              { label: "RevPAR", value: String(stats.revpar ?? "—") },
            ]}
          />

          <FormCard>
            <Text style={type.eyebrowInk}>Kecha bilan</Text>
            <Text style={styles.deltaRow}>
              OCC {fmtDelta(insights.occupancy_delta)} · Daromad{" "}
              {fmtDelta(insights.revenue_delta)} · ADR{" "}
              {fmtDelta(insights.adr_delta)}
            </Text>
            <Text style={ui.rowMeta}>
              Kecha: {String(insights.yesterday_occupancy ?? "—")}% OCC ·{" "}
              {String(insights.yesterday_revenue ?? "—")}
            </Text>
          </FormCard>

          <FormCard>
            <Text style={type.eyebrowInk}>Operatsiya</Text>
            <Text style={styles.opsLine}>
              Kirli {String(kpis.dirty_rooms ?? "—")} · Ta’mir{" "}
              {String(kpis.maintenance_open ?? "—")} · Folio{" "}
              {String(kpis.open_folio_count ?? "—")} · Xarajat kutish{" "}
              {String(kpis.expenses_pending ?? "—")}
            </Text>
          </FormCard>

          <View style={styles.chipGrid}>
            {chips.map((c) => (
              <Pressable
                key={c.label}
                style={({ pressed }) => [styles.chip, pressed && { opacity: 0.85 }]}
                onPress={c.onPress}
              >
                <Text style={styles.chipLabel}>{c.label}</Text>
                <Text style={styles.chipHint}>{c.hint}</Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: space.lg, gap: space.md, paddingBottom: 48 },
  dayNav: { flexDirection: "row", alignItems: "center", gap: 10 },
  dayBtn: {
    color: colors.accentSoft,
    fontSize: 22,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  today: {
    color: colors.nightFog,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: fontUi,
  },
  deltaRow: {
    ...type.bodyStrong,
    marginTop: 8,
    fontFamily: fontDisplay,
  },
  opsLine: { ...type.body, marginTop: 8 },
  chipGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    width: "47%",
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: space.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  chipLabel: { ...type.bodyStrong, fontSize: 15 },
  chipHint: { ...type.meta, marginTop: 4 },
});
