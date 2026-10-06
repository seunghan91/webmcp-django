# webmcp-django

[![PyPI](https://img.shields.io/pypi/v/webmcp-django)](https://pypi.org/project/webmcp-django/) [![Python](https://img.shields.io/pypi/pyversions/webmcp-django)](https://pypi.org/project/webmcp-django/) [![CI](https://github.com/seunghan91/webmcp-django/actions/workflows/ci.yml/badge.svg)](https://github.com/seunghan91/webmcp-django/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Server-side WebMCP toolkit for Django — Django is the only dependency.

[WebMCP](https://github.com/webmachinelearning/webmcp) is a W3C Community Group
proposal that lets a web page register tools an in-browser AI agent can call
through `document.modelContext`. This package is the server side of that: you define
tools where your app already knows its routes, sessions and permissions, and a
small browser runtime registers them on the pages you choose. When an agent calls
a tool, the runtime calls your existing same-origin endpoint with the user's
session and CSRF token, so authentication and authorization stay in your app.

- **Tool definitions** — `webmcp_django.tools.Tool` and `register`, validated against the spec's naming, annotation and schema rules.
- **Template tags** — `{% webmcp_manifest "list_tasks" %}` (per-page opt-in), `{% webmcp_runtime %}` (CSP nonce aware, autostart), `{% webmcp_csrf_meta %}` (works with `CSRF_COOKIE_HTTPONLY`).
- **Declarative forms** — `{% webmcp_tool %}` and `{% webmcp_param %}` with unconditional escaping.
- **Origin Trial** — `OriginTrialMiddleware` and `{% webmcp_origin_trial_meta %}`.
- **Shared browser runtime** — shipped as a static file; same-origin only, CSRF read per call, declared parameters only, no retries.

```sh
pip install webmcp-django
```

**Status:** 0.x, tracking the WebMCP Draft CG Report of 2026-10-02. WebMCP runs
behind a Chrome origin trial (Chrome 149–156, extension requested to 162) or the
`chrome://flags/#enable-webmcp-testing` flag. The shared runtime is tested in real
Chrome 154 by the [Ruby reference suite](https://github.com/seunghan91/webmcp/blob/main/test/integration/RESULTS.md)
(CSRF-protected writes, blocked redirects, HTTP errors, Turbo navigation, strict CSP).

| Language | Package | Registry |
|---|---|---|
| Ruby / Rails (reference) | [`webmcp`](https://github.com/seunghan91/webmcp) | [RubyGems](https://rubygems.org/gems/webmcp) |
| Go (`net/http`) | [`webmcp-go`](https://github.com/seunghan91/webmcp-go) | [pkg.go.dev](https://pkg.go.dev/github.com/seunghan91/webmcp-go) |
| Python / Django | [`webmcp-django`](https://github.com/seunghan91/webmcp-django) | [PyPI](https://pypi.org/project/webmcp-django/) |
| Rust | [`webmcp`](https://github.com/seunghan91/webmcp-rust) | [crates.io](https://crates.io/crates/webmcp) |

All four emit the same manifest v1 (checked against shared conformance fixtures,
fingerprints included) and ship the byte-identical browser runtime.

Coding agents: start with [AGENTS.md](AGENTS.md). LLM summary: [llms.txt](llms.txt).

## Intent: share identity, project the rest explicitly

**Surfaces are intentionally different; share identity, project the rest explicitly.**
A server MCP tool and its browser counterpart can represent the same feature
while intentionally having different schemas, limits, and execution paths.

| Difference | Server MCP | Browser WebMCP | Reason |
|---|---|---|---|
| Field names | `content`, `id` | `title`, `task_id` | Match visible labels for browser agents. |
| Dates | ISO 8601 | `YYYY-MM-DD HH:MM` in the user's timezone | Match what the user sees. |
| Result limit | 500 | 20 | Fit the browser response budget and tab context. |
| Execution path | Service object → database | Session cookies → existing web endpoint | Preserve session, CSRF and authorization checks. |

Share identity and reviewed descriptions; declare schema, limits, field mappings,
annotations and endpoints explicitly for each surface. MCP and WebMCP annotations
are different sets: `destructiveHint` is not automatically `consequentialHint`.
Even `read_only` must describe the browser endpoint itself. The Ruby reference
provides `from_mcp`-style projection; a Django SDK bridge is planned, not included.

## Quick start

Python >= 3.10; Django 4.2 LTS or 5.x. Django is the only runtime dependency.

```sh
pip install 'webmcp-django>=0.2,<0.3'
```

```python
# settings.py — retain your existing apps and middleware, including CSRF protection.
INSTALLED_APPS = [
    # ...
    "django.contrib.staticfiles",
    "webmcp_django",
]
MIDDLEWARE = [
    # ...
    "django.middleware.csrf.CsrfViewMiddleware",
    "webmcp_django.middleware.OriginTrialMiddleware",
]
STATIC_URL = "/static/"
WEBMCP_ORIGIN_TRIAL_TOKEN = "YOUR_ORIGIN_TRIAL_TOKEN"
WEBMCP_WARN_ON_OAC_OPT_OUT = True  # Optional, logs once per process.
```

Define and register tools at boot (for example, import your tool module from
`AppConfig.ready()`):

```python
from webmcp_django.tools import Tool, register, freeze_registry

register(Tool(
    name="list_tasks",
    title="List tasks",
    description="List at most 20 tasks for the signed-in user.",
    input_schema={
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}},
            "completed": {"type": "boolean"},
        },
    },
    annotations={"read_only": True, "untrusted_content": True},
    endpoint={"path": "/api/tasks", "method": "GET"},
    max_response_chars=1500,
))
register(Tool(
    name="create_task",
    description="Create one task.",
    input_schema={
        "type": "object",
        "properties": {"title": {"type": "string", "maxLength": 120}},
        "required": ["title"],
    },
    annotations={"consequential": True},
    endpoint={"path": "/api/tasks", "method": "POST", "param_map": {"title": "content"}},
))
# Call once after ALL application tool modules have been imported.
freeze_registry()
```

Definitions are copied and deeply frozen; invalid metadata and duplicate names
raise `DefinitionError` (a `ValueError`). Registration does not expose tools.
Only explicitly listed tools appear on a page; no names means no tools.

```django
{% load webmcp %}
{% webmcp_csrf_meta %}
{% webmcp_manifest "list_tasks" "create_task" %}
{% webmcp_runtime %}
```

Render with a request, e.g. `render(request, "tasks.html", context)`. The CSRF
helper obtains a masked token from that request and works with
`CSRF_COOKIE_HTTPONLY=True`; keep `CsrfViewMiddleware` enabled. The default
transport is `{"csrf":{"source":"meta","name":"csrf-token","header":"X-CSRFToken"}}`.
Writes use JSON bodies, so endpoints should parse `request.body` as JSON rather
than expecting Django's form-only `request.POST`.

The manifest has `data-webmcp-autostart` by default. The external module starts
it without inline executable JavaScript. The runtime helper resolves
`static('webmcp_django/webmcp-runtime.js')`; deploy it with your normal static
files/`collectstatic` setup. Both script helpers include an escaped
`request.csp_nonce` when present. For manual ownership, render
`{% webmcp_manifest "list_tasks" autostart=False %}` and import from your
application's external JavaScript entry:

```javascript
import { mount } from "/static/webmcp_django/webmcp-runtime.js";
const handle = mount({ selector: "#webmcp-manifest" });
// After replacing the manifest in an SPA:
handle.refresh();
// When its owner is removed:
handle.dispose();
```

Adapt the import URL to your static storage. Turbo refresh is built into the
runtime; other SPAs must call `refresh()` explicitly. Autostart exposes its handle
as `globalThis.WebMCPRuntime.handle`. Unsupported browsers are a no-op.

### Existing declarative tags and Origin Trial

```django
{% load webmcp %}
{% webmcp_origin_trial_meta %}
<form method="post" {% webmcp_tool "create_task" "Create a new task" autosubmit=True %}>
  {% csrf_token %}
  <input name="title" {% webmcp_param "The task title" %}>
</form>
```

Valid existing usage keeps the same output. Tool names must now satisfy
1..128 ASCII letters, digits, `_`, `.` or `-`. Only `toolname`, `tooldescription`,
`toolautosubmit` (boolean attribute), and `toolparamdescription` are emitted.
Values are always HTML-escaped, including `mark_safe` values.

The middleware fills only a missing `Origin-Trial` header, preserving even an
existing empty header. An empty configured token is a pass-through. With a token
configured, `WEBMCP_WARN_ON_OAC_OPT_OUT=True` logs once per process for
`Origin-Agent-Cluster: ?0`; the middleware never rewrites OAC or forces `?1`.
The meta helper is an alternative token delivery mechanism and emits nothing
when no token is configured.

### Building manifests directly

```python
from webmcp_django.manifest import build, to_script_tag
from webmcp_django.tools import get_tool

manifest = build([get_tool("list_tasks")])
html = to_script_tag(manifest, autostart=False, nonce="YOUR_CSP_NONCE")
# Override transport explicitly if your application uses another CSRF source:
manifest = build([get_tool("create_task")], transport={
    "csrf": {"source": "cookie", "name": "csrftoken", "header": "X-CSRFToken"},
})
```

Cookie transport requires a JavaScript-readable cookie. `transport={}` explicitly
omits CSRF transport; it is intended for read-only integrations. Template calls
can pass `transport=transport_config`. Empty `paramMap`, absent `title`, and absent
`maxResponseChars` are omitted; only true annotations are emitted. Fingerprints
include the effective tool entry and transport, using recursively sorted compact
UTF-8 JSON without HTML escaping. Script embedding applies escaping separately.

## Troubleshooting

| Symptom (exact text) | Cause | Fix |
|---|---|---|
| `document.modelContext` is `undefined` | WebMCP is unavailable or the page is not a secure context | Chrome 149+ with the origin trial token (header or `<meta http-equiv="origin-trial">`) or `chrome://flags/#enable-webmcp-testing`; serve over HTTPS or localhost |
| `NotAllowedError` from `registerTool` | The document may not use the `tools` Permissions Policy feature (default allowlist `self`) | For cross-origin frames delegate with `allow="tools"` and make sure ancestor `Permissions-Policy` headers permit it |
| `UnknownError: Failed to parse input arguments` from `executeTool` | Chrome 154 and earlier accept only a JSON **string** input; object input ships in Chrome 155 | Agent side: pass `JSON.stringify(input)` on Chrome ≤ 154. The runtime's `execute` receives an object either way |
| `SecurityError` from `registerTool` on an older trial build | The response sent `Origin-Agent-Cluster: ?0` (requirement removed from the spec on 2026-09-30, still enforced by older builds) | Stop sending `?0`; enable the OAC opt-out warning to find it |
| Console: `WebMCP: could not register tool "<name>"` with `InvalidStateError` | Another script in the same document already registered that name | Use unique names; names are unique per document, not per site |
| Console: `WebMCP: unsupported manifest version; no tools registered.` | Runtime and manifest come from different package versions | Upgrade so both use manifest v1 and the same runtime |
| Tool result `error.code: "csrf_token_missing"` | A non-GET tool (including a read-only POST) has CSRF transport configured but no readable token on the page | Render the configured token (Rails `csrf_meta_tags`, Django `{% webmcp_csrf_meta %}`, Go/Rust: your own escaped `<meta name="csrf-token">`) or configure a readable cookie source. Without CSRF transport the runtime skips this check |
| `error.code: "invalid_input"` | The agent sent an undeclared parameter, a missing required one, or the wrong scalar type | Fix the schema or descriptions; the runtime forwards declared parameters only |
| `error.code: "unknown_outcome"` | A write request failed after dispatch: network error, abort, or a **redirect** (redirects are never followed) | Make the endpoint answer without redirecting (e.g. 401 JSON instead of redirecting to sign-in); never retry automatically |
| `error.code: "network_error"` on a read | Network failure or redirect rejection after dispatch (an aborted read returns `aborted`) | Check connectivity and answer JSON without redirects; reads may be retried |
| `error.code: "response_too_large"` | Read response exceeded `maxResponseChars` | Narrow the query or raise the limit; responses are never truncated |
| `dataOmitted: "invalid_response"` on a write | The endpoint returned 2xx with a non-JSON body | Return JSON from write endpoints |
| Tools from the previous page remain, or none appear, after client-side navigation | Turbo is handled automatically; other SPAs (Inertia, React routers) are not | After the SPA replaces or removes `#webmcp-manifest`, `await WebMCPRuntime.handle.refresh()`. `webmcp:mounted` only delivers the initial handle. If the first page has no manifest, mount the runtime from your app entry (`mount()`) and keep that handle |
| A string-returning tool yields `hi` instead of `"hi"` | Chrome 154 does not JSON-quote string results (spec says it should) | The shared runtime always returns an envelope object, so this only affects hand-written tools |
| Definition error at boot such as `GET endpoints require read_only: true` | The definition violates a rule above | Fix the definition; errors are raised at boot on purpose |

## Security model


The server remains the security boundary. Tools call existing same-origin
endpoints with the current session; those endpoints must enforce authorization,
CSRF, input validation, range limits and result caps. A schema `maximum` is
metadata, not server enforcement. Annotations are hints, not security controls.

- Endpoint paths must begin with `/`; protocol-relative URLs, backslashes, colons
  and control characters are rejected. The runtime also checks the resolved
  origin and uses same-origin mode/credentials with redirects rejected.
- GET requires `read_only: true`; read-only POST is allowed. Other methods need a
  CSRF token read at invocation time. Missing tokens stop the request.
- Only declared input keys are sent. Prototype-related keys are rejected.
  Explicit `param_map` destinations cannot collide or target reserved transport
  fields such as `_method`, `authenticity_token`, or `csrfmiddlewaretoken`.
- JSON embedding escapes `<`, `>`, `&`, U+2028 and U+2029. This prevents script
  breakout, including mixed-case closing tags and HTML comments. Nonces and HTML
  attributes are independently escaped.
- The runtime returns structured success/error envelopes and never retries.
  An ambiguous write result is `unknown_outcome`: verify with the user before
  retrying. A successful write with unreadable/oversized output stays successful
  with `dataOmitted`; an oversized read returns `response_too_large`. Responses
  are never silently truncated.

**Tool metadata is agent-visible, not just display text.** An AI agent reads
`tooldescription` / `toolparamdescription` as part of its instructions for what
the tool does. Do not build these strings from unvalidated user input (profile
fields, query params, uploaded file names, etc.); a user-controlled value rendered
into tool metadata is a prompt-injection vector that can hijack the agent's
behavior. Keep tool names and descriptions as literal strings you write, not
values derived at request time from data a visitor controls. Define tools at boot
and freeze the registry; HTML escaping alone does not prevent prompt injection.


## Conformance

[Fixtures](conformance/fixtures) are copied verbatim from the
[Ruby reference](https://github.com/seunghan91/webmcp). Tests compare parsed
manifest entries, including fixed fingerprints, without regenerating expectations.
See [the contract](conformance/README.md). The shared runtime is copied unchanged
and checked against [RUNTIME.sha256](conformance/RUNTIME.sha256).

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]' build
.venv/bin/pytest -q
.venv/bin/python -m build
```

The suite covers definition validation, page opt-in, script/attribute escaping,
Django `QueryDict.getlist` array round trips, and real `CsrfViewMiddleware`
rejection/success through `Client(enforce_csrf_checks=True)` with HttpOnly cookies.
It does not claim live Chrome or production CSP validation.

## Limitations

This 0.x package implements a deliberate schema subset. Root schemas accept
`type: "object"`, `properties`, `required`, and `description`. Properties accept
`string`, `number`, `integer`, `boolean`, or arrays of scalars, with `enum`,
`description`, `default`, `minimum`, `maximum`, `maxLength`, and `maxItems` metadata.
Nested objects/arrays, `$ref`, composition and unknown keywords are rejected.
Metadata numbers must be integers within +/-2^53; floats are rejected. Runtime
`number` inputs may be fractional. The endpoint enforces bounds, lengths and enums.

GET requires `read_only=True`; read-only POST is allowed. GET array properties
emit `arrayFormat: "repeat"` by default (`tags=a&tags=b`, read using
`request.GET.getlist("tags")`). Set `endpoint["array_format"]` to `"brackets"`
only for endpoints that expect bracketed keys. The shared Ruby array fixture
explicitly selects brackets and therefore has the same fingerprint here.

No cross-origin exposure, MCP SDK bridge, automatic response truncation, or
Inertia adapter is included. The draft and browser implementation can change.

Sibling packages: [Ruby](https://github.com/seunghan91/webmcp),
[Go](https://github.com/seunghan91/webmcp-go),
[Django](https://github.com/seunghan91/webmcp-django),
[Rust](https://github.com/seunghan91/webmcp-rust).

## License

MIT
