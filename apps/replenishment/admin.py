"""
Admin screen for replenishment.

The derived figures are computed once per changelist request and cached on the
request object. Computing them inside each `list_display` callable would issue
a query per column per row — the classic admin N+1, and with six derived
columns it would be six times worse than the usual one.
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import (
    ExpressionWrapper,
    F,
    FloatField,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.html import format_html

from apps.replenishment.models import ReplenishmentAdvice
from apps.replenishment.service import (
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LEAD_TIME_DAYS,
    DEFAULT_SERVICE_LEVEL,
    profile_for,
)

RISK_COLOURS = {
    "critical": ("#b91c1c", "will run out before a reorder can arrive"),
    "reorder": ("#c2410c", "below the reorder point"),
    "watch": ("#a16207", "within two lead times of the reorder point"),
    "ok": ("#15803d", "comfortable"),
    "idle": ("#6b7280", "no demand recorded"),
    "unknown": ("#6b7280", "not enough history to judge"),
}

CACHE_ATTR = "_replenishment_profiles"


@admin.register(ReplenishmentAdvice)
class ReplenishmentAdviceAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "branch",
        "risk_badge",
        "on_hand",
        "daily_demand",
        "cover",
        "reorder_point",
        "configured_threshold_col",
        "suggested_order",
    )
    list_filter = ("branch",)
    search_fields = ("item__name", "item__sku")
    list_per_page = 25


    # Read-only: this screen advises, it does not edit stock.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        """
        Only items with demand history, ordered by days of cover.

        Two reasons this is done in SQL rather than in Python. The screen is
        useless if it opens on the 335 items that have never sold — those are a
        data gap, not a restocking decision. And "days of cover" is the
        ordering a buyer actually wants, which the admin cannot sort by if it
        is computed in a `list_display` callable.

        cover = on_hand / (total_consumed / window_days), and since the window
        is constant the ordering reduces to on_hand / total_consumed.
        """
        window_start = timezone.now().date() - timedelta(days=DEFAULT_HISTORY_DAYS - 1)

        queryset = (
            super()
            .get_queryset(request)
            .select_related("item", "branch")
            .annotate(
                demand_total=Coalesce(
                    Sum(
                        "item__consumptions__quantity_consumed",
                        filter=Q(
                            item__consumptions__sales_transaction__occurred_at__date__gte=window_start
                        ),
                    ),
                    Value(0),
                    output_field=FloatField(),
                )
            )
            .filter(demand_total__gt=0)
            .annotate(
                days_of_cover=ExpressionWrapper(
                    Cast("quantity", FloatField())
                    * Value(float(DEFAULT_HISTORY_DAYS))
                    / F("demand_total"),
                    output_field=FloatField(),
                )
            )
            .order_by("days_of_cover")
        )
        return queryset

    def _profile(self, request, obj):
        cache = getattr(request, CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(request, CACHE_ATTR, cache)
        if obj.pk not in cache:
            cache[obj.pk] = profile_for(
                obj,
                lead_time_days=DEFAULT_LEAD_TIME_DAYS,
                service_level=DEFAULT_SERVICE_LEVEL,
                history_days=DEFAULT_HISTORY_DAYS,
            )
        return cache[obj.pk]

    @admin.display(description="risk")
    def risk_badge(self, obj):
        profile = self._profile_for_display(obj)
        colour, tooltip = RISK_COLOURS.get(profile.risk, ("#6b7280", ""))
        return format_html(
            '<b style="color:{}" title="{}">{}</b>', colour, tooltip, profile.risk
        )

    @admin.display(description="on hand")
    def on_hand(self, obj):
        return f"{float(obj.quantity or 0):.1f}"

    @admin.display(description="demand/day")
    def daily_demand(self, obj):
        profile = self._profile_for_display(obj)
        if not profile.has_enough_history:
            return "—"
        return f"{profile.mean_daily_demand:.2f}"

    # `ordering=` maps the column to the annotation, which is how Django
    # supports sorting on a computed value. Static `ordering = (...)` cannot be
    # used for this: admin check E033 rejects any name that is not a model
    # field, and overriding get_ordering pushes the annotation name into the
    # ChangeList, which resolves it against the model and raises FieldError.
    @admin.display(description="days of cover", ordering="days_of_cover")
    def cover(self, obj):
        profile = self._profile_for_display(obj)
        if profile.days_of_cover is None:
            return "—"
        colour = "#b91c1c" if profile.days_of_cover <= profile.lead_time_days else "#111827"
        return format_html(
            '<span style="color:{}">{}</span>', colour, f"{profile.days_of_cover:.1f}"
        )

    @admin.display(description="reorder point")
    def reorder_point(self, obj):
        profile = self._profile_for_display(obj)
        if not profile.has_enough_history:
            return "—"
        return f"{profile.reorder_point:.1f}"

    @admin.display(description="threshold set")
    def configured_threshold_col(self, obj):
        profile = self._profile_for_display(obj)
        configured = profile.configured_threshold
        if not profile.has_enough_history:
            return f"{configured:.1f}"
        # The comparison this screen exists to make: what is configured against
        # what the history says it should be.
        if configured < profile.reorder_point:
            return format_html(
                '<span style="color:#b91c1c">{}</span> <small>(too low by {})</small>',
                f"{configured:.1f}",
                f"{profile.threshold_error:.1f}",
            )
        return f"{configured:.1f}"

    @admin.display(description="order now")
    def suggested_order(self, obj):
        profile = self._profile_for_display(obj)
        quantity = profile.suggested_order_quantity
        if quantity <= 0:
            return "—"
        return format_html("<b>{}</b>", f"{quantity:.1f}")

    # `list_display` callables receive only the object, so the request-scoped
    # cache is reached through a thread-local set in changelist_view.
    _request = None

    #: 1-based position of the "days of cover" column in list_display, used to
    #: build the admin's `o=` sort parameter.
    COVER_COLUMN = 6

    def changelist_view(self, request, extra_context=None):
        self._request = request

        # Open on the least cover first. Without this the screen loads in the
        # model's default order, which puts whatever is alphabetically first at
        # the top — not what a buyer opening a restocking screen needs.
        if "o" not in request.GET:
            params = request.GET.copy()
            params["o"] = str(self.COVER_COLUMN)
            return HttpResponseRedirect(f"{request.path}?{params.urlencode()}")

        return super().changelist_view(request, extra_context=extra_context)

    def _profile_for_display(self, obj):
        return self._profile(self._request, obj)
