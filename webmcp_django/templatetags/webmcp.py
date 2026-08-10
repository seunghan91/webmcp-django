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
from django.utils.html import escape, format_html

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
