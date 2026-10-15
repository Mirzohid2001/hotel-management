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
import { useI18n } from "../i18n";
import { FieldLabel, FormCard, PrimaryButton } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function ProfileScreen({ onBack }: Props) {
  const { me, updateProfile, refreshMe, uploadLogo, clearLogo, fetchLogo, deleteAccount } =
    useAuth();
  const { t, tr, lang, setLang } = useI18n();
  const [logoOn, setLogoOn] = useState(false);
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

  useEffect(() => {
    if (me?.role !== "admin") return;
    fetchLogo()
      .then((r) => setLogoOn(!!r.has_logo))
      .catch(() => undefined);
  }, [me?.role, fetchLogo]);

  async function pickLogo() {
    try {
      const ImagePicker = await import("expo-image-picker");
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert(t("logo"), "Rasmga ruxsat berilmagan");
        return;
      }
      const picked = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.7,
      });
      if (picked.canceled || !picked.assets?.[0]) return;
      const asset = picked.assets[0];
      setBusy(true);
      await uploadLogo(
        asset.uri,
        asset.fileName || "logo.jpg",
        asset.mimeType || "image/jpeg"
      );
      setLogoOn(true);
      Alert.alert(t("logo"), t("saved"));
    } catch (e) {
      Alert.alert(t("logo"), e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function onDeleteAccount() {
    Alert.alert(t("deleteAccount"), "Akkaunt o‘chiriladi va chiqasiz.", [
      { text: "Bekor", style: "cancel" },
      {
        text: t("deleteAccount"),
        style: "destructive",
        onPress: async () => {
          try {
            await deleteAccount();
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      },
    ]);
  }

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
        <FormCard>
          <FieldLabel>{t("language")}</FieldLabel>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Pressable
              style={[ui.chip, lang === "uz" && ui.chipOn]}
              onPress={() => setLang("uz")}
            >
              <Text style={[ui.chipText, lang === "uz" && ui.chipTextOn]}>
                {t("langUz")}
              </Text>
            </Pressable>
            <Pressable
              style={[ui.chip, lang === "ru" && ui.chipOn]}
              onPress={() => setLang("ru")}
            >
              <Text style={[ui.chipText, lang === "ru" && ui.chipTextOn]}>
                {t("langRu")}
              </Text>
            </Pressable>
          </View>
        </FormCard>
        {me?.role === "admin" ? (
          <FormCard>
            <FieldLabel>{t("logo")}</FieldLabel>
            <Text style={styles.meta}>
              {logoOn ? tr("Logo yuklangan") : tr("Bo‘sh bo‘lsa Rivoj logosi")}
            </Text>
            <PrimaryButton label={t("logo")} onPress={pickLogo} loading={busy} />
            {logoOn ? (
              <PrimaryButton
                label="Logo olib tashlash"
                tone="ghost"
                onPress={async () => {
                  setBusy(true);
                  try {
                    await clearLogo();
                    setLogoOn(false);
                  } catch (e) {
                    Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            ) : null}
          </FormCard>
        ) : null}
        <PrimaryButton
          label={t("deleteAccount")}
          tone="danger"
          onPress={onDeleteAccount}
        />
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
