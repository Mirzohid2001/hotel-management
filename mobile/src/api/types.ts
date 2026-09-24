export type TenantInfo = {
  id: number;
  name: string;
  slug: string;
  role: string;
};

export type MePayload = {
  user: { id: number; username: string; full_name: string };
  tenant: { id: number; name: string; slug: string; currency: string };
  role: string;
  permissions: Record<string, boolean>;
  hotel: { id: number; name: string; branch_code: string } | null;
  hotels: { id: number; name: string; branch_code: string }[];
};

export type LoginResponse = {
  token: string;
  tenants: TenantInfo[];
  me: MePayload;
};

export type BoardTile = {
  room: {
    id: number;
    number: string;
    status: string;
    room_type: string;
    hotel_id: number;
  };
  state: "vacant" | "occupied" | "dirty" | "ooo" | string;
  reservation: {
    id: number;
    code: string;
    status: string;
    check_in: string;
    check_out: string;
    guest: { id: number; name: string };
    adults: number;
    children: number;
  } | null;
  folio: { id: number; balance: string; is_open: boolean } | null;
};

export type BoardData = {
  day: string;
  stats: {
    total: number;
    vacant: number;
    occupied: number;
    dirty: number;
    ooo: number;
  };
  tiles: BoardTile[];
  hotel_id: number | null;
};

export type FolioCharge = {
  id: number;
  charge_type: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
  is_void: boolean;
  created_at: string | null;
};

export type FolioPayment = {
  id: number;
  amount: string;
  method: string;
  kind: string;
  is_void: boolean;
  note: string;
  created_at: string | null;
};

export type ReservationDetail = {
  id: number;
  code: string;
  status: string;
  check_in: string;
  check_out: string;
  adults: number;
  children: number;
  guest: { id: number; name: string };
  room: { id: number | null; number: string; status?: string };
  hotel_id: number | null;
  notes: string;
  nightly_rate?: string;
  folio: {
    id: number;
    balance: string;
    is_open: boolean;
    charges: FolioCharge[];
    payments: FolioPayment[];
  } | null;
};

export type CheckInResult = {
  reservation_id: number;
  status: string;
  emehmon: string | null;
};

export type CheckOutResult = {
  reservation_id: number;
  status: string;
};

export type WalkInPayload = {
  room_id: number;
  first_name: string;
  last_name?: string;
  phone?: string;
  nights?: number;
  adults?: number;
  children?: number;
  doc_number?: string;
  allow_dirty?: boolean;
  allow_no_docs?: boolean;
  collect_emehmon?: boolean;
  nightly_rate?: string;
  notes?: string;
};

export type WalkInResult = {
  reservation_id: number;
  code: string;
  status: string;
  emehmon: string | null;
};

export type PaymentResult = {
  payment_id: number;
  amount: string;
  method: string;
  balance: string;
};

export type ChargeResult = {
  charge_id: number;
  amount: string;
  balance: string;
};

export type ServiceItem = {
  id: number;
  name: string;
  code: string;
  unit_price: string;
  currency: string;
};

export type ServiceOrderResult = {
  order_id: number;
  service: string;
  amount: string;
  balance: string | null;
};

export type RoomStatusResult = {
  room_id: number;
  number: string;
  status: string;
};

export type ReservationSummary = {
  id: number;
  code: string;
  status: string;
  check_in: string;
  check_out: string;
  adults: number;
  children: number;
  guest: { id: number; name: string };
  room: { id: number | null; number: string };
  hotel_id: number | null;
};

export type TodayData = {
  day: string;
  arrivals: ReservationSummary[];
  departures: ReservationSummary[];
  in_house: ReservationSummary[];
  counts: { arrivals: number; departures: number; in_house: number };
};

export type TransferResult = {
  reservation_id: number;
  room: { id: number | null; number: string };
  status: string;
};

export type ExtendResult = {
  reservation_id: number;
  check_in: string;
  check_out: string;
  status: string;
};

export type AvailableRoom = {
  id: number;
  number: string;
  status: string;
  room_type: string;
  room_type_id: number | null;
  hotel_id: number;
  base_price: string;
};

export type CreateReservationPayload = {
  room_id: number;
  first_name: string;
  last_name?: string;
  phone?: string;
  check_in: string;
  check_out: string;
  adults?: number;
  children?: number;
  nightly_rate?: string;
  notes?: string;
};

export type CreateReservationResult = {
  reservation_id: number;
  code: string;
  status: string;
  check_in: string;
  check_out: string;
};

export type CashShift = {
  id: number;
  is_open: boolean;
  hotel_id: number | null;
  opening_float: string;
  opened_at: string | null;
  closed_at: string | null;
  closing_cash: string | null;
  variance: string | null;
  expected_cash: string | null;
  notes: string;
};

export type GuestSummary = {
  id: number;
  name: string;
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  is_vip: boolean;
  is_blacklisted: boolean;
};

export type MinibarItem = {
  id: number;
  name: string;
  sku: string;
  sell_price: string;
  quantity_on_hand: string;
};

export type HkBoard = {
  stats: {
    ready: number;
    dirty: number;
    cleaning: number;
    ooo: number;
    total: number;
  };
  rooms: {
    id: number;
    number: string;
    status: string;
    room_type: string;
  }[];
  tasks: {
    id: number;
    title: string;
    status: string;
    room: { id: number; number: string };
    assigned_to: string;
  }[];
};

export type CalendarSegment =
  | {
      kind: "empty";
      date: string;
      colspan: number;
    }
  | {
      kind: "stay";
      colspan: number;
      status: string;
      is_vip: boolean;
      covers_today: boolean;
      start_day: string;
      reservation: {
        id: number;
        code: string;
        guest: string;
        check_in: string;
        check_out: string;
      };
      balance: string | null;
    };

export type CalendarData = {
  start: string;
  end: string;
  days: string[];
  days_count: number;
  stats: { rooms: number; stays: number; vip: number; vacant_cells: number };
  rows: {
    room: {
      id: number;
      number: string;
      status: string;
      room_type: string;
    };
    segments: CalendarSegment[];
  }[];
};

export type FlashReport = {
  day: string;
  flash: Record<string, unknown>;
  kpis: {
    dirty_rooms?: number;
    cleaning_rooms?: number;
    ooo_rooms?: number;
    ready_rooms?: number;
    inquiries?: number;
    hk_tasks?: number;
    maintenance_open?: number;
    open_folio_count?: number;
    open_folio_balance?: string | number;
    [key: string]: unknown;
  };
};

export type MaintenanceTicket = {
  id: number;
  title: string;
  description: string;
  priority: string;
  status: string;
  set_room_ooo: boolean;
  room: { id: number; number: string } | null;
  assignee: string;
  created_at: string | null;
};
