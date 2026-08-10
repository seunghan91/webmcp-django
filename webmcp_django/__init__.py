"""webmcp-django — Django toolkit for WebMCP (W3C Web Model Context Protocol).

Status: early development. The WebMCP spec is in Chrome origin trial
(Chrome 149-156) and its surface is still moving; this package tracks the
spec and will ship its first usable release once the API stabilizes.

Planned surface:
    - Tool definitions in Python, shared between server-side MCP and WebMCP
    - Declarative template tag helpers (toolname/tooldescription/...)
    - Django middleware for serving the Origin-Trial token header
"""

__version__ = "0.1.0"
