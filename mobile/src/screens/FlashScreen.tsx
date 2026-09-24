import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { FlashReport } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, fontUi, radius, space, type, ui } from "../ui/theme";

type Props = { onBack: () => void };

function money(v: unknown): string {
  if (v == null) return "—";
  return String(v);
}

export function FlashScreen({ onBack }: Props) {
  const { fetchFlash } = useAuth();
  const [data, setData] = useState<FlashReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchFlash());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchFlash]
  );

  useEffect(() => {
    load();
  }, [load]);

  const flash = data?.flash || {};
  const stats = (flash.stats || {}) as Record<string, unknown>;
  const kpis = data?.kpis || {};

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Hisobot"
        title="Kunlik flash"
        subtitle={data?.day}
        onBack={onBack}
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
          <View style={styles.heroRow}>
            <HeroMetric label="OCC %" value={money(stats.occupancy_percent)} />
            <HeroMetric label="ADR" value={money(stats.adr)} />
            <HeroMetric label="RevPAR" value={money(stats.revpar)} />
          </View>

          <Text style={ui.section}>Daromad</Text>
          <View style={styles.pair}>
            <Metric label="Naqd tushum" value={money(flash.revenue_cash)} wide />
            <Metric label="Hisob (accrual)" value={money(flash.revenue_accrual)} wide />
            <Metric label="Xarajat" value={money(flash.expenses_today)} wide />
          </View>

          <Text style={ui.section}>Operatsiya</Text>
          <View style={styles.grid}>
            <Metric label="Tayyor" value={String(kpis.ready_rooms ?? "—")} />
            <Metric label="Kir" value={String(kpis.dirty_rooms ?? "—")} />
            <Metric label="OOO" value={String(kpis.ooo_rooms ?? "—")} />
            <Metric label="HK vazifa" value={String(kpis.hk_tasks ?? "—")} />
            <Metric label="Ta’mir" value={String(kpis.maintenance_open ?? "—")} />
            <Metric label="Qarz" value={money(kpis.open_folio_balance)} />
          </View>
        </ScrollView>
      )}
    </View>
  );
}

function HeroMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.hero}>
      <Text style={styles.heroLabel}>{label}</Text>
      <Text style={styles.heroVal}>{value}</Text>
    </View>
  );
}

function Metric({
  label,
  value,
  wide,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <View style={[styles.metric, wide && styles.metricWide]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricVal}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: space.lg, paddingBottom: 48 },
  heroRow: { flexDirection: "row", gap: space.sm },
  hero: {
    flex: 1,
    backgroundColor: colors.night,
    borderRadius: radius.lg,
    padding: space.md,
    minHeight: 88,
    justifyContent: "space-between",
  },
  heroLabel: {
    color: colors.accentSoft,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
    fontFamily: fontUi,
  },
  heroVal: {
    color: colors.white,
    fontSize: 20,
    fontWeight: "600",
    fontFamily: fontDisplay,
    marginTop: 8,
  },
  pair: { gap: space.sm },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  metric: {
    width: "48%",
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: space.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.lineSoft,
  },
  metricWide: { width: "100%" },
  metricLabel: {
    ...type.caption,
  },
  metricVal: {
    marginTop: 6,
    fontSize: 18,
    fontWeight: "600",
    color: colors.ink,
    fontFamily: fontDisplay,
  },
});
