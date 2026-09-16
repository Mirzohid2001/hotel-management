from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_alter_exchangerate_base_currency_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Bo‘sh qolsa yon panelda Rivoj logosi chiqadi.",
                upload_to="tenant-logos/",
                verbose_name="Logotip",
            ),
        ),
    ]
