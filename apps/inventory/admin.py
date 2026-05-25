import base64
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO

import barcode
from barcode.writer import SVGWriter
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.admin_mixins import EditRowActionButtonMixin, RowActionButtonsMixin
from apps.branch.models import Branch
from apps.permissions import is_admin

from .forms import InventoryItemForm
from .models import (
    BOM,
    BOMItem,
    BranchInventory,
    InventoryCategory,
    InventoryItem,
    StockAdjustment,
    StockCycleCount,
    UnitOfMeasure,
)


class ParentCategoryFilter(admin.SimpleListFilter):
    title = "section"
    parameter_name = "section"

    def lookups(self, _request, _model_admin):
        parents = InventoryCategory.objects.filter(parent_category__isnull=True)
        return [(p.id, p.name) for p in parents]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(section_id=self.value())
        return queryset


class ItemSectionFilter(admin.SimpleListFilter):
    title = "item section"
    parameter_name = "item__section"

    def lookups(self, _request, _model_admin):
        parents = InventoryCategory.objects.filter(parent_category__isnull=True)
        return [(p.id, p.name) for p in parents]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(item__section_id=self.value())
        return queryset


class CategoryFilter(admin.SimpleListFilter):
    title = "category"
    parameter_name = "category"

    def lookups(self, _request, _model_admin):
        sub_categories = InventoryCategory.objects.exclude(parent_category__isnull=True)
        return [(c.id, c.name) for c in sub_categories]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset


class ItemCategoryFilter(admin.SimpleListFilter):
    title = "item category"
    parameter_name = "item__category"

    def lookups(self, _request, _model_admin):
        sub_categories = InventoryCategory.objects.exclude(parent_category__isnull=True)
        return [(c.id, c.name) for c in sub_categories]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(item__category_id=self.value())
        return queryset


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("name", "parent_category", "get_subcategories", "row_actions")
    list_display_links = None
    search_fields = ("name", "parent_category__name")
    list_per_page = 20
    list_filter = (ParentCategoryFilter,)

    def get_subcategories(self, obj):
        return ", ".join([sub.name for sub in obj.subcategories.all()])

    get_subcategories.short_description = "Subcategories"

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)


class BOMItemInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            item = form.cleaned_data.get("inventory_item")
            if item and item.id in seen:
                raise ValidationError("Duplicate component in BOM.")
            if item:
                seen.add(item.id)


class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 0
    formset = BOMItemInlineFormSet


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("name", "abbreviation", "row_actions")
    list_display_links = None
    search_fields = ("name", "abbreviation")
    list_per_page = 20

    def has_add_permission(self, request):
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)


@admin.register(InventoryItem)
class InventoryItemAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    form = InventoryItemForm
    list_display = (
        "name",
        "barcode",
        "sku",
        "section",
        "category",
        "unit",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("unit", ParentCategoryFilter, CategoryFilter)
    search_fields = ("name", "barcode", "sku", "section__name", "category__name")
    list_per_page = 20
    actions = ["print_barcodes"]

    class Media:
        js = ("js/inventory_admin.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "barcode-lookup/",
                self.admin_site.admin_view(self.barcode_lookup_view),
                name="inventory_inventoryitem_barcode_lookup",
            ),
        ]
        return custom + urls

    def barcode_lookup_view(self, request):
        """Admin barcode scan → redirect to that item's change page."""
        from django.http import JsonResponse

        barcode = request.GET.get("barcode", "").strip()
        if not barcode:
            return JsonResponse({"found": False, "error": "No barcode provided."})
        try:
            item = InventoryItem.objects.get(barcode=barcode)
            change_url = reverse("admin:inventory_inventoryitem_change", args=[item.pk])
            return JsonResponse(
                {"found": True, "redirect": change_url, "name": item.name}
            )
        except InventoryItem.DoesNotExist:
            return JsonResponse(
                {"found": False, "error": f"No item found for barcode: {barcode}"}
            )

    @admin.action(description="Print barcode labels for selected items")
    def print_barcodes(self, request, queryset):
        items = list(queryset.select_related("unit", "section", "category"))
        labels = [self._build_barcode_label_data(item) for item in items]
        context = self.admin_site.each_context(request)
        context["labels"] = labels
        context["opts"] = self.model._meta
        return TemplateResponse(
            request,
            "admin/inventory/inventoryitem/print_barcodes.html",
            context,
        )

    def _build_barcode_label_data(self, item):
        barcode_value = (item.barcode or item.sku or "").strip()
        return {
            "item": item,
            "barcode_value": barcode_value,
            "barcode_svg_data_uri": (
                self._generate_code128_svg_data_uri(barcode_value)
                if barcode_value
                else None
            ),
        }

    def _generate_code128_svg_data_uri(self, value):
        output = BytesIO()
        try:
            barcode.Code128(value, writer=SVGWriter()).write(
                output,
                options={
                    "module_width": 0.2,
                    "module_height": 12.0,
                    "font_size": 0,
                    "quiet_zone": 1.5,
                    "text_distance": 1.0,
                    "write_text": False,
                },
            )
        except Exception:
            return None
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("unit", "section", "category")
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(
                branch_inventories__branch_id=request.user.branch_id
            ).distinct()
        if getattr(request.user, "warehouse_id", None):
            return qs.filter(
                warehouse_inventories__warehouse_id=request.user.warehouse_id
            ).distinct()
        return qs.none()

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        return super().has_view_permission(request, obj)


