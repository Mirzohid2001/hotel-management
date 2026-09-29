import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SearchField,
  StatsStrip,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation?: (id: number) => void;
};

export function CompaniesScreen({ onBack, onOpenReservation }: Props) {
  const { fetchCompanies, createCompany, updateCompany, fetchCompanyDetail } =
    useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editCredit, setEditCredit] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchCompanies(q.trim()));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchCompanies, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  async function onCreate() {
    if (!name.trim()) return;
    try {
      await createCompany({ name: name.trim(), phone: phone.trim() });
      setName("");
      setPhone("");
      setCreating(false);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  async function openEdit(item: Record<string, unknown>) {
    setCreating(false);
    setEditing(item);
    setEditName(String(item.name || ""));
    setEditPhone(String(item.phone || ""));
    setEditCredit(String(item.credit_limit ?? ""));
    setEditActive(item.is_active !== false);
    setDetailBusy(true);
    try {
      setDetail(await fetchCompanyDetail(Number(item.id)));
    } catch (e) {
      setDetail(null);
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Detail xato");
    } finally {
      setDetailBusy(false);
    }
  }

  async function onSaveEdit() {
    if (!editing || !editName.trim()) return;
    setBusy(true);
    try {
      await updateCompany(Number(editing.id), {
        name: editName.trim(),
        phone: editPhone.trim(),
        credit_limit: editCredit.trim() || "0",
        is_active: editActive,
      });
      const refreshed = await fetchCompanyDetail(Number(editing.id));
      setDetail(refreshed);
      setEditing(refreshed);
      await load();
      Alert.alert("OK", "Saqlandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    const invoices = (detail?.invoices as Record<string, unknown>[]) || [];
    const reservations =
      (detail?.reservations as Record<string, unknown>[]) || [];
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow="Kompaniya"
          title={editName || String(editing.name || "Detail")}
          subtitle={editPhone || undefined}
          onBack={() => {
            setEditing(null);
            setDetail(null);
          }}
        />
        <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: 48 }}>
          <StatsStrip
            items={[
              { label: "Open AR", value: String(detail?.open_ar ?? "—") },
              { label: "Hisob", value: String(invoices.length) },
              { label: "Bron", value: String(reservations.length) },
            ]}
          />
          {detailBusy ? (
            <ActivityIndicator color={colors.accent} />
          ) : null}
          <FormCard>
            <FieldLabel>Nomi *</FieldLabel>
            <TextInput
              style={ui.input}
              value={editName}
              onChangeText={setEditName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Telefon</FieldLabel>
            <TextInput
              style={ui.input}
              value={editPhone}
              onChangeText={setEditPhone}
              placeholderTextColor={colors.faint}
              keyboardType="phone-pad"
            />
            <FieldLabel>Kredit limiti</FieldLabel>
            <TextInput
              style={ui.input}
              value={editCredit}
              onChangeText={setEditCredit}
              keyboardType="decimal-pad"
              placeholder="0"
              placeholderTextColor={colors.faint}
            />
            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              <Pressable
                style={[ui.chip, editActive && ui.chipOn]}
                onPress={() => setEditActive(true)}
              >
                <Text style={[ui.chipText, editActive && ui.chipTextOn]}>Faol</Text>
              </Pressable>
              <Pressable
                style={[ui.chip, !editActive && ui.chipOn]}
                onPress={() => setEditActive(false)}
              >
                <Text style={[ui.chipText, !editActive && ui.chipTextOn]}>
                  O‘chiq
                </Text>
              </Pressable>
            </View>
            <PrimaryButton label="Saqlash" onPress={onSaveEdit} loading={busy} />
          </FormCard>

          <Text style={ui.section}>Hisob-fakturalar</Text>
          {invoices.length === 0 ? (
            <Text style={ui.rowMeta}>Hisob yo‘q</Text>
          ) : (
            invoices.map((inv) => (
              <ListCard
                key={String(inv.id)}
                title={String(inv.code)}
                meta={`${inv.status} · balans ${inv.balance}`}
                badge={String(inv.status)}
                badgeTone={
                  inv.status === "open" || inv.status === "partial"
                    ? "warn"
                    : "success"
                }
              />
            ))
          )}

          <Text style={ui.section}>Bronlar</Text>
          {reservations.length === 0 ? (
            <Text style={ui.rowMeta}>Bron yo‘q</Text>
          ) : (
            reservations.map((r) => {
              const guest = (r.guest as { name?: string }) || {};
              const room = (r.room as { number?: string }) || {};
              return (
                <ListCard
                  key={String(r.id)}
                  title={`${room.number ? `#${room.number}` : "—"} · ${guest.name || "Mehmon"}`}
                  meta={`${r.code} · ${r.check_in} → ${r.check_out}`}
                  badge={String(r.status)}
                  onPress={
                    onOpenReservation
                      ? () => onOpenReservation(Number(r.id))
                      : undefined
                  }
                />
              );
            })
          )}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="CRM"
        title="Kompaniyalar"
        subtitle={
          items.length
            ? `${items.length} ta kompaniya`
            : "Korporativ mijozlar"
        }
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => {
              setEditing(null);
              setCreating((v) => !v);
            }}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />
      <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
        <SearchField
          value={q}
          onChangeText={setQ}
          placeholder="Nomi yoki telefon…"
        />
      </View>
      {creating ? (
        <View style={{ paddingHorizontal: space.lg }}>
          <FormCard>
            <FieldLabel>Nomi *</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Kompaniya nomi"
              value={name}
              onChangeText={setName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Telefon</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="+998…"
              value={phone}
              onChangeText={setPhone}
              placeholderTextColor={colors.faint}
              keyboardType="phone-pad"
            />
            <PrimaryButton label="Saqlash" onPress={onCreate} />
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
            <EmptyState
              title="Kompaniya yo‘q"
              hint="Yangi kompaniya qo‘shing yoki qidiruvni o‘zgartiring"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={String(item.name)}
              meta={
                [
                  item.inn,
                  item.phone,
                  item.credit_limit != null ? `limit ${item.credit_limit}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"
              }
              badge={item.is_active === false ? "O‘chiq" : "Faol"}
              badgeTone={item.is_active === false ? "neutral" : "success"}
              leading={<AvatarMark label={String(item.name)} tone="muted" />}
              onPress={() => openEdit(item)}
            />
          )}
        />
      )}
    </View>
  );
}
