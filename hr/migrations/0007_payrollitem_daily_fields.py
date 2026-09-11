from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hr", "0006_salaryadvance_recovered_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollitem",
            name="work_date",
            field=models.DateField(
                blank=True,
                help_text="Kunlik ish kuni. Oylik qatorda bo‘sh qoladi.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payrollitem",
            name="days_count",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Kunlik to‘lovda necha kun. Oylikda 1.",
            ),
        ),
        migrations.AlterField(
            model_name="employee",
            name="base_salary",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Oylik: oyiga. Kunlik: bir kunlik stavka.",
                max_digits=14,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="payrollitem",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="payrollitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(("work_date__isnull", True)),
                fields=("period", "employee"),
                name="hr_payrollitem_monthly_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="payrollitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(("work_date__isnull", False)),
                fields=("period", "employee", "work_date"),
                name="hr_payrollitem_daily_unique",
            ),
        ),
    ]
