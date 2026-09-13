"""Guest pickers — alphabetical, case-insensitive."""

from django.db.models.functions import Lower

from guests.models import Guest


def guests_for_select(tenant):
    """Guests for booking forms: A→Z by displayed full name."""
    return Guest.objects.filter(tenant=tenant).order_by(
        Lower("first_name"), Lower("last_name"), "pk"
    )
