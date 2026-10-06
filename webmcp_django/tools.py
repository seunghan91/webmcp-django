"""Validated, immutable browser tool definitions and a boot-time registry."""

import logging
import re
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from collections.abc import Mapping


class DefinitionError(ValueError):
    """A tool or manifest falls outside the supported manifest v1 contract."""


ANNOTATIONS = {
    "read_only": "readOnlyHint",
    "untrusted_content": "untrustedContentHint",
    "consequential": "consequentialHint",
    "debugging": "debugging",
}
SCALARS = ("string", "number", "integer", "boolean")
RESERVED = ("__proto__", "constructor", "prototype")
FORBIDDEN_PARAMS = (*RESERVED, "_method", "authenticity_token", "csrfmiddlewaretoken")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
logger = logging.getLogger("webmcp_django")


def _normalize(value, ancestors=()):
    """Copy JSON metadata, stripping safe markers and rejecting lossy values."""
    if isinstance(value, (dict, list)):
        if id(value) in ancestors:
            raise DefinitionError("metadata cannot contain circular references")
        ancestors = (*ancestors, id(value))
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DefinitionError("metadata keys must be strings")
            result[_normalize(key)] = _normalize(item, ancestors)
        return result
    if isinstance(value, list):
        return [_normalize(item, ancestors) for item in value]
    if isinstance(value, str):
        try:
            return value.encode("utf-8").decode("utf-8")
        except UnicodeError as exc:
            raise DefinitionError("metadata must be valid UTF-8") from exc
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > 2**53:
            raise DefinitionError("metadata integers must be within +/-2^53")
        return value
    raise DefinitionError("metadata must contain JSON values; floats are not supported")


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise DefinitionError(f"{label} must be an object")


def _keys(value, allowed, label):
    _object(value, label)
    unknown = value.keys() - set(allowed)
    if unknown:
        raise DefinitionError(f"unsupported {label} keys: {', '.join(sorted(unknown))}")


def validate_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name):
        raise DefinitionError("tool name must be 1..128 characters from A-Z, a-z, 0-9, _, . and -")
    return name


def _matches(value, schema):
    kind = schema["type"]
    if kind == "string":
        return isinstance(value, str)
    if kind in ("number", "integer"):
        return type(value) is int
    if kind == "boolean":
        return type(value) is bool
    return isinstance(value, list) and all(_matches(item, schema["items"]) for item in value)


def _validate_property(prop, label, scalar_only=False):
    metadata = ("enum", "description", "default", "minimum", "maximum", "maxLength", "maxItems")
    _keys(prop, ("type", *metadata, *(() if scalar_only else ("items",))), f"property {label}")
    kind = prop.get("type")
    if kind not in SCALARS and (scalar_only or kind != "array"):
        raise DefinitionError(f"{label}: only scalar properties and arrays of scalars are supported")
    if kind == "array":
        _validate_property(prop.get("items"), f"{label}.items", scalar_only=True)
    elif "items" in prop:
        raise DefinitionError(f"{label}: items requires array type")
    if "description" in prop and not isinstance(prop["description"], str):
        raise DefinitionError(f"{label}: description must be a string")
    for key in ("minimum", "maximum", "maxLength", "maxItems"):
        if key in prop and (type(prop[key]) is not int or (key in ("maxLength", "maxItems") and prop[key] < 0)):
            raise DefinitionError(f"{label}: {key} must be an integer (lengths must be nonnegative)")
    if "enum" in prop:
        values = prop["enum"]
        if not isinstance(values, list) or not values or not all(_matches(v, prop) for v in values):
            raise DefinitionError(f"{label}: enum must be a nonempty array matching the property type")
    if "default" in prop and not _matches(prop["default"], prop):
        raise DefinitionError(f"{label}: default must match the property type")


def _validate_schema(schema):
    _keys(schema, ("type", "properties", "required", "description"), "input_schema")
    if schema.get("type") != "object":
        raise DefinitionError("input_schema type must be object")
    properties = schema.get("properties", {})
    _object(properties, "properties")
    for name, prop in properties.items():
        if name in RESERVED:
            raise DefinitionError(f"reserved property name: {name}")
        _validate_property(prop, name)
    if "description" in schema and not isinstance(schema["description"], str):
        raise DefinitionError("schema description must be a string")
    if "required" in schema:
        required = schema["required"]
        if (not isinstance(required, list)
                or not all(isinstance(key, str) and key in properties for key in required)
                or len(set(required)) != len(required)):
            raise DefinitionError("required must contain unique declared property names")


