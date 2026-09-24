# Mobile JSON API (`/api/v1/`)

Additive layer for React Native. **Same database as web — changes sync live.**  
Does **not** change web views/templates.

## Sync model

- Web (session/HTML) and mobile (Bearer token) both call the same Django `services.py` rules.
- One hotel DB → board, folio, rooms, cash shift update instantly on both clients.

## Coverage

**Auth / scope:** login, logout, me (+ hotels), `X-Hotel-Id`

**Front desk:** board, today, inquiries, calendar, walk-in, rooms available/status, housekeeping, maintenance

**Reservations:** create/search/detail, check-in/out, payment/deposit/refund/split-pay, charge/service/minibar, transfer/extend/amend, cancel/no-show/confirm/notes, e-mehmon, void charge/payment

**Guests:** list/create, detail/update, documents

**Folio:** receipt (JSON + optional PDF), close, split-pay, to-company (city ledger)

**Companies / ledger:** companies list/create, city-ledger list/pay

**Groups:** list/detail/create

**Inventory:** items list (flags low/minibar/soon/expired), adjust in/out/set, low-stock

**Referrers:** list/create, commission month report + pay

**HR:** employees list, advance, pay (monthly/daily), advances list/settle

**Reports / finance:** flash, night-audit status/run, expenses, P&L

**Cash:** shift open/close/movement, services catalog, minibar items

## Headers

- `Authorization: Bearer <token>`
- `X-Tenant-Id` (optional)
- `X-Hotel-Id` (hotel scope)

## Still thinner than web

Property/admin settings, full inventory item CRUD, payroll period generate/finalize, PDF share UX on device.
