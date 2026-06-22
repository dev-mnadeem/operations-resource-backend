from django.contrib import admin
from django.utils.html import format_html

from apps.admin_mixins import RowActionButtonsMixin
from apps.inventory.models import BOM
from apps.permissions import is_admin, is_branch_manager

from .models import Product, ProductCategory


class BOMInline(admin.StackedInline):
    model = BOM
    extra = 0
    readonly_fields = ("manage_items_link", "display_items")
    fields = ("name", "manage_items_link", "display_items")
    can_delete = False

    def manage_items_link(self, obj):
        if not obj.pk:
            return "Save the product first to manage BOM items."
        url = f"/admin/inventory/bom/{obj.pk}/change/"
        return format_html(
            '<a href="{}" class="btn btn-sm btn-info" target="_blank">'
            '<i class="fas fa-edit"></i> Edit BOM Items in new tab</a>',
            url,
        )

    manage_items_link.short_description = "Management"

    def display_items(self, obj):
        if not obj.pk:
            return ""
        items = obj.items.select_related("inventory_item")
        if not items.exists():
            return "No items in this BOM yet. Click the link above to add some."

        from django.utils.html import format_html, mark_safe

        html = [
            '<table class="table table-sm table-striped" style="width:100%; border-collapse: collapse; margin-top: 10px;">',
            '<thead><tr style="border-bottom: 2px solid #dee2e6;">',
            '<th style="text-align:left; padding: 8px;">Inventory Item</th>',
            '<th style="text-align:left; padding: 8px;">Quantity</th>',
            "</tr></thead>",
            "<tbody>",
        ]

        for item in items:
            html.append(
                format_html(
                    '<tr style="border-bottom: 1px solid #eee;">'
                    '<td style="padding: 8px;">{}</td>'
                    '<td style="padding: 8px;">{}</td>'
                    "</tr>",
                    item.inventory_item.name,
                    item.quantity,
                )
            )

        html.append("</tbody></table>")
        return mark_safe("".join(html))

    display_items.short_description = "Current Components"


@admin.register(ProductCategory)
class ProductCategoryAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("name", "row_actions")
    search_fields = ("name",)
    list_display_links = None


@admin.register(Product)
class ProductAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "product_code",
        "name",
        "category",
        "price",
        "branch",
        "row_actions",
    )
    search_fields = ("name", "product_code", "category__name", "branch__branch_code")
    list_filter = ("category", "branch")
    ordering = ("product_code", "category__name")
    list_display_links = None
    list_per_page = 20
    inlines = [BOMInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("category", "branch")
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            from django.db.models import Q

            return qs.filter(
                Q(branch_id=request.user.branch_id) | Q(branch__isnull=True)
            )
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            db_field.name == "branch"
            and not is_admin(request.user)
            and request.user.branch_id
        ):
            from apps.branch.models import Branch

            kwargs["queryset"] = Branch.objects.filter(
                branch_code=request.user.branch_id
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, _request, obj=None):
        """Prevent changing the Primary Key (product_code) on an existing product."""
        if obj:
            return self.readonly_fields + ("product_code",)
        return self.readonly_fields

    def has_module_permission(self, request):
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_view_permission(self, request, _obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return (
            is_admin(request.user)
            # or is_branch_manager(request.user)
        )

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return is_branch_manager(request.user)
            # Global products exist but don't let branch managers edit them
            if not obj.branch_id:
                return False
        return False

    def has_delete_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return is_branch_manager(request.user)
            return False
        return is_branch_manager(request.user)

    def save_model(self, request, obj, form, change):
        if not change and not obj.branch_id and request.user.branch_id:
            obj.branch_id = request.user.branch_id
        super().save_model(request, obj, form, change)
