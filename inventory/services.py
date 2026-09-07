from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from folio.models import FolioCharge
from folio.services import add_charge, ensure_folio_for_reservation

from .models import MinibarSale, StockItem, StockMovement


def _stock_qs(tenant, hotel=None):
    qs = StockItem.objects.filter(tenant=tenant)
    if hotel is not None:
        qs = qs.filter(hotel=hotel)
    return qs


def low_stock_items(tenant, hotel=None):
    return _stock_qs(tenant, hotel).filter(
        is_active=True,
        reorder_level__gt=0,
    ).filter(quantity_on_hand__lte=F("reorder_level"))


def expired_stock_items(tenant, hotel=None, on_date=None):
    """Qoldiq > 0 va muddati o‘tgan faol mahsulotlar."""
    today = on_date or timezone.localdate()
    return _stock_qs(tenant, hotel).filter(
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=today,
        quantity_on_hand__gt=0,
    ).order_by("expiry_date", "name")


def expiring_soon_stock_items(tenant, hotel=None, on_date=None):
    """Muddat yaqin (alert_days ichida), lekin hali o‘tmagan."""
    today = on_date or timezone.localdate()
    qs = _stock_qs(tenant, hotel).filter(
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__gte=today,
        quantity_on_hand__gt=0,
    ).order_by("expiry_date", "name")
    soon = []
    for item in qs:
        alert_days = int(item.expiry_alert_days if item.expiry_alert_days is not None else 7)
        if item.expiry_date <= today + timedelta(days=alert_days):
            soon.append(item)
    return soon


@transaction.atomic
def adjust_stock(item: StockItem, *, movement_type: str, quantity: Decimal, user=None, note="") -> StockMovement:
    if quantity <= 0:
        raise ValidationError(_("Miqdor musbat bo‘lishi kerak."))
    qty = item.quantity_on_hand
    if movement_type == StockMovement.MovementType.IN:
        item.quantity_on_hand = qty + quantity
    elif movement_type == StockMovement.MovementType.OUT:
        if qty < quantity:
            raise ValidationError(_("Ombor yetarli emas."))
        item.quantity_on_hand = qty - quantity
    elif movement_type == StockMovement.MovementType.ADJUST:
        item.quantity_on_hand = quantity
    else:
        raise ValidationError(_("Noma’lum harakat turi."))
    item.save(update_fields=["quantity_on_hand", "updated_at"])
    return StockMovement.objects.create(
        tenant=item.tenant,
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        note=note,
        created_by=user,
    )


@transaction.atomic
def sell_minibar(*, reservation, item: StockItem, user, quantity=Decimal("1")) -> MinibarSale:
    if not item.is_minibar or not item.is_active:
        raise ValidationError(_("Mahsulot faol minibar emas."))
    if item.hotel_id and reservation.hotel_id and item.hotel_id != reservation.hotel_id:
        raise ValidationError(_("Minibar mahsuloti boshqa filial omboridan."))
    if item.expiry_status() == StockItem.ExpiryStatus.EXPIRED:
        raise ValidationError(
            _("«%(name)s» muddati o‘tgan (%(d)s) — sotish mumkin emas.")
            % {"name": item.name, "d": item.expiry_date}
        )
    adjust_stock(
        item,
        movement_type=StockMovement.MovementType.OUT,
        quantity=quantity,
        user=user,
        note=f"Minibar {reservation.code}",
    )
    folio = ensure_folio_for_reservation(reservation)
    charge = add_charge(
        folio,
        user,
        charge_type=FolioCharge.ChargeType.MINIBAR,
        description=item.name,
        unit_price=item.sell_price,
        quantity=quantity,
        currency=getattr(item, "currency", None)
        or getattr(reservation, "currency", None)
        or reservation.tenant.currency,
    )
    return MinibarSale.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        item=item,
        quantity=quantity,
        unit_price=item.sell_price,
        folio_charge=charge,
        created_by=user,
    )
