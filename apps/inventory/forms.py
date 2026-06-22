from django import forms
from django.core.exceptions import ValidationError

from .models import InventoryItem


class SubCategorySelect(forms.Select):
    """
    Custom Select widget that adds data-parent-id to options for local filtering.
    """

    def __init__(self, attrs=None, choices=(), parent_map=None):
        super().__init__(attrs, choices)
        self.parent_map = parent_map or {}

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value and str(value) in self.parent_map:
            option["attrs"]["data-parent-id"] = self.parent_map[str(value)]
        return option


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "name",
            "barcode",
            "sku",
            "section",
            "category",
            "unit",
        ]
        widgets = {
            "category": SubCategorySelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import InventoryCategory

        self.fields["category"].empty_label = "First select section to choose category"

        # Load all sub-categories (categories with a parent) and build parent mapping
        all_sub_categories = InventoryCategory.objects.exclude(
            parent_category__isnull=True
        ).select_related("parent_category")
        self.fields["category"].queryset = all_sub_categories

        parent_map = {
            str(cat.id): str(cat.parent_category_id) for cat in all_sub_categories
        }
        self.fields["category"].widget.parent_map = parent_map

    def clean_barcode(self):
        barcode = self.cleaned_data.get("barcode")
        if not barcode:
            return barcode

        qs = InventoryItem.objects.filter(barcode=barcode)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("An inventory item with this barcode already exists.")
        return barcode
