from dataclasses import FrozenInstanceError

import pytest

from webmcp_django import tools
from webmcp_django.tools import DefinitionError, Tool


def make_tool(**overrides):
    definition = {
        "name": "search", "description": "Search tasks.",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "limit": {"type": "integer"}}},
        "endpoint": {"path": "/api/search", "method": "POST"},
    }
    return Tool(**{**definition, **overrides})


@pytest.mark.parametrize("name", ["", "x" * 129, "a b", "é", "x\n", "<script>", 3, None])
def test_invalid_names(name):
    with pytest.raises(DefinitionError, match="tool name"):
        make_tool(name=name)


@pytest.mark.parametrize("name", ["x", "a.A-1_", "x" * 128])
def test_valid_names(name):
    assert make_tool(name=name).name == name


@pytest.mark.parametrize("override, message", [
    ({"description": ""}, "description"),
    ({"description": 1}, "description"),
    ({"title": 1}, "title"),
    ({"annotations": {"destructiveHint": True}}, "annotation sets differ"),
    ({"annotations": {"read_only": 1}}, "booleans"),
    ({"annotations": []}, "object"),
    ({"max_response_chars": 0}, "positive integer"),
    ({"max_response_chars": -1}, "positive integer"),
    ({"max_response_chars": True}, "positive integer"),
    ({"max_response_chars": 1.5}, "floats"),
    ({"max_response_chars": 2**53 + 1}, "2\\^53"),
    ({"description": "\ud800"}, "UTF-8"),
])
def test_invalid_metadata(override, message):
    with pytest.raises(DefinitionError, match=message):
        make_tool(**override)


