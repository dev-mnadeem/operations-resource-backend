from django.shortcuts import redirect


def dashboard_redirect(_request):
    """
    Keep as a simple redirect to admin index if anyone hits /redirect/
    """
    return redirect("admin:index")
