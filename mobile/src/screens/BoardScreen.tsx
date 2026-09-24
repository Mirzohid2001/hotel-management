import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { BoardTile } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  colors,
  fontDisplay,
  fontUi,
  radius,
  roomState,
  space,
  ui,
} from "../ui/theme";

const STATE_LABEL: Record<string, string> = {
  vacant: "Bo‘sh",
  occupied: "Band",
  dirty: "Kir",
  ooo: "OOO",
  cleaning: "Toza…",
};

type Filter = "all" | "vacant" | "occupied" | "dirty" | "ooo";

function shiftDate(iso: string, delta: number): string {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

function formatDayLabel(iso: string): string {
  try {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
    });
  } catch {
    return iso;
  }
}

function Tile({
  item,
  onPress,
}: {
  item: BoardTile;
  onPress?: () => void;
}) {
  const palette =
    roomState[item.state as keyof typeof roomState] || roomState.vacant;
  const guest = item.reservation?.guest?.name;
  const dates =
    item.reservation != null
      ? `${item.reservation.check_in.slice(5)} → ${item.reservation.check_out.slice(5)}`
      : null;
  const cta =
    item.state === "vacant"
      ? "Joylashtirish"
      : item.state === "dirty"
        ? "Tozalash / Joylash"
        : null;

  const body = (
    <>
      <View style={[styles.accent, { backgroundColor: palette.accent }]} />
      <View style={styles.tileBody}>
        <View style={styles.tileTop}>
          <Text style={[styles.roomNum, { color: palette.fg }]}>
            {item.room.number}
          </Text>
          <View style={[styles.pill, { backgroundColor: palette.pillBg }]}>
            <Text style={[styles.pillText, { color: palette.pillFg }]}>
              {STATE_LABEL[item.state] || item.state}
            </Text>
          </View>
        </View>
        <Text style={[styles.type, { color: palette.fg, opacity: 0.7 }]}>
          {item.room.room_type || "—"}
        </Text>
        {guest ? (
          <Text style={[styles.guest, { color: palette.fg }]} numberOfLines={1}>
            {guest}
          </Text>
        ) : cta ? (
          <Text style={[styles.cta, { color: palette.fg }]}>{cta}</Text>
        ) : (
          <Text style={[styles.cta, { color: palette.fg, opacity: 0.5 }]}>—</Text>
        )}
        {dates ? (
          <Text style={[styles.dates, { color: palette.fg, opacity: 0.65 }]}>
            {dates}
            {item.folio?.balance ? ` · ${item.folio.balance}` : ""}
          </Text>
        ) : null}
      </View>
    </>
  );

  if (onPress) {
    return (
      <Pressable
        style={[styles.tile, { backgroundColor: palette.bg }]}
        onPress={onPress}
      >
        {body}
      </Pressable>
    );
  }
  return (
    <View style={[styles.tile, { backgroundColor: palette.bg }]}>{body}</View>
  );
}

type BoardProps = {
  onOpenReservation: (id: number) => void;
  onWalkIn: (room: BoardTile["room"]) => void;
  onNewBooking?: () => void;
  onCashShift?: () => void;
  onOpenGuests?: () => void;
  onOpenInquiries?: () => void;
  onOpenFlash?: () => void;
  onOpenMaintenance?: () => void;
  onOpenCalendar?: () => void;
  onOpenHousekeeping?: () => void;
  reloadToken?: number;
  onHotelChanged?: () => void;
};

