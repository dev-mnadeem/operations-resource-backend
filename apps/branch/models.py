from django.db import models


class Branch(models.Model):
    branch_code = models.CharField(
        primary_key=True,
        max_length=10,
        unique=True,
    )
    name = models.CharField(max_length=255, blank=True)
    address = models.TextField()
    phone = models.CharField(max_length=15, blank=True)

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"

    def __str__(self):
        return (
            f"{self.name} ({self.branch_code or self.pk})"
            if self.name
            else f"Branch #{self.branch_code or self.pk}"
        )