@admin.register(BranchInventory)
class BranchInventoryAdmin(EditRowActionButtonMixin, admin.ModelAdmin):
    list_display = (
        "item",
        "branch",
        "quantity",
        "minimum_threshold",
        "tracking_frequency",
        "row_actions",
    )
    list_display_links = None
    list_filter = (
        "tracking_frequency",
        "branch",
        ItemSectionFilter,
        ItemCategoryFilter,
    )
    list_editable = ("quantity", "minimum_threshold", "tracking_frequency")
    search_fields = (
        "item__name",
        "item__barcode",
        "item__sku",
        "branch__branch_code",
        "branch__name",
    )
    readonly_fields = ("item", "branch")
    # raw_id_fields = ("item", "branch")
    list_per_page = 20

    class Media:
        js = ("js/inventory_admin.js",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch" and not is_admin(request.user):
            kwargs["queryset"] = Branch.objects.filter(pk=request.user.branch_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, _request, obj=None):
        # Keep item/branch immutable on edit, but allow setting them on create.
        if obj is None:
            return ()
        return self.readonly_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("item", "branch")
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(branch_id=request.user.branch_id)
        return qs.none()

    def has_add_permission(self, request):
        return is_admin(request.user) or request.user.branch_id is not None

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and request.user.branch_id:
            return obj.branch_id == request.user.branch_id
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if is_admin(request.user):
            return True
        if obj and request.user.branch_id:
            return obj.branch_id == request.user.branch_id
        return request.user.branch_id is not None


@admin.register(BOM)
class BOMAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("name", "product", "row_actions")
    list_display_links = None
    search_fields = ("name", "product__name")
    # raw_id_fields = ("product",)
    inlines = [BOMItemInline]
    list_per_page = 20

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("product")
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(product__branch_id=request.user.branch_id)
        return qs.none()

    def has_add_permission(self, request):
        return super().has_add_permission(request) and (
            is_admin(request.user) or bool(request.user.branch_id)
        )

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        return bool(
            obj
            and obj.product_id
            and request.user.branch_id
            and obj.product.branch_id == request.user.branch_id
        )

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if is_admin(request.user):
            return True
        if (
            obj
            and obj.product_id
            and request.user.branch_id
            and obj.product.branch_id == request.user.branch_id
        ):
            return True
        return bool(request.user.branch_id)


@admin.register(StockCycleCount)
class StockCycleCountAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "branch",
        "warehouse",
        "scheduled_date",
        "actual_date",
        "counted_quantity",
        "variance",
        "status",
        "counted_by",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "scheduled_date", "actual_date", "branch", "warehouse")
    actions = ["update_branch_inventory_items"]

    class Media:
        css = {"all": ("css/admin_filters.css",)}

    search_fields = ("inventory_item__name", "inventory_item__barcode")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "create-from-inventory/",
                self.admin_site.admin_view(self.create_from_inventory),
                name="inventory_stockcyclecount_add_custom",
            ),
        ]
        return custom + urls

    def add_view(self, request, _form_url="", _extra_context=None):
        return self.create_from_inventory(request)

    @admin.action(description="Set branch inventory to counted quantity")
    def update_branch_inventory_items(self, request, queryset):
        updated = 0
        skipped = 0

        for count in queryset.select_related("inventory_item", "branch"):
            if not count.branch or count.counted_quantity is None:
                skipped += 1
                continue

            branch_inventory, _ = BranchInventory.objects.get_or_create(
                branch=count.branch,
                item=count.inventory_item,
            )
            branch_inventory.quantity = count.counted_quantity
            branch_inventory.save(update_fields=["quantity"])
            updated += 1

        if updated:
            self.message_user(
                request,
                f"{updated} branch inventory item(s) updated successfully.",
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"{skipped} cycle count(s) skipped (missing branch or counted quantity).",
                messages.WARNING,
            )

    def create_from_inventory(self, request):
        user = request.user
        if not self.has_add_permission(request):
            messages.error(
                request, "You do not have permission to create cycle counts."
            )
            return self.changelist_view(request)

        user_has_branch = bool(getattr(user, "branch_id", None))
        show_branch_choice = not user_has_branch and is_admin(user)
        selected_branch_code = None

        qs = (
            InventoryItem.objects.all()
            .select_related("unit", "section", "category")
            .order_by("section__name", "category__name", "name")
        )

        target_branch = None
        if user_has_branch:
            target_branch = Branch.objects.filter(pk=user.branch_id).first()
            if target_branch:
                qs = qs.filter(branch_inventories__branch=target_branch).distinct()
        elif show_branch_choice:
            selected_branch_code = request.GET.get("count_branch", "").strip()
            if selected_branch_code:
                try:
                    target_branch = Branch.objects.get(branch_code=selected_branch_code)
                    qs = qs.filter(branch_inventories__branch=target_branch).distinct()
                except Branch.DoesNotExist:
                    target_branch = None
                    selected_branch_code = None
                    qs = qs.none()
            else:
                qs = qs.none()
        elif not user.is_superuser and getattr(user, "warehouse_id", None):
            qs = qs.none()

        all_items = list(qs)
        system_quantities = {}

        if target_branch and all_items:
            from apps.inventory.models import BranchInventory

            branch_inventories = {
                bi.item_id: bi
                for bi in BranchInventory.objects.filter(branch=target_branch)
            }
            for item in all_items:
                bi = branch_inventories.get(item.id)
                item.current_stock = bi.quantity if bi else Decimal("0")
                system_quantities[item.id] = item.current_stock
        else:
            for item in all_items:
                item.current_stock = Decimal("0")
                system_quantities[item.id] = Decimal("0")

        grouped = defaultdict(lambda: defaultdict(list))
        for item in all_items:
            cat_name = item.section.name if item.section else "Uncategorized"
            sub_name = item.category.name if item.category else "—"
            grouped[cat_name][sub_name].append(item)

        grouped_items = []
        for cat_name in sorted(grouped.keys()):
            subcats = grouped[cat_name]
            grouped_items.append(
                {
                    "category": cat_name,
                    "subcategories": [
                        {"name": sub_name, "items": subcats[sub_name]}
                        for sub_name in sorted(subcats.keys())
                    ],
                }
            )

        if request.method == "POST":
            selected_items = []
            errors = []

            for item in all_items:
                raw_qty = (request.POST.get(f"qty_{item.id}") or "").strip()
                if not raw_qty:
                    continue
                try:
                    qty = Decimal(raw_qty)
                except InvalidOperation:
                    errors.append(f"Invalid counted quantity for {item.name}.")
                    continue
                if qty < 0:
                    errors.append(
                        f"Counted quantity for {item.name} cannot be negative."
                    )
                    continue
                selected_items.append((item, qty))

            if not selected_items:
                messages.error(
                    request, "Please enter a counted quantity for at least one item."
                )
            elif errors:
                for msg in errors:
                    messages.error(request, msg)
            else:
                branch = getattr(user, "branch", None)
                if not branch and is_admin(user):
                    branch_code = request.POST.get("count_branch", "").strip()
                    if branch_code:
                        try:
                            branch = Branch.objects.get(branch_code=branch_code)
                        except Branch.DoesNotExist:
                            branch = None
                    if not branch:
                        messages.error(
                            request, "Please select a branch for these counts."
                        )

                if branch:
                    today = timezone.localdate()
                    count = 0
                    for item, qty in selected_items:
                        variance = qty - system_quantities[item.id]
                        StockCycleCount.objects.create(
                            inventory_item=item,
                            branch=branch,
                            scheduled_date=today,
                            actual_date=today,
                            counted_quantity=qty,
                            variance=variance,
                            status=StockCycleCount.STATUS_COMPLETED,
                            counted_by=user,
                        )
                        count += 1
                    messages.success(
                        request,
                        f"Successfully created {count} cycle count records.",
                    )
                    return redirect(
                        reverse("admin:inventory_stockcyclecount_changelist")
                    )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Create cycle counts from inventory",
                "grouped_items": grouped_items,
                "opts": self.model._meta,
                "has_add_permission": self.has_add_permission(request),
                "show_branch_choice": show_branch_choice,
                "selected_branch_code": selected_branch_code,
                "branches": list(Branch.objects.all().order_by("branch_code"))
                if show_branch_choice
                else [],
            }
        )
        return TemplateResponse(
            request,
            "admin/inventory/stockcyclecount/create_from_inventory.html",
            context,
        )

    # raw_id_fields = ("inventory_item", "branch", "warehouse")

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("inventory_item", "branch", "warehouse")
        )
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(branch_id=request.user.branch_id)
        if request.user.warehouse_id:
            return qs.filter(warehouse_id=request.user.warehouse_id)
        return qs.none()

    def has_add_permission(self, request):
        return super().has_add_permission(request) and (
            is_admin(request.user)
            or request.user.branch_id
            or request.user.warehouse_id
        )

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return True
            if (
                request.user.warehouse_id
                and obj.warehouse_id == request.user.warehouse_id
            ):
                return True
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return True
            if (
                request.user.warehouse_id
                and obj.warehouse_id == request.user.warehouse_id
            ):
                return True
        return bool(request.user.branch_id or request.user.warehouse_id)


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "branch",
        "warehouse",
        "adjustment_type",
        "quantity",
        "user",
        "timestamp",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("timestamp",)

    search_fields = (
        "inventory_item__name",
        "inventory_item__barcode",
        "user__username",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "create-from-inventory/",
                self.admin_site.admin_view(self.create_from_inventory),
                name="inventory_stockadjustment_add_custom",
            ),
        ]
        return custom + urls

    def add_view(self, request, _form_url="", _extra_context=None):
        return self.create_from_inventory(request)

    def create_from_inventory(self, request):
        user = request.user
        if not self.has_add_permission(request):
            messages.error(
                request, "You do not have permission to create stock adjustments."
            )
            return self.changelist_view(request)

        from apps.warehouse.models import Warehouse, WarehouseInventory

        user_has_branch = bool(getattr(user, "branch_id", None))
        user_has_warehouse = bool(getattr(user, "warehouse_id", None))
        show_branch_choice = (
            not user_has_branch and not user_has_warehouse and is_admin(user)
        )
        selected_branch_code = None
        target_warehouse = None

        qs = (
            InventoryItem.objects.all()
            .select_related("unit", "section", "category")
            .order_by("section__name", "category__name", "name")
        )

        target_branch = None
        if user_has_branch:
            target_branch = Branch.objects.filter(pk=user.branch_id).first()
            if target_branch:
                qs = qs.filter(branch_inventories__branch=target_branch).distinct()
        elif user_has_warehouse:
            target_warehouse = Warehouse.objects.filter(pk=user.warehouse_id).first()
            if target_warehouse:
                qs = qs.filter(
                    warehouse_inventories__warehouse=target_warehouse
                ).distinct()
            else:
                qs = qs.none()
        elif show_branch_choice:
            selected_branch_code = request.GET.get("adj_branch", "").strip()
            if selected_branch_code:
                try:
                    target_branch = Branch.objects.get(branch_code=selected_branch_code)
                    qs = qs.filter(branch_inventories__branch=target_branch).distinct()
                except Branch.DoesNotExist:
                    target_branch = None
                    selected_branch_code = None
                    qs = qs.none()
            else:
                qs = qs.none()

        all_items = list(qs)

        if target_branch and all_items:
            branch_inventories = {
                bi.item_id: bi
                for bi in BranchInventory.objects.filter(branch=target_branch)
            }
            for item in all_items:
                bi = branch_inventories.get(item.id)
                item.current_stock = bi.quantity if bi else Decimal("0")
        elif target_warehouse and all_items:
            wh_inventories = {
                wi.inventory_item_id: wi
                for wi in WarehouseInventory.objects.filter(warehouse=target_warehouse)
            }
            for item in all_items:
                wi = wh_inventories.get(item.id)
                item.current_stock = wi.quantity if wi else Decimal("0")
        else:
            for item in all_items:
                item.current_stock = Decimal("0")

        grouped = defaultdict(lambda: defaultdict(list))
        for item in all_items:
            cat_name = item.section.name if item.section else "Uncategorized"
            sub_name = item.category.name if item.category else "—"
            grouped[cat_name][sub_name].append(item)

        grouped_items = []
        for cat_name in sorted(grouped.keys()):
            subcats = grouped[cat_name]
            grouped_items.append(
                {
                    "category": cat_name,
                    "subcategories": [
                        {"name": sub_name, "items": subcats[sub_name]}
                        for sub_name in sorted(subcats.keys())
                    ],
                }
            )

        if request.method == "POST":
            selected_items = []
            errors = []

            common_reason = request.POST.get("common_reason", "").strip()

            for item in all_items:
                raw_qty = (request.POST.get(f"qty_{item.id}") or "").strip()
                if not raw_qty:
                    continue
                try:
                    qty = Decimal(raw_qty)
                except InvalidOperation:
                    errors.append(f"Invalid quantity for {item.name}.")
                    continue
                if qty <= 0:
                    errors.append(
                        f"Adjustment quantity for {item.name} must be greater than zero."
                    )
                    continue

                adj_type = request.POST.get(f"type_{item.id}")
                if adj_type not in dict(StockAdjustment.ADJUSTMENT_CHOICES):
                    errors.append(f"Invalid adjustment type for {item.name}.")
                    continue

                selected_items.append((item, qty, adj_type))

            if not selected_items:
                messages.error(
                    request, "Please enter a quantity for at least one item."
                )
            elif not common_reason:
                messages.error(
                    request, "Please provide a reason for these adjustments."
                )
            elif errors:
                for msg in errors:
                    messages.error(request, msg)
            else:
                branch = getattr(user, "branch", None)
                warehouse = (
                    getattr(user, "warehouse", None) if user_has_warehouse else None
                )
                if not branch and not warehouse and is_admin(user):
                    branch_code = request.POST.get("adj_branch", "").strip()
                    if branch_code:
                        try:
                            branch = Branch.objects.get(branch_code=branch_code)
                        except Branch.DoesNotExist:
                            branch = None
                    if not branch:
                        messages.error(
                            request, "Please select a branch for these adjustments."
                        )

                if branch or warehouse:
                    count = 0
                    for item, qty, adj_type in selected_items:
                        StockAdjustment.objects.create(
                            inventory_item=item,
                            branch=branch,
                            warehouse=warehouse,
                            adjustment_type=adj_type,
                            quantity=qty,
                            reason=common_reason,
                            user=user,
                        )
                        count += 1
                    messages.success(
                        request,
                        f"Successfully created {count} stock adjustments.",
                    )
                    return redirect(
                        reverse("admin:inventory_stockadjustment_changelist")
                    )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Create stock adjustments from inventory",
                "grouped_items": grouped_items,
                "opts": self.model._meta,
                "has_add_permission": self.has_add_permission(request),
                "show_branch_choice": show_branch_choice,
                "selected_branch_code": selected_branch_code,
                "branches": list(Branch.objects.all().order_by("branch_code"))
                if show_branch_choice
                else [],
                "ADJUST_INCREASE": StockAdjustment.ADJUST_INCREASE,
                "ADJUST_DECREASE": StockAdjustment.ADJUST_DECREASE,
                "ADJUST_CORRECTION": StockAdjustment.ADJUST_CORRECTION,
                "target_warehouse": target_warehouse,
            }
        )
        return TemplateResponse(
            request,
            "admin/inventory/stockadjustment/create_from_inventory.html",
            context,
        )

    # raw_id_fields = ("inventory_item", "branch", "warehouse", "user")

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("inventory_item", "branch", "warehouse", "user")
        )
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(branch_id=request.user.branch_id)
        if request.user.warehouse_id:
            return qs.filter(warehouse_id=request.user.warehouse_id)
        return qs.none()

    def has_add_permission(self, request):
        # Admins or location-bound users can create adjustments
        return super().has_add_permission(request) and (
            is_admin(request.user)
            or request.user.branch_id
            or request.user.warehouse_id
        )

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return True
            if (
                request.user.warehouse_id
                and obj.warehouse_id == request.user.warehouse_id
            ):
                return True
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if not super().has_view_permission(request, obj):
            return False
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id and obj.branch_id == request.user.branch_id:
                return True
            if (
                request.user.warehouse_id
                and obj.warehouse_id == request.user.warehouse_id
            ):
                return True
        return bool(request.user.branch_id or request.user.warehouse_id)
