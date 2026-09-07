"""
Tests for replenishment analysis.

Most of these construct a DemandProfile directly rather than going through the
database. The arithmetic — safety stock, reorder point, days of cover — is the
part that decides whether a buyer over-orders or runs out, and it should be
checkable without fixtures. The database is exercised separately, where the
thing being tested is the query rather than the formula.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.branch.models import Branch
from apps.inventory.models import (
    BranchInventory,
    InventoryItem,
    UnitOfMeasure,
)
from apps.products.models import Product, ProductCategory
from apps.replenishment.service import (
    DemandProfile,
    daily_demand_series,
    profile_for,
    rank_inventory,
    z_for,
)
from apps.sales.models import InventoryConsumption, SalesTransaction


def profile(**overrides) -> DemandProfile:
    """A profile with sane defaults; override only what a test is about."""
    defaults = dict(
        item_id=1,
        item_name="Beef Mince",
        branch_id="BR001",
        branch_name="Raya",
        days_observed=90,
        days_with_demand=80,
        total_consumed=900.0,
        mean_daily_demand=10.0,
        stdev_daily_demand=4.0,
        on_hand=50.0,
        configured_threshold=0.0,
        lead_time_days=5,
        service_level=0.95,
    )
    defaults.update(overrides)
    return DemandProfile(**defaults)


class ServiceLevelTests(TestCase):
    def test_z_scores_increase_with_service_level(self):
        self.assertLess(z_for(0.80), z_for(0.95))
        self.assertLess(z_for(0.95), z_for(0.99))

    def test_a_service_level_snaps_to_the_nearest_tabulated_value(self):
        self.assertEqual(z_for(0.949), z_for(0.95))

    def test_a_fifty_percent_service_level_carries_no_safety_stock(self):
        # z = 0: cover the mean and nothing more.
        self.assertEqual(profile(service_level=0.50).safety_stock, 0.0)


class ReorderMathTests(TestCase):
    def test_lead_time_demand_is_mean_times_lead_time(self):
        self.assertEqual(profile(mean_daily_demand=10, lead_time_days=5).lead_time_demand, 50)

    def test_safety_stock_scales_with_the_square_root_of_lead_time(self):
        """
        The part that is most often wrong. Demand over L days has L times the
        variance, so the standard deviation grows with √L — not with L.
        """
        short = profile(lead_time_days=4).safety_stock
        long = profile(lead_time_days=16).safety_stock
        # Four times the lead time, twice the safety stock.
        self.assertAlmostEqual(long / short, 2.0, places=6)

    def test_reorder_point_is_lead_time_demand_plus_safety_stock(self):
        p = profile()
        self.assertAlmostEqual(p.reorder_point, p.lead_time_demand + p.safety_stock)

    def test_steady_demand_needs_less_safety_stock_than_erratic_demand(self):
        steady = profile(stdev_daily_demand=1.0)
        erratic = profile(stdev_daily_demand=9.0)
        self.assertLess(steady.safety_stock, erratic.safety_stock)

    def test_days_of_cover_is_stock_over_demand(self):
        self.assertAlmostEqual(profile(on_hand=50, mean_daily_demand=10).days_of_cover, 5.0)

    def test_days_of_cover_is_none_when_nothing_is_moving(self):
        # Not infinity and not zero: dividing by no demand has no answer, and
        # reporting 0 would rank a dead item as the most urgent on the screen.
        self.assertIsNone(profile(mean_daily_demand=0.0).days_of_cover)

    def test_projected_stockout_is_cover_days_from_today(self):
        p = profile(on_hand=30, mean_daily_demand=10)
        self.assertEqual(p.projected_stockout, timezone.now().date() + timedelta(days=3))


class OrderQuantityTests(TestCase):
    def test_nothing_is_suggested_above_the_reorder_point(self):
        self.assertEqual(profile(on_hand=10_000).suggested_order_quantity, 0.0)

    def test_an_order_lifts_stock_past_the_reorder_point(self):
        p = profile(on_hand=5.0)
        self.assertGreater(p.suggested_order_quantity, 0)
        self.assertGreater(p.on_hand + p.suggested_order_quantity, p.reorder_point)

    def test_the_order_covers_one_further_lead_time(self):
        # Ordering exactly up to the reorder point means reordering again the
        # same day.
        p = profile(on_hand=0.0)
        self.assertAlmostEqual(
            p.suggested_order_quantity, p.reorder_point + p.lead_time_demand
        )


class RiskTests(TestCase):
    def test_stock_that_runs_out_inside_the_lead_time_is_critical(self):
        self.assertEqual(profile(on_hand=20, mean_daily_demand=10).risk, "critical")

    def test_stock_below_the_reorder_point_is_a_reorder(self):
        p = profile(on_hand=60, mean_daily_demand=10, stdev_daily_demand=4)
        self.assertLess(p.on_hand, p.reorder_point)
        self.assertGreater(p.days_of_cover, p.lead_time_days)
        self.assertEqual(p.risk, "reorder")

    def test_ample_stock_is_ok(self):
        self.assertEqual(profile(on_hand=1000, mean_daily_demand=10).risk, "ok")

    def test_an_item_with_no_demand_is_idle_not_critical(self):
        self.assertEqual(profile(mean_daily_demand=0.0, on_hand=0.0).risk, "idle")

    def test_too_little_history_is_reported_as_unknown(self):
        # Two days of sales cannot support a variability estimate, and saying
        # so is more useful than a safety stock derived from two points.
        p = profile(days_with_demand=2)
        self.assertFalse(p.has_enough_history)
        self.assertEqual(p.risk, "unknown")
        self.assertEqual(p.safety_stock, 0.0)

    def test_threshold_error_shows_how_wrong_the_configured_value_is(self):
        p = profile(configured_threshold=0.0)
        self.assertAlmostEqual(p.threshold_error, p.reorder_point)


class DemandHistoryTests(TestCase):
    """The database side: that demand is read from the right column."""

    def setUp(self):
        self.branch = Branch.objects.create(branch_code="BR001", name="Raya", address="x")
        self.unit = UnitOfMeasure.objects.create(name="Kilogram", abbreviation="kg")
        self.item = InventoryItem.objects.create(name="Beef Mince", unit=self.unit)
        category = ProductCategory.objects.create(name="Mains")
        self.product = Product.objects.create(
            name="Burger",
            product_code=1001,
            category=category,
            branch=self.branch,
            price=Decimal("10.00"),
        )
        # A signal creates a BranchInventory row for every branch when an
        # InventoryItem is saved, so this updates that row rather than adding
        # a second one and tripping the (branch, item) unique constraint.
        self.stock, _ = BranchInventory.objects.update_or_create(
            item=self.item,
            branch=self.branch,
            defaults={"quantity": Decimal("50"), "minimum_threshold": Decimal("0")},
        )

    def _sell(self, when: date, quantity: int):
        sale = SalesTransaction.objects.create(
            branch=self.branch,
            product=self.product,
            quantity_sold=quantity,
            unit_price=Decimal("1.00"),
            occurred_at=timezone.make_aware(
                timezone.datetime.combine(when, timezone.datetime.min.time())
            ),
        )
        InventoryConsumption.objects.create(
            inventory_item=self.item,
            sales_transaction=sale,
            quantity_consumed=Decimal(quantity),
        )

    def test_demand_is_dated_by_the_sale_not_by_the_row_write(self):
        """
        InventoryConsumption.timestamp is auto_now_add — it records when the
        row was written, not when the stock was consumed. Reading it would put
        every historical sale on today's date.
        """
        today = timezone.now().date()
        self._sell(today - timedelta(days=10), 7)

        series = daily_demand_series(
            self.item.pk, self.branch.pk, today - timedelta(days=30), today
        )

        self.assertEqual(series[today - timedelta(days=10)], 7.0)
        self.assertEqual(series[today], 0.0)

    def test_days_without_sales_are_included_as_zero(self):
        # Omitting them would inflate both the mean and the variance: an item
        # sold on 3 of 90 days would look like steady daily demand.
        today = timezone.now().date()
        self._sell(today - timedelta(days=1), 10)

        series = daily_demand_series(
            self.item.pk, self.branch.pk, today - timedelta(days=4), today
        )

        self.assertEqual(len(series), 5)
        self.assertEqual(sum(series.values()), 10.0)

    def test_same_day_sales_are_summed(self):
        today = timezone.now().date()
        day = today - timedelta(days=2)
        self._sell(day, 4)
        self._sell(day, 6)

        series = daily_demand_series(self.item.pk, self.branch.pk, day, today)
        self.assertEqual(series[day], 10.0)

    def test_profile_reads_stock_and_threshold_from_the_row(self):
        today = timezone.now().date()
        for offset in range(1, 20):
            self._sell(today - timedelta(days=offset), 5)

        p = profile_for(self.stock, history_days=30)

        self.assertEqual(p.on_hand, 50.0)
        self.assertEqual(p.configured_threshold, 0.0)
        self.assertTrue(p.has_enough_history)
        self.assertGreater(p.mean_daily_demand, 0)

    def test_ranking_puts_the_least_cover_first(self):
        today = timezone.now().date()
        for offset in range(1, 30):
            self._sell(today - timedelta(days=offset), 20)

        second_item = InventoryItem.objects.create(name="Salt", unit=self.unit)
        BranchInventory.objects.update_or_create(
            item=second_item,
            branch=self.branch,
            defaults={"quantity": Decimal("9999"), "minimum_threshold": Decimal("0")},
        )

        ranked = rank_inventory(BranchInventory.objects.all(), history_days=60)
        self.assertEqual(ranked[0].item_name, "Beef Mince")
