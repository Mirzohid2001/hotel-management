# Mobile JSON API (`/api/v1/`)

Additive layer for React Native. **Same database as web — changes sync live.**  
Does **not** change web views/templates.

## Sync model

- Web (session/HTML) and mobile (Bearer token) both call the same Django `services.py` rules.
- One hotel DB → board, folio, rooms, cash shift update instantly on both clients.

## Coverage

**Auth / scope:** login, logout, me (+ hotels), `X-Hotel-Id`

**Front desk:** board, today, inquiries, calendar, walk-in, rooms available/status, housekeeping, maintenance, reservations list (period/status), minibar quick (by room), services order/catalog/recent

**Reservations:** create/search/detail/list, check-in/out, payment/deposit/refund/split-pay, charge/service/minibar, transfer/extend/amend, cancel/no-show/confirm/notes, e-mehmon, void charge/payment

**Guests:** list/create, detail/update, documents

**Folio:** receipt (JSON + optional PDF), close, split-pay, to-company (city ledger)

**Companies / ledger:** companies list/create/update, city-ledger list/detail/PDF/pay

**Groups:** list/detail/create

**Inventory:** items list/create/update, adjust in/out/set, low-stock

**Referrers:** list/create/update, commission month report + pay

**HR:** employees list/create/update, advance, pay, advances settle, payroll generate/finalize/pay-all

**Setup (admin/manager):** property settings, room types/rooms, services catalog, rate plans (+ seasons)

**Maintenance:** list/create/complete/assign/cancel/spend

**Staff (admin):** list, invite, role/active update

**Reports / finance:** dashboard, flash (+ date), report history, night-audit, expenses (+ reject/reopen/delete), P&L, profit share, FX/CBU, audit log, e-mehmon month, CSV export (payments/P&L/AR), cash-shift history

**Cash:** shift open/close/movement, services catalog, minibar items

## Headers

- `Authorization: Bearer <token>`
- `X-Tenant-Id` (optional)
- `X-Hotel-Id` (hotel scope)

## Still thinner than web

Widget admin (Django admin only). Full season matrix *cell editor* (mobile: 42-day read + season create).

## Phase 1 additions (mobile parity)

- HK assign + staff list
- Expense create / approve / pay + meta (categories)
- Groups create UI (endpoint already existed)
- Calendar empty-cell → quick book
- Folio receipt PDF share (base64)

## Phase 2 additions (ops admin)

- Inventory item create/update
- HR employee create + payroll period generate/finalize/pay-all
- Property settings + room types/rooms + services catalog
- Maintenance assign / cancel / spend

## Phase 3 additions (admin / reports)

- Staff list / invite / role+active update
- Audit log (optional action filter)
- CSV export (payments, P&L, AR) as base64 for share
- Rate plans list/create/update + season create
- E-mehmon monthly report

## Phase 4 additions (booking / stay parity)

- Reservation create / walk-in: existing `guest_id`, `company_id`, `referrer_id`, `rate_plan_id`, occupants
- Occupants sync: `POST /reservations/<id>/occupants/`
- Reservation detail: company, referrer, rate_plan, occupants + missing count
- Board: OOO filter + long-press room status (ready / dirty / cleaning / OOO)
- Groups: multi-room create (rooms[])
- HR: advances list + settle wired on mobile

## Phase 5 additions (finance / setup)

- FX rates list/create/delete + CBU sync
- Profit share ledger / partners / withdraw / reset
- Expense reject / reopen / delete + category/vendor create
- Company + referrer update
- City ledger invoice detail + PDF
- Rate plan 42-day matrix (read)
