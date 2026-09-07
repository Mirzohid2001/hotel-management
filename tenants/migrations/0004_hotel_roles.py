# Generated manually for multi-role hotel RBAC

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_membershipproperty"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenantmembership",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("manager", "Menejer"),
                    ("receptionist", "Qabulxona"),
                    ("housekeeper", "Tozalash"),
                    ("accountant", "Hisobchi"),
                    ("hr", "Kadrlar"),
                ],
                default="manager",
                max_length=32,
            ),
        ),
    ]
