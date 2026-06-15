from django.contrib.admin.views.main import IS_POPUP_VAR
from django.utils.html import format_html


def _get_popup_select_link(obj, request):
    """Build a 'Select' link for related lookup popup (same behavior as list_display_links)."""
    to_field = request.GET.get("_to_field", "pk")
    value = getattr(obj, to_field, None)
    if value is None:
        value = obj.pk
    return format_html(
        '<a href="javascript:void(0)" class="btn btn-xs btn-primary" data-popup-opener="{}">'
        '<i class="fas fa-check"></i> Select</a>',
        str(value),
    )


class RowActionButtonsMixin:
    """
    Mixin to add Edit/Delete buttons in Django admin list_display.
    In related lookup popups (_popup=1), shows a 'Select' link so the user can choose an item.
    """

    def changelist_view(self, request, *args, **kwargs):
        self._changelist_request = request
        return super().changelist_view(request, *args, **kwargs)

    def row_actions(self, obj):
        request = getattr(self, "_changelist_request", None)
        if request and request.GET.get(IS_POPUP_VAR):
            return _get_popup_select_link(obj, request)
        edit_url = (
            f"/admin/{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/change/"
        )
        delete_url = (
            f"/admin/{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/delete/"
        )
        return format_html(
            '<div style="display: flex; gap: 4px; white-space: nowrap;">'
            '<a class="btn btn-xs btn-info" href="{}"><i class="fas fa-edit"></i> Edit</a>'
            '<a class="btn btn-xs btn-danger" href="{}"><i class="fas fa-trash"></i> Delete</a>'
            "</div>",
            edit_url,
            delete_url,
        )

    row_actions.short_description = "Actions"
    row_actions.allow_tags = True


class EditRowActionButtonMixin:
    """
    Mixin to add only Edit button in Django admin list_display.
    In related lookup popups (_popup=1), shows a 'Select' link so the user can choose an item.
    """

    def changelist_view(self, request, *args, **kwargs):
        self._changelist_request = request
        return super().changelist_view(request, *args, **kwargs)

    def row_actions(self, obj):
        request = getattr(self, "_changelist_request", None)
        if request and request.GET.get(IS_POPUP_VAR):
            return _get_popup_select_link(obj, request)
        edit_url = (
            f"/admin/{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/change/"
        )
        return format_html(
            '<div style="display: flex; gap: 4px; white-space: nowrap;">'
            '<a class="btn btn-xs btn-info" href="{}"><i class="fas fa-edit"></i> Edit</a>'
            "</div>",
            edit_url,
        )

    row_actions.short_description = "Actions"
    row_actions.allow_tags = True


class DeleteRowActionButtonMixin:
    """
    Mixin to add only Delete button in Django admin list_display.
    In related lookup popups (_popup=1), shows a 'Select' link so the user can choose an item.
    """

    def changelist_view(self, request, *args, **kwargs):
        self._changelist_request = request
        return super().changelist_view(request, *args, **kwargs)

    def row_actions(self, obj):
        request = getattr(self, "_changelist_request", None)
        if request and request.GET.get(IS_POPUP_VAR):
            return _get_popup_select_link(obj, request)
        delete_url = (
            f"/admin/{obj._meta.app_label}/{obj._meta.model_name}/{obj.pk}/delete/"
        )
        return format_html(
            '<div style="display: flex; gap: 4px; white-space: nowrap;">'
            '<a class="btn btn-xs btn-danger" href="{}"><i class="fas fa-trash"></i> Delete</a>'
            "</div>",
            delete_url,
        )

    row_actions.short_description = "Actions"
    row_actions.allow_tags = True
