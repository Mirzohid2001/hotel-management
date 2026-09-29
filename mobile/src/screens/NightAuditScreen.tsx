import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ActionCard, ListCard, StatusBadge } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function NightAuditScreen({ onBack }: Props) {
  const { fetchNightAudit, runNightAudit, me } = useAuth();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [day, setDay] = useState(isoToday());
  const [draft, setDraft] = useState(isoToday());

  const canRun =
    me?.permissions?.audit === true ||
    ["admin", "manager", "accountant"].includes(me?.role || "");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchNightAudit(day));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchNightAudit, day]);

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
            await runNightAudit(day);
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
  const alreadyRun = Boolean(data?.already_run);

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Audit"
        title="Kun yopish"
        subtitle={
          data
            ? `${String(data.day)} · ${String(data.hotel || "")}`
            : "Night audit holati"
        }
        onBack={onBack}
      />
      {loading && !data ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={colors.accent}
            />
          }
          showsVerticalScrollIndicator={false}
        >
          <View style={{ flexDirection: "row", gap: 8, marginBottom: space.md }}>
            <TextInput
              style={[ui.input, { flex: 1, marginBottom: 0 }]}
              value={draft}
              onChangeText={setDraft}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.faint}
              autoCapitalize="none"
              onSubmitEditing={() => {
                if (/^\d{4}-\d{2}-\d{2}$/.test(draft.trim())) setDay(draft.trim());
                else Alert.alert("Sana", "YYYY-MM-DD kiriting");
              }}
            />
            <Pressable
              style={ui.chip}
              onPress={() => {
                const next = isoToday();
                setDraft(next);
                setDay(next);
              }}
            >
              <Text style={ui.chipText}>Bugun</Text>
            </Pressable>
            <Pressable
              style={[ui.chip, day === draft.trim() && ui.chipOn]}
              onPress={() => {
                if (/^\d{4}-\d{2}-\d{2}$/.test(draft.trim())) setDay(draft.trim());
                else Alert.alert("Sana", "YYYY-MM-DD kiriting");
              }}
            >
              <Text style={[ui.chipText, day === draft.trim() && ui.chipTextOn]}>
                Ochish
              </Text>
            </Pressable>
          </View>
          <ListCard
            title={alreadyRun ? "Shu kun yopilgan" : "Hali yopilmagan"}
            meta={String(data?.hotel || "")}
            badge={alreadyRun ? "Yopiq" : "Ochiq"}
            badgeTone={alreadyRun ? "success" : "warn"}
          >
            <View style={{ marginTop: space.sm }}>
              <StatusBadge
                label={alreadyRun ? "Audit bajarilgan" : "Audit kutilmoqda"}
                tone={alreadyRun ? "success" : "info"}
              />
            </View>
          </ListCard>

          <View style={{ marginTop: space.md, marginBottom: space.sm }}>
            {blockers.length === 0 ? (
              <ListCard
                title="Bloklovchi yo‘q"
                meta="Kunni yopish mumkin"
                badge="OK"
                badgeTone="success"
              />
            ) : (
              blockers.map((b, i) => (
                <ListCard
                  key={i}
                  title={
                    typeof b === "object" && b && "message" in b
                      ? String((b as { message: string }).message)
                      : JSON.stringify(b)
                  }
                  badge="Blok"
                  badgeTone="danger"
                />
              ))
            )}
          </View>

          {canRun && !alreadyRun ? (
            <ActionCard
              title="Night audit"
              hint="Kunni yopish va kunlik hisobotni yozish"
              cta="Ishga tushirish"
              onPress={run}
              busy={busy}
              tone="night"
            />
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}
