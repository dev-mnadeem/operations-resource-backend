from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchases"

    def ready(self):
        """Import signals when app is ready."""
        import apps.purchases.signals  # noqa
