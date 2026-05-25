from typing import TYPE_CHECKING

from django.db import transaction
from rest_framework import serializers

from apps.branch.models import Branch
from apps.inventory.models import InventoryItem

from .models import Demand, DemandItem

if TYPE_CHECKING:
    from collections.abc import Iterable


class DemandItemCreateSerializer(serializers.Serializer):
    inventory_item = serializers.PrimaryKeyRelatedField(
        queryset=InventoryItem.objects.all(),
    )
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    priority = serializers.ChoiceField(
        choices=DemandItem.PRIORITY_CHOICES,
        default=DemandItem.PRIORITY_MEDIUM,
    )

    def validate(self, attrs):
        if attrs["quantity"] <= 0:
            raise serializers.ValidationError(
                {"quantity": "Quantity must be greater than zero."},
            )
        return attrs


class DemandCreateSerializer(serializers.Serializer):
    """
    Serializer used by the custom "create demand" page.

    Expects:
    - branch (optional, defaults to request.user.branch when present)
    - items: list of {inventory_item, quantity, priority}
    """

    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        required=False,
        allow_null=True,
    )
    items = DemandItemCreateSerializer(many=True)

    def _get_request(self):
        return self.context.get("request")

    def validate(self, attrs):
        request = self._get_request()

        branch = attrs.get("branch")
        if branch is None:
            user = getattr(request, "user", None)
            user_branch = getattr(user, "branch", None) if user else None
            if user_branch is None:
                raise serializers.ValidationError(
                    {
                        "branch": "Branch is required when user is not linked to a branch."
                    },
                )
            attrs["branch"] = user_branch

        items = attrs.get("items") or []
        if not items:
            raise serializers.ValidationError(
                {"items": "At least one item must be provided."},
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self._get_request()
        user = getattr(request, "user", None)
        branch = validated_data["branch"]
        items_data: Iterable[dict] = validated_data["items"]

        demand = Demand.objects.create(
            branch=branch,
            submitted_by=user,
        )

        demand_items: list[DemandItem] = []
        for item in items_data:
            inventory_item: InventoryItem = item["inventory_item"]
            demand_items.append(
                DemandItem(
                    demand=demand,
                    inventory_item=inventory_item,
                    quantity=item["quantity"],
                    unit=inventory_item.unit,
                    priority=item["priority"],
                ),
            )

        DemandItem.objects.bulk_create(demand_items)
        return demand


class DemandItemReadSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(
        source="inventory_item.name",
        read_only=True,
    )
    unit = serializers.CharField(source="unit.abbreviation", read_only=True)

    class Meta:
        model = DemandItem
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "quantity",
            "unit",
            "priority",
        ]


class DemandReadSerializer(serializers.ModelSerializer):
    items = DemandItemReadSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Demand
        fields = [
            "id",
            "branch",
            "branch_name",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "items",
        ]
