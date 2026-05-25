from decimal import Decimal

from django.test import TestCase

from apps.common.testing import (
    make_branch,
    make_item,
    make_user,
    make_warehouse,
    warehouse_qty,
)
from apps.purchases.models import Notification
from apps.warehouse.models import WarehouseRequest, WarehouseTransaction


class WarehouseRequestNotificationTests(TestCase):
    def setUp(self):
        self.warehouse = make_warehouse()
        self.branch = make_branch()
        self.requester = make_user("Branch Manager", branch=self.branch)
        self.approver = make_user("Warehouse Manager", warehouse=self.warehouse)
        self.request = WarehouseRequest.objects.create(
            warehouse=self.warehouse, branch=self.branch, requested_by=self.requester
        )

    def test_the_warehouse_manager_hears_about_a_new_request(self):
        self.assertTrue(
            Notification.objects.filter(
                user=self.approver, type="warehouse_request_submitted"
            ).exists()
        )

    def test_a_superuser_admin_is_told_about_a_new_request_once(self):
        admin = make_user("Admin", is_superuser=True)
        WarehouseRequest.objects.create(
            warehouse=self.warehouse, branch=self.branch, requested_by=self.requester
        )
        self.assertEqual(Notification.objects.filter(user=admin).count(), 1)

    def test_approval_is_reported_to_the_requester_once(self):
        self.request.status = WarehouseRequest.STATUS_APPROVED
        self.request.approved_by = self.approver
        self.request.save()
        self.request.rejection_reason = ""
        self.request.save()
        self.assertEqual(
            Notification.objects.filter(
                user=self.requester, type="warehouse_request_approved"
            ).count(),
            1,
        )


class WarehouseTransactionTests(TestCase):
    def setUp(self):
        self.item = make_item()
        self.warehouse = make_warehouse()
        self.user = make_user("Warehouse Manager", warehouse=self.warehouse)

    def record(self, kind, qty):
        WarehouseTransaction.objects.create(
            warehouse=self.warehouse,
            inventory_item=self.item,
            transaction_type=kind,
            quantity=Decimal(qty),
            user=self.user,
        )

    def test_inward_outward_and_adjustment_move_stock(self):
        self.record(WarehouseTransaction.TRANSACTION_INWARD, "20")
        self.record(WarehouseTransaction.TRANSACTION_OUTWARD, "5")
        self.record(WarehouseTransaction.TRANSACTION_ADJUSTMENT, "-2")
        self.assertEqual(warehouse_qty(self.warehouse, self.item), Decimal("13"))
