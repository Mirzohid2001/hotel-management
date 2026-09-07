from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction

from folio.models import FolioCharge
from folio.services import add_charge, ensure_folio_for_reservation

from .models import ServiceItem, ServiceOrder


@transaction.atomic
def order_service(*, reservation, service: ServiceItem, user, quantity=Decimal("1"), note="") -> ServiceOrder:
    if not service.is_active:
        raise ValidationError(_("Xizmat faol emas."))
    folio = ensure_folio_for_reservation(reservation)
    charge = add_charge(
        folio,
        user,
        charge_type=FolioCharge.ChargeType.SERVICE,
        description=service.name,
        unit_price=service.unit_price,
        quantity=quantity,
        currency=getattr(service, "currency", None)
        or getattr(reservation, "currency", None)
        or reservation.tenant.currency,
    )
    return ServiceOrder.objects.create(
        tenant=reservation.tenant,
        reservation=reservation,
        service=service,
        quantity=quantity,
        unit_price=service.unit_price,
        note=note,
        posted_by=user,
        folio_charge=charge,
    )
