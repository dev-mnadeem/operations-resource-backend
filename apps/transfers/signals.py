"""
Signals for transfers app automation.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.db.models.signals import post_save, pre_save
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


def _move_stock(*, branch, warehouse, inventory_item, delta):
    """Add `delta` (negative to deduct) to one location's stock, in SQL."""
    if branch is not None:
        from apps.inventory.models import BranchInventory

        BranchInventory.objects.get_or_create(branch=branch, item=inventory_item)
        BranchInventory.objects.filter(branch=branch, item=inventory_item).update(
            quantity=F("quantity") + delta
        )
    elif warehouse is not None:
        from apps.warehouse.models import WarehouseInventory

        WarehouseInventory.objects.get_or_create(
            warehouse=warehouse,
            inventory_item=inventory_item,
            defaults={"quantity": Decimal("0")},
        )
        WarehouseInventory.objects.filter(
            warehouse=warehouse, inventory_item=inventory_item
        ).update(quantity=F("quantity") + delta)


@receiver(pre_save, sender=Transfer)
def remember_previous_transfer_status(instance, **_kwargs):
    instance._previous_status = (
        Transfer.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=Transfer)
def update_inventory_on_transfer(instance, created, **_kwargs):
    """
    Move stock when a transfer becomes dispatched (out of the source) or
    received (into the destination).

    Only the status change moves stock. Saving a dispatched or received
    transfer again, e.g. to edit its notes, must not move it a second time.
    """
    if created or getattr(instance, "_previous_status", None) == instance.status:
        return

    if instance.status == Transfer.STATUS_DISPATCHED:
        with transaction.atomic():
            for item in instance.items.select_related("inventory_item"):
                qty = (
                    item.dispatched_quantity
                    if item.dispatched_quantity is not None
                    else item.quantity
                )
                _move_stock(
                    branch=instance.from_branch,
                    warehouse=instance.from_warehouse,
                    inventory_item=item.inventory_item,
                    delta=-qty,
                )
        _notify_transfer_dispatched(instance)

    elif instance.status == Transfer.STATUS_RECEIVED:
        with transaction.atomic():
            for item in instance.items.select_related("inventory_item"):
                qty = (
                    item.received_quantity
                    if item.received_quantity is not None
                    else item.quantity
                )
                _move_stock(
                    branch=instance.to_branch,
                    warehouse=instance.to_warehouse,
                    inventory_item=item.inventory_item,
                    delta=qty,
                )
