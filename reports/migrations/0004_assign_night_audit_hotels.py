from django.db import migrations


def assign_night_audit_hotels(apps, schema_editor):
    NightAuditRun = apps.get_model("reports", "NightAuditRun")
    Property = apps.get_model("properties", "Property")

    for run in NightAuditRun.objects.filter(hotel__isnull=True).iterator():
        prop = (
            Property.objects.filter(tenant_id=run.tenant_id, is_active=True)
            .order_by("id")
            .first()
        )
        if prop is None:
            run.delete()
            continue
        run.hotel_id = prop.id
        run.save(update_fields=["hotel_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_alter_nightauditrun_unique_together_and_more"),
        ("properties", "0005_property_branch_code_and_more"),
    ]

    operations = [
        migrations.RunPython(assign_night_audit_hotels, migrations.RunPython.noop),
    ]
