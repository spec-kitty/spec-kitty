---
title: ADR 2026-05-18-2 — DELETE specify_cli.auth.transport (deferred to Robert)
description: 'Deletes the auth transport module: it has zero production callers and its architectural gate passes vacuously, so it mediates nothing that it claims to mediate.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-05-18'
---

## Context

`src/specify_cli/auth/transport.py` ships as part of the spec-kitty CLI but has
zero non-test callers in the current codebase. Verified at HEAD `6ae8d449`:

```bash
rg "from specify_cli.auth.transport" src/specify_cli/
# returns 0 matches

rg "import specify_cli.auth.transport" src/specify_cli/
# returns 0 matches
```

Alternate HTTP paths exist in `src/specify_cli/sync/` and
`src/specify_cli/tracker/`, which use their own `httpx.AsyncClient` instances
directly. The `test_auth_transport_singleton.py` architectural gate passes
vacuously: its `_ALLOWED_DIRECT_HTTPX_FILES` allowlist carries 2 entries that
do not currently route through the module.

This is a C4 contradiction: the module claims to mediate auth-transport but
mediates nothing. It introduces surface area (an `AuthTransport` singleton)
with no active enforcement.

---

## Audit Evidence

- **Zero callers:** `rg "from specify_cli.auth.transport" src/specify_cli/`
  returns 0 matches. `rg "from .*auth.transport import\|import .*auth\.transport"`
  confirms this across the full `src/` tree.
- **Vacuous singleton gate:** `tests/architectural/test_auth_transport_singleton.py`
  asserts the singleton pattern and lists 2 allowed files in
  `_ALLOWED_DIRECT_HTTPX_FILES`. Neither of those files currently routes through
  the `AuthTransport` module; the allowlist was grandfathered from a prior
  design that was never fully wired.
- **Sync subsystem:** `src/specify_cli/sync/` uses its own `httpx.AsyncClient`
  directly without going through `AuthTransport`.
- **Tracker subsystem:** `src/specify_cli/tracker/` manages its own request
  flow; `AuthTransport` is not in the call chain.
- **No public API surface:** `src/specify_cli/auth/__init__.py` does not
  re-export `AuthTransport`; it is not part of any declared public facade.

---

## Recommendation

**DELETE** `src/specify_cli/auth/transport.py` and remove
`tests/architectural/test_auth_transport_singleton.py` (vacuous gate).

Additionally:
- Remove the `allowed_direct_httpx_files: 2` baseline from
  `tests/architectural/_baselines.yaml`.
- Update any import in `src/specify_cli/auth/__init__.py` that references
  `transport` (if any).
- Verify the full architectural suite still passes after deletion.

---

## Deferral Rationale (HiC §5a.3, binding via C-005)

Verbatim HiC adjudication (2026-05-18):

> "Delete, but explicitly create an ADR for it, which is to be updated mentioning
> the code that is deleted, and the commit in which it happened. In general: we
> want to be extremely careful with auth-path cleanup as Robert (lead maintainer)
> has indicated the SaaS platform has had recent auth-related challenges. It
> would be best to highlight this, add our research / evidence and
> recommendations, but leave the decision and clean-up action to Robert.
> (descope from our proposed mission scope, but create a ticket with our
> findings)."

Per C-005 (binding for the Slice F mission): **Slice F MUST NOT modify
`src/specify_cli/auth/transport.py` or
`tests/architectural/test_auth_transport_singleton.py`.** Deletion is Robert's
call after reviewing this ADR and the linked GitHub ticket.

---

## Reserved Fields for Robert

**Deleted in commit:** `<SHA>` *(to be filled when deletion happens)*
**Deletion PR:** `<URL>` *(to be filled)*
**Date of deletion:** `<DATE>` *(to be filled)*

---

## Related

- **GitHub ticket:** `Priivacy-ai/spec-kitty#1118` — https://github.com/Priivacy-ai/spec-kitty/issues/1118
- **spec.md:** FR-200, FR-201, FR-202, C-005, AC-12, AC-13
- **HiC §5a.3** adjudication record (verbatim above)
- **Slice F mission:** `slice-f-multi-context-extensibility-01KRX5C8`
- **WP12 close-out commit:** see `git log --grep="WP12"` on lane-a branch
