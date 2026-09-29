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
import { FormCard, ListCard } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, space, type, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenFlash: (date: string) => void;
  onOpenPnl: (year: number, month: number) => void;
};

const MONTHS = [
  "",
  "Yanvar",
  "Fevral",
  "Mart",
  "Aprel",
  "May",
  "Iyun",
  "Iyul",
  "Avgust",
  "Sentabr",
  "Oktabr",
  "Noyabr",
  "Dekabr",
];

export function ReportsHistoryScreen({ onBack, onOpenFlash, onOpenPnl }: Props) {
  const { fetchReportHistory } = useAuth();
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [years, setYears] = useState<number[]>([]);
  const [months, setMonths] = useState<
    { num: number; label: string; flash_day: string; year: number; month: number }[]
  >([]);
  const [profits, setProfits] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReportHistory(year);
      setYears(data.years);
      setMonths(data.months);
      setProfits(data.profit_periods || []);
      setYear(data.year);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [fetchReportHistory, year]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Hisobotlar"
        title="Tarix"
        subtitle={`${year}-yil`}
        onBack={onBack}
      />

      <View style={styles.yearRow}>
        {years.map((y) => {
          const on = y === year;
          return (
            <Pressable
              key={y}
              style={[ui.chip, on && ui.chipOn]}
              onPress={() => setYear(y)}
            >
              <Text style={[ui.chipText, on && ui.chipTextOn]}>{y}</Text>
            </Pressable>
          );
        })}
      </View>

      {error ? <Text style={[ui.error, { padding: space.lg }]}>{error}</Text> : null}
      {loading ? (
        <ActivityIndicator style={{ marginTop: 32 }} color={colors.accent} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.body}
          refreshControl={
            <RefreshControl refreshing={false} onRefresh={load} tintColor={colors.accent} />
          }
        >
          <Text style={ui.section}>Oylar</Text>
          {months.map((m) => (
            <FormCard key={m.num}>
              <Text style={type.bodyStrong}>
                {m.label || MONTHS[m.num]} {m.year}
              </Text>
              <View style={styles.actions}>
                <Pressable
                  style={styles.linkBtn}
                  onPress={() => onOpenFlash(m.flash_day)}
                >
                  <Text style={styles.linkText}>Flash</Text>
                </Pressable>
                <Pressable
                  style={styles.linkBtn}
                  onPress={() => onOpenPnl(m.year, m.month)}
                >
                  <Text style={styles.linkText}>P&L</Text>
                </Pressable>
              </View>
            </FormCard>
          ))}

          {profits.length ? (
            <>
              <Text style={ui.section}>Yopilgan foyda davrlari</Text>
              {profits.map((p) => (
                <ListCard
                  key={String(p.id)}
                  title={String(p.label || p.id)}
                  meta={`${p.started_on} → ${p.ended_on}`}
                />
              ))}
            </>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  yearRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    paddingHorizontal: space.lg,
    paddingTop: space.md,
  },
  body: { padding: space.lg, gap: space.sm, paddingBottom: 48 },
  actions: { flexDirection: "row", gap: 10, marginTop: 10 },
  linkBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: colors.accentFog,
  },
  linkText: {
    color: colors.accentDeep,
    fontWeight: "700",
    fontSize: 13,
    fontFamily: fontUi,
  },
});
