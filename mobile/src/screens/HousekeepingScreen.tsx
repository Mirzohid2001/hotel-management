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
import { EmptyState, ListCard, StatsStrip } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = {
  onBack?: () => void;
  onChanged?: () => void;
};

type Staff = { id: number; username: string; name: string };

export function HousekeepingScreen({ onBack, onChanged }: Props) {
  const {
    fetchHousekeeping,
    completeHkTask,
    setRoomStatus,
    fetchHkStaff,
    assignHkTask,
  } = useAuth();
  const [data, setData] = useState<HkBoard | null>(null);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const [board, staffList] = await Promise.all([
          fetchHousekeeping(),
          fetchHkStaff().catch(() => [] as Staff[]),
        ]);
        setData(board);
        setStaff(staffList);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchHousekeeping, fetchHkStaff]
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

  function assignTask(taskId: number) {
    const buttons: {
      text: string;
      style?: "cancel" | "destructive" | "default";
      onPress?: () => void;
    }[] = [
      { text: "Bekor", style: "cancel" },
      {
        text: "Menga",
        onPress: async () => {
          try {
            await assignHkTask(taskId);
            await load(true);
            onChanged?.();
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      },
    ];
    for (const s of staff.slice(0, 8)) {
      buttons.push({
        text: s.name || s.username,
        onPress: async () => {
          try {
            await assignHkTask(taskId, s.id);
            await load(true);
            onChanged?.();
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      });
    }
    Alert.alert("Biriktirish", "Kimga biriktirilsin?", buttons);
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
            ? `Kir ${data.stats.dirty} · Tayyor ${data.stats.ready}`
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
              {data ? (
                <StatsStrip
                  items={[
                    {
                      label: "Kir",
                      value: data.stats.dirty,
                      warn: data.stats.dirty > 0,
                    },
                    { label: "Tayyor", value: data.stats.ready },
                    { label: "Vazifa", value: data.tasks.length },
                  ]}
                />
              ) : null}

              <Text style={[ui.section, { marginTop: space.md }]}>Vazifalar</Text>
              {(data?.tasks || []).length === 0 ? (
                <EmptyState title="Ochiq vazifa yo‘q" />
              ) : (
                data!.tasks.map((t) => (
                  <ListCard
                    key={t.id}
                    title={`${t.room.number} · ${t.title}`}
                    meta={
                      t.assigned_to
                        ? `${t.status} · ${t.assigned_to}`
                        : `${t.status} · biriktirilmagan`
                    }
                    badge={t.assigned_to ? "Biriktirilgan" : "Ochiq"}
                    badgeTone={t.assigned_to ? "accent" : "warn"}
                  >
                    <View style={styles.taskActions}>
                      <Pressable
                        style={({ pressed }) => [
                          styles.mini,
                          pressed && { opacity: 0.85 },
                        ]}
                        onPress={() => assignTask(t.id)}
                      >
                        <Text style={styles.miniText}>Biriktir</Text>
                      </Pressable>
                      <Pressable
                        style={({ pressed }) => [
                          styles.mini,
                          styles.miniDone,
                          pressed && { opacity: 0.85 },
                        ]}
                        onPress={() => completeTask(t.id)}
                      >
                        <Text style={styles.miniText}>Tayyor</Text>
                      </Pressable>
                    </View>
                  </ListCard>
                ))
              )}
              <Text style={[ui.section, { marginTop: space.lg }]}>
                Kir xonalar
              </Text>
            </>
          }
          ListEmptyComponent={
            <EmptyState title="Kir xona yo‘q" hint="Hammasi toza" />
          }
          contentContainerStyle={ui.listPad}
          renderItem={({ item }) => (
            <ListCard
              title={`${item.number} · ${item.room_type}`}
              meta="Bosing — tayyor deb belgilash"
              badge={item.status}
              badgeTone={item.status === "cleaning" ? "info" : "warn"}
              onPress={() => markReady(item.id, item.number)}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  taskActions: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
  },
  mini: {
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderRadius: radius.sm,
    backgroundColor: colors.nightLift,
  },
  miniDone: { backgroundColor: colors.accent },
  miniText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 12,
    fontFamily: fontUi,
  },
});
