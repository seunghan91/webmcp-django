from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory

from webmcp_django.middleware import OriginTrialMiddleware


def test_adds_header_when_token_configured():
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = "test-token"
    middleware = OriginTrialMiddleware(lambda request: HttpResponse())
    request = RequestFactory().get("/")

    response = middleware(request)

    assert response["Origin-Trial"] == "test-token"


def test_no_op_when_token_missing():
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = ""
    middleware = OriginTrialMiddleware(lambda request: HttpResponse())
    request = RequestFactory().get("/")

    response = middleware(request)

    assert "Origin-Trial" not in response


def test_adds_header_on_streaming_response():
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = "test-token"
    middleware = OriginTrialMiddleware(
        lambda request: StreamingHttpResponse(iter([b"chunk"]))
    )
    request = RequestFactory().get("/")

    response = middleware(request)

    assert response["Origin-Trial"] == "test-token"


def test_preserves_existing_header():
    settings.WEBMCP_ORIGIN_TRIAL_TOKEN = "new-token"

    def get_response(request):
        response = HttpResponse()
        response["Origin-Trial"] = "existing-token"
        return response

    middleware = OriginTrialMiddleware(get_response)
    request = RequestFactory().get("/")

    response = middleware(request)

    assert response["Origin-Trial"] == "existing-token"
