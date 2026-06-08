from django.db import models


class Warehouse(models.Model):
    name = models.TextField()
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"{self.id} - {self.name or 'Unnamed Warehouse'}"


class WarehouseInventory(models.Model):
    """
    Inventory ledger for warehouse items.

    Spec fields: (warehouse, inventory_item, quantity, location)
    """

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="warehouse_inventories",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="warehouse_inventories",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Current stock quantity in warehouse",
    )
    minimum_threshold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Minimum stock level; alerts when quantity falls below this.",
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Storage location within warehouse (e.g., 'Aisle 3, Shelf B')",
    )

    class Meta:
        verbose_name = "Warehouse inventory"
        verbose_name_plural = "Warehouse inventories"
        ordering = ["warehouse", "inventory_item"]
        unique_together = [["warehouse", "inventory_item"]]

    def __str__(self):
        return f"{self.inventory_item.name} @ {self.warehouse.name}: {self.quantity}"


class WarehouseTransaction(models.Model):
    """
    Audit trail for warehouse inventory movements.

    Spec fields: (warehouse, inventory_item, transaction_type, quantity,
    reference_type, reference_id, user, timestamp)
    """

    TRANSACTION_INWARD = "inward"
    TRANSACTION_OUTWARD = "outward"
    TRANSACTION_ADJUSTMENT = "adjustment"
    TRANSACTION_CHOICES = [
        (TRANSACTION_INWARD, "Inward"),
        (TRANSACTION_OUTWARD, "Outward"),
        (TRANSACTION_ADJUSTMENT, "Adjustment"),
    ]

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="warehouse_transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_CHOICES,
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Positive for inward/adjustment increase, negative for outward/adjustment decrease",
    )
    reference_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of related object (e.g., 'WarehouseRequest', 'Transfer', 'GoodsReceipt')",
    )
    reference_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of related object",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="warehouse_transactions",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Warehouse transaction"
        verbose_name_plural = "Warehouse transactions"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} of {self.inventory_item.name} @ {self.warehouse.name}"


class WarehouseRequest(models.Model):
    """
    Request from branch to warehouse for inventory items.

    Spec fields: (warehouse, branch, status, requested_by, requested_at,
    approved_by, approved_at)
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.PROTECT,
        related_name="warehouse_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    requested_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="warehouse_requests_created",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="warehouse_requests_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection if status is rejected",
    )

    class Meta:
        verbose_name = "Warehouse request"
        verbose_name_plural = "Warehouse requests"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Request {self.id}: {self.branch.branch_code} → {self.warehouse.name} ({self.status})"


class WarehouseRequestItem(models.Model):
    """
    Line item in a warehouse request.

    Spec fields: (warehouse_request, inventory_item, quantity)
    """

    warehouse_request = models.ForeignKey(
        WarehouseRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="warehouse_request_items",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    class Meta:
        verbose_name = "Warehouse request item"
        verbose_name_plural = "Warehouse request items"
        ordering = ["warehouse_request", "inventory_item"]
        unique_together = [["warehouse_request", "inventory_item"]]

    def __str__(self):
        return f"{self.inventory_item.name} x {self.quantity} (Request {self.warehouse_request.id})"