@pytest.mark.parametrize("schema", [
    {}, [], {"type": "array"}, {"type": "object", "$ref": "#"},
    {"type": "object", "allOf": []}, {"type": "object", "additionalProperties": False},
    {"type": "object", "properties": []}, {"type": "object", "description": 2},
    {"type": "object", "required": ["missing"]},
    {"type": "object", "required": [{}]},
    {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x", "x"]},
    {"type": "object", "properties": {"__proto__": {"type": "string"}}},
    {"type": "object", "properties": {"constructor": {"type": "string"}}},
    {"type": "object", "properties": {"prototype": {"type": "string"}}},
])
def test_invalid_schema_roots(schema):
    with pytest.raises(DefinitionError):
        make_tool(input_schema=schema)


@pytest.mark.parametrize("prop", [
    {}, {"type": "object"}, {"type": ["string", "null"]},
    {"type": "array"}, {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
    {"type": "string", "items": {"type": "string"}},
    {"type": "string", "pattern": "a"}, {"type": "string", "anyOf": []},
    {"type": "string", "description": 4}, {"type": "string", "maxLength": -1},
    {"type": "array", "items": {"type": "string"}, "maxItems": True},
    {"type": "integer", "minimum": False}, {"type": "integer", "maximum": 1.5},
    {"type": "string", "enum": []}, {"type": "string", "enum": [1]},
    {"type": "integer", "default": True}, {"type": "boolean", "default": 1},
    {"type": "array", "items": {"type": "string"}, "default": [None]},
    {"type": "string", "default": None},
])
def test_invalid_properties(prop):
    with pytest.raises(DefinitionError):
        make_tool(input_schema={"type": "object", "properties": {"x": prop}})


def test_supported_metadata_and_boundary_integers():
    schema = {"type": "object", "description": "Inputs", "properties": {
        "s": {"type": "string", "enum": ["a", "b"], "default": "a", "maxLength": 4},
        "n": {"type": "number", "minimum": -(2**53), "maximum": 2**53, "default": 1},
        "b": {"type": "boolean", "default": False},
        "a": {"type": "array", "items": {"type": "integer", "minimum": 0}, "enum": [[1]], "default": [1], "maxItems": 2},
    }, "required": ["s"]}
    assert make_tool(input_schema=schema).to_manifest_entry({})["inputSchema"] == schema


@pytest.mark.parametrize("path", ["tasks", "//evil.test", "/\\evil", "https://evil.test", "/x:y", "/\n", "/\x00", "/\x7f", 1, None])
def test_endpoint_path(path):
    with pytest.raises(DefinitionError, match="endpoint path"):
        make_tool(endpoint={"path": path, "method": "POST"})


@pytest.mark.parametrize("method", ["GET", "post", "Patch", "PUT", "delete"])
def test_methods_and_read_only_post(method):
    tool = make_tool(endpoint={"path": "/api/search", "method": method}, annotations={"read_only": True})
    assert tool.endpoint["method"] == method.upper()


@pytest.mark.parametrize("endpoint, message", [
    ({"path": "/", "method": "GET"}, "read_only"),
    ({"path": "/", "method": "OPTIONS"}, "method"),
    ({"path": "/", "method": 2}, "method"),
    ({"path": "/"}, "method"),
    ({"path": "/", "method": "POST", "extra": True}, "unsupported"),
    ({"path": "/", "method": "POST", "array_format": "csv"}, "array_format"),
    ({"path": "/", "method": "POST", "param_map": {"missing": "q"}}, "not in schema"),
    ({"path": "/", "method": "POST", "param_map": {"title": "limit"}}, "collide"),
    ({"path": "/", "method": "POST", "param_map": {"title": "q", "limit": "q"}}, "collide"),
    ({"path": "/", "method": "POST", "param_map": []}, "object"),
])
def test_invalid_endpoints(endpoint, message):
    with pytest.raises(DefinitionError, match=message):
        make_tool(endpoint=endpoint)


@pytest.mark.parametrize("destination", [*tools.FORBIDDEN_PARAMS, "a-b", "a[]", "1a", "a\n", 1])
def test_invalid_mapping_destinations(destination):
    with pytest.raises(DefinitionError, match="destination"):
        make_tool(endpoint={"path": "/", "method": "POST", "param_map": {"title": destination}})


def test_metadata_copied_and_deeply_frozen():
    schema = {"type": "object", "properties": {"x": {"type": "string", "enum": ["a"]}}}
    tool = make_tool(input_schema=schema)
    schema["properties"]["x"]["enum"].append("b")
    assert tool.input_schema["properties"]["x"]["enum"] == ("a",)
    with pytest.raises(FrozenInstanceError):
        tool.name = "changed"
    with pytest.raises(TypeError):
        tool.input_schema["properties"]["x"]["type"] = "integer"
    with pytest.raises(TypeError):
        tool.endpoint["param_map"]["x"] = "y"
    emitted = tool.to_manifest_entry({})
    emitted["inputSchema"]["properties"]["x"]["enum"].append("c")
    assert tool.input_schema["properties"]["x"]["enum"] == ("a",)


def test_circular_and_non_json_metadata():
    schema = {"type": "object"}
    schema["properties"] = schema
    for value in (schema, {1: "key"}, {"type": "object", "x": object()}):
        with pytest.raises(DefinitionError):
            make_tool(input_schema=value)


def test_budget_warnings(caplog):
    make_tool(name="a" * 31, description="a" * 501)
    assert "30-character" in caplog.text
    assert "500-character" in caplog.text


def test_registry_duplicate_unknown_and_freeze(monkeypatch):
    monkeypatch.setattr(tools, "_registry", {})
    monkeypatch.setattr(tools, "_registry_frozen", False)
    tool = make_tool()
    assert tools.register(tool) is tool
    assert tools.get_tool("search") is tool
    with pytest.raises(DefinitionError, match="duplicate"):
        tools.register(tool)
    with pytest.raises(DefinitionError, match="unknown"):
        tools.get_tool("missing")
    with pytest.raises(DefinitionError, match="requires a Tool"):
        tools.register({})
    tools.freeze_registry()
    with pytest.raises(DefinitionError, match="frozen"):
        tools.register(make_tool(name="another"))
