import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { CashShift } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { FieldLabel, FormCard, ListCard, PrimaryButton, StatusBadge } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

type Props = {
  onBack: () => void;
};

export function CashShiftScreen({ onBack }: Props) {
  const {
    me,
    fetchCashShift,
    openCashShift,
    closeCashShift,
    postCashMovement,
    fetchCashShiftHistory,
    printCashShift,
  } = useAuth();
  const [shift, setShift] = useState<CashShift | null>(null);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openingFloat, setOpeningFloat] = useState("0");
  const [closingCash, setClosingCash] = useState("");
  const [moveAmount, setMoveAmount] = useState("");
  const [moveNote, setMoveNote] = useState("");

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [s, hist] = await Promise.all([
        fetchCashShift(),
        fetchCashShiftHistory().catch(() => [] as Record<string, unknown>[]),
      ]);
      setShift(s);
      setHistory(hist);
      if (s?.expected_cash) setClosingCash(s.expected_cash);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [fetchCashShift, fetchCashShiftHistory]);

  useEffect(() => {
    load();
  }, [load]);

  async function doOpen() {
    setBusy(true);
    setError(null);
    try {
      const s = await openCashShift(openingFloat.trim() || "0");
      setShift(s);
      await load();
      Alert.alert("Kassa", "Smena ochildi.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ochish xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doClose() {
    const amount = closingCash.trim().replace(/\s/g, "").replace(",", ".");
    if (amount === "" || Number(amount) < 0) {
      setError("Yopish summasini kiriting.");
      return;
    }
    Alert.alert("Smenani yopish", `Yakuniy naqd: ${amount}?`, [
      { text: "Bekor", style: "cancel" },
      {
        text: "Yopish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            const s = await closeCashShift(amount);
            setShift(s);
            Alert.alert(
              "Yopildi",
              s.variance != null ? `Farq: ${s.variance}` : "Smena yopildi."
            );
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Yopish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function onPrint(id: number) {
    setBusy(true);
    try {
      const file = await printCashShift(id);
      await sharePdfBase64(
        file.pdf_base64,
        file.filename || `cash-shift-${id}.pdf`
      );
    } catch (e) {
      Alert.alert("PDF", e instanceof ApiError ? e.message : "Chop etish xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doMove(kind: "pay_in" | "pay_out") {
    const amount = moveAmount.trim().replace(/\s/g, "").replace(",", ".");
    if (!amount || Number(amount) <= 0) {
      setError("Harakat summasini kiriting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await postCashMovement(kind, amount, moveNote.trim());
      setMoveAmount("");
      setMoveNote("");
      await load();
      Alert.alert(
        "Kassa",
        kind === "pay_in" ? "Kirim qo‘shildi" : "Chiqim qo‘shildi"
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Harakat xatosi");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  const open = !!shift?.is_open;

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Kassa"
        title="Smena"
        subtitle={me?.hotel?.name || me?.tenant.name || "Hotel"}
        onBack={onBack}
        right={
          shift?.id ? (
            <Pressable
              style={({ pressed }) => [
                ui.copperBtn,
                pressed && { opacity: 0.85 },
                busy && { opacity: 0.5 },
              ]}
              onPress={() => onPrint(Number(shift.id))}
              disabled={busy}
            >
              <Text style={ui.copperBtnText}>PDF</Text>
            </Pressable>
          ) : null
        }
      />

      <ScrollView contentContainerStyle={styles.body}>
        <StatusBadge
          label={open ? "OCHIQ" : "YOPIQ"}
          tone={open ? "success" : "neutral"}
        />

        {open && shift ? (
          <FormCard>
            <Row label="Boshlang‘ich" value={shift.opening_float} />
            <Row label="Kutilgan naqd" value={shift.expected_cash || "—"} />
            <Row
              label="Ochilgan"
              value={
                shift.opened_at
                  ? shift.opened_at.replace("T", " ").slice(0, 16)
                  : "—"
              }
            />
            <FieldLabel>Yakuniy naqd *</FieldLabel>
            <TextInput
              style={styles.input}
              value={closingCash}
              onChangeText={setClosingCash}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Kassa harakati</FieldLabel>
            <TextInput
              style={styles.input}
              value={moveAmount}
              onChangeText={setMoveAmount}
              keyboardType="decimal-pad"
              placeholder="Summa"
              placeholderTextColor={colors.faint}
            />
            <TextInput
              style={styles.input}
              value={moveNote}
              onChangeText={setMoveNote}
              placeholder="Izoh (ixtiyoriy)"
              placeholderTextColor={colors.faint}
            />
            <View style={styles.moveRow}>
              <Pressable
                style={[styles.moveBtn, styles.moveIn, busy && styles.disabled]}
                onPress={() => doMove("pay_in")}
                disabled={busy}
              >
                <Text style={styles.btnText}>+ Kirim</Text>
              </Pressable>
              <Pressable
                style={[styles.moveBtn, styles.moveOut, busy && styles.disabled]}
                onPress={() => doMove("pay_out")}
                disabled={busy}
              >
                <Text style={styles.btnText}>− Chiqim</Text>
              </Pressable>
            </View>
            {error ? <Text style={ui.error}>{error}</Text> : null}
            <PrimaryButton
              label="Smenani yopish"
              tone="ink"
              onPress={doClose}
              loading={busy}
            />
          </FormCard>
        ) : (
          <FormCard>
            <Text style={styles.hint}>
              Naqd to‘lovlar uchun smenani oching.
            </Text>
            <FieldLabel>Boshlang‘ich naqd</FieldLabel>
            <TextInput
              style={styles.input}
              value={openingFloat}
              onChangeText={setOpeningFloat}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            {error ? <Text style={ui.error}>{error}</Text> : null}
            <PrimaryButton
              label="Smenani ochish"
              onPress={doOpen}
              loading={busy}
            />
            {shift && !shift.is_open ? (
              <View style={{ marginTop: 12 }}>
                <Row
                  label="Oxirgi farq"
                  value={shift.variance != null ? shift.variance : "—"}
                />
              </View>
            ) : null}
          </FormCard>
        )}

        <Text style={ui.section}>Tarix</Text>
        {history.length === 0 ? (
          <Text style={ui.rowMeta}>Yopilgan smena yo‘q</Text>
        ) : (
          history.map((h) => (
            <ListCard
              key={String(h.id)}
              title={
                h.is_open
                  ? "Ochiq smena"
                  : `Yopilgan · farq ${h.variance ?? "—"}`
              }
              meta={`${String(h.opened_at || "").replace("T", " ").slice(0, 16)} → ${
                h.closed_at
                  ? String(h.closed_at).replace("T", " ").slice(0, 16)
                  : "…"
              }`}
              badge={h.is_open ? "OCHIQ" : "YOPIQ"}
              badgeTone={h.is_open ? "success" : "neutral"}
              onPress={() => onPrint(Number(h.id))}
            />
          ))
        )}
      </ScrollView>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLbl}>{label}</Text>
      <Text style={styles.rowVal}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.paper,
  },
  body: { padding: space.lg, gap: space.md, paddingBottom: 48 },
  hint: {
    color: colors.muted,
    marginBottom: space.md,
    lineHeight: 20,
    fontFamily: fontUi,
  },
  input: {
    ...ui.input,
    fontSize: 18,
    fontWeight: "600",
  },
  row: {
    backgroundColor: colors.paper,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.sm,
  },
  rowLbl: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fontUi,
  },
  rowVal: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.ink,
    marginTop: 4,
    fontFamily: fontUi,
  },
  btnText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 15,
    fontFamily: fontUi,
  },
  moveRow: { flexDirection: "row", gap: space.sm, marginBottom: space.md },
  moveBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: radius.md,
    alignItems: "center",
  },
  moveIn: { backgroundColor: colors.success },
  moveOut: { backgroundColor: colors.warn },
  disabled: { opacity: 0.7 },
});
