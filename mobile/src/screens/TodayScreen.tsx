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
import type { ReservationSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
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
          <Pressable onPress={logout} style={ui.ghostBtn}>
            <Text style={ui.ghostBtnText}>Chiqish</Text>
          </Pressable>
        }
      />

      <View style={styles.searchWrap}>
        <TextInput
          style={styles.search}
          value={query}
          onChangeText={setQuery}
          placeholder="Kod, mehmon, xona, telefon…"
          placeholderTextColor={colors.faint}
          autoCapitalize="none"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>

      {searchHits == null ? (
        <View style={styles.segs}>
          {SEGMENTS.map((s) => (
            <Pressable
              key={s.id}
              style={[styles.seg, segment === s.id && styles.segOn]}
              onPress={() => setSegment(s.id)}
            >
              <Text
                style={[styles.segText, segment === s.id && styles.segTextOn]}
              >
                {s.label}
              </Text>
              <Text
                style={[styles.segCount, segment === s.id && styles.segTextOn]}
              >
                {counts[s.id]}
              </Text>
            </Pressable>
          ))}
        </View>
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
          ListEmptyComponent={<Text style={ui.empty}>Ro‘yxat bo‘sh</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={styles.card}
              onPress={() => onOpenReservation(item.id)}
            >
              <View style={styles.cardTop}>
                <Text style={styles.room}>{item.room.number || "—"}</Text>
                <Text style={styles.code}>{item.code}</Text>
              </View>
              <Text style={styles.guest} numberOfLines={1}>
                {item.guest.name || "—"}
              </Text>
              <Text style={styles.meta}>
                {item.check_in} → {item.check_out} ·{" "}
                {STATUS_LABEL[item.status] || item.status}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: { paddingHorizontal: space.md, paddingTop: space.md },
  search: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    paddingHorizontal: space.lg,
    paddingVertical: 13,
    fontSize: 16,
    color: colors.ink,
    fontFamily: fontUi,
  },
  segs: {
    flexDirection: "row",
    gap: space.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.md,
  },
  seg: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingVertical: 11,
    alignItems: "center",
  },
  segOn: { backgroundColor: colors.night },
  segText: {
    fontWeight: "700",
    color: colors.inkSoft,
    fontSize: 13,
    fontFamily: fontUi,
  },
  segCount: {
    marginTop: 2,
    color: colors.muted,
    fontWeight: "600",
    fontSize: 12,
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
  list: { paddingHorizontal: space.md, paddingBottom: 100 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space.lg,
    marginBottom: space.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.lineSoft,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  room: {
    fontSize: 22,
    fontWeight: "600",
    color: colors.ink,
    fontFamily: fontDisplay,
  },
  code: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
    fontFamily: fontUi,
  },
  guest: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.ink,
    marginTop: 6,
    fontFamily: fontUi,
  },
  meta: {
    fontSize: 12,
    color: colors.muted,
    marginTop: 4,
    fontFamily: fontUi,
  },
});
