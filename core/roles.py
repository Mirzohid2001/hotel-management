"""Hotel tenant RBAC — 6 roles with module permission groups."""

from tenants.models import TenantMembership

R = TenantMembership.Role

ALL_STAFF = (
    R.ADMIN,
    R.MANAGER,
    R.RECEPTIONIST,
    R.HOUSEKEEPER,
    R.ACCOUNTANT,
    R.HR,
)

# Xodimlar ro‘yxati / taklif — faqat admin
STAFF_ADMIN = (R.ADMIN,)
TENANT_ADMIN = (R.ADMIN,)
DAY_LOCK_OVERRIDE = (R.ADMIN,)

# Mehmonxona sozlamalari (xonalar, tariflar)
PROPERTY_ADMIN = (R.ADMIN, R.MANAGER)

# Qabulxona, bron, mehmonlar
FRONT_OFFICE = (R.ADMIN, R.MANAGER, R.RECEPTIONIST)

# Folio to‘lov / charge
FRONT_DESK_MONEY = (R.ADMIN, R.MANAGER, R.RECEPTIONIST, R.ACCOUNTANT)

# Void charge/payment — receptionist emas
MONEY_VOID = (R.ADMIN, R.MANAGER, R.ACCOUNTANT)

# Bosh sahifa (operatsion dashboard)
DASHBOARD = (R.ADMIN, R.MANAGER, R.RECEPTIONIST, R.ACCOUNTANT)

# Kassa smena
CASH = (R.ADMIN, R.MANAGER, R.RECEPTIONIST, R.ACCOUNTANT)

# Tozalash
HOUSEKEEPING = (R.ADMIN, R.MANAGER, R.HOUSEKEEPER)

# Rasxodlar, moliya
FINANCE = (R.ADMIN, R.MANAGER, R.ACCOUNTANT)

# Oylik / HR moduli
HR = (R.ADMIN, R.MANAGER, R.HR)

# Ta’mir, transfer, operatsion
OPS_MANAGER = (R.ADMIN, R.MANAGER)

# Kun yopish, P&L, eksport, nazorat
AUDIT = (R.ADMIN, R.MANAGER, R.ACCOUNTANT)
ACCOUNTING = (R.ADMIN, R.MANAGER, R.ACCOUNTANT)

# Inventar / minibar (ops + hisob)
INVENTORY = (R.ADMIN, R.MANAGER, R.ACCOUNTANT, R.RECEPTIONIST)

# Xizmatlar katalogi
SERVICES = (R.ADMIN, R.MANAGER, R.RECEPTIONIST)


def nav_permissions(role: str | None) -> dict[str, bool]:
    """Template-friendly flags for sidebar / hub visibility."""
    if not role:
        return {
            "front_office": False,
            "properties": False,
            "housekeeping": False,
            "services": False,
            "inventory": False,
            "maintenance": False,
            "cash": False,
            "city_ledger": False,
            "expenses": False,
            "hr": False,
            "pnl": False,
            "audit": False,
            "staff": False,
        }
    return {
        "front_office": role in FRONT_OFFICE,
        "properties": role in PROPERTY_ADMIN,
        "housekeeping": role in HOUSEKEEPING,
        "services": role in SERVICES,
        "inventory": role in INVENTORY,
        "maintenance": role in OPS_MANAGER,
        "cash": role in CASH,
        "city_ledger": role in FINANCE,
        "expenses": role in FINANCE,
        "hr": role in HR,
        "pnl": role in ACCOUNTING,
        "audit": role in AUDIT,
        "staff": role in STAFF_ADMIN,
    }


def home_url_name(role: str | None) -> str:
    """Post-login landing by role."""
    if role == R.HOUSEKEEPER:
        return "housekeeping:board"
    if role in {R.MANAGER, R.RECEPTIONIST}:
        return "bookings:board"
    if role == R.ACCOUNTANT:
        return "reports:pnl"
    if role == R.HR:
        return "hr:employees"
    return "reports:dashboard"
