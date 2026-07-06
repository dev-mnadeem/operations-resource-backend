from django.urls import path

from .views import dashboard_redirect

app_name = "users"
urlpatterns = [
    path("redirect/", dashboard_redirect, name="dashboard_redirect"),
]
