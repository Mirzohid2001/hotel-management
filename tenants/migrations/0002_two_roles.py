from django.db import migrations, models


def forward_roles(apps, schema_editor):
    TenantMembership = apps.get_model("tenants", "TenantMembership")
    for m in TenantMembership.objects.all():
        if m.role == "owner":
            m.role = "admin"
        elif m.role in {"receptionist", "housekeeper", "accountant", "hr_manager"}:
            m.role = "manager"
        m.save(update_fields=["role"])


def backward_roles(apps, schema_editor):
    TenantMembership = apps.get_model("tenants", "TenantMembership")
    for m in TenantMembership.objects.all():
        if m.role == "admin":
            m.role = "owner"
        m.save(update_fields=["role"])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward_roles, backward_roles),
        migrations.AlterField(
            model_name="tenantmembership",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("manager", "Ish boshqaruvchi"),
                ],
                default="manager",
                max_length=32,
            ),
        ),
    ]
