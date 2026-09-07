"""Replenishment API."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import BranchInventory
from apps.replenishment.service import (
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LEAD_TIME_DAYS,
    DEFAULT_SERVICE_LEVEL,
    Z_SCORES,
    rank_inventory,
)


class ReplenishmentAdviceView(APIView):
    """Stock ranked by how soon it runs out, with a reorder quantity."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="replenishment_advice",
        summary="Rank stock by stockout risk with reorder recommendations",
        parameters=[
            OpenApiParameter("branch", str, description="Branch code to filter by."),
            OpenApiParameter("lead_time_days", int,
                             description=f"Supplier lead time (default {DEFAULT_LEAD_TIME_DAYS})."),
            OpenApiParameter("service_level", float,
                             description="Target service level, e.g. 0.95."),
            OpenApiParameter("history_days", int,
                             description=f"Days of history to read (default {DEFAULT_HISTORY_DAYS})."),
            OpenApiParameter("risk", str,
                             description="Only return this risk band (critical, reorder, watch, ok)."),
            OpenApiParameter("limit", int, description="Maximum rows."),
        ],
    )
    def get(self, request, *args, **kwargs):
        try:
            lead_time = int(request.query_params.get("lead_time_days", DEFAULT_LEAD_TIME_DAYS))
            service_level = float(request.query_params.get("service_level", DEFAULT_SERVICE_LEVEL))
            history_days = int(request.query_params.get("history_days", DEFAULT_HISTORY_DAYS))
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            return Response(
                {"detail": "lead_time_days, history_days and limit must be numbers; "
                           "service_level must be a decimal fraction."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if lead_time < 1:
            return Response({"detail": "lead_time_days must be at least 1."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not 0 < service_level < 1:
            return Response(
                {"detail": f"service_level must be between 0 and 1; "
                           f"tabulated values are {sorted(Z_SCORES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = BranchInventory.objects.all()
        branch = request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch__branch_code=branch)

        profiles = rank_inventory(
            queryset,
            lead_time_days=lead_time,
            service_level=service_level,
            history_days=history_days,
        )

        wanted = request.query_params.get("risk")
        if wanted:
            profiles = [p for p in profiles if p.risk == wanted]

        profiles = profiles[:limit]
        return Response(
            {
                "parameters": {
                    "lead_time_days": lead_time,
                    "service_level": service_level,
                    "history_days": history_days,
                },
                "count": len(profiles),
                "results": [p.as_dict() for p in profiles],
            }
        )
