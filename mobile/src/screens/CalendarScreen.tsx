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
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = {
  onBack?: () => void;
  onOpenReservation: (id: number) => void;
};

const DAY_W = 40;
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

export function CalendarScreen({ onBack, onOpenReservation }: Props) {
  const { fetchCalendar } = useAuth();
  const [data, setData] = useState<CalendarData | null>(null);
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        setData(await fetchCalendar(start, 14));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchCalendar, start]
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
            : undefined
        }
        onBack={onBack}
      >
        <View style={styles.navRow}>
          <Pressable
            style={styles.navBtn}
            onPress={() => setStart((s) => shiftIso(s, -7))}
          >
            <Text style={styles.navText}>‹ Hafta</Text>
          </Pressable>
          <Pressable
            style={styles.navBtn}
            onPress={() => setStart(new Date().toISOString().slice(0, 10))}
          >
            <Text style={styles.navText}>Bugun</Text>
          </Pressable>
          <Pressable
            style={styles.navBtn}
            onPress={() => setStart((s) => shiftIso(s, 7))}
          >
            <Text style={styles.navText}>Hafta ›</Text>
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
        >
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={styles.grid}>
              <View style={styles.dayRow}>
                <View style={styles.roomLabel} />
                {data.days.map((d) => (
                  <View key={d} style={styles.dayCell}>
                    <Text style={styles.dayText}>{d.slice(8)}</Text>
                  </View>
                ))}
              </View>
              {data.rows.map((row) => (
                <View key={row.room.id} style={styles.roomRow}>
                  <View style={styles.roomLabel}>
                    <Text style={styles.roomNum}>{row.room.number}</Text>
                  </View>
                  {row.segments.map((seg, i) => {
                    if (seg.kind === "empty") {
                      return (
                        <View
                          key={`e-${i}`}
                          style={[styles.empty, { width: DAY_W * seg.colspan }]}
                        />
                      );
                    }
                    return (
                      <Pressable
                        key={`s-${i}`}
                        style={[
                          styles.stay,
                          {
                            width: DAY_W * seg.colspan - 3,
                            backgroundColor:
                              STATUS_BG[seg.status] || colors.warn,
                          },
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
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  navRow: { flexDirection: "row", gap: space.sm, marginTop: space.md },
  navBtn: {
    flex: 1,
    paddingVertical: 9,
    borderRadius: radius.sm,
    backgroundColor: colors.nightLift,
    alignItems: "center",
  },
  navText: {
    color: colors.white,
    fontWeight: "600",
    fontSize: 13,
    fontFamily: fontUi,
  },
  pad: { padding: space.lg },
  grid: { padding: space.md, paddingBottom: 48 },
  dayRow: { flexDirection: "row", marginBottom: 6 },
  roomRow: { flexDirection: "row", alignItems: "center", marginBottom: 5 },
  roomLabel: { width: 52, justifyContent: "center" },
  roomNum: {
    fontWeight: "700",
    color: colors.ink,
    fontSize: 13,
    fontFamily: fontUi,
  },
  dayCell: { width: DAY_W, alignItems: "center" },
  dayText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fontUi,
  },
  empty: {
    height: 30,
    backgroundColor: colors.paperDeep,
    marginRight: 3,
    borderRadius: 6,
  },
  stay: {
    height: 30,
    borderRadius: 6,
    marginRight: 3,
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  stayText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: "700",
    fontFamily: fontUi,
  },
});
