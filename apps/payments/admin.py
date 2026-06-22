from django.contrib import admin
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from apps.admin_mixins import RowActionButtonsMixin
from apps.permissions import is_admin, is_purchaser

from .models import Payment, PaymentDocument, VendorInvoice


@admin.register(PaymentDocument)
class PaymentDocumentAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = ("document_type", "uploaded_by", "uploaded_at", "row_actions")
    list_display_links = None
    list_filter = ("document_type", "uploaded_at")
    search_fields = ("uploaded_by__username", "notes")
    raw_id_fields = ("uploaded_by",)
    readonly_fields = ("uploaded_at",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    raw_id_fields = ("purchase_order", "document", "recorded_by")
    readonly_fields = ("created_at",)
    fields = (
        "amount",
        "payment_date",
        "purchase_order",
        "document",
        "recorded_by",
        "notes",
    )


@admin.register(VendorInvoice)
class VendorInvoiceAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "vendor",
        "amount",
        "amount_paid_display",
        "outstanding_display",
        "status",
        "due_date",
        "received_at",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "vendor", "due_date")
    search_fields = ("invoice_number", "vendor__name")
    raw_id_fields = ("vendor", "purchase_order")
    readonly_fields = ("received_at",)
    inlines = [PaymentInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("vendor", "purchase_order")
            .prefetch_related("payments")
        )

    def amount_paid_display(self, obj):
        paid = obj.payments.aggregate(total=Sum("amount"))["total"] or 0
        return paid

    amount_paid_display.short_description = "Paid"

    def outstanding_display(self, obj):
        paid = obj.payments.aggregate(total=Sum("amount"))["total"] or 0
        outstanding = obj.amount - paid
        if outstanding > 0:
            return format_html(
                '<span style="color:#dc3545;font-weight:bold;">{}</span>', outstanding
            )
        return format_html('<span style="color:#28a745;">{}</span>', 0)

    outstanding_display.short_description = "Outstanding"

    def has_add_permission(self, request):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)


@admin.register(Payment)
class PaymentAdmin(RowActionButtonsMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "vendor_invoice",
        "purchase_order",
        "amount",
        "payment_date",
        "recorded_by",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("payment_date",)
    search_fields = ("vendor_invoice__invoice_number", "recorded_by__username")
    raw_id_fields = ("purchase_order", "vendor_invoice", "document", "recorded_by")
    readonly_fields = ("created_at",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "reconciliation/",
                self.admin_site.admin_view(self.reconciliation_view),
                name="payments_payment_reconciliation",
            ),
        ]
        return custom + urls

    def reconciliation_view(self, request):
        """Outstanding invoices vs payments reconciliation (Admin-only)."""
        if not is_admin(request.user):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Admin only.")

        invoices = (
            VendorInvoice.objects.select_related("vendor", "purchase_order")
            .prefetch_related("payments")
            .order_by("vendor__name", "-received_at")
        )

        rows = []
        for inv in invoices:
            paid = inv.payments.aggregate(total=Sum("amount"))["total"] or 0
            outstanding = inv.amount - paid
            rows.append(
                {
                    "invoice": inv,
                    "paid": paid,
                    "outstanding": outstanding,
                    "overdue": inv.due_date and outstanding > 0,
                }
            )

        total_invoiced = sum(r["invoice"].amount for r in rows)
        total_paid = sum(r["paid"] for r in rows)
        total_outstanding = sum(r["outstanding"] for r in rows)

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Payment Reconciliation",
                "rows": rows,
                "total_invoiced": total_invoiced,
                "total_paid": total_paid,
                "total_outstanding": total_outstanding,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request, "admin/payments/payment/reconciliation.html", context
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)
        # Update invoice status based on total payments
        if obj.vendor_invoice_id:
            inv = obj.vendor_invoice
            paid = inv.payments.aggregate(total=Sum("amount"))["total"] or 0
            if paid >= inv.amount:
                inv.status = VendorInvoice.STATUS_PAID
            elif paid > 0:
                inv.status = VendorInvoice.STATUS_PARTIAL
            else:
                inv.status = VendorInvoice.STATUS_UNPAID
            inv.save(update_fields=["status"])

    def has_add_permission(self, request):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_change_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user) or is_purchaser(request.user)
