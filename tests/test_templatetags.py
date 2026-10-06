import pytest
from django.template import Context, Template
from django.utils.safestring import mark_safe

from webmcp_django.tools import DefinitionError


def render(template_string, **context):
    return Template("{% load webmcp %}" + template_string).render(Context(context))


def test_webmcp_tool_renders_attributes():
    output = render('{% webmcp_tool "create_task" "Create a new task" %}')

    assert output == 'toolname="create_task" tooldescription="Create a new task"'


def test_webmcp_tool_autosubmit():
    output = render('{% webmcp_tool "create_task" "Create a new task" autosubmit=True %}')

    assert output == (
        'toolname="create_task" tooldescription="Create a new task" toolautosubmit'
    )


def test_webmcp_tool_escapes_values():
    output = render(
        '{% webmcp_tool tool_name description %}',
        tool_name="create_task",
        description='"><script>alert(1)</script>',
    )

    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_webmcp_tool_escapes_safe_string():
    output = render(
        '{% webmcp_tool tool_name description %}',
        tool_name=mark_safe("create_task"),
        description=mark_safe("<script>alert(1)</script>"),
    )

    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_webmcp_param_renders_and_escapes():
    output = render('{% webmcp_param description %}', description='"quoted" & <b>')

    assert output == 'toolparamdescription="&quot;quoted&quot; &amp; &lt;b&gt;"'


def test_webmcp_param_escapes_safe_string():
    output = render('{% webmcp_param description %}', description=mark_safe("<b>bold</b>"))

    assert "<b>" not in output
    assert "&lt;b&gt;" in output


@pytest.mark.parametrize("name", ["", "two words", "a" * 129, "bad\n", mark_safe("<script>")])
def test_webmcp_tool_rejects_invalid_name(name):
    with pytest.raises(DefinitionError, match="tool name"):
        render('{% webmcp_tool name "Description" %}', name=name)
