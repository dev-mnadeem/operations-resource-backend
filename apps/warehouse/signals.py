"""
Signals for warehouse app automation.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Warehouse, WarehouseRequest, WarehouseTransaction


@receiver(post_save, sender=Warehouse)
def create_warehouse_inventory_for_new_warehouse(instance, created, **_kwargs):
    """
    Whenever a new Warehouse is created, automatically create a WarehouseInventory
    record with 0 quantity for every existing InventoryItem.
    """
    if not created:
        return
    from decimal import Decimal

    from apps.inventory.models import InventoryItem

    from .models import WarehouseInventory

    items = InventoryItem.objects.all()
    WarehouseInventory.objects.bulk_create(
        [
            WarehouseInventory(
                warehouse=instance,
                inventory_item=item,
                quantity=Decimal("0"),
                minimum_threshold=Decimal("0"),
            )
            for item in items
        ],
        ignore_conflicts=True,
    )


@receiver(post_save, sender=WarehouseTransaction)
def update_warehouse_inventory_on_transaction(instance, created, **_kwargs):
    """
    Automatically update WarehouseInventory quantity when a transaction is created.
    """
    if not created:
        return  # Only process new transactions

    from decimal import Decimal

    from .models import WarehouseInventory

    # Get or create WarehouseInventory record
    warehouse_inventory, _ = WarehouseInventory.objects.get_or_create(
        warehouse=instance.warehouse,
        inventory_item=instance.inventory_item,
        defaults={"quantity": Decimal("0")},
    )

    # Update quantity based on transaction type
    if instance.transaction_type == WarehouseTransaction.TRANSACTION_INWARD:
        warehouse_inventory.quantity += instance.quantity
    elif instance.transaction_type == WarehouseTransaction.TRANSACTION_OUTWARD:
        warehouse_inventory.quantity -= instance.quantity
    elif instance.transaction_type == WarehouseTransaction.TRANSACTION_ADJUSTMENT:
        # For adjustments, quantity can be positive (increase) or negative (decrease)
        warehouse_inventory.quantity += instance.quantity

    warehouse_inventory.save()


@receiver(post_save, sender=WarehouseRequest)
def notify_on_warehouse_request_status_change(instance, created, **_kwargs):
    """
    Create notifications when WarehouseRequest status changes.
    """
    from apps.purchases.models import Notification

    if created:
        # New request created - notify warehouse managers assigned to this warehouse
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.db.models import Q

        from apps.permissions import ADMIN_GROUP, WAREHOUSE_MANAGER_GROUP

        User = get_user_model()

        group = Group.objects.filter(name=WAREHOUSE_MANAGER_GROUP).first()
        if group:
            message = f"New warehouse request from branch {instance.branch.branch_code} to warehouse {instance.warehouse.name}"
            for manager in group.user_set.all():
                if manager.warehouse_id == instance.warehouse_id:
                    Notification.objects.create(
                        user=manager,
                        message=message,
                        type="warehouse_request_submitted",
                        related_object_type="WarehouseRequest",
                        related_object_id=instance.id,
                    )

        message_admin = f"New warehouse request #{instance.id} from branch {instance.branch.branch_code} to warehouse {instance.warehouse.name} created by {instance.requested_by.username}."
        admin_ids = User.objects.filter(
            Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
        ).values_list("id", flat=True)

        for uid in admin_ids:
            Notification.objects.create(
                user_id=uid,
                message=message_admin,
                type="warehouse_request_submitted",
                related_object_type="WarehouseRequest",
                related_object_id=instance.id,
            )
    else:
        # Status changed - notify the requester
        if instance.status == WarehouseRequest.STATUS_APPROVED and instance.approved_by:
            Notification.objects.create(
                user=instance.requested_by,
                message=f"Your warehouse request to {instance.warehouse.name} has been approved by {instance.approved_by.username}",
                type="warehouse_request_approved",
                related_object_type="WarehouseRequest",
                related_object_id=instance.id,
            )
        elif (
            instance.status == WarehouseRequest.STATUS_REJECTED and instance.approved_by
        ):
            Notification.objects.create(
                user=instance.requested_by,
                message=f"Your warehouse request to {instance.warehouse.name} has been rejected by {instance.approved_by.username}",
                type="warehouse_request_rejected",
                related_object_type="WarehouseRequest",
                related_object_id=instance.id,
            )
