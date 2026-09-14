from django.db import migrations, models
import django.db.models.deletion


def backfill_primary_occupants(apps, schema_editor):
    Reservation = apps.get_model("bookings", "Reservation")
    Occupant = apps.get_model("bookings", "ReservationOccupant")
    existing = set(
        Occupant.objects.filter(is_primary=True).values_list("reservation_id", flat=True)
    )
    to_create = []
    for res in Reservation.objects.exclude(guest_id=None).iterator():
        if res.pk in existing:
            continue
        to_create.append(
            Occupant(
                tenant_id=res.tenant_id,
                reservation_id=res.pk,
                guest_id=res.guest_id,
                kind="adult",
                is_primary=True,
                sort_order=0,
            )
        )
        if len(to_create) >= 500:
            Occupant.objects.bulk_create(to_create)
            to_create = []
    if to_create:
        Occupant.objects.bulk_create(to_create)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0011_alter_referrercommissionpayment_currency_and_more"),
        ("guests", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservationOccupant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("adult", "Katta"), ("child", "Bola")],
                        default="adult",
                        max_length=16,
                    ),
                ),
                ("is_primary", models.BooleanField(default=False)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "guest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="occupancies",
                        to="guests.guest",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="occupants",
                        to="bookings.reservation",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookings_reservationoccupant_set",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["-is_primary", "sort_order", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="reservationoccupant",
            constraint=models.UniqueConstraint(
                fields=("reservation", "guest"),
                name="bookings_occupant_reservation_guest_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservationoccupant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_primary", True)),
                fields=("reservation",),
                name="bookings_occupant_one_primary",
            ),
        ),
        migrations.RunPython(backfill_primary_occupants, noop_reverse),
    ]
