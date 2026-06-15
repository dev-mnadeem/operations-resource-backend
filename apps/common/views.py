from datetime import UTC, datetime

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SnapshotSerializer


class PingView(APIView):
    """
    Lightweight connectivity check for the admin offline UI.

    Must live under /api/v1/ so the service worker does not serve a cached
    /admin/* page and falsely report "online" when the network is down.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        return Response(
            {"ok": True},
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            },
        )


class SnapshotView(APIView):
    """
    Returns a snapshot of reference data for offline use.

    GET /api/v1/snapshot/         — full snapshot
    GET /api/v1/snapshot/?since=<iso_timestamp>  — delta: only records changed after that time
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        since = None
        since_raw = request.GET.get("since", "").strip()
        if since_raw:
            try:
                since = datetime.fromisoformat(since_raw)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                pass  # ignore bad timestamp; fall back to full snapshot

        serializer = SnapshotSerializer(
            None, context={"request": request, "since": since}
        )
        return Response(serializer.data)
