from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import BranchInventory
from apps.sales.models import InventoryConsumption


def get_automated_demand_suggestions(branch_id):
    """
    Calculates suggested demand quantities for all items in a branch.
    Logic:
    - Threshold-based: min_threshold - current_stock
    - Trend-based: (daily usage over last 30 days) * 14
    - Result: max(threshold, trend, 0)
    """
    # 1. Get current stock and thresholds for all items in the branch
    branch_inventories = BranchInventory.objects.filter(
        branch_id=branch_id
    ).select_related(
        "item",
    )

    # 2. Calculate trends (30-day consumption)
    last_30_days = timezone.now() - timedelta(days=30)
    consumption_data = (
        InventoryConsumption.objects.filter(
            sales_transaction__branch_id=branch_id,
            timestamp__gte=last_30_days,
        )
        .values("inventory_item_id")
        .annotate(total_consumed=Sum("quantity_consumed"))
    )

    consumption_map = {
        c["inventory_item_id"]: c["total_consumed"] for c in consumption_data
    }

    suggestions = {}
    for bi in branch_inventories:
        # Threshold gap
        threshold_gap = max(Decimal("0"), bi.minimum_threshold - bi.quantity)

        # Trend forecast (14 days based on 30-day average)
        total_consumed = consumption_map.get(bi.item_id, Decimal("0"))
        avg_daily_usage = total_consumed / Decimal("30")
        trend_requirement = avg_daily_usage * Decimal("14")

        # Final suggestion: higher of the two, rounded up to 2 decimal places
        suggested_qty = max(threshold_gap, trend_requirement)

        if suggested_qty > 0:
            suggestions[bi.item_id] = float(round(suggested_qty, 2))

    return suggestions
