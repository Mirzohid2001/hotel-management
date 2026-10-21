"""Mehmon cheki uchun imzolangan ochiq havola + QR."""

from __future__ import annotations

import base64
from io import BytesIO

from django.core import signing
from django.db.models import Prefetch
from django.urls import reverse

SALT = "folio.receipt.v1"


def make_receipt_token(folio) -> str:
    return signing.dumps(
        {"f": folio.pk, "t": folio.tenant_id},
        salt=SALT,
    )


def resolve_receipt_token(token: str):
    """Token bo‘yicha Folio yoki None."""
    from .models import Folio, FolioCharge, GuestPayment

    try:
        data = signing.loads(token, salt=SALT)
        folio_id = int(data["f"])
        tenant_id = int(data["t"])
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError, ValueError):
        return None

    return (
        Folio.objects.select_related(
            "tenant",
            "reservation",
            "reservation__guest",
            "reservation__hotel",
            "reservation__room",
        )
        .prefetch_related(
            Prefetch(
                "charges",
                queryset=FolioCharge.objects.filter(is_void=False).order_by("created_at"),
            ),
            Prefetch(
                "payments",
                queryset=GuestPayment.objects.filter(is_void=False).order_by("created_at"),
            ),
        )
        .filter(pk=folio_id, tenant_id=tenant_id)
        .first()
    )


def receipt_share_path(folio) -> str:
    return reverse("folio:receipt_share", kwargs={"token": make_receipt_token(folio)})


def receipt_share_url(request, folio) -> str:
    return request.build_absolute_uri(receipt_share_path(folio))


def receipt_qr_png_bytes(url: str) -> bytes:
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1410", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def receipt_qr_data_uri(url: str) -> str:
    raw = receipt_qr_png_bytes(url)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
