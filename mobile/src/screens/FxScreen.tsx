import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  StatsStrip,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };

const CURRENCIES = ["USD", "EUR", "RUB"] as const;

export function FxScreen({ onBack }: Props) {
  const { fetchFx, createFx, deleteFx, syncCbuFx } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [base, setBase] = useState("UZS");
  const [live, setLive] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [currency, setCurrency] = useState<string>("USD");
  const [rate, setRate] = useState("");
  const [effectiveOn, setEffectiveOn] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchFx();
      setItems(data.items || []);
      setBase(data.base_currency || "UZS");
      setLive(data.live || {});
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchFx]);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate() {
    if (!rate.trim()) {
      Alert.alert("Xato", "Kurs kerak");
      return;
    }
    setBusy(true);
    try {
      await createFx({
        currency,
        rate: rate.trim(),
        effective_on: effectiveOn.trim() || undefined,
      });
      setRate("");
      setEffectiveOn("");
      setCreating(false);
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function onSync() {
    setBusy(true);
    try {
      await syncCbuFx(true);
      await load();
      Alert.alert("OK", "CBU kurslari yangilandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function onDelete(id: number) {
    Alert.alert("O‘chirish", "Kurs o‘chirilsinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "O‘chirish",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteFx(id);
            await load();
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          }
        },
      },
    ]);
  }

  const liveItems = CURRENCIES.filter((c) => live[c] != null).map((c) => ({
    label: c,
    value: String(live[c]),
  }));

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Moliya"
        title="Kurslar (FX)"
        subtitle={`Baza: ${base}`}
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => setCreating((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />

      {liveItems.length ? (
        <View style={{ marginTop: space.sm }}>
          <StatsStrip items={liveItems} />
        </View>
      ) : null}

      <View
        style={{
          paddingHorizontal: space.lg,
          paddingTop: space.md,
          flexDirection: "row",
          gap: 8,
        }}
      >
        <View style={{ flex: 1 }}>
          <PrimaryButton
            label="CBU sync"
            onPress={onSync}
            loading={busy}
            tone="ghost"
          />
        </View>
      </View>

      {creating ? (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
          <FormCard>
            <FieldLabel>Valyuta</FieldLabel>
            <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
              {CURRENCIES.map((c) => (
                <Pressable
                  key={c}
                  style={[ui.chip, currency === c && ui.chipOn]}
                  onPress={() => setCurrency(c)}
                >
                  <Text
                    style={[ui.chipText, currency === c && ui.chipTextOn]}
                  >
                    {c}
                  </Text>
                </Pressable>
              ))}
            </View>
            <FieldLabel>{`Kurs (1 ${currency} → ${base})`}</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="12500"
              placeholderTextColor={colors.faint}
              keyboardType="decimal-pad"
              value={rate}
              onChangeText={setRate}
            />
            <FieldLabel>Sana (YYYY-MM-DD)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Bugun"
              placeholderTextColor={colors.faint}
              value={effectiveOn}
              onChangeText={setEffectiveOn}
              autoCapitalize="none"
            />
            <PrimaryButton label="Saqlash" onPress={onCreate} loading={busy} />
          </FormCard>
        </View>
      ) : null}

      {loading && !items.length ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Kurs yo‘q" hint="CBU sync yoki qo‘lda qo‘shing" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={`${String(item.currency)} · ${String(item.rate)}`}
              meta={`${String(item.effective_on)} · ${String(item.base_currency || base)}${
                item.note ? ` · ${item.note}` : ""
              }`}
              badge={String(item.currency)}
              badgeTone="accent"
            >
              <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
                <Pressable
                  style={ui.chip}
                  onPress={() => onDelete(Number(item.id))}
                >
                  <Text style={ui.chipText}>O‘chirish</Text>
                </Pressable>
              </View>
            </ListCard>
          )}
        />
      )}
    </View>
  );
}
