from django.db import models


class SalesTransaction(models.Model):
    """
    Read-only reference to a POS sale for comparison with inventory.
    """

    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        related_name="sales_transactions",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sales_transactions",
    )
    quantity_sold = models.PositiveIntegerField(null=False, default=0)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    occurred_at = models.DateTimeField()

    class Meta:
        verbose_name = "Sales transaction"
        verbose_name_plural = "Sales transactions"
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.branch_id} ({self.id})"

    def save(self, *args, **kwargs):
        if self.product and (self.unit_price is None or self.unit_price == 0):
            self.unit_price = self.product.price
        self.total_amount = self.quantity_sold * self.unit_price
        super().save(*args, **kwargs)


class InventoryConsumption(models.Model):
    """
    Record of inventory consumed by a sale (for reporting).
    """

    inventory_item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="consumptions",
    )
    sales_transaction = models.ForeignKey(
        SalesTransaction,
        on_delete=models.CASCADE,
        related_name="consumptions",
    )
    quantity_consumed = models.DecimalField(max_digits=14, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inventory consumption"
        verbose_name_plural = "Inventory consumptions"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.inventory_item} -{self.quantity_consumed} for {self.sales_transaction}"
