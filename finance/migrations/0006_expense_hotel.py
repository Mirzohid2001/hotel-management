# Generated manually — Expense.hotel (per-branch expenses)

from django.db import migrations, models
import django.db.models.deletion


def assign_expense_hotels(apps, schema_editor):
    Expense = apps.get_model("finance", "Expense")
    Property = apps.get_model("properties", "Property")
    for tenant_id in Expense.objects.values_list("tenant_id", flat=True).distinct():
        prop = Property.objects.filter(tenant_id=tenant_id).order_by("id").first()
        if prop is None:
            continue
        Expense.objects.filter(tenant_id=tenant_id, hotel_id__isnull=True).update(
            hotel_id=prop.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0009_emehmon_per_guest_night"),
        ("finance", "0005_backfill_amount_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="hotel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="expenses",
                to="properties.property",
            ),
        ),
        migrations.RunPython(assign_expense_hotels, migrations.RunPython.noop),
    ]
