"""
Signals for automatic audit logging.
"""

import logging

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AuditLog

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LogEntry)
def log_admin_action(instance, created, **_kwargs):
    """
    Log all admin actions (create, update, delete) to the custom AuditLog.
    """
    if not created:
        return

    if instance.action_flag == ADDITION:
        action_type = AuditLog.ACTION_CREATE
    elif instance.action_flag == CHANGE:
        action_type = AuditLog.ACTION_UPDATE
    elif instance.action_flag == DELETION:
        action_type = AuditLog.ACTION_DELETE
    else:
        return

    try:
        model_class = instance.content_type.model_class()
        model_name = (
            model_class._meta.label if model_class else instance.content_type.model
        )
    except Exception:
        model_name = "Unknown"

    try:
        AuditLog.objects.create(
            user=instance.user,
            action_type=action_type,
            model_name=model_name,
            object_id=str(instance.object_id),
            object_repr=instance.object_repr,
            changes=instance.change_message,
        )
    except Exception as e:
        logger.error(
            f"Audit log failed for admin action on {instance.object_repr}: {e}"
        )
