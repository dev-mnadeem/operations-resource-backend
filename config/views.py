from django.shortcuts import redirect
from django.urls import reverse


def root_redirect(request):
    """
    Redirect root URL based on user authentication:
    - Authenticated → admin dashboard
    - Not authenticated → admin login
    """
    if request.user.is_authenticated:
        return redirect(reverse("admin:index"))
    else:
        return redirect(reverse("admin:login"))
