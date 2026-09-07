from django.db import migrations


def mark_paid_emehmon_required(apps, schema_editor):
    FolioCharge = apps.get_model("folio", "FolioCharge")
    Reservation = apps.get_model("bookings", "Reservation")
    ids = (
        FolioCharge.objects.filter(charge_type="emehmon", is_void=False)
        .values_list("folio__reservation_id", flat=True)
        .distinct()
    )
    Reservation.objects.filter(pk__in=ids, emehmon_required=False).update(
        emehmon_required=True
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0008_reservation_emehmon_required"),
        ("folio", "0008_backfill_amount_base"),
    ]

    operations = [
        migrations.RunPython(mark_paid_emehmon_required, noop_reverse),
    ]
