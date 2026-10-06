import json
import re

import pytest
from django.http import HttpResponse, JsonResponse
from django.template import Context, RequestContext, Template
from django.test import Client, RequestFactory, override_settings
from django.urls import path
from django.utils.safestring import mark_safe

from webmcp_django import tools
from webmcp_django.tools import DefinitionError, Tool


def page(request):
    return HttpResponse(Template('{% load webmcp %}{% webmcp_csrf_meta %}').render(RequestContext(request)))


def write(request):
    return JsonResponse({"received": json.loads(request.body)})


urlpatterns = [path("", page), path("write", write)]


@override_settings(
    ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"], SECRET_KEY="test-only",
    MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"], CSRF_COOKIE_HTTPONLY=True,
)
def test_http_only_csrf_meta_real_middleware():
    client = Client(enforce_csrf_checks=True)
    response = client.get("/")
    assert response.status_code == 200
    assert response.cookies["csrftoken"]["httponly"]
    token = re.fullmatch(r'<meta name="csrf-token" content="([A-Za-z0-9]+)">', response.content.decode()).group(1)
    payload = {"title": "Task"}
    assert client.post("/write", payload, content_type="application/json").status_code == 403
    response = client.post("/write", payload, content_type="application/json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
    assert response.json() == {"received": payload}
    assert client.post("/write", payload, content_type="application/json", HTTP_X_CSRFTOKEN="x" * 64).status_code == 403


def render(source, **values):
    return Template("{% load webmcp %}" + source).render(Context(values))


@override_settings(STATIC_URL="/static/")
def test_runtime_static_and_nonce():
    assert render("{% webmcp_runtime %}") == '<script type="module" src="/static/webmcp_django/webmcp-runtime.js"></script>'
    request = RequestFactory().get("/")
    request.csp_nonce = mark_safe('\"><script>&')
    html = render("{% webmcp_runtime %}", request=request)
    assert 'nonce="&quot;&gt;&lt;script&gt;&amp;"' in html
    assert html.count("<script") == 1


@override_settings(WEBMCP_ORIGIN_TRIAL_TOKEN=mark_safe('\"><script>&'))
def test_origin_meta_escaping():
    assert render("{% webmcp_origin_trial_meta %}") == '<meta http-equiv="origin-trial" content="&quot;&gt;&lt;script&gt;&amp;">'
    with override_settings(WEBMCP_ORIGIN_TRIAL_TOKEN=""):
        assert render("{% webmcp_origin_trial_meta %}") == ""


def test_csrf_context_fallback_escapes_safe_values():
    assert render("{% webmcp_csrf_meta %}", csrf_token=mark_safe('\"><script>')) == '<meta name="csrf-token" content="&quot;&gt;&lt;script&gt;">'


def test_manifest_page_opt_in(monkeypatch):
    monkeypatch.setattr(tools, "_registry", {})
    monkeypatch.setattr(tools, "_registry_frozen", False)
    for name in ("one", "two"):
        tools.register(Tool(name=name, description="Test", input_schema={"type": "object"}, endpoint={"path": "/", "method": "POST"}))
    html = render('{% webmcp_manifest "two" autostart=False %}')
    data = json.loads(html.split(">", 1)[1].removesuffix("</script>"))
    assert [tool["name"] for tool in data["tools"]] == ["two"]
    assert "data-webmcp-autostart" not in html
    empty = render("{% webmcp_manifest %}")
    assert json.loads(empty.split(">", 1)[1].removesuffix("</script>"))["tools"] == []
    with pytest.raises(DefinitionError, match="unknown"):
        render('{% webmcp_manifest "unknown" %}')
    with pytest.raises(DefinitionError, match="duplicate"):
        render('{% webmcp_manifest "one" "one" %}')
