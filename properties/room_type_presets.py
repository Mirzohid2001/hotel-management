"""Ideal mehmonxona xona turi shablonlari."""

from decimal import Decimal

from django.utils.translation import gettext_lazy as _


# Faqat Double / Twin / Triple — price_factor: Double/Twin = 1.0 baza
STANDARD_ROOM_TYPE_PRESETS = (
    {
        "code": "twin",
        "name": _("Twin"),
        "name_uz": "Ikki alohida",
        "capacity_adults": 2,
        "capacity_children": 0,
        "price_factor": Decimal("1.00"),
        "description": _("Ikki alohida (single) yotoq — 2 kishi."),
    },
    {
        "code": "double",
        "name": _("Double"),
        "name_uz": "Juftlik",
        "capacity_adults": 2,
        "capacity_children": 0,
        "price_factor": Decimal("1.00"),
        "description": _("Bitta katta (double/queen) yotoq — juftlik."),
    },
    {
        "code": "triple",
        "name": _("Triple"),
        "name_uz": "Uch kishilik",
        "capacity_adults": 3,
        "capacity_children": 0,
        "price_factor": Decimal("1.35"),
        "description": _("Uch kishi uchun xona."),
    },
)

STANDARD_ROOM_TYPE_CODES = frozenset(p["code"] for p in STANDARD_ROOM_TYPE_PRESETS)

# Eski preset kodlari → yangi standart (xonani qayta biriktirish)
LEGACY_ROOM_TYPE_REMAP = {
    "single": "twin",
    "family": "triple",
    "deluxe": "double",
    "suite": "double",
}

DEFAULT_BASE_PRICE = Decimal("500000")
