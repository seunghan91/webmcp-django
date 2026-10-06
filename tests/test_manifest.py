import hashlib
import json
from pathlib import Path

import pytest
from django.http import QueryDict
from django.utils.safestring import mark_safe
from urllib.parse import urlencode

from webmcp_django.manifest import build, fingerprint, to_script_tag
from webmcp_django.tools import DefinitionError, Tool

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = sorted((ROOT / "conformance/fixtures").glob("*.json"))


def minimal(**kwargs):
    return Tool(**{
        "name": "test", "description": "Test", "input_schema": {"type": "object"},
        "endpoint": {"path": "/", "method": "POST"}, **kwargs,
    })


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_conformance_fixture(path):
    fixture = json.loads(path.read_text())
    actual = build([Tool(**fixture["definition"])], transport=fixture["transport"])
    assert json.loads(json.dumps(actual)) == {
        "webmcpManifestVersion": 1, "transport": fixture["transport"], "tools": [fixture["expected"]],
    }


def test_runtime_hash():
    expected, path = (ROOT / "conformance/RUNTIME.sha256").read_text().split()
    assert path == "webmcp_django/static/webmcp_django/webmcp-runtime.js"
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected


def test_manifest_optionals_annotations_and_transport():
    entry = build([minimal(annotations={"read_only": False, "debugging": True})])["tools"][0]
    assert entry["annotations"] == {"debugging": True}
    assert set(entry) == {"name", "description", "inputSchema", "annotations", "endpoint", "fingerprint"}
    assert entry["endpoint"] == {"path": "/", "method": "POST"}
    assert build([])["transport"] == {"csrf": {"source": "meta", "name": "csrf-token", "header": "X-CSRFToken"}}
    assert build([], transport={})["transport"] == {}
    assert build([minimal()])["tools"][0]["annotations"] == {}
    with pytest.raises(DefinitionError, match="duplicate"):
        build([minimal(), minimal()])


@pytest.mark.parametrize("transport", [
    [], {"other": 1}, {"csrf": {}}, {"csrf": None},
    {"csrf": {"source": "localStorage", "name": "x", "header": "X-X"}},
    {"csrf": {"source": "meta", "name": "", "header": "X-X"}},
    {"csrf": {"source": "meta", "name": "x\x7f", "header": "X-X"}},
    {"csrf": {"source": "meta", "name": "x", "header": "X-X\r\n"}},
    {"csrf": {"source": "meta", "name": "x", "header": 3}},
    {"csrf": {"source": "meta", "name": "x", "header": "X-X", "extra": True}},
])
def test_transport_validation(transport):
    with pytest.raises(DefinitionError):
        build([], transport=transport)


def test_fingerprint_covers_effective_contract_and_transport():
    tool = minimal()
    first = build([tool])["tools"][0]["fingerprint"]
    assert first != build([tool], transport={})["tools"][0]["fingerprint"]
    assert first != build([minimal(endpoint={"path": "/other", "method": "POST"})])["tools"][0]["fingerprint"]
    assert first != build([minimal(title="Title")])["tools"][0]["fingerprint"]
    assert fingerprint({"z": 1, "a": {"z": 2, "a": 3}}) == fingerprint({"a": {"a": 3, "z": 2}, "z": 1})
    assert fingerprint([1, 2]) != fingerprint([2, 1])
    # Literal preimage is independent of the serializer under test.
    preimage = '{"a":"한글</ScRiPt>&\u2028\u2029","z":1}'
    assert fingerprint({"z": 1, "a": "한글</ScRiPt>&\u2028\u2029"}) == "sha256:" + hashlib.sha256(preimage.encode()).hexdigest()


@pytest.mark.parametrize("safe", [False, True])
def test_script_escape_table_and_round_trip(safe):
    text = '</ScRiPt><!-->&\u2028\u2029한글'
    manifest = build([minimal(description=mark_safe(text) if safe else text)])
    html = str(to_script_tag(manifest))
    prefix = '<script type="application/json" id="webmcp-manifest" data-webmcp-autostart>'
    assert html.startswith(prefix)
    payload = html[len(prefix):-len("</script>")]
    for character in "<>&\u2028\u2029":
        assert character not in payload
    for escaped in (r"\u003c", r"\u003e", r"\u0026", r"\u2028", r"\u2029"):
        assert escaped in payload
    assert json.loads(payload) == manifest
    assert "data-webmcp-autostart" not in to_script_tag(manifest, autostart=False)
    assert 'nonce="&quot;&lt;&amp;"' in to_script_tag(manifest, nonce=mark_safe('"<&'))


def test_get_array_repeat_round_trip():
    tool = minimal(
        input_schema={"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
        endpoint={"path": "/", "method": "GET"}, annotations={"read_only": True},
    )
    assert build([tool])["tools"][0]["endpoint"]["arrayFormat"] == "repeat"
    values = ["alpha", "two words", "a&b", "한글", "", "alpha"]
    # URLSearchParams.append(name, String(item)): repeated unbracketed keys.
    query = urlencode([("tags", value) for value in values])
    assert query.startswith("tags=alpha&tags=two+words&tags=a%26b")
    assert QueryDict(query).getlist("tags") == values
