"""Origin-Trial header middleware for WebMCP.

Adds a configured Origin-Trial token without replacing existing headers.
"""

import logging
from threading import Lock

from django.conf import settings

_warning_lock = Lock()
_warned_oac = False
logger = logging.getLogger("webmcp_django")


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
        global _warned_oac
        response = self.get_response(request)
        token = getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", None)
        if token:
            response.headers.setdefault("Origin-Trial", token)
            if (getattr(settings, "WEBMCP_WARN_ON_OAC_OPT_OUT", False)
                    and response.headers.get("Origin-Agent-Cluster") == "?0"):
                with _warning_lock:
                    if not _warned_oac:
                        logger.warning("WebMCP: Origin-Agent-Cluster: ?0 may cause SecurityError in older Origin-Trial builds; header left unchanged")
                        _warned_oac = True
        return response
