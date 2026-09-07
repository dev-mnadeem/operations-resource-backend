"""
Replenishment analysis: when to reorder, and how much.

Every inventory row in this system carries a `minimum_threshold` — the level
that triggers a restock alert. It is a number a person typed, it defaults to
zero, and in the seeded database it is zero for all 375 items. A threshold of
zero means the alert fires when the shelf is already empty, which is the same
as having no alert.

The data needed to compute a defensible threshold is already here: every sale
records what was consumed and when. This module derives, per item and location:

    average daily demand      from actual consumption history
    demand variability        the standard deviation of that daily series
    lead-time demand          what will be sold while a replacement order is
                              in transit
    safety stock              cover for the variability, sized to a chosen
                              service level
    reorder point             lead-time demand + safety stock
    days of cover             how long current stock lasts at current demand

and compares the computed reorder point against the threshold that is actually
configured, so a buyer can see which of their settings are wrong and by how
much.

**This is statistics, not a language model, and that is deliberate.** The
question "how much stock covers 95% of the demand that arrives during a
five-day lead time" has a correct answer derivable from the history. Asking a
model to guess it would be less accurate, more expensive, and impossible to
audit — and a wrong answer here means either a stockout or dead capital on a
shelf. The right tool for a quantity with a closed form is the closed form.

Demand history is read through `SalesTransaction.occurred_at`, never through
`InventoryConsumption.timestamp`: that column is `auto_now_add`, so it records
when the row was written rather than when the stock was consumed. In the seeded
database every consumption carries the same instant, five months after the
sales it describes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.sales.models import InventoryConsumption

#: One-sided normal quantiles, for the service levels a buyer actually picks.
#: Tabulated rather than pulled from scipy: five constants do not justify a
#: numerical stack, and these are auditable by anyone with a z-table.
Z_SCORES = {
    0.50: 0.0000,
    0.80: 0.8416,
    0.90: 1.2816,
    0.95: 1.6449,
    0.97: 1.8808,
    0.99: 2.3263,
}

DEFAULT_SERVICE_LEVEL = 0.95
DEFAULT_LEAD_TIME_DAYS = 5
DEFAULT_HISTORY_DAYS = 90

#: Below this many observed days of demand, the variability estimate is not
#: worth reporting as a number. Saying "not enough history" is more useful than
#: a safety stock computed from three data points.
MIN_DAYS_WITH_DEMAND = 5


def z_for(service_level: float) -> float:
    """Nearest tabulated z-score for a service level."""
    return Z_SCORES[min(Z_SCORES, key=lambda s: abs(s - service_level))]


@dataclass
class DemandProfile:
    """What the history says about one item at one location."""

    item_id: int
    item_name: str
    # Branch's primary key is `branch_code`, a CharField — not an integer.
    branch_id: str | int | None
    branch_name: str

    days_observed: int
    days_with_demand: int
    total_consumed: float
    mean_daily_demand: float
    stdev_daily_demand: float

    on_hand: float
    configured_threshold: float

    lead_time_days: int
    service_level: float

    daily_series: list[float] = field(default_factory=list, repr=False)

    # ---- derived quantities -------------------------------------------

    @property
    def has_enough_history(self) -> bool:
        return self.days_with_demand >= MIN_DAYS_WITH_DEMAND

    @property
    def lead_time_demand(self) -> float:
        """Expected consumption while a replacement order is in transit."""
        return self.mean_daily_demand * self.lead_time_days

    @property
    def safety_stock(self) -> float:
        """
        Cover for variability over the lead time.

        z * σ_daily * √L — the standard formula. The square root is the part
        people get wrong: demand over L days has L times the variance, not L
        times the standard deviation.
        """
        if not self.has_enough_history:
            return 0.0
        return z_for(self.service_level) * self.stdev_daily_demand * (self.lead_time_days ** 0.5)

    @property
    def reorder_point(self) -> float:
        """Stock level at which a replacement order should be placed."""
        return self.lead_time_demand + self.safety_stock

    @property
    def days_of_cover(self) -> float | None:
        """How long current stock lasts. None when nothing is moving."""
        if self.mean_daily_demand <= 0:
            return None
        return self.on_hand / self.mean_daily_demand

    @property
    def projected_stockout(self) -> date | None:
        cover = self.days_of_cover
        if cover is None:
            return None
        return timezone.now().date() + timedelta(days=int(cover))

    @property
    def below_reorder_point(self) -> bool:
        return self.on_hand < self.reorder_point

    @property
    def suggested_order_quantity(self) -> float:
        """
        Enough to reach the reorder point plus one lead time of demand.

        Not an economic order quantity: EOQ needs an ordering cost and a
        holding cost, and this system records neither. Inventing them to make
        the formula fit would produce a number that looks rigorous and means
        nothing.
        """
        if not self.below_reorder_point:
            return 0.0
        target = self.reorder_point + self.lead_time_demand
        return max(0.0, target - self.on_hand)

    @property
    def threshold_error(self) -> float:
        """How far the configured threshold is from the computed one."""
        return self.reorder_point - self.configured_threshold

    @property
    def risk(self) -> str:
        """A rank a person can sort by, not a probability."""
        if not self.has_enough_history:
            return "unknown"
        cover = self.days_of_cover
        if cover is None:
            return "idle"
        if cover <= self.lead_time_days:
            # Stock runs out before a replacement can arrive.
            return "critical"
        if self.below_reorder_point:
            return "reorder"
        if cover <= self.lead_time_days * 2:
            return "watch"
        return "ok"

    def as_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "item": self.item_name,
            "branch": self.branch_name,
            "risk": self.risk,
            "on_hand": round(self.on_hand, 2),
            "mean_daily_demand": round(self.mean_daily_demand, 3),
            "stdev_daily_demand": round(self.stdev_daily_demand, 3),
            "days_of_cover": (
                round(self.days_of_cover, 1) if self.days_of_cover is not None else None
            ),
            "projected_stockout": (
                self.projected_stockout.isoformat() if self.projected_stockout else None
            ),
            "lead_time_demand": round(self.lead_time_demand, 2),
            "safety_stock": round(self.safety_stock, 2),
            "reorder_point": round(self.reorder_point, 2),
            "configured_threshold": round(self.configured_threshold, 2),
            "threshold_error": round(self.threshold_error, 2),
            "suggested_order_quantity": round(self.suggested_order_quantity, 2),
            "days_observed": self.days_observed,
            "days_with_demand": self.days_with_demand,
            "enough_history": self.has_enough_history,
        }


def daily_demand_series(
    item_id: int,
    # Branch's primary key is `branch_code`, a CharField — not an integer.
    branch_id: str | int | None,
    since: date,
    until: date,
) -> dict[date, float]:
    """
    Consumption per day for one item, keyed by the date of the *sale*.

    Days with no consumption are included as zero. Leaving them out would
    inflate both the mean and the variance: an item sold on 3 of 90 days would
    otherwise look like steady daily demand.
    """
    rows = InventoryConsumption.objects.filter(
        inventory_item_id=item_id,
        sales_transaction__occurred_at__date__gte=since,
        sales_transaction__occurred_at__date__lte=until,
    )
    if branch_id is not None:
        rows = rows.filter(sales_transaction__branch_id=branch_id)

    grouped = (
        rows.values("sales_transaction__occurred_at__date")
        .annotate(total=Sum("quantity_consumed"))
        .order_by()
    )
    observed = {
        row["sales_transaction__occurred_at__date"]: float(row["total"] or 0)
        for row in grouped
    }

    series: dict[date, float] = {}
    day = since
    while day <= until:
        series[day] = observed.get(day, 0.0)
        day += timedelta(days=1)
    return series


def profile_for(
    branch_inventory,
    *,
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
    service_level: float = DEFAULT_SERVICE_LEVEL,
    history_days: int = DEFAULT_HISTORY_DAYS,
    until: date | None = None,
) -> DemandProfile:
    """Build a DemandProfile from one BranchInventory row."""
    until = until or timezone.now().date()
    since = until - timedelta(days=history_days - 1)

    item = branch_inventory.item
    branch = branch_inventory.branch

    # `.pk` rather than `.id`: Branch is keyed on branch_code.
    series = daily_demand_series(item.pk, branch.pk if branch else None, since, until)
    values = list(series.values())
    non_zero = [v for v in values if v > 0]

    mean = statistics.fmean(values) if values else 0.0
    # Population stdev over the full window, zeros included: the variability
    # that matters is day-to-day, and a day with no sales is a real observation.
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0

    return DemandProfile(
        item_id=item.pk,
        item_name=item.name,
        branch_id=branch.pk if branch else None,
        branch_name=str(branch) if branch else "—",
        days_observed=len(values),
        days_with_demand=len(non_zero),
        total_consumed=sum(values),
        mean_daily_demand=mean,
        stdev_daily_demand=stdev,
        on_hand=float(branch_inventory.quantity or Decimal("0")),
        configured_threshold=float(branch_inventory.minimum_threshold or Decimal("0")),
        lead_time_days=lead_time_days,
        service_level=service_level,
        daily_series=values,
    )


#: Worst first. "unknown" sits below the actionable states — an item with no
#: history is a data gap, not an emergency, and putting it at the top of the
#: list would bury the items that are genuinely about to run out.
RISK_ORDER = {"critical": 0, "reorder": 1, "watch": 2, "ok": 3, "idle": 4, "unknown": 5}


def rank_inventory(
    queryset,
    *,
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
    service_level: float = DEFAULT_SERVICE_LEVEL,
    history_days: int = DEFAULT_HISTORY_DAYS,
    limit: int | None = None,
) -> list[DemandProfile]:
    """Profile every row in `queryset`, worst risk first."""
    profiles = [
        profile_for(
            row,
            lead_time_days=lead_time_days,
            service_level=service_level,
            history_days=history_days,
        )
        for row in queryset.select_related("item", "branch")
    ]
    profiles.sort(
        key=lambda p: (
            RISK_ORDER.get(p.risk, 9),
            p.days_of_cover if p.days_of_cover is not None else float("inf"),
        )
    )
    return profiles[:limit] if limit else profiles
