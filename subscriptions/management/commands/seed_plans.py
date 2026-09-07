from django.core.management.base import BaseCommand

from subscriptions.models import DEFAULT_PLAN_LIMITS, Plan


class Command(BaseCommand):
    help = "Create or update Free/Basic/Pro subscription plans"

    def handle(self, *args, **options):
        specs = [
            (Plan.Code.FREE, "Free", "0", "0"),
            (Plan.Code.BASIC, "Basic", "299000", "2990000"),
            (Plan.Code.PRO, "Pro", "599000", "5990000"),
        ]
        for code, name, monthly, yearly in specs:
            plan, created = Plan.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "price_monthly": monthly,
                    "price_yearly": yearly,
                    "limits": DEFAULT_PLAN_LIMITS[code].copy(),
                    "is_active": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} plan: {plan.code}")
        self.stdout.write(self.style.SUCCESS("Plans ready."))
