import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

export function NightAuditScreen({ onBack }: Props) {
  const { fetchNightAudit, runNightAudit, me } = useAuth();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const canRun =
    me?.permissions?.audit === true ||
    ["admin", "manager", "accountant"].includes(me?.role || "");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchNightAudit());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchNightAudit]);

  useEffect(() => {
    load();
  }, [load]);

  async function run() {
    Alert.alert("Kun yopish", "Night audit ishga tushirilsinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "Ishga tushirish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          try {
            await runNightAudit();
            await load();
            Alert.alert("Tayyor", "Kun yopildi");
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  const blockers = (data?.blockers as unknown[]) || [];

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Audit"
        title="Kun yopish"
        subtitle={data ? String(data.day) : undefined}
        onBack={onBack}
      />
      {loading && !data ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
          }
        >
          <View style={ui.rowItem}>
            <Text style={ui.rowTitle}>
              {data?.already_run ? "Bugun yopilgan" : "Hali yopilmagan"}
            </Text>
            <Text style={ui.rowMeta}>{String(data?.hotel || "")}</Text>
          </View>
          <Text style={ui.section}>Bloklovchilar</Text>
          {blockers.length === 0 ? (
            <Text style={ui.empty}>Bloklovchi yo‘q</Text>
          ) : (
            blockers.map((b, i) => (
              <View key={i} style={ui.rowItem}>
                <Text style={ui.rowTitle}>
                  {typeof b === "object" && b && "message" in b
                    ? String((b as { message: string }).message)
                    : JSON.stringify(b)}
                </Text>
              </View>
            ))
          )}
          {canRun && !data?.already_run ? (
            <Pressable
              style={[ui.primaryBtn, { marginTop: space.lg }, busy && { opacity: 0.7 }]}
              onPress={run}
              disabled={busy}
            >
              <Text style={ui.primaryBtnText}>Night audit</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}
