import logging

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import BOM, BranchInventory
from apps.sales.models import InventoryConsumption, SalesTransaction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SalesTransaction)
def reduce_inventory_on_sale(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created:
        return

    if not instance.product_id:
        logger.warning(
            "SalesTransaction #%s has no product — skipping BOM deduction.", instance.pk
        )
        return

    bom = (
        BOM.objects.filter(product=instance.product)
        .prefetch_related("items__inventory_item")
        .first()
    )

    if not bom or not bom.items.exists():
        logger.warning(
            "No BOM configured for product '%s' (SalesTransaction #%s) — inventory deduction skipped.",
            instance.product,
            instance.pk,
        )
        return

    with transaction.atomic():
        for bom_item in bom.items.all():
            # BOM qty x factor = qty in the inventory item's base unit
            base_qty = (
                bom_item.quantity * bom_item.conversion_factor * instance.quantity_sold
            )
            BranchInventory.objects.get_or_create(
                branch=instance.branch, item=bom_item.inventory_item
            )
            # Imports can create sales concurrently; update in SQL, not Python.
            BranchInventory.objects.filter(
                branch=instance.branch, item=bom_item.inventory_item
            ).update(quantity=F("quantity") - base_qty)

            InventoryConsumption.objects.create(
                inventory_item=bom_item.inventory_item,
                sales_transaction=instance,
                quantity_consumed=base_qty,
            )
