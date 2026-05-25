from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.common.testing import make_branch, make_item, make_user
from apps.inventory.models import BranchInventory, StockCycleCount
from apps.purchases.models import Notification


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
