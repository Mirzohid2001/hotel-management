import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ActionCard } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, fontUi, radius, space, type, ui } from "../ui/theme";
import { shareCsvBase64, sharePdfBase64 } from "../utils/sharePdf";

type Props = { onBack: () => void };

const now = new Date();

export function ExportsScreen({ onBack }: Props) {
  const { exportPaymentsCsv, exportPnlCsv, exportArCsv, fetchEmehmonReport, printEmehmonStatement } =
    useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [emehmon, setEmehmon] = useState<Record<string, unknown> | null>(null);
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => ({
        id: i + 1,
        label: String(i + 1).padStart(2, "0"),
      })),
    []
  );

  const years = useMemo(() => {
    const y = now.getFullYear();
    return [y, y - 1, y - 2];
  }, []);

  async function runExport(
    key: string,
    fn: () => Promise<{
      content_base64: string;
      filename: string;
    }>
  ) {
    setBusy(key);
    try {
      const file = await fn();
      await shareCsvBase64(file.content_base64, file.filename);
    } catch (e) {
      Alert.alert("Eksport", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(null);
    }
  }

  async function printEmehmon() {
    setBusy("emehmon-pdf");
    try {
      const file = await printEmehmonStatement(year, month);
      await sharePdfBase64(
        file.pdf_base64,
        file.filename || `emehmon-${year}-${month}.pdf`
      );
    } catch (e) {
      Alert.alert("PDF", e instanceof ApiError ? e.message : "Chop etish xatosi");
    } finally {
      setBusy(null);
    }
  }

  async function loadEmehmon() {
    setBusy("emehmon");
    try {
      setEmehmon(await fetchEmehmonReport(year, month));
    } catch (e) {
      Alert.alert("E-mehmon", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(null);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Moliya"
        title="Eksport"
        subtitle="CSV ulashish · E-mehmon hisobot"
        onBack={onBack}
      />
      <ScrollView
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.section}>CSV fayllar</Text>
        <ActionCard
          title="To‘lovlar"
          hint="So‘nggi to‘lovlar ro‘yxati"
          cta="CSV"
          busy={busy === "payments"}
          onPress={() => runExport("payments", exportPaymentsCsv)}
        />
        <ActionCard
          title="P&L"
          hint="Joriy oy foyda / zarar"
          cta="CSV"
          busy={busy === "pnl"}
          onPress={() =>
            runExport("pnl", () => exportPnlCsv(year, month))
          }
        />
        <ActionCard
          title="AR / City ledger"
          hint="Qarzlar va ochiq foliolar"
          cta="CSV"
          busy={busy === "ar"}
          onPress={() => runExport("ar", exportArCsv)}
        />

        <Text style={styles.section}>Davr</Text>
        <View style={styles.chipRow}>
          {years.map((y) => (
            <Pressable
              key={y}
              style={[ui.chip, year === y && ui.chipOn]}
              onPress={() => setYear(y)}
            >
              <Text style={[ui.chipText, year === y && ui.chipTextOn]}>
                {y}
              </Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.chipRow}>
          {months.map((m) => (
            <Pressable
              key={m.id}
              style={[ui.chip, month === m.id && ui.chipOn]}
              onPress={() => setMonth(m.id)}
            >
              <Text style={[ui.chipText, month === m.id && ui.chipTextOn]}>
                {m.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.section}>E-mehmon</Text>
        <ActionCard
          title="Oylik hisobot"
          hint={`${year}-${String(month).padStart(2, "0")} · kerak · olingan · farq`}
          cta="Yuklash"
          tone="accent"
          busy={busy === "emehmon"}
          onPress={loadEmehmon}
        />
        <ActionCard
          title="Oylik vedomost"
          hint="Topshirish cheki — olingan E-mehmon"
          cta="PDF"
          tone="accent"
          busy={busy === "emehmon-pdf"}
          onPress={printEmehmon}
        />

        {busy === "emehmon" ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 8 }} />
        ) : null}

        {emehmon ? (
          <View style={styles.report}>
            <Text style={styles.reportEyebrow}>Tanlangan oy</Text>
            <Text style={styles.reportTitle}>
              {String(emehmon.year ?? year)} ·{" "}
              {String(emehmon.month ?? month)}-oy
            </Text>
            <View style={styles.reportStats}>
              <View style={styles.reportStat}>
                <Text style={styles.reportStatVal}>
                  {String(emehmon.total_expected ?? "—")}
                </Text>
                <Text style={styles.reportStatLbl}>Kerak</Text>
              </View>
              <View style={styles.reportStatDiv} />
              <View style={styles.reportStat}>
                <Text style={styles.reportStatVal}>
                  {String(emehmon.total_collected ?? "—")}
                </Text>
                <Text style={styles.reportStatLbl}>Olingan</Text>
              </View>
              <View style={styles.reportStatDiv} />
              <View style={styles.reportStat}>
                <Text
                  style={[
                    styles.reportStatVal,
                    Number(emehmon.shortfall ?? emehmon.total_gap) > 0 && {
                      color: colors.warn,
                    },
                  ]}
                >
                  {String(emehmon.shortfall ?? emehmon.total_gap ?? "—")}
                </Text>
                <Text style={styles.reportStatLbl}>Farq</Text>
              </View>
            </View>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    padding: space.lg,
    gap: space.sm,
    paddingBottom: 48,
  },
  section: {
    ...ui.section,
    marginTop: space.md,
    marginBottom: space.sm,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: space.sm,
  },
  report: {
    marginTop: space.md,
    padding: space.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  reportEyebrow: {
    ...type.eyebrowInk,
  },
  reportTitle: {
    ...type.titleInk,
    fontSize: 20,
    marginTop: 6,
    marginBottom: space.md,
    fontFamily: fontUi,
  },
  reportStats: {
    flexDirection: "row",
    alignItems: "center",
  },
  reportStat: {
    flex: 1,
    alignItems: "center",
  },
  reportStatDiv: {
    width: StyleSheet.hairlineWidth,
    height: 28,
    backgroundColor: colors.line,
  },
  reportStatVal: {
    fontFamily: fontDisplay,
    fontSize: 18,
    fontWeight: "700",
    color: colors.ink,
  },
  reportStatLbl: {
    marginTop: 2,
    fontFamily: fontUi,
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
  },
});
