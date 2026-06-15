from django.conf import settings
from django.urls import path
from django.views.generic import TemplateView
from django.views.static import serve

from .views import PingView, SnapshotView

app_name = "common"

urlpatterns = [
    path("api/v1/ping/", PingView.as_view(), name="ping"),
    path("api/v1/snapshot/", SnapshotView.as_view(), name="snapshot"),
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="admin/js/sw.js", content_type="application/javascript"
        ),
        name="service_worker",
    ),
    path(
        "admin/manifest.json",
        serve,
        kwargs={"path": "manifest.json", "document_root": settings.STATICFILES_DIRS[0]},
        name="pwa_manifest",
    ),
]
