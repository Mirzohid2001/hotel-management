import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { ReservationSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation: (id: number) => void;
};

export function InquiriesScreen({ onBack, onOpenReservation }: Props) {
  const { fetchInquiries, confirmInquiry } = useAuth();
  const [items, setItems] = useState<ReservationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setItems(await fetchInquiries());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchInquiries]
  );

  useEffect(() => {
    load();
  }, [load]);

  async function confirm(id: number) {
    setBusyId(id);
    try {
      await confirmInquiry(id);
      await load(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Tasdiqlash xatosi");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Front desk"
        title="So‘rovlar"
        subtitle={items.length ? `${items.length} ta` : undefined}
        onBack={onBack}
      />
      {error ? (
        <Text style={[ui.error, { padding: space.lg }]}>{error}</Text>
      ) : null}
      {loading && !items.length ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={<Text style={ui.empty}>So‘rov yo‘q</Text>}
          renderItem={({ item }) => (
            <View style={ui.rowItem}>
              <Pressable onPress={() => onOpenReservation(item.id)}>
                <Text style={styles.code}>{item.code}</Text>
                <Text style={ui.rowTitle}>{item.guest.name || "—"}</Text>
                <Text style={ui.rowMeta}>
                  {item.room.number || "—"} · {item.check_in} → {item.check_out}
                </Text>
              </Pressable>
              <Pressable
                style={[ui.primaryBtn, { marginTop: space.md }]}
                onPress={() => confirm(item.id)}
                disabled={busyId === item.id}
              >
                {busyId === item.id ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={ui.primaryBtnText}>Tasdiqlash</Text>
                )}
              </Pressable>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  code: {
    fontWeight: "700",
    color: colors.muted,
    fontSize: 12,
    marginBottom: 4,
    letterSpacing: 0.4,
  },
});
