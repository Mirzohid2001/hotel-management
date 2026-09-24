import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { AvailableRoom } from "../api/types";
import { useAuth } from "../auth/AuthContext";

type Props = {
  onBack: () => void;
  onCreated: (reservationId: number) => void;
};

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function BookingScreen({ onBack, onCreated }: Props) {
  const { createReservation, fetchAvailableRooms } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [checkIn, setCheckIn] = useState(isoToday());
  const [checkOut, setCheckOut] = useState(isoPlus(1));
  const [adults, setAdults] = useState("1");
  const [rooms, setRooms] = useState<AvailableRoom[]>([]);
  const [roomId, setRoomId] = useState<number | null>(null);
  const [loadingRooms, setLoadingRooms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nights = useMemo(() => {
    try {
      const a = new Date(checkIn + "T12:00:00");
      const b = new Date(checkOut + "T12:00:00");
      const n = Math.round((b.getTime() - a.getTime()) / 86400000);
      return n > 0 ? n : 0;
    } catch {
      return 0;
    }
  }, [checkIn, checkOut]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (nights < 1) {
        setRooms([]);
        setRoomId(null);
        return;
      }
      setLoadingRooms(true);
      setError(null);
      try {
        const items = await fetchAvailableRooms(checkIn, checkOut);
        if (!cancelled) {
          setRooms(items);
          setRoomId((prev) =>
            prev && items.some((r) => r.id === prev) ? prev : items[0]?.id ?? null
          );
        }
      } catch (e) {
        if (!cancelled) {
          setRooms([]);
          setRoomId(null);
          setError(e instanceof ApiError ? e.message : "Xonalar yuklanmadi");
        }
      } finally {
        if (!cancelled) setLoadingRooms(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [checkIn, checkOut, nights, fetchAvailableRooms]);

  async function submit() {
    if (!firstName.trim() || !roomId || nights < 1) {
      setError("Ism, sanalar va xona kerak.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createReservation({
        room_id: roomId,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        check_in: checkIn,
        check_out: checkOut,
        adults: Math.max(1, parseInt(adults, 10) || 1),
      });
      Alert.alert("Bron", result.code);
      onCreated(result.reservation_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Bron xatosi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.header}>
        <Pressable onPress={onBack}>
          <Text style={styles.back}>← Orqaga</Text>
        </Pressable>
        <Text style={styles.title}>Yangi bron</Text>
        <Text style={styles.sub}>{nights > 0 ? `${nights} kecha` : "Sanalarni tekshiring"}</Text>
      </View>

      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <Field label="Ism *" value={firstName} onChange={setFirstName} />
        <Field label="Familiya" value={lastName} onChange={setLastName} />
        <Field
          label="Telefon"
          value={phone}
          onChange={setPhone}
          keyboardType="phone-pad"
        />
        <Field
          label="Kirish (YYYY-MM-DD)"
          value={checkIn}
          onChange={setCheckIn}
          autoCapitalize="none"
        />
        <Field
          label="Chiqish (YYYY-MM-DD)"
          value={checkOut}
          onChange={setCheckOut}
          autoCapitalize="none"
        />
        <Field
          label="Kattalar"
          value={adults}
          onChange={setAdults}
          keyboardType="number-pad"
        />

        <Text style={styles.section}>Bo‘sh xonalar</Text>
        {loadingRooms ? (
          <ActivityIndicator color="#0e6b56" style={{ marginVertical: 12 }} />
        ) : rooms.length === 0 ? (
          <Text style={styles.empty}>Shu sanalarda bo‘sh xona yo‘q</Text>
        ) : (
          rooms.map((r) => (
            <Pressable
              key={r.id}
              style={[styles.roomRow, roomId === r.id && styles.roomRowOn]}
              onPress={() => setRoomId(r.id)}
            >
              <Text
                style={[styles.roomNum, roomId === r.id && styles.roomTextOn]}
              >
                {r.number}
              </Text>
              <Text
                style={[styles.roomMeta, roomId === r.id && styles.roomTextOn]}
              >
                {r.room_type || r.status}
                {r.base_price ? ` · ${r.base_price}` : ""}
              </Text>
            </Pressable>
          ))
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.btn, (busy || !roomId || !firstName.trim()) && styles.disabled]}
          onPress={submit}
          disabled={busy || !roomId || !firstName.trim()}
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnText}>Bron yaratish</Text>
          )}
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Field({
  label,
  value,
  onChange,
  keyboardType,
  autoCapitalize,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  keyboardType?: "default" | "phone-pad" | "number-pad";
  autoCapitalize?: "none" | "characters" | "words";
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize || "words"}
        placeholderTextColor="#a89f94"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#eef0f3" },
  header: {
    backgroundColor: "#12151a",
    paddingTop: 56,
    paddingBottom: 18,
    paddingHorizontal: 18,
  },
  back: { color: "#e8a86a", fontWeight: "600", marginBottom: 10 },
  title: { color: "#fff", fontSize: 24, fontWeight: "700" },
  sub: { color: "rgba(245,239,230,0.75)", marginTop: 4 },
  body: { padding: 18, paddingBottom: 40 },
  field: { marginBottom: 12 },
  label: { fontSize: 12, fontWeight: "600", color: "#7a7168", marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: "#d9cfc3",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    color: "#12151a",
    backgroundColor: "#fff",
  },
  section: {
    marginTop: 8,
    marginBottom: 8,
    fontWeight: "700",
    color: "#12151a",
    fontSize: 15,
  },
  empty: { color: "#7a7168", marginBottom: 12 },
  roomRow: {
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#d9cfc3",
    padding: 12,
    marginBottom: 8,
  },
  roomRowOn: { backgroundColor: "#12151a", borderColor: "#12151a" },
  roomNum: { fontSize: 18, fontWeight: "700", color: "#12151a" },
  roomMeta: { marginTop: 2, color: "#7a7168", fontSize: 13 },
  roomTextOn: { color: "#fff" },
  error: { color: "#9f2f28", marginBottom: 10 },
  btn: {
    marginTop: 8,
    backgroundColor: "#0e6b56",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  disabled: { opacity: 0.7 },
});
