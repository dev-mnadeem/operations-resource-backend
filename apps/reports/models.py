from django.db import models


class AuditLog(models.Model):
    """
    System-wide audit log for tracking all important actions.

    Tracks: user, action_type, model_name, object_id, changes, timestamp
    """

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_VIEW = "view"
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_DISPATCH = "dispatch"
    ACTION_RECEIVE = "receive"
    ACTION_CANCEL = "cancel"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_VIEW, "View"),
        (ACTION_APPROVE, "Approve"),
        (ACTION_REJECT, "Reject"),
        (ACTION_DISPATCH, "Dispatch"),
        (ACTION_RECEIVE, "Receive"),
        (ACTION_CANCEL, "Cancel"),
    ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
    )
    model_name = models.CharField(
        max_length=100,
        help_text="Name of the model (e.g., 'PurchaseOrder', 'Demand')",
    )
    object_id = models.CharField(
        max_length=255,
        default="",
        blank=True,
        help_text="ID of the affected object (can be string or integer)",
    )
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="String representation of the object",
    )
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON field storing before/after values for updates",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user",
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text="User agent string",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the action",
    )

    class Meta:
        verbose_name = "Audit log"
        verbose_name_plural = "Audit logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["model_name", "-timestamp"]),
            models.Index(fields=["action_type", "-timestamp"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "System"
        return f"{user_str} {self.action_type} {self.model_name} #{self.object_id} at {self.timestamp}"
