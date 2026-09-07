"""
Generate sales and consumption history so demand analysis has something to read.

`setup_dev` seeds 30 sales transactions spread over five months — roughly one
sale every five days across 375 items. Nothing can be inferred about daily
demand from that, so the replenishment figures would be arithmetic on noise.

This creates a realistic pattern for a subset of items: a per-item base rate,
weekday seasonality (restaurants are busier at the weekend), occasional spikes,
and Poisson-distributed counts. Seeded, so the numbers in the README are
reproducible.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.branch.models import Branch
from apps.inventory.models import BranchInventory, InventoryItem
from apps.products.models import Product
from apps.sales.models import InventoryConsumption, SalesTransaction

# Weekend trade is heavier; Monday is the quiet day.
WEEKDAY_MULTIPLIER = {0: 0.7, 1: 0.8, 2: 0.9, 3: 1.0, 4: 1.4, 5: 1.6, 6: 1.2}


class Command(BaseCommand):
    help = "Generate realistic consumption history for replenishment analysis."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=120)
        parser.add_argument("--items", type=int, default=40,
                            help="How many items get an active demand pattern")
        parser.add_argument("--seed", type=int, default=11)

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        days = options["days"]
        today = timezone.now().date()
        start = today - timedelta(days=days - 1)

        branch = Branch.objects.first()
        if branch is None:
            self.stderr.write("No branch found — run `manage.py setup_dev` first.")
            return

        product = Product.objects.first()
        items = list(InventoryItem.objects.order_by("id")[: options["items"]])
        if not items:
            self.stderr.write("No inventory items found.")
            return

        # Re-runnable: clear the window this command owns before regenerating.
        # SalesTransaction has no free-text field to tag rows with, so the date
        # range is the marker.
        SalesTransaction.objects.filter(
            occurred_at__date__gte=start, occurred_at__date__lte=today
        ).delete()

        profiles = {
            item.id: {
                "base": rng.uniform(0.5, 12.0),
                "spike_chance": rng.uniform(0.01, 0.05),
            }
            for item in items
        }

        pending_sales: list[SalesTransaction] = []
        pending_items: list[InventoryItem] = []

        for offset in range(days):
            day = start + timedelta(days=offset)
            occurred = timezone.make_aware(
                timezone.datetime.combine(day, timezone.datetime.min.time())
            ) + timedelta(hours=rng.randint(9, 21))
            weekday_factor = WEEKDAY_MULTIPLIER[day.weekday()]

            for item in items:
                profile = profiles[item.id]
                expected = profile["base"] * weekday_factor
                if rng.random() < profile["spike_chance"]:
                    expected *= rng.uniform(2.5, 4.0)

                quantity = self._poisson(rng, expected)
                if quantity <= 0:
                    continue

                pending_sales.append(
                    SalesTransaction(
                        branch=branch,
                        product=product,
                        quantity_sold=quantity,
                        unit_price=Decimal("1.00"),
                        total_amount=Decimal(quantity),
                        occurred_at=occurred,
                    )
                )
                pending_items.append(item)

        # bulk_create does not send post_save, which keeps the inventory
        # deduction signal from firing thousands of times and re-deriving stock
        # levels this command sets explicitly below.
        SalesTransaction.objects.bulk_create(pending_sales, batch_size=500)
        sales_made = len(pending_sales)

        consumptions = [
            InventoryConsumption(
                inventory_item=item,
                sales_transaction=sale,
                quantity_consumed=Decimal(sale.quantity_sold),
            )
            for sale, item in zip(pending_sales, pending_items)
        ]
        InventoryConsumption.objects.bulk_create(consumptions, batch_size=500)

        # Give the tracked items a plausible amount of stock on hand, so the
        # risk ranking has a spread rather than every item reading "critical".
        for item in items:
            row = BranchInventory.objects.filter(item=item, branch=branch).first()
            if row is None:
                continue
            base = profiles[item.id]["base"]
            # Between 1 and 30 days of cover, so some items are genuinely at risk.
            row.quantity = Decimal(str(round(base * rng.uniform(1, 30), 2)))
            row.save(update_fields=["quantity"])

        self.stdout.write(self.style.SUCCESS(
            f"  {sales_made:,} sales and {len(consumptions):,} consumptions "
            f"across {days} days for {len(items)} items "
            f"({start} → {today})"
        ))

    @staticmethod
    def _poisson(rng: random.Random, lam: float) -> int:
        """Knuth's sampler — avoids a numpy dependency for one distribution."""
        if lam <= 0:
            return 0
        import math

        limit = math.exp(-lam)
        k, p = 0, 1.0
        while True:
            p *= rng.random()
            if p <= limit:
                return k
            k += 1
            if k > 1000:
                return k
