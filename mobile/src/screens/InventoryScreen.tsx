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

const FLAGS: { id: string; label: string }[] = [
  { id: "", label: "Hammasi" },
  { id: "low", label: "Kam" },
  { id: "minibar", label: "Minibar" },
  { id: "soon", label: "Muddati" },
  { id: "expired", label: "O‘tgan" },
];

export function InventoryScreen({ onBack }: Props) {
  const { fetchInventory, adjustInventory } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [badges, setBadges] = useState<Record<string, number>>({});
  const [q, setQ] = useState("");
  const [flag, setFlag] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [qty, setQty] = useState("");
  const [moveType, setMoveType] = useState<"in" | "out" | "adjust">("in");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchInventory(q.trim(), flag);
      setItems(data.items);
      setBadges(data.badges || {});
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchInventory, q, flag]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  async function onAdjust() {
    if (!selected?.id || !qty.trim()) return;
    setBusy(true);
    try {
      await adjustInventory(Number(selected.id), {
        movement_type: moveType,
        quantity: qty.trim(),
      });
      setSelected(null);
      setQty("");
      await load();
      Alert.alert("Ombor", "Yangilandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Ombor"
        title="Inventar"
        subtitle={
          badges.low
            ? `Kam: ${badges.low} · Muddat: ${badges.soon || 0}`
            : undefined
        }
        onBack={onBack}
      />
      <View style={styles.pad}>
        <TextInput
          style={ui.input}
          placeholder="Qidiruv…"
          placeholderTextColor={colors.faint}
          value={q}
          onChangeText={setQ}
        />
        <View style={styles.flags}>
          {FLAGS.map((f) => (
            <Pressable
              key={f.id || "all"}
              style={[styles.chip, flag === f.id && styles.chipOn]}
              onPress={() => setFlag(f.id)}
            >
              <Text style={[styles.chipText, flag === f.id && styles.chipTextOn]}>
                {f.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {selected ? (
        <View style={styles.pad}>
          <Text style={ui.rowTitle}>{String(selected.name)}</Text>
          <View style={styles.flags}>
            {(
              [
                ["in", "Kirim"],
                ["out", "Chiqim"],
                ["adjust", "Belgilash"],
              ] as const
            ).map(([id, label]) => (
              <Pressable
                key={id}
                style={[styles.chip, moveType === id && styles.chipOn]}
                onPress={() => setMoveType(id)}
              >
                <Text
                  style={[styles.chipText, moveType === id && styles.chipTextOn]}
                >
                  {label}
                </Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            style={ui.input}
            placeholder="Miqdor"
            value={qty}
            onChangeText={setQty}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <View style={styles.rowBtns}>
            <Pressable style={ui.copperBtn} onPress={() => setSelected(null)}>
              <Text style={ui.copperBtnText}>Bekor</Text>
            </Pressable>
            <Pressable
              style={[ui.primaryBtn, { flex: 1 }, busy && { opacity: 0.6 }]}
              onPress={onAdjust}
              disabled={busy}
            >
              <Text style={ui.primaryBtnText}>Saqlash</Text>
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
          ListEmptyComponent={<Text style={ui.empty}>Mahsulot yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable style={ui.rowItem} onPress={() => setSelected(item)}>
              <Text style={ui.rowTitle}>
                {String(item.name)}
                {item.is_low ? " · KAM" : ""}
                {item.is_minibar ? " · MB" : ""}
              </Text>
              <Text style={ui.rowMeta}>
                {String(item.quantity_on_hand)} {String(item.unit)} ·{" "}
                {String(item.sku)}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.sm, gap: space.sm },
  flags: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
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
