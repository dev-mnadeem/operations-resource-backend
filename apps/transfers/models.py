from django.db import models


class Transfer(models.Model):
    """
    Transfer of inventory between branches and/or warehouses.

    Spec fields: (from_location, to_location, transfer_type, status,
    initiated_by, initiated_at, approved_by, approved_at, dispatched_at, received_at)
    """

    TRANSFER_BRANCH_TO_BRANCH = "branch_to_branch"
    TRANSFER_BRANCH_TO_WAREHOUSE = "branch_to_warehouse"
    TRANSFER_WAREHOUSE_TO_BRANCH = "warehouse_to_branch"
    TRANSFER_WAREHOUSE_TO_WAREHOUSE = "warehouse_to_warehouse"
    TRANSFER_TYPE_CHOICES = [
        (TRANSFER_BRANCH_TO_BRANCH, "Branch to Branch"),
        (TRANSFER_BRANCH_TO_WAREHOUSE, "Branch to Warehouse"),
        (TRANSFER_WAREHOUSE_TO_BRANCH, "Warehouse to Branch"),
        (TRANSFER_WAREHOUSE_TO_WAREHOUSE, "Warehouse to Warehouse"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DISPATCHED = "dispatched"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DISPATCHED, "Dispatched"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    from_branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_from",
    )
    from_warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_from",
    )
    to_branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_to",
    )
    to_warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_to",
    )
    transfer_type = models.CharField(
        max_length=30,
        choices=TRANSFER_TYPE_CHOICES,
        help_text="Automatically determined from from/to locations",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    initiated_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="transfers_initiated",
    )
    initiated_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True,
        help_text="Optional notes or reason for this transfer.",
    )
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfers_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Transfer"
        verbose_name_plural = "Transfers"
        ordering = ["-initiated_at"]

    def __str__(self):
        from_loc = (
            self.from_branch.branch_code
            if self.from_branch
            else (self.from_warehouse.name if self.from_warehouse else "Unknown")
        )
        to_loc = (
            self.to_branch.branch_code
            if self.to_branch
            else (self.to_warehouse.name if self.to_warehouse else "Unknown")
        )
        return f"Transfer {self.id}: {from_loc} → {to_loc} ({self.status})"

    def clean(self):
        """Validate that exactly one from_location and one to_location are set."""
        from django.core.exceptions import ValidationError

        if not self.from_branch and not self.from_warehouse:
            raise ValidationError("Either from_branch or from_warehouse must be set.")
        if self.from_branch and self.from_warehouse:
            raise ValidationError("Cannot set both from_branch and from_warehouse.")
        if not self.to_branch and not self.to_warehouse:
            raise ValidationError("Either to_branch or to_warehouse must be set.")
        if self.to_branch and self.to_warehouse:
            raise ValidationError("Cannot set both to_branch and to_warehouse.")


class TransferItem(models.Model):
    """
    Line item in a transfer.

    Spec fields: (transfer, inventory_item, quantity, dispatched_quantity,
    received_quantity, variance)
    """

    transfer = models.ForeignKey(
        Transfer,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="transfer_items",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Requested/expected quantity",
    )
    dispatched_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual quantity dispatched",
    )
    received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual quantity received",
    )
    variance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Received quantity - dispatched quantity",
    )

    class Meta:
        verbose_name = "Transfer item"
        verbose_name_plural = "Transfer items"
        ordering = ["transfer", "inventory_item"]
        unique_together = [["transfer", "inventory_item"]]

    def __str__(self):
        return f"{self.inventory_item.name} x {self.quantity} (Transfer {self.transfer.id})"
