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
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
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
  const {
    fetchInventory,
    adjustInventory,
    createInventoryItem,
    updateInventoryItem,
  } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [badges, setBadges] = useState<Record<string, number>>({});
  const [q, setQ] = useState("");
  const [flag, setFlag] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [qty, setQty] = useState("");
  const [moveType, setMoveType] = useState<"in" | "out" | "adjust">("in");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSku, setNewSku] = useState("");
  const [newSell, setNewSell] = useState("");
  const [newExpiry, setNewExpiry] = useState("");
  const [editName, setEditName] = useState("");
  const [editSell, setEditSell] = useState("");
  const [editReorder, setEditReorder] = useState("");
  const [editExpiry, setEditExpiry] = useState("");

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

  async function onCreate() {
    if (!newName.trim() || !newSku.trim()) {
      Alert.alert("Xato", "Nom va SKU kerak");
      return;
    }
    setBusy(true);
    try {
      await createInventoryItem({
        name: newName.trim(),
        sku: newSku.trim(),
        sell_price: newSell || "0",
        expiry_date: newExpiry.trim() || undefined,
      });
      setCreating(false);
      setNewName("");
      setNewSku("");
      setNewSell("");
      setNewExpiry("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onUpdateItem() {
    if (!selected?.id) return;
    setBusy(true);
    try {
      await updateInventoryItem(Number(selected.id), {
        name: editName.trim() || String(selected.name),
        sell_price: editSell.trim() || undefined,
        reorder_level: editReorder.trim() || undefined,
        expiry_date: editExpiry.trim(),
      });
      await load();
      Alert.alert("Ombor", "Mahsulot yangilandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function openItem(item: Record<string, unknown>) {
    setSelected(item);
    setEditName(String(item.name || ""));
    setEditSell(String(item.sell_price ?? ""));
    setEditReorder(String(item.reorder_level ?? ""));
    setEditExpiry(String(item.expiry_date || ""));
    setQty("");
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Ombor"
        title="Inventar"
        subtitle={
          badges.low
            ? `Kam qoldiq: ${badges.low}`
            : `${items.length} mahsulot`
        }
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => setCreating((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />

      {creating ? (
        <View style={styles.pad}>
          <FormCard>
            <FieldLabel>Nomi</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Suv"
              placeholderTextColor={colors.faint}
              value={newName}
              onChangeText={setNewName}
            />
            <FieldLabel>SKU</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="suv-05"
              placeholderTextColor={colors.faint}
              value={newSku}
              onChangeText={setNewSku}
              autoCapitalize="none"
            />
            <FieldLabel>Sotish narxi</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="5000"
              placeholderTextColor={colors.faint}
              value={newSell}
              onChangeText={setNewSell}
              keyboardType="decimal-pad"
            />
            <FieldLabel>Yaroqlilik (YYYY-MM-DD)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="2026-12-31"
              placeholderTextColor={colors.faint}
              value={newExpiry}
              onChangeText={setNewExpiry}
              autoCapitalize="none"
            />
            <PrimaryButton label="Saqlash" onPress={onCreate} loading={busy} />
          </FormCard>
        </View>
      ) : null}

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
              style={[ui.chip, flag === f.id && ui.chipOn]}
              onPress={() => setFlag(f.id)}
            >
              <Text style={[ui.chipText, flag === f.id && ui.chipTextOn]}>
                {f.label}
                {f.id && badges[f.id] != null ? ` ${badges[f.id]}` : ""}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {selected ? (
        <View style={styles.pad}>
          <FormCard>
            <Text style={ui.rowTitle}>{String(selected.name)}</Text>
            <Text style={[ui.rowMeta, { marginBottom: 8 }]}>
              {String(selected.quantity_on_hand)} {String(selected.unit)} ·{" "}
              {String(selected.sku)}
            </Text>
            <FieldLabel>Nom</FieldLabel>
            <TextInput
              style={ui.input}
              value={editName}
              onChangeText={setEditName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Sotish narxi</FieldLabel>
            <TextInput
              style={ui.input}
              value={editSell}
              onChangeText={setEditSell}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Minimal qoldiq</FieldLabel>
            <TextInput
              style={ui.input}
              value={editReorder}
              onChangeText={setEditReorder}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Yaroqlilik (YYYY-MM-DD)</FieldLabel>
            <TextInput
              style={ui.input}
              value={editExpiry}
              onChangeText={setEditExpiry}
              placeholder="2026-12-31"
              placeholderTextColor={colors.faint}
              autoCapitalize="none"
            />
            <PrimaryButton
              label="Ma’lumotni saqlash"
              onPress={onUpdateItem}
              loading={busy}
              tone="ink"
            />
            <Text style={[ui.section, { marginTop: space.md }]}>Harakat</Text>
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
                  style={[ui.chip, moveType === id && ui.chipOn]}
                  onPress={() => setMoveType(id)}
                >
                  <Text
                    style={[ui.chipText, moveType === id && ui.chipTextOn]}
                  >
                    {label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <FieldLabel>Miqdor</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="0"
              value={qty}
              onChangeText={setQty}
              keyboardType="decimal-pad"
              placeholderTextColor={colors.faint}
            />
            <View style={styles.rowBtns}>
              <Pressable style={ui.copperBtn} onPress={() => setSelected(null)}>
                <Text style={ui.copperBtnText}>Bekor</Text>
              </Pressable>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  label="Harakat"
                  onPress={onAdjust}
                  loading={busy}
                />
              </View>
            </View>
          </FormCard>
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
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Mahsulot yo‘q" hint="Filterni o‘zgartiring" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.name)}
              meta={`${String(item.quantity_on_hand)} ${String(item.unit)} · ${String(item.sku)}`}
              badge={
                item.is_low
                  ? "KAM"
                  : item.is_minibar
                    ? "MB"
                    : item.is_expired
                      ? "Muddati o‘tgan"
                      : String(item.sell_price || "")
              }
              badgeTone={
                item.is_low || item.is_expired
                  ? "danger"
                  : item.is_minibar
                    ? "info"
                    : "accent"
              }
              onPress={() => openItem(item)}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.sm },
  flags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: space.sm,
  },
  rowBtns: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    marginTop: space.sm,
  },
});
