from django.db.models.signals import post_save
from django.dispatch import receiver

from properties.models import Property

from .models import WidgetConfig


@receiver(post_save, sender=Property)
def ensure_property_widget(sender, instance, **kwargs):
    WidgetConfig.objects.get_or_create(
        tenant=instance.tenant,
        hotel=instance,
        defaults={"is_enabled": False},
    )
