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
import { colors, fontUi, radius, space, ui } from "../ui/theme";

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
  email: string;
  nationality: string;
  is_vip: boolean;
  is_blacklisted: boolean;
  notes: string;
  documents: { id: number; doc_type: string; number: string }[];
  stays: {
    id: number;
    code: string;
    status: string;
    check_in: string;
    check_out: string;
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
          onBack={() => {
            setSelectedId(null);
            setDetail(null);
          }}
        />
        {detailBusy && !detail ? (
          <ActivityIndicator style={{ marginTop: 24 }} color={colors.accent} />
        ) : (
          <ScrollView contentContainerStyle={styles.detailPad}>
            {error ? <Text style={ui.error}>{error}</Text> : null}
            <TextInput
              style={ui.input}
              value={editFirst}
              onChangeText={setEditFirst}
              placeholder="Ism"
              placeholderTextColor={colors.faint}
            />
            <TextInput
              style={ui.input}
              value={editLast}
              onChangeText={setEditLast}
              placeholder="Familiya"
              placeholderTextColor={colors.faint}
            />
            <TextInput
              style={ui.input}
              value={editPhone}
              onChangeText={setEditPhone}
              placeholder="Telefon"
              keyboardType="phone-pad"
              placeholderTextColor={colors.faint}
            />
            <TextInput
              style={[ui.input, styles.notes]}
              value={editNotes}
              onChangeText={setEditNotes}
              placeholder="Izoh"
              multiline
              placeholderTextColor={colors.faint}
            />
            <Pressable
              style={[ui.primaryBtn, detailBusy && { opacity: 0.6 }]}
              onPress={saveGuest}
              disabled={detailBusy}
            >
              <Text style={ui.primaryBtnText}>Saqlash</Text>
            </Pressable>

            <Text style={styles.section}>Hujjatlar</Text>
            {(detail?.documents || []).map((d) => (
              <Text key={d.id} style={ui.rowMeta}>
                {d.doc_type}: {d.number}
              </Text>
            ))}
            {(detail?.documents || []).length === 0 ? (
              <Text style={ui.empty}>Hujjat yo‘q</Text>
            ) : null}
            <TextInput
              style={ui.input}
              value={docNumber}
              onChangeText={setDocNumber}
              placeholder="Passport / ID raqami"
              placeholderTextColor={colors.faint}
              autoCapitalize="characters"
            />
            <Pressable
              style={[ui.copperBtn, detailBusy && { opacity: 0.6 }]}
              onPress={addDoc}
              disabled={detailBusy}
            >
              <Text style={ui.copperBtnText}>Hujjat qo‘shish</Text>
            </Pressable>

            <Text style={styles.section}>Bronlar</Text>
            {(detail?.stays || []).map((r) => (
              <Pressable
                key={r.id}
                style={ui.rowItem}
                onPress={() => onOpenReservation(r.id)}
              >
                <Text style={ui.rowTitle}>
                  {r.code} · {r.status}
                </Text>
                <Text style={ui.rowMeta}>
                  {r.check_in} → {r.check_out}
                </Text>
              </Pressable>
            ))}
            {(detail?.stays || []).length === 0 ? (
              <Text style={ui.empty}>Bron yo‘q</Text>
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
        <TextInput
          style={styles.search}
          value={q}
          onChangeText={setQ}
          placeholder="Ism, telefon…"
          placeholderTextColor={colors.faint}
          autoCorrect={false}
        />
      </View>

      {showCreate ? (
        <View style={styles.create}>
          <TextInput
            style={ui.input}
            placeholder="Ism *"
            value={firstName}
            onChangeText={setFirstName}
            placeholderTextColor={colors.faint}
          />
          <TextInput
            style={ui.input}
            placeholder="Familiya"
            value={lastName}
            onChangeText={setLastName}
            placeholderTextColor={colors.faint}
          />
          <TextInput
            style={ui.input}
            placeholder="Telefon"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            placeholderTextColor={colors.faint}
          />
          <Pressable style={ui.primaryBtn} onPress={onCreate}>
            <Text style={ui.primaryBtnText}>Saqlash</Text>
          </Pressable>
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
          ListEmptyComponent={<Text style={ui.empty}>Topilmadi</Text>}
          renderItem={({ item }) => (
            <Pressable style={ui.rowItem} onPress={() => openGuest(item.id)}>
              <Text style={ui.rowTitle}>
                {item.name}
                {item.is_vip ? " · VIP" : ""}
                {item.is_blacklisted ? " · QORA" : ""}
              </Text>
              <Text style={ui.rowMeta}>{item.phone || "Telefon yo‘q"}</Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: { paddingHorizontal: space.lg, paddingTop: space.md },
  search: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    paddingHorizontal: space.lg,
    paddingVertical: 13,
    fontSize: 16,
    color: colors.ink,
    fontFamily: fontUi,
  },
  create: { paddingHorizontal: space.lg, marginTop: space.md },
  pad: { paddingHorizontal: space.lg },
  detailPad: {
    paddingHorizontal: space.lg,
    paddingBottom: space.xxl,
    gap: space.sm,
  },
  notes: { minHeight: 72, textAlignVertical: "top" },
  section: {
    marginTop: space.lg,
    marginBottom: space.xs,
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fontUi,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
});
