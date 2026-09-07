from django.db import migrations
from django.utils.text import slugify


def populate_branch_codes(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    for prop in Property.objects.all():
        if prop.branch_code:
            continue
        base = slugify(prop.name) or "filial"
        code = base[:32]
        n = 1
        while (
            Property.objects.filter(tenant_id=prop.tenant_id, branch_code=code)
            .exclude(pk=prop.pk)
            .exists()
        ):
            n += 1
            code = f"{base[:28]}-{n}"
        prop.branch_code = code
        prop.save(update_fields=["branch_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0005_property_branch_code_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_branch_codes, migrations.RunPython.noop),
    ]
