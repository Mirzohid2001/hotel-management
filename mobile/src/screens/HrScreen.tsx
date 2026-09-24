import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function HrScreen({ onBack }: Props) {
  const { fetchEmployees, payEmployee, advanceEmployee } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [mode, setMode] = useState<"pay" | "advance">("pay");
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState("1");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchEmployees());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchEmployees]);

  useEffect(() => {
    load();
  }, [load]);

  async function onSubmit() {
    if (!selected?.id) return;
    setBusy(true);
    try {
      if (mode === "advance") {
        if (!amount.trim()) return;
        await advanceEmployee(Number(selected.id), amount.trim());
        Alert.alert("HR", "Avans berildi");
      } else {
        await payEmployee(Number(selected.id), {
          days: selected.is_daily ? Number(days) || 1 : undefined,
        });
        Alert.alert("HR", "To‘landi");
      }
      setSelected(null);
      setAmount("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader eyebrow="HR" title="Xodimlar" onBack={onBack} />

      {selected ? (
        <View style={styles.pad}>
          <Text style={ui.rowTitle}>{String(selected.full_name)}</Text>
          <Text style={ui.rowMeta}>
            {selected.is_daily ? "Kunlik" : "Oylik"} · stavka{" "}
            {String(selected.base_salary)} · avans {String(selected.open_advance)}
          </Text>
          <View style={styles.flags}>
            <Pressable
              style={[styles.chip, mode === "pay" && styles.chipOn]}
              onPress={() => setMode("pay")}
            >
              <Text style={[styles.chipText, mode === "pay" && styles.chipTextOn]}>
                To‘lash
              </Text>
            </Pressable>
            <Pressable
              style={[styles.chip, mode === "advance" && styles.chipOn]}
              onPress={() => setMode("advance")}
            >
              <Text
                style={[styles.chipText, mode === "advance" && styles.chipTextOn]}
              >
                Avans
              </Text>
            </Pressable>
          </View>
          {mode === "pay" && selected.is_daily ? (
            <TextInput
              style={ui.input}
              placeholder="Kunlar"
              value={days}
              onChangeText={setDays}
              keyboardType="number-pad"
              placeholderTextColor={colors.faint}
            />
          ) : null}
          {mode === "advance" ? (
            <TextInput
              style={ui.input}
              placeholder="Avans summasi"
              value={amount}
              onChangeText={setAmount}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
          ) : null}
          <View style={styles.rowBtns}>
            <Pressable style={ui.copperBtn} onPress={() => setSelected(null)}>
              <Text style={ui.copperBtnText}>Bekor</Text>
            </Pressable>
            <Pressable
              style={[ui.primaryBtn, { flex: 1 }, busy && { opacity: 0.6 }]}
              onPress={onSubmit}
              disabled={busy}
            >
              <Text style={ui.primaryBtnText}>
                {mode === "pay" ? "To‘lash" : "Avans berish"}
              </Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {loading ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
          }
          ListEmptyComponent={<Text style={ui.empty}>Xodim yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable style={ui.rowItem} onPress={() => setSelected(item)}>
              <Text style={ui.rowTitle}>{String(item.full_name)}</Text>
              <Text style={ui.rowMeta}>
                {String(item.position || "—")} ·{" "}
                {item.is_daily ? "kunlik" : "oylik"} {String(item.base_salary)}
                {Number(item.open_advance) > 0
                  ? ` · avans ${String(item.open_advance)}`
                  : ""}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md, gap: space.sm },
  flags: { flexDirection: "row", gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: colors.paperDeep,
  },
  chipOn: { backgroundColor: colors.accent },
  chipText: { color: colors.inkSoft, fontWeight: "600", fontSize: 13 },
  chipTextOn: { color: colors.white },
  rowBtns: { flexDirection: "row", gap: 10, alignItems: "center" },
});