def _validate_endpoint(endpoint, schema, annotations):
    _keys(endpoint, ("path", "method", "param_map", "array_format"), "endpoint")
    path = endpoint.get("path")
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
            or "\\" in path or ":" in path or CONTROL.search(path)):
        raise DefinitionError("endpoint path must be same-origin, start with /, and contain no // prefix, backslash, colon or control character")
    method = endpoint.get("method")
    if not isinstance(method, str) or method.upper() not in ("GET", "POST", "PATCH", "PUT", "DELETE"):
        raise DefinitionError("endpoint method must be GET, POST, PATCH, PUT or DELETE")
    method = method.upper()
    if method == "GET" and annotations.get("read_only") is not True:
        raise DefinitionError("GET endpoints require read_only: true")
    mapping = endpoint.get("param_map", {})
    _object(mapping, "param_map")
    properties = schema.get("properties", {})
    for key, destination in mapping.items():
        if key not in properties:
            raise DefinitionError(f"param_map key is not in schema properties: {key}")
        if (not isinstance(destination, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", destination)
                or destination in FORBIDDEN_PARAMS):
            raise DefinitionError(f"invalid or reserved param_map destination: {destination!r}")
    destinations = [mapping.get(key, key) for key in properties]
    if len(set(destinations)) != len(destinations):
        raise DefinitionError("param_map destinations collide")
    array_format = endpoint.get("array_format")
    if array_format is not None and array_format not in ("brackets", "repeat"):
        raise DefinitionError("array_format must be brackets or repeat")
    if array_format is None and method == "GET" and any(p["type"] == "array" for p in properties.values()):
        array_format = "repeat"
    return {"path": path, "method": method, "param_map": mapping, "array_format": array_format}


@dataclass(frozen=True)
class Tool:
    """A reviewed browser contract, copied and deeply frozen at construction."""

    name: str
    description: str
    input_schema: Mapping
    endpoint: Mapping
    annotations: Mapping = field(default_factory=dict)
    title: str | None = None
    max_response_chars: int | None = None

    def __post_init__(self):
        values = {key: _normalize(getattr(self, key)) for key in self.__dataclass_fields__}
        validate_name(values["name"])
        description = values["description"]
        if not isinstance(description, str) or not description:
            raise DefinitionError("description must be a nonempty string")
        if values["title"] is not None and not isinstance(values["title"], str):
            raise DefinitionError("title must be a string")
        _validate_schema(values["input_schema"])
        annotations = values["annotations"]
        _object(annotations, "annotations")
        if annotations.keys() - ANNOTATIONS.keys():
            raise DefinitionError("MCP and WebMCP annotation sets differ; WebMCP accepts only read_only, untrusted_content, consequential, debugging; MCP hints are not mapped")
        if any(type(value) is not bool for value in annotations.values()):
            raise DefinitionError("annotations must be booleans")
        values["endpoint"] = _validate_endpoint(values["endpoint"], values["input_schema"], annotations)
        limit = values["max_response_chars"]
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise DefinitionError("max_response_chars must be a positive integer")
        for key, value in values.items():
            object.__setattr__(self, key, _freeze(value))
        if len(self.name) > 30:
            logger.warning("WebMCP name exceeds Chrome's recommended 30-character budget: %s", self.name)
        if len(self.description) > 500:
            logger.warning("WebMCP description exceeds Chrome's recommended 500-character budget: %s", self.name)

    def to_manifest_entry(self, transport):
        from .manifest import fingerprint, normalize_transport

        entry = {
            "name": self.name, "description": self.description,
            "inputSchema": _thaw(self.input_schema),
            "annotations": {ANNOTATIONS[key]: True for key, value in self.annotations.items() if value},
            "endpoint": {"path": self.endpoint["path"], "method": self.endpoint["method"]},
        }
        if self.title is not None:
            entry["title"] = self.title
        if self.max_response_chars is not None:
            entry["maxResponseChars"] = self.max_response_chars
        if self.endpoint["param_map"]:
            entry["endpoint"]["paramMap"] = _thaw(self.endpoint["param_map"])
        if self.endpoint["array_format"] is not None:
            entry["endpoint"]["arrayFormat"] = self.endpoint["array_format"]
        entry["fingerprint"] = fingerprint({**entry, "transport": normalize_transport(transport)})
        return entry


_registry = {}
_registry_lock = RLock()
_registry_frozen = False


def register(tool):
    """Register a definition at boot; registration alone never exposes it."""
    if not isinstance(tool, Tool):
        raise DefinitionError("register requires a Tool")
    with _registry_lock:
        if _registry_frozen:
            raise DefinitionError("tool registry is frozen")
        if tool.name in _registry:
            raise DefinitionError(f"duplicate tool name: {tool.name}")
        _registry[tool.name] = tool
    return tool


def get_tool(name):
    validate_name(name)
    with _registry_lock:
        if name not in _registry:
            raise DefinitionError(f"unknown tool name: {name}")
        return _registry[name]


def freeze_registry():
    """Optionally close registration after all application tools are loaded."""
    global _registry_frozen
    with _registry_lock:
        _registry_frozen = True
