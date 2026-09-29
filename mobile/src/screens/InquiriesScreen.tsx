import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { ReservationSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  AvatarMark,
  EmptyState,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
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
        subtitle={
          items.length
            ? `${items.length} ta so‘rov · tasdiqlash kutmoqda`
            : "Tasdiqlash kutayotgan bronlar"
        }
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
          ListEmptyComponent={
            <EmptyState
              title="So‘rov yo‘q"
              hint="Yangi inquiry kelganda shu yerda ko‘rinadi"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={item.guest.name || "—"}
              meta={`${item.code} · ${item.room.number || "—"} · ${item.check_in} → ${item.check_out}`}
              badge="Inquiry"
              badgeTone="warn"
              leading={<AvatarMark label={item.guest.name || item.code} />}
              onPress={() => onOpenReservation(item.id)}
            >
              <PrimaryButton
                label="Tasdiqlash"
                onPress={() => confirm(item.id)}
                loading={busyId === item.id}
                disabled={busyId === item.id}
              />
            </ListCard>
          )}
        />
      )}
    </View>
  );
}
