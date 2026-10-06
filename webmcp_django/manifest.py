"""Manifest v1 serialization, effective-contract fingerprints and safe HTML."""

import hashlib
import json

from django.utils.html import escape
from django.utils.safestring import mark_safe

from .tools import CONTROL, DefinitionError, Tool, _keys, _normalize


_DEFAULT_TRANSPORT = {"csrf": {"source": "meta", "name": "csrf-token", "header": "X-CSRFToken"}}
_ESCAPES = str.maketrans({
    "<": r"\u003c", ">": r"\u003e", "&": r"\u0026",
    "\u2028": r"\u2028", "\u2029": r"\u2029",
})


def normalize_transport(transport):
    transport = _normalize(transport)
    _keys(transport, ("csrf",), "transport")
    if "csrf" in transport:
        csrf = transport["csrf"]
        _keys(csrf, ("source", "name", "header"), "csrf")
        if csrf.get("source") not in ("meta", "cookie") or not all(
            isinstance(csrf.get(key), str) and csrf[key] and not CONTROL.search(csrf[key])
            for key in ("name", "header")
        ):
            raise DefinitionError("csrf requires source meta/cookie and nonempty name/header without control characters")
    return transport


def fingerprint(value):
    preimage = json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def build(tools, *, transport=None):
    """Build only the supplied tools; omitted transport uses Django CSRF meta."""
    transport = normalize_transport(_DEFAULT_TRANSPORT if transport is None else transport)
    entries = []
    names = set()
    for tool in tools:
        if not isinstance(tool, Tool):
            raise DefinitionError("manifest tools must be Tool definitions")
        if tool.name in names:
            raise DefinitionError("duplicate tool names in manifest")
        names.add(tool.name)
        entries.append(tool.to_manifest_entry(transport))
    return {"webmcpManifestVersion": 1, "transport": transport, "tools": entries}


def to_script_tag(manifest, *, autostart=True, nonce=None):
    """Embed JSON using the exact manifest v1 escape table, even for SafeString."""
    payload = json.dumps(_normalize(manifest), separators=(",", ":"), ensure_ascii=False).translate(_ESCAPES)
    start_attr = " data-webmcp-autostart" if autostart else ""
    nonce_attr = "" if nonce is None else f' nonce="{escape(nonce)}"'
    return mark_safe(f'<script type="application/json" id="webmcp-manifest"{start_attr}{nonce_attr}>{payload}</script>')
