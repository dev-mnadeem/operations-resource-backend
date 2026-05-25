from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.branch.models import Branch
from apps.inventory.models import (
    BranchInventory,
    InventoryItem,
    StockAdjustment,
    StockCycleCount,
)


@receiver(post_save, sender=Branch)
def create_branch_inventory_for_new_branch(instance, created, **_kwargs):
    """
    Whenever a new Branch is created, automatically create a BranchInventory
    record with 0 quantity for every existing InventoryItem.
    """
    if created:
        items = InventoryItem.objects.all()
        branch_inventories = [
            BranchInventory(branch=instance, item=item, quantity=0, minimum_threshold=0)
            for item in items
        ]
        BranchInventory.objects.bulk_create(branch_inventories, ignore_conflicts=True)


@receiver(post_save, sender=InventoryItem)
def create_branch_inventory_for_new_item(instance, created, **_kwargs):
    """
    Whenever a new InventoryItem is created, automatically create a BranchInventory
    record with 0 quantity for every existing Branch.
    """
    if created:
        branches = Branch.objects.all()
        branch_inventories = [
            BranchInventory(
                branch=branch, item=instance, quantity=0, minimum_threshold=0
            )
            for branch in branches
        ]
        BranchInventory.objects.bulk_create(branch_inventories, ignore_conflicts=True)


@receiver(post_save, sender=StockAdjustment)
def apply_stock_adjustment(instance, created, **_kwargs):
    """
    Apply a stock adjustment to BranchInventory or WarehouseInventory.

    INCREASE / CORRECTION → add quantity
    DECREASE              → subtract quantity
    """
    if not created:
        return

    delta = instance.quantity
    if instance.adjustment_type == StockAdjustment.ADJUST_DECREASE:
        delta = -delta

    if instance.branch_id:
        BranchInventory.objects.filter(
            branch_id=instance.branch_id,
            item=instance.inventory_item,
        ).update(quantity=models.F("quantity") + delta)

    elif instance.warehouse_id:
        from apps.warehouse.models import WarehouseInventory

        WarehouseInventory.objects.filter(
            warehouse_id=instance.warehouse_id,
            inventory_item=instance.inventory_item,
        ).update(quantity=models.F("quantity") + delta)


@receiver(post_save, sender=StockCycleCount)
def notify_on_cycle_count_variance(instance, **_kwargs):
    """
    When a StockCycleCount is completed with non-zero variance,
    notify the Branch Manager for that branch and all Admins.
    """
    if instance.status != StockCycleCount.STATUS_COMPLETED:
        return
    if not instance.variance or instance.variance == 0:
        return
    if not instance.branch_id:
        return  # warehouse cycle counts: skip for now

    from apps.permissions import ADMIN_GROUP, BRANCH_MANAGER_GROUP
    from apps.purchases.models import Notification
    from apps.users.models import User

    direction = "surplus" if instance.variance > 0 else "shortage"
    abs_variance = abs(instance.variance)
    message = (
        f"Stock variance detected for '{instance.inventory_item.name}' at branch "
        f"{instance.branch.branch_code}: {direction} of {abs_variance} "
        f"{instance.inventory_item.unit.abbreviation if instance.inventory_item.unit else 'units'}."
    )

    notify_user_ids = set(
        User.objects.filter(
            groups__name=ADMIN_GROUP,
        ).values_list("id", flat=True)
    )
    notify_user_ids.update(
        User.objects.filter(
            groups__name=BRANCH_MANAGER_GROUP,
            branch_id=instance.branch_id,
        ).values_list("id", flat=True)
    )

    Notification.objects.bulk_create(
        [
            Notification(
                user_id=uid,
                message=message,
                type="cycle_count_variance",
                related_object_type="StockCycleCount",
                related_object_id=instance.id,
            )
            for uid in notify_user_ids
        ]
    )
