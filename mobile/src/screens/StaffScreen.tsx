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
import {
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

type StaffRow = {
  id: number;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  properties: { id: number; name: string }[];
  all_properties?: boolean;
};

export function StaffScreen({ onBack }: Props) {
  const { fetchStaff, fetchStaffMeta, inviteStaff, updateStaff } = useAuth();
  const [items, setItems] = useState<StaffRow[]>([]);
  const [roles, setRoles] = useState<{ id: string; label: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("receptionist");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (isRefresh = false) => {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const [list, meta] = await Promise.all([fetchStaff(), fetchStaffMeta()]);
        setItems(list as StaffRow[]);
        setRoles(meta.roles || []);
        if (meta.roles?.[0] && !meta.roles.find((r) => r.id === role)) {
          setRole(meta.roles[0].id);
        }
      } catch (e) {
        Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchStaff, fetchStaffMeta, role]
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitInvite() {
    if (!username.trim() || password.length < 8) {
      Alert.alert("Xodim", "Login va parol (min 8) kiriting");
      return;
    }
    setBusy(true);
    try {
      await inviteStaff({
        username: username.trim(),
        password,
        role,
      });
      setUsername("");
      setPassword("");
      setCreating(false);
      await load(true);
      Alert.alert("Xodim", "Qo‘shildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function openMember(item: StaffRow) {
    const buttons: {
      text: string;
      style?: "cancel" | "destructive" | "default";
      onPress?: () => void;
    }[] = [{ text: "Yopish", style: "cancel" }];
    for (const r of roles) {
      if (r.id === item.role) continue;
      buttons.push({
        text: `Rol: ${r.label}`,
        onPress: async () => {
          try {
            await updateStaff(item.id, { role: r.id });
            await load(true);
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      });
    }
    buttons.push({
      text: item.is_active ? "Faolsizlantirish" : "Faollashtirish",
      style: item.is_active ? "destructive" : "default",
      onPress: async () => {
        try {
          await updateStaff(item.id, { is_active: !item.is_active });
          await load(true);
        } catch (e) {
          Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
        }
      },
    });
    Alert.alert(item.full_name || item.username, `Rol: ${item.role}`, buttons);
  }

  const roleLabel = (id: string) =>
    roles.find((r) => r.id === id)?.label || id;

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Admin"
        title="Staff"
        subtitle={`${items.length} a’zo · login va rollar`}
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => setCreating((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Taklif"}
            </Text>
          </Pressable>
        }
      />

      {creating ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
          <FieldLabel>Login</FieldLabel>
          <TextInput
            style={ui.input}
            placeholder="username"
            placeholderTextColor={colors.faint}
            autoCapitalize="none"
            value={username}
            onChangeText={setUsername}
          />
          <FieldLabel>Parol</FieldLabel>
          <TextInput
            style={ui.input}
            placeholder="Kamida 8 belgi"
            placeholderTextColor={colors.faint}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
          <FieldLabel>Rol</FieldLabel>
          <View style={styles.roleRow}>
            {roles.map((r) => (
              <Pressable
                key={r.id}
                style={[ui.chip, role === r.id && ui.chipOn]}
                onPress={() => setRole(r.id)}
              >
                <Text style={[ui.chipText, role === r.id && ui.chipTextOn]}>
                  {r.label}
                </Text>
              </Pressable>
            ))}
          </View>
          <PrimaryButton
            label="Xodimni qo‘shish"
            onPress={submitInvite}
            loading={busy}
          />
          </FormCard>
        </View>
      ) : null}

      {loading && items.length === 0 ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => String(t.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={
            <EmptyState title="Xodim yo‘q" hint="Yuqoridan taklif qiling" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={item.full_name || item.username}
              meta={`@${item.username} · ${roleLabel(item.role)}${
                item.all_properties
                  ? " · barcha filial"
                  : item.properties?.length
                    ? ` · ${item.properties.map((p) => p.name).join(", ")}`
                    : ""
              }`}
              badge={item.is_active ? "Faol" : "O‘chiq"}
              badgeTone={item.is_active ? "success" : "neutral"}
              leading={
                <AvatarMark
                  label={item.full_name || item.username}
                  tone={item.is_active ? "accent" : "muted"}
                />
              }
              onPress={() => openMember(item)}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  roleRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.sm,
    marginBottom: space.sm,
  },
});
