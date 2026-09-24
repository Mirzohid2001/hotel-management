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
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function CompaniesScreen({ onBack }: Props) {
  const { fetchCompanies, createCompany } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

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

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="CRM"
        title="Kompaniyalar"
        onBack={onBack}
        right={
          <Pressable style={ui.copperBtn} onPress={() => setCreating((v) => !v)}>
            <Text style={ui.copperBtnText}>{creating ? "Yopish" : "+ Yangi"}</Text>
          </Pressable>
        }
      />
      <View style={styles.pad}>
        <TextInput
          style={ui.input}
          placeholder="Qidiruv…"
          placeholderTextColor={colors.faint}
          value={q}
          onChangeText={setQ}
        />
      </View>
      {creating ? (
        <View style={styles.pad}>
          <TextInput
            style={ui.input}
            placeholder="Nomi *"
            value={name}
            onChangeText={setName}
            placeholderTextColor={colors.faint}
          />
          <TextInput
            style={ui.input}
            placeholder="Telefon"
            value={phone}
            onChangeText={setPhone}
            placeholderTextColor={colors.faint}
          />
          <Pressable style={ui.primaryBtn} onPress={onCreate}>
            <Text style={ui.primaryBtnText}>Saqlash</Text>
          </Pressable>
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
            <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
          }
          ListEmptyComponent={<Text style={ui.empty}>Kompaniya yo‘q</Text>}
          renderItem={({ item }) => (
            <View style={ui.rowItem}>
              <Text style={ui.rowTitle}>{String(item.name)}</Text>
              <Text style={ui.rowMeta}>
                {[item.inn, item.phone].filter(Boolean).join(" · ") || "—"}
              </Text>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md },
});
