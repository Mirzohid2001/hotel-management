import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { colors, fontDisplay, fontUi, radius, space, type } from "../ui/theme";

export function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.hero}>
        <Text style={styles.brandMark}>RIVOJ</Text>
        <Text style={styles.brandSub}>Hotel operations</Text>
      </View>

      <View style={styles.sheet}>
        <Text style={type.eyebrowInk}>Kirish</Text>
        <Text style={styles.sheetTitle}>Hisobingizga kiring</Text>
        <Text style={styles.sheetHint}>Web bilan bir xil login</Text>

        <Text style={styles.label}>Login</Text>
        <TextInput
          style={styles.input}
          autoCapitalize="none"
          autoCorrect={false}
          value={username}
          onChangeText={setUsername}
          placeholder="username"
          placeholderTextColor={colors.faint}
        />

        <Text style={styles.label}>Parol</Text>
        <TextInput
          style={styles.input}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          placeholder="••••••••"
          placeholderTextColor={colors.faint}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          style={[styles.btn, busy && styles.btnDisabled]}
          onPress={onSubmit}
          disabled={busy}
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.btnText}>Davom etish</Text>
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.night,
  },
  hero: {
    flex: 1,
    justifyContent: "flex-end",
    paddingHorizontal: space.xxl,
    paddingBottom: space.xxl,
    backgroundColor: colors.night,
  },
  brandMark: {
    fontFamily: fontDisplay,
    fontSize: 48,
    fontWeight: "600",
    color: colors.white,
    letterSpacing: 2,
  },
  brandSub: {
    marginTop: 8,
    fontFamily: fontUi,
    fontSize: 15,
    color: colors.accentSoft,
    fontWeight: "500",
    letterSpacing: 0.4,
  },
  sheet: {
    backgroundColor: colors.paper,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    paddingHorizontal: space.xxl,
    paddingTop: space.xxl,
    paddingBottom: 48,
  },
  sheetTitle: {
    ...type.titleInk,
    marginTop: 8,
    marginBottom: 4,
  },
  sheetHint: {
    ...type.meta,
    marginBottom: space.xl,
  },
  label: {
    ...type.label,
    marginBottom: 6,
  },
  input: {
    borderBottomWidth: 1.5,
    borderBottomColor: colors.line,
    borderRadius: 0,
    paddingHorizontal: 0,
    paddingVertical: 12,
    marginBottom: space.lg,
    fontSize: 17,
    fontFamily: fontUi,
    fontWeight: "500",
    color: colors.ink,
    backgroundColor: "transparent",
  },
  error: {
    color: colors.danger,
    fontWeight: "600",
    marginBottom: space.md,
  },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: space.sm,
  },
  btnDisabled: { opacity: 0.7 },
  btnText: {
    color: colors.white,
    fontWeight: "700",
    fontSize: 16,
    fontFamily: fontUi,
  },
});
