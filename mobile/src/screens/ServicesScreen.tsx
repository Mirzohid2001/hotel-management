import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { ServiceItem } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SegmentedTabs,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };
type Tab = "order" | "catalog" | "recent";

export function ServicesScreen({ onBack }: Props) {
  const {
    fetchServices,
    orderServiceQuick,
    fetchServiceOrders,
    fetchServicesCatalog,
    createServiceItem,
    updateServiceItem,
  } = useAuth();
  const [tab, setTab] = useState<Tab>("order");
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [catalog, setCatalog] = useState<Record<string, unknown>[]>([]);
  const [recent, setRecent] = useState<Record<string, unknown>[]>([]);
  const [room, setRoom] = useState("");
  const [qty, setQty] = useState("1");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [editPrice, setEditPrice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "order") {
        setServices(await fetchServices());
      } else if (tab === "catalog") {
        setCatalog(await fetchServicesCatalog());
      } else {
        setRecent(await fetchServiceOrders());
      }
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [tab, fetchServices, fetchServicesCatalog, fetchServiceOrders]);

  useEffect(() => {
    load();
  }, [load]);

  async function onOrder() {
    if (!room.trim() || !selectedId) {
      Alert.alert("Xato", "Xona va xizmatni tanlang");
      return;
    }
    setBusy(true);
    try {
      const res = await orderServiceQuick({
        room_number: room.trim(),
        service_id: selectedId,
        quantity: qty.trim() || "1",
      });
      Alert.alert(
        "Xizmat",
        `${res.room} · ${res.service} · ${res.amount}`
      );
      setSelectedId(null);
      setQty("1");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Buyurtma xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function onCreate() {
    if (!newName.trim() || !newCode.trim()) {
      Alert.alert("Xato", "Nom va kod kerak");
      return;
    }
    setBusy(true);
    try {
      await createServiceItem({
        name: newName.trim(),
        code: newCode.trim().toLowerCase(),
        unit_price: newPrice.trim() || "0",
      });
      setNewName("");
      setNewCode("");
      setNewPrice("");
      await load();
      Alert.alert("Xizmat", "Qo‘shildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveEdit() {
    if (!editId) return;
    setBusy(true);
    try {
      await updateServiceItem(editId, { unit_price: editPrice.trim() });
      setEditId(null);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Operatsiya"
        title="Xizmatlar"
        subtitle="Buyurtma · katalog · tarix"
        onBack={onBack}
      />
      <View style={styles.pad}>
        <SegmentedTabs
          value={tab}
          onChange={(v) => setTab(v)}
          tabs={[
            { id: "order", label: "Buyurtma" },
            { id: "catalog", label: "Katalog" },
            { id: "recent", label: "Tarix" },
          ]}
        />
      </View>

      {tab === "order" ? (
        <>
          <View style={styles.pad}>
            <FormCard>
              <FieldLabel>Xona raqami</FieldLabel>
              <TextInput
                style={ui.input}
                value={room}
                onChangeText={setRoom}
                placeholder="103"
                placeholderTextColor={colors.faint}
                keyboardType="number-pad"
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
                label="Hisobga yozish"
                onPress={onOrder}
                loading={busy}
                disabled={busy}
              />
            </FormCard>
          </View>
          {loading ? (
            <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
          ) : (
            <FlatList
              data={services}
              keyExtractor={(s) => String(s.id)}
              contentContainerStyle={ui.listPad}
              ListEmptyComponent={
                <EmptyState title="Xizmat yo‘q" hint="Katalogga qo‘shing" />
              }
              renderItem={({ item }) => (
                <ListCard
                  title={item.name}
                  meta={`${item.unit_price} ${item.currency || ""}`}
                  badge={selectedId === item.id ? "Tanlangan" : item.code}
                  badgeTone={selectedId === item.id ? "accent" : "neutral"}
                  onPress={() => setSelectedId(item.id)}
                />
              )}
            />
          )}
        </>
      ) : null}

      {tab === "catalog" ? (
        <>
          <View style={styles.pad}>
            <FormCard>
              <FieldLabel>Yangi xizmat</FieldLabel>
              <TextInput
                style={ui.input}
                value={newName}
                onChangeText={setNewName}
                placeholder="Nonushta"
                placeholderTextColor={colors.faint}
              />
              <TextInput
                style={ui.input}
                value={newCode}
                onChangeText={setNewCode}
                placeholder="kod"
                placeholderTextColor={colors.faint}
                autoCapitalize="none"
              />
              <TextInput
                style={ui.input}
                value={newPrice}
                onChangeText={setNewPrice}
                placeholder="narx"
                placeholderTextColor={colors.faint}
                keyboardType="decimal-pad"
              />
              <PrimaryButton label="Qo‘shish" onPress={onCreate} loading={busy} />
            </FormCard>
          </View>
          {loading ? (
            <ActivityIndicator color={colors.accent} />
          ) : (
            <FlatList
              data={catalog}
              keyExtractor={(s) => String(s.id)}
              contentContainerStyle={ui.listPad}
              renderItem={({ item }) => {
                const id = Number(item.id);
                const editing = editId === id;
                return (
                  <ListCard
                    title={String(item.name)}
                    meta={`${item.unit_price} · ${item.code}${item.is_active === false ? " · o‘chiq" : ""}`}
                    badge={editing ? "Tahrir" : undefined}
                    onPress={() => {
                      setEditId(id);
                      setEditPrice(String(item.unit_price ?? ""));
                    }}
                  >
                    {editing ? (
                      <View style={{ marginTop: 10, gap: 8 }}>
                        <TextInput
                          style={ui.input}
                          value={editPrice}
                          onChangeText={setEditPrice}
                          keyboardType="decimal-pad"
                          placeholderTextColor={colors.faint}
                        />
                        <PrimaryButton label="Saqlash" onPress={onSaveEdit} loading={busy} />
                        <PrimaryButton
                          label="Faol / o‘chirish"
                          tone="ghost"
                          onPress={async () => {
                            try {
                              await updateServiceItem(id, {
                                is_active: item.is_active === false,
                              });
                              setEditId(null);
                              await load();
                            } catch (e) {
                              Alert.alert(
                                "Xato",
                                e instanceof ApiError ? e.message : "Xato"
                              );
                            }
                          }}
                        />
                      </View>
                    ) : null}
                  </ListCard>
                );
              }}
            />
          )}
        </>
      ) : null}

      {tab === "recent" ? (
        loading ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
        ) : (
          <FlatList
            data={recent}
            keyExtractor={(r) => String(r.id)}
            contentContainerStyle={ui.listPad}
            ListEmptyComponent={<EmptyState title="Buyurtma yo‘q" />}
            renderItem={({ item }) => (
              <ListCard
                title={`${item.room || "—"} · ${item.service}`}
                meta={`${item.guest || ""} · ${item.amount} · ${String(item.created_at || "").slice(0, 16)}`}
              />
            )}
          />
        )
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md },
});
