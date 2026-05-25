from decimal import Decimal

from django.test import TestCase

from apps.common.testing import (
    branch_qty,
    make_branch,
    make_item,
    make_user,
    make_warehouse,
    set_branch_qty,
    warehouse_qty,
)
from apps.purchases.models import Notification
from apps.transfers.models import Transfer, TransferItem


class TransferStockMovementTests(TestCase):
    def setUp(self):
        self.source = make_branch("SRC")
        self.dest = make_branch("DST")
        self.item = make_item()
        set_branch_qty(self.source, self.item, "50")
        self.user = make_user("Admin")
        self.transfer = Transfer.objects.create(
            from_branch=self.source,
            to_branch=self.dest,
            transfer_type=Transfer.TRANSFER_BRANCH_TO_BRANCH,
            status=Transfer.STATUS_APPROVED,
            initiated_by=self.user,
        )
        self.line = TransferItem.objects.create(
            transfer=self.transfer, inventory_item=self.item, quantity=Decimal("10")
        )

    def set_status(self, status):
        self.transfer.status = status
        self.transfer.save()

    def test_dispatch_deducts_from_the_source(self):
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.assertEqual(branch_qty(self.source, self.item), Decimal("40"))

    def test_dispatch_uses_the_dispatched_quantity_when_given(self):
        self.line.dispatched_quantity = Decimal("7")
        self.line.save()
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.assertEqual(branch_qty(self.source, self.item), Decimal("43"))

    def test_saving_a_dispatched_transfer_again_does_not_deduct_twice(self):
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.transfer.notes = "Driver delayed"
        self.transfer.save()
        self.assertEqual(branch_qty(self.source, self.item), Decimal("40"))

    def test_dispatch_notifies_once(self):
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.transfer.save()
        self.assertEqual(
            Notification.objects.filter(type="transfer_dispatched").count(), 1
        )

    def test_receive_adds_to_the_destination_once(self):
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.set_status(Transfer.STATUS_RECEIVED)
        self.transfer.save()
        self.assertEqual(branch_qty(self.dest, self.item), Decimal("10"))
        self.assertEqual(branch_qty(self.source, self.item), Decimal("40"))

    def test_receiving_zero_adds_nothing(self):
        self.set_status(Transfer.STATUS_DISPATCHED)
        self.line.received_quantity = Decimal("0")
        self.line.save()
        self.set_status(Transfer.STATUS_RECEIVED)
        self.assertEqual(branch_qty(self.dest, self.item), Decimal("0"))

    def test_warehouse_source_is_deducted(self):
        warehouse = make_warehouse()
        transfer = Transfer.objects.create(
            from_warehouse=warehouse,
            to_branch=self.dest,
            transfer_type=Transfer.TRANSFER_WAREHOUSE_TO_BRANCH,
            status=Transfer.STATUS_APPROVED,
            initiated_by=self.user,
        )
        TransferItem.objects.create(
            transfer=transfer, inventory_item=self.item, quantity=Decimal("3")
        )
        transfer.status = Transfer.STATUS_DISPATCHED
        transfer.save()
        transfer.save()
        self.assertEqual(warehouse_qty(warehouse, self.item), Decimal("-3"))
