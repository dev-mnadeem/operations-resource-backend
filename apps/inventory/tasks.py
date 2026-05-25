from celery import shared_task
from django.utils import timezone


@shared_task
def schedule_cycle_counts():
    """
    Daily task that creates StockCycleCount records (status=scheduled) based on
    each BranchInventory's tracking_frequency:

      - daily   → every run (06:00 daily)
      - weekly  → every Monday
      - monthly → 1st of each month

    Skips items that already have a scheduled count for today.
    Returns the number of cycle count records created.
    """
    from apps.inventory.models import BranchInventory, StockCycleCount

    today = timezone.localdate()

    due_frequencies = [BranchInventory.TRACKING_DAILY]
    if today.weekday() == 0:  # Monday
        due_frequencies.append(BranchInventory.TRACKING_WEEKLY)
    if today.day == 1:  # 1st of the month
        due_frequencies.append(BranchInventory.TRACKING_MONTHLY)

    branch_inventories = BranchInventory.objects.filter(
        tracking_frequency__in=due_frequencies,
    ).select_related("item", "branch")

    # Avoid duplicates if the task runs more than once
    already_scheduled = set(
        StockCycleCount.objects.filter(
            scheduled_date=today,
            status=StockCycleCount.STATUS_SCHEDULED,
            branch__isnull=False,
        ).values_list("inventory_item_id", "branch_id")
    )

    to_create = [
        StockCycleCount(
            inventory_item=bi.item,
            branch=bi.branch,
            scheduled_date=today,
            counted_quantity=0,
            variance=0,
            status=StockCycleCount.STATUS_SCHEDULED,
        )
        for bi in branch_inventories
        if (bi.item_id, bi.branch_id) not in already_scheduled
    ]

    if to_create:
        StockCycleCount.objects.bulk_create(to_create)

    return len(to_create)
