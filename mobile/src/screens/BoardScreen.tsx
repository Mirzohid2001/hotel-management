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
  useWindowDimensions,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { BoardTile } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import { EmptyState } from "../ui/primitives";
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
  cleaning: "Tozalanmoqda",
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
    return d.toLocaleDateString("uz-UZ", {
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
  onLongPress,
  wide,
}: {
  item: BoardTile;
  onPress?: () => void;
  onLongPress?: () => void;
  wide?: boolean;
}) {
  const palette =
    roomState[item.state as keyof typeof roomState] || roomState.vacant;
  const guest = item.reservation?.guest?.name;
  const roomType = (item.room.room_type || "").trim();
  const showType = roomType.length > 1;
  const dates =
    item.reservation != null
      ? `${item.reservation.check_in.slice(5)} → ${item.reservation.check_out.slice(5)}`
      : null;
  const isVacant = item.state === "vacant";
  const isDirty = item.state === "dirty";

  const body = (
    <View style={[styles.tileInner, { backgroundColor: palette.bg }]}>
      <View style={[styles.accentBar, { backgroundColor: palette.accent }]} />
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

        {showType ? (
          <Text style={[styles.type, { color: palette.fg }]} numberOfLines={1}>
            {roomType}
          </Text>
        ) : (
          <View style={{ height: 4 }} />
        )}

        <View style={styles.tileFooter}>
          {guest ? (
            <>
              <Text
                style={[styles.guest, { color: palette.fg }]}
                numberOfLines={1}
              >
                {guest}
              </Text>
              {dates ? (
                <Text style={[styles.dates, { color: palette.fg }]}>
                  {dates}
                  {item.folio?.balance ? ` · ${item.folio.balance}` : ""}
                </Text>
              ) : null}
            </>
          ) : isVacant || isDirty ? (
            <View
              style={[
                styles.ctaBtn,
                {
                  backgroundColor: colors.accentFog,
                },
              ]}
            >
              <Text
                style={[
                  styles.ctaBtnText,
                  {
                    color: colors.accentDeep,
                  },
                ]}
              >
                {isVacant ? "Joylashtirish →" : "Tozalash →"}
              </Text>
            </View>
          ) : (
            <Text style={[styles.dates, { color: palette.fg, opacity: 0.5 }]}>
              —
            </Text>
          )}
        </View>
      </View>
    </View>
  );

  const shellStyle = [styles.tile, wide && styles.tileWide];

  if (onPress || onLongPress) {
    return (
      <Pressable
        style={({ pressed }) => [
          ...shellStyle,
          pressed && { opacity: 0.9, transform: [{ scale: 0.985 }] },
        ]}
        onPress={onPress}
        onLongPress={onLongPress}
        delayLongPress={380}
      >
        {body}
      </Pressable>
    );
  }
  return <View style={shellStyle}>{body}</View>;
}

