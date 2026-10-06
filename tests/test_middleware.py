from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, override_settings

from webmcp_django.middleware import OriginTrialMiddleware
from webmcp_django import middleware as module


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


@override_settings(WEBMCP_ORIGIN_TRIAL_TOKEN="token", WEBMCP_WARN_ON_OAC_OPT_OUT=True)
def test_oac_warning_once_across_instances(monkeypatch, caplog):
    monkeypatch.setattr(module, "_warned_oac", False)
    for _ in range(3):
        response = HttpResponse(headers={"Origin-Agent-Cluster": "?0", "Origin-Trial": ""})
        result = OriginTrialMiddleware(lambda request: response)(RequestFactory().get("/"))
        assert result["Origin-Agent-Cluster"] == "?0"
        assert result["Origin-Trial"] == ""
    assert len([record for record in caplog.records if "Origin-Agent-Cluster" in record.message]) == 1


def test_oac_opt_in_and_empty_token_no_op(monkeypatch, caplog):
    monkeypatch.setattr(module, "_warned_oac", False)
    for token, enabled, oac in [("token", False, "?0"), ("", True, "?0"), ("token", True, "?1")]:
        with override_settings(WEBMCP_ORIGIN_TRIAL_TOKEN=token, WEBMCP_WARN_ON_OAC_OPT_OUT=enabled):
            response = HttpResponse(headers={"Origin-Agent-Cluster": oac})
            result = OriginTrialMiddleware(lambda request: response)(RequestFactory().get("/"))
            assert result["Origin-Agent-Cluster"] == oac
    assert not caplog.records
