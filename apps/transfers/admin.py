from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import models
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import (
    is_admin,
    is_branch_manager,
    is_warehouse_manager,
)

from .models import Transfer, TransferItem


class TransferItemInline(admin.TabularInline):
    model = TransferItem
    extra = 0
    raw_id_fields = ("inventory_item",)
    fields = (
        "inventory_item",
        "quantity",
        "dispatched_quantity",
        "received_quantity",
        "variance",
    )


@admin.register(Transfer)
class TransferAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "from_location_display",
        "to_location_display",
        "transfer_type",
        "status",
        "initiated_by",
        "initiated_at",
        "approved_by",
        "dispatched_at",
        "received_at",
        "dispatch_action_btn",
        "receive_action_btn",
        "row_actions",
    )
    list_display_links = None
    list_filter = (
        "status",
        "transfer_type",
        "initiated_at",
        "approved_at",
        "dispatched_at",
        "received_at",
    )
    search_fields = (
        "from_branch__branch_code",
        "from_branch__name",
        "from_warehouse__name",
        "to_branch__branch_code",
        "to_branch__name",
        "to_warehouse__name",
        "initiated_by__username",
    )
    raw_id_fields = (
        "from_branch",
        "from_warehouse",
        "to_branch",
        "to_warehouse",
    )
    readonly_fields = (
        "initiated_at",
        "approved_at",
        "dispatched_at",
        "received_at",
    )
    inlines = [TransferItemInline]
    actions = [
        "approve_transfers",
        "dispatch_transfers",
        "receive_transfers",
        "cancel_transfers",
    ]
    fieldsets = (
        (
            "Transfer Details",
            {
                "fields": (
                    "from_branch",
                    "from_warehouse",
                    "to_branch",
                    "to_warehouse",
                    "transfer_type",
                    "status",
                    "notes",
                )
            },
        ),
        (
            "Initiation",
            {"fields": ("initiated_by", "initiated_at")},
        ),
        (
            "Approval",
            {"fields": ("approved_by", "approved_at")},
        ),
        (
            "Execution",
            {"fields": ("dispatched_at", "received_at")},
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/dispatch/",
                self.admin_site.admin_view(self.dispatch_view),
                name="transfers_transfer_dispatch",
            ),
            path(
                "<int:pk>/receive/",
                self.admin_site.admin_view(self.receive_view),
                name="transfers_transfer_receive",
            ),
        ]
        return custom + urls

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "initiated_by":
            User = get_user_model()
            if is_admin(request.user):
                kwargs["queryset"] = User.objects.filter(is_active=True).order_by(
                    "username"
                )
            else:
                kwargs["queryset"] = User.objects.filter(pk=request.user.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if not is_admin(request.user):
            initial["initiated_by"] = request.user.pk
        return initial

    def save_model(self, request, obj, form, change):
        if not is_admin(request.user) or (not change and not obj.initiated_by_id):
            obj.initiated_by = request.user
        super().save_model(request, obj, form, change)

    def dispatch_view(self, request, pk):
        """Custom barcode-assisted dispatch view."""
        from decimal import Decimal, InvalidOperation

        transfer = (
            self.get_queryset(request)
            .filter(pk=pk)
            .prefetch_related("items__inventory_item__unit")
            .first()
        )
        if not transfer:
            messages.error(request, "Transfer not found or permission denied.")
            return redirect(reverse("admin:transfers_transfer_changelist"))
        if transfer.status != Transfer.STATUS_APPROVED:
            messages.warning(request, "Only approved transfers can be dispatched.")
            return redirect(reverse("admin:transfers_transfer_change", args=[pk]))

        items = list(transfer.items.select_related("inventory_item__unit"))
        for ti in items:
            ti.barcode = ti.inventory_item.barcode or ""
            ti.sku = ti.inventory_item.sku or ""

        if request.method == "POST":
            errors = []
            updates = []
            for ti in items:
                raw = (request.POST.get(f"dispatched_{ti.pk}") or "").strip()
                if not raw:
                    updates.append((ti, ti.quantity))
                    continue
                try:
                    qty = Decimal(raw)
                    if qty <= 0:
                        errors.append(
                            f"{ti.inventory_item.name}: quantity must be positive."
                        )
                        continue
                    updates.append((ti, qty))
                except InvalidOperation:
                    errors.append(f"{ti.inventory_item.name}: invalid quantity.")

            if errors:
                for msg in errors:
                    messages.error(request, msg)
            else:
                for ti, qty in updates:
                    ti.dispatched_quantity = qty
                    ti.save(update_fields=["dispatched_quantity"])
                transfer.status = Transfer.STATUS_DISPATCHED
                transfer.dispatched_at = timezone.now()
                transfer.save(update_fields=["status", "dispatched_at"])
                messages.success(request, f"Transfer #{pk} marked as dispatched.")
                return redirect(reverse("admin:transfers_transfer_change", args=[pk]))

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": f"Dispatch Transfer #{pk}",
                "transfer": transfer,
                "transfer_items": items,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request, "admin/transfers/transfer/dispatch.html", context
        )

    def receive_view(self, request, pk):
        """Custom barcode-assisted receive view."""
        from decimal import Decimal, InvalidOperation

        transfer = (
            self.get_queryset(request)
            .filter(pk=pk)
            .prefetch_related("items__inventory_item__unit")
            .first()
        )
        if not transfer:
            messages.error(request, "Transfer not found or permission denied.")
            return redirect(reverse("admin:transfers_transfer_changelist"))
        if transfer.status != Transfer.STATUS_DISPATCHED:
            messages.warning(request, "Only dispatched transfers can be received.")
            return redirect(reverse("admin:transfers_transfer_change", args=[pk]))

        items = list(transfer.items.select_related("inventory_item__unit"))
        for ti in items:
            ti.barcode = ti.inventory_item.barcode or ""
            ti.sku = ti.inventory_item.sku or ""

        if request.method == "POST":
            errors = []
            updates = []
            for ti in items:
                raw = (request.POST.get(f"received_{ti.pk}") or "").strip()
                disp = (
                    ti.dispatched_quantity
                    if ti.dispatched_quantity is not None
                    else ti.quantity
                )
                if not raw:
                    updates.append((ti, disp))
                    continue
                try:
                    qty = Decimal(raw)
                    if qty < 0:
                        errors.append(
                            f"{ti.inventory_item.name}: quantity cannot be negative."
                        )
                        continue
                    updates.append((ti, qty))
                except InvalidOperation:
                    errors.append(f"{ti.inventory_item.name}: invalid quantity.")

            if errors:
                for msg in errors:
                    messages.error(request, msg)
            else:
                for ti, qty in updates:
                    disp = (
                        ti.dispatched_quantity
                        if ti.dispatched_quantity is not None
                        else ti.quantity
                    )
                    ti.received_quantity = qty
                    ti.variance = qty - disp
                    ti.save(update_fields=["received_quantity", "variance"])
                transfer.status = Transfer.STATUS_RECEIVED
                transfer.received_at = timezone.now()
                transfer.save(update_fields=["status", "received_at"])
                messages.success(request, f"Transfer #{pk} marked as received.")
                return redirect(reverse("admin:transfers_transfer_change", args=[pk]))

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": f"Receive Transfer #{pk}",
                "transfer": transfer,
                "transfer_items": items,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request, "admin/transfers/transfer/receive.html", context
        )

    def dispatch_action_btn(self, obj):
        from django.utils.html import format_html

        if obj.status != Transfer.STATUS_APPROVED:
            return "—"
        url = reverse("admin:transfers_transfer_dispatch", args=[obj.pk])
        return format_html(
            '<a class="btn btn-xs btn-warning" href="{}"><i class="fas fa-truck"></i> Dispatch</a>',
            url,
        )

    dispatch_action_btn.short_description = "Dispatch"

    def receive_action_btn(self, obj):
        from django.utils.html import format_html

        if obj.status != Transfer.STATUS_DISPATCHED:
            return "—"
        url = reverse("admin:transfers_transfer_receive", args=[obj.pk])
        return format_html(
            '<a class="btn btn-xs btn-success" href="{}"><i class="fas fa-check-circle"></i> Receive</a>',
            url,
        )

    receive_action_btn.short_description = "Receive"

    def from_location_display(self, obj):
        if obj.from_branch:
            return f"Branch: {obj.from_branch.branch_code}"
        if obj.from_warehouse:
            return f"Warehouse: {obj.from_warehouse.name}"
        return "—"

    from_location_display.short_description = "From"

    def to_location_display(self, obj):
        if obj.to_branch:
            return f"Branch: {obj.to_branch.branch_code}"
        if obj.to_warehouse:
            return f"Warehouse: {obj.to_warehouse.name}"
        return "—"

    to_location_display.short_description = "To"

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related(
                "from_branch",
                "from_warehouse",
                "to_branch",
                "to_warehouse",
                "initiated_by",
                "approved_by",
            )
        )
        if is_admin(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(
                models.Q(from_branch_id=request.user.branch_id)
                | models.Q(to_branch_id=request.user.branch_id)
            )
        if request.user.warehouse_id:
            return qs.filter(
                models.Q(from_warehouse_id=request.user.warehouse_id)
                | models.Q(to_warehouse_id=request.user.warehouse_id)
            )
        return qs.none()

    def has_add_permission(self, request):
        return (
            is_admin(request.user)
            or is_branch_manager(request.user)
            or is_warehouse_manager(request.user)
        )

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id:
                return (
                    obj.from_branch_id == request.user.branch_id
                    or obj.to_branch_id == request.user.branch_id
                ) and obj.status in [
                    Transfer.STATUS_PENDING,
                    Transfer.STATUS_APPROVED,
                ]
            if request.user.warehouse_id:
                return (
                    obj.from_warehouse_id == request.user.warehouse_id
                    or obj.to_warehouse_id == request.user.warehouse_id
                ) and obj.status in [
                    Transfer.STATUS_PENDING,
                    Transfer.STATUS_APPROVED,
                ]
        return False

    def has_delete_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and obj.status == Transfer.STATUS_PENDING:
            if request.user.branch_id:
                return obj.from_branch_id == request.user.branch_id
            if request.user.warehouse_id:
                return obj.from_warehouse_id == request.user.warehouse_id
        return False

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj:
            if request.user.branch_id:
                return (
                    obj.from_branch_id == request.user.branch_id
                    or obj.to_branch_id == request.user.branch_id
                )
            if request.user.warehouse_id:
                return (
                    obj.from_warehouse_id == request.user.warehouse_id
                    or obj.to_warehouse_id == request.user.warehouse_id
                )
        return (
            request.user.branch_id is not None or request.user.warehouse_id is not None
        )

    @admin.action(description="Approve selected transfers")
    def approve_transfers(self, request, queryset):
        if not (
            is_admin(request.user)
            or is_branch_manager(request.user)
            or is_warehouse_manager(request.user)
        ):
            self.message_user(
                request, "You do not have permission to approve transfers."
            )
            return
        updated = queryset.filter(status=Transfer.STATUS_PENDING).update(
            status=Transfer.STATUS_APPROVED,
            approved_by=request.user,
            approved_at=timezone.now(),
        )
        self.message_user(request, f"Approved {updated} transfer(s).")

    @admin.action(description="Dispatch selected transfers")
    def dispatch_transfers(self, request, queryset):
        if not (
            is_admin(request.user)
            or is_branch_manager(request.user)
            or is_warehouse_manager(request.user)
        ):
            self.message_user(
                request, "You do not have permission to dispatch transfers."
            )
            return

        from decimal import Decimal

        from apps.inventory.models import BranchInventory  # noqa: TC001
        from apps.warehouse.models import WarehouseInventory  # noqa: TC001

        approved_transfers = (
            queryset.filter(status=Transfer.STATUS_APPROVED)
            .select_related("from_branch", "from_warehouse")
            .prefetch_related("items__inventory_item")
        )

        dispatched_count = 0
        for transfer in approved_transfers:
            items = list(transfer.items.all())

            # Build current stock map for the source location
            shortages = []
            if transfer.from_branch:
                # Branch stock: use BranchInventory
                item_ids = [item.inventory_item_id for item in items]
                branch_inv_map = {
                    bi.item_id: bi
                    for bi in BranchInventory.objects.filter(
                        branch=transfer.from_branch,
                        item_id__in=item_ids,
                    )
                }
                for item in items:
                    bi = branch_inv_map.get(item.inventory_item_id)
                    current_qty = bi.quantity if bi else Decimal("0")
                    dispatch_qty = (
                        item.dispatched_quantity
                        if item.dispatched_quantity is not None
                        else item.quantity
                    )
                    if current_qty < dispatch_qty:
                        shortages.append(
                            f"{item.inventory_item.name} (have {current_qty}, need {dispatch_qty})"
                        )
            elif transfer.from_warehouse:
                # Warehouse stock: WarehouseInventory per item
                item_ids = [item.inventory_item_id for item in items]
                inventory_by_item = {
                    wi.inventory_item_id: wi
                    for wi in WarehouseInventory.objects.filter(
                        warehouse=transfer.from_warehouse,
                        inventory_item_id__in=item_ids,
                    )
                }
                for item in items:
                    wi = inventory_by_item.get(item.inventory_item_id)
                    current_qty = wi.quantity if wi else Decimal("0")
                    dispatch_qty = (
                        item.dispatched_quantity
                        if item.dispatched_quantity is not None
                        else item.quantity
                    )
                    if current_qty < dispatch_qty:
                        shortages.append(
                            f"{item.inventory_item.name} (have {current_qty}, need {dispatch_qty})"
                        )

            if shortages:
                self.message_user(
                    request,
                    "Cannot dispatch transfer "
                    f"{transfer.id} due to insufficient stock: " + "; ".join(shortages),
                    level="error",
                )
                continue

            # At this point we know we have enough stock; default dispatched_quantity where missing
            for item in items:
                if item.dispatched_quantity is None:
                    item.dispatched_quantity = item.quantity
                    item.save(update_fields=["dispatched_quantity"])

            transfer.status = Transfer.STATUS_DISPATCHED
            transfer.dispatched_at = timezone.now()
            transfer.save(update_fields=["status", "dispatched_at"])
            dispatched_count += 1

        self.message_user(
            request,
            f"Dispatched {dispatched_count} transfer(s).",
        )

    @admin.action(description="Mark selected transfers as received")
    def receive_transfers(self, request, queryset):
        if not (
            is_admin(request.user)
            or is_branch_manager(request.user)
            or is_warehouse_manager(request.user)
        ):
            self.message_user(
                request, "You do not have permission to receive transfers."
            )
            return
        from decimal import Decimal

        dispatched_transfers = (
            queryset.filter(status=Transfer.STATUS_DISPATCHED)
            .select_related("to_branch", "to_warehouse")
            .prefetch_related("items__inventory_item")
        )

        received_count = 0
        for transfer in dispatched_transfers:
            items = list(transfer.items.all())
            if not items:
                self.message_user(
                    request,
                    f"Transfer {transfer.id} has no items and was skipped.",
                    level="warning",
                )
                continue

            for item in items:
                dispatched_qty = (
                    item.dispatched_quantity
                    if item.dispatched_quantity is not None
                    else item.quantity
                )
                # Default received_quantity if not provided
                if item.received_quantity is None:
                    item.received_quantity = dispatched_qty

                # Compute variance: received - dispatched
                recv = item.received_quantity or Decimal("0")
                disp = dispatched_qty or Decimal("0")
                item.variance = recv - disp
                item.save(update_fields=["received_quantity", "variance"])

            transfer.status = Transfer.STATUS_RECEIVED
            transfer.received_at = timezone.now()
            transfer.save(update_fields=["status", "received_at"])
            received_count += 1

        self.message_user(
            request,
            f"Marked {received_count} transfer(s) as received.",
        )

    @admin.action(description="Cancel selected transfers")
    def cancel_transfers(self, request, queryset):
        if not (
            is_admin(request.user)
            or is_branch_manager(request.user)
            or is_warehouse_manager(request.user)
        ):
            self.message_user(
                request, "You do not have permission to cancel transfers."
            )
            return
        updated = queryset.filter(
            status__in=[Transfer.STATUS_PENDING, Transfer.STATUS_APPROVED]
        ).update(status=Transfer.STATUS_CANCELLED)
        self.message_user(request, f"Cancelled {updated} transfer(s).")
