from decimal import Decimal

from django.contrib import admin
from django.db.models import F
from django.utils import timezone

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import (
    is_admin,
    is_branch_manager,
    is_warehouse_manager,
)

from .models import (
    Warehouse,
    WarehouseInventory,
    WarehouseRequest,
    WarehouseRequestItem,
    WarehouseTransaction,
)


@admin.register(Warehouse)
class WarehouseAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    fieldsets = ((None, {"fields": ("name", "address", "phone")}),)

    list_display = ("name", "phone", "address", "row_actions")
    list_display_links = None
    search_fields = ("name", "address")

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if is_admin(request.user):
            return qs
        if request.user.warehouse_id:
            return qs.filter(id=request.user.warehouse_id)
        return qs.none()

    def has_add_permission(self, request):
        """Only Admins can add warehouses."""
        return is_admin(request.user)

    def has_change_permission(self, request, obj=None):
        """Admins can change any warehouse, Warehouse Managers can change their own."""
        if is_admin(request.user):
            return True
        if obj and request.user.warehouse_id:
            return obj.id == request.user.warehouse_id
        return False

    def has_delete_permission(self, request, _obj=None):
        """Only Admins can delete warehouses."""
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        """Admins can view all, Warehouse Managers can view their own."""
        if is_admin(request.user):
            return True
        if obj and request.user.warehouse_id:
            return obj.id == request.user.warehouse_id
        return super().has_view_permission(request, obj)


class WarehouseRequestItemInline(admin.TabularInline):
    model = WarehouseRequestItem
    extra = 0
    raw_id_fields = ("inventory_item",)


class LowStockFilter(admin.SimpleListFilter):
    title = "stock level"
    parameter_name = "stock_level"

    def lookups(self, _request, _model_admin):
        return (("low", "Below minimum"),)

    def queryset(self, _request, queryset):
        if self.value() == "low":
            return queryset.filter(
                minimum_threshold__gt=0,
                quantity__lt=F("minimum_threshold"),
            )
        return queryset


