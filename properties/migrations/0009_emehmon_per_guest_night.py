from decimal import Decimal

from django.db import migrations, models


def set_emehmon_unit_9000(apps, schema_editor):
    """Eski «bir martalik» summalar endi kunlik tarif — 9000 ga yangilanadi."""
    PropertySettings = apps.get_model("properties", "PropertySettings")
    PropertySettings.objects.all().update(emehmon_fee=Decimal("9000"))


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0008_multicurrency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propertysettings",
            name="emehmon_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("9000"),
                help_text="E-mehmon: 1 mehmon × 1 kecha tarifi (odatda 9000 so‘m).",
                max_digits=14,
            ),
        ),
        migrations.RunPython(set_emehmon_unit_9000, migrations.RunPython.noop),
    ]
