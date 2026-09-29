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
    opts?: {
      allow_dirty?: boolean;
      allow_no_docs?: boolean;
      collect_emehmon?: boolean;
      emehmon_amount?: string;
      emehmon_method?: string;
    }
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
    opts?: { reason?: string; update_rate?: boolean }
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
  postMinibarQuick: (
    roomNumber: string,
    itemId: number,
    quantity?: string
  ) => Promise<{
    room: string;
    guest: string;
    item: string;
    quantity: string;
    amount: string;
    balance: string | null;
    reservation_id: number;
  }>;
  fetchReservationsList: (opts?: {
    date_from?: string;
    date_to?: string;
    status?: string;
    q?: string;
  }) => Promise<{
    items: ReservationSummary[];
    statuses: { id: string; label: string }[];
    filter_count: number;
    booking_total: string;
    booking_total_count: number;
    checked_in_count: number;
    confirmed_count: number;
    arrivals_today: number;
    date_from: string;
    date_to: string;
    status: string;
    q: string;
  }>;
  fetchCashShiftHistory: () => Promise<Record<string, unknown>[]>;
  fetchDashboard: (date?: string) => Promise<Record<string, unknown>>;
  fetchReportHistory: (year?: number) => Promise<{
    year: number;
    years: number[];
    months: {
      num: number;
      label: string;
      flash_day: string;
      year: number;
      month: number;
    }[];
    profit_periods: Record<string, unknown>[];
  }>;
  orderServiceQuick: (payload: {
    room_number?: string;
    reservation_id?: number;
    service_id: number;
    quantity?: string;
    note?: string;
  }) => Promise<{
    order_id: number;
    service: string;
    quantity: string;
    amount: string;
    balance: string | null;
    reservation_id: number;
    room: string;
  }>;
  fetchServiceOrders: () => Promise<Record<string, unknown>[]>;
  updateServiceItem: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
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
  fetchHkStaff: () => Promise<{ id: number; username: string; name: string }[]>;
  assignHkTask: (taskId: number, userId?: number | null) => Promise<void>;
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
      company_id?: number | null;
      referrer_id?: number | null;
      commission_percent?: string | null;
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
    opts?: { method?: string; amount?: string; note?: string }
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
  updateCompany: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchCompanyDetail: (id: number) => Promise<Record<string, unknown>>;
  updateProfile: (payload: {
    first_name?: string;
    last_name?: string;
    email?: string;
    phone?: string;
    new_password?: string;
  }) => Promise<MePayload>;
  refreshMe: () => Promise<MePayload>;
  updateRoomType: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  updateAdminRoom: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  createFloor: (payload: {
    number: number;
    name?: string;
  }) => Promise<Record<string, unknown>>;
  updateFloor: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchCityLedger: (status?: string) => Promise<Record<string, unknown>[]>;
  fetchCityLedgerDetail: (
    id: number,
    withPdf?: boolean
  ) => Promise<Record<string, unknown>>;
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
  fetchExpenses: (status?: string) => Promise<Record<string, unknown>[]>;
  fetchExpenseMeta: () => Promise<Record<string, unknown>>;
  createExpense: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>;
  approveExpense: (id: number) => Promise<Record<string, unknown>>;
  payExpense: (id: number) => Promise<Record<string, unknown>>;
  rejectExpense: (
    id: number,
    reason?: string
  ) => Promise<Record<string, unknown>>;
  reopenExpense: (id: number) => Promise<Record<string, unknown>>;
  deleteExpense: (id: number) => Promise<Record<string, unknown>>;
  createExpenseCategory: (name: string) => Promise<Record<string, unknown>>;
  createExpenseVendor: (payload: {
    name: string;
    phone?: string;
  }) => Promise<Record<string, unknown>>;
  fetchPnl: (year?: number, month?: number) => Promise<Record<string, unknown>>;
  fetchFx: () => Promise<{
    items: Record<string, unknown>[];
    base_currency: string;
    live: Record<string, string | null>;
  }>;
  createFx: (payload: {
    currency: string;
    rate: string;
    effective_on?: string;
    note?: string;
  }) => Promise<Record<string, unknown>>;
  deleteFx: (id: number) => Promise<Record<string, unknown>>;
  syncCbuFx: (force?: boolean) => Promise<Record<string, unknown>>;
  fetchProfit: () => Promise<Record<string, unknown>>;
  fetchProfitPartners: () => Promise<Record<string, unknown>[]>;
  createProfitPartner: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  updateProfitPartner: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  withdrawProfit: (payload: {
    partner_id: number;
    amount: string;
    method?: string;
    note?: string;
  }) => Promise<Record<string, unknown>>;
  resetProfit: (ended_on?: string) => Promise<Record<string, unknown>>;
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
  createInventoryItem: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  updateInventoryItem: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchReferrers: (q?: string) => Promise<Record<string, unknown>[]>;
  createReferrer: (payload: {
    name: string;
    phone?: string;
    default_commission_percent?: string;
  }) => Promise<Record<string, unknown>>;
  updateReferrer: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
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
  createEmployee: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  payEmployee: (
    id: number,
    opts?: { days?: number; work_date?: string; method?: string }
  ) => Promise<Record<string, unknown>>;
  advanceEmployee: (
    id: number,
    amount: string,
    note?: string
  ) => Promise<Record<string, unknown>>;
  fetchHrAdvances: () => Promise<Record<string, unknown>[]>;
  settleHrAdvance: (id: number) => Promise<Record<string, unknown>>;
  syncOccupants: (
    reservationId: number,
    occupants: Record<string, unknown>[]
  ) => Promise<Record<string, unknown>>;
  fetchPayroll: (year?: number, month?: number) => Promise<Record<string, unknown>>;
  generatePayroll: (
    year?: number,
    month?: number
  ) => Promise<Record<string, unknown>>;
  finalizePayroll: (id: number) => Promise<Record<string, unknown>>;
  payAllPayroll: (opts?: {
    year?: number;
    month?: number;
    method?: string;
  }) => Promise<Record<string, unknown>>;
  assignMaintenance: (id: number, userId?: number | null) => Promise<void>;
  cancelMaintenance: (id: number) => Promise<void>;
  spendMaintenance: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchPropertySettings: () => Promise<Record<string, unknown>>;
  updatePropertySettings: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchRoomTypes: () => Promise<Record<string, unknown>[]>;
  createRoomType: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchAdminRooms: () => Promise<{
    items: Record<string, unknown>[];
    floors: Record<string, unknown>[];
  }>;
  createAdminRoom: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchServicesCatalog: () => Promise<Record<string, unknown>[]>;
  createServiceItem: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchStaff: () => Promise<Record<string, unknown>[]>;
  fetchStaffMeta: () => Promise<{
    roles: { id: string; label: string }[];
    properties: { id: number; name: string }[];
  }>;
  inviteStaff: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  updateStaff: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchAuditLog: (opts?: {
    action?: string;
    user_id?: number;
    limit?: number;
  }) => Promise<Record<string, unknown>[]>;
  exportPaymentsCsv: () => Promise<{
    content_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  exportPnlCsv: (year?: number, month?: number) => Promise<{
    content_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  exportArCsv: () => Promise<{
    content_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  fetchEmehmonReport: (
    year?: number,
    month?: number
  ) => Promise<Record<string, unknown>>;
  printEmehmonStatement: (
    year?: number,
    month?: number
  ) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  fetchRatePlans: () => Promise<Record<string, unknown>[]>;
  createRatePlan: (
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  updateRatePlan: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  createRateSeason: (
    id: number,
    payload: Record<string, unknown>
  ) => Promise<Record<string, unknown>>;
  fetchRatePlanMatrix: (
    id: number,
    start?: string,
    days?: number
  ) => Promise<Record<string, unknown>>;
  printFlash: (date?: string) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  printPnl: (year?: number, month?: number) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  printCashShift: (id: number) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  printExpense: (id: number) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  printCommission: (
    referrerId: number,
    year?: number,
    month?: number
  ) => Promise<{
    pdf_base64: string;
    filename: string;
    mime_type?: string;
  }>;
  fetchNotifications: () => Promise<{
    count: number;
    day?: string;
    items: {
      key: string;
      kind: string;
      title: string;
      detail: string;
        pk?: number;
        url_name?: string;
        target?: string;
        target_id?: number;
      }[];
  }>;
  dismissNotification: (key: string) => Promise<Record<string, unknown>>;
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
        emehmon_amount?: string;
        emehmon_method?: string;
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
          emehmon_method: opts?.emehmon_method || "cash",
          ...(opts?.emehmon_amount
            ? { emehmon_amount: opts.emehmon_amount }
            : {}),
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
    async (
      reservationId: number,
      roomId: number,
      opts?: { reason?: string; update_rate?: boolean }
    ) => {
      if (!token) throw new Error("Not authenticated");
      const reason = typeof opts === "string" ? opts : opts?.reason || "";
      const updateRate =
        typeof opts === "object" && opts && "update_rate" in opts
          ? opts.update_rate
          : true;
      return apiRequest<TransferResult>(
        `/reservations/${reservationId}/transfer/`,
        {
          ...authOpts(),
          method: "POST",
          body: { room_id: roomId, reason, update_rate: updateRate !== false },
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

  const postMinibarQuick = useCallback(
    async (roomNumber: string, itemId: number, quantity = "1") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        room: string;
        guest: string;
        item: string;
        quantity: string;
        amount: string;
        balance: string | null;
        reservation_id: number;
      }>("/minibar/quick/", {
        ...authOpts(),
        method: "POST",
        body: { room_number: roomNumber, item_id: itemId, quantity },
      });
    },
    [token, authOpts]
  );

  const fetchReservationsList = useCallback(
    async (opts?: {
      date_from?: string;
      date_to?: string;
      status?: string;
      q?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (opts?.date_from) params.set("date_from", opts.date_from);
      if (opts?.date_to) params.set("date_to", opts.date_to);
      if (opts?.status) params.set("status", opts.status);
      if (opts?.q) params.set("q", opts.q);
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<{
        items: ReservationSummary[];
        statuses: { id: string; label: string }[];
        filter_count: number;
        booking_total: string;
        booking_total_count: number;
        checked_in_count: number;
        confirmed_count: number;
        arrivals_today: number;
        date_from: string;
        date_to: string;
        status: string;
        q: string;
      }>(`/reservations/list/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchCashShiftHistory = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/cash-shift/history/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const fetchDashboard = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<Record<string, unknown>>(
        `/reports/dashboard/${q}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const fetchReportHistory = useCallback(
    async (year?: number) => {
      if (!token) throw new Error("Not authenticated");
      const q = year ? `?year=${year}` : "";
      return apiRequest<{
        year: number;
        years: number[];
        months: {
          num: number;
          label: string;
          flash_day: string;
          year: number;
          month: number;
        }[];
        profit_periods: Record<string, unknown>[];
      }>(`/reports/history/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const orderServiceQuick = useCallback(
    async (payload: {
      room_number?: string;
      reservation_id?: number;
      service_id: number;
      quantity?: string;
      note?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        order_id: number;
        service: string;
        quantity: string;
        amount: string;
        balance: string | null;
        reservation_id: number;
        room: string;
      }>("/services/order/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchServiceOrders = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/services/orders/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const updateServiceItem = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/services/${id}/update/`,
        {
          ...authOpts(),
          method: "POST",
          body: payload,
        }
      );
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

  const fetchHkStaff = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{
      items: { id: number; username: string; name: string }[];
    }>("/housekeeping/staff/", authOpts());
    return data.items;
  }, [token, authOpts]);

  const assignHkTask = useCallback(
    async (taskId: number, userId?: number | null) => {
      if (!token) throw new Error("Not authenticated");
      await apiRequest(`/housekeeping/tasks/${taskId}/assign/`, {
        ...authOpts(),
        method: "POST",
        body: userId ? { user_id: userId } : {},
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
        company_id?: number | null;
        referrer_id?: number | null;
        commission_percent?: string | null;
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
    async (
      reservationId: number,
      opts?: { method?: string; amount?: string; note?: string } | string
    ) => {
      if (!token) throw new Error("Not authenticated");
      // Back-compat: postEmehmon(id, "cash")
      const body =
        typeof opts === "string"
          ? { method: opts }
          : {
              method: opts?.method || "cash",
              ...(opts?.amount ? { amount: opts.amount } : {}),
              ...(opts?.note ? { note: opts.note } : {}),
            };
      return apiRequest<{ amount: string; balance: string }>(
        `/reservations/${reservationId}/emehmon/`,
        { ...authOpts(), method: "POST", body }
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

  const updateCompany = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/companies/${id}/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchCompanyDetail = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/companies/${id}/`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const updateProfile = useCallback(
    async (payload: {
      first_name?: string;
      last_name?: string;
      email?: string;
      phone?: string;
      new_password?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      const data = await apiRequest<MePayload>("/me/update/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
      setMe(data);
      return data;
    },
    [token, authOpts]
  );

  const refreshMe = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<MePayload>("/me/", authOpts());
    setMe(data);
    return data;
  }, [token, authOpts]);

  const updateRoomType = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/room-types/${id}/update/`,
        { ...authOpts(), method: "POST", body: payload }
      );
    },
    [token, authOpts]
  );

  const updateAdminRoom = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/rooms/${id}/update/`,
        { ...authOpts(), method: "POST", body: payload }
      );
    },
    [token, authOpts]
  );

  const createFloor = useCallback(
    async (payload: { number: number; name?: string }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/floors/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const updateFloor = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/floors/${id}/update/`,
        { ...authOpts(), method: "POST", body: payload }
      );
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

  const fetchCityLedgerDetail = useCallback(
    async (id: number, withPdf = false) => {
      if (!token) throw new Error("Not authenticated");
      const q = withPdf ? "?pdf=1" : "";
      return apiRequest<Record<string, unknown>>(
        `/city-ledger/${id}/${q}`,
        authOpts()
      );
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

  const fetchExpenses = useCallback(async (status = "") => {
    if (!token) throw new Error("Not authenticated");
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      `/expenses/${q}`,
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const fetchExpenseMeta = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<Record<string, unknown>>("/expenses/meta/", authOpts());
  }, [token, authOpts]);

  const createExpense = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/expenses/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const approveExpense = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/expenses/${id}/approve/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const payExpense = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/expenses/${id}/pay/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const rejectExpense = useCallback(
    async (id: number, reason = "") => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/expenses/${id}/reject/`, {
        ...authOpts(),
        method: "POST",
        body: reason ? { reason } : {},
      });
    },
    [token, authOpts]
  );

  const reopenExpense = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/expenses/${id}/reopen/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const deleteExpense = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/expenses/${id}/delete/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const createExpenseCategory = useCallback(
    async (name: string) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        "/expenses/categories/create/",
        {
          ...authOpts(),
          method: "POST",
          body: { name },
        }
      );
    },
    [token, authOpts]
  );

  const createExpenseVendor = useCallback(
    async (payload: { name: string; phone?: string }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/expenses/vendors/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

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

  const fetchFx = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      items: Record<string, unknown>[];
      base_currency: string;
      live: Record<string, string | null>;
    }>("/fx/", authOpts());
  }, [token, authOpts]);

  const createFx = useCallback(
    async (payload: {
      currency: string;
      rate: string;
      effective_on?: string;
      note?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/fx/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const deleteFx = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/fx/${id}/delete/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const syncCbuFx = useCallback(
    async (force = true) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/fx/sync-cbu/", {
        ...authOpts(),
        method: "POST",
        body: { force },
      });
    },
    [token, authOpts]
  );

  const fetchProfit = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<Record<string, unknown>>("/profit/", authOpts());
  }, [token, authOpts]);

  const fetchProfitPartners = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/profit/partners/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const createProfitPartner = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/profit/partners/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const updateProfitPartner = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/profit/partners/${id}/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const withdrawProfit = useCallback(
    async (payload: {
      partner_id: number;
      amount: string;
      method?: string;
      note?: string;
    }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/profit/withdraw/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const resetProfit = useCallback(
    async (ended_on?: string) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/profit/reset/", {
        ...authOpts(),
        method: "POST",
        body: ended_on ? { ended_on } : {},
      });
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

  const createInventoryItem = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/inventory/items/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const updateInventoryItem = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/inventory/items/${id}/update/`,
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

  const updateReferrer = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/referrers/${id}/`, {
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

  const fetchHrAdvances = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/hr/advances/?open=1",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const settleHrAdvance = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/hr/advances/${id}/settle/`,
        { ...authOpts(), method: "POST", body: {} }
      );
    },
    [token, authOpts]
  );

  const syncOccupants = useCallback(
    async (reservationId: number, occupants: Record<string, unknown>[]) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/reservations/${reservationId}/occupants/`,
        { ...authOpts(), method: "POST", body: { occupants } }
      );
    },
    [token, authOpts]
  );

  const createEmployee = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/hr/employees/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchPayroll = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (month) params.set("month", String(month));
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<Record<string, unknown>>(`/hr/payroll/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const generatePayroll = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/hr/payroll/generate/", {
        ...authOpts(),
        method: "POST",
        body: { year, month },
      });
    },
    [token, authOpts]
  );

  const finalizePayroll = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/hr/payroll/${id}/finalize/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const payAllPayroll = useCallback(
    async (opts?: { year?: number; month?: number; method?: string }) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/hr/payroll/pay-all/", {
        ...authOpts(),
        method: "POST",
        body: opts || {},
      });
    },
    [token, authOpts]
  );

  const assignMaintenance = useCallback(
    async (id: number, userId?: number | null) => {
      if (!token) throw new Error("Not authenticated");
      await apiRequest(`/maintenance/${id}/assign/`, {
        ...authOpts(),
        method: "POST",
        body: userId ? { user_id: userId } : {},
      });
    },
    [token, authOpts]
  );

  const cancelMaintenance = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      await apiRequest(`/maintenance/${id}/cancel/`, {
        ...authOpts(),
        method: "POST",
        body: {},
      });
    },
    [token, authOpts]
  );

  const spendMaintenance = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/maintenance/${id}/spend/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchPropertySettings = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<Record<string, unknown>>("/setup/settings/", authOpts());
  }, [token, authOpts]);

  const updatePropertySettings = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/settings/update/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchRoomTypes = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/setup/room-types/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const createRoomType = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/room-types/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchAdminRooms = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      items: Record<string, unknown>[];
      floors: Record<string, unknown>[];
    }>("/setup/rooms/", authOpts());
  }, [token, authOpts]);

  const createAdminRoom = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/rooms/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchServicesCatalog = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/setup/services/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const createServiceItem = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/services/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchStaff = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/staff/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const fetchStaffMeta = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      roles: { id: string; label: string }[];
      properties: { id: number; name: string }[];
    }>("/staff/meta/", authOpts());
  }, [token, authOpts]);

  const inviteStaff = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/staff/invite/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const updateStaff = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(`/staff/${id}/`, {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const fetchAuditLog = useCallback(
    async (opts?: { action?: string; user_id?: number; limit?: number }) => {
      if (!token) throw new Error("Not authenticated");
      const q = new URLSearchParams();
      if (opts?.action) q.set("action", opts.action);
      if (opts?.user_id) q.set("user_id", String(opts.user_id));
      if (opts?.limit) q.set("limit", String(opts.limit));
      const qs = q.toString();
      const data = await apiRequest<{ items: Record<string, unknown>[] }>(
        `/reports/audit/${qs ? `?${qs}` : ""}`,
        authOpts()
      );
      return data.items;
    },
    [token, authOpts]
  );

  const exportPaymentsCsv = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      content_base64: string;
      filename: string;
      mime_type?: string;
    }>("/export/payments.csv/", authOpts());
  }, [token, authOpts]);

  const exportPnlCsv = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const q = new URLSearchParams();
      if (year) q.set("year", String(year));
      if (month) q.set("month", String(month));
      const qs = q.toString();
      return apiRequest<{
        content_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/export/pnl.csv/${qs ? `?${qs}` : ""}`, authOpts());
    },
    [token, authOpts]
  );

  const exportArCsv = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      content_base64: string;
      filename: string;
      mime_type?: string;
    }>("/export/ar.csv/", authOpts());
  }, [token, authOpts]);

  const fetchEmehmonReport = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const q = new URLSearchParams();
      if (year) q.set("year", String(year));
      if (month) q.set("month", String(month));
      const qs = q.toString();
      return apiRequest<Record<string, unknown>>(
        `/reports/emehmon/${qs ? `?${qs}` : ""}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const printEmehmonStatement = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const q = new URLSearchParams();
      if (year) q.set("year", String(year));
      if (month) q.set("month", String(month));
      const qs = q.toString();
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/reports/emehmon/print/${qs ? `?${qs}` : ""}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchRatePlans = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    const data = await apiRequest<{ items: Record<string, unknown>[] }>(
      "/setup/rate-plans/",
      authOpts()
    );
    return data.items;
  }, [token, authOpts]);

  const createRatePlan = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/setup/rate-plans/create/", {
        ...authOpts(),
        method: "POST",
        body: payload,
      });
    },
    [token, authOpts]
  );

  const updateRatePlan = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/rate-plans/${id}/update/`,
        {
          ...authOpts(),
          method: "POST",
          body: payload,
        }
      );
    },
    [token, authOpts]
  );

  const createRateSeason = useCallback(
    async (id: number, payload: Record<string, unknown>) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>(
        `/setup/rate-plans/${id}/seasons/`,
        {
          ...authOpts(),
          method: "POST",
          body: payload,
        }
      );
    },
    [token, authOpts]
  );

  const fetchRatePlanMatrix = useCallback(
    async (id: number, start?: string, days = 42) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (start) params.set("start", start);
      params.set("days", String(days));
      return apiRequest<Record<string, unknown>>(
        `/setup/rate-plans/${id}/matrix/?${params}`,
        authOpts()
      );
    },
    [token, authOpts]
  );

  const printFlash = useCallback(
    async (date?: string) => {
      if (!token) throw new Error("Not authenticated");
      const q = date ? `?date=${encodeURIComponent(date)}` : "";
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/reports/flash/print/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const printPnl = useCallback(
    async (year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (month) params.set("month", String(month));
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/reports/pnl/print/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const printCashShift = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/cash-shift/${id}/print/`, authOpts());
    },
    [token, authOpts]
  );

  const printExpense = useCallback(
    async (id: number) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/expenses/${id}/print/`, authOpts());
    },
    [token, authOpts]
  );

  const printCommission = useCallback(
    async (referrerId: number, year?: number, month?: number) => {
      if (!token) throw new Error("Not authenticated");
      const params = new URLSearchParams();
      if (year) params.set("year", String(year));
      if (month) params.set("month", String(month));
      const q = params.toString() ? `?${params}` : "";
      return apiRequest<{
        pdf_base64: string;
        filename: string;
        mime_type?: string;
      }>(`/reports/commission/${referrerId}/print/${q}`, authOpts());
    },
    [token, authOpts]
  );

  const fetchNotifications = useCallback(async () => {
    if (!token) throw new Error("Not authenticated");
    return apiRequest<{
      count: number;
      day?: string;
      items: {
        key: string;
        kind: string;
        title: string;
        detail: string;
        pk?: number;
        url_name?: string;
        target?: string;
        target_id?: number;
      }[];
    }>("/notifications/", authOpts());
  }, [token, authOpts]);

  const dismissNotification = useCallback(
    async (key: string) => {
      if (!token) throw new Error("Not authenticated");
      return apiRequest<Record<string, unknown>>("/notifications/dismiss/", {
        ...authOpts(),
        method: "POST",
        body: { key },
      });
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
      postMinibarQuick,
      fetchReservationsList,
      fetchCashShiftHistory,
      fetchDashboard,
      fetchReportHistory,
      orderServiceQuick,
      fetchServiceOrders,
      updateServiceItem,
      confirmInquiry,
      fetchInquiries,
      searchGuests,
      createGuest,
      fetchHousekeeping,
      completeHkTask,
      fetchHkStaff,
      assignHkTask,
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
      updateCompany,
      fetchCompanyDetail,
      updateProfile,
      refreshMe,
      updateRoomType,
      updateAdminRoom,
      createFloor,
      updateFloor,
      fetchCityLedger,
      fetchCityLedgerDetail,
      payCityLedger,
      fetchGroups,
      fetchGroup,
      createGroup,
      fetchNightAudit,
      runNightAudit,
      fetchExpenses,
      fetchExpenseMeta,
      createExpense,
      approveExpense,
      payExpense,
      rejectExpense,
      reopenExpense,
      deleteExpense,
      createExpenseCategory,
      createExpenseVendor,
      fetchPnl,
      fetchFx,
      createFx,
      deleteFx,
      syncCbuFx,
      fetchProfit,
      fetchProfitPartners,
      createProfitPartner,
      updateProfitPartner,
      withdrawProfit,
      resetProfit,
      fetchInventory,
      adjustInventory,
      createInventoryItem,
      updateInventoryItem,
      fetchReferrers,
      createReferrer,
      updateReferrer,
      fetchCommission,
      payCommission,
      fetchEmployees,
      createEmployee,
      payEmployee,
      advanceEmployee,
      fetchHrAdvances,
      settleHrAdvance,
      syncOccupants,
      fetchPayroll,
      generatePayroll,
      finalizePayroll,
      payAllPayroll,
      assignMaintenance,
      cancelMaintenance,
      spendMaintenance,
      fetchPropertySettings,
      updatePropertySettings,
      fetchRoomTypes,
      createRoomType,
      fetchAdminRooms,
      createAdminRoom,
      fetchServicesCatalog,
      createServiceItem,
      fetchStaff,
      fetchStaffMeta,
      inviteStaff,
      updateStaff,
      fetchAuditLog,
      exportPaymentsCsv,
      exportPnlCsv,
      exportArCsv,
      fetchEmehmonReport,
      printEmehmonStatement,
      fetchRatePlans,
      createRatePlan,
      updateRatePlan,
      createRateSeason,
      fetchRatePlanMatrix,
      printFlash,
      printPnl,
      printCashShift,
      printExpense,
      printCommission,
      fetchNotifications,
      dismissNotification,
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
      postMinibarQuick,
      fetchReservationsList,
      fetchCashShiftHistory,
      fetchDashboard,
      fetchReportHistory,
      orderServiceQuick,
      fetchServiceOrders,
      updateServiceItem,
      confirmInquiry,
      fetchInquiries,
      searchGuests,
      createGuest,
      fetchHousekeeping,
      completeHkTask,
      fetchHkStaff,
      assignHkTask,
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
      updateCompany,
      fetchCompanyDetail,
      updateProfile,
      refreshMe,
      updateRoomType,
      updateAdminRoom,
      createFloor,
      updateFloor,
      fetchCityLedger,
      fetchCityLedgerDetail,
      payCityLedger,
      fetchGroups,
      fetchGroup,
      createGroup,
      fetchNightAudit,
      runNightAudit,
      fetchExpenses,
      fetchExpenseMeta,
      createExpense,
      approveExpense,
      payExpense,
      rejectExpense,
      reopenExpense,
      deleteExpense,
      createExpenseCategory,
      createExpenseVendor,
      fetchPnl,
      fetchFx,
      createFx,
      deleteFx,
      syncCbuFx,
      fetchProfit,
      fetchProfitPartners,
      createProfitPartner,
      updateProfitPartner,
      withdrawProfit,
      resetProfit,
      fetchInventory,
      adjustInventory,
      createInventoryItem,
      updateInventoryItem,
      fetchReferrers,
      createReferrer,
      updateReferrer,
      fetchCommission,
      payCommission,
      fetchEmployees,
      createEmployee,
      payEmployee,
      advanceEmployee,
      fetchHrAdvances,
      settleHrAdvance,
      syncOccupants,
      fetchPayroll,
      generatePayroll,
      finalizePayroll,
      payAllPayroll,
      assignMaintenance,
      cancelMaintenance,
      spendMaintenance,
      fetchPropertySettings,
      updatePropertySettings,
      fetchRoomTypes,
      createRoomType,
      fetchAdminRooms,
      createAdminRoom,
      fetchServicesCatalog,
      createServiceItem,
      fetchStaff,
      fetchStaffMeta,
      inviteStaff,
      updateStaff,
      fetchAuditLog,
      exportPaymentsCsv,
      exportPnlCsv,
      exportArCsv,
      fetchEmehmonReport,
      printEmehmonStatement,
      fetchRatePlans,
      createRatePlan,
      updateRatePlan,
      createRateSeason,
      fetchRatePlanMatrix,
      printFlash,
      printPnl,
      printCashShift,
      printExpense,
      printCommission,
      fetchNotifications,
      dismissNotification,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
