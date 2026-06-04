from django.db import models


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Product category"
        verbose_name_plural = "Product categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    product_code = models.PositiveIntegerField(
        primary_key=True, null=False, blank=False
    )
    name = models.CharField(max_length=255, null=False, blank=False)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
    )
    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.product_code})"
