from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Expense = apps.get_model("finance", "Expense")
    ProfitWithdrawal = apps.get_model("finance", "ProfitWithdrawal")
    Expense.objects.filter(amount_base=0).exclude(amount=0).update(
        amount_base=F("amount"), fx_rate=1
    )
    ProfitWithdrawal.objects.filter(amount_base=0).exclude(amount=0).update(
        amount_base=F("amount"), fx_rate=1
    )


class Migration(migrations.Migration):
    dependencies = [("finance", "0004_multicurrency")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
