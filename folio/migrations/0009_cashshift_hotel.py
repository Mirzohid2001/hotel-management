# Generated manually — CashShift.hotel (per-branch cash drawer)

from django.db import migrations, models
import django.db.models.deletion


def assign_shift_hotels(apps, schema_editor):
    CashShift = apps.get_model("folio", "CashShift")
    Property = apps.get_model("properties", "Property")
    for tenant_id in CashShift.objects.values_list("tenant_id", flat=True).distinct():
        prop = Property.objects.filter(tenant_id=tenant_id).order_by("id").first()
        if prop is None:
            continue
        CashShift.objects.filter(tenant_id=tenant_id, hotel_id__isnull=True).update(
            hotel_id=prop.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0009_emehmon_per_guest_night"),
        ("folio", "0008_backfill_amount_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashshift",
            name="hotel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cash_shifts",
                to="properties.property",
            ),
        ),
        migrations.RunPython(assign_shift_hotels, migrations.RunPython.noop),
    ]
