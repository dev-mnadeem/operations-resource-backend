from django.db import models


class Vendor(models.Model):
    """Supplier / vendor master record."""

    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    payment_terms = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. 'Net 30', 'COD', '50% advance'",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """Purchase order raised against an approved demand."""

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_PARTIALLY_RECEIVED = "partially_received"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent to Vendor"),
        (STATUS_PARTIALLY_RECEIVED, "Partially Received"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    demand = models.ForeignKey(
        "demands.Demand",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
        help_text="Assign vendor before sending the PO.",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    expected_delivery_date = models.DateField(null=True, blank=True)
    image_field = models.FileField(
        upload_to="purchase_orders/",
        null=True,
        blank=True,
        help_text="Optional image attachment for this purchase order.",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="purchase_orders_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Purchase order"
        verbose_name_plural = "Purchase orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"PO #{self.pk} — {self.vendor} ({self.get_status_display()})"


class PurchaseOrderItem(models.Model):
    """Line item in a purchase order."""

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="po_items",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Agreed unit price from vendor.",
    )

    class Meta:
        verbose_name = "Purchase order item"
        verbose_name_plural = "Purchase order items"
        ordering = ["purchase_order", "inventory_item"]
        unique_together = [["purchase_order", "inventory_item"]]

    def __str__(self):
        return f"{self.inventory_item.name} × {self.quantity} @ {self.unit_price}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class GoodsReceipt(models.Model):
    """
    Goods receiving record against a demand.

    Spec fields:
    (demand, receiver, received_at, status, total_received_quantity)
    """

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_PARTIAL = "partial"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_PARTIAL, "Partially received"),
    ]

    demand = models.ForeignKey(
        "demands.Demand",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
        help_text="Linked purchase order (optional; set when PO workflow is used).",
    )
    receiver = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    received_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    total_received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    image_file = models.FileField(
        upload_to="goods_receipts/",
        null=True,
        blank=True,
        help_text="Optional goods receipt image proof.",
    )

    class Meta:
        verbose_name = "Goods receipt"
        verbose_name_plural = "Goods receipts"
        ordering = ["-received_at"]

    def __str__(self):
        return f"GR for {self.demand} at {self.received_at}"


class GoodsReceiptItem(models.Model):
    """
    Line items on a goods receipt.

    Spec fields:
    (goods_receipt, inventory_item, expected_quantity,
     received_quantity, variance, condition, images)
    """

    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    expected_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    variance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Received quantity - expected quantity.",
    )
    condition = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional condition/quality notes (e.g. damaged, short, excess).",
    )

    class Meta:
        verbose_name = "Goods receipt item"
        verbose_name_plural = "Goods receipt items"
        ordering = ["goods_receipt", "inventory_item"]

    def __str__(self):
        return f"{self.goods_receipt} - {self.inventory_item}"


class PurchaseReceiptImage(models.Model):
    """
    Receipt images uploaded by the purchaser against a demand.
    """

    demand = models.ForeignKey(
        "demands.Demand",
        on_delete=models.CASCADE,
        related_name="purchase_receipt_images",
    )
    image_file = models.FileField(upload_to="purchase_receipts/", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Purchase receipt image"
        verbose_name_plural = "Purchase receipt images"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Purchase receipt for {self.demand}"


class ReceivedItemImage(models.Model):
    """
    Image/file evidence for a received goods receipt item (uploaded by branch manager).
    """

    goods_receipt_item = models.ForeignKey(
        GoodsReceiptItem,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image_file = models.FileField(upload_to="receipts/", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Received item image"
        verbose_name_plural = "Received item images"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Received image for {self.goods_receipt_item}"


class Notification(models.Model):
    """
    Simple notification model.

    Spec fields:
    (user, message, type, is_read, created_at,
     related_object_type, related_object_id)
    """

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.TextField()
    type = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.user}: {self.message[:50]}"
