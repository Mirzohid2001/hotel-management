import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../api/client";
import type {
  BoardTile,
  MinibarItem,
  ReservationDetail,
  ServiceItem,
} from "../api/types";
import { useAuth } from "../auth/AuthContext";

type Props = {
  reservationId: number;
  onBack: () => void;
  onChanged: () => void;
};

const STATUS_LABEL: Record<string, string> = {
  confirmed: "Tasdiqlangan",
  checked_in: "Joylashgan",
  checked_out: "Chiqqan",
  cancelled: "Bekor",
  no_show: "Kelmagan",
  inquiry: "So‘rov",
};

const PAY_METHODS = [
  { id: "cash", label: "Naqd" },
  { id: "card", label: "Karta" },
  { id: "transfer", label: "O‘tkazma" },
] as const;

type Panel = "none" | "pay" | "charge" | "service" | "transfer" | "deposit" | "minibar" | "amend" | "split";
type VacantRoom = BoardTile["room"];

export function ReservationDetailScreen({
  reservationId,
  onBack,
  onChanged,
}: Props) {
  const {
    fetchReservation,
    fetchBoard,
    checkIn,
    checkOut,
    postPayment,
    postCharge,
    fetchServices,
    orderService,
    transferRoom,
    extendStay,
    cancelReservation,
    markNoShow,
    saveNotes,
    postDeposit,
    postRefund,
    fetchMinibarItems,
    postMinibar,
    confirmInquiry,
    voidCharge,
    voidPayment,
    amendReservation,
    postEmehmon,
    fetchReceipt,
    transferToCompany,
    closeFolio,
    splitPay,
    me,
  } = useAuth();
  const [data, setData] = useState<ReservationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>("none");
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] =
    useState<(typeof PAY_METHODS)[number]["id"]>("cash");
  const [chargeDesc, setChargeDesc] = useState("");
  const [chargeAmount, setChargeAmount] = useState("");
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [vacantRooms, setVacantRooms] = useState<VacantRoom[]>([]);
  const [notesDraft, setNotesDraft] = useState("");
  const [editingNotes, setEditingNotes] = useState(false);
  const [minibarItems, setMinibarItems] = useState<MinibarItem[]>([]);
  const [depositAmount, setDepositAmount] = useState("");
  const [amendOut, setAmendOut] = useState("");
  const [amendRate, setAmendRate] = useState("");
  const [splitA, setSplitA] = useState("");
  const [splitB, setSplitB] = useState("");

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const d = await fetchReservation(reservationId);
      setData(d);
      setNotesDraft(d.notes || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Yuklash xatosi");
    } finally {
      setLoading(false);
    }
  }, [fetchReservation, reservationId]);

  useEffect(() => {
    load();
  }, [load]);

  const canStay =
    me?.permissions?.floor_view === true ||
    ["admin", "manager", "receptionist"].includes(me?.role || "");

  const canPay =
    me?.permissions?.cash === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");

  const canService =
    me?.permissions?.services === true ||
    ["admin", "receptionist"].includes(me?.role || "");

  const canInventory =
    me?.permissions?.inventory === true ||
    ["admin", "receptionist", "accountant"].includes(me?.role || "");

  const canVoid = ["admin", "accountant"].includes(me?.role || "");

  async function doCheckIn(force?: {
    allow_dirty?: boolean;
    allow_no_docs?: boolean;
  }) {
    setBusy(true);
    setError(null);
    try {
      const result = await checkIn(reservationId, {
        allow_dirty: force?.allow_dirty,
        allow_no_docs: force?.allow_no_docs,
        collect_emehmon: true,
      });
      await load();
      onChanged();
      const extra =
        result.emehmon && result.emehmon !== "collected"
          ? `\nE-mehmon: ${result.emehmon}`
          : result.emehmon === "collected"
            ? "\nE-mehmon olindi."
            : "";
      Alert.alert("Kirish", `Joylashdi.${extra}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Kirish xatosi";
      if (/kir|dirty|tozala/i.test(msg)) {
        Alert.alert("Xona holati", msg, [
          { text: "Bekor", style: "cancel" },
          {
            text: "Baribir kirish",
            onPress: () => doCheckIn({ allow_dirty: true }),
          },
        ]);
      } else if (/hujjat|pasport|ID/i.test(msg)) {
        Alert.alert("Hujjat", msg, [
          { text: "Bekor", style: "cancel" },
          {
            text: "Hujjatsiz kirish",
            onPress: () => doCheckIn({ allow_no_docs: true }),
          },
        ]);
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  async function doCheckOut() {
    Alert.alert("Chiqish", "Mehmonni chiqarishni tasdiqlaysizmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "Chiqish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            await checkOut(reservationId);
            await load();
            onChanged();
            Alert.alert("Chiqish", "Mehmon chiqarildi.");
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Chiqish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function doPayment() {
    const amount = payAmount.trim().replace(/\s/g, "").replace(",", ".");
    if (!amount || Number(amount) <= 0) {
      setError("To‘lov summasini kiriting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await postPayment(reservationId, amount, payMethod);
      setPayAmount("");
      setPanel("none");
      await load();
      onChanged();
      Alert.alert(
        "To‘lov",
        `${result.amount} qabul qilindi.\nBalans: ${result.balance}`
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "To‘lov xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doCharge() {
    const price = chargeAmount.trim().replace(/\s/g, "").replace(",", ".");
    const desc = chargeDesc.trim();
    if (!desc || !price || Number(price) < 0) {
      setError("Tavsif va summani kiriting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await postCharge(reservationId, {
        description: desc,
        unit_price: price,
        charge_type: "other",
      });
      setChargeDesc("");
      setChargeAmount("");
      setPanel("none");
      await load();
      onChanged();
      Alert.alert("Hisob", `+${result.amount}\nBalans: ${result.balance}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yozuv xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function openServices() {
    setError(null);
    setBusy(true);
    try {
      setServices(await fetchServices());
      setPanel("service");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Xizmatlar yuklanmadi");
    } finally {
      setBusy(false);
    }
  }

  async function doOrderService(item: ServiceItem) {
    setBusy(true);
    setError(null);
    try {
      const result = await orderService(reservationId, item.id);
      setPanel("none");
      await load();
      onChanged();
      Alert.alert(
        "Xizmat",
        `${result.service}: ${result.amount}` +
          (result.balance ? `\nBalans: ${result.balance}` : "")
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Xizmat xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doExtend() {
    Alert.alert("Uzaytirish", "Yana 1 kecha qo‘shilsinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "+1 kecha",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            const result = await extendStay(reservationId, 1);
            await load();
            onChanged();
            Alert.alert(
              "Uzaytirildi",
              `Chiqish: ${result.check_out}`
            );
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Uzaytirish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function openTransfer() {
    setError(null);
    setBusy(true);
    try {
      const board = await fetchBoard();
      const rooms = board.tiles
        .filter(
          (t) =>
            (t.state === "vacant" || t.state === "dirty") &&
            t.room.id !== data?.room.id
        )
        .map((t) => t.room)
        .sort((a, b) => a.number.localeCompare(b.number, undefined, { numeric: true }));
      setVacantRooms(rooms);
      setPanel("transfer");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Xonalar yuklanmadi");
    } finally {
      setBusy(false);
    }
  }

  async function doTransfer(room: VacantRoom) {
    Alert.alert(
      "Xona almashtirish",
      `${data?.room.number || "—"} → ${room.number}?`,
      [
        { text: "Bekor", style: "cancel" },
        {
          text: "O‘tkazish",
          onPress: async () => {
            setBusy(true);
            setError(null);
            try {
              const result = await transferRoom(reservationId, room.id);
              setPanel("none");
              await load();
              onChanged();
              Alert.alert("O‘tkazildi", `Yangi xona: ${result.room.number}`);
            } catch (e) {
              setError(
                e instanceof ApiError ? e.message : "O‘tkazish xatosi"
              );
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  }

  function doCancel() {
    Alert.alert("Bekor qilish", "Bronni bekor qilasizmi?", [
      { text: "Yo‘q", style: "cancel" },
      {
        text: "Bekor qilish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            await cancelReservation(reservationId);
            await load();
            onChanged();
            Alert.alert("Bekor", "Bron bekor qilindi.");
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Bekor qilish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  function doNoShow() {
    Alert.alert("Kelmagan", "Mehmon kelmagan deb belgilansinmi?", [
      { text: "Yo‘q", style: "cancel" },
      {
        text: "Kelmagan",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            await markNoShow(reservationId);
            await load();
            onChanged();
            Alert.alert("Kelmagan", "Bron yangilandi.");
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Xato");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function doSaveNotes() {
    setBusy(true);
    setError(null);
    try {
      const notes = await saveNotes(reservationId, notesDraft);
      setEditingNotes(false);
      setData((prev) => (prev ? { ...prev, notes } : prev));
      Alert.alert("Izoh", "Saqlandi.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Izoh xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doDeposit() {
    const amount = depositAmount.trim().replace(/\s/g, "").replace(",", ".");
    if (!amount || Number(amount) <= 0) {
      setError("Depozit summasini kiriting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await postDeposit(reservationId, amount, payMethod);
      setDepositAmount("");
      setPanel("none");
      await load();
      onChanged();
      Alert.alert("Depozit", `${result.amount}\nBalans: ${result.balance}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Depozit xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doRefund() {
    Alert.alert("Sdachi", "Ortgan summani qaytaramizmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "Qaytarish",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            const result = await postRefund(reservationId, undefined, payMethod);
            await load();
            onChanged();
            Alert.alert("Qaytarildi", `${result.amount}\nBalans: ${result.balance}`);
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Qaytarish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function openMinibar() {
    setBusy(true);
    setError(null);
    try {
      setMinibarItems(await fetchMinibarItems());
      setPanel("minibar");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Minibar yuklanmadi");
    } finally {
      setBusy(false);
    }
  }

  async function doMinibar(item: MinibarItem) {
    setBusy(true);
    setError(null);
    try {
      const result = await postMinibar(reservationId, item.id);
      setPanel("none");
      await load();
      onChanged();
      Alert.alert(
        "Minibar",
        `${result.item}: ${result.amount}` +
          (result.balance ? `\nBalans: ${result.balance}` : "")
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Minibar xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doConfirm() {
    setBusy(true);
    setError(null);
    try {
      await confirmInquiry(reservationId);
      await load();
      onChanged();
      Alert.alert("Tasdiq", "So‘rov tasdiqlandi.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Tasdiqlash xatosi");
    } finally {
      setBusy(false);
    }
  }

  function askVoidCharge(id: number, desc: string) {
    Alert.alert("Bekor qilish", `"${desc}" yozuvini bekor qilasizmi?`, [
      { text: "Yo‘q", style: "cancel" },
      {
        text: "Bekor qilish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            await voidCharge(id, "Mobile void");
            await load();
            onChanged();
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Void xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  function askVoidPayment(id: number, amount: string) {
    Alert.alert("Bekor qilish", `To‘lov ${amount} bekor qilinsinmi?`, [
      { text: "Yo‘q", style: "cancel" },
      {
        text: "Bekor qilish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            await voidPayment(id, "Mobile void");
            await load();
            onChanged();
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "Void xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function doAmend() {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await amendReservation(reservationId, {
        check_out: amendOut.trim() || data.check_out,
        nightly_rate: amendRate.trim() || undefined,
        reason: "mobile amend",
      });
      setPanel("none");
      await load();
      onChanged();
      Alert.alert("Bron", "O‘zgartirildi");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Amend xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doEmehmon() {
    setBusy(true);
    setError(null);
    try {
      const r = await postEmehmon(reservationId, "cash");
      await load();
      onChanged();
      Alert.alert("E-mehmon", `Yozildi: ${r.amount}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "E-mehmon xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doReceipt() {
    if (!data?.folio?.id) return;
    setBusy(true);
    try {
      const r = await fetchReceipt(data.folio.id);
      const charges = (Array.isArray(r.charges) ? r.charges : []) as {
        description?: string;
        amount?: string;
      }[];
      const lines = charges
        .slice(0, 8)
        .map((c) => `${c.description || "?"}: ${c.amount || ""}`)
        .join("\n");
      Alert.alert(
        "Chek",
        `Balans: ${String(r.balance ?? "")}\n\n${lines || "Yozuv yo‘q"}`
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Chek xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doToCompany() {
    if (!data?.folio?.id) return;
    Alert.alert("City ledger", "Ochiq yozuvlar kompaniyaga o‘tkazilsinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "O‘tkazish",
        onPress: async () => {
          setBusy(true);
          try {
            const r = await transferToCompany(data.folio!.id);
            await load();
            onChanged();
            Alert.alert("City ledger", `Faktura: ${String(r.code ?? "")}`);
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "O‘tkazish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function doCloseFolio() {
    if (!data?.folio?.id) return;
    setBusy(true);
    try {
      await closeFolio(data.folio.id);
      await load();
      onChanged();
      Alert.alert("Folio", "Yopildi");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Yopish xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doSplitPay() {
    if (!data?.folio?.id) return;
    const a = splitA.trim();
    const b = splitB.trim();
    if (!a && !b) {
      setError("Kamida bitta summa kerak");
      return;
    }
    const lines: { amount: string; method?: string }[] = [];
    if (a) lines.push({ amount: a, method: "cash" });
    if (b) lines.push({ amount: b, method: "card" });
    setBusy(true);
    setError(null);
    try {
      await splitPay(data.folio.id, lines);
      setPanel("none");
      setSplitA("");
      setSplitB("");
      await load();
      onChanged();
      Alert.alert("To‘lov", "Bo‘lib to‘landi");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Bo‘lish xatosi");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator size="large" color="#0e6b56" />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.boot}>
        <Text style={styles.error}>{error || "Topilmadi"}</Text>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backBtnText}>← Doska</Text>
        </Pressable>
      </View>
    );
  }

  const statusLabel = STATUS_LABEL[data.status] || data.status;
  const showCheckIn = canStay && data.status === "confirmed";
  const showCheckOut = canStay && data.status === "checked_in";
  const showConfirm = canStay && data.status === "inquiry";
  const showExtend =
    canStay &&
    (data.status === "checked_in" || data.status === "confirmed");
  const showTransfer = canStay && data.status === "checked_in";
  const showCancel =
    canStay &&
    (data.status === "confirmed" || data.status === "inquiry");
  const showNoShow = canStay && data.status === "confirmed";
  const showNotes =
    canStay &&
    !["cancelled", "checked_out", "no_show"].includes(data.status);
  const folioOpen = !!data.folio?.is_open;
  const showMoney =
    canPay &&
    (data.status === "checked_in" ||
      data.status === "confirmed" ||
      data.status === "inquiry");
  const showService =
    canService &&
    folioOpen &&
    (data.status === "checked_in" || data.status === "confirmed");
  const showMinibar = canInventory && data.status === "checked_in";
  const charges = data.folio?.charges || [];
  const payments = data.folio?.payments || [];

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable onPress={onBack} hitSlop={12}>
          <Text style={styles.back}>← Doska</Text>
        </Pressable>
        <Text style={styles.code}>{data.code}</Text>
        <Text style={styles.status}>{statusLabel}</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.body}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.guest}>{data.guest.name || "—"}</Text>
        <Row label="Xona" value={data.room.number || "—"} />
        <Row label="Kirish" value={data.check_in} />
        <Row label="Chiqish" value={data.check_out} />
        <Row
          label="Mehmonlar"
          value={`${data.adults} katta${data.children ? ` · ${data.children} bola` : ""}`}
        />
        {data.folio ? <Row label="Balans" value={data.folio.balance} /> : null}

        <View style={styles.notesBox}>
          <View style={styles.notesHead}>
            <Text style={styles.notesTitle}>Izoh</Text>
            {showNotes && !editingNotes ? (
              <Pressable onPress={() => setEditingNotes(true)}>
                <Text style={styles.notesEdit}>Tahrirlash</Text>
              </Pressable>
            ) : null}
          </View>
          {editingNotes ? (
            <>
              <TextInput
                style={styles.notesInput}
                value={notesDraft}
                onChangeText={setNotesDraft}
                multiline
                placeholder="Izoh…"
                placeholderTextColor="#a89f94"
              />
              <View style={styles.notesActions}>
                <Pressable
                  style={styles.notesCancel}
                  onPress={() => {
                    setEditingNotes(false);
                    setNotesDraft(data.notes || "");
                  }}
                >
                  <Text style={styles.notesCancelText}>Bekor</Text>
                </Pressable>
                <Pressable
                  style={[styles.notesSave, busy && styles.disabled]}
                  onPress={doSaveNotes}
                  disabled={busy}
                >
                  <Text style={styles.actionText}>Saqlash</Text>
                </Pressable>
              </View>
            </>
          ) : (
            <Text style={styles.notesBody}>
              {data.notes?.trim() ? data.notes : "Izoh yo‘q"}
            </Text>
          )}
        </View>

        {(charges.length > 0 || payments.length > 0) && (
          <View style={styles.ledger}>
            <Text style={styles.ledgerTitle}>Hisob</Text>
            {charges.map((c) => (
              <Pressable
                key={`c-${c.id}`}
                style={styles.ledgerRow}
                disabled={!canVoid || c.is_void || busy}
                onLongPress={() => {
                  if (canVoid && !c.is_void) askVoidCharge(c.id, c.description);
                }}
              >
                <Text
                  style={[
                    styles.ledgerDesc,
                    c.is_void && styles.ledgerVoid,
                  ]}
                  numberOfLines={1}
                >
                  {c.is_void ? "∅ " : ""}
                  {c.description}
                </Text>
                <Text
                  style={[
                    styles.ledgerAmt,
                    c.is_void && styles.ledgerVoid,
                  ]}
                >
                  +{c.amount}
                </Text>
              </Pressable>
            ))}
            {payments.map((p) => (
              <Pressable
                key={`p-${p.id}`}
                style={styles.ledgerRow}
                disabled={!canVoid || p.is_void || busy}
                onLongPress={() => {
                  if (canVoid && !p.is_void) askVoidPayment(p.id, p.amount);
                }}
              >
                <Text
                  style={[
                    styles.ledgerDesc,
                    p.is_void && styles.ledgerVoid,
                  ]}
                  numberOfLines={1}
                >
                  {p.is_void ? "∅ " : ""}
                  To‘lov ({p.method})
                </Text>
                <Text
                  style={[
                    styles.ledgerAmt,
                    styles.ledgerPay,
                    p.is_void && styles.ledgerVoid,
                  ]}
                >
                  −{p.amount}
                </Text>
              </Pressable>
            ))}
            {canVoid ? (
              <Text style={styles.voidHint}>
                Bekor qilish: yozuvni uzoq bosib turing
              </Text>
            ) : null}
          </View>
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {showConfirm ? (
          <Pressable
            style={[styles.action, busy && styles.disabled]}
            onPress={doConfirm}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.actionText}>So‘rovni tasdiqlash</Text>
            )}
          </Pressable>
        ) : null}

        {showCheckIn ? (
          <Pressable
            style={[styles.action, busy && styles.disabled]}
            onPress={() => doCheckIn()}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.actionText}>Kirish (zayezd)</Text>
            )}
          </Pressable>
        ) : null}

        {showCheckOut ? (
          <Pressable
            style={[styles.action, styles.actionOut, busy && styles.disabled]}
            onPress={doCheckOut}
            disabled={busy}
          >
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.actionText}>Chiqish</Text>
            )}
          </Pressable>
        ) : null}

        {(showExtend || showTransfer) && (
          <View style={styles.actionRow}>
            {showExtend ? (
              <Pressable
                style={[styles.miniBtn, styles.miniExtend]}
                onPress={doExtend}
                disabled={busy}
              >
                <Text style={styles.miniText}>+1 kecha</Text>
              </Pressable>
            ) : null}
            {showTransfer ? (
              <Pressable
                style={[styles.miniBtn, styles.miniTransfer]}
                onPress={openTransfer}
                disabled={busy}
              >
                <Text style={styles.miniText}>Xona almashtirish</Text>
              </Pressable>
            ) : null}
          </View>
        )}

        {(showCancel || showNoShow) && (
          <View style={styles.actionRow}>
            {showCancel ? (
              <Pressable
                style={[styles.miniBtn, styles.miniCancel]}
                onPress={doCancel}
                disabled={busy}
              >
                <Text style={styles.miniText}>Bekor qilish</Text>
              </Pressable>
            ) : null}
            {showNoShow ? (
              <Pressable
                style={[styles.miniBtn, styles.miniNoShow]}
                onPress={doNoShow}
                disabled={busy}
              >
                <Text style={styles.miniText}>Kelmagan</Text>
              </Pressable>
            ) : null}
          </View>
        )}

        {showMoney || showService || showMinibar ? (
          <View style={styles.actionRow}>
            {showMoney ? (
              <Pressable
                style={[styles.miniBtn, styles.miniPay]}
                onPress={() => setPanel(panel === "pay" ? "none" : "pay")}
                disabled={busy}
              >
                <Text style={styles.miniText}>To‘lov</Text>
              </Pressable>
            ) : null}
            {showMoney ? (
              <Pressable
                style={[styles.miniBtn, styles.miniDeposit]}
                onPress={() =>
                  setPanel(panel === "deposit" ? "none" : "deposit")
                }
                disabled={busy}
              >
                <Text style={styles.miniText}>Depozit</Text>
              </Pressable>
            ) : null}
            {showMoney ? (
              <Pressable
                style={[styles.miniBtn, styles.miniCharge]}
                onPress={() => setPanel(panel === "charge" ? "none" : "charge")}
                disabled={busy}
              >
                <Text style={styles.miniText}>Yozuv</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        {showMoney || showService || showMinibar ? (
          <View style={styles.actionRow}>
            {showMoney ? (
              <Pressable
                style={[styles.miniBtn, styles.miniRefund]}
                onPress={doRefund}
                disabled={busy}
              >
                <Text style={styles.miniText}>Sdachi</Text>
              </Pressable>
            ) : null}
            {showService ? (
              <Pressable
                style={[styles.miniBtn, styles.miniSvc]}
                onPress={openServices}
                disabled={busy}
              >
                <Text style={styles.miniText}>Xizmat</Text>
              </Pressable>
            ) : null}
            {showMinibar ? (
              <Pressable
                style={[styles.miniBtn, styles.miniMinibar]}
                onPress={openMinibar}
                disabled={busy}
              >
                <Text style={styles.miniText}>Minibar</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}

        <View style={styles.actionRow}>
          {showExtend || showCheckIn || showCheckOut ? (
            <Pressable
              style={[styles.miniBtn, styles.miniExtend]}
              onPress={() => {
                if (data) {
                  setAmendOut(data.check_out);
                  setAmendRate(data.nightly_rate || "");
                }
                setPanel(panel === "amend" ? "none" : "amend");
              }}
              disabled={busy}
            >
              <Text style={styles.miniText}>O‘zgartirish</Text>
            </Pressable>
          ) : null}
          {showMoney && data?.folio?.id ? (
            <Pressable
              style={[styles.miniBtn, styles.miniPay]}
              onPress={doReceipt}
              disabled={busy}
            >
              <Text style={styles.miniText}>Chek</Text>
            </Pressable>
          ) : null}
          {showMoney ? (
            <Pressable
              style={[styles.miniBtn, styles.miniCharge]}
              onPress={doEmehmon}
              disabled={busy}
            >
              <Text style={styles.miniText}>E-mehmon</Text>
            </Pressable>
          ) : null}
        </View>

        {showMoney && data?.folio?.id ? (
          <View style={styles.actionRow}>
            <Pressable
              style={[styles.miniBtn, styles.miniTransfer]}
              onPress={doToCompany}
              disabled={busy}
            >
              <Text style={styles.miniText}>Kompaniyaga</Text>
            </Pressable>
            <Pressable
              style={[styles.miniBtn, styles.miniCancel]}
              onPress={doCloseFolio}
              disabled={busy}
            >
              <Text style={styles.miniText}>Folio yopish</Text>
            </Pressable>
            <Pressable
              style={[styles.miniBtn, styles.miniPay]}
              onPress={() => setPanel(panel === "split" ? "none" : "split")}
              disabled={busy}
            >
              <Text style={styles.miniText}>Bo‘lish</Text>
            </Pressable>
          </View>
        ) : null}

        {panel === "amend" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Bronni o‘zgartirish</Text>
            <TextInput
              style={styles.payInput}
              value={amendOut}
              onChangeText={setAmendOut}
              placeholder="Chiqish (YYYY-MM-DD)"
              placeholderTextColor="#a89f94"
              autoCapitalize="none"
            />
            <TextInput
              style={styles.payInput}
              value={amendRate}
              onChangeText={setAmendRate}
              keyboardType="decimal-pad"
              placeholder="Kunlik narx"
              placeholderTextColor="#a89f94"
            />
            <Pressable
              style={[styles.paySubmit, busy && styles.disabled]}
              onPress={doAmend}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.actionText}>Saqlash</Text>
              )}
            </Pressable>
          </View>
        ) : null}

        {panel === "split" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Bo‘lib to‘lash</Text>
            <TextInput
              style={styles.payInput}
              value={splitA}
              onChangeText={setSplitA}
              keyboardType="decimal-pad"
              placeholder="Naqd"
              placeholderTextColor="#a89f94"
            />
            <TextInput
              style={styles.payInput}
              value={splitB}
              onChangeText={setSplitB}
              keyboardType="decimal-pad"
              placeholder="Karta"
              placeholderTextColor="#a89f94"
            />
            <Pressable
              style={[styles.paySubmit, busy && styles.disabled]}
              onPress={doSplitPay}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.actionText}>To‘lash</Text>
              )}
            </Pressable>
          </View>
        ) : null}

        {panel === "pay" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>To‘lov</Text>
            <TextInput
              style={styles.payInput}
              value={payAmount}
              onChangeText={setPayAmount}
              keyboardType="decimal-pad"
              placeholder="Summa"
              placeholderTextColor="#a89f94"
            />
            <View style={styles.methodRow}>
              {PAY_METHODS.map((m) => (
                <Pressable
                  key={m.id}
                  style={[
                    styles.methodChip,
                    payMethod === m.id && styles.methodChipOn,
                  ]}
                  onPress={() => setPayMethod(m.id)}
                >
                  <Text
                    style={[
                      styles.methodText,
                      payMethod === m.id && styles.methodTextOn,
                    ]}
                  >
                    {m.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Pressable
              style={[styles.paySubmit, busy && styles.disabled]}
              onPress={doPayment}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.actionText}>Qabul qilish</Text>
              )}
            </Pressable>
          </View>
        ) : null}

        {panel === "deposit" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Depozit</Text>
            <TextInput
              style={styles.payInput}
              value={depositAmount}
              onChangeText={setDepositAmount}
              keyboardType="decimal-pad"
              placeholder="Summa"
              placeholderTextColor="#a89f94"
            />
            <View style={styles.methodRow}>
              {PAY_METHODS.map((m) => (
                <Pressable
                  key={m.id}
                  style={[
                    styles.methodChip,
                    payMethod === m.id && styles.methodChipOn,
                  ]}
                  onPress={() => setPayMethod(m.id)}
                >
                  <Text
                    style={[
                      styles.methodText,
                      payMethod === m.id && styles.methodTextOn,
                    ]}
                  >
                    {m.label}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Pressable
              style={[styles.paySubmit, styles.depositSubmit, busy && styles.disabled]}
              onPress={doDeposit}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.actionText}>Depozit olish</Text>
              )}
            </Pressable>
          </View>
        ) : null}

        {panel === "minibar" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Minibar</Text>
            {minibarItems.length === 0 ? (
              <Text style={styles.emptySvc}>Mahsulot yo‘q</Text>
            ) : (
              minibarItems.map((s) => (
                <Pressable
                  key={s.id}
                  style={styles.svcRow}
                  onPress={() => doMinibar(s)}
                  disabled={busy}
                >
                  <Text style={styles.svcName}>{s.name}</Text>
                  <Text style={styles.svcPrice}>{s.sell_price}</Text>
                </Pressable>
              ))
            )}
          </View>
        ) : null}

        {panel === "charge" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Qo‘shimcha yozuv</Text>
            <TextInput
              style={styles.payInput}
              value={chargeDesc}
              onChangeText={setChargeDesc}
              placeholder="Masalan: Minibar"
              placeholderTextColor="#a89f94"
            />
            <TextInput
              style={styles.payInput}
              value={chargeAmount}
              onChangeText={setChargeAmount}
              keyboardType="decimal-pad"
              placeholder="Summa"
              placeholderTextColor="#a89f94"
            />
            <Pressable
              style={[styles.paySubmit, styles.chargeSubmit, busy && styles.disabled]}
              onPress={doCharge}
              disabled={busy}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.actionText}>Hisobga yozish</Text>
              )}
            </Pressable>
          </View>
        ) : null}

        {panel === "service" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Xizmatlar</Text>
            {services.length === 0 ? (
              <Text style={styles.emptySvc}>Katalog bo‘sh</Text>
            ) : (
              services.map((s) => (
                <Pressable
                  key={s.id}
                  style={styles.svcRow}
                  onPress={() => doOrderService(s)}
                  disabled={busy}
                >
                  <Text style={styles.svcName}>{s.name}</Text>
                  <Text style={styles.svcPrice}>{s.unit_price}</Text>
                </Pressable>
              ))
            )}
          </View>
        ) : null}

        {panel === "transfer" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Bo‘sh xonaga o‘tkazish</Text>
            {vacantRooms.length === 0 ? (
              <Text style={styles.emptySvc}>Bo‘sh xona yo‘q</Text>
            ) : (
              vacantRooms.map((r) => (
                <Pressable
                  key={r.id}
                  style={styles.svcRow}
                  onPress={() => doTransfer(r)}
                  disabled={busy}
                >
                  <Text style={styles.svcName}>
                    {r.number}
                    {r.room_type ? ` · ${r.room_type}` : ""}
                  </Text>
                  <Text style={styles.svcPrice}>{r.status}</Text>
                </Pressable>
              ))
            )}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLbl}>{label}</Text>
      <Text style={styles.rowVal}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#eef0f3" },
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#eef0f3",
    padding: 24,
  },
  header: {
    backgroundColor: "#12151a",
    paddingTop: 56,
    paddingBottom: 18,
    paddingHorizontal: 18,
  },
  back: { color: "#e8a86a", fontWeight: "600", marginBottom: 10 },
  code: { color: "#fff", fontSize: 22, fontWeight: "700" },
  status: { color: "rgba(245,239,230,0.75)", marginTop: 4 },
  body: { padding: 18, paddingBottom: 40 },
  guest: {
    fontSize: 28,
    fontWeight: "600",
    color: "#12151a",
    marginBottom: 16,
    fontFamily: "Georgia",
  },
  notesBox: {
    backgroundColor: "#faf6f1",
    borderRadius: 16,
    padding: 14,
    marginBottom: 8,
  },
  notesHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  notesTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: "#7a7168",
    letterSpacing: 0.4,
  },
  notesEdit: { color: "#0e6b56", fontWeight: "700", fontSize: 13 },
  notesBody: { color: "#12151a", fontSize: 15, lineHeight: 22 },
  notesInput: {
    borderWidth: 1,
    borderColor: "#d9cfc3",
    borderRadius: 10,
    padding: 10,
    minHeight: 80,
    textAlignVertical: "top",
    color: "#12151a",
    fontSize: 15,
  },
  notesActions: { flexDirection: "row", gap: 8, marginTop: 10 },
  notesCancel: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#d9cfc3",
  },
  notesCancelText: { fontWeight: "600", color: "#7a7168" },
  notesSave: {
    flex: 2,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    backgroundColor: "#0e6b56",
  },
  row: {
    backgroundColor: "#faf6f1",
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
  },
  rowLbl: {
    fontSize: 11,
    fontWeight: "700",
    color: "#7a7168",
    letterSpacing: 0.4,
  },
  rowVal: { fontSize: 16, fontWeight: "600", color: "#12151a", marginTop: 4 },
  ledger: {
    marginTop: 8,
    marginBottom: 8,
    backgroundColor: "#faf6f1",
    borderRadius: 14,
    padding: 14,
  },
  ledgerTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#7a7168",
    marginBottom: 8,
  },
  ledgerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#e8e2da",
  },
  ledgerDesc: { flex: 1, color: "#12151a", fontSize: 14 },
  ledgerAmt: { fontWeight: "700", color: "#12151a" },
  ledgerPay: { color: "#2a6b4f" },
  ledgerVoid: { color: "#a89f94", textDecorationLine: "line-through" },
  voidHint: {
    marginTop: 8,
    fontSize: 11,
    color: "#a89f94",
  },
  error: { color: "#9f2f28", marginVertical: 12 },
  action: {
    marginTop: 16,
    backgroundColor: "#0e6b56",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  actionOut: { backgroundColor: "#221c18" },
  actionText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  actionRow: { flexDirection: "row", gap: 8, marginTop: 16 },
  miniBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
  },
  miniPay: { backgroundColor: "#2a6b4f" },
  miniDeposit: { backgroundColor: "#2a6b4f" },
  miniRefund: { backgroundColor: "#221c18" },
  miniCharge: { backgroundColor: "#221c18" },
  miniSvc: { backgroundColor: "#221c18" },
  miniMinibar: { backgroundColor: "#221c18" },
  miniExtend: { backgroundColor: "#221c18" },
  miniTransfer: { backgroundColor: "#221c18" },
  miniCancel: { backgroundColor: "#9f2f28" },
  miniNoShow: { backgroundColor: "#7a7168" },
  miniText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.7 },
  backBtn: {
    marginTop: 16,
    padding: 12,
    backgroundColor: "#0e6b56",
    borderRadius: 10,
  },
  backBtnText: { color: "#fff", fontWeight: "700" },
  payBox: {
    marginTop: 12,
    backgroundColor: "#fff",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#d9cfc3",
    padding: 14,
  },
  payTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#12151a",
    marginBottom: 10,
  },
  payInput: {
    borderWidth: 1,
    borderColor: "#d9cfc3",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    fontWeight: "600",
    color: "#12151a",
    marginBottom: 10,
  },
  methodRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  methodChip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#d9cfc3",
    alignItems: "center",
    backgroundColor: "#faf6f1",
  },
  methodChipOn: {
    backgroundColor: "#2a6b4f",
    borderColor: "#2a6b4f",
  },
  methodText: { fontWeight: "600", color: "#221c18", fontSize: 13 },
  methodTextOn: { color: "#fff" },
  paySubmit: {
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    backgroundColor: "#2a6b4f",
  },
  depositSubmit: { backgroundColor: "#1f6b5c" },
  chargeSubmit: { backgroundColor: "#8a5a2b" },
  emptySvc: { color: "#7a7168", paddingVertical: 8 },
  svcRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#e8e2da",
  },
  svcName: { fontWeight: "600", color: "#12151a", flex: 1 },
  svcPrice: { fontWeight: "700", color: "#3a4f6b" },
});
