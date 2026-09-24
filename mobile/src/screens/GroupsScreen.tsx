import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation: (id: number) => void;
};

export function GroupsScreen({ onBack, onOpenReservation }: Props) {
  const { fetchGroups, fetchGroup } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchGroups());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchGroups]);

  useEffect(() => {
    load();
  }, [load]);

  async function openGroup(id: number) {
    try {
      setDetail(await fetchGroup(id));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  if (detail) {
    const rooms = (detail.reservations as Record<string, unknown>[]) || [];
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow={String(detail.code)}
          title={String(detail.name)}
          subtitle={`${detail.check_in} → ${detail.check_out}`}
          onBack={() => setDetail(null)}
        />
        <FlatList
          data={rooms}
          keyExtractor={(r) => String(r.id)}
          contentContainerStyle={ui.listPad}
          renderItem={({ item }) => (
            <Pressable
              style={ui.rowItem}
              onPress={() => onOpenReservation(Number(item.id))}
            >
              <Text style={ui.rowTitle}>
                {String((item.guest as { name?: string })?.name || item.code)}
              </Text>
              <Text style={ui.rowMeta}>
                {(item.room as { number?: string })?.number || "—"} ·{" "}
                {String(item.status)}
              </Text>
            </Pressable>
          )}
        />
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader eyebrow="Bron" title="Guruhlar" onBack={onBack} />
      {loading && !items.length ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
          }
          ListEmptyComponent={<Text style={ui.empty}>Guruh yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable style={ui.rowItem} onPress={() => openGroup(Number(item.id))}>
              <Text style={ui.rowTitle}>
                {String(item.code)} · {String(item.name)}
              </Text>
              <Text style={ui.rowMeta}>
                {String(item.check_in)} → {String(item.check_out)} ·{" "}
                {String(item.rooms)} xona
                {item.company ? ` · ${item.company}` : ""}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}
