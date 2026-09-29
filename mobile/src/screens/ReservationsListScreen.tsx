import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { ReservationSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  SearchField,
  StatsStrip,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation: (id: number) => void;
};

type StatusOpt = { id: string; label: string };

function monthBounds(d = new Date()): { from: string; to: string } {
  const y = d.getFullYear();
  const m = d.getMonth();
  const pad = (n: number) => String(n).padStart(2, "0");
  const last = new Date(y, m + 1, 0).getDate();
  return {
    from: `${y}-${pad(m + 1)}-01`,
    to: `${y}-${pad(m + 1)}-${pad(last)}`,
  };
}

export function ReservationsListScreen({ onBack, onOpenReservation }: Props) {
  const { fetchReservationsList } = useAuth();
  const bounds = monthBounds();
  const [dateFrom, setDateFrom] = useState(bounds.from);
  const [dateTo, setDateTo] = useState(bounds.to);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ReservationSummary[]>([]);
  const [statuses, setStatuses] = useState<StatusOpt[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const data = await fetchReservationsList({
          date_from: dateFrom,
          date_to: dateTo,
          status: status || undefined,
          q: q.trim() || undefined,
        });
        setItems(data.items);
        setStatuses(data.statuses || []);
        setMeta(data as unknown as Record<string, unknown>);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchReservationsList, dateFrom, dateTo, status, q]
  );

  useEffect(() => {
    const t = setTimeout(() => load(), q ? 280 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Reseption"
        title="Bronlar"
        subtitle={`${meta.filter_count ?? "—"} ta · jami ${meta.booking_total ?? "—"}`}
        onBack={onBack}
      />

      <View style={styles.pad}>
        <FormCard>
          <SearchField
            value={q}
            onChangeText={setQ}
            placeholder="Kod, mehmon, xona…"
          />
          <View style={styles.row}>
            <View style={styles.half}>
              <FieldLabel>Dan</FieldLabel>
              <TextInput
                style={ui.input}
                value={dateFrom}
                onChangeText={setDateFrom}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={colors.faint}
                autoCapitalize="none"
              />
            </View>
            <View style={styles.half}>
              <FieldLabel>Gacha</FieldLabel>
              <TextInput
                style={ui.input}
                value={dateTo}
                onChangeText={setDateTo}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={colors.faint}
                autoCapitalize="none"
              />
            </View>
          </View>
          <View style={styles.chips}>
            <Pressable
              style={[ui.chip, !status && ui.chipOn]}
              onPress={() => setStatus("")}
            >
              <Text style={[ui.chipText, !status && ui.chipTextOn]}>Hammasi</Text>
            </Pressable>
            {statuses.map((s) => {
              const on = status === s.id;
              return (
                <Pressable
                  key={s.id}
                  style={[ui.chip, on && ui.chipOn]}
                  onPress={() => setStatus(s.id)}
                >
                  <Text style={[ui.chipText, on && ui.chipTextOn]}>{s.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </FormCard>
      </View>

      <StatsStrip
        items={[
          { label: "In-house", value: String(meta.checked_in_count ?? "—") },
          { label: "Tasdiq", value: String(meta.confirmed_count ?? "—") },
          { label: "Kelish", value: String(meta.arrivals_today ?? "—") },
        ]}
      />

      {error ? <Text style={[ui.error, { padding: space.lg }]}>{error}</Text> : null}
      {loading && !items.length ? (
        <ActivityIndicator style={{ marginTop: 32 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(it) => String(it.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Bron yo‘q" hint="Sana yoki statusni o‘zgartiring" />
          }
          renderItem={({ item }) => (
            <ListCard
              title={`${item.room?.number ? `#${item.room.number}` : "—"} · ${item.guest?.name || "Mehmon"}`}
              meta={`${item.code} · ${item.check_in} → ${item.check_out}`}
              badge={item.status}
              badgeTone={
                item.status === "checked_in"
                  ? "accent"
                  : item.status === "confirmed"
                    ? "info"
                    : "neutral"
              }
              onPress={() => onOpenReservation(item.id)}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { paddingHorizontal: space.lg, paddingTop: space.md },
  row: { flexDirection: "row", gap: space.sm },
  half: { flex: 1 },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: space.sm,
  },
});
