"""Declarative template tags for WebMCP attribute strings.

Renders the `toolname` / `tooldescription` / `toolparamdescription`
attributes that WebMCP reads from `<form>` and `<input>` elements
(the declarative counterpart to registering tools imperatively via
`document.modelContext`). Values are always HTML-escaped — including
values passed in as a Django `SafeString` (e.g. via `mark_safe` or a
`|safe` filter upstream). `format_html`'s normal escaping only
conditionally escapes (it trusts anything with `__html__`, which is how
`SafeString` opts out), so these tags call `django.utils.html.escape()`
directly first, which escapes unconditionally regardless of a value's
"safe" marking. A caller cannot smuggle unescaped markup into tool
metadata by pre-marking a value as safe.

Security note — tool metadata is agent-visible, not just display text:
an AI agent reads `tooldescription` / `toolparamdescription` as part of
its instructions for what the tool does. Do not build these strings from
unvalidated user input (profile fields, query params, uploaded file
names, etc.); a user-controlled value rendered into tool metadata is a
prompt-injection vector that can hijack the agent's behavior. Keep tool
names and descriptions as literal strings you write, not values derived
at request time from data a visitor controls.
"""

from django import template
from django.conf import settings
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.utils.html import escape, format_html

from webmcp_django import manifest
from webmcp_django.tools import get_tool, validate_name

register = template.Library()


@register.simple_tag(name="webmcp_tool")
def webmcp_tool(tool_name, description, autosubmit=False):
    """Render `toolname`/`tooldescription` (and optionally `toolautosubmit`).

    Usage:
        {% webmcp_tool "create_task" "Create a new task" autosubmit=True %}

    `tool_name` and `description` are always escaped via `escape()` before
    rendering, so a pre-marked-safe (`mark_safe`) value cannot bypass
    escaping.
    """
    validate_name(tool_name)
    tool_name = escape(tool_name)
    description = escape(description)
    if autosubmit:
        return format_html(
            'toolname="{}" tooldescription="{}" toolautosubmit',
            tool_name,
            description,
        )
    return format_html(
        'toolname="{}" tooldescription="{}"',
        tool_name,
        description,
    )


@register.simple_tag(name="webmcp_param")
def webmcp_param(description):
    """Render `toolparamdescription` for a form field.

    Usage:
        {% webmcp_param "The task title" %}

    `description` is always escaped via `escape()` before rendering, so a
    pre-marked-safe (`mark_safe`) value cannot bypass escaping.
    """
    return format_html('toolparamdescription="{}"', escape(description))


def _request(context):
    return getattr(context, "request", None) or context.get("request")


@register.simple_tag(takes_context=True)
def webmcp_manifest(context, *names, autostart=True, transport=None):
    """Expose only explicitly named tools on this page."""
    return manifest.to_script_tag(
        manifest.build([get_tool(name) for name in names], transport=transport),
        autostart=autostart,
        nonce=getattr(_request(context), "csp_nonce", None),
    )


@register.simple_tag(takes_context=True)
def webmcp_runtime(context):
    """Load the shared external ES module through Django's static storage."""
    src = escape(static("webmcp_django/webmcp-runtime.js"))
    nonce = getattr(_request(context), "csp_nonce", None)
    if nonce is not None:
        return format_html('<script type="module" src="{}" nonce="{}"></script>', src, escape(nonce))
    return format_html('<script type="module" src="{}"></script>', src)


@register.simple_tag
def webmcp_origin_trial_meta():
    """Render the configured token, or nothing when no token is configured."""
    token = getattr(settings, "WEBMCP_ORIGIN_TRIAL_TOKEN", "")
    if not token:
        return ""
    return format_html('<meta http-equiv="origin-trial" content="{}">', escape(token))


@register.simple_tag(takes_context=True)
def webmcp_csrf_meta(context):
    """Expose a masked CSRF token, including with HttpOnly CSRF cookies."""
    request = _request(context)
    token = get_token(request) if request is not None else context.get("csrf_token", "")
    if token == "NOTPROVIDED":
        token = ""
    return format_html('<meta name="csrf-token" content="{}">', escape(token))
