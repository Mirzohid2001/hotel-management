from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    for name in ("SalaryPayment", "SalaryAdvance"):
        Model = apps.get_model("hr", name)
        Model.objects.filter(amount_base=0).exclude(amount=0).update(
            amount_base=F("amount"), fx_rate=1
        )


class Migration(migrations.Migration):
    dependencies = [("hr", "0004_multicurrency")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
