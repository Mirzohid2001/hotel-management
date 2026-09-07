# Generated manually for multi-filial widget refactor

import secrets

import django.db.models.deletion
from django.db import migrations, models


def migrate_widget_to_per_property(apps, schema_editor):
    WidgetConfig = apps.get_model("widget", "WidgetConfig")
    Property = apps.get_model("properties", "Property")

    for config in WidgetConfig.objects.all():
        tenant_id = config.tenant_id
        hotel_id = getattr(config, "hotel_id", None)
        if hotel_id:
            if Property.objects.filter(pk=hotel_id, tenant_id=tenant_id).exists():
                continue
        prop = Property.objects.filter(tenant_id=tenant_id, is_active=True).order_by("id").first()
        if prop is None:
            config.delete()
            continue
        config.hotel_id = prop.id
        config.save(update_fields=["hotel_id"])

    seen_hotels = set()
    for config in WidgetConfig.objects.order_by("id"):
        if config.hotel_id in seen_hotels:
            config.delete()
        else:
            seen_hotels.add(config.hotel_id)

    existing_hotels = set(WidgetConfig.objects.values_list("hotel_id", flat=True))
    for prop in Property.objects.filter(is_active=True).iterator():
        if prop.id in existing_hotels:
            continue
        WidgetConfig.objects.create(
            tenant_id=prop.tenant_id,
            hotel_id=prop.id,
            is_enabled=False,
            public_key=secrets.token_urlsafe(24),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("widget", "0001_initial"),
        ("properties", "0005_property_branch_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="widgetconfig",
            name="tenant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="widget_configs",
                to="tenants.tenant",
            ),
        ),
        migrations.RunPython(migrate_widget_to_per_property, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="widgetconfig",
            name="hotel",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="widget_config",
                to="properties.property",
                verbose_name="Filial",
            ),
        ),
    ]
