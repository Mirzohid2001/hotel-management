import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
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

const DAY_W = 44;
const ROOM_LABEL_W = 64;
const BAR_H = 36;
const STATUS_BG: Record<string, string> = {
  checked_in: colors.success,
  confirmed: colors.accent,
  inquiry: colors.muted,
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
  const { fetchCalendar } = useAuth();
  const [data, setData] = useState<CalendarData | null>(null);
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [days, setDays] = useState<14 | 30>(14);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const todayIso = new Date().toISOString().slice(0, 10);

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

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Reja"
        title="Taqvim"
        subtitle={
          data
            ? `${data.stats.rooms} xona · ${data.stats.stays} band`
            : `${days} kunlik ko‘rinish`
        }
        onBack={onBack}
      >
        <View style={{ marginBottom: space.sm }}>
          <SegmentedTabs
            value={String(days) as "14" | "30"}
            onChange={(v) => setDays(Number(v) as 14 | 30)}
            tabs={[
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
      </ScreenHeader>

      {error ? <Text style={[ui.error, styles.pad]}>{error}</Text> : null}
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
                        style={[styles.dayCell, isToday && styles.dayCellToday]}
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
                              { width: DAY_W * seg.colspan },
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
                              width: DAY_W * seg.colspan - 3,
                              backgroundColor:
                                STATUS_BG[seg.status] || colors.warn,
                            },
                            pressed && { opacity: 0.88 },
                          ]}
                          onPress={() => onOpenReservation(seg.reservation.id)}
                        >
                          <Text style={styles.stayText} numberOfLines={1}>
                            {seg.reservation.guest || seg.reservation.code}
                          </Text>
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
    width: DAY_W,
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
});
