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
import type { MaintenanceTicket } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

const PRIORITIES = [
  { id: "low", label: "Past" },
  { id: "medium", label: "O‘rtacha" },
  { id: "high", label: "Yuqori" },
] as const;

export function MaintenanceScreen({ onBack }: Props) {
  const {
    fetchMaintenance,
    createMaintenance,
    completeMaintenance,
    fetchBoard,
    me,
  } = useAuth();
  const [items, setItems] = useState<MaintenanceTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [roomNumber, setRoomNumber] = useState("");
  const [priority, setPriority] =
    useState<(typeof PRIORITIES)[number]["id"]>("medium");
  const [ooo, setOoo] = useState(false);
  const [busy, setBusy] = useState(false);

  const canWrite =
    me?.permissions?.maintenance === true ||
    ["admin", "manager", "receptionist"].includes(me?.role || "");

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setItems(await fetchMaintenance());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchMaintenance]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function submit() {
    if (!title.trim()) {
      Alert.alert("Ta’mir", "Sarlavha kiriting");
      return;
    }
    setBusy(true);
    try {
      const payload: {
        title: string;
        description?: string;
        priority: string;
        set_room_ooo: boolean;
        room_id?: number;
      } = {
        title: title.trim(),
        description: description.trim(),
        priority,
        set_room_ooo: ooo,
      };
      const num = roomNumber.trim();
      if (num) {
        const board = await fetchBoard();
        const match = board.tiles.find((t) => t.room.number === num);
        if (!match) {
          Alert.alert("Ta’mir", `Xona ${num} topilmadi`);
          setBusy(false);
          return;
        }
        payload.room_id = match.room.id;
      }
      await createMaintenance(payload);
      setTitle("");
      setDescription("");
      setRoomNumber("");
      setOoo(false);
      setCreating(false);
      await load(true);
      Alert.alert("Ta’mir", "Ariza ochildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function complete(id: number) {
    try {
      await completeMaintenance(id);
      await load(true);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Operatsiya"
        title="Ta’mir"
        subtitle={`${items.length} ochiq ariza`}
        onBack={onBack}
        right={
          canWrite ? (
            <Pressable
              style={ui.copperBtn}
              onPress={() => setCreating((v) => !v)}
            >
              <Text style={ui.copperBtnText}>
                {creating ? "Yopish" : "+ Yangi"}
              </Text>
            </Pressable>
          ) : null
        }
      />

      {error ? <Text style={[ui.error, { padding: space.lg }]}>{error}</Text> : null}

      {creating ? (
        <View style={styles.form}>
          <TextInput
            style={ui.input}
            placeholder="Sarlavha"
            placeholderTextColor={colors.faint}
            value={title}
            onChangeText={setTitle}
          />
          <TextInput
            style={[ui.input, styles.area]}
            placeholder="Tavsif"
            placeholderTextColor={colors.faint}
            value={description}
            onChangeText={setDescription}
            multiline
          />
          <TextInput
            style={ui.input}
            placeholder="Xona raqami (ixtiyoriy)"
            placeholderTextColor={colors.faint}
            value={roomNumber}
            onChangeText={setRoomNumber}
          />
          <View style={styles.prioRow}>
            {PRIORITIES.map((p) => (
              <Pressable
                key={p.id}
                style={[ui.chip, priority === p.id && ui.chipOn, { flex: 1 }]}
                onPress={() => setPriority(p.id)}
              >
                <Text
                  style={[
                    ui.chipText,
                    priority === p.id && ui.chipTextOn,
                    { textAlign: "center" },
                  ]}
                >
                  {p.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <Pressable style={styles.check} onPress={() => setOoo((v) => !v)}>
            <Text style={styles.checkText}>
              {ooo ? "☑" : "☐"}  Xonani OOO qilish
            </Text>
          </Pressable>
          <Pressable
            style={[ui.primaryBtn, busy && { opacity: 0.7 }]}
            onPress={submit}
            disabled={busy}
          >
            <Text style={ui.primaryBtnText}>Ochish</Text>
          </Pressable>
        </View>
      ) : null}

      {loading && items.length === 0 ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => String(t.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={<Text style={ui.empty}>Ochiq ariza yo‘q</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={ui.rowItem}
              onPress={() => {
                if (!canWrite) return;
                Alert.alert(item.title, "Arizani yakunlash?", [
                  { text: "Bekor", style: "cancel" },
                  {
                    text: "Bajarildi",
                    onPress: () => complete(item.id),
                  },
                ]);
              }}
            >
              <Text style={ui.rowTitle}>
                {item.room ? `${item.room.number} · ` : ""}
                {item.title}
              </Text>
              <Text style={ui.rowMeta}>
                {item.priority} · {item.status}
                {item.assignee ? ` · ${item.assignee}` : ""}
                {canWrite ? " · bajarish ›" : ""}
              </Text>
              {item.description ? (
                <Text style={styles.desc} numberOfLines={2}>
                  {item.description}
                </Text>
              ) : null}
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  form: {
    margin: space.lg,
    padding: space.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
  },
  area: { minHeight: 72, textAlignVertical: "top" },
  prioRow: { flexDirection: "row", gap: space.sm, marginBottom: space.sm },
  check: { paddingVertical: space.sm, marginBottom: space.sm },
  checkText: {
    color: colors.ink,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  desc: {
    marginTop: 6,
    color: colors.inkSoft,
    fontSize: 13,
    fontFamily: fontUi,
  },
});
