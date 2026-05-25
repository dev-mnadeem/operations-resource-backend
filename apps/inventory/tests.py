import io
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import authenticate
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.common.testing import (
    branch_qty,
    make_branch,
    make_item,
    make_user,
    make_warehouse,
    warehouse_qty,
)
from apps.inventory.models import (
    BranchInventory,
    InventoryItem,
    StockAdjustment,
    StockCycleCount,
)
from apps.purchases.models import Notification
from apps.sales.models import SalesTransaction


class InventoryRowTests(TestCase):
    def test_new_items_and_branches_get_a_zero_stock_row(self):
        item = make_item()
        branch = make_branch()
        self.assertTrue(BranchInventory.objects.filter(item=item, branch=branch))

    def test_a_blank_barcode_is_generated(self):
        item = make_item()
        self.assertRegex(item.barcode, r"^BC[0-9A-F]{6}$")


class CycleCountVarianceTests(TestCase):
    def setUp(self):
        self.branch = make_branch()
        self.manager = make_user("Branch Manager", branch=self.branch)
        self.admin = make_user("Admin")
        self.count = StockCycleCount.objects.create(
            inventory_item=make_item(),
            branch=self.branch,
            scheduled_date=date(2026, 1, 5),
            counted_quantity=Decimal("8"),
            variance=Decimal("-2"),
        )

    def alerts(self):
        return Notification.objects.filter(type="cycle_count_variance")

    def test_completing_a_count_with_variance_alerts_manager_and_admin(self):
        self.count.status = StockCycleCount.STATUS_COMPLETED
        self.count.save()
        self.assertEqual(
            set(self.alerts().values_list("user_id", flat=True)),
            {self.manager.pk, self.admin.pk},
        )

    def test_saving_a_completed_count_again_does_not_repeat_the_alert(self):
        self.count.status = StockCycleCount.STATUS_COMPLETED
        self.count.save()
        self.count.actual_date = date(2026, 1, 6)
        self.count.save()
        self.assertEqual(self.alerts().count(), 2)

    def test_a_scheduled_count_raises_nothing(self):
        self.count.save()
        self.assertFalse(self.alerts().exists())


class StockAdjustmentTests(TestCase):
    def setUp(self):
        self.user = make_user("Admin")

    def adjust(self, kind, qty, **where):
        StockAdjustment.objects.create(
            inventory_item=self.item,
            adjustment_type=kind,
            quantity=Decimal(qty),
            reason="test",
            user=self.user,
            **where,
        )

    def test_branch_increase_and_decrease(self):
        branch = make_branch()
        self.item = make_item()
        self.adjust(StockAdjustment.ADJUST_INCREASE, "5", branch=branch)
        self.adjust(StockAdjustment.ADJUST_DECREASE, "2", branch=branch)
        self.assertEqual(branch_qty(branch, self.item), Decimal("3"))

    def test_a_warehouse_adjustment_for_a_newer_item_is_not_lost(self):
        warehouse = make_warehouse()
        self.item = make_item()  # created after the warehouse: no stock row yet
        self.adjust(StockAdjustment.ADJUST_INCREASE, "4", warehouse=warehouse)
        self.assertEqual(warehouse_qty(warehouse, self.item), Decimal("4"))


class BarcodeLookupTests(TestCase):
    def setUp(self):
        self.north = make_branch("NTH")
        self.south = make_branch("STH")
        self.item = make_item("Mozzarella")
        BranchInventory.objects.filter(item=self.item, branch=self.north).update(
            quantity=4
        )

    def lookup(self, user, barcode=None):
        self.client.force_login(user)
        return self.client.get(
            reverse("barcode-lookup", args=[barcode or self.item.barcode])
        )

    def test_admins_see_stock_for_every_branch(self):
        stock = self.lookup(make_user("Admin")).json()["stock"]
        self.assertEqual({row["branch__branch_code"] for row in stock}, {"NTH", "STH"})

    def test_branch_managers_see_their_own_branch(self):
        stock = self.lookup(make_user("Branch Manager", branch=self.north)).json()
        self.assertEqual(stock["stock"]["branch_code"], "NTH")
        self.assertEqual(stock["stock"]["quantity"], "4.00")

    def test_purchasers_get_item_details_without_stock(self):
        data = self.lookup(make_user("Purchaser")).json()
        self.assertEqual(data["name"], "Mozzarella")
        self.assertIsNone(data["stock"])

    def test_an_unknown_barcode_is_a_404(self):
        self.assertEqual(self.lookup(make_user("Admin"), "BC000000").status_code, 404)


class SetupDevCommandTests(TestCase):
    """setup_dev seeds every app at once, so it exercises the signals together."""

    def test_setup_dev_builds_a_usable_demo_dataset(self):
        with mock.patch.dict(
            os.environ,
            {"DEV_ADMIN_PASSWORD": "demo-admin-pw", "DEV_SEED_PASSWORD": "demo-pw"},
        ):
            call_command("setup_dev", "--skip-migrate", stdout=io.StringIO())

        self.assertTrue(
            authenticate(username="admin", password="demo-admin-pw").is_superuser
        )
        self.assertIsNotNone(authenticate(username="bm", password="demo-pw"))
        self.assertGreater(InventoryItem.objects.count(), 100)
        self.assertEqual(SalesTransaction.objects.count(), 30)
