# Generated manually — backfill amount_base = amount for existing rows

from django.db import migrations
from django.db.models import F


def backfill_amount_base(apps, schema_editor):
    for model_name in (
        "FolioCharge",
        "GuestPayment",
        "CashShiftMovement",
        "CompanyInvoiceLine",
        "CompanyPayment",
    ):
        Model = apps.get_model("folio", model_name)
        Model.objects.filter(amount_base=0).exclude(amount=0).update(
            amount_base=F("amount"), fx_rate=1
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("folio", "0007_multicurrency"),
    ]

    operations = [
        migrations.RunPython(backfill_amount_base, noop),
    ]
