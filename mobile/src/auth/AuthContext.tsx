import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiRequest } from "../api/client";
import type {
  AvailableRoom,
  BoardData,
  CalendarData,
  CashShift,
  ChargeResult,
  CheckInResult,
  CheckOutResult,
  CreateReservationPayload,
  CreateReservationResult,
  ExtendResult,
  FlashReport,
  GuestSummary,
  HkBoard,
  LoginResponse,
  MePayload,
  MaintenanceTicket,
  MinibarItem,
  PaymentResult,
  ReservationDetail,
  ReservationSummary,
  RoomStatusResult,
  ServiceItem,
  ServiceOrderResult,
  TodayData,
  TransferResult,
  WalkInPayload,
  WalkInResult,
} from "../api/types";

const TOKEN_KEY = "rivoj_api_token";
const TENANT_KEY = "rivoj_tenant_id";
const HOTEL_KEY = "rivoj_hotel_id";

type AuthState = {
  ready: boolean;
  token: string | null;
  tenantId: number | null;
  hotelId: number | null;
  me: MePayload | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setHotel: (hotelId: number) => Promise<void>;
  fetchBoard: (date?: string) => Promise<BoardData>;
  fetchToday: (date?: string) => Promise<TodayData>;
  searchReservations: (q: string) => Promise<ReservationSummary[]>;
  fetchReservation: (id: number) => Promise<ReservationDetail>;
  fetchAvailableRooms: (
    checkIn: string,
    checkOut: string
  ) => Promise<AvailableRoom[]>;
  createReservation: (
    payload: CreateReservationPayload
  ) => Promise<CreateReservationResult>;
  checkIn: (
    id: number,
    opts?: { allow_dirty?: boolean; allow_no_docs?: boolean; collect_emehmon?: boolean }
  ) => Promise<CheckInResult>;
  checkOut: (id: number) => Promise<CheckOutResult>;
  cancelReservation: (id: number, reason?: string) => Promise<{ status: string }>;
  markNoShow: (id: number, reason?: string) => Promise<{ status: string }>;
  walkIn: (payload: WalkInPayload) => Promise<WalkInResult>;
  postPayment: (
    reservationId: number,
    amount: string,
    method?: string,
    note?: string
  ) => Promise<PaymentResult>;
  postCharge: (
    reservationId: number,
    opts: {
      description: string;
      unit_price: string;
      quantity?: string;
      charge_type?: string;
    }
  ) => Promise<ChargeResult>;
  fetchServices: () => Promise<ServiceItem[]>;
  orderService: (
    reservationId: number,
    serviceId: number,
    quantity?: string
  ) => Promise<ServiceOrderResult>;
  setRoomStatus: (roomId: number, status: string) => Promise<RoomStatusResult>;
  transferRoom: (
    reservationId: number,
    roomId: number,
    reason?: string
  ) => Promise<TransferResult>;
  extendStay: (reservationId: number, nights?: number) => Promise<ExtendResult>;
  fetchCashShift: () => Promise<CashShift | null>;
  openCashShift: (openingFloat?: string) => Promise<CashShift>;
  closeCashShift: (closingCash: string, notes?: string) => Promise<CashShift>;
  saveNotes: (reservationId: number, notes: string) => Promise<string>;
  postDeposit: (
    reservationId: number,
    amount: string,
    method?: string
  ) => Promise<PaymentResult>;
  postRefund: (
    reservationId: number,
    amount?: string,
    method?: string
  ) => Promise<PaymentResult>;
  fetchMinibarItems: () => Promise<MinibarItem[]>;
  postMinibar: (
    reservationId: number,
    itemId: number,
    quantity?: string
  ) => Promise<{ item: string; amount: string; balance: string | null }>;
  confirmInquiry: (id: number) => Promise<{ status: string }>;
  fetchInquiries: () => Promise<ReservationSummary[]>;
  searchGuests: (q: string) => Promise<GuestSummary[]>;
  createGuest: (payload: {
    first_name: string;
    last_name?: string;
    phone?: string;
  }) => Promise<GuestSummary>;
  fetchHousekeeping: () => Promise<HkBoard>;
  completeHkTask: (taskId: number) => Promise<void>;
  postCashMovement: (
    kind: "pay_in" | "pay_out",
    amount: string,
    note?: string
  ) => Promise<void>;
  fetchCalendar: (start?: string, days?: number) => Promise<CalendarData>;
  fetchFlash: (date?: string) => Promise<FlashReport>;
  fetchMaintenance: (status?: string) => Promise<MaintenanceTicket[]>;
  createMaintenance: (payload: {
    title: string;
    description?: string;
    room_id?: number;
    priority?: string;
    set_room_ooo?: boolean;
  }) => Promise<MaintenanceTicket>;
  completeMaintenance: (id: number) => Promise<{ id: number; status: string }>;
  voidCharge: (
    chargeId: number,
    reason?: string
  ) => Promise<{ charge_id: number; is_void: boolean; balance: string }>;
  voidPayment: (
    paymentId: number,
    reason?: string
  ) => Promise<{ payment_id: number; is_void: boolean; balance: string }>;
  amendReservation: (
    id: number,
    payload: {
      check_in?: string;
      check_out?: string;
      adults?: number;
      children?: number;
      nightly_rate?: string;
      reason?: string;
    }
  ) => Promise<ReservationSummary>;
  fetchGuest: (id: number) => Promise<Record<string, unknown>>;
  updateGuest: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  addGuestDocument: (
    id: number,
    payload: {
      number: string;
      doc_type?: string;
      issued_country?: string;
      expiry_date?: string;
    }
  ) => Promise<Record<string, unknown>>;
  fetchReceipt: (
    folioId: number,
    withPdf?: boolean
  ) => Promise<Record<string, unknown>>;
  closeFolio: (folioId: number) => Promise<{ folio_id: number; is_open: boolean }>;
  splitPay: (
    folioId: number,
    lines: { amount: string; method?: string; kind?: string }[]
  ) => Promise<{ balance: string }>;
  postEmehmon: (
    reservationId: number,
    method?: string
  ) => Promise<{ amount: string; balance: string }>;
  transferToCompany: (
    folioId: number,
    companyId?: number
  ) => Promise<Record<string, unknown>>;
  fetchCompanies: (q?: string) => Promise<Record<string, unknown>[]>;
  createCompany: (payload: {
    name: string;
    phone?: string;
    inn?: string;
  }) => Promise<Record<string, unknown>>;
  fetchCityLedger: (status?: string) => Promise<Record<string, unknown>[]>;
  payCityLedger: (
    id: number,
    amount: string,
    method?: string
  ) => Promise<Record<string, unknown>>;
  fetchGroups: () => Promise<Record<string, unknown>[]>;
  fetchGroup: (id: number) => Promise<Record<string, unknown>>;
  createGroup: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>;
  fetchNightAudit: (date?: string) => Promise<Record<string, unknown>>;
  runNightAudit: (date?: string) => Promise<Record<string, unknown>>;
  fetchExpenses: () => Promise<Record<string, unknown>[]>;
  fetchPnl: (year?: number, month?: number) => Promise<Record<string, unknown>>;
  fetchInventory: (
    q?: string,
    flag?: string
  ) => Promise<{
    items: Record<string, unknown>[];
    badges: Record<string, number>;
  }>;
  adjustInventory: (
    id: number,
    payload: { movement_type: string; quantity: string; note?: string }
  ) => Promise<Record<string, unknown>>;
  fetchReferrers: (q?: string) => Promise<Record<string, unknown>[]>;
  createReferrer: (payload: {
    name: string;
    phone?: string;
    default_commission_percent?: string;
  }) => Promise<Record<string, unknown>>;
  fetchCommission: (
    year?: number,
    month?: number
  ) => Promise<Record<string, unknown>>;
  payCommission: (
    referrerId: number,
    amount: string,
    opts?: { year?: number; month?: number; method?: string }
  ) => Promise<Record<string, unknown>>;
  fetchEmployees: (q?: string) => Promise<Record<string, unknown>[]>;
  payEmployee: (
    id: number,
    opts?: { days?: number; work_date?: string; method?: string }
  ) => Promise<Record<string, unknown>>;
  advanceEmployee: (
    id: number,
    amount: string,
    note?: string
  ) => Promise<Record<string, unknown>>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<number | null>(null);
  const [hotelId, setHotelId] = useState<number | null>(null);
  const [me, setMe] = useState<MePayload | null>(null);

  const authOpts = useCallback(
    () => ({
      token,
      tenantId,
      hotelId,
    }),
    [token, tenantId, hotelId]
  );

  useEffect(() => {
    (async () => {
      try {
        const [t, tid, hid] = await Promise.all([
          AsyncStorage.getItem(TOKEN_KEY),
          AsyncStorage.getItem(TENANT_KEY),
          AsyncStorage.getItem(HOTEL_KEY),
        ]);
        if (t) {
          setToken(t);
          setTenantId(tid ? Number(tid) : null);
          const hotelNum = hid ? Number(hid) : null;
          setHotelId(hotelNum);
          try {
            const profile = await apiRequest<MePayload>("/me/", {
              token: t,
              tenantId: tid ? Number(tid) : null,
              hotelId: hotelNum,
            });
            if (!profile.hotels) profile.hotels = [];
            setMe(profile);
            if (!hotelNum && profile.hotel?.id) {
              setHotelId(profile.hotel.id);
              await AsyncStorage.setItem(HOTEL_KEY, String(profile.hotel.id));
            }
          } catch {
            await AsyncStorage.multiRemove([TOKEN_KEY, TENANT_KEY, HOTEL_KEY]);
            setToken(null);
            setTenantId(null);
            setHotelId(null);
          }
        }
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiRequest<LoginResponse>("/auth/login/", {
      method: "POST",
      body: { username, password },
    });
    if (!data.me.hotels) data.me.hotels = [];
    const hid = data.me.hotel?.id ?? data.me.hotels[0]?.id ?? null;
    await AsyncStorage.setItem(TOKEN_KEY, data.token);
    await AsyncStorage.setItem(TENANT_KEY, String(data.me.tenant.id));
    if (hid) await AsyncStorage.setItem(HOTEL_KEY, String(hid));
    else await AsyncStorage.removeItem(HOTEL_KEY);
    setToken(data.token);
    setTenantId(data.me.tenant.id);
    setHotelId(hid);
    setMe(data.me);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (token) {
        await apiRequest("/auth/logout/", {
          method: "POST",
          token,
          tenantId,
          hotelId,
        });
      }
    } catch {
      // ignore
    }
    await AsyncStorage.multiRemove([TOKEN_KEY, TENANT_KEY, HOTEL_KEY]);
    setToken(null);
    setTenantId(null);
    setHotelId(null);
    setMe(null);
  }, [token, tenantId, hotelId]);

  const setHotel = useCallback(
    async (nextHotelId: number) => {
      if (!token) throw new Error("Not authenticated");
      await AsyncStorage.setItem(HOTEL_KEY, String(nextHotelId));
      setHotelId(nextHotelId);
      const profile = await apiRequest<MePayload>("/me/", {
        token,
        tenantId,
        hotelId: nextHotelId,
      });
      if (!profile.hotels) profile.hotels = [];
      setMe(profile);
    },
    [token, tenantId]
  );

  const fetchBoard = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<BoardData>(`/board/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchToday = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<TodayData>(`/today/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const searchReservations = useCallback(
    async (q: string) => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ items: ReservationSummary[] }>(
        `/reservations/search/?q=${encodeURIComponent(q)}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const fetchReservation = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<ReservationDetail>(`/reservations/${id}/`, authOpts());
    },
    [token, authOpts]
  );

  const fetchAvailableRooms = useCallback(
    async (checkIn: string, checkOut: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = `?check_in=${encodeURIComponent(checkIn)}&check_out=${encodeURIComponent(checkOut)}`;
      const data = await apiRequest<{ items: AvailableRoom[] }>(
        `/rooms/available/${q}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const createReservation = useCallback(
    async (payload: CreateReservationPayload) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<CreateReservationResult>("/reservations/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const checkIn = useCallback(
    async (
      id: number,
      opts?: {
        allow_dirty?: boolean;
        allow_no_docs?: boolean;
        collect_emehmon?: boolean;
      }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<CheckInResult>(`/reservations/${id}/check-in/`, {
        ...authOpts(),
        method: "POST",
        body: {
          allow_dirty: !!opts?.allow_dirty,
          allow_no_docs: !!opts?.allow_no_docs,
          collect_emehmon: opts?.collect_emehmon !== false,
          emehmon_method: "cash",
        },
      });
    },
    [token, authOpts]
  );

  const checkOut = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<CheckOutResult>(`/reservations/${id}/check-out/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const cancelReservation = useCallback(
    async (id: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ status: string }>(`/reservations/${id}/cancel/`, {
        ...authOpts(),
        method: "POST",
        body: { reason },
      });
    },
    [token, authOpts]
  );

  const markNoShow = useCallback(
    async (id: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ status: string }>(`/reservations/${id}/no-show/`, {
        ...authOpts(),
        method: "POST",
        body: { reason },
      });
    },
    [token, authOpts]
  );

  const walkIn = useCallback(
    async (payload: WalkInPayload) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<WalkInResult>("/walk-in/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const postPayment = useCallback(
    async (
      reservationId: number,
      amount: string,
      method = "cash",
      note = ""
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<PaymentResult>(
        `/reservations/${reservationId}/payment/`,
        {
          ...authOpts(),
          method: "POST",
          body: { amount, method, note },
        }
      );
    },
    [token, authOpts]
  );

  const postCharge = useCallback(
    async (
      reservationId: number,
      opts: {
        description: string;
        unit_price: string;
        quantity?: string;
        charge_type?: string;
      }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<ChargeResult>(`/reservations/${reservationId}/charge/`, {
        ...authOpts(),
        method: "POST",
        body: {
          description: opts.description,
          unit_price: opts.unit_price,
          quantity: opts.quantity || "1",
          charge_type: opts.charge_type || "other",
        },
      });
    },
    [token, authOpts]
  );

  const fetchServices = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: ServiceItem[] }>(
      "/services/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const orderService = useCallback(
    async (reservationId: number, serviceId: number, quantity = "1") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<ServiceOrderResult>(
        `/reservations/${reservationId}/service/`,
        {
          ...authOpts(),
          method: "POST",
          body: { service_id: serviceId, quantity },
        }
      );
    },
    [token, authOpts]
  );

  const setRoomStatus = useCallback(
    async (roomId: number, status: string) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<RoomStatusResult>(`/rooms/${roomId}/status/`, {
        ...authOpts(),
        method: "POST",
        body: { status },
      });
    },
    [token, authOpts]
  );

  const transferRoom = useCallback(
    async (reservationId: number, roomId: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<TransferResult>(
        `/reservations/${reservationId}/transfer/`,
        {
          ...authOpts(),
          method: "POST",
          body: { room_id: roomId, reason },
        }
      );
    },
    [token, authOpts]
  );

  const extendStay = useCallback(
    async (reservationId: number, nights = 1) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<ExtendResult>(
        `/reservations/${reservationId}/extend/`,
        {
          ...authOpts(),
          method: "POST",
          body: { nights },
        }
      );
    },
    [token, authOpts]
  );

  const fetchCashShift = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ shift: CashShift | null }>(
      "/cash-shift/",
      authOpts()
    );
    return data.shift;
  }, [token, authOpts]);

  const openCashShift = useCallback(
    async (openingFloat = "0") => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ shift: CashShift }>("/cash-shift/open/", {
        ...authOpts(),
        method: "POST",
        body: { opening_float: openingFloat },
      });
      return data.shift;
    },
    [token, authOpts]
  );

  const closeCashShift = useCallback(
    async (closingCash: string, notes = "") => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ shift: CashShift }>("/cash-shift/close/", {
        ...authOpts(),
        method: "POST",
        body: { closing_cash: closingCash, notes },
      });
      return data.shift;
    },
    [token, authOpts]
  );

  const saveNotes = useCallback(
    async (reservationId: number, notes: string) => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ notes: string }>(
        `/reservations/${reservationId}/notes/`,
        {
          ...authOpts(),
          method: "POST",
          body: { notes },
        }
      );
      return data.notes;
    },
    [token, authOpts]
  );

  const postDeposit = useCallback(
    async (reservationId: number, amount: string, method = "cash") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<PaymentResult>(
        `/reservations/${reservationId}/deposit/`,
        {
          ...authOpts(),
          method: "POST",
          body: { amount, method },
        }
      );
    },
    [token, authOpts]
  );

  const postRefund = useCallback(
    async (reservationId: number, amount?: string, method = "cash") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<PaymentResult>(
        `/reservations/${reservationId}/refund/`,
        {
          ...authOpts(),
          method: "POST",
          body: amount ? { amount, method } : { method },
        }
      );
    },
    [token, authOpts]
  );

  const fetchMinibarItems = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: MinibarItem[] }>(
      "/minibar/items/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const postMinibar = useCallback(
    async (reservationId: number, itemId: number, quantity = "1") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        item: string;
        amount: string;
        balance: string | null;
      }>(`/reservations/${reservationId}/minibar/`, {
        ...authOpts(),
        method: "POST",
        body: { item_id: itemId, quantity },
      });
    },
    [token, authOpts]
  );

  const confirmInquiry = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ status: string }>(`/reservations/${id}/confirm/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const fetchInquiries = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: ReservationSummary[] }>(
      "/inquiries/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const searchGuests = useCallback(
    async (q: string) => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ items: GuestSummary[] }>(
        `/guests/?q=${encodeURIComponent(q)}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const createGuest = useCallback(
    async (payload: {
      first_name: string;
      last_name?: string;
      phone?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<GuestSummary>("/guests/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchHousekeeping = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<HkBoard>("/housekeeping/", authOpts());
  }, [token, authOpts]);

  const completeHkTask = useCallback(
    async (taskId: number) => {
      if (!token) throw new Error("Not authenticated");
      await apiRequest(`/housekeeping/tasks/${taskId}/complete/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const postCashMovement = useCallback(
    async (kind: "pay_in" | "pay_out", amount: string, note = "") => {
      if (!token) throw new Error("Not authenticated");
      await apiRequest("/cash-shift/movement/", {
        ...authOpts(),
        method: "POST",
        body: { kind, amount, note },
      });
    },
    [token, authOpts]
  );

  const fetchCalendar = useCallback(
    async (start?: string, days = 14) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (start) params.set("start", start);
      params.set("days", String(days));
      return apiRequest<CalendarData>(`/calendar/?${params}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchFlash = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<FlashReport>(`/reports/flash/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchMaintenance = useCallback(
    async (status?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = status ? `?status=${encodeURIComponent(status)}` : "";
      const data = await apiRequest<{ items: MaintenanceTicket[] }>(
        `/maintenance/${q}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const createMaintenance = useCallback(
    async (payload: {
      title: string;
      description?: string;
      room_id?: number;
      priority?: string;
      set_room_ooo?: boolean;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<MaintenanceTicket>("/maintenance/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const completeMaintenance = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ id: number; status: string }>(
        `/maintenance/${id}/complete/`,
        {
          ...authOpts(),
          method: "POST",
          body: {},
        }
      );
    },
    [token, authOpts]
  );

  const voidCharge = useCallback(
    async (chargeId: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ charge_id: number; is_void: boolean; balance: string }>(
        `/charges/${chargeId}/void/`,
        {
          ...authOpts(),
          method: "POST",
          body: { reason },
        }
      );
    },
    [token, authOpts]
  );

  const voidPayment = useCallback(
    async (paymentId: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        payment_id: number;
        is_void: boolean;
        balance: string;
      }>(`/payments/${paymentId}/void/`, {
        ...authOpts(),
        method: "POST",
        body: { reason },
      });
    },
    [token, authOpts]
  );

  const amendReservation = useCallback(
    async (
      id: number,
      payload: {
        check_in?: string;
        check_out?: string;
        adults?: number;
        children?: number;
        nightly_rate?: string;
        reason?: string;
      }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<ReservationSummary>(`/reservations/${id}/amend/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchGuest = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/guests/${id}/`, authOpts());
    },
    [token, authOpts]
  );

  const updateGuest = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/guests/${id}/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const addGuestDocument = useCallback(
    async (
      id: number,
      payload: {
        number: string;
        doc_type?: string;
        issued_country?: string;
        expiry_date?: string;
      }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/guests/${id}/documents/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchReceipt = useCallback(
    async (folioId: number, withPdf = false) => {
      if (!token) throw new Error("Not authenticated");
      const q = withPdf ? "?pdf=1" : "";
      return apiRequest<Record<string, unknown>>(
        `/folios/${folioId}/receipt/${q}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const closeFolio = useCallback(
    async (folioId: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ folio_id: number; is_open: boolean }>(
        `/folios/${folioId}/close/`,
        { ...authOpts(), method: "POST", body: {} }
      );
    },
    [token, authOpts]
  );

  const splitPay = useCallback(
    async (
      folioId: number,
      lines: { amount: string; method?: string; kind?: string }[]
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ balance: string }>(`/folios/${folioId}/split-pay/`, {
        ...authOpts(),
        method: "POST",
        body: { lines },
      });
    },
    [token, authOpts]
  );

  const postEmehmon = useCallback(
    async (reservationId: number, method = "cash") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{ amount: string; balance: string }>(
        `/reservations/${reservationId}/emehmon/`,
        { ...authOpts(), method: "POST", body: { method } }
      );
    },
    [token, authOpts]
  );

  const transferToCompany = useCallback(
    async (folioId: number, companyId?: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/folios/${folioId}/to-company/`, {
        ...authOpts(),
        method: "POST",
        body: companyId ? { company_id: companyId } : {},
      });
    },
    [token, authOpts]
  );

  const fetchCompanies = useCallback(
    async (q = "") => {
      if (!token) throw new Error("Not authenticated");
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      const data = await apiRequest<{ items: Record<string, unknown>[] }>(
        `/companies/${qs}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const createCompany = useCallback(
    async (payload: { name: string; phone?: string; inn?: string }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/companies/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchCityLedger = useCallback(
    async (status = "open") => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<{ items: Record<string, unknown>[] }>(
        `/city-ledger/?status=${encodeURIComponent(status)}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const payCityLedger = useCallback(
    async (id: number, amount: string, method = "transfer") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/city-ledger/${id}/pay/`, {
        ...authOpts(),
        method: "POST",
        body: { amount, method },
      });
    },
    [token, authOpts]
  );

  const fetchGroups = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/groups/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const fetchGroup = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/groups/${id}/`, authOpts());
    },
    [token, authOpts]
  );

  const createGroup = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/groups/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchNightAudit = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<Record<string, unknown>>(
        `/reports/night-audit/${q}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const runNightAudit = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/reports/night-audit/run/", {
        ...authOpts(),
        method: "POST",
        body: date ? { date } : {},
      });
    },
    [token, authOpts]
  );

  const fetchExpenses = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/expenses/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const fetchPnl = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (month) params.set("month", String(month));
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<Record<string, unknown>>(`/reports/pnl/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchInventory = useCallback(
    async (q = "", flag = "") => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (flag) params.set("flag", flag);
      const qs = params.toString() ? `?${params}` : "";
      return apiRequest<{
        items: Record<string, unknown>[];
        badges: Record<string, number>;
      }>(`/inventory/items/${qs}`, authOpts());
    },
    [token, authOpts]
  );

  const adjustInventory = useCallback(
    async (
      id: number,
      payload: { movement_type: string; quantity: string; note?: string }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/inventory/items/${id}/adjust/`,
        { ...authOpts(), method: "POST", body: payload }
      );
    },
    [token, authOpts]
  );

  const fetchReferrers = useCallback(
    async (q = "") => {
      if (!token) throw new Error("Not authenticated");
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      const data = await apiRequest<{ items: Record<string, unknown>[] }>(
        `/referrers/${qs}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const createReferrer = useCallback(
    async (payload: {
      name: string;
      phone?: string;
      default_commission_percent?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/referrers/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchCommission = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (month) params.set("month", String(month));
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<Record<string, unknown>>(
        `/reports/commission/${q}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const payCommission = useCallback(
    async (
      referrerId: number,
      amount: string,
      opts?: { year?: number; month?: number; method?: string }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/reports/commission/${referrerId}/pay/`,
        {
          ...authOpts(),
          method: "POST",
          body: { amount, method: "cash", ...opts },
        }
      );
    },
    [token, authOpts]
  );

  const fetchEmployees = useCallback(
    async (q = "") => {
      if (!token) throw new Error("Not authenticated");
      const qs = q ? `?q=${encodeURIComponent(q)}` : "";
      const data = await apiRequest<{ items: Record<string, unknown>[] }>(
        `/hr/employees/${qs}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const payEmployee = useCallback(
    async (
      id: number,
      opts?: { days?: number; work_date?: string; method?: string }
    ) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/hr/employees/${id}/pay/`, {
        ...authOpts(),
        method: "POST",
        body: { method: "cash", ...opts },
      });
    },
    [token, authOpts]
  );

  const advanceEmployee = useCallback(
    async (id: number, amount: string, note = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/hr/employees/${id}/advance/`,
        { ...authOpts(), method: "POST", body: { amount, note } }
      );
    },
    [token, authOpts]
  );

  const value = useMemo(
    () => ({
      ready,
      token,
      tenantId,
      hotelId,
      me,
      login,
      logout,
      setHotel,
      fetchBoard,
      fetchToday,
      searchReservations,
      fetchReservation,
      fetchAvailableRooms,
      createReservation,
      checkIn,
      checkOut,
      cancelReservation,
      markNoShow,
      walkIn,
      postPayment,
      postCharge,
      fetchServices,
      orderService,
      setRoomStatus,
      transferRoom,
      extendStay,
      fetchCashShift,
      openCashShift,
      closeCashShift,
      saveNotes,
      postDeposit,
      postRefund,
      fetchMinibarItems,
      postMinibar,
      confirmInquiry,
      fetchInquiries,
      searchGuests,
      createGuest,
      fetchHousekeeping,
      completeHkTask,
      postCashMovement,
      fetchCalendar,
      fetchFlash,
      fetchMaintenance,
      createMaintenance,
      completeMaintenance,
      voidCharge,
      voidPayment,
      amendReservation,
      fetchGuest,
      updateGuest,
      addGuestDocument,
      fetchReceipt,
      closeFolio,
      splitPay,
      postEmehmon,
      transferToCompany,
      fetchCompanies,
      createCompany,
      fetchCityLedger,
      payCityLedger,
      fetchGroups,
      fetchGroup,
      createGroup,
      fetchNightAudit,
      runNightAudit,
      fetchExpenses,
      fetchPnl,
      fetchInventory,
      adjustInventory,
      fetchReferrers,
      createReferrer,
      fetchCommission,
      payCommission,
      fetchEmployees,
      payEmployee,
      advanceEmployee,
    }),
    [
      ready,
      token,
      tenantId,
      hotelId,
      me,
      login,
      logout,
      setHotel,
      fetchBoard,
      fetchToday,
      searchReservations,
      fetchReservation,
      fetchAvailableRooms,
      createReservation,
      checkIn,
      checkOut,
      cancelReservation,
      markNoShow,
      walkIn,
      postPayment,
      postCharge,
      fetchServices,
      orderService,
      setRoomStatus,
      transferRoom,
      extendStay,
      fetchCashShift,
      openCashShift,
      closeCashShift,
      saveNotes,
      postDeposit,
      postRefund,
      fetchMinibarItems,
      postMinibar,
      confirmInquiry,
      fetchInquiries,
      searchGuests,
      createGuest,
      fetchHousekeeping,
      completeHkTask,
      postCashMovement,
      fetchCalendar,
      fetchFlash,
      fetchMaintenance,
      createMaintenance,
      completeMaintenance,
      voidCharge,
      voidPayment,
      amendReservation,
      fetchGuest,
      updateGuest,
      addGuestDocument,
      fetchReceipt,
      closeFolio,
      splitPay,
      postEmehmon,
      transferToCompany,
      fetchCompanies,
      createCompany,
      fetchCityLedger,
      payCityLedger,
      fetchGroups,
      fetchGroup,
      createGroup,
      fetchNightAudit,
      runNightAudit,
      fetchExpenses,
      fetchPnl,
      fetchInventory,
      adjustInventory,
      fetchReferrers,
      createReferrer,
      fetchCommission,
      payCommission,
      fetchEmployees,
      payEmployee,
      advanceEmployee,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