type BoardProps = {
  onOpenReservation: (id: number) => void;
  onWalkIn: (room: BoardTile["room"]) => void;
  onNewBooking?: () => void;
  onCashShift?: () => void;
  onOpenGuests?: () => void;
  onOpenInquiries?: () => void;
  onOpenFlash?: () => void;
  onOpenDashboard?: () => void;
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
  onOpenDashboard,
  onOpenMaintenance,
  reloadToken = 0,
  onHotelChanged,
}: BoardProps) {
  const { width } = useWindowDimensions();
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

  async function applyRoomStatus(
    room: BoardTile["room"],
    status: "ready" | "dirty" | "cleaning" | "out_of_order"
  ) {
    try {
      await setRoomStatus(room.id, status);
      await load(true, selectedDay);
    } catch (e) {
      Alert.alert(
        "Holat",
        e instanceof ApiError ? e.message : "Xona holatini o‘zgartirib bo‘lmadi"
      );
    }
  }

  function roomStatusMenu(room: BoardTile["room"], state: string) {
    const buttons: {
      text: string;
      style?: "cancel" | "destructive" | "default";
      onPress?: () => void;
    }[] = [{ text: "Bekor", style: "cancel" }];

    if (canWalkIn && (state === "vacant" || state === "dirty")) {
      buttons.push({
        text: "Joylashtirish",
        onPress: () => onWalkIn(room),
      });
    }
    if (canClean || canWalkIn) {
      if (state !== "vacant") {
        buttons.push({
          text: "Tayyor (ready)",
          onPress: () => applyRoomStatus(room, "ready"),
        });
      }
      if (state !== "dirty") {
        buttons.push({
          text: "Kir deb belgilash",
          onPress: () => applyRoomStatus(room, "dirty"),
        });
      }
      if (state !== "cleaning") {
        buttons.push({
          text: "Tozalanmoqda",
          onPress: () => applyRoomStatus(room, "cleaning"),
        });
      }
      if (state !== "ooo") {
        buttons.push({
          text: "OOO (ishdan chiqarish)",
          style: "destructive",
          onPress: () => applyRoomStatus(room, "out_of_order"),
        });
      }
    }
    if (buttons.length <= 1) return;
    Alert.alert(
      `Xona ${room.number}`,
      "Holatni o‘zgartirish (uzoq bosish)",
      buttons
    );
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
        onPress: () => applyRoomStatus(room, "ready"),
      });
    }
    if (canWalkIn) {
      buttons.push({
        text: "Joylashtirish",
        onPress: () => onWalkIn(room),
      });
    }
    if (canClean || canWalkIn) {
      buttons.push({
        text: "OOO",
        style: "destructive",
        onPress: () => applyRoomStatus(room, "out_of_order"),
      });
    }
    Alert.alert(`Xona ${room.number}`, "Kir xona — nima qilamiz?", buttons);
  }

  function pickHotel() {
    const hotels = me?.hotels || [];
    if (hotels.length < 2) return;
    Alert.alert("Filial", "Qaysi mehmonxona?", [
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
    ]);
  }

  const filtered = tiles.filter((t) =>
    filter === "all" ? true : t.state === filter
  );

  const occPct =
    stats.total > 0 ? Math.round((stats.occupied / stats.total) * 100) : 0;

  const hotelTitle =
    (me?.hotel?.name || "").trim().length > 1
      ? me!.hotel!.name
      : (me?.tenant.name || "").trim().length > 1
        ? me!.tenant.name
        : "Mehmonxona";

  const quick: { label: string; mark: string; onPress?: () => void }[] = [
    canDash && onOpenDashboard
      ? { label: "Dashboard", mark: "D", onPress: onOpenDashboard }
      : null,
    canCash && onCashShift
      ? { label: "Kassa", mark: "₸", onPress: onCashShift }
      : null,
    canWalkIn && onOpenGuests
      ? { label: "Mehmonlar", mark: "M", onPress: onOpenGuests }
      : null,
    canWalkIn && onOpenInquiries
      ? { label: "So‘rovlar", mark: "S", onPress: onOpenInquiries }
      : null,
    canMaint && onOpenMaintenance
      ? { label: "Ta’mir", mark: "T", onPress: onOpenMaintenance }
      : null,
    canDash && onOpenFlash
      ? { label: "Flash", mark: "F", onPress: onOpenFlash }
      : null,
  ].filter(Boolean) as { label: string; mark: string; onPress?: () => void }[];

  const filters: { id: Filter; label: string; count: number }[] = [
    { id: "all", label: "Hammasi", count: stats.total },
    { id: "vacant", label: "Bo‘sh", count: stats.vacant },
    { id: "occupied", label: "Band", count: stats.occupied },
    { id: "dirty", label: "Kir", count: stats.dirty },
    { id: "ooo", label: "OOO", count: stats.ooo },
  ];

  const useSingleCol = filtered.length <= 1 || width < 360;
  const gap = 10;
  const pad = 16;
  const tileWidth = useSingleCol
    ? width - pad * 2
    : (width - pad * 2 - gap) / 2;

  const listHeader = (
    <View style={styles.toolbar}>
      <View style={styles.statsCard}>
        <View style={styles.statBlock}>
          <Text style={styles.statValue}>{occPct}%</Text>
          <Text style={styles.statLabel}>OCC</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statBlock}>
          <Text style={styles.statValue}>{stats.vacant}</Text>
          <Text style={styles.statLabel}>Bo‘sh</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statBlock}>
          <Text style={styles.statValue}>{stats.occupied}</Text>
          <Text style={styles.statLabel}>Band</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statBlock}>
          <Text style={[styles.statValue, stats.dirty > 0 && { color: colors.warn }]}>
            {stats.dirty}
          </Text>
          <Text style={styles.statLabel}>Kir</Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statBlock}>
          <Text
            style={[styles.statValue, stats.ooo > 0 && { color: colors.danger }]}
          >
            {stats.ooo}
          </Text>
          <Text style={styles.statLabel}>OOO</Text>
        </View>
      </View>

      {quick.length > 0 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.quickRow}
        >
          {quick.map((q) => (
            <Pressable
              key={q.label}
              style={({ pressed }) => [
                styles.quick,
                pressed && { backgroundColor: colors.accentFog },
              ]}
              onPress={q.onPress}
            >
              <View style={styles.quickMark}>
                <Text style={styles.quickMarkText}>{q.mark}</Text>
              </View>
              <Text style={styles.quickText}>{q.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filterRow}
      >
        {filters.map((f) => {
          const on = filter === f.id;
          return (
            <Pressable
              key={f.id}
              style={[styles.filter, on && styles.filterOn]}
              onPress={() => setFilter(f.id)}
            >
              <Text style={[styles.filterText, on && styles.filterTextOn]}>
                {f.label}
              </Text>
              <View style={[styles.filterCount, on && styles.filterCountOn]}>
                <Text
                  style={[
                    styles.filterCountText,
                    on && styles.filterCountTextOn,
                  ]}
                >
                  {f.count}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>

      {error ? <Text style={[ui.error, styles.errorPad]}>{error}</Text> : null}
    </View>
  );

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Doska"
        title={hotelTitle}
        subtitle={
          (me?.hotels?.length || 0) > 1
            ? `${me?.role || "staff"} · filialni almashtirish ›`
            : me?.role || undefined
        }
        onTitlePress={(me?.hotels?.length || 0) > 1 ? pickHotel : undefined}
        right={
          canWalkIn && onNewBooking ? (
            <Pressable
              onPress={onNewBooking}
              style={({ pressed }) => [
                styles.bronBtn,
                pressed && { opacity: 0.85 },
              ]}
            >
              <Text style={styles.bronBtnText}>+ Bron</Text>
            </Pressable>
          ) : null
        }
      >
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
              <Text style={styles.todayLink}>Bugun</Text>
            ) : null}
          </Pressable>
          <Pressable onPress={() => goDay(1)} style={styles.dateBtn}>
            <Text style={styles.dateBtnText}>›</Text>
          </Pressable>
        </View>
      </ScreenHeader>

      {loading && !tiles.length ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(t) => String(t.room.id)}
          numColumns={useSingleCol ? 1 : 2}
          key={useSingleCol ? "1" : "2"}
          columnWrapperStyle={useSingleCol ? undefined : styles.row}
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
            <EmptyState
              title="Bu filtrda xona yo‘q"
              hint="Boshqa filtrni tanlang"
            />
          }
          renderItem={({ item }) => (
            <View style={{ width: tileWidth }}>
              <Tile
                item={item}
                wide={useSingleCol}
                onPress={
                  item.reservation
                    ? () => onOpenReservation(item.reservation!.id)
                    : item.state === "vacant" && canWalkIn
                      ? () => onWalkIn(item.room)
                      : item.state === "dirty" && (canWalkIn || canClean)
                        ? () => onDirtyPress(item.room)
                        : item.state === "ooo" && (canClean || canWalkIn)
                          ? () => roomStatusMenu(item.room, item.state)
                          : undefined
                }
                onLongPress={
                  !item.reservation && (canClean || canWalkIn)
                    ? () => roomStatusMenu(item.room, item.state)
                    : undefined
                }
              />
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bronBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bronBtnText: {
    color: colors.white,
    fontWeight: "800",
    fontSize: 13,
    fontFamily: fontUi,
  },
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
  toolbar: {
    marginBottom: space.sm,
  },
  statsCard: {
    marginHorizontal: space.lg,
    marginTop: space.md,
    marginBottom: space.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    paddingVertical: 16,
    paddingHorizontal: 8,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  statBlock: {
    flex: 1,
    alignItems: "center",
  },
  statValue: {
    fontFamily: fontDisplay,
    fontSize: 22,
    fontWeight: "700",
    color: colors.ink,
  },
  statLabel: {
    marginTop: 2,
    fontFamily: fontUi,
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
    letterSpacing: 0.3,
  },
  statDivider: {
    width: StyleSheet.hairlineWidth,
    height: 28,
    backgroundColor: colors.line,
  },
  quickRow: {
    paddingHorizontal: space.lg,
    paddingVertical: space.sm,
    gap: space.sm,
  },
  quick: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    paddingLeft: 8,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  quickMark: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: colors.accentFog,
    alignItems: "center",
    justifyContent: "center",
  },
  quickMarkText: {
    fontFamily: fontUi,
    fontWeight: "800",
    fontSize: 12,
    color: colors.accentDeep,
  },
  quickText: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 13,
    color: colors.ink,
  },
  filterRow: {
    paddingHorizontal: space.lg,
    paddingBottom: space.md,
    gap: space.sm,
  },
  filter: {
    height: 36,
    paddingLeft: 12,
    paddingRight: 6,
    borderRadius: radius.md,
    backgroundColor: colors.paperDeep,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
  },
  filterOn: {
    backgroundColor: colors.night,
  },
  filterText: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 12,
    color: colors.inkSoft,
  },
  filterTextOn: {
    color: colors.white,
  },
  filterCount: {
    minWidth: 22,
    height: 22,
    borderRadius: 8,
    paddingHorizontal: 6,
    backgroundColor: "rgba(18,21,26,0.08)",
    alignItems: "center",
    justifyContent: "center",
  },
  filterCountOn: {
    backgroundColor: "rgba(255,255,255,0.16)",
  },
  filterCountText: {
    fontFamily: fontUi,
    fontSize: 11,
    fontWeight: "800",
    color: colors.inkSoft,
  },
  filterCountTextOn: {
    color: colors.white,
  },
  errorPad: { paddingHorizontal: space.lg, marginBottom: space.sm },
  list: { paddingBottom: 32, paddingHorizontal: space.lg },
  row: {
    gap: 10,
    marginBottom: 10,
  },
  tile: {
    marginBottom: 10,
    borderRadius: radius.lg,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  tileWide: {
    minHeight: 132,
  },
  tileInner: {
    flexDirection: "row",
    minHeight: 124,
  },
  accentBar: {
    width: 5,
  },
  tileBody: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 14,
    justifyContent: "space-between",
  },
  tileTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  roomNum: {
    fontFamily: fontDisplay,
    fontSize: 28,
    fontWeight: "700",
    letterSpacing: -0.5,
  },
  pill: {
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 8,
  },
  pillText: {
    fontSize: 11,
    fontWeight: "800",
    fontFamily: fontUi,
    letterSpacing: 0.2,
  },
  type: {
    fontSize: 13,
    marginTop: 4,
    fontFamily: fontUi,
    fontWeight: "600",
    opacity: 0.65,
  },
  tileFooter: {
    marginTop: 10,
  },
  guest: {
    fontSize: 14,
    fontWeight: "700",
    fontFamily: fontUi,
  },
  dates: {
    fontSize: 12,
    marginTop: 3,
    fontFamily: fontUi,
    fontWeight: "500",
    opacity: 0.7,
  },
  ctaBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
  },
  ctaBtnText: {
    fontFamily: fontUi,
    fontWeight: "800",
    fontSize: 13,
  },
});
