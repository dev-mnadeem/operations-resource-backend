from django.urls import path

from .views import BarcodeLookupView

urlpatterns = [
    path(
        "items/barcode/<str:barcode>/",
        BarcodeLookupView.as_view(),
        name="barcode-lookup",
    ),
]
