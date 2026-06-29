import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import admin
from django.db.models import Sum
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.permissions import (
    is_admin,
    is_branch_manager,
    is_purchaser,
    is_warehouse_manager,
)

from .models import AuditLog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_dates(request):
    """Return (date_from, date_to) from GET params, defaulting to last 30 days."""
    today = date.today()
    try:
        date_from = date.fromisoformat(request.GET.get("date_from", ""))
    except (ValueError, TypeError):
        date_from = today - timedelta(days=30)
    try:
        date_to = date.fromisoformat(request.GET.get("date_to", ""))
    except (ValueError, TypeError):
        date_to = today
    return date_from, date_to


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


# ---------------------------------------------------------------------------
# AuditLog admin
# ---------------------------------------------------------------------------


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    change_list_template = "admin/reports/auditlog/change_list.html"
    list_display = (
        "timestamp",
        "user",
        "action_type",
        "model_name",
        "object_id",
        "object_repr",
    )
    list_display_links = list_display
    list_filter = (
        "action_type",
        "model_name",
        "timestamp",
    )
    search_fields = (
        "user__username",
        "model_name",
        "object_repr",
        "notes",
    )
    raw_id_fields = ("user",)
    readonly_fields = (
        "user",
        "action_type",
        "model_name",
        "object_id",
        "object_repr",
        "changes",
        "ip_address",
        "user_agent",
        "timestamp",
        "notes",
    )
    fieldsets = (
        (
            "Action Details",
            {"fields": ("user", "action_type", "timestamp")},
        ),
        (
            "Object Details",
            {"fields": ("model_name", "object_id", "object_repr")},
        ),
        (
            "Change Details",
            {"fields": ("changes",), "classes": ("collapse",)},
        ),
        (
            "Request Details",
            {"fields": ("ip_address", "user_agent"), "classes": ("collapse",)},
        ),
        ("Notes", {"fields": ("notes",)}),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["report_links"] = [
            {
                "name": "Sales vs Consumption",
                "url": reverse("admin:reports_sales_vs_consumption"),
            },
            {"name": "Item Usage", "url": reverse("admin:reports_item_usage")},
            {
                "name": "Demand vs Received",
                "url": reverse("admin:reports_demand_vs_received"),
            },
            {
                "name": "Warehouse Stock",
                "url": reverse("admin:reports_warehouse_stock"),
            },
            {
                "name": "Branch Inventory",
                "url": reverse("admin:reports_branch_inventory"),
            },
            {
                "name": "Demand vs Actual Usage",
                "url": reverse("admin:reports_demand_vs_usage"),
            },
        ]
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user")
        if is_admin(request.user):
            return qs
        return qs.none()

    def has_add_permission(self, _request):
        return False

    def has_change_permission(self, _request, _obj=None):
        return False

    def has_delete_permission(self, request, _obj=None):
        return is_admin(request.user)

    def has_view_permission(self, request, _obj=None):
        return is_admin(request.user)

    # ------------------------------------------------------------------
    # Extra report URLs attached to the AuditLogAdmin
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "reports/sales-vs-consumption/",
                self.admin_site.admin_view(self.report_sales_vs_consumption),
                name="reports_sales_vs_consumption",
            ),
            path(
                "reports/item-usage/",
                self.admin_site.admin_view(self.report_item_usage),
                name="reports_item_usage",
            ),
            path(
                "reports/demand-vs-received/",
                self.admin_site.admin_view(self.report_demand_vs_received),
                name="reports_demand_vs_received",
            ),
            path(
                "reports/warehouse-stock/",
                self.admin_site.admin_view(self.report_warehouse_stock),
                name="reports_warehouse_stock",
            ),
            path(
                "reports/branch-inventory/",
                self.admin_site.admin_view(self.report_branch_inventory),
                name="reports_branch_inventory",
            ),
            path(
                "reports/demand-vs-usage/",
                self.admin_site.admin_view(self.report_demand_vs_usage),
                name="reports_demand_vs_usage",
            ),
        ]
        return custom + urls

    # ------------------------------------------------------------------
    # 1. Sales vs Inventory Consumption  (Admin-only)
    # ------------------------------------------------------------------

    def report_sales_vs_consumption(self, request):
        if not is_admin(request.user):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Admin only.")

        from apps.sales.models import InventoryConsumption, SalesTransaction

        date_from, date_to = _default_dates(request)

        sales = (
            SalesTransaction.objects.filter(
                occurred_at__date__gte=date_from, occurred_at__date__lte=date_to
            )
            .values("product__name", "branch__name")
            .annotate(
                units_sold=Sum("quantity_sold"),
                revenue=Sum("total_amount"),
            )
            .order_by("product__name", "branch__name")
        )

        consumption = (
            InventoryConsumption.objects.filter(
                sales_transaction__occurred_at__date__gte=date_from,
                sales_transaction__occurred_at__date__lte=date_to,
            )
            .values("inventory_item__name", "sales_transaction__branch__name")
            .annotate(total_consumed=Sum("quantity_consumed"))
            .order_by("inventory_item__name")
        )

        if request.GET.get("export") == "csv":
            rows = [
                [s["branch__name"], s["product__name"], s["units_sold"], s["revenue"]]
                for s in sales
            ]
            return _csv_response(
                "sales_vs_consumption.csv",
                ["Branch", "Product", "Units Sold", "Revenue"],
                rows,
            )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Sales vs Inventory Consumption",
                "sales": list(sales),
                "consumption": list(consumption),
                "date_from": date_from,
                "date_to": date_to,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request, "admin/reports/sales_vs_consumption.html", context
        )

    # ------------------------------------------------------------------
    # 2. Item Usage Report  (Admin-only)
    # ------------------------------------------------------------------

    def report_item_usage(self, request):
        if not is_admin(request.user):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Admin only.")

        from apps.sales.models import InventoryConsumption

        date_from, date_to = _default_dates(request)

        rows = (
            InventoryConsumption.objects.filter(
                sales_transaction__occurred_at__date__gte=date_from,
                sales_transaction__occurred_at__date__lte=date_to,
            )
            .values(
                "inventory_item__name",
                "inventory_item__unit__abbreviation",
                "sales_transaction__branch__name",
            )
            .annotate(total_consumed=Sum("quantity_consumed"))
            .order_by("inventory_item__name", "sales_transaction__branch__name")
        )

        if request.GET.get("export") == "csv":
            return _csv_response(
                "item_usage.csv",
                ["Item", "Unit", "Branch", "Total Consumed"],
                [
                    [
                        r["inventory_item__name"],
                        r["inventory_item__unit__abbreviation"],
                        r["sales_transaction__branch__name"],
                        r["total_consumed"],
                    ]
                    for r in rows
                ],
            )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Item Usage Report",
                "rows": list(rows),
                "date_from": date_from,
                "date_to": date_to,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(request, "admin/reports/item_usage.html", context)

    # ------------------------------------------------------------------
    # 3. Demand vs Received  (Admin, Branch Manager own branch, Purchaser)
    # ------------------------------------------------------------------

    def report_demand_vs_received(self, request):
        user = request.user
        can_view = is_admin(user) or is_branch_manager(user) or is_purchaser(user)
        if not can_view:
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Not authorised.")

        from apps.demands.models import Demand
        from apps.purchases.models import GoodsReceiptItem

        date_from, date_to = _default_dates(request)

        demand_qs = Demand.objects.filter(
            submitted_at__date__gte=date_from,
            submitted_at__date__lte=date_to,
            status=Demand.STATUS_APPROVED,
        ).prefetch_related("items__inventory_item", "goods_receipts__items")

        if is_branch_manager(user) and user.branch_id:
            demand_qs = demand_qs.filter(branch_id=user.branch_id)

        rows = []
        for demand in demand_qs.select_related("branch"):
            for di in demand.items.all():
                approved_qty = (
                    di.approved_quantity
                    if di.approved_quantity is not None
                    else di.quantity
                )
                received_qty = GoodsReceiptItem.objects.filter(
                    goods_receipt__demand=demand,
                    inventory_item=di.inventory_item,
                ).aggregate(total=Sum("received_quantity"))["total"] or Decimal("0")
                rows.append(
                    {
                        "branch": demand.branch.name,
                        "demand_id": demand.pk,
                        "item": di.inventory_item.name,
                        "requested": di.quantity,
                        "approved": approved_qty,
                        "received": received_qty,
                        "variance": received_qty - approved_qty,
                    }
                )

        if request.GET.get("export") == "csv":
            return _csv_response(
                "demand_vs_received.csv",
                [
                    "Branch",
                    "Demand #",
                    "Item",
                    "Requested",
                    "Approved",
                    "Received",
                    "Variance",
                ],
                [
                    [
                        r["branch"],
                        r["demand_id"],
                        r["item"],
                        r["requested"],
                        r["approved"],
                        r["received"],
                        r["variance"],
                    ]
                    for r in rows
                ],
            )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Demand vs Received Report",
                "rows": rows,
                "date_from": date_from,
                "date_to": date_to,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(
            request, "admin/reports/demand_vs_received.html", context
        )

    # ------------------------------------------------------------------
    # 4. Warehouse Stock Levels  (Admin, Warehouse Manager own warehouse)
    # ------------------------------------------------------------------

    def report_warehouse_stock(self, request):
        user = request.user
        if not (is_admin(user) or is_warehouse_manager(user)):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Not authorised.")

        from apps.warehouse.models import WarehouseInventory

        qs = WarehouseInventory.objects.select_related(
            "warehouse", "inventory_item__unit"
        ).order_by("warehouse__name", "inventory_item__name")

        if is_warehouse_manager(user) and user.warehouse_id:
            qs = qs.filter(warehouse_id=user.warehouse_id)

        warehouse_filter = request.GET.get("warehouse", "")
        if warehouse_filter and is_admin(user):
            qs = qs.filter(warehouse_id=warehouse_filter)

        if request.GET.get("export") == "csv":
            return _csv_response(
                "warehouse_stock.csv",
                [
                    "Warehouse",
                    "Item",
                    "Unit",
                    "Quantity",
                    "Min Threshold",
                    "Location",
                    "Low Stock",
                ],
                [
                    [
                        wi.warehouse.name,
                        wi.inventory_item.name,
                        wi.inventory_item.unit.abbreviation
                        if wi.inventory_item.unit
                        else "",
                        wi.quantity,
                        wi.minimum_threshold,
                        wi.location,
                        "YES"
                        if wi.minimum_threshold > 0
                        and wi.quantity < wi.minimum_threshold
                        else "",
                    ]
                    for wi in qs
                ],
            )

        from apps.warehouse.models import Warehouse

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Warehouse Stock Levels",
                "rows": list(qs),
                "warehouses": list(Warehouse.objects.all()) if is_admin(user) else [],
                "selected_warehouse": warehouse_filter,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(request, "admin/reports/warehouse_stock.html", context)

    # ------------------------------------------------------------------
    # 5. Branch Inventory Status  (Admin, Branch Manager own branch)
    # ------------------------------------------------------------------

    def report_branch_inventory(self, request):
        user = request.user
        if not (is_admin(user) or is_branch_manager(user)):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Not authorised.")

        from apps.inventory.models import BranchInventory

        qs = BranchInventory.objects.select_related("branch", "item__unit").order_by(
            "branch__name", "item__name"
        )

        if is_branch_manager(user) and user.branch_id:
            qs = qs.filter(branch_id=user.branch_id)

        branch_filter = request.GET.get("branch", "")
        if branch_filter and is_admin(user):
            qs = qs.filter(branch__branch_code=branch_filter)

        if request.GET.get("export") == "csv":
            return _csv_response(
                "branch_inventory.csv",
                ["Branch", "Item", "Unit", "Quantity", "Min Threshold", "Low Stock"],
                [
                    [
                        bi.branch.name,
                        bi.item.name,
                        bi.item.unit.abbreviation if bi.item.unit else "",
                        bi.quantity,
                        bi.minimum_threshold,
                        "YES"
                        if bi.minimum_threshold > 0
                        and bi.quantity < bi.minimum_threshold
                        else "",
                    ]
                    for bi in qs
                ],
            )

        from apps.branch.models import Branch

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Branch Inventory Status",
                "rows": list(qs),
                "branches": list(Branch.objects.all()) if is_admin(user) else [],
                "selected_branch": branch_filter,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(request, "admin/reports/branch_inventory.html", context)

    # ------------------------------------------------------------------
    # 6. Demand vs Actual Usage  (Admin, Branch Manager, Purchaser)
    # ------------------------------------------------------------------

    def report_demand_vs_usage(self, request):
        user = request.user
        can_view = is_admin(user) or is_branch_manager(user) or is_purchaser(user)
        if not can_view:
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden("Not authorised.")

        from django.db.models.functions import Coalesce

        from apps.demands.models import Demand, DemandItem
        from apps.sales.models import InventoryConsumption

        date_from, date_to = _default_dates(request)

        # 1. Aggregate Demand Data (Only Approved Demands)
        demand_qs = DemandItem.objects.filter(
            demand__submitted_at__date__gte=date_from,
            demand__submitted_at__date__lte=date_to,
            demand__status=Demand.STATUS_APPROVED,
        )
        if is_branch_manager(user) and user.branch_id:
            demand_qs = demand_qs.filter(demand__branch_id=user.branch_id)

        demand_data = demand_qs.values(
            "demand__branch__name", "inventory_item__name", "inventory_item_id"
        ).annotate(
            total_requested=Sum("quantity"),
            total_approved=Sum(Coalesce("approved_quantity", "quantity")),
        )

        # 2. Aggregate Consumption Data
        consumption_qs = InventoryConsumption.objects.filter(
            sales_transaction__occurred_at__date__gte=date_from,
            sales_transaction__occurred_at__date__lte=date_to,
        )
        if is_branch_manager(user) and user.branch_id:
            consumption_qs = consumption_qs.filter(
                sales_transaction__branch_id=user.branch_id
            )

        consumption_data = consumption_qs.values(
            "sales_transaction__branch__name", "inventory_item_id"
        ).annotate(total_consumed=Sum("quantity_consumed"))

        # 3. Merge Data in Python
        # Key: (branch_name, inventory_item_id)
        merged = {}

        for d in demand_data:
            key = (d["demand__branch__name"], d["inventory_item_id"])
            merged[key] = {
                "branch": d["demand__branch__name"],
                "item": d["inventory_item__name"],
                "requested": d["total_requested"],
                "approved": d["total_approved"],
                "consumed": 0,
            }

        # Optimization: Pre-fetch item names for items that have consumption but no demand
        consumption_item_ids = {c["inventory_item_id"] for c in consumption_data}
        existing_item_ids = {d["inventory_item_id"] for d in demand_data}
        missing_item_ids = consumption_item_ids - existing_item_ids

        missing_item_names = {}
        if missing_item_ids:
            from apps.inventory.models import InventoryItem

            missing_item_names = dict(
                InventoryItem.objects.filter(id__in=missing_item_ids).values_list(
                    "id", "name"
                )
            )

        for c in consumption_data:
            branch_name = c["sales_transaction__branch__name"]
            item_id = c["inventory_item_id"]
            key = (branch_name, item_id)

            if key in merged:
                merged[key]["consumed"] = c["total_consumed"]
            else:
                # If there's consumption but no demand in this period
                merged[key] = {
                    "branch": branch_name,
                    "item": missing_item_names.get(item_id, f"Item #{item_id}"),
                    "requested": 0,
                    "approved": 0,
                    "consumed": c["total_consumed"],
                }

        # Calculate variance
        rows = []
        for _, val in merged.items():
            val["variance"] = float(val["approved"] or 0) - float(val["consumed"] or 0)
            rows.append(val)

        rows.sort(key=lambda x: (x["branch"], x["item"]))

        if request.GET.get("export") == "csv":
            return _csv_response(
                "demand_vs_usage.csv",
                ["Branch", "Item", "Requested", "Approved", "Consumed", "Variance"],
                [
                    [
                        r["branch"],
                        r["item"],
                        r["requested"],
                        r["approved"],
                        r["consumed"],
                        r["variance"],
                    ]
                    for r in rows
                ],
            )

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Demand vs Actual Usage",
                "rows": rows,
                "date_from": date_from,
                "date_to": date_to,
                "opts": self.model._meta,
            }
        )
        return TemplateResponse(request, "admin/reports/demand_vs_usage.html", context)
