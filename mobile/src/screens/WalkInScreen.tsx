import { useEffect, useState } from "react";
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
import type { GuestSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  FieldLabel,
  FormCard,
  PrimaryButton,
  SearchField,
} from "../ui/primitives";
import { colors, fontUi, radius, space, ui } from "../ui/theme";
import {
  CompanionEditor,
  companionPayload,
  companionsIncomplete,
  companionSlots,
  type CompanionDraft,
} from "../ui/companions";

type RoomInfo = {
  id: number;
  number: string;
  room_type: string;
  status: string;
};

type Props = {
  room: RoomInfo;
  onBack: () => void;
  onCreated: (reservationId: number) => void;
};

export function WalkInScreen({ room, onBack, onCreated }: Props) {
  const {
    walkIn,
    searchGuests,
    fetchCompanies,
    fetchReferrers,
    fetchPropertySettings,
  } = useAuth();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [nights, setNights] = useState("1");
  const [adults, setAdults] = useState("1");
  const [children, setChildren] = useState("0");
  const [nightlyRate, setNightlyRate] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [guestId, setGuestId] = useState<number | null>(null);
  const [guestQ, setGuestQ] = useState("");
  const [guestHits, setGuestHits] = useState<GuestSummary[]>([]);
  const [searchingGuests, setSearchingGuests] = useState(false);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [referrerId, setReferrerId] = useState<number | null>(null);
  const [companies, setCompanies] = useState<Record<string, unknown>[]>([]);
  const [referrers, setReferrers] = useState<Record<string, unknown>[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collectEmehmon, setCollectEmehmon] = useState(true);
  const [emehmonUnit, setEmehmonUnit] = useState(0);
  const [emehmonAmount, setEmehmonAmount] = useState("");
  const [companions, setCompanions] = useState<CompanionDraft[]>([]);

  const guestLocked = guestId != null;

  const guestsCount = Math.max(
    1,
    (parseInt(adults, 10) || 1) + (parseInt(children, 10) || 0)
  );
  const nightsCount = Math.max(1, parseInt(nights, 10) || 1);
  const emehmonDefault =
    emehmonUnit > 0 ? String(emehmonUnit * nightsCount * guestsCount) : "";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cos, refs, settings] = await Promise.all([
          fetchCompanies().catch(() => []),
          fetchReferrers().catch(() => []),
          fetchPropertySettings().catch(() => null),
        ]);
        if (!cancelled) {
          setCompanies(cos);
          setReferrers(refs);
          const unit = Number(settings?.emehmon_fee || 0);
          setEmehmonUnit(Number.isFinite(unit) ? unit : 0);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchCompanies, fetchReferrers, fetchPropertySettings]);

  useEffect(() => {
    if (emehmonDefault) setEmehmonAmount(emehmonDefault);
  }, [emehmonDefault]);

  useEffect(() => {
    const a = Math.max(1, parseInt(adults, 10) || 1);
    const c = Math.max(0, parseInt(children, 10) || 0);
    setCompanions((prev) => companionSlots(a, c, prev));
  }, [adults, children]);

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

  async function submit(force?: { allow_dirty?: boolean; allow_no_docs?: boolean }) {
    setError(null);
    const missing = companionsIncomplete(companions);
    if (missing) {
      setError(missing);
      setBusy(false);
      return;
    }
    setBusy(true);
    try {
      const result = await walkIn({
        room_id: room.id,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim(),
        nights: Math.max(1, parseInt(nights, 10) || 1),
        adults: Math.max(1, parseInt(adults, 10) || 1),
        children: Math.max(0, parseInt(children, 10) || 0),
        doc_number: docNumber.trim(),
        allow_dirty: !!force?.allow_dirty || room.status === "dirty",
        allow_no_docs: !!force?.allow_no_docs || !docNumber.trim(),
        collect_emehmon: collectEmehmon,
        emehmon_method: "cash",
        ...(collectEmehmon && emehmonAmount.trim()
          ? { emehmon_amount: emehmonAmount.trim() }
          : {}),
        ...(companions.length
          ? { occupants: companionPayload(companions) }
          : {}),
        ...(guestId ? { guest_id: guestId } : {}),
        ...(companyId ? { company_id: companyId } : {}),
        ...(referrerId ? { referrer_id: referrerId } : {}),
        ...(nightlyRate.trim() ? { nightly_rate: nightlyRate.trim() } : {}),
      });
      Alert.alert("Joylashdi", `${result.code}`);
      onCreated(result.reservation_id);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Xato";
      if (/kir|dirty|tozala/i.test(msg)) {
        Alert.alert("Xona holati", msg, [
          { text: "Bekor", style: "cancel" },
          {
            text: "Baribir",
            onPress: () => submit({ allow_dirty: true }),
          },
        ]);
      } else {
        setError(msg);
      }
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
        eyebrow="Walk-in"
        title="Darhol joylash"
        subtitle={`Xona ${room.number}${room.room_type ? ` · ${room.room_type}` : ""}`}
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
        </FormCard>

        <FormCard>
          <FieldLabel>Kechalar</FieldLabel>
          <TextInput
            style={ui.input}
            value={nights}
            onChangeText={setNights}
            keyboardType="number-pad"
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
          <FieldLabel>Pasport/ID (ixtiyoriy)</FieldLabel>
          <TextInput
            style={ui.input}
            value={docNumber}
            onChangeText={setDocNumber}
            autoCapitalize="characters"
            placeholderTextColor={colors.faint}
          />
        </FormCard>

        <FormCard>
          <Text style={styles.section}>E-mehmon</Text>
          <Text style={styles.hint}>
            {emehmonUnit > 0
              ? `${emehmonUnit} × ${nightsCount} kecha × ${guestsCount} kishi`
              : "Setup’da tarif yo‘q"}
          </Text>
          <Pressable
            style={[ui.chip, collectEmehmon && ui.chipOn, { marginBottom: 8 }]}
            onPress={() => setCollectEmehmon((v) => !v)}
          >
            <Text style={[ui.chipText, collectEmehmon && ui.chipTextOn]}>
              {collectEmehmon ? "✓ E-mehmon olinsin" : "E-mehmon olinmasin"}
            </Text>
          </Pressable>
          {collectEmehmon ? (
            <>
              <FieldLabel>Summa (o‘zgartirish mumkin)</FieldLabel>
              <TextInput
                style={ui.input}
                value={emehmonAmount}
                onChangeText={setEmehmonAmount}
                keyboardType="decimal-pad"
                placeholder={emehmonDefault || "0"}
                placeholderTextColor={colors.faint}
              />
            </>
          ) : null}
          <Text style={styles.hint}>
            Qo‘shimcha kishilar soni kattalar/bolalar bilan ochiladi.
          </Text>
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
                onPress={() => setReferrerId(null)}
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
                    onPress={() => setReferrerId(on ? null : id)}
                  >
                    <Text style={[ui.chipText, on && ui.chipTextOn]}>
                      {String(r.name)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </FormCard>
        ) : null}

        {error ? <Text style={ui.error}>{error}</Text> : null}

        <PrimaryButton
          label="Joylashtirish"
          onPress={() => submit()}
          loading={busy}
          disabled={busy || !firstName.trim()}
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
  hint: {
    marginBottom: space.sm,
    fontSize: 12,
    lineHeight: 17,
    color: colors.muted,
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
});
