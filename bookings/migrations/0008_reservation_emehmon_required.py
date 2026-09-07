# Generated manually for optional E-mehmon per reservation

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0007_reservation_nightly_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="emehmon_required",
            field=models.BooleanField(
                default=False,
                help_text="True — bu mehmondan E-mehmon olinadi; False — ixtiyoriy, olinmaydi.",
            ),
        ),
    ]
