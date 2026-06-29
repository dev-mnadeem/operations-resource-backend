import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_email_notifications(users, subject, message):
    """Send plain-text email notifications to users with email addresses."""
    recipients = []
    for user in users:
        email = (getattr(user, "email", "") or "").strip()
        if email:
            recipients.append(email)

    if not recipients:
        return 0

    sent = 0
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    for email in sorted(set(recipients)):
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            sent += 1
        except Exception:
            logger.exception("Failed sending demand notification email to %s", email)

    return sent