export function BoardScreen({
  onOpenReservation,
  onWalkIn,
  onNewBooking,
  onCashShift,
  onOpenGuests,
  onOpenInquiries,
  onOpenFlash,
  onOpenMaintenance,
  onOpenCalendar,
  onOpenHousekeeping,
  reloadToken = 0,
  onHotelChanged,
}: BoardProps) {
  const { me, fetchBoard, setRoomStatus, setHotel } = useAuth();
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [tiles, setTiles] = useState<BoardTile[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    vacant: 0,
    occupied: 0,
    dirty: 0,
    ooo: 0,
  });
  const [day, setDay] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const todayIso = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const load = useCallback(
    async (isRefresh = false, dateOverride?: string | null) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      try {
        const target = dateOverride === undefined ? selectedDay : dateOverride;
        const data = await fetchBoard(target || undefined);
        setTiles(data.tiles);
        setStats(data.stats);
        setDay(data.day);
        if (!selectedDay) setSelectedDay(data.day);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Yuklash xatosi");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [fetchBoard, selectedDay]
  );

  useEffect(() => {
    load(false, selectedDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadToken]);

  useEffect(() => {
    if (selectedDay) load(false, selectedDay);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDay]);

  function goDay(delta: number) {
    const base = selectedDay || day || todayIso;
    setSelectedDay(shiftDate(base, delta));
  }

  const canWalkIn =
    me?.permissions?.front_office === true ||
    ["admin", "receptionist"].includes(me?.role || "");

  const canCash =
    me?.permissions?.cash === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");

  const canClean =
    me?.permissions?.housekeeping === true ||
    me?.permissions?.floor_view === true ||
    ["admin", "manager", "receptionist", "housekeeper"].includes(me?.role || "");

  const canDash =
    me?.permissions?.dashboard === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");

  const canMaint =
    me?.permissions?.maintenance === true ||
    ["admin", "manager", "receptionist"].includes(me?.role || "");

  async function markClean(room: BoardTile["room"]) {
    try {
      await setRoomStatus(room.id, "ready");
      await load(true, selectedDay);
    } catch (e) {
      Alert.alert(
        "Tozalash",
        e instanceof ApiError ? e.message : "Xona holatini o‘zgartirib bo‘lmadi"
      );
    }
  }

  function onDirtyPress(room: BoardTile["room"]) {
    const buttons: {
      text: string;
      style?: "cancel" | "destructive" | "default";
      onPress?: () => void;
    }[] = [{ text: "Bekor", style: "cancel" }];
    if (canClean) {
      buttons.push({
        text: "Tozalash (tayyor)",
        onPress: () => markClean(room),
      });
    }
    if (canWalkIn) {
      buttons.push({
        text: "Joylashtirish",
        onPress: () => onWalkIn(room),
      });
    }
    Alert.alert(`Xona ${room.number}`, "Kir xona — nima qilamiz?", buttons);
  }

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
              await load(true, selectedDay);
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

  const filtered = tiles.filter((t) =>
    filter === "all" ? true : t.state === filter
  );

  const quick: { label: string; onPress?: () => void }[] = [
    canCash && onCashShift ? { label: "Kassa", onPress: onCashShift } : null,
    canWalkIn && onOpenGuests
      ? { label: "Mehmonlar", onPress: onOpenGuests }
      : null,
    canWalkIn && onOpenInquiries
      ? { label: "So‘rovlar", onPress: onOpenInquiries }
      : null,
    canMaint && onOpenMaintenance
      ? { label: "Ta’mir", onPress: onOpenMaintenance }
      : null,
    canDash && onOpenFlash ? { label: "Flash", onPress: onOpenFlash } : null,
  ].filter(Boolean) as { label: string; onPress?: () => void }[];

  const filters: { id: Filter; label: string; count: number }[] = [
    { id: "all", label: "Hammasi", count: stats.total },
    { id: "vacant", label: "Bo‘sh", count: stats.vacant },
    { id: "occupied", label: "Band", count: stats.occupied },
    { id: "dirty", label: "Kir", count: stats.dirty },
  ];

  const listHeader = (
    <View style={styles.toolbar}>
      {quick.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.hScroll}
          contentContainerStyle={styles.quickRow}
        >
          {quick.map((q) => (
            <Pressable key={q.label} style={styles.quick} onPress={q.onPress}>
              <Text style={styles.quickText}>{q.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.hScroll}
        contentContainerStyle={styles.filterRow}
      >
        {filters.map((f) => (
          <Pressable
            key={f.id}
            style={[styles.filter, filter === f.id && styles.filterOn]}
            onPress={() => setFilter(f.id)}
          >
            <Text
              style={[styles.filterText, filter === f.id && styles.filterTextOn]}
            >
              {f.label} {f.count}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {error ? <Text style={[ui.error, styles.errorPad]}>{error}</Text> : null}
    </View>
  );

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Doska"
        title={me?.hotel?.name || me?.tenant.name || "Hotel"}
        subtitle={
          (me?.hotels?.length || 0) > 1 ? "Filialni almashtirish ›" : me?.role
        }
        onTitlePress={(me?.hotels?.length || 0) > 1 ? pickHotel : undefined}
        right={
          canWalkIn && onNewBooking ? (
            <Pressable onPress={onNewBooking} style={ui.copperBtn}>
              <Text style={ui.copperBtnText}>+ Bron</Text>
            </Pressable>
          ) : null
        }
      />

      <View style={styles.dateNav}>
        <Pressable onPress={() => goDay(-1)} style={styles.dateBtn}>
          <Text style={styles.dateBtnText}>‹</Text>
        </Pressable>
        <Pressable
          style={styles.datePill}
          onPress={() => setSelectedDay(todayIso)}
        >
          <Text style={styles.dateLabel}>
            {formatDayLabel(selectedDay || day || todayIso)}
          </Text>
          {(selectedDay || day) !== todayIso ? (
            <Text style={styles.todayLink}>Bugunga qaytish</Text>
          ) : null}
        </Pressable>
        <Pressable onPress={() => goDay(1)} style={styles.dateBtn}>
          <Text style={styles.dateBtnText}>›</Text>
        </Pressable>
      </View>

      {loading && !tiles.length ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(t) => String(t.room.id)}
          numColumns={2}
          columnWrapperStyle={styles.row}
          contentContainerStyle={styles.list}
          ListHeaderComponent={listHeader}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <Text style={ui.empty}>Bu filtrda xona yo‘q</Text>
          }
          renderItem={({ item }) => (
            <Tile
              item={item}
              onPress={
                item.reservation
                  ? () => onOpenReservation(item.reservation!.id)
                  : item.state === "vacant" && canWalkIn
                    ? () => onWalkIn(item.room)
                    : item.state === "dirty" && (canWalkIn || canClean)
                      ? () => onDirtyPress(item.room)
                      : undefined
              }
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  dateNav: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    backgroundColor: colors.night,
  },
  dateBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.nightLift,
    alignItems: "center",
    justifyContent: "center",
  },
  dateBtnText: {
    color: colors.white,
    fontSize: 20,
    fontWeight: "600",
  },
  datePill: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    borderRadius: radius.sm,
    backgroundColor: colors.nightLift,
  },
  dateLabel: {
    color: colors.white,
    fontWeight: "700",
    fontFamily: fontUi,
    fontSize: 14,
  },
  todayLink: {
    color: colors.accentSoft,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },
  toolbar: {
    marginBottom: space.sm,
  },
  hScroll: {
    flexGrow: 0,
  },
  quickRow: {
    paddingHorizontal: space.md,
    paddingTop: space.md,
    paddingBottom: space.sm,
    gap: space.sm,
    alignItems: "center",
  },
  quick: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 18,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  quickText: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 13,
    color: colors.ink,
  },
  filterRow: {
    paddingHorizontal: space.md,
    paddingBottom: space.md,
    gap: space.sm,
    alignItems: "center",
  },
  filter: {
    height: 32,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: colors.paperDeep,
    alignItems: "center",
    justifyContent: "center",
  },
  filterOn: {
    backgroundColor: colors.night,
  },
  filterText: {
    fontFamily: fontUi,
    fontWeight: "600",
    fontSize: 12,
    color: colors.inkSoft,
  },
  filterTextOn: {
    color: colors.white,
  },
  errorPad: { paddingHorizontal: space.lg, marginBottom: space.sm },
  list: { paddingBottom: 28 },
  row: {
    gap: space.sm,
    marginBottom: space.sm,
    paddingHorizontal: space.md,
  },
  tile: {
    flex: 1,
    minHeight: 104,
    borderRadius: radius.lg,
    overflow: "hidden",
    flexDirection: "row",
    backgroundColor: colors.surface,
  },
  accent: {
    width: 4,
  },
  tileBody: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 12,
    justifyContent: "space-between",
  },
  tileTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 6,
  },
  roomNum: {
    fontFamily: fontDisplay,
    fontSize: 22,
    fontWeight: "700",
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  pillText: {
    fontSize: 10,
    fontWeight: "800",
    fontFamily: fontUi,
    letterSpacing: 0.3,
  },
  type: {
    fontSize: 12,
    marginTop: 2,
    fontFamily: fontUi,
    fontWeight: "500",
  },
  guest: {
    fontSize: 13,
    fontWeight: "700",
    marginTop: 8,
    fontFamily: fontUi,
  },
  cta: {
    fontSize: 12,
    fontWeight: "600",
    marginTop: 8,
    fontFamily: fontUi,
  },
  dates: {
    fontSize: 11,
    marginTop: 2,
    fontFamily: fontUi,
    fontWeight: "500",
  },
});
