from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import BOM

from .models import Product


@receiver(post_save, sender=Product)
def create_product_bom(sender, instance, created, **kwargs):  # noqa: ARG001
    """Automatically create a BOM with the same name as the product if it doesn't exist."""
    if created:
        BOM.objects.get_or_create(
            product=instance,
            defaults={"name": f"BOM for {instance.name}"},
        )
