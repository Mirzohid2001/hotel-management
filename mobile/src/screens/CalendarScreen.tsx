import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { CalendarData } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, SegmentedTabs, StatsStrip } from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontDisplay, fontUi, radius, space, ui } from "../ui/theme";

type Props = {
  onBack?: () => void;
  onOpenReservation: (id: number) => void;
  onQuickBook?: (roomId: number, date: string) => void;
};

const ROOM_LABEL_W = 88;
const BAR_H = 38;
const STATUS_BG: Record<string, string> = {
  checked_in: colors.success,
  confirmed: colors.accent,
  inquiry: colors.muted,
};
const STATUS_LABEL: Record<string, string> = {
  checked_in: "Joylangan",
  confirmed: "Tasdiq",
  inquiry: "So‘rov",
};

function shiftIso(iso: string, days: number): string {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatRangeLabel(start: string, end?: string): string {
  try {
    const a = new Date(start + "T12:00:00");
    const label = a.toLocaleDateString("uz-UZ", {
      day: "numeric",
      month: "short",
    });
    if (!end) return label;
    const b = new Date(end + "T12:00:00");
    return `${label} – ${b.toLocaleDateString("uz-UZ", {
      day: "numeric",
      month: "short",
    })}`;
  } catch {
    return start;
  }
}

export function CalendarScreen({
  onBack,
  onOpenReservation,
  onQuickBook,
}: Props) {
  const { fetchCalendar, hotelId, extendStay, transferRoom } = useAuth();
  const [data, setData] = useState<CalendarData | null>(null);
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [days, setDays] = useState<7 | 14 | 30>(14);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const todayIso = new Date().toISOString().slice(0, 10);
  const dayW = days === 7 ? 52 : days === 14 ? 44 : 36;

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchCalendar(start, days));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchCalendar, start, days]
  );

  useEffect(() => {
    load();
  }, [load]);

  const vacantByDate = useMemo(() => {
    const map = new Map<string, { id: number; number: string }[]>();
    if (!data) return map;
    for (const row of data.rows) {
      for (const seg of row.segments) {
        if (seg.kind !== "empty" || !seg.date) continue;
        const list = map.get(seg.date) || [];
        list.push({ id: row.room.id, number: row.room.number });
        map.set(seg.date, list);
      }
    }
    return map;
  }, [data]);

  function onStayActions(
    seg: Extract<CalendarData["rows"][number]["segments"][number], { kind: "stay" }>,
    currentRoomId: number
  ) {
    const title = seg.reservation.guest || seg.reservation.code || "Bron";
    const dayKey = seg.start_day || data?.days[0] || todayIso;
    Alert.alert(String(title), "Harakat tanlang", [
      { text: "Bekor", style: "cancel" },
      {
        text: "Ochish",
        onPress: () => onOpenReservation(seg.reservation.id),
      },
      {
        text: "+1 kecha",
        onPress: async () => {
          setBusy(true);
          try {
            await extendStay(seg.reservation.id, 1);
            await load(true);
            Alert.alert("OK", "1 kecha qo‘shildi");
          } catch (e) {
            Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
          } finally {
            setBusy(false);
          }
        },
      },
      {
        text: "Boshqa xona",
        onPress: () => {
          const targets = (vacantByDate.get(dayKey) || []).filter(
            (r) => r.id !== currentRoomId
          );
          if (!targets.length) {
            Alert.alert("Taqvim", "Shu kunda bo‘sh xona yo‘q");
            return;
          }
          Alert.alert(
            "Xonaga o‘tkazish",
            "Bo‘sh xonani tanlang",
            [
              { text: "Bekor", style: "cancel" },
              ...targets.slice(0, 6).map((r) => ({
                text: r.number,
                onPress: async () => {
                  setBusy(true);
                  try {
                    await transferRoom(seg.reservation.id, r.id, {
                      reason: "Taqvimdan o‘tkazish",
                    });
                    await load(true);
                    Alert.alert("OK", `${r.number} ga o‘tkazildi`);
                  } catch (e) {
                    Alert.alert(
                      "Xato",
                      e instanceof ApiError ? e.message : "Xato"
                    );
                  } finally {
                    setBusy(false);
                  }
                },
              })),
            ],
            { cancelable: true }
          );
        },
      },
      {
        text: "Info",
        onPress: () =>
          Alert.alert(
            String(title),
            `Holat: ${STATUS_LABEL[seg.status] || seg.status}\nDavomiylik: ${seg.colspan} kun\n${seg.reservation.check_in} → ${seg.reservation.check_out}`
          ),
      },
    ]);
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Reja"
        title="Taqvim"
        subtitle={
          data
            ? `${data.stats.rooms} xona · ${data.stats.stays} band`
            : `${days} kunlik shaxmatka`
        }
        onBack={onBack}
      >
        <View style={{ marginBottom: space.sm }}>
          <SegmentedTabs
            value={String(days) as "7" | "14" | "30"}
            onChange={(v) => setDays(Number(v) as 7 | 14 | 30)}
            tabs={[
              { id: "7", label: "7 kun" },
              { id: "14", label: "14 kun" },
              { id: "30", label: "1 oy" },
            ]}
          />
        </View>
        <View style={styles.dateNav}>
          <Pressable
            onPress={() => setStart((s) => shiftIso(s, -Math.min(days, 14)))}
            style={({ pressed }) => [
              styles.dateBtn,
              pressed && { opacity: 0.75 },
            ]}
          >
            <Text style={styles.dateBtnText}>‹</Text>
          </Pressable>
          <Pressable
            style={({ pressed }) => [
              styles.datePill,
              pressed && { opacity: 0.85 },
            ]}
            onPress={() => setStart(todayIso)}
          >
            <Text style={styles.dateLabel}>
              {formatRangeLabel(start, data?.end)}
            </Text>
            {start !== todayIso ? (
              <Text style={styles.todayLink}>Bugun</Text>
            ) : null}
          </Pressable>
          <Pressable
            onPress={() => setStart((s) => shiftIso(s, Math.min(days, 14)))}
            style={({ pressed }) => [
              styles.dateBtn,
              pressed && { opacity: 0.75 },
            ]}
          >
            <Text style={styles.dateBtnText}>›</Text>
          </Pressable>
        </View>
        <View style={styles.legend}>
          {Object.entries(STATUS_LABEL).map(([id, label]) => (
            <View key={id} style={styles.legendItem}>
              <View
                style={[styles.legendDot, { backgroundColor: STATUS_BG[id] }]}
              />
              <Text style={styles.legendText}>{label}</Text>
            </View>
          ))}
          <Text style={styles.legendHint}>Uzoq bosish: +kecha / o‘tkazish</Text>
        </View>
      </ScreenHeader>

      {error ? <Text style={[ui.error, styles.pad]}>{error}</Text> : null}
      {busy ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 8 }} />
      ) : null}
      {loading && !data ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : data ? (
        <ScrollView
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          showsVerticalScrollIndicator={false}
        >
          <StatsStrip
            items={[
              { label: "Xona", value: data.stats.rooms },
              { label: "Band", value: data.stats.stays },
              {
                label: "VIP",
                value: data.stats.vip,
                warn: data.stats.vip > 0,
              },
              { label: "Bo‘sh", value: data.stats.vacant_cells },
            ]}
          />
          {data.rows.length === 0 ? (
            <EmptyState
              title="Xona yo‘q"
              hint="Bu mehmonxonada xonalar sozlanmagan"
            />
          ) : (
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.grid}>
                <View style={styles.dayRow}>
                  <View style={styles.roomLabel} />
                  {data.days.map((d) => {
                    const isToday = d === todayIso;
                    return (
                      <View
                        key={d}
                        style={[
                          styles.dayCell,
                          { width: dayW },
                          isToday && styles.dayCellToday,
                        ]}
                      >
                        <Text
                          style={[
                            styles.dayText,
                            isToday && styles.dayTextToday,
                          ]}
                        >
                          {d.slice(8)}
                        </Text>
                      </View>
                    );
                  })}
                </View>
                {data.rows.map((row) => (
                  <View key={row.room.id} style={styles.roomRow}>
                    <View style={styles.roomLabel}>
                      <Text style={styles.roomNum}>{row.room.number}</Text>
                      {hotelId === "all" && row.room.hotel_name ? (
                        <Text style={styles.roomType} numberOfLines={1}>
                          {row.room.hotel_name}
                        </Text>
                      ) : null}
                      {row.room.room_type ? (
                        <Text style={styles.roomType} numberOfLines={1}>
                          {row.room.room_type}
                        </Text>
                      ) : null}
                    </View>
                    {row.segments.map((seg, i) => {
                      if (seg.kind === "empty") {
                        return (
                          <Pressable
                            key={`e-${i}`}
                            style={({ pressed }) => [
                              styles.empty,
                              { width: dayW * seg.colspan },
                              pressed && styles.emptyPressed,
                              !onQuickBook && styles.emptyDisabled,
                            ]}
                            onPress={() =>
                              onQuickBook?.(
                                row.room.id,
                                seg.date || data.days[0]
                              )
                            }
                            disabled={!onQuickBook}
                          >
                            {onQuickBook ? (
                              <Text style={styles.emptyHint}>+</Text>
                            ) : null}
                          </Pressable>
                        );
                      }
                      return (
                        <Pressable
                          key={`s-${i}`}
                          style={({ pressed }) => [
                            styles.stay,
                            {
                              width: dayW * seg.colspan - 3,
                              backgroundColor:
                                STATUS_BG[seg.status] || colors.warn,
                            },
                            pressed && { opacity: 0.88 },
                          ]}
                          onPress={() => onOpenReservation(seg.reservation.id)}
                          onLongPress={() => onStayActions(seg, row.room.id)}
                          delayLongPress={280}
                        >
                          <Text style={styles.stayText} numberOfLines={1}>
                            {seg.reservation.guest || seg.reservation.code}
                          </Text>
                          {seg.colspan >= 2 ? (
                            <Text style={styles.stayMeta} numberOfLines={1}>
                              {STATUS_LABEL[seg.status] || seg.status} ·{" "}
                              {seg.colspan}k
                            </Text>
                          ) : null}
                        </Pressable>
                      );
                    })}
                  </View>
                ))}
              </View>
            </ScrollView>
          )}
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  dateNav: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    marginTop: space.md,
  },
  dateBtn: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.08)",
    alignItems: "center",
    justifyContent: "center",
  },
  dateBtnText: {
    color: colors.white,
    fontSize: 22,
    fontWeight: "500",
    marginTop: -2,
  },
  datePill: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  dateLabel: {
    color: colors.white,
    fontWeight: "700",
    fontFamily: fontUi,
    fontSize: 15,
  },
  todayLink: {
    color: colors.accentSoft,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "700",
  },
  legend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginTop: space.md,
    alignItems: "center",
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: {
    color: "rgba(255,255,255,0.75)",
    fontSize: 11,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  legendHint: {
    color: "rgba(255,255,255,0.45)",
    fontSize: 10,
    fontFamily: fontUi,
    marginLeft: "auto",
  },
  pad: { padding: space.lg },
  grid: { padding: space.lg, paddingBottom: 48 },
  dayRow: { flexDirection: "row", marginBottom: 8, alignItems: "center" },
  roomRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
  },
  roomLabel: {
    width: ROOM_LABEL_W,
    paddingRight: 6,
    justifyContent: "center",
  },
  roomNum: {
    fontFamily: fontDisplay,
    fontWeight: "700",
    color: colors.ink,
    fontSize: 15,
    letterSpacing: -0.2,
  },
  roomType: {
    fontFamily: fontUi,
    fontSize: 10,
    fontWeight: "600",
    color: colors.muted,
    marginTop: 1,
  },
  dayCell: {
    alignItems: "center",
    paddingVertical: 4,
    borderRadius: 8,
  },
  dayCellToday: {
    backgroundColor: colors.accentFog,
  },
  dayText: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fontUi,
  },
  dayTextToday: {
    color: colors.accentDeep,
  },
  empty: {
    height: BAR_H,
    backgroundColor: colors.paperDeep,
    marginRight: 3,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
  },
  emptyPressed: {
    backgroundColor: colors.accentFog,
    borderColor: colors.accentSoft,
    borderStyle: "solid",
  },
  emptyDisabled: {
    opacity: 0.55,
  },
  emptyHint: {
    color: colors.faint,
    fontSize: 16,
    fontWeight: "600",
    fontFamily: fontUi,
  },
  stay: {
    height: BAR_H,
    borderRadius: 8,
    marginRight: 3,
    justifyContent: "center",
    paddingHorizontal: 7,
  },
  stayText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: fontUi,
  },
  stayMeta: {
    color: "rgba(255,255,255,0.8)",
    fontSize: 9,
    fontWeight: "600",
    fontFamily: fontUi,
    marginTop: 1,
  },
});
