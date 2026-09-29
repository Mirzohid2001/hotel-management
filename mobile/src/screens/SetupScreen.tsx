import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  FieldLabel,
  FormCard,
  ListCard,
  PrimaryButton,
  SegmentedTabs,
} from "../ui/primitives";
import { ScreenHeader } from "../ui/ScreenHeader";
import { colors, space, ui } from "../ui/theme";

type Props = { onBack: () => void };
type Tab = "settings" | "rooms" | "services" | "rates";

export function SetupScreen({ onBack }: Props) {
  const {
    fetchPropertySettings,
    updatePropertySettings,
    fetchRoomTypes,
    createRoomType,
    fetchAdminRooms,
    createAdminRoom,
    createFloor,
    updateRoomType,
    updateAdminRoom,
    fetchServicesCatalog,
    createServiceItem,
    fetchRatePlans,
    createRatePlan,
    createRateSeason,
    fetchRatePlanMatrix,
  } = useAuth();
  const [tab, setTab] = useState<Tab>("settings");
  const [loading, setLoading] = useState(true);
  const [emehmon, setEmehmon] = useState("");
  const [tax, setTax] = useState("");
  const [cancelPct, setCancelPct] = useState("");
  const [earlyFee, setEarlyFee] = useState("");
  const [lateFee, setLateFee] = useState("");
  const [checkinTime, setCheckinTime] = useState("");
  const [checkoutTime, setCheckoutTime] = useState("");
  const [requireId, setRequireId] = useState(true);
  const [roomTypes, setRoomTypes] = useState<Record<string, unknown>[]>([]);
  const [rooms, setRooms] = useState<Record<string, unknown>[]>([]);
  const [floors, setFloors] = useState<Record<string, unknown>[]>([]);
  const [floorId, setFloorId] = useState<number | null>(null);
  const [floorNumber, setFloorNumber] = useState("");
  const [floorName, setFloorName] = useState("");
  const [services, setServices] = useState<Record<string, unknown>[]>([]);
  const [rates, setRates] = useState<Record<string, unknown>[]>([]);
  const [rtName, setRtName] = useState("");
  const [rtCode, setRtCode] = useState("");
  const [rtPrice, setRtPrice] = useState("");
  const [roomNumber, setRoomNumber] = useState("");
  const [roomTypeId, setRoomTypeId] = useState<number | null>(null);
  const [svcName, setSvcName] = useState("");
  const [svcCode, setSvcCode] = useState("");
  const [svcPrice, setSvcPrice] = useState("");
  const [rateName, setRateName] = useState("");
  const [rateCode, setRateCode] = useState("");
  const [ratePrice, setRatePrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [matrixPlanId, setMatrixPlanId] = useState<number | null>(null);
  const [matrixRows, setMatrixRows] = useState<Record<string, unknown>[]>([]);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [seasonPlanId, setSeasonPlanId] = useState<number | null>(null);
  const [seasonName, setSeasonName] = useState("");
  const [seasonStart, setSeasonStart] = useState("");
  const [seasonEnd, setSeasonEnd] = useState("");
  const [seasonPrice, setSeasonPrice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, rts, rms, svcs, rps] = await Promise.all([
        fetchPropertySettings().catch(() => null),
        fetchRoomTypes().catch(() => []),
        fetchAdminRooms().catch(() => ({ items: [], floors: [] })),
        fetchServicesCatalog().catch(() => []),
        fetchRatePlans().catch(() => []),
      ]);
      if (s) {
        setEmehmon(String(s.emehmon_fee ?? ""));
        setTax(String(s.tax_percent ?? ""));
        setCancelPct(String(s.cancel_fee_percent ?? ""));
        setEarlyFee(String(s.early_checkin_fee ?? ""));
        setLateFee(String(s.late_checkout_fee ?? ""));
        setCheckinTime(String(s.checkin_time ?? ""));
        setCheckoutTime(String(s.checkout_time ?? ""));
        setRequireId(Boolean(s.require_id_on_checkin));
      }
      setRoomTypes(rts);
      setRooms(rms.items || []);
      setFloors(rms.floors || []);
      if (!roomTypeId && rts[0]) setRoomTypeId(Number(rts[0].id));
      if (!floorId && (rms.floors || [])[0]) setFloorId(Number(rms.floors[0].id));
      setServices(svcs);
      setRates(rps);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setLoading(false);
    }
  }, [
    fetchPropertySettings,
    fetchRoomTypes,
    fetchAdminRooms,
    fetchServicesCatalog,
    fetchRatePlans,
    roomTypeId,
  ]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveSettings() {
    setBusy(true);
    try {
      await updatePropertySettings({
        emehmon_fee: emehmon,
        tax_percent: tax,
        cancel_fee_percent: cancelPct,
        early_checkin_fee: earlyFee,
        late_checkout_fee: lateFee,
        checkin_time: checkinTime.trim(),
        checkout_time: checkoutTime.trim(),
        require_id_on_checkin: requireId,
      });
      Alert.alert("OK", "Sozlamalar saqlandi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addRoomType() {
    if (!rtName.trim() || !rtCode.trim()) return;
    setBusy(true);
    try {
      await createRoomType({
        name: rtName.trim(),
        code: rtCode.trim(),
        base_price: rtPrice || "0",
      });
      setRtName("");
      setRtCode("");
      setRtPrice("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addRoom() {
    if (!roomNumber.trim() || !roomTypeId) return;
    setBusy(true);
    try {
      await createAdminRoom({
        number: roomNumber.trim(),
        room_type_id: roomTypeId,
        ...(floorId ? { floor_id: floorId } : {}),
      });
      setRoomNumber("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addFloor() {
    if (!floorNumber.trim()) return;
    setBusy(true);
    try {
      await createFloor({
        number: Number(floorNumber.trim()),
        name: floorName.trim() || undefined,
      });
      setFloorNumber("");
      setFloorName("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addService() {
    if (!svcName.trim() || !svcCode.trim()) return;
    setBusy(true);
    try {
      await createServiceItem({
        name: svcName.trim(),
        code: svcCode.trim(),
        unit_price: svcPrice || "0",
      });
      setSvcName("");
      setSvcCode("");
      setSvcPrice("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function addRate() {
    if (!rateName.trim() || !rateCode.trim() || !roomTypeId) return;
    setBusy(true);
    try {
      await createRatePlan({
        name: rateName.trim(),
        code: rateCode.trim(),
        room_type_id: roomTypeId,
        price: ratePrice || "0",
        is_default: rates.length === 0,
      });
      setRateName("");
      setRateCode("");
      setRatePrice("");
      await load();
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  async function loadMatrix(planId: number) {
    if (matrixPlanId === planId) {
      setMatrixPlanId(null);
      setMatrixRows([]);
      return;
    }
    setMatrixLoading(true);
    setMatrixPlanId(planId);
    try {
      const data = await fetchRatePlanMatrix(planId, undefined, 42);
      setMatrixRows((data.rows as Record<string, unknown>[]) || []);
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
      setMatrixPlanId(null);
      setMatrixRows([]);
    } finally {
      setMatrixLoading(false);
    }
  }

  async function addSeason() {
    if (!seasonPlanId || !seasonStart.trim() || !seasonEnd.trim()) {
      Alert.alert("Xato", "Sana oralig‘i kerak");
      return;
    }
    setBusy(true);
    try {
      await createRateSeason(seasonPlanId, {
        name: seasonName.trim() || "Sezon",
        date_from: seasonStart.trim(),
        date_to: seasonEnd.trim(),
        price: seasonPrice.trim() || "0",
      });
      setSeasonName("");
      setSeasonStart("");
      setSeasonEnd("");
      setSeasonPrice("");
      const plan = seasonPlanId;
      setSeasonPlanId(null);
      await load();
      if (matrixPlanId === plan) {
        const data = await fetchRatePlanMatrix(plan, undefined, 42);
        setMatrixRows((data.rows as Record<string, unknown>[]) || []);
      }
      Alert.alert("OK", "Sezon qo‘shildi");
    } catch (e) {
      Alert.alert("Xato", e instanceof ApiError ? e.message : "Xato");
    } finally {
      setBusy(false);
    }
  }

  function editMatrixCell(row: Record<string, unknown>) {
    if (!matrixPlanId) return;
    const d = String(row.date || "");
    if (!d) return;
    setSeasonPlanId(matrixPlanId);
    setSeasonName(d);
    setSeasonStart(d);
    setSeasonEnd(d);
    setSeasonPrice(String(row.price ?? ""));
  }

  return (
    <View style={ui.screen}>
      <ScreenHeader
        eyebrow="Admin"
        title="Sozlama"
        subtitle="Mehmonxona · xonalar · xizmatlar · tariflar"
        onBack={onBack}
      />
      <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
        <SegmentedTabs
          tabs={[
            { id: "settings", label: "Asosiy" },
            { id: "rooms", label: "Xonalar" },
            { id: "services", label: "Xizmat" },
            { id: "rates", label: "Tarif" },
          ]}
          value={tab}
          onChange={setTab}
        />
      </View>
      {loading ? (
        <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={ui.listPad}
          showsVerticalScrollIndicator={false}
        >
          {tab === "settings" ? (
            <FormCard>
              <FieldLabel>E-mehmon to‘lovi</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="9000"
                placeholderTextColor={colors.faint}
                value={emehmon}
                onChangeText={setEmehmon}
                keyboardType="decimal-pad"
              />
              <FieldLabel>QQS %</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="12"
                placeholderTextColor={colors.faint}
                value={tax}
                onChangeText={setTax}
                keyboardType="decimal-pad"
              />
              <FieldLabel>Bekor %</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="0"
                placeholderTextColor={colors.faint}
                value={cancelPct}
                onChangeText={setCancelPct}
                keyboardType="decimal-pad"
              />
              <FieldLabel>Erta check-in to‘lovi</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="0"
                placeholderTextColor={colors.faint}
                value={earlyFee}
                onChangeText={setEarlyFee}
                keyboardType="decimal-pad"
              />
              <FieldLabel>Kech check-out to‘lovi</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="0"
                placeholderTextColor={colors.faint}
                value={lateFee}
                onChangeText={setLateFee}
                keyboardType="decimal-pad"
              />
              <FieldLabel>Check-in vaqti</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="14:00"
                placeholderTextColor={colors.faint}
                value={checkinTime}
                onChangeText={setCheckinTime}
                autoCapitalize="none"
              />
              <FieldLabel>Check-out vaqti</FieldLabel>
              <TextInput
                style={ui.input}
                placeholder="12:00"
                placeholderTextColor={colors.faint}
                value={checkoutTime}
                onChangeText={setCheckoutTime}
                autoCapitalize="none"
              />
              <Pressable onPress={() => setRequireId((v) => !v)}>
                <Text style={ui.rowMeta}>
                  {requireId
                    ? "Check-in: pasport majburiy"
                    : "Check-in: hujjatsiz ruxsat"}
                </Text>
              </Pressable>
              <PrimaryButton
                label="Saqlash"
                onPress={saveSettings}
                loading={busy}
              />
            </FormCard>
          ) : null}

          {tab === "rooms" ? (
            <>
              <FormCard>
                <Text style={ui.section}>Yangi xona turi</Text>
                <FieldLabel>Nomi</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="Standart"
                  placeholderTextColor={colors.faint}
                  value={rtName}
                  onChangeText={setRtName}
                />
                <FieldLabel>Kod</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="std"
                  placeholderTextColor={colors.faint}
                  value={rtCode}
                  onChangeText={setRtCode}
                  autoCapitalize="none"
                />
                <FieldLabel>Narx</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="350000"
                  placeholderTextColor={colors.faint}
                  value={rtPrice}
                  onChangeText={setRtPrice}
                  keyboardType="decimal-pad"
                />
                <PrimaryButton
                  label="Tur qo‘shish"
                  onPress={addRoomType}
                  loading={busy}
                />
              </FormCard>

              <FormCard>
                <Text style={ui.section}>Qavat</Text>
                <FieldLabel>Raqam</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="1"
                  placeholderTextColor={colors.faint}
                  value={floorNumber}
                  onChangeText={setFloorNumber}
                  keyboardType="number-pad"
                />
                <FieldLabel>Nomi</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="Birinchi"
                  placeholderTextColor={colors.faint}
                  value={floorName}
                  onChangeText={setFloorName}
                />
                <PrimaryButton label="Qavat qo‘shish" onPress={addFloor} loading={busy} />
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                  {floors.map((f) => (
                    <Pressable
                      key={String(f.id)}
                      style={[ui.chip, floorId === Number(f.id) && ui.chipOn]}
                      onPress={() => setFloorId(Number(f.id))}
                    >
                      <Text style={[ui.chipText, floorId === Number(f.id) && ui.chipTextOn]}>
                        {String(f.number)}{f.name ? ` · ${f.name}` : ""}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </FormCard>

              <FormCard>
                <Text style={ui.section}>Yangi xona</Text>
                <FieldLabel>Raqam</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="101"
                  placeholderTextColor={colors.faint}
                  value={roomNumber}
                  onChangeText={setRoomNumber}
                />
                <FieldLabel>Xona turi</FieldLabel>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                    {roomTypes.map((rt) => (
                      <Pressable
                        key={String(rt.id)}
                        style={[ui.chip, roomTypeId === Number(rt.id) && ui.chipOn]}
                        onPress={() => setRoomTypeId(Number(rt.id))}
                      >
                        <Text
                          style={[
                            ui.chipText,
                            roomTypeId === Number(rt.id) && ui.chipTextOn,
                          ]}
                        >
                          {String(rt.name)}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </ScrollView>
                <PrimaryButton
                  label="Xona qo‘shish"
                  onPress={addRoom}
                  loading={busy}
                />
              </FormCard>

              <Text style={ui.section}>Xonalar ({rooms.length})</Text>
              {rooms.slice(0, 40).map((r) => (
                <ListCard
                  key={String(r.id)}
                  title={`${String(r.number)} · ${String(r.room_type)}`}
                  meta={String(r.status)}
                  badge={r.is_active ? "Faol" : "O‘chiq"}
                  badgeTone={r.is_active ? "success" : "neutral"}
                />
              ))}
            </>
          ) : null}

          {tab === "services" ? (
            <>
              <FormCard>
                <Text style={ui.section}>Yangi xizmat</Text>
                <FieldLabel>Nomi</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="Kir yuvish"
                  placeholderTextColor={colors.faint}
                  value={svcName}
                  onChangeText={setSvcName}
                />
                <FieldLabel>Kod</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="laundry"
                  placeholderTextColor={colors.faint}
                  value={svcCode}
                  onChangeText={setSvcCode}
                  autoCapitalize="none"
                />
                <FieldLabel>Narx</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="25000"
                  placeholderTextColor={colors.faint}
                  value={svcPrice}
                  onChangeText={setSvcPrice}
                  keyboardType="decimal-pad"
                />
                <PrimaryButton
                  label="Qo‘shish"
                  onPress={addService}
                  loading={busy}
                />
              </FormCard>
              <Text style={ui.section}>Katalog ({services.length})</Text>
              {services.map((s) => (
                <ListCard
                  key={String(s.id)}
                  title={String(s.name)}
                  meta={String(s.code)}
                  badge={String(s.unit_price)}
                  badgeTone="accent"
                />
              ))}
            </>
          ) : null}

          {tab === "rates" ? (
            <>
              <FormCard>
                <Text style={ui.section}>Yangi tarif</Text>
                <FieldLabel>Nomi</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="BAR"
                  placeholderTextColor={colors.faint}
                  value={rateName}
                  onChangeText={setRateName}
                />
                <FieldLabel>Kod</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="bar"
                  placeholderTextColor={colors.faint}
                  value={rateCode}
                  onChangeText={setRateCode}
                  autoCapitalize="none"
                />
                <FieldLabel>Narx</FieldLabel>
                <TextInput
                  style={ui.input}
                  placeholder="350000"
                  placeholderTextColor={colors.faint}
                  value={ratePrice}
                  onChangeText={setRatePrice}
                  keyboardType="decimal-pad"
                />
                <FieldLabel>Xona turi</FieldLabel>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
                    {roomTypes.map((rt) => (
                      <Pressable
                        key={String(rt.id)}
                        style={[ui.chip, roomTypeId === Number(rt.id) && ui.chipOn]}
                        onPress={() => setRoomTypeId(Number(rt.id))}
                      >
                        <Text
                          style={[
                            ui.chipText,
                            roomTypeId === Number(rt.id) && ui.chipTextOn,
                          ]}
                        >
                          {String(rt.name)}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </ScrollView>
                <PrimaryButton
                  label="Tarif qo‘shish"
                  onPress={addRate}
                  loading={busy}
                />
              </FormCard>
              <Text style={ui.section}>Tariflar ({rates.length})</Text>
              {seasonPlanId != null ? (
                <FormCard>
                  <Text style={ui.section}>
                    Sezon · tarif #{seasonPlanId}
                  </Text>
                  <FieldLabel>Nomi</FieldLabel>
                  <TextInput
                    style={ui.input}
                    placeholder="Yoz"
                    placeholderTextColor={colors.faint}
                    value={seasonName}
                    onChangeText={setSeasonName}
                  />
                  <FieldLabel>Boshlanish (YYYY-MM-DD)</FieldLabel>
                  <TextInput
                    style={ui.input}
                    placeholder="2026-06-01"
                    placeholderTextColor={colors.faint}
                    value={seasonStart}
                    onChangeText={setSeasonStart}
                    autoCapitalize="none"
                  />
                  <FieldLabel>Tugash (YYYY-MM-DD)</FieldLabel>
                  <TextInput
                    style={ui.input}
                    placeholder="2026-08-31"
                    placeholderTextColor={colors.faint}
                    value={seasonEnd}
                    onChangeText={setSeasonEnd}
                    autoCapitalize="none"
                  />
                  <FieldLabel>Narx</FieldLabel>
                  <TextInput
                    style={ui.input}
                    placeholder="450000"
                    placeholderTextColor={colors.faint}
                    value={seasonPrice}
                    onChangeText={setSeasonPrice}
                    keyboardType="decimal-pad"
                  />
                  <PrimaryButton
                    label="Sezon saqlash"
                    onPress={addSeason}
                    loading={busy}
                  />
                  <PrimaryButton
                    label="Bekor"
                    onPress={() => setSeasonPlanId(null)}
                    tone="ghost"
                  />
                </FormCard>
              ) : null}
              {rates.map((r) => (
                <View key={String(r.id)}>
                  <ListCard
                    title={`${String(r.name)} · ${String(r.price)}`}
                    meta={`${String(r.code)} · ${String(r.room_type || "")}${
                      Array.isArray(r.seasons) && r.seasons.length
                        ? ` · ${r.seasons.length} sezon`
                        : ""
                    }`}
                    badge={r.is_default ? "Default" : "Faol"}
                    badgeTone={r.is_default ? "accent" : "success"}
                  >
                    <View
                      style={{
                        flexDirection: "row",
                        flexWrap: "wrap",
                        gap: 8,
                        marginTop: 10,
                      }}
                    >
                      <Pressable
                        style={ui.chip}
                        onPress={() => loadMatrix(Number(r.id))}
                      >
                        <Text style={ui.chipText}>
                          {matrixPlanId === Number(r.id)
                            ? "Matritsa yopish"
                            : "Matritsa"}
                        </Text>
                      </Pressable>
                      <Pressable
                        style={ui.chip}
                        onPress={() =>
                          setSeasonPlanId(
                            seasonPlanId === Number(r.id)
                              ? null
                              : Number(r.id)
                          )
                        }
                      >
                        <Text style={ui.chipText}>+ Sezon</Text>
                      </Pressable>
                    </View>
                  </ListCard>
                  {matrixPlanId === Number(r.id) ? (
                    matrixLoading ? (
                      <ActivityIndicator
                        color={colors.accent}
                        style={{ marginVertical: 12 }}
                      />
                    ) : (
                      <ScrollView
                        horizontal
                        showsHorizontalScrollIndicator={false}
                        style={{ marginBottom: space.md }}
                      >
                        <View
                          style={{
                            flexDirection: "row",
                            gap: 8,
                            paddingVertical: 4,
                          }}
                        >
                          {matrixRows.map((row) => (
                            <Pressable
                              key={String(row.date)}
                              style={[
                                ui.chip,
                                row.is_season ? ui.chipOn : null,
                              ]}
                              onPress={() => editMatrixCell(row)}
                            >
                              <Text
                                style={[
                                  ui.chipText,
                                  row.is_season ? ui.chipTextOn : null,
                                  { fontSize: 11 },
                                ]}
                              >
                                {String(row.date).slice(5)}
                              </Text>
                              <Text
                                style={[
                                  ui.chipText,
                                  row.is_season ? ui.chipTextOn : null,
                                  { fontWeight: "700" },
                                ]}
                              >
                                {String(row.price)}
                              </Text>
                            </Pressable>
                          ))}
                        </View>
                      </ScrollView>
                    )
                  ) : null}
                </View>
              ))}
            </>
          ) : null}
        </ScrollView>
      )}
    </View>
  );
}
