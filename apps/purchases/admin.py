from django.contrib import admin, messages
from django.db.models import Q
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.admin_mixins import RowActionButtonsMixin
from apps.demands.models import Demand
from apps.inventory.models import StockCycleCount
from apps.permissions import is_admin, is_branch_manager, is_purchaser
from apps.transfers.models import Transfer
from apps.warehouse.models import WarehouseRequest

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    Notification,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceiptImage,
    ReceivedItemImage,
    Vendor,
)


@admin.register(Vendor)
class VendorAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "contact_person",
        "email",
        "phone",
        "payment_terms",
        "is_active",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("is_active",)
    search_fields = ("name", "contact_person", "email")

    def has_add_permission(self, request):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0
    # raw_id_fields = ("inventory_item",)
    fields = ("inventory_item", "quantity", "unit_price", "line_total_display")
    readonly_fields = ("line_total_display",)

    def line_total_display(self, obj):
        if obj.pk:
            return obj.line_total
        return "—"

    line_total_display.short_description = "Line total"


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "vendor",
        "demand",
        "status",
        "expected_delivery_date",
        "created_by",
        "created_at",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "vendor", "created_at")
    search_fields = ("vendor__name", "demand__id", "created_by__username")
    # raw_id_fields = ("demand", "vendor", "created_by")
    readonly_fields = ("created_by", "created_at")
    inlines = [PurchaseOrderItemInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "vendor",
                    "demand",
                    "status",
                    "expected_delivery_date",
                    "image_field",
                    "notes",
                )
            },
        ),
        ("Audit", {"fields": ("created_by", "created_at"), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("vendor", "demand", "created_by")
        )
        if is_admin(request.user) or is_purchaser(request.user):
            return qs
        if request.user.has_perm("purchases.view_purchaseorder") and is_branch_manager(
            request.user
        ):
            if request.user.branch_id:
                return qs.filter(demand__branch_id=request.user.branch_id)
            return qs.none()
        return qs.none()

    def has_add_permission(self, request):
        return (
            is_admin(request.user)
            or is_purchaser(request.user)
            or super().has_add_permission(request)
        )

    def has_change_permission(self, request, obj=None):
        return (
            is_admin(request.user)
            or is_purchaser(request.user)
            or super().has_change_permission(request, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return is_admin(request.user) or super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        return (
            is_admin(request.user)
            or is_purchaser(request.user)
            or super().has_view_permission(request, obj)
        )


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0
    # raw_id_fields = ("inventory_item",)
    readonly_fields = ("variance",)


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "demand",
        "receiver",
        "received_at",
        "status",
        "total_received_quantity",
        "receive_action",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "receiver", "received_at")
    search_fields = ("demand__id", "receiver__username")
    # raw_id_fields = ("demand", "receiver")
    readonly_fields = ("total_received_quantity",)
    inlines = [GoodsReceiptItemInline]

    def receive_action(self, obj):
        from django.utils.html import format_html

        if obj.status == GoodsReceipt.STATUS_COMPLETED:
            return "—"
        url = reverse("admin:purchases_goodsreceipt_receive", args=[obj.pk])
        return format_html(
            '<a class="btn btn-xs btn-primary" href="{}">'
            '<i class="fas fa-barcode"></i> Receive</a>',
            url,
        )

    receive_action.short_description = "Receive"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/receive/",
                self.admin_site.admin_view(self.receive_view),
                name="purchases_goodsreceipt_receive",
            ),
        ]
        return custom + urls

    def receive_view(self, request, pk):
        """Custom barcode-assisted receiving view for a GoodsReceipt."""
        from decimal import Decimal, InvalidOperation

        qs = self.get_queryset(request).prefetch_related(
            "items__inventory_item__unit",
        )
        receipt = qs.filter(pk=pk).first()
        if not receipt:
            messages.error(request, "Goods receipt not found or permission denied.")
            return redirect(reverse("admin:purchases_goodsreceipt_changelist"))

        if receipt.status == GoodsReceipt.STATUS_COMPLETED:
            messages.warning(request, "This goods receipt is already completed.")
            return redirect(reverse("admin:purchases_goodsreceipt_change", args=[pk]))

        # Build items with barcode data
        receipt_items = list(receipt.items.select_related("inventory_item__unit"))
        for ri in receipt_items:
            ri.barcode = ri.inventory_item.barcode or ""
            ri.sku = ri.inventory_item.sku or ""

        if request.method == "POST":
            errors = []
            updates = []
            for ri in receipt_items:
                raw = (request.POST.get(f"received_{ri.pk}") or "").strip()
                if not raw:
                    continue
                try:
                    qty = Decimal(raw)
                    if qty < 0:
                        errors.append(
                            f"{ri.inventory_item.name}: quantity cannot be negative."
                        )
                        continue
                    updates.append((ri, qty))
                except InvalidOperation:
                    errors.append(f"{ri.inventory_item.name}: invalid quantity.")

            if errors:
                for msg in errors:
                    messages.error(request, msg)
            elif not updates:
                messages.error(request, "Please enter at least one received quantity.")
            else:
                for ri, qty in updates:
                    ri.received_quantity = qty
                    ri.save(update_fields=["received_quantity"])

                all_received = all(
                    ri.received_quantity >= ri.expected_quantity
                    for ri in receipt.items.all()
                )
                receipt.status = (
                    GoodsReceipt.STATUS_COMPLETED
                    if all_received
                    else GoodsReceipt.STATUS_PARTIAL
                )
                receipt.save(update_fields=["status"])
                messages.success(
                    request,
                    f"Goods receipt #{pk} updated ({receipt.get_status_display()}).",
                )
                return redirect(
                    reverse("admin:purchases_goodsreceipt_change", args=[pk])
                )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": f"Receive Goods — Receipt #{pk}",
                "receipt": receipt,
                "receipt_items": receipt_items,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request,
            "admin/purchases/goodsreceipt/receive.html",
            context,
        )

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("demand", "receiver", "demand__branch")
        )
        if is_admin(request.user) or is_branch_manager(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(demand__branch_id=request.user.branch_id)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if obj.status in (GoodsReceipt.STATUS_COMPLETED, GoodsReceipt.STATUS_PARTIAL):
            has_receipt_img = (
                obj.demand.purchase_receipt_images.exists() if obj.pk else False
            )
            has_item_img = (
                ReceivedItemImage.objects.filter(
                    goods_receipt_item__goods_receipt=obj
                ).exists()
                if obj.pk
                else False
            )
            if not has_receipt_img and not has_item_img:
                self.message_user(
                    request,
                    "Cannot mark as completed/partial without attaching at least one receipt image or item image. "
                    "Please upload a receipt image first.",
                    level="error",
                )
                # Revert to pending so the record is not saved as completed/partial
                obj.status = GoodsReceipt.STATUS_PENDING
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Branch Managers, Purchasers, and Admins can record goods receipts
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_change_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if obj and is_branch_manager(request.user):
            return obj.receiver_id == request.user.id
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user):
            return True
        if is_branch_manager(request.user):
            if obj and request.user.branch_id and obj.demand_id:
                return obj.demand.branch_id == request.user.branch_id
            return True
        return False


