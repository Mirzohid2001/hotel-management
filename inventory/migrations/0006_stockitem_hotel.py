# Generated manually — StockItem.hotel (per-branch inventory)

from django.db import migrations, models
import django.db.models.deletion


def assign_stock_hotels(apps, schema_editor):
    StockItem = apps.get_model("inventory", "StockItem")
    Property = apps.get_model("properties", "Property")
    for tenant_id in StockItem.objects.values_list("tenant_id", flat=True).distinct():
        prop = Property.objects.filter(tenant_id=tenant_id).order_by("id").first()
        if prop is None:
            continue
        StockItem.objects.filter(tenant_id=tenant_id, hotel_id__isnull=True).update(
            hotel_id=prop.id
        )


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0009_emehmon_per_guest_night"),
        ("inventory", "0005_currency_accounting"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="hotel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stock_items",
                to="properties.property",
            ),
        ),
        migrations.RunPython(assign_stock_hotels, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="stockitem",
            unique_together={("tenant", "hotel", "sku")},
        ),
    ]
