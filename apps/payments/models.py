from django.db import models


class PaymentDocument(models.Model):
    """Uploaded financial document (cheque scan, receipt, proof of payment)."""

    TYPE_CHEQUE = "cheque"
    TYPE_RECEIPT = "receipt"
    TYPE_PROOF_OF_PAYMENT = "proof_of_payment"
    TYPE_CHOICES = [
        (TYPE_CHEQUE, "Cheque"),
        (TYPE_RECEIPT, "Receipt"),
        (TYPE_PROOF_OF_PAYMENT, "Proof of Payment"),
    ]

    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    file = models.FileField(upload_to="payment_documents/")
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="payment_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Payment document"
        verbose_name_plural = "Payment documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} uploaded by {self.uploaded_by} at {self.uploaded_at:%Y-%m-%d}"


class VendorInvoice(models.Model):
    """Invoice received from a vendor."""

    STATUS_UNPAID = "unpaid"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_UNPAID, "Unpaid"),
        (STATUS_PARTIAL, "Partially paid"),
        (STATUS_PAID, "Paid"),
    ]

    vendor = models.ForeignKey(
        "purchases.Vendor",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    purchase_order = models.ForeignKey(
        "purchases.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID
    )
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vendor invoice"
        verbose_name_plural = "Vendor invoices"
        ordering = ["-received_at"]
        unique_together = [["vendor", "invoice_number"]]

    def __str__(self):
        return f"Invoice {self.invoice_number} from {self.vendor} ({self.get_status_display()})"


class Payment(models.Model):
    """Payment made against a vendor invoice."""

    purchase_order = models.ForeignKey(
        "purchases.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    vendor_invoice = models.ForeignKey(
        VendorInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    document = models.ForeignKey(
        PaymentDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    recorded_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="payments_recorded",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"Payment of {self.amount} on {self.payment_date} by {self.recorded_by}"
