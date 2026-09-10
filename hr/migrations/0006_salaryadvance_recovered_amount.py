from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hr", "0005_backfill_amount_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="salaryadvance",
            name="recovered_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="Oylikdan ushlangan qism (qisman qoplash).",
                max_digits=14,
            ),
        ),
    ]
