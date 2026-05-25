from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True, blank=False)
    phone = models.CharField(max_length=15)

    branch = models.ForeignKey(
        "branch.Branch",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        help_text="Required for all users except Warehouse Manager",
    )
    purchaser_branches = models.ManyToManyField(
        "branch.Branch",
        blank=True,
        related_name="purchaser_users",
        help_text="Branches this purchaser handles notifications/workflows for.",
    )

    warehouse = models.ForeignKey(
        "warehouse.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="Only for Warehouse Manager group",
    )

    class Meta:
        permissions = [
            ("can_view_own_profile", "Can view own profile"),
        ]

    def __str__(self):
        return self.username or f"User #{self.pk}"
