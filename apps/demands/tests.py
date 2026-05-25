from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.common.testing import make_branch, make_item, make_user, set_branch_qty
from apps.demands.models import Demand
from apps.demands.services import get_automated_demand_suggestions
from apps.inventory.models import BranchInventory
from apps.products.models import Product
from apps.purchases.models import Notification
from apps.sales.models import InventoryConsumption, SalesTransaction


class DemandSuggestionTests(TestCase):
    def setUp(self):
        self.branch = make_branch()
        self.item = make_item()
        self.product = Product.objects.create(product_code=5, name="Soup", price=1)

    def consume(self, qty, days_ago):
        sale = SalesTransaction.objects.create(
            branch=self.branch,
            product=self.product,
            quantity_sold=1,
            total_amount=0,
            occurred_at=timezone.now() - timedelta(days=days_ago),
        )
        InventoryConsumption.objects.create(
            inventory_item=self.item,
            sales_transaction=sale,
            quantity_consumed=Decimal(qty),
        )

    def test_threshold_gap_is_suggested(self):
        BranchInventory.objects.filter(branch=self.branch, item=self.item).update(
            quantity=2, minimum_threshold=5
        )
        self.assertEqual(
            get_automated_demand_suggestions(self.branch.pk), {self.item.pk: 3.0}
        )

    def test_trend_is_fourteen_days_of_the_thirty_day_average(self):
        self.consume("30", days_ago=3)
        self.assertEqual(
            get_automated_demand_suggestions(self.branch.pk), {self.item.pk: 14.0}
        )

    def test_old_sales_imported_today_do_not_count_as_recent(self):
        self.consume("300", days_ago=60)
        self.assertEqual(get_automated_demand_suggestions(self.branch.pk), {})


class DemandNotificationTests(TestCase):
    def setUp(self):
        self.branch = make_branch()
        self.manager = make_user("Branch Manager", branch=self.branch)
        self.purchaser = make_user("Purchaser", branch=self.branch)
        self.other_purchaser = make_user("Purchaser", branch=make_branch())
        self.admin = make_user("Admin")
        set_branch_qty(self.branch, make_item(), "0")
        self.demand = Demand.objects.create(
            branch=self.branch,
            status=Demand.STATUS_SUBMITTED,
            submitted_by=self.manager,
        )

    def recipients(self, kind):
        return set(
            Notification.objects.filter(type=kind).values_list("user_id", flat=True)
        )

    def test_a_branch_managers_demand_is_emailed_to_purchasers(self):
        self.assertEqual(
            sorted(m.to[0] for m in mail.outbox),
            sorted([self.purchaser.email, self.other_purchaser.email]),
        )

    def test_a_new_demand_reaches_admins_and_the_branchs_purchasers(self):
        self.assertEqual(
            self.recipients("demand_submitted"), {self.admin.pk, self.purchaser.pk}
        )

    def test_approval_tells_the_submitter_once(self):
        self.demand.status = Demand.STATUS_APPROVED
        self.demand.approved_by = self.purchaser
        self.demand.save()
        self.demand.save()
        self.assertEqual(
            Notification.objects.filter(
                type="demand_approved", user=self.manager
            ).count(),
            1,
        )
