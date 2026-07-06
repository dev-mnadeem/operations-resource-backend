from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import root_redirect

admin.site.disable_action("delete_selected")

urlpatterns = [
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("", include("apps.users.urls")),
    path("", include("apps.common.urls")),
    path("api/v1/", include("apps.inventory.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
