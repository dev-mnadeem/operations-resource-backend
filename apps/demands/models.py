from django.db import models


class Demand(models.Model):
    """
    Demand raised by a branch for inventory items.

    Spec fields:
    (branch, status, submitted_by, submitted_at,
     approved_by, approved_at, rejection_reason)
    """

    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_APPROVED = "approved"
    STATUS_COMPLETED = "completed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        related_name="demands",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
    )
    submitted_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="submitted_demands",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_demands",
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Demand"
        verbose_name_plural = "Demands"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"Demand #{self.pk} - {self.branch} ({self.status})"


class DemandItem(models.Model):
    """
    Line items for a demand.

    Spec fields:
    (demand, inventory_item, quantity, unit, priority)
    """

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    demand = models.ForeignKey(
        Demand,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="demand_items",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit = models.ForeignKey(
        "inventory.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="demand_items",
    )
    approved_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Approved quantity (for partial approval). Null = full quantity approved.",
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )

    class Meta:
        verbose_name = "Demand item"
        verbose_name_plural = "Demand items"
        ordering = ["demand", "priority", "inventory_item"]
        unique_together = [["demand", "inventory_item"]]

    def __str__(self):
        return f"{self.demand} - {self.inventory_item} x {self.quantity}"
