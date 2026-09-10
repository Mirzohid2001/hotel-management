from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0006_expense_hotel"),
        ("maintenance", "0002_alter_maintenanceticket_priority_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="funding",
            field=models.CharField(
                choices=[
                    ("operating", "Joriy (Sofdan)"),
                    ("reinvestment", "Reinvestitsiya (foydadan)"),
                ],
                default="operating",
                help_text=(
                    "Joriy — mehmonxona Sofidan. Reinvestitsiya — Sofga tegmaydi, "
                    "uchreditel/foyda ulushidan ayiriladi."
                ),
                max_length=20,
                verbose_name="Moliyalashtirish",
            ),
        ),
        migrations.AddField(
            model_name="expense",
            name="maintenance_ticket",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="expenses",
                to="maintenance.maintenanceticket",
                verbose_name="Ta’mir arizasi",
            ),
        ),
    ]
