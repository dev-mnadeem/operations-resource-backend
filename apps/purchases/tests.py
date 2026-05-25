from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.common.testing import (
    PLAIN_STATIC_FILES,
    branch_qty,
    make_branch,
    make_item,
    make_user,
)
from apps.demands.models import Demand
from apps.purchases.models import GoodsReceipt, GoodsReceiptItem, Notification


class GoodsReceiptTestCase(TestCase):
    def setUp(self):
        self.branch = make_branch("RCV")
        self.item = make_item()
        self.manager = make_user("Branch Manager", branch=self.branch)
        self.admin = make_user("Admin")
        self.purchaser = make_user("Purchaser")
        self.demand = Demand.objects.create(
            branch=self.branch,
            status=Demand.STATUS_APPROVED,
            submitted_by=self.manager,
        )
        self.receipt = GoodsReceipt.objects.create(
            demand=self.demand, receiver=self.manager, received_at=timezone.now()
        )

    def add_line(self, received, expected="10", item=None):
        return GoodsReceiptItem.objects.create(
            goods_receipt=self.receipt,
            inventory_item=item or self.item,
            expected_quantity=Decimal(expected),
            received_quantity=Decimal(received),
        )


class ReceiptStockTests(GoodsReceiptTestCase):
    def test_a_received_line_credits_the_branch(self):
        self.add_line("8")
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("8"))

    def test_editing_a_line_applies_only_the_difference(self):
        line = self.add_line("8")
        line.received_quantity = Decimal("10")
        line.save()
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("10"))

    def test_deleting_a_line_takes_its_stock_back(self):
        line = self.add_line("8")
        line.delete()
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("0"))

    def test_repointing_a_line_moves_the_credit_to_the_new_item(self):
        other = make_item()
        line = self.add_line("8")
        line.inventory_item = other
        line.save()
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("0"))
        self.assertEqual(branch_qty(self.branch, other), Decimal("8"))


class ReceiptNotificationTests(GoodsReceiptTestCase):
    def discrepancy_count(self):
        return Notification.objects.filter(type="receipt_discrepancy").count()

    def test_a_short_delivery_is_reported_once_per_recipient(self):
        self.add_line("6")
        self.receipt.status = GoodsReceipt.STATUS_PARTIAL
        self.receipt.save()
        # Further saves (e.g. another line refreshing the total) are not news.
        self.receipt.save()
        self.add_line("5", item=make_item())
        self.assertEqual(self.discrepancy_count(), 2)  # admin + purchaser

    def test_an_exact_delivery_raises_no_discrepancy(self):
        self.add_line("10")
        self.receipt.status = GoodsReceipt.STATUS_COMPLETED
        self.receipt.save()
        self.assertEqual(self.discrepancy_count(), 0)

    def test_a_superuser_in_the_admin_group_is_notified_once(self):
        self.admin.is_superuser = True
        self.admin.save()
        receipt = GoodsReceipt.objects.create(
            demand=self.demand, receiver=self.manager, received_at=timezone.now()
        )
        self.assertEqual(
            Notification.objects.filter(
                type="goods_receipt_created",
                user=self.admin,
                related_object_id=receipt.pk,
            ).count(),
            1,
        )


@PLAIN_STATIC_FILES
class ReceiptBranchScopeTests(GoodsReceiptTestCase):
    def setUp(self):
        super().setUp()
        self.add_line("0")
        self.outsider = make_user("Branch Manager", branch=make_branch("OTH"))

    def test_a_manager_cannot_list_another_branchs_receipts(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("admin:purchases_goodsreceipt_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].queryset), [])

    def test_a_manager_cannot_receive_another_branchs_goods(self):
        line = self.receipt.items.get()
        self.client.force_login(self.outsider)
        self.client.post(
            reverse("admin:purchases_goodsreceipt_receive", args=[self.receipt.pk]),
            {f"received_{line.pk}": "9"},
        )
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("0"))

    def test_the_branchs_own_manager_can_receive(self):
        line = self.receipt.items.get()
        self.client.force_login(self.manager)
        self.client.post(
            reverse("admin:purchases_goodsreceipt_receive", args=[self.receipt.pk]),
            {f"received_{line.pk}": "9"},
        )
        self.assertEqual(branch_qty(self.branch, self.item), Decimal("9"))
