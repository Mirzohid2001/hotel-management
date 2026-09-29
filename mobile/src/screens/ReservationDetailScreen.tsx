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
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  FieldLabel,
  FormCard,
  PrimaryButton,
  SegmentedTabs,
  StatsStrip,
  StatusBadge,
} from "../ui/primitives";
import { colors, fontUi, radius, space, ui } from "../ui/theme";
import { sharePdfBase64 } from "../utils/sharePdf";

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

type Panel =
  | "none"
  | "pay"
  | "charge"
  | "service"
  | "transfer"
  | "deposit"
  | "minibar"
  | "amend"
  | "split"
  | "emehmon"
  | "checkin";
type VacantRoom = BoardTile["room"];

const DOC_TYPES = [
  { id: "passport", label: "Pasport" },
  { id: "id_card", label: "ID karta" },
] as const;

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
    syncOccupants,
    postEmehmon,
    fetchReceipt,
    transferToCompany,
    closeFolio,
    splitPay,
    fetchCompanies,
    fetchReferrers,
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
  const [amendIn, setAmendIn] = useState("");
  const [amendOut, setAmendOut] = useState("");
  const [amendRate, setAmendRate] = useState("");
  const [amendAdults, setAmendAdults] = useState("");
  const [amendChildren, setAmendChildren] = useState("");
  const [amendCompanyId, setAmendCompanyId] = useState<number | null>(null);
  const [amendReferrerId, setAmendReferrerId] = useState<number | null>(null);
  const [companies, setCompanies] = useState<{ id: number; name: string }[]>([]);
  const [referrers, setReferrers] = useState<
    { id: number; name: string; percent: string }[]
  >([]);
  const [updateRate, setUpdateRate] = useState(true);
  const [occFirst, setOccFirst] = useState("");
  const [occLast, setOccLast] = useState("");
  const [occPhone, setOccPhone] = useState("");
  const [occKind, setOccKind] = useState<"adult" | "child">("adult");
  const [occNationality, setOccNationality] = useState("UZ");
  const [occDocType, setOccDocType] = useState<"passport" | "id_card">("passport");
  const [occDocNumber, setOccDocNumber] = useState("");
  const [occIssuedCountry, setOccIssuedCountry] = useState("UZ");
  const [emehmonAmount, setEmehmonAmount] = useState("");
  const [emehmonMethod, setEmehmonMethod] =
    useState<(typeof PAY_METHODS)[number]["id"]>("cash");
  const [collectEmehmon, setCollectEmehmon] = useState(true);
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
    if (!force && panel !== "checkin") {
      setEmehmonAmount(data?.emehmon_default || "");
      setEmehmonMethod("cash");
      setCollectEmehmon(true);
      setPanel("checkin");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await checkIn(reservationId, {
        allow_dirty: force?.allow_dirty,
        allow_no_docs: force?.allow_no_docs,
        collect_emehmon: collectEmehmon,
        emehmon_method: emehmonMethod,
        emehmon_amount: collectEmehmon
          ? emehmonAmount.trim() || undefined
          : undefined,
      });
      setPanel("none");
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
      } else if (/hujjat|pasport|ID|mehmon/i.test(msg)) {
        Alert.alert("Hujjat / mehmonlar", msg, [
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
              const result = await transferRoom(reservationId, room.id, {
                update_rate: updateRate,
              });
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
      const adultsParsed = amendAdults.trim()
        ? Number(amendAdults.trim())
        : undefined;
      const childrenParsed = amendChildren.trim()
        ? Number(amendChildren.trim())
        : undefined;
      await amendReservation(reservationId, {
        check_in: amendIn.trim() || data.check_in,
        check_out: amendOut.trim() || data.check_out,
        nightly_rate: amendRate.trim() || undefined,
        adults:
          adultsParsed !== undefined && !Number.isNaN(adultsParsed)
            ? adultsParsed
            : undefined,
        children:
          childrenParsed !== undefined && !Number.isNaN(childrenParsed)
            ? childrenParsed
            : undefined,
        company_id: amendCompanyId,
        referrer_id: amendReferrerId,
        commission_percent: amendReferrerId
          ? referrers.find((r) => r.id === amendReferrerId)?.percent ?? undefined
          : null,
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

  async function doAddCompanion() {
    if (!data) return;
    const first = occFirst.trim();
    if (!first) {
      setError("Hamroh ismini kiriting.");
      return;
    }
    if (!occDocNumber.trim()) {
      setError("Pasport / ID raqamini kiriting (web bilan bir xil).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const existing = (data.occupants || [])
        .filter((o) => !o.is_primary)
        .map((o) => ({
          guest_id: o.guest.id,
          kind: o.kind || "adult",
          first_name: o.guest.first_name || undefined,
          last_name: o.guest.last_name || undefined,
          phone: o.guest.phone || undefined,
          nationality: o.guest.nationality || undefined,
          doc_type: o.guest.documents?.[0]?.doc_type,
          doc_number: o.guest.documents?.[0]?.number,
          issued_country: o.guest.documents?.[0]?.issued_country,
        }));
      const companions = [
        ...existing,
        {
          first_name: first,
          last_name: occLast.trim(),
          phone: occPhone.trim(),
          kind: occKind,
          nationality: occNationality.trim() || "UZ",
          doc_type: occDocType,
          doc_number: occDocNumber.trim(),
          issued_country: occIssuedCountry.trim() || occNationality.trim() || "UZ",
        },
      ];
      await syncOccupants(reservationId, companions);

      // Headcount must match named people (E-mehmon = unit × nights × guests)
      const adultsNamed =
        1 + companions.filter((c) => (c.kind || "adult") !== "child").length;
      const childrenNamed = companions.filter(
        (c) => c.kind === "child"
      ).length;
      if (
        adultsNamed !== data.adults ||
        childrenNamed !== (data.children || 0)
      ) {
        await amendReservation(reservationId, {
          adults: adultsNamed,
          children: childrenNamed,
          reason: "occupant sync",
        });
      }

      setOccFirst("");
      setOccLast("");
      setOccPhone("");
      setOccKind("adult");
      setOccNationality("UZ");
      setOccDocType("passport");
      setOccDocNumber("");
      setOccIssuedCountry("UZ");
      await load();
      onChanged();
      Alert.alert(
        "Mehmonlar",
        `Hamroh qo‘shildi · E-mehmon: ${adultsNamed + childrenNamed} kishi`
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Hamroh xatosi");
    } finally {
      setBusy(false);
    }
  }

  async function doRemoveCompanion(guestId: number) {
    if (!data) return;
    Alert.alert("Hamroh", "Bu mehmon xonadan olib tashlansinmi?", [
      { text: "Bekor", style: "cancel" },
      {
        text: "O‘chirish",
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          setError(null);
          try {
            const companions = (data.occupants || [])
              .filter((o) => !o.is_primary && o.guest.id !== guestId)
              .map((o) => ({
                guest_id: o.guest.id,
                kind: o.kind || "adult",
              }));
            await syncOccupants(reservationId, companions);
            const adultsNamed =
              1 +
              companions.filter((c) => (c.kind || "adult") !== "child").length;
            const childrenNamed = companions.filter(
              (c) => c.kind === "child"
            ).length;
            await amendReservation(reservationId, {
              adults: Math.max(1, adultsNamed),
              children: childrenNamed,
              reason: "occupant remove",
            });
            await load();
            onChanged();
          } catch (e) {
            setError(e instanceof ApiError ? e.message : "O‘chirish xatosi");
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  async function doEmehmon() {
    if (panel !== "emehmon") {
      setEmehmonAmount(data?.emehmon_default || "");
      setEmehmonMethod("cash");
      setPanel("emehmon");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await postEmehmon(reservationId, {
        method: emehmonMethod,
        amount: emehmonAmount.trim() || undefined,
      });
      setPanel("none");
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
      const r = await fetchReceipt(data.folio.id, true);
      const charges = (Array.isArray(r.charges) ? r.charges : []) as {
        description?: string;
        amount?: string;
      }[];
      const lines = charges
        .slice(0, 8)
        .map((c) => `${c.description || "?"}: ${c.amount || ""}`)
        .join("\n");
      const pdfB64 = typeof r.pdf_base64 === "string" ? r.pdf_base64 : "";
      const filename =
        typeof r.filename === "string" ? r.filename : `invoice-${data.code}.pdf`;
      if (pdfB64) {
        Alert.alert(
          "Chek",
          `Balans: ${String(r.balance ?? "")}\n\n${lines || "Yozuv yo‘q"}`,
          [
            { text: "OK", style: "cancel" },
            {
              text: "PDF ulashish",
              onPress: () => sharePdfBase64(pdfB64, filename),
            },
          ]
        );
      } else {
        Alert.alert(
          "Chek",
          `Balans: ${String(r.balance ?? "")}\n\n${lines || "Yozuv yo‘q"}`
        );
      }
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
        <ActivityIndicator size="large" color="#c45c26" />
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
  const statusTone =
    data.status === "checked_in"
      ? ("success" as const)
      : data.status === "confirmed"
        ? ("accent" as const)
        : data.status === "cancelled" || data.status === "no_show"
          ? ("danger" as const)
          : data.status === "inquiry"
            ? ("warn" as const)
            : ("neutral" as const);
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
      <ScreenHeader
        eyebrow="Bron"
        title={data.guest.name || data.code}
        subtitle={`${data.room.number || "—"} · ${data.check_in} → ${data.check_out}`}
        onBack={onBack}
        right={<StatusBadge label={statusLabel} tone={statusTone} />}
      />

      {data.folio ? (
        <StatsStrip
          items={[
            { label: "Balans", value: data.folio.balance },
            {
              label: "Mehmonlar",
              value: `${data.adults}${data.children ? `+${data.children}` : ""}`,
            },
            { label: "Kod", value: data.code },
          ]}
        />
      ) : (
        <StatsStrip
          items={[
            { label: "Xona", value: data.room.number || "—" },
            {
              label: "Mehmonlar",
              value: `${data.adults}${data.children ? `+${data.children}` : ""}`,
            },
            { label: "Kod", value: data.code },
          ]}
        />
      )}

      <ScrollView
        contentContainerStyle={styles.body}
        keyboardShouldPersistTaps="handled"
      >
        <FormCard>
          <Row label="Xona" value={data.room.number || "—"} />
          <Row label="Kirish" value={data.check_in} />
          <Row label="Chiqish" value={data.check_out} />
          <Row
            label="Mehmonlar"
            value={`${data.adults} katta${data.children ? ` · ${data.children} bola` : ""}`}
          />
          {data.company?.name ? (
            <Row label="Kompaniya" value={data.company.name} />
          ) : null}
          {data.referrer?.name ? (
            <Row label="Yo‘naltiruvchi" value={data.referrer.name} />
          ) : null}
          {data.rate_plan?.name ? (
            <Row label="Tarif" value={data.rate_plan.name} />
          ) : null}
        </FormCard>

        <FormCard>
          <Text style={styles.ledgerTitle}>Xonadagi mehmonlar</Text>
          <Text style={styles.occHint}>
            Asosiy + hamrohlar. Har bir kishi: ism va pasport/ID. E-mehmon =
            tarif × kecha × mehmonlar soni.
          </Text>
          {(data.occupants || []).length === 0 ? (
            <Text style={styles.emptySvc}>Hali mehmonlar yozilmagan</Text>
          ) : (
            (data.occupants || []).map((o) => {
              const kindLabel = o.is_primary
                ? "Asosiy"
                : o.kind === "child"
                  ? "Bola"
                  : "Katta";
              const tone = o.is_primary
                ? ("accent" as const)
                : o.kind === "child"
                  ? ("info" as const)
                  : ("neutral" as const);
              const doc = o.guest?.documents?.[0];
              return (
                <View key={o.id} style={styles.occRow}>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={styles.occName} numberOfLines={1}>
                      {o.guest?.name || "—"}
                    </Text>
                    {o.guest?.phone ? (
                      <Text style={styles.occPhone}>{o.guest.phone}</Text>
                    ) : null}
                    {doc?.number ? (
                      <Text style={styles.occPhone}>
                        {doc.doc_type === "id_card" ? "ID" : "Pasport"} ·{" "}
                        {doc.number}
                        {doc.issued_country ? ` · ${doc.issued_country}` : ""}
                      </Text>
                    ) : (
                      <Text style={[styles.occPhone, { color: colors.warn }]}>
                        Hujjat yo‘q
                      </Text>
                    )}
                  </View>
                  <View style={{ alignItems: "flex-end", gap: 6 }}>
                    <StatusBadge label={kindLabel} tone={tone} />
                    {!o.is_primary &&
                    canStay &&
                    !["cancelled", "checked_out", "no_show"].includes(
                      data.status
                    ) ? (
                      <Pressable
                        onPress={() => doRemoveCompanion(o.guest.id)}
                        hitSlop={8}
                      >
                        <Text style={styles.occRemove}>O‘chirish</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
              );
            })
          )}
          {(data.occupants_missing ?? 0) > 0 ? (
            <Text style={styles.occWarn}>
              Yetishmayapti: {data.occupants_missing} mehmon
              {data.occupants_expected
                ? ` (kutiladi: ${data.occupants_expected})`
                : ""}
            </Text>
          ) : null}
          {data.emehmon_unit ? (
            <Text style={styles.occHint}>
              E-mehmon tarif: {data.emehmon_unit} × {data.nights ?? "?"} kecha ×{" "}
              {data.emehmon_guests ?? data.adults + (data.children || 0)} kishi
              {data.emehmon_default ? ` = ${data.emehmon_default}` : ""}
              {data.emehmon_paid ? " · olingan" : ""}
            </Text>
          ) : null}
          {canStay &&
          !["cancelled", "checked_out", "no_show"].includes(data.status) ? (
            <View style={styles.occForm}>
              <Text style={styles.ledgerTitle}>Yangi hamroh</Text>
              <Text style={styles.occHint}>
                Avval ism va pasport/ID. Qolgani ixtiyoriy.
              </Text>
              <FieldLabel>Ism *</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occFirst}
                onChangeText={(t) => {
                  setOccFirst(t);
                  if (
                    error === "Hamroh ismini kiriting." ||
                    error === "Pasport / ID raqamini kiriting (web bilan bir xil)."
                  ) {
                    setError(null);
                  }
                }}
                placeholder="Masalan: Ali"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Familiya</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occLast}
                onChangeText={setOccLast}
                placeholder="Familiya"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Pasport / ID *</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occDocNumber}
                onChangeText={setOccDocNumber}
                placeholder="AA 1234567"
                placeholderTextColor={colors.faint}
                autoCapitalize="characters"
              />
              <FieldLabel>Turi</FieldLabel>
              <SegmentedTabs
                tabs={[
                  { id: "adult", label: "Katta" },
                  { id: "child", label: "Bola" },
                ]}
                value={occKind}
                onChange={setOccKind}
              />
              {error === "Hamroh ismini kiriting." ||
              error === "Pasport / ID raqamini kiriting (web bilan bir xil)." ? (
                <Text style={styles.error}>{error}</Text>
              ) : null}
              <View style={{ marginTop: space.sm }}>
                <PrimaryButton
                  label="Hamroh qo‘shish"
                  onPress={doAddCompanion}
                  loading={busy}
                />
              </View>
              <FieldLabel>Telefon</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occPhone}
                onChangeText={setOccPhone}
                placeholder="+998…"
                keyboardType="phone-pad"
                placeholderTextColor={colors.faint}
              />
              <FieldLabel>Hujjat turi</FieldLabel>
              <SegmentedTabs
                tabs={DOC_TYPES.map((d) => ({ id: d.id, label: d.label }))}
                value={occDocType}
                onChange={setOccDocType}
              />
              <FieldLabel>Fuqarolik</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occNationality}
                onChangeText={setOccNationality}
                placeholder="UZ"
                placeholderTextColor={colors.faint}
                autoCapitalize="characters"
              />
              <FieldLabel>Berilgan mamlakat</FieldLabel>
              <TextInput
                style={styles.payInput}
                value={occIssuedCountry}
                onChangeText={setOccIssuedCountry}
                placeholder="UZ"
                placeholderTextColor={colors.faint}
                autoCapitalize="characters"
              />
            </View>
          ) : null}
        </FormCard>

        <FormCard>
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
              <FieldLabel>Matn</FieldLabel>
              <TextInput
                style={styles.notesInput}
                value={notesDraft}
                onChangeText={setNotesDraft}
                multiline
                placeholder="Izoh…"
                placeholderTextColor={colors.faint}
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
                <View style={{ flex: 2 }}>
                  <PrimaryButton
                    label="Saqlash"
                    onPress={doSaveNotes}
                    loading={busy}
                  />
                </View>
              </View>
            </>
          ) : (
            <Text style={styles.notesBody}>
              {data.notes?.trim() ? data.notes : "Izoh yo‘q"}
            </Text>
          )}
        </FormCard>

        {(charges.length > 0 || payments.length > 0) && (
          <FormCard>
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
          </FormCard>
        )}

        {error &&
        error !== "Hamroh ismini kiriting." &&
        error !== "Pasport / ID raqamini kiriting (web bilan bir xil)." ? (
          <Text style={styles.error}>{error}</Text>
        ) : null}

        {showConfirm ? (
          <PrimaryButton
            label="So‘rovni tasdiqlash"
            onPress={doConfirm}
            loading={busy}
            tone="success"
          />
        ) : null}

        {showCheckIn ? (
          <PrimaryButton
            label="Kirish (zayezd)"
            onPress={() => doCheckIn()}
            loading={busy}
            tone="success"
          />
        ) : null}

        {showCheckOut ? (
          <PrimaryButton
            label="Chiqish"
            onPress={doCheckOut}
            loading={busy}
            tone="ink"
          />
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
                  setAmendIn(data.check_in);
                  setAmendOut(data.check_out);
                  setAmendRate(data.nightly_rate || "");
                  setAmendAdults(String(data.adults ?? ""));
                  setAmendChildren(String(data.children ?? ""));
                  setAmendCompanyId(data.company?.id ?? null);
                  setAmendReferrerId(data.referrer?.id ?? null);
                }
                const opening = panel !== "amend";
                setPanel(opening ? "amend" : "none");
                if (opening && companies.length === 0 && referrers.length === 0) {
                  Promise.all([
                    fetchCompanies().catch(() => []),
                    fetchReferrers().catch(() => []),
                  ]).then(([cs, rs]) => {
                    setCompanies(
                      cs.map((c) => ({
                        id: Number(c.id),
                        name: String(c.name || ""),
                      }))
                    );
                    setReferrers(
                      rs.map((r) => ({
                        id: Number(r.id),
                        name: String(r.name || ""),
                        percent: String(r.default_commission_percent ?? ""),
                      }))
                    );
                  });
                }
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
          {showMoney && !data?.emehmon_paid ? (
            <Pressable
              style={[styles.miniBtn, styles.miniCharge]}
              onPress={() => {
                setEmehmonAmount(data?.emehmon_default || "");
                setPanel(panel === "emehmon" ? "none" : "emehmon");
              }}
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

        {panel === "checkin" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Kirish · E-mehmon</Text>
            <Text style={styles.occHint}>
              {data?.emehmon_unit || "0"} × {data?.nights ?? "?"} kecha ×{" "}
              {data?.emehmon_guests ?? "?"} kishi
            </Text>
            <Pressable
              style={[ui.chip, collectEmehmon && ui.chipOn, { marginBottom: 8 }]}
              onPress={() => setCollectEmehmon((v) => !v)}
            >
              <Text
                style={[ui.chipText, collectEmehmon && ui.chipTextOn]}
              >
                {collectEmehmon ? "✓ E-mehmon olinsin" : "E-mehmon olinmasin"}
              </Text>
            </Pressable>
            {collectEmehmon ? (
              <>
                <FieldLabel>Summa</FieldLabel>
                <TextInput
                  style={styles.payInput}
                  value={emehmonAmount}
                  onChangeText={setEmehmonAmount}
                  keyboardType="decimal-pad"
                  placeholder={data?.emehmon_default || "0"}
                  placeholderTextColor={colors.faint}
                />
                <FieldLabel>To‘lov usuli</FieldLabel>
                <SegmentedTabs
                  tabs={PAY_METHODS.map((m) => ({
                    id: m.id,
                    label: m.label,
                  }))}
                  value={emehmonMethod}
                  onChange={setEmehmonMethod}
                />
              </>
            ) : null}
            {(data?.occupants_missing ?? 0) > 0 ? (
              <Text style={styles.occWarn}>
                Avval yetishmayotgan {data?.occupants_missing} mehmonni
                to‘ldiring (yoki hujjatsiz kirish).
              </Text>
            ) : null}
            <PrimaryButton
              label="Joylash"
              onPress={() => doCheckIn({})}
              loading={busy}
            />
            <PrimaryButton
              label="Bekor"
              tone="ghost"
              onPress={() => setPanel("none")}
            />
          </View>
        ) : null}

        {panel === "emehmon" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>E-mehmon to‘lovi</Text>
            <Text style={styles.occHint}>
              Tarif {data?.emehmon_unit || "—"} ·{" "}
              {data?.nights ?? "?"} kecha · {data?.emehmon_guests ?? "?"} kishi
            </Text>
            <FieldLabel>Summa</FieldLabel>
            <TextInput
              style={styles.payInput}
              value={emehmonAmount}
              onChangeText={setEmehmonAmount}
              keyboardType="decimal-pad"
              placeholder={data?.emehmon_default || "0"}
              placeholderTextColor={colors.faint}
            />
            <FieldLabel>To‘lov usuli</FieldLabel>
            <SegmentedTabs
              tabs={PAY_METHODS.map((m) => ({ id: m.id, label: m.label }))}
              value={emehmonMethod}
              onChange={setEmehmonMethod}
            />
            <PrimaryButton
              label="Yozish"
              onPress={doEmehmon}
              loading={busy}
            />
            <PrimaryButton
              label="Bekor"
              tone="ghost"
              onPress={() => setPanel("none")}
            />
          </View>
        ) : null}

        {panel === "amend" ? (
          <View style={styles.payBox}>
            <Text style={styles.payTitle}>Bronni o‘zgartirish</Text>
            <TextInput
              style={styles.payInput}
              value={amendIn}
              onChangeText={setAmendIn}
              placeholder="Kirish (YYYY-MM-DD)"
              placeholderTextColor="#a89f94"
              autoCapitalize="none"
            />
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
            <TextInput
              style={styles.payInput}
              value={amendAdults}
              onChangeText={setAmendAdults}
              keyboardType="number-pad"
              placeholder="Kattalar"
              placeholderTextColor="#a89f94"
            />
            <TextInput
              style={styles.payInput}
              value={amendChildren}
              onChangeText={setAmendChildren}
              keyboardType="number-pad"
              placeholder="Bolalar"
              placeholderTextColor="#a89f94"
            />
            <Text style={[styles.payTitle, { marginTop: 8 }]}>Kompaniya</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Pressable
                style={[styles.miniBtn, amendCompanyId == null && styles.miniExtend]}
                onPress={() => setAmendCompanyId(null)}
              >
                <Text style={styles.miniText}>Yo‘q</Text>
              </Pressable>
              {companies.map((c) => (
                <Pressable
                  key={c.id}
                  style={[
                    styles.miniBtn,
                    amendCompanyId === c.id && styles.miniExtend,
                  ]}
                  onPress={() => setAmendCompanyId(c.id)}
                >
                  <Text style={styles.miniText}>{c.name}</Text>
                </Pressable>
              ))}
            </View>
            <Text style={[styles.payTitle, { marginTop: 8 }]}>Yo‘naltiruvchi</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Pressable
                style={[styles.miniBtn, amendReferrerId == null && styles.miniExtend]}
                onPress={() => setAmendReferrerId(null)}
              >
                <Text style={styles.miniText}>Yo‘q</Text>
              </Pressable>
              {referrers.map((r) => (
                <Pressable
                  key={r.id}
                  style={[
                    styles.miniBtn,
                    amendReferrerId === r.id && styles.miniExtend,
                  ]}
                  onPress={() => setAmendReferrerId(r.id)}
                >
                  <Text style={styles.miniText}>{r.name}</Text>
                </Pressable>
              ))}
            </View>
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
            <Pressable
              style={[styles.miniBtn, updateRate && styles.miniExtend, { marginBottom: 8 }]}
              onPress={() => setUpdateRate((v) => !v)}
            >
              <Text style={styles.miniText}>
                {updateRate
                  ? "Yangi xona tarifi qo‘llanadi"
                  : "Eski tarif saqlanadi"}
              </Text>
            </Pressable>
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
  root: { flex: 1, backgroundColor: colors.paper },
  boot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.paper,
    padding: 24,
  },
  body: { padding: space.lg, paddingBottom: 40 },
  notesHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  notesTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.4,
    fontFamily: fontUi,
    textTransform: "uppercase",
  },
  notesEdit: {
    color: colors.accent,
    fontWeight: "700",
    fontSize: 13,
    fontFamily: fontUi,
  },
  notesBody: {
    color: colors.ink,
    fontSize: 15,
    lineHeight: 22,
    fontFamily: fontUi,
  },
  notesInput: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: 10,
    minHeight: 80,
    textAlignVertical: "top",
    color: colors.ink,
    fontSize: 15,
    backgroundColor: colors.paper,
    fontFamily: fontUi,
  },
  notesActions: { flexDirection: "row", gap: 8, marginTop: 4, alignItems: "center" },
  notesCancel: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: radius.md,
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  notesCancelText: {
    fontWeight: "600",
    color: colors.inkSoft,
    fontFamily: fontUi,
  },
  row: {
    backgroundColor: colors.paper,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.sm,
  },
  rowLbl: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.4,
    fontFamily: fontUi,
  },
  rowVal: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.ink,
    marginTop: 4,
    fontFamily: fontUi,
  },
  ledgerTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
    marginBottom: space.sm,
    fontFamily: fontUi,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  ledgerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: space.md,
    marginBottom: space.sm,
    backgroundColor: colors.paper,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  ledgerDesc: {
    flex: 1,
    color: colors.ink,
    fontSize: 14,
    fontFamily: fontUi,
  },
  ledgerAmt: {
    fontWeight: "700",
    color: colors.ink,
    fontFamily: fontUi,
  },
  ledgerPay: { color: colors.accent },
  ledgerVoid: { color: colors.faint, textDecorationLine: "line-through" },
  voidHint: {
    marginTop: 4,
    fontSize: 11,
    color: colors.faint,
    fontFamily: fontUi,
  },
  error: { color: colors.danger, marginVertical: 12, fontFamily: fontUi },
  action: {
    marginTop: 16,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 16,
    alignItems: "center",
  },
  actionOut: { backgroundColor: colors.night },
  actionText: { color: colors.white, fontWeight: "700", fontSize: 16 },
  actionRow: { flexDirection: "row", gap: 8, marginTop: 16 },
  miniBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: radius.md,
    alignItems: "center",
  },
  miniPay: { backgroundColor: colors.accent },
  miniDeposit: { backgroundColor: colors.accent },
  miniRefund: { backgroundColor: colors.night },
  miniCharge: { backgroundColor: colors.night },
  miniSvc: { backgroundColor: colors.night },
  miniMinibar: { backgroundColor: colors.night },
  miniExtend: { backgroundColor: colors.night },
  miniTransfer: { backgroundColor: colors.night },
  miniCancel: { backgroundColor: colors.danger },
  miniNoShow: { backgroundColor: colors.muted },
  miniText: { color: colors.white, fontWeight: "700", fontSize: 14 },
  disabled: { opacity: 0.7 },
  backBtn: {
    marginTop: 16,
    padding: 12,
    backgroundColor: colors.accent,
    borderRadius: radius.md,
  },
  backBtnText: { color: colors.white, fontWeight: "700" },
  payBox: {
    marginTop: 12,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    padding: space.lg,
  },
  payTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.ink,
    marginBottom: 10,
    fontFamily: fontUi,
  },
  payInput: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    fontWeight: "600",
    color: colors.ink,
    marginBottom: 10,
    backgroundColor: colors.paper,
    fontFamily: fontUi,
  },
  methodRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  methodChip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    alignItems: "center",
    backgroundColor: colors.paper,
  },
  methodChipOn: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  methodText: {
    fontWeight: "600",
    color: colors.ink,
    fontSize: 13,
    fontFamily: fontUi,
  },
  methodTextOn: { color: colors.white },
  paySubmit: {
    paddingVertical: 14,
    borderRadius: radius.md,
    alignItems: "center",
    backgroundColor: colors.accent,
  },
  depositSubmit: { backgroundColor: colors.accent },
  chargeSubmit: { backgroundColor: colors.copper },
  emptySvc: { color: colors.muted, paddingVertical: 8, fontFamily: fontUi },
  svcRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.lineSoft,
  },
  svcName: { fontWeight: "600", color: colors.ink, flex: 1, fontFamily: fontUi },
  svcPrice: { fontWeight: "700", color: colors.info, fontFamily: fontUi },
  occRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    paddingHorizontal: space.md,
    marginBottom: space.sm,
    backgroundColor: colors.paper,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  occName: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.ink,
    fontFamily: fontUi,
  },
  occPhone: {
    fontSize: 12,
    color: colors.muted,
    marginTop: 2,
    fontFamily: fontUi,
  },
  occHint: {
    fontSize: 12,
    color: colors.muted,
    lineHeight: 18,
    marginBottom: space.sm,
    fontFamily: fontUi,
  },
  occRemove: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.danger,
    fontFamily: fontUi,
  },
  occWarn: {
    color: colors.warn,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: space.sm,
    fontFamily: fontUi,
  },
  occForm: { marginTop: space.sm },
});
