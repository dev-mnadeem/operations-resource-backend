from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import is_admin
from apps.users.forms import AdminUserChangeForm, AdminUserCreationForm, GroupAdminForm

from .models import User

admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(RowActionButtonsMixin, BaseGroupAdmin):
    form = GroupAdminForm
    list_display = (
        "name",
        "get_all_permissions",
        "permissions_count",
        "users_count",
        "row_actions",
    )
    list_display_links = None

    def get_all_permissions(self, obj):
        perms = list(obj.permissions.all())[:4]
        text = ", ".join([p.name for p in perms])
        if obj.permissions.count() > 4:
            return f"{text}, ... (+{obj.permissions.count() - 4} more)"
        return text

    get_all_permissions.short_description = "Assigned Permissions"

    def permissions_count(self, obj):
        return obj.permissions.count()

    permissions_count.short_description = "Perms"

    def users_count(self, obj):
        return obj.user_set.count()

    users_count.short_description = "Users"


@admin.register(User)
class UserAdmin(RowActionButtonsMixin, BaseUserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm

    add_fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "role_group",
                    "branch",
                    "purchaser_branches",
                    "warehouse",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "branch",
        "warehouse",
        "get_groups",
        "row_actions",
    )
    list_filter = (
        "groups",
        "branch",
        "purchaser_branches",
        "warehouse",
        "is_staff",
        "is_active",
    )
    search_fields = ("username", "email", "first_name", "last_name")
    raw_id_fields = ("branch", "warehouse")
    filter_horizontal = ("user_permissions",)

    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])

    get_groups.short_description = "Groups"

    def role_group(self, obj):
        """Displays the first group for use in fieldsets and read-only views."""
        group = obj.groups.first()
        return group.name if group else "-"

    role_group.short_description = "Role group"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "username",
                    "role_group",
                    "branch",
                    "purchaser_branches",
                    "warehouse",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                )
            },
        ),
    )
    list_display_links = None

    def has_module_permission(self, request):
        """Hide User model from dashboard for non-admins."""
        if is_admin(request.user):
            return True
        return request.user.has_perm("users.can_view_own_profile")

    def get_queryset(self, request):
        """Filter users based on role and permission."""
        qs = super().get_queryset(request)

        if is_admin(request.user):
            return qs
        if request.user.has_perm("users.can_view_own_profile"):
            return qs.filter(pk=request.user.pk)
        return qs.none()

    def has_add_permission(self, request):
        """Only Admins can add users."""
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        """Non-admins cannot change any user."""
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        """Only Admins can delete users."""
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        """Admins can view all, others can view only themselves in lists/popups if they have permission."""
        if is_admin(request.user):
            return True
        if obj:
            return obj.pk == request.user.pk and request.user.has_perm(
                "users.can_view_own_profile"
            )
        return super().has_view_permission(request, obj) or request.user.has_perm(
            "users.can_view_own_profile"
        )

    def get_readonly_fields(self, request, obj=None):
        """Make ALL fields read-only for non-admin users."""
        if not is_admin(request.user):
            # Return all fields for the model to make them read-only
            return [f.name for f in self.model._meta.fields] + [
                "role_group",
                "user_permissions",
            ]
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        """Set is_staff=True for users with role groups so they can log in to admin."""
        role_group = form.cleaned_data.get("role_group") if form.cleaned_data else None

        # Check if any group is assigned (either from form or existing)
        if role_group is not None:
            has_groups = True
        elif obj.pk:
            has_groups = obj.groups.exists()
        else:
            has_groups = False

        if has_groups:
            obj.is_staff = True
        super().save_model(request, obj, form, change)

    class Media:
        js = ("js/admin_user_role_toggle.js",)
