import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { CashShift } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
};

export function CashShiftScreen({ onBack }: Props) {
  const { me, fetchCashShift, openCashShift, closeCashShift, postCashMovement } =
    useAuth();
  const [shift, setShift] = useState<CashShift | null>(null);
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
      const s = await fetchCashShift();
      setShift(s);
      if (s?.expected_cash) setClosingCash(s.expected_cash);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [fetchCashShift]);

  useEffect(() => {
    load();
  }, [load]);

  async function doOpen() {
    setBusy(true);
    setError(null);
    try {
      const s = await openCashShift(openingFloat.trim() || "0");
      setShift(s);
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
      />

      <View style={styles.body}>
        <View
          style={[styles.badge, open ? styles.badgeOpen : styles.badgeClosed]}
        >
          <Text style={styles.badgeText}>{open ? "OCHIQ" : "YOPIQ"}</Text>
        </View>

        {open && shift ? (
          <>
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
            <Text style={styles.label}>Yakuniy naqd *</Text>
            <TextInput
              style={styles.input}
              value={closingCash}
              onChangeText={setClosingCash}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <Text style={styles.label}>Kassa harakati</Text>
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
            <Pressable
              style={[styles.btn, styles.btnClose, busy && styles.disabled]}
              onPress={doClose}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.btnText}>Smenani yopish</Text>
              )}
            </Pressable>
          </>
        ) : (
          <>
            <Text style={styles.hint}>
              Naqd to‘lovlar uchun smenani oching.
            </Text>
            <Text style={styles.label}>Boshlang‘ich naqd</Text>
            <TextInput
              style={styles.input}
              value={openingFloat}
              onChangeText={setOpeningFloat}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            {error ? <Text style={ui.error}>{error}</Text> : null}
            <Pressable
              style={[styles.btn, busy && styles.disabled]}
              onPress={doOpen}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.btnText}>Smenani ochish</Text>
              )}
            </Pressable>
            {shift && !shift.is_open ? (
              <View style={{ marginTop: 16 }}>
                <Row
                  label="Oxirgi farq"
                  value={shift.variance != null ? shift.variance : "—"}
                />
              </View>
            ) : null}
          </>
        )}
      </View>
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
  body: { padding: space.xl },
  badge: {
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.sm,
    marginBottom: space.lg,
  },
  badgeOpen: { backgroundColor: colors.success },
  badgeClosed: { backgroundColor: colors.muted },
  badgeText: {
    color: colors.white,
    fontWeight: "800",
    letterSpacing: 0.8,
    fontFamily: fontUi,
  },
  hint: {
    color: colors.muted,
    marginBottom: space.lg,
    lineHeight: 20,
    fontFamily: fontUi,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
    marginBottom: 6,
    marginTop: 8,
    fontFamily: fontUi,
  },
  input: {
    ...ui.input,
    fontSize: 18,
    fontWeight: "600",
  },
  row: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: space.lg,
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
  btn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 4,
  },
  btnClose: { backgroundColor: colors.night },
  btnText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 16,
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
