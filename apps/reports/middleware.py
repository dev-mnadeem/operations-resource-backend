"""
Middleware for automatic audit logging.
"""


class AuditLogMiddleware:
    """
    Middleware to automatically create audit logs for admin actions.

    This middleware captures create/update/delete actions in Django Admin
    and creates AuditLog entries.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # This middleware doesn't intercept requests, it's used via signals
        # Actual audit logging is handled by model signals
        response = self.get_response(request)
        return response
