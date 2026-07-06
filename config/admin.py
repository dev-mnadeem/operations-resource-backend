from django.contrib import admin

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import is_admin

from .models import Product


@admin.register(Product)
class ProductAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("item_code", "name", "price", "is_active", "row_actions")
    list_display_links = None
    list_filter = ("is_active",)
    search_fields = ("item_code", "name")

    def get_queryset(self, request):
        return super().get_queryset(request)

    def has_add_permission(self, request):
        """Only Admins can add products."""
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        """Only Admins can edit product records."""
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        """Only Admins can delete product records."""
        return is_admin(request.user)
