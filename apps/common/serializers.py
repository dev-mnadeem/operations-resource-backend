from django.utils import timezone
from rest_framework import serializers

from apps.branch.models import Branch
from apps.inventory.models import BranchInventory, InventoryItem
from apps.permissions import is_purchaser
from apps.warehouse.models import Warehouse


class SnapshotSerializer(serializers.Serializer):
    """
    Serializes reference data tailored specifically to the user's permissions.
    Supports delta sync via `since` param (ISO timestamp).
    """

    server_time = serializers.SerializerMethodField()
    inventory_items = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()
    warehouses = serializers.SerializerMethodField()
    user_context = serializers.SerializerMethodField()

    def get_server_time(self, obj):  # noqa: ARG002
        return timezone.now().isoformat()

    def get_inventory_items(self, obj):  # noqa: ARG002
        user = self.context["request"].user
        since = self.context.get("since")
        if not user.has_perm("inventory.view_inventoryitem"):
            return []

        qs = InventoryItem.objects.select_related("unit", "section", "category").all()
        if since:
            qs = qs.filter(updated_at__gt=since)

        return [
            {
                "id": i.id,
                "name": i.name,
                "barcode": i.barcode,
                "sku": i.sku,
                "category": i.section.name if i.section else None,
                "sub_category": i.category.name if i.category else None,
                "unit": i.unit.abbreviation if i.unit else "",
                "updated_at": i.updated_at.isoformat(),
            }
            for i in qs
        ]

    def get_stock(self, obj):  # noqa: ARG002
        """Return branch stock levels scoped to the user's branch (for offline lookups)."""
        user = self.context["request"].user
        since = self.context.get("since")

        if not user.has_perm("inventory.view_branchinventory"):
            return []

        qs = BranchInventory.objects.select_related("item", "branch").all()
        if not user.is_superuser and user.branch_id:
            qs = qs.filter(branch_id=user.branch_id)
        elif not user.is_superuser:
            return []

        if since:
            qs = qs.filter(updated_at__gt=since)

        return [
            {
                "item_id": bi.item_id,
                "branch_id": bi.branch_id,
                "quantity": str(bi.quantity),
                "minimum_threshold": str(bi.minimum_threshold),
                "updated_at": bi.updated_at.isoformat(),
            }
            for bi in qs
        ]

    def get_branches(self, obj):  # noqa: ARG002
        user = self.context["request"].user
        if not user.has_perm("branch.view_branch"):
            return []

        qs = Branch.objects.all()
        if not user.is_superuser:
            if is_purchaser(user):
                branch_ids = set(user.purchaser_branches.values_list("pk", flat=True))
                if user.branch_id:
                    branch_ids.add(user.branch_id)
                if branch_ids:
                    qs = qs.filter(branch_code__in=branch_ids)
                else:
                    return []
            elif user.branch_id:
                qs = qs.filter(branch_code=user.branch_id)
            else:
                return []

        return [{"id": b.pk, "name": b.name, "code": b.branch_code} for b in qs]

    def get_warehouses(self, obj):  # noqa: ARG002
        user = self.context["request"].user
        if not user.has_perm("warehouse.view_warehouse"):
            return []

        qs = Warehouse.objects.all()
        if not user.is_superuser and user.warehouse_id:
            qs = qs.filter(id=user.warehouse_id)

        return [{"id": w.id, "name": w.name} for w in qs]

    def get_user_context(self, obj):  # noqa: ARG002
        user = self.context["request"].user
        return {
            "id": user.id,
            "username": user.username,
            "branch_id": getattr(user, "branch_id", None),
            "warehouse_id": getattr(user, "warehouse_id", None),
            "is_admin": user.is_superuser,
            "permissions": list(user.get_all_permissions())
            if user.is_superuser
            else [],
        }
