from django.urls import path

from apps.replenishment.views import ReplenishmentAdviceView

urlpatterns = [
    path("replenishment/advice/", ReplenishmentAdviceView.as_view(),
         name="replenishment-advice"),
]
