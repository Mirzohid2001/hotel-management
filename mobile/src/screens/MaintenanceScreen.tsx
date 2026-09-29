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
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
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
    assignMaintenance,
    cancelMaintenance,
    spendMaintenance,
    fetchBoard,
    fetchHkStaff,
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
  const [spendId, setSpendId] = useState<number | null>(null);
  const [spendAmount, setSpendAmount] = useState("");
  const [assignFor, setAssignFor] = useState<number | null>(null);
  const [actionItem, setActionItem] = useState<MaintenanceTicket | null>(null);
  const [staff, setStaff] = useState<{ id: number; label: string }[]>([]);

  const canWrite =
    me?.permissions?.maintenance === true ||
    ["admin", "manager", "receptionist"].includes(me?.role || "");
  const canSpend =
    me?.permissions?.maintenance === true ||
    ["admin", "manager"].includes(me?.role || "");

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
      setActionItem(null);
      await load(true);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function assign(id: number, userId?: number) {
    try {
      await assignMaintenance(id, userId);
      setAssignFor(null);
      setActionItem(null);
      await load(true);
      Alert.alert("Ta’mir", userId ? "Xodimga biriktirildi" : "O‘zingizga biriktirildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function openStaffPicker(ticketId: number) {
    setAssignFor(ticketId);
    try {
      const rows = await fetchHkStaff();
      setStaff(
        rows
          .map((r) => ({
            id: Number(r.id),
            label: String(r.name || r.username || r.id),
          }))
          .filter((r) => Number.isFinite(r.id) && r.id > 0)
      );
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function cancel(id: number) {
    try {
      await cancelMaintenance(id);
      setActionItem(null);
      await load(true);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function submitSpend() {
    if (spendId == null || !spendAmount.trim()) {
      Alert.alert("Xarajat", "Summani kiriting");
      return;
    }
    setBusy(true);
    try {
      await spendMaintenance(spendId, {
        amount: spendAmount.trim().replace(/\s/g, "").replace(",", "."),
      });
      setSpendId(null);
      setSpendAmount("");
      setActionItem(null);
      await load(true);
      Alert.alert("Ta’mir", "Xarajat yozildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function openActions(item: MaintenanceTicket) {
    if (!canWrite) return;
    setAssignFor(null);
    setSpendId(null);
    setActionItem(item);
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
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>Sarlavha</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Masalan: Konditsioner"
              placeholderTextColor={colors.faint}
              value={title}
              onChangeText={setTitle}
            />
            <FieldLabel>Tavsif</FieldLabel>
            <TextInput
              style={[ui.input, styles.area]}
              placeholder="Muammo haqida"
              placeholderTextColor={colors.faint}
              value={description}
              onChangeText={setDescription}
              multiline
            />
            <FieldLabel>Xona (ixtiyoriy)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="101"
              placeholderTextColor={colors.faint}
              value={roomNumber}
              onChangeText={setRoomNumber}
            />
            <FieldLabel>Prioritet</FieldLabel>
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
            <PrimaryButton label="Ariza ochish" onPress={submit} loading={busy} />
          </FormCard>
        </View>
      ) : null}

      {actionItem ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <Text style={ui.section}>{actionItem.title}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Pressable style={ui.chip} onPress={() => assign(actionItem.id)}>
                <Text style={ui.chipText}>Menga biriktirish</Text>
              </Pressable>
              <Pressable
                style={ui.chip}
                onPress={() => openStaffPicker(actionItem.id)}
              >
                <Text style={ui.chipText}>Xodimga biriktirish</Text>
              </Pressable>
              <Pressable style={ui.chip} onPress={() => complete(actionItem.id)}>
                <Text style={ui.chipText}>Bajarildi</Text>
              </Pressable>
              {canSpend ? (
                <Pressable
                  style={ui.chip}
                  onPress={() => {
                    setSpendId(actionItem.id);
                    setSpendAmount("");
                  }}
                >
                  <Text style={ui.chipText}>Xarajat yozish</Text>
                </Pressable>
              ) : null}
              <Pressable
                style={ui.chip}
                onPress={() =>
                  Alert.alert("Bekor", "Ariza bekor qilinsinmi?", [
                    { text: "Yo‘q", style: "cancel" },
                    {
                      text: "Ha",
                      style: "destructive",
                      onPress: () => cancel(actionItem.id),
                    },
                  ])
                }
              >
                <Text style={ui.chipText}>Bekor qilish</Text>
              </Pressable>
              <Pressable style={ui.chip} onPress={() => setActionItem(null)}>
                <Text style={ui.chipText}>Yopish</Text>
              </Pressable>
            </View>
          </FormCard>
        </View>
      ) : null}

      {assignFor != null ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <Text style={ui.section}>Xodimga biriktirish</Text>
            {staff.length === 0 ? (
              <Text style={ui.rowMeta}>Xodimlar ro‘yxati ochilmadi</Text>
            ) : (
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {staff.map((s) => (
                  <Pressable
                    key={s.id}
                    style={ui.chip}
                    onPress={() => assign(assignFor, s.id)}
                  >
                    <Text style={ui.chipText}>{s.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}
            <Pressable
              style={[ui.chip, { marginTop: 10, alignSelf: "flex-start" }]}
              onPress={() => setAssignFor(null)}
            >
              <Text style={ui.chipText}>Bekor</Text>
            </Pressable>
          </FormCard>
        </View>
      ) : null}

      {spendId != null ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>{`Xarajat · ariza #${spendId}`}</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Summa"
              placeholderTextColor={colors.faint}
              keyboardType="decimal-pad"
              value={spendAmount}
              onChangeText={setSpendAmount}
            />
            <View style={styles.prioRow}>
              <Pressable
                style={[ui.chip, { flex: 1 }]}
                onPress={() => {
                  setSpendId(null);
                  setSpendAmount("");
                }}
              >
                <Text style={[ui.chipText, { textAlign: "center" }]}>Bekor</Text>
              </Pressable>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  label="Saqlash"
                  onPress={submitSpend}
                  loading={busy}
                />
              </View>
            </View>
          </FormCard>
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
          ListEmptyComponent={
            <EmptyState title="Ochiq ariza yo‘q" hint="Hammasi joyida" />
          }
          renderItem={({ item }) => {
            const prioTone =
              item.priority === "high"
                ? "danger"
                : item.priority === "low"
                  ? "neutral"
                  : "warn";
            return (
              <ListCard
                title={`${item.room ? `${item.room.number} · ` : ""}${item.title}`}
                meta={`${item.status}${item.assignee ? ` · ${item.assignee}` : ""}${
                  canWrite ? " · amallar" : ""
                }`}
                badge={item.priority}
                badgeTone={prioTone}
                onPress={() => openActions(item)}
              >
                {item.description ? (
                  <Text style={styles.desc} numberOfLines={2}>
                    {item.description}
                  </Text>
                ) : null}
              </ListCard>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  area: { minHeight: 72, textAlignVertical: "top" },
  prioRow: {
    flexDirection: "row",
    gap: space.sm,
    marginBottom: space.sm,
    alignItems: "center",
  },
  check: { paddingVertical: space.sm, marginBottom: space.sm },
  checkText: {
    color: colors.ink,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  desc: {
    marginTop: 8,
    color: colors.inkSoft,
    fontSize: 13,
    fontFamily: fontUi,
    lineHeight: 18,
  },
});
