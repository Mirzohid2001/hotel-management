import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
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
import {
  EmptyState,
  SearchField,
  StatsStrip,
  StatusBadge,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  colors,
  fontDisplay,
  fontUi,
  radius,
  space,
  ui,
} from "../ui/theme";

type Segment = "arrivals" | "departures" | "in_house";

type Props = {
  onOpenReservation: (id: number) => void;
  reloadToken?: number;
  onHotelChanged?: () => void;
};

const SEGMENTS: { id: Segment; label: string }[] = [
  { id: "arrivals", label: "Kirish" },
  { id: "departures", label: "Chiqish" },
  { id: "in_house", label: "Joylashgan" },
];

const STATUS_LABEL: Record<string, string> = {
  confirmed: "Tasdiqlangan",
  checked_in: "Joylashgan",
  checked_out: "Chiqqan",
  cancelled: "Bekor",
  no_show: "Kelmagan",
  inquiry: "So‘rov",
};

function statusTone(
  status: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  if (status === "checked_in") return "success";
  if (status === "confirmed") return "accent";
  if (status === "cancelled" || status === "no_show") return "danger";
  if (status === "inquiry") return "warn";
  return "neutral";
}

export function TodayScreen({
  onOpenReservation,
  reloadToken = 0,
  onHotelChanged,
}: Props) {
  const { me, logout, fetchToday, searchReservations, setHotel } = useAuth();
  const [segment, setSegment] = useState<Segment>("arrivals");
  const [arrivals, setArrivals] = useState<ReservationSummary[]>([]);
  const [departures, setDepartures] = useState<ReservationSummary[]>([]);
  const [inHouse, setInHouse] = useState<ReservationSummary[]>([]);
  const [counts, setCounts] = useState({
    arrivals: 0,
    departures: 0,
    in_house: 0,
  });
  const [day, setDay] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [searchHits, setSearchHits] = useState<ReservationSummary[] | null>(
    null
  );
  const [searching, setSearching] = useState(false);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const data = await fetchToday();
        setArrivals(data.arrivals);
        setDepartures(data.departures);
        setInHouse(data.in_house);
        setCounts(data.counts);
        setDay(data.day);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchToday]
  );

  useEffect(() => {
    load();
  }, [load, reloadToken]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setSearchHits(null);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const items = await searchReservations(q);
        if (!cancelled) setSearchHits(items);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Qidiruv xatosi");
          setSearchHits([]);
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query, searchReservations]);

  const list =
    searchHits != null
      ? searchHits
      : segment === "arrivals"
        ? arrivals
        : segment === "departures"
          ? departures
          : inHouse;

  function pickHotel() {
    const hotels = me?.hotels || [];
    if (hotels.length < 2) return;
    Alert.alert(
      "Filial",
      "Qaysi mehmonxona?",
      [
        ...hotels.map((h) => ({
          text: h.name + (h.id === me?.hotel?.id ? " ✓" : ""),
          onPress: async () => {
            try {
              await setHotel(h.id);
              onHotelChanged?.();
              await load(true);
            } catch (e) {
              Alert.alert(
                "Filial",
                e instanceof ApiError ? e.message : "Almashtirish xatosi"
              );
            }
          },
        })),
        { text: "Bekor", style: "cancel" as const },
      ]
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Bugun"
        title={me?.hotel?.name || me?.tenant.name || "Hotel"}
        subtitle={day || undefined}
        onTitlePress={(me?.hotels?.length || 0) > 1 ? pickHotel : undefined}
        right={
          <Pressable
            onPress={logout}
            style={({ pressed }) => [ui.ghostBtn, pressed && { opacity: 0.75 }]}
          >
            <Text style={ui.ghostBtnText}>Chiqish</Text>
          </Pressable>
        }
      />

      <View style={styles.searchWrap}>
        <SearchField
          value={query}
          onChangeText={setQuery}
          placeholder="Kod, mehmon, xona, telefon…"
        />
      </View>

      {searchHits == null ? (
        <>
          <StatsStrip
            items={[
              { label: "Kirish", value: counts.arrivals },
              { label: "Chiqish", value: counts.departures },
              { label: "Joylashgan", value: counts.in_house },
            ]}
          />
          <View style={styles.segs}>
            {SEGMENTS.map((s) => {
              const on = segment === s.id;
              return (
                <Pressable
                  key={s.id}
                  style={[styles.seg, on && styles.segOn]}
                  onPress={() => setSegment(s.id)}
                >
                  <Text style={[styles.segText, on && styles.segTextOn]}>
                    {s.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </>
      ) : (
        <Text style={styles.searchMeta}>
          {searching ? "Qidirilmoqda…" : `${searchHits.length} ta natija`}
        </Text>
      )}

      {error ? <Text style={[ui.error, styles.pad]}>{error}</Text> : null}

      {loading && !list.length ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={list}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState title="Ro‘yxat bo‘sh" hint="Hozircha yozuv yo‘q" />
          }
          renderItem={({ item }) => (
            <Pressable
              style={({ pressed }) => [
                styles.card,
                pressed && { opacity: 0.92 },
              ]}
              onPress={() => onOpenReservation(item.id)}
            >
              <View style={styles.cardTop}>
                <Text style={styles.room}>{item.room.number || "—"}</Text>
                <StatusBadge
                  label={STATUS_LABEL[item.status] || item.status}
                  tone={statusTone(item.status)}
                />
              </View>
              <Text style={styles.guest} numberOfLines={1}>
                {item.guest.name || "—"}
              </Text>
              <Text style={styles.meta}>
                {item.code} · {item.check_in} → {item.check_out}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: { paddingHorizontal: space.lg, paddingTop: space.md },
  segs: {
    flexDirection: "row",
    gap: space.sm,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  seg: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  segOn: { backgroundColor: colors.night, borderColor: colors.night },
  segText: {
    fontWeight: "700",
    color: colors.inkSoft,
    fontSize: 13,
    fontFamily: fontUi,
  },
  segTextOn: { color: colors.white },
  searchMeta: {
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    color: colors.muted,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  pad: { paddingHorizontal: space.lg, marginBottom: space.sm },
  list: { paddingHorizontal: space.lg, paddingBottom: 100 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    marginBottom: space.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.sm,
  },
  room: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.ink,
    fontFamily: fontDisplay,
  },
  guest: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.ink,
    marginTop: 8,
    fontFamily: fontUi,
  },
  meta: {
    fontSize: 12,
    color: colors.muted,
    marginTop: 4,
    fontFamily: fontUi,
    fontWeight: "500",
  },
});
