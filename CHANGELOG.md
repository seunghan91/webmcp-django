# Changelog

## 0.2.2 — 2026-10-06

- Documentation for people and AI agents: `AGENTS.md`, `llms.txt`, a README troubleshooting table with exact error messages, and more PyPI keywords. No behaviour changes.

## 0.2.1 — 2026-10-06

- Documentation and packaging metadata: PyPI summary no longer says "early development"; README leads with what the package does, install, status and the four-package family; changelog/issue links; CI. No code changes.

## 0.2.0 — 2026-10-06

- Add frozen, validated Tool definitions and an explicit page-selected registry.
- Add manifest v1, canonical SHA-256 fingerprints, safe JSON script embedding,
  CSRF meta, Origin Trial meta, and nonce-aware external runtime tags.
- Ship the unchanged shared browser runtime with checksum and golden fixtures.
- Default Django GET arrays to repeat encoding and CSRF to meta/X-CSRFToken.
- Add an opt-in, once-per-process OAC opt-out warning without rewriting headers.
- Preserve valid declarative tag output; reject invalid tool names at render time.
- Require Python >=3.10; support Django 4.2 LTS and 5.x with no other runtime dependencies.
- Add conformance, escaping, immutable-definition and enforced-CSRF integration tests.
