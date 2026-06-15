from django.contrib import admin

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import is_admin, is_purchaser, is_warehouse_manager

from .models import Branch


@admin.register(Branch)
class BranchAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    fieldsets = ((None, {"fields": ("branch_code", "name", "address", "phone")}),)
    list_display = ("branch_code", "name", "address", "phone", "row_actions")
    list_display_links = None
    search_fields = ("branch_code", "name", "address")

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if is_admin(request.user):
            return qs
        if is_warehouse_manager(request.user):
            return qs
        if is_purchaser(request.user):
            branch_ids = set(
                request.user.purchaser_branches.values_list("pk", flat=True)
            )
            if request.user.branch_id:
                branch_ids.add(request.user.branch_id)
            if branch_ids:
                return qs.filter(branch_code__in=branch_ids)
            return qs.none()
        if request.user.branch_id:
            return qs.filter(branch_code=request.user.branch_id)
        return qs.none()

    def get_readonly_fields(self, _request, obj=None):
        """Prevent changing the Primary Key (branch_code) on an existing branch to avoid creating duplicates."""
        if obj:
            return self.readonly_fields + ("branch_code",)
        return self.readonly_fields

    def has_add_permission(self, request):
        """Only Admins can add branches."""
        return is_admin(request.user)

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Admins can change any branch, Branch Managers can change their own branch."""
        if is_admin(request.user):
            return True
        if is_purchaser(request.user):
            if obj is None:
                return self.get_queryset(request).exists()
            return self.get_queryset(request).filter(pk=obj.pk).exists()
        if obj and request.user.branch_id:
            return obj.branch_code == request.user.branch_id
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Only Admins can delete branches."""
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):  # noqa: ARG002
        """Admins can view all, Branch Managers can view their own."""
        if is_admin(request.user):
            return True
        if is_purchaser(request.user):
            if obj is None:
                return self.get_queryset(request).exists()
            return self.get_queryset(request).filter(pk=obj.pk).exists()
        if obj and request.user.branch_id:
            return obj.branch_code == request.user.branch_id
        return super().has_view_permission(request, obj)
