"""
Signals for purchases app automation.
"""

from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.demands.models import Demand

from .models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder
from .notification_channels import send_email_notifications


@receiver(pre_save, sender=GoodsReceiptItem)
def calculate_receipt_variance(instance, **_kwargs):
    """
    Automatically calculate variance when GoodsReceiptItem is saved.
    Variance = received_quantity - expected_quantity
    """
    if (
        instance.received_quantity is not None
        and instance.expected_quantity is not None
    ):
        instance.variance = instance.received_quantity - instance.expected_quantity


@receiver(post_save, sender=GoodsReceiptItem)
@receiver(post_delete, sender=GoodsReceiptItem)
def update_receipt_total_quantity(instance, **_kwargs):
    """
    Update GoodsReceipt total_received_quantity when items are modified.
    """
    receipt = instance.goods_receipt
    total = sum(item.received_quantity or 0 for item in receipt.items.all())
    receipt.total_received_quantity = total
    receipt.save(update_fields=["total_received_quantity"])


@receiver(pre_save, sender=GoodsReceiptItem)
def capture_old_received_qty(instance, **_kwargs):
    """Capture old received quantity to calculate delta."""
    if instance.pk:
        old_instance = GoodsReceiptItem.objects.get(pk=instance.pk)
        instance._old_received_quantity = old_instance.received_quantity
    else:
        instance._old_received_quantity = Decimal("0")


@receiver(post_save, sender=GoodsReceiptItem)
def update_inventory_on_receipt_item_save(instance, **_kwargs):
    """Update BranchInventory when GoodsReceiptItem is saved."""
    old_qty = getattr(instance, "_old_received_quantity", Decimal("0"))
    new_qty = instance.received_quantity or Decimal("0")
    delta = new_qty - old_qty

    if delta != Decimal("0"):
        from apps.inventory.models import BranchInventory

        branch = instance.goods_receipt.demand.branch
        branch_inv, _ = BranchInventory.objects.get_or_create(
            branch=branch,
            item=instance.inventory_item,
        )
        branch_inv.quantity += delta
        branch_inv.save(update_fields=["quantity"])


@receiver(post_save, sender=GoodsReceipt)
def notify_on_receipt_discrepancy(instance, **_kwargs):
    """
    When a GoodsReceipt is marked completed or partial and any item has non-zero variance,
    notify all Purchasers and Admins of the discrepancy.
    """
    if instance.status not in (
        GoodsReceipt.STATUS_COMPLETED,
        GoodsReceipt.STATUS_PARTIAL,
    ):
        return

    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from apps.permissions import ADMIN_GROUP, PURCHASER_GROUP

    from .models import Notification

    User = get_user_model()

    discrepant_items = instance.items.exclude(variance=0)
    if not discrepant_items.exists():
        return

    lines = []
    for item in discrepant_items.select_related("inventory_item"):
        direction = "surplus" if item.variance > 0 else "shortage"
        lines.append(
            f"{item.inventory_item.name}: {direction} of {abs(item.variance)}"
            + (f" ({item.condition})" if item.condition else "")
        )

    message = (
        f"Discrepancy on GoodsReceipt #{instance.pk} for demand "
        f"#{instance.demand_id} ({instance.demand.branch.branch_code}): "
        + "; ".join(lines)
    )

    notify_ids = set(
        User.objects.filter(
            Q(is_superuser=True)
            | Q(groups__name=ADMIN_GROUP)
            | Q(groups__name=PURCHASER_GROUP)
        ).values_list("id", flat=True)
    )
    Notification.objects.bulk_create(
        [
            Notification(
                user_id=uid,
                message=message,
                type="receipt_discrepancy",
                related_object_type="GoodsReceipt",
                related_object_id=instance.id,
            )
            for uid in notify_ids
        ],
        ignore_conflicts=True,
    )