@admin.register(WarehouseInventory)
class WarehouseInventoryAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "warehouse",
        "inventory_item",
        "quantity",
        "location",
        "row_actions",
    )
    list_display_links = None
    list_filter = (
        "warehouse",
        LowStockFilter,
    )
    search_fields = (
        "inventory_item__name",
        "inventory_item__barcode",
        "inventory_item__sku",
        "location",
    )
    raw_id_fields = ("warehouse", "inventory_item")
    fieldsets = (
        (None, {"fields": ("warehouse", "inventory_item")}),
        (
            "Stock Information",
            {"fields": ("quantity", "minimum_threshold", "location")},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("warehouse", "inventory_item")
        if is_admin(request.user):
            return qs
        if request.user.warehouse_id:
            return qs.filter(warehouse_id=request.user.warehouse_id)
        return qs.none()

    def has_add_permission(self, request):
        return is_admin(request.user) or is_warehouse_manager(request.user)

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and request.user.warehouse_id:
            return obj.warehouse_id == request.user.warehouse_id
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and request.user.warehouse_id:
            return obj.warehouse_id == request.user.warehouse_id
        return super().has_view_permission(request, obj)


@admin.register(WarehouseTransaction)
class WarehouseTransactionAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "warehouse",
        "inventory_item",
        "transaction_type",
        "quantity",
        "user",
        "timestamp",
        "row_actions",
    )
    list_display_links = None
    list_filter = (
        "transaction_type",
        "warehouse",
        "timestamp",
    )
    search_fields = (
        "inventory_item__name",
        "inventory_item__barcode",
        "user__username",
        "reference_type",
    )
    raw_id_fields = ("warehouse", "inventory_item", "user")
    readonly_fields = ("timestamp",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "warehouse",
                    "inventory_item",
                    "transaction_type",
                    "quantity",
                )
            },
        ),
        (
            "Reference",
            {"fields": ("reference_type", "reference_id")},
        ),
        (
            "Audit",
            {"fields": ("user", "timestamp")},
        ),
    )

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("warehouse", "inventory_item", "user")
        )
        if is_admin(request.user):
            return qs
        if request.user.warehouse_id:
            return qs.filter(warehouse_id=request.user.warehouse_id)
        return qs.none()

    def has_add_permission(self, request):
        return is_admin(request.user) or is_warehouse_manager(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and request.user.warehouse_id:
            return obj.warehouse_id == request.user.warehouse_id
        return super().has_view_permission(request, obj)


@admin.register(WarehouseRequest)
class WarehouseRequestAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "warehouse",
        "branch",
        "status",
        "requested_by",
        "requested_at",
        "approved_by",
        "approved_at",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "warehouse", "branch", "requested_by", "approved_by")
    search_fields = (
        "warehouse__name",
        "branch__branch_code",
        "branch__name",
    )
    raw_id_fields = ("warehouse", "branch")
    readonly_fields = ("requested_by", "approved_by", "requested_at", "approved_at")
    inlines = [WarehouseRequestItemInline]
    actions = ["approve_requests", "reject_requests"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "warehouse",
                    "branch",
                    "status",
                )
            },
        ),
        (
            "Request Details",
            {"fields": ("requested_by", "requested_at")},
        ),
        (
            "Approval Details",
            {"fields": ("approved_by", "approved_at", "rejection_reason")},
        ),
    )

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("warehouse", "branch", "requested_by", "approved_by")
        )
        if is_admin(request.user) or is_warehouse_manager(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(branch_id=request.user.branch_id)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not change and getattr(obj, "requested_by_id", None) is None:
            obj.requested_by = request.user

        if change and "status" in form.changed_data:
            if obj.status in [
                WarehouseRequest.STATUS_APPROVED,
                WarehouseRequest.STATUS_REJECTED,
            ]:
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
            elif obj.status == WarehouseRequest.STATUS_PENDING:
                obj.approved_by = None
                obj.approved_at = None

        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user) or is_warehouse_manager(request.user):
            return True
        if obj and is_branch_manager(request.user) and request.user.branch_id:
            return (
                obj.branch_id == request.user.branch_id
                and obj.status == WarehouseRequest.STATUS_PENDING
            )
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user) or is_warehouse_manager(request.user):
            return True
        if obj and request.user.branch_id:
            return obj.branch_id == request.user.branch_id
        return super().has_view_permission(request, obj)

    @admin.action(description="Approve selected warehouse requests")
    def approve_requests(self, request, queryset):
        if not (is_admin(request.user) or is_warehouse_manager(request.user)):
            self.message_user(
                request, "You do not have permission to approve warehouse requests."
            )
            return
        from .models import WarehouseInventory, WarehouseTransaction

        pending_requests = (
            queryset.filter(status=WarehouseRequest.STATUS_PENDING)
            .select_related("warehouse")
            .prefetch_related("items__inventory_item")
        )

        approved_count = 0
        for warehouse_request in pending_requests:
            # Preload current stock for all items in this request
            items = list(warehouse_request.items.all())
            item_ids = [item.inventory_item_id for item in items]
            inventory_by_item = {
                wi.inventory_item_id: wi
                for wi in WarehouseInventory.objects.filter(
                    warehouse=warehouse_request.warehouse,
                    inventory_item_id__in=item_ids,
                )
            }

            # Check for shortages before creating any transactions
            shortages = []
            for item in items:
                wi = inventory_by_item.get(item.inventory_item_id)
                current_qty = wi.quantity if wi else Decimal("0")
                if current_qty < item.quantity:
                    shortages.append(
                        f"{item.inventory_item.name} (have {current_qty}, need {item.quantity})"
                    )

            if shortages:
                self.message_user(
                    request,
                    "Cannot approve request "
                    f"{warehouse_request.id} due to insufficient stock: "
                    + "; ".join(shortages),
                    level="error",
                )
                continue

            # Create one OUTWARD transaction per requested item
            # (signal on WarehouseTransaction deducts WarehouseInventory)
            for item in items:
                WarehouseTransaction.objects.create(
                    warehouse=warehouse_request.warehouse,
                    inventory_item=item.inventory_item,
                    transaction_type=WarehouseTransaction.TRANSACTION_OUTWARD,
                    quantity=item.quantity,
                    reference_type="WarehouseRequest",
                    reference_id=warehouse_request.id,
                    user=request.user,
                )

            # Also increment BranchInventory for the requesting branch
            from apps.inventory.models import BranchInventory

            for item in items:
                BranchInventory.objects.filter(
                    branch=warehouse_request.branch,
                    item=item.inventory_item,
                ).update(quantity=F("quantity") + item.quantity)

            warehouse_request.status = WarehouseRequest.STATUS_APPROVED
            warehouse_request.approved_by = request.user
            warehouse_request.approved_at = timezone.now()
            warehouse_request.save(
                update_fields=["status", "approved_by", "approved_at"]
            )
            approved_count += 1

        self.message_user(
            request,
            f"Approved {approved_count} warehouse request(s) and created issue transactions.",
        )

    @admin.action(description="Reject selected warehouse requests")
    def reject_requests(self, request, queryset):
        if not (is_admin(request.user) or is_warehouse_manager(request.user)):
            self.message_user(
                request, "You do not have permission to reject warehouse requests."
            )
            return
        updated = queryset.filter(status=WarehouseRequest.STATUS_PENDING).update(
            status=WarehouseRequest.STATUS_REJECTED,
            approved_by=request.user,
            approved_at=timezone.now(),
        )
        self.message_user(request, f"Rejected {updated} warehouse request(s).")
