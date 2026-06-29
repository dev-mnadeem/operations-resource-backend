from django.contrib import admin

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import is_admin

from .models import InventoryConsumption, SalesTransaction


@admin.register(SalesTransaction)
class SalesTransactionAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "branch",
        "product",
        "quantity_sold",
        "occurred_at",
        "total_amount",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("branch", "occurred_at")
    search_fields = ("branch__branch_code", "product")
    readonly_fields = ("unit_price", "total_amount")

    def get_exclude(self, request, obj=None):
        if obj is None:  # Adding a new object
            return ("unit_price", "total_amount")
        return super().get_exclude(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("branch", "product")
        if is_admin(request.user):
            return qs
        return qs.none()

    def has_view_permission(self, request, obj=None):  # noqa: ARG002
        return is_admin(request.user)

    def has_add_permission(self, request):
        """Only Admins can add sales (imported from Gmail sheets via Celery)."""
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)


@admin.register(InventoryConsumption)
class InventoryConsumptionAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "inventory_item",
        "sales_transaction",
        "quantity_consumed",
        "timestamp",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("timestamp",)
    search_fields = (
        "inventory_item__name",
        "inventory_item__barcode",
        "sales_transaction__branch__branch_code",
    )

    # raw_id_fields = ("inventory_item", "sales_transaction")
    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related(
                "inventory_item",
                "sales_transaction",
                "sales_transaction__branch",
            )
        )
        if is_admin(request.user):
            return qs
        return qs.none()

    def has_view_permission(self, request, obj=None):  # noqa: ARG002
        return is_admin(request.user)

    def has_add_permission(self, request):
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)
