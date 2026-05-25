from django.core.cache import cache
from django.http import HttpResponse


class IdempotencyMiddleware:
    """
    Prevents duplicate POST requests using a client-provided X-Client-Request-ID.

    Responses are kept in Django's cache, so with several worker processes the
    cache has to be shared (e.g. Redis) for a replay to find the first answer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST":
            return self.get_response(request)

        request_id = request.headers.get("X-Client-Request-ID")
        if not request_id:
            # Check if it was sent in the body (form data)
            if request.POST.get("x_client_request_id"):
                request_id = request.POST.get("x_client_request_id")
            else:
                return self.get_response(request)

        # Cache key based on user and request ID
        user_id = request.user.id if request.user.is_authenticated else "anon"
        cache_key = f"idempotency_{user_id}_{request_id}"
        cached_response = cache.get(cache_key)

        if cached_response:
            replay = HttpResponse(
                content=cached_response["content"],
                status=cached_response["status"],
                content_type=cached_response["content_type"],
            )
            if cached_response.get("location"):
                replay["Location"] = cached_response["location"]
            return replay

        response = self.get_response(request)

        # Remember successful outcomes for 24 hours. A successful admin form
        # POST answers with a redirect, so 3xx counts as success: it is
        # exactly the request the offline queue replays after a lost response.
        if 200 <= response.status_code < 400 and not response.streaming:
            cache.set(
                cache_key,
                {
                    "content": response.content,
                    "status": response.status_code,
                    "content_type": response.get("Content-Type"),
                    "location": response.get("Location"),
                },
                86400,
            )

        return response
