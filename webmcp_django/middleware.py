"""Origin-Trial header middleware for WebMCP.

Chrome's WebMCP origin trial (Chrome 149-156) requires participating
origins to serve an `Origin-Trial` response header containing a token
issued for the origin. This middleware adds that header when a token is
configured, and is a no-op otherwise.
"""

from django.conf import settings


class OriginTrialMiddleware:
    """Standard Django middleware that adds the `Origin-Trial` header.

    Reads the token from ``settings.WEBMCP_ORIGIN_TRIAL_TOKEN``. When the
    setting is unset or falsy, the middleware passes the response through
    unmodified. If the response already carries an `Origin-Trial` header
    (set by a view or another middleware), that value is left untouched —
    this middleware only fills in a missing header, it never overrides one.
    Works with both `HttpResponse` and `StreamingHttpResponse`, since both
    expose the same `.headers` mapping.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        token = getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", None)
        if token:
            response.headers.setdefault("Origin-Trial", token)
        return response
