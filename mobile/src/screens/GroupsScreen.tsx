import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { GuestSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import {
  AvatarMark,
  EmptyState,
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, fontUi, radius, space, ui } from "../ui/theme";

type Props = {
  onBack: () => void;
  onOpenReservation: (id: number) => void;
};

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function statusTone(
  status: string
): "neutral" | "success" | "warn" | "danger" | "info" | "accent" {
  const s = status.toLowerCase();
  if (s === "checked_in" || s === "confirmed") return "success";
  if (s === "inquiry") return "warn";
  if (s === "cancelled" || s === "no_show") return "danger";
  return "neutral";
}

type RoomLine = {
  guestId: number | null;
  guestLabel: string;
  firstName: string;
  rate: string;
  adults: string;
  children: string;
};

export function GroupsScreen({ onBack, onOpenReservation }: Props) {
  const {
    fetchGroups,
    fetchGroup,
    createGroup,
    fetchAvailableRooms,
    fetchCompanies,
    searchGuests,
  } = useAuth();
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [checkIn, setCheckIn] = useState(isoToday());
  const [checkOut, setCheckOut] = useState(isoPlus(1));
  const [guestFirst, setGuestFirst] = useState("");
  const [guestLast, setGuestLast] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedRoomIds, setSelectedRoomIds] = useState<number[]>([]);
  const [lines, setLines] = useState<Record<number, RoomLine>>({});
  const [guestHits, setGuestHits] = useState<GuestSummary[]>([]);
  const [searchRoomId, setSearchRoomId] = useState<number | null>(null);
  const [companies, setCompanies] = useState<{ id: number; name: string }[]>([]);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [rooms, setRooms] = useState<
    { id: number; number: string; price: string }[]
  >([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchGroups());
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [fetchGroups]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!creating) return;
    let cancelled = false;
    (async () => {
      try {
        const items = await fetchAvailableRooms(checkIn, checkOut);
        if (!cancelled) {
          const next = items.map((r) => ({
            id: r.id,
            number: r.number,
            price: r.base_price || "",
          }));
          setRooms(next);
          setSelectedRoomIds((prev) =>
            prev.filter((id) => next.some((r) => r.id === id))
          );
        }
      } catch {
        if (!cancelled) {
          setRooms([]);
          setSelectedRoomIds([]);
        }
      }
      try {
        const rows = await fetchCompanies();
        if (!cancelled) {
          setCompanies(
            rows.map((c) => ({ id: Number(c.id), name: String(c.name) }))
          );
        }
      } catch {
        if (!cancelled) setCompanies([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [creating, checkIn, checkOut, fetchAvailableRooms, fetchCompanies]);

  function blankLine(price = ""): RoomLine {
    return {
      guestId: null,
      guestLabel: "",
      firstName: "",
      rate: price,
      adults: "1",
      children: "0",
    };
  }

  function patchLine(id: number, patch: Partial<RoomLine>) {
    setLines((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || blankLine()), ...patch },
    }));
  }

  async function openGroup(id: number) {
    try {
      setDetail(await fetchGroup(id));
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    }
  }

  function toggleRoom(id: number) {
    const room = rooms.find((r) => r.id === id);
    setSelectedRoomIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      setLines((linesPrev) =>
        linesPrev[id] ? linesPrev : { ...linesPrev, [id]: blankLine(room?.price || "") }
      );
      return [...prev, id];
    });
  }

  async function lookupGuest(roomId: number, q: string) {
    setSearchRoomId(roomId);
    if (q.trim().length < 2) {
      setGuestHits([]);
      return;
    }
    try {
      setGuestHits(await searchGuests(q.trim()));
    } catch {
      setGuestHits([]);
    }
  }

  async function submitGroup() {
    const missing = selectedRoomIds.some((id) => {
      const line = lines[id];
      return !line?.guestId && !(line?.firstName || guestFirst).trim();
    });
    if (!name.trim() || missing || selectedRoomIds.length < 1) {
      Alert.alert("Xato", "Nom, har xona uchun mehmon va kamida 1 xona kerak");
      return;
    }
    setBusy(true);
    try {
      const g = await createGroup({
        name: name.trim(),
        check_in: checkIn,
        check_out: checkOut,
        notes: notes.trim(),
        company_id: companyId || undefined,
        rooms: selectedRoomIds.map((id) => {
          const line = lines[id] || blankLine();
          const adults = Number(line.adults);
          const children = Number(line.children);
          return {
            guest_id: line.guestId || undefined,
            first_name: line.guestId
              ? undefined
              : (line.firstName || guestFirst).trim(),
            last_name: line.guestId ? undefined : guestLast.trim(),
            room_id: id,
            nightly_rate: line.rate.trim() || undefined,
            adults: Number.isFinite(adults) && adults >= 1 ? adults : 1,
            children: Number.isFinite(children) && children >= 0 ? children : 0,
          };
        }),
      });
      setCreating(false);
      setName("");
      setGuestFirst("");
      setGuestLast("");
      setNotes("");
      setLines({});
      setGuestHits([]);
      setCompanyId(null);
      setSelectedRoomIds([]);
      await load();
      Alert.alert("OK", `Guruh: ${String(g.code || g.name)}`);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  if (detail) {
    const roomsList = (detail.reservations as Record<string, unknown>[]) || [];
    return (
      <View style={ui.screen}>
        <ScreenHeader
          eyebrow={String(detail.code)}
          title={String(detail.name)}
          subtitle={`${detail.check_in} → ${detail.check_out} · ${roomsList.length} bron`}
          onBack={() => setDetail(null)}
        />
        <FlatList
          data={roomsList}
          keyExtractor={(r) => String(r.id)}
          contentContainerStyle={ui.listPad}
          ListEmptyComponent={
            <EmptyState title="Bron yo‘q" hint="Guruhda rezervatsiya yo‘q" />
          }
          renderItem={({ item }) => {
            const guestName =
              (item.guest as { name?: string })?.name || String(item.code);
            const roomNum =
              (item.room as { number?: string })?.number || "—";
            return (
              <ListCard
                title={String(guestName)}
                meta={`${roomNum} · ${String(item.status)}`}
                badge={String(item.status)}
                badgeTone={statusTone(String(item.status))}
                leading={<AvatarMark label={String(guestName)} />}
                onPress={() => onOpenReservation(Number(item.id))}
              />
            );
          }}
        />
      </View>
    );
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Bron"
        title="Guruhlar"
        subtitle={
          creating
            ? selectedRoomIds.length
              ? `${selectedRoomIds.length} xona tanlangan`
              : "Xonalarni tanlang"
            : items.length
              ? `${items.length} ta guruh`
              : "Guruh bronlari"
        }
        onBack={onBack}
        right={
          <Pressable
            style={({ pressed }) => [ui.copperBtn, pressed && { opacity: 0.85 }]}
            onPress={() => setCreating((v) => !v)}
          >
            <Text style={ui.copperBtnText}>
              {creating ? "Yopish" : "+ Yangi"}
            </Text>
          </Pressable>
        }
      />
      {creating ? (
        <ScrollView
          contentContainerStyle={ui.listPad}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <FormCard>
            <FieldLabel>Guruh nomi</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Masalan: Tour A"
              placeholderTextColor={colors.faint}
              value={name}
              onChangeText={setName}
            />
            <FieldLabel>Kirish (YYYY-MM-DD)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.faint}
              value={checkIn}
              onChangeText={setCheckIn}
              autoCapitalize="none"
            />
            <FieldLabel>Chiqish (YYYY-MM-DD)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.faint}
              value={checkOut}
              onChangeText={setCheckOut}
              autoCapitalize="none"
            />
            <FieldLabel>Mehmon ismi (yangi mehmon uchun)</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Ism"
              placeholderTextColor={colors.faint}
              value={guestFirst}
              onChangeText={setGuestFirst}
            />
            <FieldLabel>Familiya</FieldLabel>
            <TextInput
              style={ui.input}
              placeholder="Familiya"
              placeholderTextColor={colors.faint}
              value={guestLast}
              onChangeText={setGuestLast}
            />
            <FieldLabel>Izoh</FieldLabel>
            <TextInput
              style={[ui.input, { minHeight: 72 }]}
              placeholder="Guruh izohi"
              placeholderTextColor={colors.faint}
              value={notes}
              onChangeText={setNotes}
              multiline
            />
          </FormCard>

          {companies.length ? (
            <>
              <Text style={ui.section}>Kompaniya</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                <Pressable
                  style={[ui.chip, companyId == null && ui.chipOn]}
                  onPress={() => setCompanyId(null)}
                >
                  <Text
                    style={[ui.chipText, companyId == null && ui.chipTextOn]}
                  >
                    Yo‘q
                  </Text>
                </Pressable>
                {companies.map((c) => (
                  <Pressable
                    key={c.id}
                    style={[ui.chip, companyId === c.id && ui.chipOn]}
                    onPress={() => setCompanyId(c.id)}
                  >
                    <Text
                      style={[
                        ui.chipText,
                        companyId === c.id && ui.chipTextOn,
                      ]}
                    >
                      {c.name}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}

          <Text style={ui.section}>
            Xonalar
            {selectedRoomIds.length
              ? ` · ${selectedRoomIds.length} tanlangan`
              : ""}
          </Text>
          {rooms.length === 0 ? (
            <EmptyState
              title="Bo‘sh xona yo‘q"
              hint="Sanalarni o‘zgartiring"
            />
          ) : (
            <View style={styles.roomGrid}>
              {rooms.map((r) => {
                const on = selectedRoomIds.includes(r.id);
                return (
                  <Pressable
                    key={r.id}
                    style={[styles.roomChip, on && styles.roomChipOn]}
                    onPress={() => toggleRoom(r.id)}
                  >
                    <Text
                      style={[styles.roomChipText, on && styles.roomChipTextOn]}
                    >
                      {r.number}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          )}
          {selectedRoomIds.length ? (
            <FormCard>
              <Text style={ui.section}>Har bir xona</Text>
              {selectedRoomIds.map((id) => {
                const room = rooms.find((r) => r.id === id);
                const line = lines[id] || blankLine(room?.price || "");
                return (
                  <View key={id} style={{ marginBottom: space.md }}>
                    <FieldLabel>{room?.number || String(id)}</FieldLabel>
                    <TextInput
                      style={ui.input}
                      placeholder="Mavjud mehmonni qidirish"
                      placeholderTextColor={colors.faint}
                      value={searchRoomId === id ? line.guestLabel || "" : line.guestLabel}
                      onChangeText={(text) => {
                        patchLine(id, {
                          guestLabel: text,
                          guestId: null,
                          firstName: line.firstName,
                        });
                        lookupGuest(id, text);
                      }}
                    />
                    {searchRoomId === id && guestHits.length ? (
                      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                        {guestHits.slice(0, 8).map((g) => (
                          <Pressable
                            key={g.id}
                            style={[ui.chip, line.guestId === g.id && ui.chipOn]}
                            disabled={g.is_blacklisted}
                            onPress={() => {
                              if (g.is_blacklisted) return;
                              patchLine(id, {
                                guestId: g.id,
                                guestLabel: g.name,
                              });
                              setGuestHits([]);
                            }}
                          >
                            <Text
                              style={[
                                ui.chipText,
                                line.guestId === g.id && ui.chipTextOn,
                              ]}
                            >
                              {g.name}
                              {g.is_blacklisted ? " · qora" : ""}
                            </Text>
                          </Pressable>
                        ))}
                      </View>
                    ) : null}
                    {line.guestId ? (
                      <Pressable
                        style={[ui.chip, { marginBottom: 8 }]}
                        onPress={() =>
                          patchLine(id, { guestId: null, guestLabel: "" })
                        }
                      >
                        <Text style={ui.chipText}>Tanlovni olib tashlash</Text>
                      </Pressable>
                    ) : (
                      <TextInput
                        style={ui.input}
                        placeholder={guestFirst || "Yangi ism"}
                        placeholderTextColor={colors.faint}
                        value={line.firstName}
                        onChangeText={(text) => patchLine(id, { firstName: text })}
                      />
                    )}
                    <FieldLabel>Kecha narxi</FieldLabel>
                    <TextInput
                      style={ui.input}
                      placeholder={room?.price || "0"}
                      placeholderTextColor={colors.faint}
                      keyboardType="decimal-pad"
                      value={line.rate}
                      onChangeText={(text) => patchLine(id, { rate: text })}
                    />
                    <FieldLabel>Kattalar</FieldLabel>
                    <TextInput
                      style={ui.input}
                      keyboardType="number-pad"
                      value={line.adults}
                      onChangeText={(text) => patchLine(id, { adults: text })}
                    />
                    <FieldLabel>Bolalar</FieldLabel>
                    <TextInput
                      style={ui.input}
                      keyboardType="number-pad"
                      value={line.children}
                      onChangeText={(text) => patchLine(id, { children: text })}
                    />
                  </View>
                );
              })}
            </FormCard>
          ) : null}
          <PrimaryButton
            label={
              selectedRoomIds.length
                ? `Guruh yaratish (${selectedRoomIds.length} xona)`
                : "Guruh yaratish"
            }
            onPress={submitGroup}
            loading={busy}
            disabled={busy || selectedRoomIds.length < 1}
          />
        </ScrollView>
      ) : loading && !items.length ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={ui.listPad}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={load}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <EmptyState
              title="Guruh yo‘q"
              hint="Yangi guruh bronini yarating"
            />
          }
          renderItem={({ item }) => (
            <ListCard
              title={`${String(item.code)} · ${String(item.name)}`}
              meta={`${String(item.check_in)} → ${String(item.check_out)} · ${String(item.rooms)} xona${item.company ? ` · ${item.company}` : ""}`}
              badge={`${String(item.rooms)} xona`}
              badgeTone="accent"
              leading={<AvatarMark label={String(item.name || item.code)} />}
              onPress={() => openGroup(Number(item.id))}
            />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  roomGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.sm,
    marginBottom: space.md,
  },
  roomChip: {
    minWidth: 56,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    alignItems: "center",
  },
  roomChipOn: {
    backgroundColor: colors.night,
    borderColor: colors.night,
  },
  roomChipText: {
    fontFamily: fontUi,
    fontWeight: "700",
    fontSize: 14,
    color: colors.ink,
  },
  roomChipTextOn: {
    color: colors.white,
  },
});