@admin.register(PurchaseReceiptImage)
class PurchaseReceiptImageAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("demand", "uploaded_at", "row_actions")
    list_display_links = None
    # raw_id_fields = ("demand",)

    def has_add_permission(self, request):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)


@admin.register(ReceivedItemImage)
class ReceivedItemImageAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("goods_receipt_item", "uploaded_at", "row_actions")
    list_display_links = None
    # raw_id_fields = ("goods_receipt_item",)

    def has_add_permission(self, request):
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    change_list_template = "admin/purchases/notification/change_list.html"
    list_display = (
        "actor_username",
        "type",
        "created_at",
        "view_list",
        "clear_notification",
    )
    list_display_links = None
    list_filter = ("type", "created_at")
    search_fields = ("user__username", "message")
    # raw_id_fields = ("user",)
    ordering = ("-created_at",)
    actions = None

    @staticmethod
    def _relation_map(related_object_id):
        return {
            "Demand": (
                Demand,
                reverse("admin:demands_demand_items", args=[related_object_id]),
            ),
            "PurchaseOrder": (
                PurchaseOrder,
                reverse(
                    "admin:purchases_purchaseorder_change",
                    args=[related_object_id],
                ),
            ),
            "GoodsReceipt": (
                GoodsReceipt,
                reverse(
                    "admin:purchases_goodsreceipt_change", args=[related_object_id]
                ),
            ),
            "StockCycleCount": (
                StockCycleCount,
                reverse(
                    "admin:inventory_stockcyclecount_change",
                    args=[related_object_id],
                ),
            ),
            "WarehouseRequest": (
                WarehouseRequest,
                reverse(
                    "admin:warehouse_warehouserequest_change",
                    args=[related_object_id],
                ),
            ),
            "Transfer": (
                Transfer,
                reverse("admin:transfers_transfer_change", args=[related_object_id]),
            ),
        }

    def view_list(self, obj):
        if not obj.related_object_type or not obj.related_object_id:
            return "N/A"

        mapped = self._relation_map(obj.related_object_id).get(obj.related_object_type)
        if not mapped:
            return "N/A"
        model, url = mapped

        request = getattr(self, "_changelist_request", None)
        if request is None:
            return "N/A"

        model_admin = self.admin_site._registry.get(model)
        if model_admin is None:
            return "N/A"

        target_obj = (
            model_admin.get_queryset(request).filter(pk=obj.related_object_id).first()
        )
        if not target_obj or not model_admin.has_view_permission(request, target_obj):
            return "N/A"

        return format_html(
            '<a class="btn btn-xs btn-secondary" href="{}">'
            '<i class="fas fa-list-ul"></i> View list</a>',
            url,
        )

    view_list.short_description = "View list"

    def clear_notification(self, obj):
        request = getattr(self, "_changelist_request", None)
        if request is None:
            return "N/A"

        if not is_admin(request.user) and obj.user_id != request.user.id:
            return ""

        csrf_token = get_token(request)
        url = reverse("admin:purchases_notification_clear", args=[obj.pk])
        return format_html(
            '<button type="button" class="btn btn-xs btn-danger" onclick="'
            "if(confirm('Are you sure you want to clear this notification?'))"
            "{{var f=document.createElement('form');"
            "f.method='post';f.action='{}';"
            "var c=document.createElement('input');"
            "c.type='hidden';c.name='csrfmiddlewaretoken';c.value='{}';"
            "f.appendChild(c);document.body.appendChild(f);f.submit();}}"
            '"><i class="fas fa-trash"></i> Clear</button>',
            url,
            csrf_token,
        )

    clear_notification.short_description = "Clear Notification"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/clear/",
                self.admin_site.admin_view(self.clear_notification_view),
                name="purchases_notification_clear",
            ),
            path(
                "clear-all/",
                self.admin_site.admin_view(self.clear_all_view),
                name="purchases_notification_clear_all",
            ),
        ]
        return custom + urls

    def clear_notification_view(self, request, pk):
        if request.method != "POST":
            return redirect(reverse("admin:purchases_notification_changelist"))

        obj = self.get_queryset(request).filter(pk=pk).first()
        if not obj:
            messages.error(
                request,
                "Notification not found or you do not have permission to clear it.",
            )
            return redirect(reverse("admin:purchases_notification_changelist"))
        if not is_admin(request.user) and obj.user_id != request.user.id:
            messages.error(request, "You can only clear your own notifications.")
            return redirect(reverse("admin:purchases_notification_changelist"))

        obj.delete()
        messages.success(request, "Notification cleared.")
        return redirect(reverse("admin:purchases_notification_changelist"))

    def clear_all_view(self, request):
        if request.method != "POST":
            return redirect(reverse("admin:purchases_notification_changelist"))

        deleted_count, _ = Notification.objects.filter(user=request.user).delete()
        messages.success(request, f"Cleared {deleted_count} notification(s).")
        return redirect(reverse("admin:purchases_notification_changelist"))

    def changelist_view(self, request, extra_context=None):
        self._changelist_request = request
        extra_context = extra_context or {}
        extra_context["clear_all_url"] = reverse(
            "admin:purchases_notification_clear_all"
        )
        extra_context["clear_all_csrf"] = get_token(request)
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user")
        qs = qs.filter(user=request.user)
        if is_admin(request.user):
            return qs.exclude(
                Q(related_object_type="Demand")
                & ~Q(
                    type__in=[
                        "demand_approved",
                        "demand_rejected",
                        "demand_completed",
                    ]
                )
            )
        return qs

    def has_add_permission(self, request):
        # Notifications are usually system-generated; restrict manual creation
        return is_admin(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    @admin.display(description="User")
    def actor_username(self, obj):
        if obj.related_object_type == "Demand" and obj.related_object_id:
            from apps.demands.models import Demand

            demand = (
                Demand.objects.filter(pk=obj.related_object_id)
                .select_related("submitted_by", "approved_by")
                .only("id", "submitted_by__username", "approved_by__username")
                .first()
            )
            if demand:
                if obj.type == "demand_submitted" and demand.submitted_by:
                    return demand.submitted_by.username
                if (
                    obj.type in {"demand_approved", "demand_rejected"}
                    and demand.approved_by
                ):
                    return demand.approved_by.username

        elif obj.related_object_type == "PurchaseOrder" and obj.related_object_id:
            po = (
                PurchaseOrder.objects.filter(pk=obj.related_object_id)
                .select_related("created_by")
                .only("id", "created_by__username")
                .first()
            )
            if po and po.created_by:
                return po.created_by.username

        elif obj.related_object_type == "GoodsReceipt" and obj.related_object_id:
            gr = (
                GoodsReceipt.objects.filter(pk=obj.related_object_id)
                .select_related("receiver")
                .only("id", "receiver__username")
                .first()
            )
            if gr and gr.receiver:
                return gr.receiver.username

        elif obj.related_object_type == "WarehouseRequest" and obj.related_object_id:
            wr = (
                WarehouseRequest.objects.filter(pk=obj.related_object_id)
                .select_related("requested_by")
                .only("id", "requested_by__username")
                .first()
            )
            if wr and wr.requested_by:
                return wr.requested_by.username

        return obj.user.username
