"""Who sees which branch's replenishment advice, through the API and the admin."""

from decimal import Decimal

from django.contrib import admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.common.testing import make_branch, make_item, make_user, set_branch_qty
from apps.products.models import Product
from apps.replenishment.models import ReplenishmentAdvice
from apps.sales.models import InventoryConsumption, SalesTransaction

URL = reverse("replenishment-advice")


class ReplenishmentScopeTestCase(TestCase):
    def setUp(self):
        self.north = make_branch("NTH")
        self.south = make_branch("STH")
        self.item = make_item("Flour")
        set_branch_qty(self.north, self.item, "10")
        set_branch_qty(self.south, self.item, "10")
        product = Product.objects.create(product_code=7, name="Bread", price=1)
        # North sells 1 a day, south 9 a day.
        for branch, qty in ((self.north, 1), (self.south, 9)):
            for days_ago in range(10):
                sale = SalesTransaction.objects.create(
                    branch=branch,
                    product=product,
                    quantity_sold=qty,
                    total_amount=0,
                    occurred_at=timezone.now() - timezone.timedelta(days=days_ago),
                )
                InventoryConsumption.objects.create(
                    inventory_item=self.item,
                    sales_transaction=sale,
                    quantity_consumed=Decimal(qty),
                )
        self.admin = make_user("Admin")
        self.north_manager = make_user("Branch Manager", branch=self.north)


class AdviceApiScopeTests(ReplenishmentScopeTestCase):
    def branches_seen_by(self, user, **params):
        self.client.force_login(user)
        response = self.client.get(URL, params)
        self.assertEqual(response.status_code, 200)
        return {row["branch"] for row in response.json()["results"]}

    def test_an_admin_sees_every_branch(self):
        self.assertEqual(
            self.branches_seen_by(self.admin), {str(self.north), str(self.south)}
        )

    def test_a_branch_manager_sees_only_their_branch(self):
        self.assertEqual(self.branches_seen_by(self.north_manager), {str(self.north)})

    def test_asking_for_another_branch_returns_nothing(self):
        self.assertEqual(self.branches_seen_by(self.north_manager, branch="STH"), set())

    def test_a_purchaser_sees_the_branches_they_buy_for(self):
        purchaser = make_user("Purchaser")
        purchaser.purchaser_branches.add(self.south)
        self.assertEqual(self.branches_seen_by(purchaser), {str(self.south)})

    def test_anonymous_requests_are_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))

    def test_non_positive_limits_are_rejected(self):
        self.client.force_login(self.admin)
        for params in ({"limit": 0}, {"history_days": 0}, {"lead_time_days": -1}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(URL, params).status_code, 400)


class AdviceAdminTests(ReplenishmentScopeTestCase):
    def rows_for(self, user):
        request = RequestFactory().get("/")
        request.user = user
        model_admin = admin.site._registry[ReplenishmentAdvice]
        return {row.branch_id: row for row in model_admin.get_queryset(request)}

    def test_each_row_is_ranked_on_its_own_branchs_demand(self):
        rows = self.rows_for(self.admin)
        self.assertAlmostEqual(rows["NTH"].demand_total, 10)
        self.assertAlmostEqual(rows["STH"].demand_total, 90)

    def test_a_branch_manager_sees_only_their_branch(self):
        self.assertEqual(set(self.rows_for(self.north_manager)), {"NTH"})
