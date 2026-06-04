import secrets

from django.db import IntegrityError, models


class UnitOfMeasure(models.Model):
    """Unit for quantity (kg, g, pcs, L, etc.)."""

    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name = "Unit of measure"
        verbose_name_plural = "Units of measure"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class InventoryCategory(models.Model):
    """Category for inventory items."""

    name = models.CharField(max_length=100)
    parent_category = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
        help_text="Parent category for this category. set null for sections",
    )

    class Meta:
        verbose_name = "Inventory category"
        verbose_name_plural = "Inventory categories"
        ordering = ["name"]
        unique_together = [["name", "parent_category"]]

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """Global stocked item."""

    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=8, unique=True, blank=True)
    sku = models.CharField(max_length=100, blank=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    section = models.ForeignKey(
        InventoryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="section_items",
        limit_choices_to={"parent_category__isnull": True},
        verbose_name="Section",
    )
    category = models.ForeignKey(
        InventoryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="category_items",
        verbose_name="Category",
    )
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )

    class Meta:
        verbose_name = "Inventory item"
        verbose_name_plural = "Inventory items"
        ordering = ["name"]

    def __str__(self):
        return f"{self.barcode} - {self.name}"

    def save(self, *args, **kwargs):
        """
        Auto-generate barcode when blank.
        Keeps user-provided barcode untouched.
        """
        auto_generated = not bool(self.barcode)
        if auto_generated:
            self._assign_unique_barcode()

        for _ in range(5):
            try:
                return super().save(*args, **kwargs)
            except IntegrityError as exc:
                # Handle rare race condition on barcode uniqueness.
                if auto_generated and "barcode" in str(exc).lower():
                    self.barcode = ""
                    self._assign_unique_barcode()
                    continue
                raise

        raise RuntimeError("Failed to save InventoryItem due to repeated collisions.")

    @staticmethod
    def _generate_barcode_candidate():
        """Generate an 8-char barcode: BC + 6 hex chars."""
        return f"BC{secrets.token_hex(3).upper()}"

    def _assign_unique_barcode(self):
        """
        Populate self.barcode with a unique value.
        Retries a few times to avoid random collisions.
        """
        for _ in range(20):
            candidate = self._generate_barcode_candidate()
            qs = type(self).objects.filter(barcode=candidate)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if not qs.exists():
                self.barcode = candidate
                return
        raise RuntimeError("Failed to generate a unique barcode after 20 attempts.")


class BranchInventory(models.Model):
    """Stock tracking for an item at a specific branch."""

    TRACKING_DAILY = "daily"
    TRACKING_WEEKLY = "weekly"
    TRACKING_MONTHLY = "monthly"
    TRACKING_CHOICES = [
        (TRACKING_DAILY, "Daily"),
        (TRACKING_WEEKLY, "Weekly"),
        (TRACKING_MONTHLY, "Monthly"),
    ]

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="branch_inventories",
    )
    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        related_name="branch_inventories",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    minimum_threshold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        blank=True,
    )
    historical_usage = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        blank=True,
        help_text="Historical usage used for planning (optional).",
    )
    tracking_frequency = models.CharField(
        max_length=20,
        choices=TRACKING_CHOICES,
        default=TRACKING_MONTHLY,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Branch inventory"
        verbose_name_plural = "Branch inventories"
        ordering = ["branch", "item"]
        unique_together = [["branch", "item"]]

    def __str__(self):
        return f"{self.item.name} at {self.branch}"


class BOM(models.Model):
    """Bill of materials: a product made from other inventory items."""

    name = models.CharField(max_length=255)
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="boms",
        help_text="The finished product this BOM defines.",
    )

    class Meta:
        verbose_name = "Bill of materials"
        verbose_name_plural = "Bills of materials"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BOMItem(models.Model):
    """One component in a BOM with quantity."""

    bom = models.ForeignKey(
        BOM,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="bom_components",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit = models.ForeignKey(
        "UnitOfMeasure",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bom_items",
        help_text="Unit of this component in the BOM (e.g., 250g). "
        "Leave blank to use the item's base unit.",
    )
    conversion_factor = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=1,
        help_text="Factor to convert BOM quantity to inventory base unit. "
        "e.g., if BOM says 250g and item is tracked in kg, factor = 0.001 (250g × 0.001 = 0.25kg).",
    )

    class Meta:
        verbose_name = "BOM item"
        verbose_name_plural = "BOM items"
        ordering = ["bom", "inventory_item"]
        unique_together = [["bom", "inventory_item"]]

    def __str__(self):
        return f"{self.bom.name}: {self.inventory_item.name} x {self.quantity}"


class StockCycleCount(models.Model):
    """
    Cycle count record for an inventory item at a branch or warehouse.

    Matches spec: (inventory_item, branch/warehouse, scheduled_date, actual_date,
    counted_quantity, variance, status).
    """

    STATUS_SCHEDULED = "scheduled"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="cycle_counts",
    )
    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cycle_counts",
    )
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cycle_counts",
    )
    scheduled_date = models.DateField()
    actual_date = models.DateField(null=True, blank=True)
    counted_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    variance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Counted quantity - system quantity at time of count.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
    )
    counted_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cycle_counts_performed",
        help_text="User who performed this count.",
    )

    class Meta:
        verbose_name = "Stock cycle count"
        verbose_name_plural = "Stock cycle counts"
        ordering = ["-scheduled_date"]

    def __str__(self):
        return f"{self.inventory_item} on {self.scheduled_date} ({self.status})"


class StockAdjustment(models.Model):
    """
    Manual stock adjustment for an inventory item.

    Matches spec: (inventory_item, branch/warehouse, adjustment_type, quantity,
    reason, user, timestamp).
    """

    ADJUST_INCREASE = "increase"
    ADJUST_DECREASE = "decrease"
    ADJUST_CORRECTION = "correction"
    ADJUSTMENT_CHOICES = [
        (ADJUST_INCREASE, "Increase"),
        (ADJUST_DECREASE, "Decrease"),
        (ADJUST_CORRECTION, "Correction"),
    ]

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )
    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stock_adjustments",
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_CHOICES,
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    user = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock adjustment"
        verbose_name_plural = "Stock adjustments"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.inventory_item} {self.adjustment_type} {self.quantity} by {self.user}"
