import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.admin_mixins import DeleteRowActionButtonMixin
from apps.branch.models import Branch
from apps.inventory.models import InventoryItem
from apps.permissions import (
    is_admin,
    is_branch_manager,
    is_purchaser,
    is_warehouse_manager,
)

from .models import Demand, DemandItem
from .services import get_automated_demand_suggestions


class DemandItemInline(admin.TabularInline):
    model = DemandItem
    extra = 0
    raw_id_fields = ("inventory_item", "unit")


@admin.register(Demand)
class DemandAdmin(DeleteRowActionButtonMixin, admin.ModelAdmin):
    change_list_template = "admin/demands/demand/change_list.html"
    list_display = (
        "branch",
        "status_badge",
        "submitted_by",
        "submitted_at",
        "approved_by",
        "approved_at",
        "row_actions",
    )
    list_display_links = None
    list_filter = ("status", "branch", "submitted_by", "approved_by")
    search_fields = ("branch__branch_code",)
    # raw_id_fields = ("branch",)
    readonly_fields = ("submitted_by", "submitted_at", "approved_by", "approved_at")
    inlines = [DemandItemInline]
    actions = ["approve_demands", "reject_demands", "convert_to_purchase_order"]

    def row_actions(self, obj):
        """
        Add a per-row 'View list' (items) and 'Delete' button.
        """
        from django.utils.html import format_html

        items_url = reverse("admin:demands_demand_items", args=[obj.pk])
        delete_url = (
            f"/admin/{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/delete/"
        )
        return format_html(
            '<div style="display: flex; gap: 4px; white-space: nowrap;">'
            '<a class="btn btn-xs btn-secondary" href="{}">'
            '<i class="fas fa-list-ul"></i> View list</a>'
            '<a class="btn btn-xs btn-danger" href="{}">'
            '<i class="fas fa-trash"></i> Delete</a>'
            "</div>",
            items_url,
            delete_url,
        )

    row_actions.short_description = "Actions"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        from django.utils.html import format_html

        css_class = {
            Demand.STATUS_PENDING: "badge-secondary",
            Demand.STATUS_SUBMITTED: "badge-info",
            Demand.STATUS_APPROVED: "badge-success",
            Demand.STATUS_COMPLETED: "badge-primary",
            Demand.STATUS_REJECTED: "badge-danger",
        }.get(obj.status, "badge-light")
        return format_html(
            '<span class="badge {} text-uppercase">{}</span>',
            css_class,
            obj.get_status_display(),
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard_url"] = reverse("admin:demands_demand_dashboard")
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.demand_dashboard),
                name="demands_demand_dashboard",
            ),
            path(
                "items/<int:pk>/",
                self.admin_site.admin_view(self.demand_items_view),
                name="demands_demand_items",
            ),
            path(
                "items/<int:pk>/export/csv/",
                self.admin_site.admin_view(self.demand_items_export_view),
                name="demands_demand_items_export",
            ),
            path(
                "get-suggestions/",
                self.admin_site.admin_view(self.get_suggestions_view),
                name="demands_demand_suggestions",
            ),
        ]
        return custom + urls

    def demand_dashboard(self, request):
        """Status dashboard: demand counts per branch grouped by status."""
        from django.db.models import Count, Q

        user = request.user
        qs = self.get_queryset(request)

        # Aggregate counts per branch for each status in one query
        rows = (
            qs.values("branch__name", "branch__branch_code")
            .annotate(
                total=Count("pk"),
                pending=Count("pk", filter=Q(status=Demand.STATUS_PENDING)),
                submitted=Count("pk", filter=Q(status=Demand.STATUS_SUBMITTED)),
                approved=Count("pk", filter=Q(status=Demand.STATUS_APPROVED)),
                rejected=Count("pk", filter=Q(status=Demand.STATUS_REJECTED)),
            )
            .order_by("branch__name")
        )

        totals = {
            "total": sum(r["total"] for r in rows),
            "pending": sum(r["pending"] for r in rows),
            "submitted": sum(r["submitted"] for r in rows),
            "approved": sum(r["approved"] for r in rows),
            "rejected": sum(r["rejected"] for r in rows),
        }

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Demand Status Dashboard",
                "rows": list(rows),
                "totals": totals,
                "opts": self.model._meta,
                "is_admin": is_admin(user),
            }
        )
        return TemplateResponse(request, "admin/demands/demand/dashboard.html", context)

    def get_suggestions_view(self, request):
        """AJAX endpoint to return suggested quantities for a branch."""
        branch_code = (request.GET.get("branch_code") or "").strip()
        if branch_code.lower() in {"none", "null", "undefined"}:
            branch_code = ""

        if (
            is_branch_manager(request.user)
            and request.user.branch_id
            and not branch_code
        ):
            branch_code = str(request.user.branch_id).strip()

        if not branch_code:
            return JsonResponse({"error": "No branch code provided"}, status=400)

        try:
            branch = Branch.objects.get(branch_code=branch_code)
        except Branch.DoesNotExist:
            return JsonResponse({"error": "Invalid branch code"}, status=404)

        # Security: Branch Manager can only get suggestions for their own branch
        if is_branch_manager(request.user) and request.user.branch_id != branch.pk:
            return JsonResponse({"error": "Access denied"}, status=403)

        suggestions = get_automated_demand_suggestions(branch.pk)
        return JsonResponse(suggestions)

    def add_view(self, request, _form_url="", _extra_context=None):
        """
        Override the default add page to use the
        'create from inventory' flow instead of the standard model form.
        """
        return self.create_from_inventory(request)

    def demand_items_view(self, request, pk):
        """Custom page: show a single demand with all its items; purchasers can approve/reject."""
        qs = self.get_queryset(request).prefetch_related(
            "items__inventory_item__section",
            "items__inventory_item__category",
            "items__unit",
        )
        demand = qs.filter(pk=pk).first()
        if not demand:
            messages.error(request, "You do not have permission to view this demand.")
            return redirect(reverse("admin:demands_demand_changelist"))

        # Handle approve/reject (purchaser or admin/superadmin only, and only when submitted)
        can_approve_reject = demand.status == Demand.STATUS_SUBMITTED and (
            is_purchaser(request.user) or is_admin(request.user)
        )
        can_mark_completed = demand.status == Demand.STATUS_APPROVED and (
            is_warehouse_manager(request.user)
        )

        if request.method == "POST":
            action = request.POST.get("action")
            if action == "approve" and can_approve_reject:
                # Apply per-item approved_quantity if provided
                for di in demand.items.all():
                    raw = (request.POST.get(f"approved_qty_{di.pk}") or "").strip()
                    if raw:
                        try:
                            approved_qty = Decimal(raw)
                            if Decimal("0") < approved_qty <= di.quantity:
                                di.approved_quantity = approved_qty
                                di.save(update_fields=["approved_quantity"])
                        except Exception:
                            pass
                demand.status = Demand.STATUS_APPROVED
                demand.approved_by = request.user
                demand.approved_at = timezone.now()
                demand.rejection_reason = ""
                demand.save()
                messages.success(request, f"Demand #{demand.pk} has been approved.")
                return redirect(reverse("admin:demands_demand_items", args=[demand.pk]))
            if action == "reject" and can_approve_reject:
                rejection_reason = (request.POST.get("rejection_reason") or "").strip()
                demand.status = Demand.STATUS_REJECTED
                demand.approved_by = request.user
                demand.approved_at = timezone.now()
                demand.rejection_reason = rejection_reason
                demand.save()
                messages.success(request, f"Demand #{demand.pk} has been rejected.")
                return redirect(reverse("admin:demands_demand_items", args=[demand.pk]))
            if action == "mark_completed":
                if not can_mark_completed:
                    messages.error(
                        request, "You do not have permission to complete this demand."
                    )
                elif request.POST.get("confirm_completed") != "on":
                    messages.error(
                        request,
                        "Please tick the confirmation checkbox before marking completed.",
                    )
                else:
                    demand.status = Demand.STATUS_COMPLETED
                    demand.save(update_fields=["status"])
                    messages.success(
                        request, f"Demand #{demand.pk} marked as completed."
                    )
                    return redirect(
                        reverse("admin:demands_demand_items", args=[demand.pk])
                    )

        # Group items by category and subcategory for display
        grouped = defaultdict(lambda: defaultdict(list))
        for di in demand.items.all():
            inv = di.inventory_item
            cat_name = inv.section.name if inv.section else "Uncategorized"
            sub_name = inv.category.name if inv.category else "—"
            grouped[cat_name][sub_name].append(di)
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

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": f"Demand #{demand.pk} items",
                "demand": demand,
                "opts": self.model._meta,
                "can_approve_reject": can_approve_reject,
                "can_mark_completed": can_mark_completed,
                "grouped_items": grouped_items,
            },
        )
        return TemplateResponse(
            request,
            "admin/demands/demand/items.html",
            context,
        )

    def demand_items_export_view(self, request, pk):
        qs = self.get_queryset(request).prefetch_related(
            "items__inventory_item__section",
            "items__inventory_item__category",
            "items__unit",
        )
        demand = qs.filter(pk=pk).first()
        if not demand:
            messages.error(request, "You do not have permission to export this demand.")
            return redirect(reverse("admin:demands_demand_changelist"))

        rows = []
        for di in demand.items.all():
            inv = di.inventory_item
            rows.append(
                {
                    "section": inv.section.name if inv.section else "Uncategorized",
                    "category": inv.category.name if inv.category else "—",
                    "item": inv.name,
                    "requested": di.quantity,
                    "approved": (
                        di.approved_quantity
                        if di.approved_quantity is not None
                        else di.quantity
                    ),
                    "unit": di.unit.abbreviation if di.unit else "",
                    "priority": di.get_priority_display(),
                }
            )
        return self._export_demand_items_csv(demand, rows)

    def _export_demand_items_csv(self, demand, rows):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="demand_{demand.pk}_items.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "Demand ID",
                "Branch",
                "Status",
                "Section",
                "Category",
                "Item",
                "Requested Qty",
                "Approved Qty",
                "Unit",
                "Priority",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    demand.pk,
                    demand.branch.name,
                    demand.get_status_display(),
                    row["section"],
                    row["category"],
                    row["item"],
                    row["requested"],
                    row["approved"],
                    row["unit"],
                    row["priority"],
                ]
            )
        return response

    def create_from_inventory(self, request):
        """
        Custom admin view: create a Demand by ticking items and entering quantities.
        - Branch manager: inventory is filtered to their assigned branch.
        - Admin/Superadmin: must select a branch; inventory is shown only for that branch.
        """
        user = request.user
        if not self.has_add_permission(request):
            messages.error(request, "You do not have permission to create demands.")
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
                selected_branch_code = str(target_branch.pk)
                qs = qs.filter(branch_inventories__branch=target_branch).distinct()
        elif show_branch_choice:
            selected_branch_code = request.GET.get("demand_branch", "").strip()
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

        if target_branch and all_items:
            from apps.inventory.models import BranchInventory

            branch_inventories = {
                bi.item_id: bi
                for bi in BranchInventory.objects.filter(branch=target_branch)
            }
            for item in all_items:
                bi = branch_inventories.get(item.id)
                item.current_stock = bi.quantity if bi else Decimal("0")
                item.min_threshold = bi.minimum_threshold if bi else Decimal("0")
        else:
            for item in all_items:
                item.current_stock = Decimal("0")
                item.min_threshold = Decimal("0")

        # Group by category and subcategory (same hierarchy as create_default_inventory).
        grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for item in all_items:
            cat_name = item.section.name if item.section else "Uncategorized"
            sub_name = item.category.name if item.category else "—"
            grouped[cat_name][sub_name].append(item)
        # Build ordered list for template: [{"category": name, "subcategories": [{"name": sub, "items": [...]}]}]
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
        unit_options = sorted(
            {
                (item.unit.abbreviation or "").strip()
                for item in all_items
                if item.unit and (item.unit.abbreviation or "").strip()
            },
            key=str.lower,
        )

        if request.method == "POST":
            selected_items: list[tuple[InventoryItem, Decimal]] = []
            errors = []

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
                        f"Quantity for {item.name} must be greater than zero."
                    )
                    continue
                selected_items.append((item, qty))

            if not selected_items:
                messages.error(
                    request,
                    "Please enter a quantity for at least one item.",
                )
            elif errors:
                for msg in errors:
                    messages.error(request, msg)
            else:
                branch = getattr(user, "branch", None)
                if not branch and is_admin(user):
                    branch_code = request.POST.get("demand_branch", "").strip()
                    if branch_code:
                        try:
                            branch = Branch.objects.get(branch_code=branch_code)
                        except Branch.DoesNotExist:
                            branch = None
                    if not branch:
                        messages.error(
                            request,
                            "Please select a branch for this demand.",
                        )
                elif not branch:
                    messages.error(
                        request,
                        "You must be assigned to a branch to create demands.",
                    )

                if branch:
                    demand = Demand.objects.create(
                        branch=branch,
                        submitted_by=user,
                    )
                    DemandItem.objects.bulk_create(
                        [
                            DemandItem(
                                demand=demand,
                                inventory_item=item,
                                quantity=qty,
                                unit=item.unit,
                            )
                            for item, qty in selected_items
                        ],
                    )
                    messages.success(
                        request,
                        f"Demand #{demand.pk} created successfully.",
                    )
                    return self._redirect_to_change_view(demand)

        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Create demand from inventory",
                "grouped_items": grouped_items,
                "opts": self.model._meta,
                "has_add_permission": self.has_add_permission(request),
                "show_branch_choice": show_branch_choice,
                "selected_branch_code": selected_branch_code,
                "unit_options": unit_options,
                "branches": list(Branch.objects.all().order_by("branch_code"))
                if show_branch_choice
                else [],
            },
        )
        return TemplateResponse(
            request,
            "admin/demands/demand/create_from_inventory.html",
            context,
        )

    def _redirect_to_change_view(self, obj):
        url = reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
            args=[obj.pk],
        )
        return redirect(url)

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related(
                "branch",
                "submitted_by",
                "approved_by",
            )
        )
        if is_admin(request.user) or is_purchaser(request.user):
            return qs
        if request.user.branch_id:
            return qs.filter(branch_id=request.user.branch_id)
        if is_warehouse_manager(request.user):
            return qs.filter(
                status__in=[Demand.STATUS_APPROVED, Demand.STATUS_COMPLETED]
            )
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not change and getattr(obj, "submitted_by_id", None) is None:
            obj.submitted_by = request.user

        if change and "status" in form.changed_data:
            if obj.status in [Demand.STATUS_APPROVED, Demand.STATUS_REJECTED]:
                obj.approved_by = request.user
                obj.approved_at = timezone.now()
            elif obj.status in [Demand.STATUS_PENDING, Demand.STATUS_SUBMITTED]:
                obj.approved_by = None
                obj.approved_at = None

        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Admin, Superadmin, and Branch Manager can create demands
        return is_admin(request.user) or is_branch_manager(request.user)

    def has_change_permission(self, request, obj=None):
        # Admins and Purchasers can change; Branch Managers can edit only their branch's submitted demands
        if is_admin(request.user) or is_purchaser(request.user):
            return True
        if obj and is_branch_manager(request.user) and request.user.branch_id:
            return (
                obj.branch_id == request.user.branch_id
                and obj.status == Demand.STATUS_SUBMITTED
            )
        return False

    def has_delete_permission(self, request, obj=None):
        # Admin, Superadmin, and Purchaser can delete; Branch Manager can delete their branch's demands
        if is_admin(request.user) or is_purchaser(request.user):
            return True
        if obj and is_branch_manager(request.user) and request.user.branch_id:
            return obj.branch_id == request.user.branch_id
        return False

    def has_view_permission(self, request, obj=None):
        if is_admin(request.user) or is_purchaser(request.user):
            return True
        if obj and request.user.branch_id:
            return obj.branch_id == request.user.branch_id
        if is_warehouse_manager(request.user):
            return (
                obj.status in [Demand.STATUS_APPROVED, Demand.STATUS_COMPLETED]
                if obj
                else True
            )
        return request.user.branch_id is not None

    @admin.action(description="Approve selected demands")
    def approve_demands(self, request, queryset):
        if not (is_admin(request.user) or is_purchaser(request.user)):
            self.message_user(request, "You do not have permission to approve demands.")
            return
        now = timezone.now()
        updated = 0
        for demand in queryset.filter(status=Demand.STATUS_SUBMITTED):
            demand.status = Demand.STATUS_APPROVED
            demand.approved_by = request.user
            demand.approved_at = now
            demand.save()
            updated += 1
        self.message_user(request, f"Approved {updated} demand(s).")

    @admin.action(description="Reject selected demands")
    def reject_demands(self, request, queryset):
        if not (is_admin(request.user) or is_purchaser(request.user)):
            self.message_user(request, "You do not have permission to reject demands.")
            return
        now = timezone.now()
        updated = 0
        for demand in queryset.filter(status=Demand.STATUS_SUBMITTED):
            demand.status = Demand.STATUS_REJECTED
            demand.approved_by = request.user
            demand.approved_at = now
            demand.save()
            updated += 1
        self.message_user(request, f"Rejected {updated} demand(s).")

    @admin.action(description="Convert approved demands to Purchase Orders")
    def convert_to_purchase_order(self, request, queryset):
        if not (is_admin(request.user) or is_purchaser(request.user)):
            self.message_user(
                request, "You do not have permission to create purchase orders."
            )
            return
        from apps.purchases.models import PurchaseOrder, PurchaseOrderItem

        created = 0
        for demand in queryset.filter(status=Demand.STATUS_APPROVED):
            if demand.purchase_orders.filter(
                status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_SENT]
            ).exists():
                self.message_user(
                    request,
                    f"Demand #{demand.pk} already has an active PO — skipped.",
                    level="warning",
                )
                continue

            po = PurchaseOrder.objects.create(
                demand=demand,
                status=PurchaseOrder.STATUS_DRAFT,
                created_by=request.user,
            )
            for di in demand.items.select_related("inventory_item"):
                qty = di.approved_quantity if di.approved_quantity else di.quantity
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    inventory_item=di.inventory_item,
                    quantity=qty,
                    unit_price=0,
                )
            created += 1
        self.message_user(
            request,
            f"Created {created} draft Purchase Order(s). Assign vendors before sending.",
        )
