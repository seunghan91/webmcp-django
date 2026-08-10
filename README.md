# webmcp-django

Django toolkit for [WebMCP](https://github.com/webmachinelearning/webmcp) —
the W3C proposal that lets web pages declare structured tools for AI agents
(`document.modelContext`).

**Status: early development.** The WebMCP spec is in Chrome origin trial
(Chrome 149–156) and its API surface has already changed twice. This package
ships the pieces that are stable enough to use today — an `Origin-Trial`
header middleware and declarative template tags — and will grow alongside
the spec.

## Install

```bash
pip install webmcp-django
```

## Setup

Add the middleware to `MIDDLEWARE` to serve the `Origin-Trial` token header
required by Chrome's origin trial:

```python
# settings.py
MIDDLEWARE = [
    ...
    "webmcp_django.middleware.OriginTrialMiddleware",
]

WEBMCP_ORIGIN_TRIAL_TOKEN = "your-origin-trial-token"
```

When `WEBMCP_ORIGIN_TRIAL_TOKEN` is unset, the middleware is a no-op.

Add `webmcp_django` to `INSTALLED_APPS` to use the template tags:

```python
INSTALLED_APPS = [
    ...
    "webmcp_django",
]
```

## Usage

```django
{% load webmcp %}

<form {% webmcp_tool "create_task" "Create a new task" autosubmit=True %}>
  <input name="title" {% webmcp_param "The task title" %}>
</form>
```

renders:

```html
<form toolname="create_task" tooldescription="Create a new task" toolautosubmit>
  <input name="title" toolparamdescription="The task title">
</form>
```

Values are always HTML-escaped, including values pre-marked as safe with
`mark_safe` — the tags call `escape()` unconditionally, which ignores
Django's "safe" marking, so a caller cannot smuggle unescaped markup into
tool metadata.

## Security: tool metadata is agent-visible

`tooldescription` and `toolparamdescription` aren't just display text — an
AI agent reads them as instructions describing what the tool does. Don't
build these strings from unvalidated user input (profile fields, query
params, uploaded file names, etc.). A user-controlled value rendered into
tool metadata is a prompt-injection vector that can hijack the agent's
behavior through your own tool declarations. Keep tool names and
descriptions as literal strings you write, not values derived at request
time from data a visitor controls.

## License

MIT