@receiver(post_save, sender=Demand)
def notify_on_demand_status_change(instance, created, **_kwargs):
    """
    Create notifications when Demand is created or status changes.
    - On create: notify admin/superadmin and purchasers (for this branch or global).
    - On status change: notify submitter when approved/rejected.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from apps.permissions import (
        ADMIN_GROUP,
        BRANCH_MANAGER_GROUP,
        PURCHASER_GROUP,
        WAREHOUSE_MANAGER_GROUP,
    )

    from .models import Notification

    User = get_user_model()

    status_changed = (
        created or getattr(instance, "_old_status", None) != instance.status
    )
    if not status_changed:
        return

    if created:
        message = (
            f"New demand submitted by {instance.submitted_by.username} "
            f"for branch {instance.branch.name} ({instance.branch.branch_code})."
        )
        notification_kwargs = {
            "message": message,
            "type": "demand_submitted",
            "related_object_type": "Demand",
            "related_object_id": instance.id,
        }
        submitter_id = instance.submitted_by_id

        # Collect users to notify (one notification per user; no duplicates)
        user_ids = set()

        # Purchasers assigned to this branch (supports multi-branch purchasers)
        user_ids.update(
            User.objects.filter(
                Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
            ).values_list("id", flat=True)
        )

        user_ids.update(
            User.objects.filter(groups__name=PURCHASER_GROUP)
            .filter(Q(purchaser_branches=instance.branch) | Q(branch=instance.branch))
            .exclude(Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP))
            .distinct()
            .values_list("id", flat=True)
        )

        for user_id in user_ids:
            if user_id != submitter_id:
                Notification.objects.create(user_id=user_id, **notification_kwargs)

        if instance.submitted_by.groups.filter(name=BRANCH_MANAGER_GROUP).exists():
            purchaser_users = list(
                User.objects.filter(groups__name=PURCHASER_GROUP)
                .exclude(Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP))
                .exclude(id=submitter_id)
                .distinct()
            )
            email_subject = f"New Demand Submitted (Demand #{instance.id})"
            send_email_notifications(
                purchaser_users,
                email_subject,
                message,
            )
    else:
        # Status changed - notify the submitter
        if instance.status == Demand.STATUS_APPROVED and instance.approved_by:
            Notification.objects.create(
                user=instance.submitted_by,
                message=f"Your demand for branch {instance.branch.branch_code} has been approved by {instance.approved_by.username}",
                type="demand_approved",
                related_object_type="Demand",
                related_object_id=instance.id,
            )
            # Notify admin, branch manager, and warehouse manager on approval
            approve_msg = (
                f"Demand #{instance.id} for branch {instance.branch.branch_code} "
                f"has been approved by {instance.approved_by.username}."
            )
            approve_kwargs = {
                "message": approve_msg,
                "type": "demand_approved",
                "related_object_type": "Demand",
                "related_object_id": instance.id,
            }
            approve_notify_ids = set()
            approve_notify_ids.update(
                User.objects.filter(
                    Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
                ).values_list("id", flat=True)
            )
            approve_notify_ids.update(
                User.objects.filter(
                    groups__name=BRANCH_MANAGER_GROUP,
                    branch=instance.branch,
                ).values_list("id", flat=True)
            )
            approve_notify_ids.update(
                User.objects.filter(groups__name=WAREHOUSE_MANAGER_GROUP)
                .exclude(Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP))
                .values_list("id", flat=True)
            )
            for uid in approve_notify_ids:
                if uid != instance.submitted_by_id:
                    Notification.objects.create(user_id=uid, **approve_kwargs)
            admin_users_for_email = list(
                User.objects.filter(Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP))
                .exclude(id=instance.submitted_by_id)
                .distinct()
            )
            send_email_notifications(
                admin_users_for_email,
                f"Demand Approved (Demand #{instance.id})",
                approve_msg,
            )
        elif instance.status == Demand.STATUS_REJECTED and instance.approved_by:
            reject_msg = (
                f"Your demand for branch {instance.branch.branch_code} "
                f"has been rejected by {instance.approved_by.username}"
            )
            Notification.objects.create(
                user=instance.submitted_by,
                message=reject_msg,
                type="demand_rejected",
                related_object_type="Demand",
                related_object_id=instance.id,
            )
            # Notify branch manager, admin, and superuser when purchaser rejects
            notify_msg = (
                f"Demand #{instance.id} for branch {instance.branch.branch_code} "
                f"has been rejected by {instance.approved_by.username}."
            )
            if instance.rejection_reason:
                notify_msg += f" Reason: {instance.rejection_reason}"
            notify_kwargs = {
                "message": notify_msg,
                "type": "demand_rejected",
                "related_object_type": "Demand",
                "related_object_id": instance.id,
            }
            reject_notify_ids = set()
            reject_notify_ids.update(
                User.objects.filter(
                    Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
                ).values_list("id", flat=True)
            )
            reject_notify_ids.update(
                User.objects.filter(
                    groups__name=BRANCH_MANAGER_GROUP,
                    branch=instance.branch,
                ).values_list("id", flat=True)
            )
            for uid in reject_notify_ids:
                if uid != instance.submitted_by_id:
                    Notification.objects.create(user_id=uid, **notify_kwargs)
            admin_users_for_email = list(
                User.objects.filter(Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP))
                .exclude(id=instance.submitted_by_id)
                .distinct()
            )
            send_email_notifications(
                admin_users_for_email,
                f"Demand Rejected (Demand #{instance.id})",
                notify_msg,
            )
        elif instance.status == Demand.STATUS_COMPLETED:
            complete_msg = (
                f"Demand #{instance.id} for branch {instance.branch.branch_code} "
                "has been marked as completed."
            )
            complete_kwargs = {
                "message": complete_msg,
                "type": "demand_completed",
                "related_object_type": "Demand",
                "related_object_id": instance.id,
            }
            complete_notify_ids = set(
                User.objects.filter(
                    Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
                ).values_list("id", flat=True)
            )
            for uid in complete_notify_ids:
                Notification.objects.create(user_id=uid, **complete_kwargs)


@receiver(pre_save, sender=Demand)
def capture_old_demand_status(instance, **_kwargs):
    """Capture previous demand status to avoid duplicate notifications."""
    if not instance.pk:
        instance._old_status = None
        return

    instance._old_status = (
        Demand.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=PurchaseOrder)
def notify_admin_on_purchase_order_creation(instance, created, **_kwargs):
    if not created:
        return

    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from apps.permissions import ADMIN_GROUP

    from .models import Notification

    User = get_user_model()

    message = (
        f"New Purchase Order #{instance.id} created by {instance.created_by.username}."
    )

    admin_ids = User.objects.filter(
        Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
    ).values_list("id", flat=True)

    for uid in admin_ids:
        Notification.objects.create(
            user_id=uid,
            message=message,
            type="purchase_order_created",
            related_object_type="PurchaseOrder",
            related_object_id=instance.id,
        )


@receiver(post_save, sender=GoodsReceipt)
def notify_admin_on_goods_receipt_creation(instance, created, **_kwargs):
    if not created:
        return

    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from apps.permissions import ADMIN_GROUP

    from .models import Notification

    User = get_user_model()

    message = f"New Goods Receipt #{instance.id} created for demand #{instance.demand_id} by {instance.receiver.username}."

    admin_ids = User.objects.filter(
        Q(is_superuser=True) | Q(groups__name=ADMIN_GROUP)
    ).values_list("id", flat=True)

    for uid in admin_ids:
        Notification.objects.create(
            user_id=uid,
            message=message,
            type="goods_receipt_created",
            related_object_type="GoodsReceipt",
            related_object_id=instance.id,
        )
