from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0006_currency_accounting"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="nightly_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Qo‘lda kelishilgan 1 kecha narxi (tarif o‘rniga).",
                max_digits=14,
                null=True,
            ),
        ),
    ]
