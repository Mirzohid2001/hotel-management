import { useState } from "react";
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
import { useAuth } from "../auth/AuthContext";

type RoomInfo = {
  id: number;
  number: string;
  room_type: string;
  status: string;
};

type Props = {
  room: RoomInfo;
  onBack: () => void;
  onCreated: (reservationId: number) => void;
};

export function WalkInScreen({ room, onBack, onCreated }: Props) {
  const { walkIn } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [nights, setNights] = useState("1");
  const [adults, setAdults] = useState("1");
  const [docNumber, setDocNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(force?: { allow_dirty?: boolean; allow_no_docs?: boolean }) {
    setError(null);
    setBusy(true);
    try {
      const result = await walkIn({
        room_id: room.id,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        nights: Math.max(1, parseInt(nights, 10) || 1),
        adults: Math.max(1, parseInt(adults, 10) || 1),
        doc_number: docNumber.trim(),
        allow_dirty: !!force?.allow_dirty || room.status === "dirty",
        allow_no_docs: !!force?.allow_no_docs || !docNumber.trim(),
        collect_emehmon: true,
      });
      Alert.alert("Joylashdi", `${result.code}`);
      onCreated(result.reservation_id);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Xato";
      if (/kir|dirty|tozala/i.test(msg)) {
        Alert.alert("Xona holati", msg, [
          { text: "Bekor", style: "cancel" },
          {
            text: "Baribir",
            onPress: () => submit({ allow_dirty: true }),
          },
        ]);
      } else {
        setError(msg);
      }
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
          <Text style={styles.back}>← Doska</Text>
        </Pressable>
        <Text style={styles.title}>Darhol joylash</Text>
        <Text style={styles.sub}>
          Xona {room.number}
          {room.room_type ? ` · ${room.room_type}` : ""}
        </Text>
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
          label="Kechalar"
          value={nights}
          onChange={setNights}
          keyboardType="number-pad"
        />
        <Field
          label="Kattalar"
          value={adults}
          onChange={setAdults}
          keyboardType="number-pad"
        />
        <Field
          label="Pasport/ID (ixtiyoriy)"
          value={docNumber}
          onChange={setDocNumber}
          autoCapitalize="characters"
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.btn, busy && styles.disabled]}
          onPress={() => submit()}
          disabled={busy || !firstName.trim()}
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnText}>Joylashtirish</Text>
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
