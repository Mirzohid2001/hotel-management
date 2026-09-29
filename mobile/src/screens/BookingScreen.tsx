import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type { AvailableRoom, GuestSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  EmptyState,
  FieldLabel,
  FormCard,
  PrimaryButton,
  SearchField,
  SegmentedTabs,
} from "../ui/primitives";
import { colors, fontDisplay, fontUi, radius, space, ui } from "../ui/theme";
import {
  CompanionEditor,
  companionPayload,
  companionsIncomplete,
  companionSlots,
  type CompanionDraft,
} from "../ui/companions";

type Props = {
  onBack: () => void;
  onCreated: (reservationId: number) => void;
  initialRoomId?: number | null;
  initialCheckIn?: string | null;
};

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function isoPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function BookingScreen({
  onBack,
  onCreated,
  initialRoomId = null,
  initialCheckIn = null,
}: Props) {
  const {
    createReservation,
    fetchAvailableRooms,
    searchGuests,
    fetchCompanies,
    fetchReferrers,
    fetchRatePlans,
  } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [checkIn, setCheckIn] = useState(initialCheckIn || isoToday());
  const [checkOut, setCheckOut] = useState(() => {
    if (initialCheckIn) {
      const d = new Date(initialCheckIn + "T12:00:00");
      d.setDate(d.getDate() + 1);
      return d.toISOString().slice(0, 10);
    }
    return isoPlus(1);
  });
  const [adults, setAdults] = useState("1");
  const [children, setChildren] = useState("0");
  const [nightlyRate, setNightlyRate] = useState("");
  const [notes, setNotes] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [docType, setDocType] = useState<"passport" | "id_card">("passport");
  const [issuedCountry, setIssuedCountry] = useState("UZ");
  const [source, setSource] = useState("phone");
  const [commission, setCommission] = useState("");
  const [companions, setCompanions] = useState<CompanionDraft[]>([]);
  const [guestId, setGuestId] = useState<number | null>(null);
  const [guestQ, setGuestQ] = useState("");
  const [guestHits, setGuestHits] = useState<GuestSummary[]>([]);
  const [searchingGuests, setSearchingGuests] = useState(false);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [referrerId, setReferrerId] = useState<number | null>(null);
  const [ratePlanId, setRatePlanId] = useState<number | null>(null);
  const [companies, setCompanies] = useState<Record<string, unknown>[]>([]);
  const [referrers, setReferrers] = useState<Record<string, unknown>[]>([]);
  const [ratePlans, setRatePlans] = useState<Record<string, unknown>[]>([]);
  const [rooms, setRooms] = useState<AvailableRoom[]>([]);
  const [roomId, setRoomId] = useState<number | null>(initialRoomId);
  const [loadingRooms, setLoadingRooms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nights = useMemo(() => {
    try {
      const a = new Date(checkIn + "T12:00:00");
      const b = new Date(checkOut + "T12:00:00");
      const n = Math.round((b.getTime() - a.getTime()) / 86400000);
      return n > 0 ? n : 0;
    } catch {
      return 0;
    }
  }, [checkIn, checkOut]);

  const guestLocked = guestId != null;

  useEffect(() => {
    const a = Math.max(1, parseInt(adults, 10) || 1);
    const c = Math.max(0, parseInt(children, 10) || 0);
    setCompanions((prev) => companionSlots(a, c, prev));
  }, [adults, children]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cos, refs, plans] = await Promise.all([
          fetchCompanies().catch(() => []),
          fetchReferrers().catch(() => []),
          fetchRatePlans().catch(() => []),
        ]);
        if (!cancelled) {
          setCompanies(cos);
          setReferrers(refs);
          setRatePlans(plans);
        }
      } catch {
        /* ignore picker load errors */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchCompanies, fetchReferrers, fetchRatePlans]);

  useEffect(() => {
    let cancelled = false;
    const q = guestQ.trim();
    if (!q || guestLocked) {
      setGuestHits([]);
      setSearchingGuests(false);
      return;
    }
    setSearchingGuests(true);
    const t = setTimeout(async () => {
      try {
        const rows = await searchGuests(q);
        if (!cancelled) setGuestHits(rows);
      } catch {
        if (!cancelled) setGuestHits([]);
      } finally {
        if (!cancelled) setSearchingGuests(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [guestQ, guestLocked, searchGuests]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (nights < 1) {
        setRooms([]);
        setRoomId(null);
        return;
      }
      setLoadingRooms(true);
      setError(null);
      try {
        const items = await fetchAvailableRooms(checkIn, checkOut);
        if (!cancelled) {
          setRooms(items);
          setRoomId((prev) => {
            if (initialRoomId && items.some((r) => r.id === initialRoomId)) {
              return initialRoomId;
            }
            return prev && items.some((r) => r.id === prev)
              ? prev
              : items[0]?.id ?? null;
          });
        }
      } catch (e) {
        if (!cancelled) {
          setRooms([]);
          setRoomId(null);
          setError(e instanceof ApiError ? e.message : "Xonalar yuklanmadi");
        }
      } finally {
        if (!cancelled) setLoadingRooms(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [checkIn, checkOut, nights, fetchAvailableRooms, initialRoomId]);

  function pickGuest(g: GuestSummary) {
    setGuestId(g.id);
    setFirstName(g.first_name || g.name || "");
    setLastName(g.last_name || "");
    setPhone(g.phone || "");
    setGuestQ("");
    setGuestHits([]);
  }

  function clearGuest() {
    setGuestId(null);
    setFirstName("");
    setLastName("");
    setPhone("");
    setGuestQ("");
    setGuestHits([]);
  }

  async function submit() {
    if (!firstName.trim() || !roomId || nights < 1) {
      setError("Ism, sanalar va xona kerak.");
      return;
    }
    const missing = companionsIncomplete(companions);
    if (missing) {
      setError(missing);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createReservation({
        room_id: roomId,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        check_in: checkIn,
        check_out: checkOut,
        adults: Math.max(1, parseInt(adults, 10) || 1),
        children: Math.max(0, parseInt(children, 10) || 0),
        source,
        ...(guestId ? { guest_id: guestId } : {}),
        ...(companyId ? { company_id: companyId } : {}),
        ...(referrerId ? { referrer_id: referrerId } : {}),
        ...(referrerId && commission.trim()
          ? { commission_percent: commission.trim() }
          : {}),
        ...(ratePlanId ? { rate_plan_id: ratePlanId } : {}),
        ...(nightlyRate.trim() ? { nightly_rate: nightlyRate.trim() } : {}),
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        ...(docNumber.trim()
          ? {
              doc_number: docNumber.trim(),
              doc_type: docType,
              issued_country: issuedCountry.trim() || "UZ",
            }
          : {}),
        ...(companions.length
          ? { occupants: companionPayload(companions) }
          : {}),
      });
      Alert.alert("Bron", result.code);
      onCreated(result.reservation_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Bron xatosi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={ui.screen}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScreenHeader
        eyebrow="Bron"
        title="Yangi bron"
        subtitle={nights > 0 ? `${nights} kecha` : "Sanalarni tekshiring"}
        onBack={onBack}
      />

      <ScrollView
        contentContainerStyle={styles.body}
        keyboardShouldPersistTaps="handled"
      >
        <FormCard>
          <FieldLabel>Mehmon qidirish</FieldLabel>
          {guestLocked ? (
            <View style={styles.guestBanner}>
              <Text style={styles.guestBannerText}>Mavjud mehmon</Text>
              <Pressable onPress={clearGuest} hitSlop={8}>
                <Text style={styles.clearLink}>Tozalash</Text>
              </Pressable>
            </View>
          ) : (
            <>
              <SearchField
                value={guestQ}
                onChangeText={setGuestQ}
                placeholder="Ism, telefon…"
              />
              {searchingGuests ? (
                <ActivityIndicator
                  color={colors.accent}
                  style={{ marginVertical: 8 }}
                />
              ) : null}
              {guestHits.map((g) => (
                <Pressable
                  key={g.id}
                  style={styles.hitRow}
                  onPress={() => pickGuest(g)}
                >
                  <Text style={styles.hitTitle}>{g.name}</Text>
                  <Text style={styles.hitMeta}>{g.phone || "—"}</Text>
                </Pressable>
              ))}
            </>
          )}
          <FieldLabel>Ism *</FieldLabel>
          <TextInput
            style={[ui.input, guestLocked && styles.inputLocked]}
            value={firstName}
            onChangeText={setFirstName}
            autoCapitalize="words"
            editable={!guestLocked}
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Familiya</FieldLabel>
          <TextInput
            style={[ui.input, guestLocked && styles.inputLocked]}
            value={lastName}
            onChangeText={setLastName}
            autoCapitalize="words"
            editable={!guestLocked}
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Telefon</FieldLabel>
          <TextInput
            style={[ui.input, guestLocked && styles.inputLocked]}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            editable={!guestLocked}
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Hujjat</FieldLabel>
          <SegmentedTabs
            tabs={[
              { id: "passport", label: "Pasport" },
              { id: "id_card", label: "ID" },
            ]}
            value={docType}
            onChange={setDocType}
          />
          <FieldLabel>Pasport / ID</FieldLabel>
          <TextInput
            style={ui.input}
            value={docNumber}
            onChangeText={setDocNumber}
            autoCapitalize="characters"
            placeholder="AA 1234567"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Berilgan mamlakat</FieldLabel>
          <TextInput
            style={ui.input}
            value={issuedCountry}
            onChangeText={setIssuedCountry}
            autoCapitalize="characters"
            placeholder="UZ"
            placeholderTextColor={colors.faint}
          />
        </FormCard>

        <FormCard>
          <FieldLabel>Kirish (YYYY-MM-DD)</FieldLabel>
          <TextInput
            style={ui.input}
            value={checkIn}
            onChangeText={setCheckIn}
            autoCapitalize="none"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Chiqish (YYYY-MM-DD)</FieldLabel>
          <TextInput
            style={ui.input}
            value={checkOut}
            onChangeText={setCheckOut}
            autoCapitalize="none"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Kattalar</FieldLabel>
          <TextInput
            style={ui.input}
            value={adults}
            onChangeText={setAdults}
            keyboardType="number-pad"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Bolalar</FieldLabel>
          <TextInput
            style={ui.input}
            value={children}
            onChangeText={setChildren}
            keyboardType="number-pad"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Kecha narxi (ixtiyoriy)</FieldLabel>
          <TextInput
            style={ui.input}
            value={nightlyRate}
            onChangeText={setNightlyRate}
            keyboardType="decimal-pad"
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Izoh</FieldLabel>
          <TextInput
            style={[ui.input, styles.notes]}
            value={notes}
            onChangeText={setNotes}
            multiline
            placeholderTextColor={colors.faint}
          />
          <FieldLabel>Manba</FieldLabel>
          <SegmentedTabs
            tabs={[
              { id: "phone", label: "Telefon" },
              { id: "website", label: "Sayt" },
              { id: "other", label: "Boshqa" },
            ]}
            value={source}
            onChange={setSource}
          />
          {companions.length > 0 ? (
            <CompanionEditor rows={companions} onChange={setCompanions} />
          ) : null}
        </FormCard>

        {companies.length > 0 ? (
          <FormCard>
            <Text style={styles.section}>Kompaniya</Text>
            <View style={styles.chipWrap}>
              <Pressable
                style={[ui.chip, companyId == null && ui.chipOn]}
                onPress={() => setCompanyId(null)}
              >
                <Text
                  style={[
                    ui.chipText,
                    companyId == null && ui.chipTextOn,
                  ]}
                >
                  Yo‘q
                </Text>
              </Pressable>
              {companies.map((c) => {
                const id = Number(c.id);
                const on = companyId === id;
                return (
                  <Pressable
                    key={id}
                    style={[ui.chip, on && ui.chipOn]}
                    onPress={() => setCompanyId(on ? null : id)}
                  >
                    <Text style={[ui.chipText, on && ui.chipTextOn]}>
                      {String(c.name)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </FormCard>
        ) : null}

        {referrers.length > 0 ? (
          <FormCard>
            <Text style={styles.section}>Referrer</Text>
            <View style={styles.chipWrap}>
              <Pressable
                style={[ui.chip, referrerId == null && ui.chipOn]}
                onPress={() => {
                  setReferrerId(null);
                  setCommission("");
                }}
              >
                <Text
                  style={[
                    ui.chipText,
                    referrerId == null && ui.chipTextOn,
                  ]}
                >
                  Yo‘q
                </Text>
              </Pressable>
              {referrers.map((r) => {
                const id = Number(r.id);
                const on = referrerId === id;
                return (
                  <Pressable
                    key={id}
                    style={[ui.chip, on && ui.chipOn]}
                    onPress={() => {
                      if (on) {
                        setReferrerId(null);
                        setCommission("");
                      } else {
                        setReferrerId(id);
                        setCommission(String(r.default_commission_percent ?? ""));
                      }
                    }}
                  >
                    <Text style={[ui.chipText, on && ui.chipTextOn]}>
                      {String(r.name)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            {referrerId != null ? (
              <>
                <FieldLabel>Komissiya %</FieldLabel>
                <TextInput
                  style={ui.input}
                  value={commission}
                  onChangeText={setCommission}
                  keyboardType="decimal-pad"
                  placeholder="10"
                  placeholderTextColor={colors.faint}
                />
              </>
            ) : null}
          </FormCard>
        ) : null}

        {ratePlans.length > 0 ? (
          <FormCard>
            <Text style={styles.section}>Tarif rejasi</Text>
            <View style={styles.chipWrap}>
              <Pressable
                style={[ui.chip, ratePlanId == null && ui.chipOn]}
                onPress={() => setRatePlanId(null)}
              >
                <Text
                  style={[
                    ui.chipText,
                    ratePlanId == null && ui.chipTextOn,
                  ]}
                >
                  Yo‘q
                </Text>
              </Pressable>
              {ratePlans.map((p) => {
                const id = Number(p.id);
                const on = ratePlanId === id;
                return (
                  <Pressable
                    key={id}
                    style={[ui.chip, on && ui.chipOn]}
                    onPress={() => setRatePlanId(on ? null : id)}
                  >
                    <Text style={[ui.chipText, on && ui.chipTextOn]}>
                      {String(p.name)}
                      {p.price ? ` · ${String(p.price)}` : ""}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </FormCard>
        ) : null}

        <FormCard>
          <Text style={styles.section}>Bo‘sh xonalar</Text>
          {loadingRooms ? (
            <ActivityIndicator
              color={colors.accent}
              style={{ marginVertical: 12 }}
            />
          ) : rooms.length === 0 ? (
            <EmptyState
              title="Bo‘sh xona yo‘q"
              hint="Shu sanalarda bo‘sh xona topilmadi"
            />
          ) : (
            rooms.map((r) => {
              const on = roomId === r.id;
              return (
                <Pressable
                  key={r.id}
                  style={[styles.roomRow, on && styles.roomRowOn]}
                  onPress={() => setRoomId(r.id)}
                >
                  <Text style={[styles.roomNum, on && styles.roomTextOn]}>
                    {r.number}
                  </Text>
                  <Text style={[styles.roomMeta, on && styles.roomTextOn]}>
                    {r.room_type || r.status}
                    {r.base_price ? ` · ${r.base_price}` : ""}
                  </Text>
                </Pressable>
              );
            })
          )}
        </FormCard>

        {error ? <Text style={ui.error}>{error}</Text> : null}

        <PrimaryButton
          label="Bron yaratish"
          onPress={submit}
          loading={busy}
          disabled={busy || !roomId || !firstName.trim()}
          tone="success"
        />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  body: {
    padding: space.lg,
    paddingBottom: 40,
  },
  section: {
    marginBottom: space.sm,
    fontWeight: "700",
    color: colors.ink,
    fontSize: 15,
    fontFamily: fontUi,
  },
  chipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.sm,
  },
  guestBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.accentFog,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginBottom: space.sm,
  },
  guestBannerText: {
    fontFamily: fontUi,
    fontWeight: "600",
    color: colors.accentDeep,
    fontSize: 13,
  },
  clearLink: {
    fontFamily: fontUi,
    fontWeight: "700",
    color: colors.copper,
    fontSize: 13,
  },
  hitRow: {
    paddingVertical: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  hitTitle: {
    fontFamily: fontUi,
    fontWeight: "600",
    color: colors.ink,
    fontSize: 14,
  },
  hitMeta: {
    fontFamily: fontUi,
    color: colors.muted,
    fontSize: 12,
    marginTop: 2,
  },
  inputLocked: {
    opacity: 0.65,
    backgroundColor: colors.paperDeep,
  },
  notes: {
    minHeight: 72,
    textAlignVertical: "top",
  },
  roomRow: {
    backgroundColor: colors.paper,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: space.md,
    marginBottom: space.sm,
  },
  roomRowOn: {
    backgroundColor: colors.night,
    borderColor: colors.night,
  },
  roomNum: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.ink,
    fontFamily: fontDisplay,
  },
  roomMeta: {
    marginTop: 2,
    color: colors.muted,
    fontSize: 13,
    fontFamily: fontUi,
  },
  roomTextOn: { color: colors.white },
});
