import tempfile
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.common.testing import branch_qty, make_branch, make_item, set_branch_qty
from apps.inventory.models import BOM, BOMItem
from apps.products.models import Product
from apps.sales.models import InventoryConsumption, SalesTransaction
from apps.sales.tasks import save_sales_attachment


class SaleConsumptionTests(TestCase):
    def setUp(self):
        self.branch = make_branch()
        self.cheese = make_item("Cheese")
        set_branch_qty(self.branch, self.cheese, "10")
        self.product = Product.objects.create(
            product_code=1001, name="Pizza", price=Decimal("1500")
        )
        bom = BOM.objects.get(product=self.product)  # created by a signal
        # 250 g of cheese per pizza, stock kept in kg
        BOMItem.objects.create(
            bom=bom,
            inventory_item=self.cheese,
            quantity=Decimal("250"),
            conversion_factor=Decimal("0.001"),
        )

    def sell(self, qty):
        return SalesTransaction.objects.create(
            branch=self.branch,
            product=self.product,
            quantity_sold=qty,
            total_amount=Decimal("0"),
            occurred_at=timezone.now(),
        )

    def test_a_sale_consumes_the_bom_in_base_units(self):
        sale = self.sell(4)
        self.assertEqual(branch_qty(self.branch, self.cheese), Decimal("9"))
        consumption = InventoryConsumption.objects.get(sales_transaction=sale)
        self.assertEqual(consumption.quantity_consumed, Decimal("1"))

    def test_the_total_is_quantity_times_the_product_price(self):
        self.assertEqual(self.sell(2).total_amount, Decimal("3000"))


class SalesAttachmentTests(SimpleTestCase):
    def attachment(self, filename, payload=b"sheet"):
        part = EmailMessage()
        part.add_attachment(
            payload, maintype="application", subtype="vnd.ms-excel", filename=filename
        )
        return next(part.iter_attachments())

    def test_a_hostile_name_cannot_leave_the_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_sales_attachment(
                self.attachment("../../evil.xls"), directory=directory
            )
            self.assertEqual(path.parent, Path(directory))
            self.assertEqual(path.read_bytes(), b"sheet")

    def test_encoded_names_are_decoded_before_the_extension_check(self):
        part = self.attachment("placeholder.xls")
        part.replace_header(
            "Content-Disposition",
            'attachment; filename="=?utf-8?b?' + "c2FsZXMueGxz" + '?="',
        )  # base64 of "sales.xls"
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNotNone(save_sales_attachment(part, directory=directory))

    def test_other_attachments_are_ignored(self):
        self.assertIsNone(save_sales_attachment(self.attachment("notes.pdf")))
