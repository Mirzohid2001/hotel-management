import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FieldLabel, FormCard, PrimaryButton } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function ProfileScreen({ onBack }: Props) {
  const { me, updateProfile, refreshMe } = useAuth();
  const [first, setFirst] = useState(me?.user.first_name || "");
  const [last, setLast] = useState(me?.user.last_name || "");
  const [email, setEmail] = useState(me?.user.email || "");
  const [phone, setPhone] = useState(me?.user.phone || "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFirst(me?.user.first_name || "");
    setLast(me?.user.last_name || "");
    setEmail(me?.user.email || "");
    setPhone(me?.user.phone || "");
  }, [me]);

  async function onSave() {
    setBusy(true);
    try {
      await updateProfile({
        first_name: first.trim(),
        last_name: last.trim(),
        email: email.trim(),
        phone: phone.trim(),
        ...(password.trim() ? { new_password: password.trim() } : {}),
      });
      setPassword("");
      if (refreshMe) await refreshMe();
      Alert.alert("Profil", "Saqlandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Hisob"
        title="Profil"
        subtitle={me?.user.username}
        onBack={onBack}
      />
      <ScrollView contentContainerStyle={styles.body}>
        <FormCard>
          <FieldLabel>Ism</FieldLabel>
          <TextInput
            style={ui.input}
            value={first}
            onChangeText={setFirst}
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Familiya</FieldLabel>
          <TextInput
            style={ui.input}
            value={last}
            onChangeText={setLast}
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Email</FieldLabel>
          <TextInput
            style={ui.input}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Telefon</FieldLabel>
          <TextInput
            style={ui.input}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Yangi parol (ixtiyoriy)</FieldLabel>
          <TextInput
            style={ui.input}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="••••••"
            placeholderTextColor={colors.faint}
          />
          <PrimaryButton label="Saqlash" onPress={onSave} loading={busy} />
        </FormCard>
        <Text style={styles.meta}>
          Rol: {me?.role} · {me?.tenant.name}
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: space.lg, paddingBottom: 48 },
  meta: { ...ui.rowMeta, marginTop: space.md },
});
