"""
Signals for transfers app automation.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.permissions import (
    ADMIN_GROUP,
    BRANCH_MANAGER_GROUP,
    PURCHASER_GROUP,
    WAREHOUSE_MANAGER_GROUP,
)
from apps.purchases.models import Notification

from .models import Transfer

User = get_user_model()


def _notify_transfer_dispatched(transfer):
    """Notify destination Branch Manager or Warehouse Manager when a transfer is dispatched."""

    from_loc = (
        transfer.from_branch.branch_code
        if transfer.from_branch
        else transfer.from_warehouse.name
    )
    message = f"Transfer from {from_loc} has been dispatched and is on its way to you."
    notification_kwargs = {
        "message": message,
        "type": "transfer_dispatched",
        "related_object_type": "Transfer",
        "related_object_id": transfer.id,
    }

    notify_ids = set()
    if transfer.to_branch:
        notify_ids.update(
            User.objects.filter(
                groups__name=BRANCH_MANAGER_GROUP,
                branch=transfer.to_branch,
            ).values_list("id", flat=True)
        )
        notify_ids.update(
            User.objects.filter(groups__name=PURCHASER_GROUP)
            .filter(
                Q(purchaser_branches=transfer.to_branch) | Q(branch=transfer.to_branch)
            )
            .values_list("id", flat=True)
        )
    elif transfer.to_warehouse:
        notify_ids.update(
            User.objects.filter(
                groups__name=WAREHOUSE_MANAGER_GROUP,
                warehouse=transfer.to_warehouse,
            ).values_list("id", flat=True)
        )

    notify_ids.update(
        User.objects.filter(
            Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
        ).values_list("id", flat=True)
    )

    for uid in notify_ids:
        Notification.objects.create(user_id=uid, **notification_kwargs)


@receiver(post_save, sender=Transfer)
def update_inventory_on_transfer(instance, created, **_kwargs):
    """
    Automatically update inventory when transfer is dispatched or received.
    """
    if created:
        return  # Only process status changes, not creation

    # Check if status changed to DISPATCHED
    if instance.status == Transfer.STATUS_DISPATCHED:
        # Deduct from source location
        for item in instance.items.all():
            inventory_item = item.inventory_item
            dispatched_qty = (
                item.dispatched_quantity if item.dispatched_quantity else item.quantity
            )

            # Update source inventory
            if instance.from_branch:
                # Deduct from branch inventory
                from apps.inventory.models import BranchInventory

                branch_inv = BranchInventory.objects.filter(
                    branch=instance.from_branch, item=inventory_item
                ).first()
                if branch_inv:
                    branch_inv.quantity -= dispatched_qty
                    branch_inv.save(update_fields=["quantity"])
            elif instance.from_warehouse:
                # Deduct from warehouse inventory
                from apps.warehouse.models import WarehouseInventory

                warehouse_inventory, _ = WarehouseInventory.objects.get_or_create(
                    warehouse=instance.from_warehouse,
                    inventory_item=inventory_item,
                    defaults={"quantity": Decimal("0")},
                )
                warehouse_inventory.quantity -= dispatched_qty
                warehouse_inventory.save()

    # Notify destination when dispatched
    if instance.status == Transfer.STATUS_DISPATCHED:
        _notify_transfer_dispatched(instance)

    # Check if status changed to RECEIVED
    elif instance.status == Transfer.STATUS_RECEIVED:
        # Add to destination location
        for item in instance.items.all():
            inventory_item = item.inventory_item
            received_qty = (
                item.received_quantity if item.received_quantity else item.quantity
            )

            # Update destination inventory
            if instance.to_branch:
                # Add to branch inventory
                from apps.inventory.models import BranchInventory

                branch_inv, _ = BranchInventory.objects.get_or_create(
                    branch=instance.to_branch,
                    item=inventory_item,
                )
                branch_inv.quantity += received_qty
                branch_inv.save(update_fields=["quantity"])
            elif instance.to_warehouse:
                # Add to warehouse inventory
                from apps.warehouse.models import WarehouseInventory

                warehouse_inventory, _ = WarehouseInventory.objects.get_or_create(
                    warehouse=instance.to_warehouse,
                    inventory_item=inventory_item,
                    defaults={"quantity": Decimal("0")},
                )
                warehouse_inventory.quantity += received_qty
                warehouse_inventory.save()
