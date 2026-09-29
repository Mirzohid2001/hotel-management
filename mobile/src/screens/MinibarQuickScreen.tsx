import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  StyleSheet,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { MinibarItem } from "../api/types";
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

export function MinibarQuickScreen({ onBack }: Props) {
  const { fetchMinibarItems, postMinibarQuick } = useAuth();
  const [items, setItems] = useState<MinibarItem[]>([]);
  const [room, setRoom] = useState("");
  const [qty, setQty] = useState("1");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchMinibarItems());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [fetchMinibarItems]);

  useEffect(() => {
    load();
  }, [load]);

  async function onSell() {
    if (!room.trim()) {
      Alert.alert("Xato", "Xona raqamini kiriting");
      return;
    }
    if (!selectedId) {
      Alert.alert("Xato", "Mahsulot tanlang");
      return;
    }
    setBusy(true);
    try {
      const res = await postMinibarQuick(
        room.trim(),
        selectedId,
        qty.trim() || "1"
      );
      Alert.alert(
        "Minibar",
        `${res.room} · ${res.item} × ${res.quantity}\n${res.amount}`
      );
      setQty("1");
      setSelectedId(null);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Sotish xatosi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Operatsiya"
        title="Minibar tez"
        subtitle="Xona raqami → mahsulot"
        onBack={onBack}
      />
      <View style={styles.pad}>
        <FormCard>
          <FieldLabel>Xona raqami</FieldLabel>
          <TextInput
            style={ui.input}
            value={room}
            onChangeText={setRoom}
            placeholder="101"
            placeholderTextColor={colors.faint}
            keyboardType="number-pad"
            autoFocus
          />
          <FieldLabel>Miqdor</FieldLabel>
          <TextInput
            style={ui.input}
            value={qty}
            onChangeText={setQty}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <PrimaryButton
            label="Sotish"
            onPress={onSell}
            disabled={busy}
            loading={busy}
          />
        </FormCard>
      </View>

      {loading ? (
        <ActivityIndicator style={{ marginTop: 24 }} color={colors.accent} />
      ) : items.length === 0 ? (
        <EmptyState title="Minibar bo‘sh" hint="Avval omborda mahsulot qo‘shing" />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(it) => String(it.id)}
          contentContainerStyle={ui.listPad}
          renderItem={({ item }) => (
            <ListCard
              title={item.name}
              meta={`${item.sell_price} · qoldiq ${item.quantity_on_hand}`}
              badge={selectedId === item.id ? "Tanlangan" : undefined}
              badgeTone="accent"
              onPress={() => setSelectedId(item.id)}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md },
});
