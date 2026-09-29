import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { FlashReport } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { FormCard, StatsStrip } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, fontUi, radius, space, type, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

type Props = { onBack: () => void; initialDate?: string };

function money(v: unknown): string {
  if (v == null) return "—";
  return String(v);
}

function shiftDay(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

export function FlashScreen({ onBack, initialDate }: Props) {
  const { fetchFlash, printFlash } = useAuth();
  const [day, setDay] = useState(
    () => initialDate || new Date().toISOString().slice(0, 10)
  );
  const [data, setData] = useState<FlashReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialDate) setDay(initialDate);
  }, [initialDate]);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchFlash(day));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchFlash, day]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function onPrint() {
    setPrinting(true);
    try {
      const file = await printFlash(day);
      await sharePdfBase64(
        file.pdf_base64,
        file.filename || `flash-${day}.pdf`
      );
    } catch (e) {
      Alert.alert("PDF", e instanceof ApiError ? e.message : "Chop etish xatosi");
    } finally {
      setPrinting(false);
    }
  }

  const flash = data?.flash || {};
  const stats = (flash.stats || {}) as Record<string, unknown>;
  const kpis = data?.kpis || {};

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Hisobot"
        title="Kunlik flash"
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
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
                printing && { opacity: 0.5 },
              ]}
              onPress={onPrint}
              disabled={printing}
            >
              <Text style={ui.copperBtnText}>{printing ? "…" : "PDF"}</Text>
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
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.heroRow}>
            <HeroMetric label="OCC %" value={money(stats.occupancy_percent)} />
            <HeroMetric label="ADR" value={money(stats.adr)} />
            <HeroMetric label="RevPAR" value={money(stats.revpar)} />
          </View>

          <Text style={[ui.section, { marginHorizontal: space.lg }]}>Daromad</Text>
          <View style={styles.padH}>
            <FormCard>
              <MetricRow label="Naqd tushum" value={money(flash.revenue_cash)} />
              <MetricRow
                label="Hisob (accrual)"
                value={money(flash.revenue_accrual)}
              />
              <MetricRow
                label="Xarajat"
                value={money(flash.expenses_today)}
                last
              />
            </FormCard>
          </View>

          <Text style={[ui.section, { marginHorizontal: space.lg }]}>
            Operatsiya
          </Text>
          <StatsStrip
            items={[
              { label: "Tayyor", value: String(kpis.ready_rooms ?? "—") },
              {
                label: "Kir",
                value: String(kpis.dirty_rooms ?? "—"),
                warn: Number(kpis.dirty_rooms) > 0,
              },
              { label: "OOO", value: String(kpis.ooo_rooms ?? "—") },
            ]}
          />
          <View style={{ height: space.sm }} />
          <StatsStrip
            items={[
              { label: "HK", value: String(kpis.hk_tasks ?? "—") },
              {
                label: "Ta’mir",
                value: String(kpis.maintenance_open ?? "—"),
                warn: Number(kpis.maintenance_open) > 0,
              },
              { label: "Qarz", value: money(kpis.open_folio_balance) },
            ]}
          />
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

function MetricRow({
  label,
  value,
  last,
}: {
  label: string;
  value: string;
  last?: boolean;
}) {
  return (
    <View style={[styles.metricRow, !last && styles.metricRowBorder]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricVal}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { paddingBottom: 48 },
  padH: { paddingHorizontal: space.lg },
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
  heroRow: {
    flexDirection: "row",
    gap: space.sm,
    marginHorizontal: space.lg,
    marginTop: space.md,
  },
  hero: {
    flex: 1,
    backgroundColor: colors.night,
    borderRadius: radius.lg,
    padding: space.md,
    minHeight: 96,
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
    fontSize: 22,
    fontWeight: "700",
    fontFamily: fontDisplay,
    marginTop: 8,
  },
  metricRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 12,
  },
  metricRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  metricLabel: {
    ...type.caption,
    fontFamily: fontUi,
  },
  metricVal: {
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
    fontFamily: fontDisplay,
  },
});
