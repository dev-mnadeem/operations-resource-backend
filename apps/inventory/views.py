from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.permissions import is_admin, is_branch_manager, is_warehouse_manager

from .models import BranchInventory, InventoryItem


class BarcodeLookupView(APIView):
    """
    GET /api/v1/items/barcode/<barcode>/

    Returns item details and current stock for the authenticated user's scope:
      - Admin          → stock for every branch
      - Branch Manager → stock for their branch only
      - Warehouse Manager → stock for their warehouse only
      - Purchaser      → item details only (no stock figures)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, barcode):
        try:
            item = InventoryItem.objects.select_related(
                "unit", "section", "category"
            ).get(barcode=barcode)
        except InventoryItem.DoesNotExist:
            return Response(
                {"detail": f"No item found for barcode '{barcode}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "id": item.id,
            "name": item.name,
            "barcode": item.barcode,
            "sku": item.sku,
            "unit": item.unit.abbreviation if item.unit else None,
            "section": item.section.name if item.section else None,
            "category": item.category.name if item.category else None,
            "stock": self._get_stock(request.user, item),
        }
        return Response(data)

    def _get_stock(self, user, item):
        if is_admin(user):
            return list(
                BranchInventory.objects.filter(item=item)
                .select_related("branch")
                .values(
                    "branch__branch_code",
                    "branch__name",
                    "quantity",
                    "minimum_threshold",
                )
            )

        if is_branch_manager(user) and user.branch_id:
            bi = BranchInventory.objects.filter(
                item=item, branch_id=user.branch_id
            ).first()
            return {
                "branch_code": user.branch_id,
                "quantity": str(bi.quantity) if bi else "0",
                "minimum_threshold": str(bi.minimum_threshold) if bi else "0",
            }

        if is_warehouse_manager(user) and user.warehouse_id:
            from apps.warehouse.models import WarehouseInventory

            wi = WarehouseInventory.objects.filter(
                inventory_item=item, warehouse_id=user.warehouse_id
            ).first()
            return {
                "warehouse_id": user.warehouse_id,
                "quantity": str(wi.quantity) if wi else "0",
                "location": wi.location if wi else None,
            }

        return None  # Purchaser sees item details only
