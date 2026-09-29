import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { GuestSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SearchField,
  StatusBadge,
} from "../ui/primitives";
import { colors, fontUi, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation: (id: number) => void;
};

type GuestDetail = {
  id: number;
  first_name: string;
  last_name: string;
  name: string;
  phone: string;
  email?: string;
  nationality?: string;
  notes?: string;
  is_vip: boolean;
  is_blacklisted: boolean;
  blacklist_reason?: string;
  documents?: { id: number; doc_type: string; number: string }[];
  stays?: {
    id: number;
    code: string;
    status: string;
    check_in: string;
    check_out: string;
    room?: { number: string };
  }[];
};

export function GuestsScreen({ onBack, onOpenReservation }: Props) {
  const { searchGuests, createGuest, fetchGuest, updateGuest, addGuestDocument } =
    useAuth();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<GuestSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<GuestDetail | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [editFirst, setEditFirst] = useState("");
  const [editLast, setEditLast] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editVip, setEditVip] = useState(false);
  const [editBlacklist, setEditBlacklist] = useState(false);
  const [editBlackReason, setEditBlackReason] = useState("");
  const [docNumber, setDocNumber] = useState("");

  useEffect(() => {
    let cancelled = false;
    const query = q.trim();
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const rows = await searchGuests(query);
        if (!cancelled) {
          setItems(rows);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Xato");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, query ? 250 : 0);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, searchGuests]);

  async function openGuest(id: number) {
    setSelectedId(id);
    setDetailBusy(true);
    setError(null);
    try {
      const raw = await fetchGuest(id);
      const d = raw as unknown as GuestDetail;
      setDetail(d);
      setEditFirst(d.first_name || "");
      setEditLast(d.last_name || "");
      setEditPhone(d.phone || "");
      setEditNotes(d.notes || "");
      setEditVip(!!d.is_vip);
      setEditBlacklist(!!d.is_blacklisted);
      setEditBlackReason(d.blacklist_reason || "");
      setDocNumber("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      setSelectedId(null);
    } finally {
      setDetailBusy(false);
    }
  }

  async function saveGuest() {
    if (!selectedId) return;
    if (!editFirst.trim()) {
      setError("Ism kerak");
      return;
    }
    setDetailBusy(true);
    setError(null);
    try {
      const raw = await updateGuest(selectedId, {
        first_name: editFirst.trim(),
        last_name: editLast.trim(),
        phone: editPhone.trim(),
        notes: editNotes.trim(),
        is_vip: editVip,
        is_blacklisted: editBlacklist,
        blacklist_reason: editBlacklist ? editBlackReason.trim() : "",
      });
      const d = raw as unknown as GuestDetail;
      setDetail(d);
      Alert.alert("Mehmon", "Saqlandi");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Saqlash xatosi");
    } finally {
      setDetailBusy(false);
    }
  }

  async function addDoc() {
    if (!selectedId || !docNumber.trim()) {
      setError("Hujjat raqami kerak");
      return;
    }
    setDetailBusy(true);
    setError(null);
    try {
      await addGuestDocument(selectedId, {
        number: docNumber.trim(),
        doc_type: "passport",
      });
      setDocNumber("");
      await openGuest(selectedId);
      Alert.alert("Hujjat", "Qo‘shildi");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Hujjat xatosi");
      setDetailBusy(false);
    }
  }

  async function onCreate() {
    if (!firstName.trim()) {
      setError("Ism kerak");
      return;
    }
    try {
      const g = await createGuest({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
      });
      setShowCreate(false);
      setFirstName("");
      setLastName("");
      setPhone("");
      setQ(g.first_name);
      openGuest(g.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yaratib bo‘lmadi");
    }
  }

  if (selectedId) {
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow="Mehmon"
          title={detail?.name || "Yuklanmoqda…"}
          subtitle={detail?.phone || undefined}
          onBack={() => {
            setSelectedId(null);
            setDetail(null);
          }}
          right={
            detail ? (
              <View style={styles.badgeRow}>
                {detail.is_vip ? (
                  <StatusBadge label="VIP" tone="accent" />
                ) : null}
                {detail.is_blacklisted ? (
                  <StatusBadge label="QORA" tone="danger" />
                ) : null}
              </View>
            ) : undefined
          }
        />
        {detailBusy && !detail ? (
          <ActivityIndicator style={{ marginTop: 24 }} color={colors.accent} />
        ) : (
          <ScrollView contentContainerStyle={styles.detailPad}>
            {error ? <Text style={ui.error}>{error}</Text> : null}

            <FormCard>
              <FieldLabel>Ism *</FieldLabel>
              <TextInput
                style={ui.input}
                value={editFirst}
                onChangeText={setEditFirst}
                placeholder="Ism"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Familiya</FieldLabel>
              <TextInput
                style={ui.input}
                value={editLast}
                onChangeText={setEditLast}
                placeholder="Familiya"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Telefon</FieldLabel>
              <TextInput
                style={ui.input}
                value={editPhone}
                onChangeText={setEditPhone}
                placeholder="Telefon"
                keyboardType="phone-pad"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Izoh</FieldLabel>
              <TextInput
                style={[ui.input, styles.notes]}
                value={editNotes}
                onChangeText={setEditNotes}
                placeholder="Izoh"
                multiline
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Belgilar</FieldLabel>
              <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                <Pressable
                  style={[ui.chip, editVip && ui.chipOn]}
                  onPress={() => setEditVip((v) => !v)}
                >
                  <Text style={[ui.chipText, editVip && ui.chipTextOn]}>VIP</Text>
                </Pressable>
                <Pressable
                  style={[ui.chip, editBlacklist && ui.chipOn]}
                  onPress={() => setEditBlacklist((v) => !v)}
                >
                  <Text style={[ui.chipText, editBlacklist && ui.chipTextOn]}>
                    Qora ro‘yxat
                  </Text>
                </Pressable>
              </View>
              {editBlacklist ? (
                <>
                  <FieldLabel>Sabab</FieldLabel>
                  <TextInput
                    style={ui.input}
                    value={editBlackReason}
                    onChangeText={setEditBlackReason}
                    placeholder="Sabab"
                    placeholderTextColor={colors.faint}
                  />
                </>
              ) : null}
              <PrimaryButton
                label="Saqlash"
                onPress={saveGuest}
                loading={detailBusy}
              />
            </FormCard>

            <FormCard>
              <Text style={styles.section}>Hujjatlar</Text>
              {(detail?.documents || []).map((d) => (
                <Text key={d.id} style={styles.docLine}>
                  {d.doc_type}: {d.number}
                </Text>
              ))}
              {(detail?.documents || []).length === 0 ? (
                <Text style={styles.muted}>Hujjat yo‘q</Text>
              ) : null}
              <FieldLabel>Passport / ID raqami</FieldLabel>
              <TextInput
                style={ui.input}
                value={docNumber}
                onChangeText={setDocNumber}
                placeholder="Raqam"
                placeholderTextColor={colors.faint}
                autoCapitalize="characters"
              />
              <PrimaryButton
                label="Hujjat qo‘shish"
                tone="copper"
                onPress={addDoc}
                loading={detailBusy}
              />
            </FormCard>

            <Text style={styles.section}>Bronlar</Text>
            {(detail?.stays || []).map((r) => (
              <ListCard
                key={r.id}
                title={`${r.code} · ${r.status}`}
                meta={`${r.check_in} → ${r.check_out}`}
                onPress={() => onOpenReservation(r.id)}
              />
            ))}
            {(detail?.stays || []).length === 0 ? (
              <EmptyState title="Bron yo‘q" />
            ) : null}
          </ScrollView>
        )}
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Mehmonlar"
        title="Qidiruv"
        onBack={onBack}
        right={
          <Pressable
            style={ui.copperBtn}
            onPress={() => setShowCreate((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {showCreate ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />

      <View style={styles.searchWrap}>
        <SearchField
          value={q}
          onChangeText={setQ}
          placeholder="Ism, telefon…"
        />
      </View>

      {showCreate ? (
        <View style={styles.createWrap}>
          <FormCard>
            <FieldLabel>Ism *</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Ism"
              value={firstName}
              onChangeText={setFirstName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Familiya</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Familiya"
              value={lastName}
              onChangeText={setLastName}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>Telefon</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Telefon"
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
              placeholderTextColor={colors.faint}
            />
            <PrimaryButton label="Saqlash" onPress={onCreate} />
          </FormCard>
        </View>
      ) : null}

      {error ? <Text style={[ui.error, styles.pad]}>{error}</Text> : null}
      {loading ? (
        <ActivityIndicator style={{ marginTop: 24 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(g) => String(g.id)}
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={
            <EmptyState title="Topilmadi" hint="Ism yoki telefon bilan qidiring" />
          }
          renderItem={({ item }) => {
            const badge = item.is_blacklisted
              ? "QORA"
              : item.is_vip
                ? "VIP"
                : undefined;
            const badgeTone = item.is_blacklisted
              ? "danger"
              : item.is_vip
                ? "accent"
                : undefined;
            return (
              <ListCard
                title={item.name}
                meta={item.phone || "Telefon yo‘q"}
                badge={badge}
                badgeTone={badgeTone}
                leading={
                  <AvatarMark
                    label={item.name}
                    tone={item.is_blacklisted ? "danger" : "accent"}
                  />
                }
                onPress={() => openGuest(item.id)}
              />
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: { paddingHorizontal: space.lg, paddingTop: space.md },
  createWrap: { paddingHorizontal: space.lg, marginTop: space.sm },
  pad: { paddingHorizontal: space.lg },
  detailPad: {
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    paddingBottom: space.xxl,
  },
  notes: { minHeight: 72, textAlignVertical: "top" },
  section: {
    marginBottom: space.sm,
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fontUi,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  docLine: {
    ...ui.rowMeta,
    marginBottom: 4,
  },
  muted: {
    color: colors.muted,
    fontFamily: fontUi,
    marginBottom: space.sm,
  },
  badgeRow: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
});
