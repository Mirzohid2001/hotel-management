import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { HkBoard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onBack?: () => void;
  onChanged?: () => void;
};

export function HousekeepingScreen({ onBack, onChanged }: Props) {
  const { fetchHousekeeping, completeHkTask, setRoomStatus } = useAuth();
  const [data, setData] = useState<HkBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchHousekeeping());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchHousekeeping]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function markReady(roomId: number, number: string) {
    try {
      await setRoomStatus(roomId, "ready");
      await load(true);
      onChanged?.();
      Alert.alert("Tozalash", `Xona ${number} tayyor`);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function completeTask(taskId: number) {
    try {
      await completeHkTask(taskId);
      await load(true);
      onChanged?.();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  const dirty =
    data?.rooms.filter((r) => r.status === "dirty" || r.status === "cleaning") ||
    [];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Operatsiya"
        title="Tozalash"
        subtitle={
          data
            ? `Kir ${data.stats.dirty} · Tayyor ${data.stats.ready} · Vazifa ${data.tasks.length}`
            : undefined
        }
        onBack={onBack}
      />

      {error ? (
        <Text style={[ui.error, { padding: space.lg }]}>{error}</Text>
      ) : null}
      {loading && !data ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={dirty}
          keyExtractor={(r) => String(r.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListHeaderComponent={
            <>
              <Text style={ui.section}>Vazifalar</Text>
              {(data?.tasks || []).length === 0 ? (
                <Text style={[ui.empty, styles.softEmpty]}>
                  Ochiq vazifa yo‘q
                </Text>
              ) : (
                data!.tasks.map((t) => (
                  <Pressable
                    key={t.id}
                    style={ui.rowItem}
                    onPress={() => completeTask(t.id)}
                  >
                    <Text style={ui.rowTitle}>
                      {t.room.number} · {t.title}
                    </Text>
                    <Text style={ui.rowMeta}>
                      {t.status}
                      {t.assigned_to ? ` · ${t.assigned_to}` : ""} · bajarish ›
                    </Text>
                  </Pressable>
                ))
              )}
              <Text style={ui.section}>Kir / tozalanayotgan</Text>
            </>
          }
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={
            <Text style={[ui.empty, styles.softEmpty]}>Hammasi toza</Text>
          }
          renderItem={({ item }) => (
            <Pressable
              style={ui.rowItem}
              onPress={() => markReady(item.id, item.number)}
            >
              <Text style={ui.rowTitle}>
                {item.number}
                {item.room_type ? ` · ${item.room_type}` : ""}
              </Text>
              <Text style={ui.rowMeta}>{item.status} · tayyor qilish ›</Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  softEmpty: {
    marginTop: space.sm,
    marginBottom: space.md,
    textAlign: "left",
  },
});
