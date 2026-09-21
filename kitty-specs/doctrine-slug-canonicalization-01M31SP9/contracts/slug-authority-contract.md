# Contract: slug authority (`slug_for`) + cross-surface convergence

## `slug_for(kind: str, identifier: str) -> str`
- **Pure**: deterministic, no IO, no global state. Same `(kind, identifier)` → same slug.
- **Rule** (extracted verbatim from `src/charter/activation/project_registration.py:187`):
  - `kind == "directive"` → `quote(identifier.lower().replace("_", "-"), safe="")`.
  - any other kind → `quote(identifier, safe="")`.
- **`quote(…, safe="")` is load-bearing, not decoration** (post-plan squad CRITICAL): it collapses a slash-bearing URN identity (e.g. `agent_profile:team/ops-responder`) into a single safe path component, so `provenance_path_for(kind, slug)` cannot escape `.kittify/charter/provenance/`. Dropping it regresses the existing guard `tests/charter/test_project_registration.py:165-166` (asserts the encoded `team%2Fops-responder` form and the pinned parent dir). Do NOT "simplify" it away.
- **id-grammar precondition**: directives match `^[A-Z][A-Z0-9_-]*$`; non-directive ids are lowercase-kebab and URN-safe (`project_scan.py` enforces). Under this grammar `quote()` is a no-op for well-formed ids, but it is retained as defense-in-depth.
- **Guarantee**: for a directive id matching `^[A-Z][A-Z0-9_-]*$`, the result never begins with a pure-digit segment (ids require a leading letter), so a downstream optional `NNN-` prefix strip cannot truncate it.

## Convergence invariant (the anti-drift guarantee)
For every registration-writing kind and any valid id:
```
scaffolder_filename_stem(kind, id) == slug_for(kind, id)
registration_slug(kind, id)        == slug_for(kind, id)
validator_slug_for(registered artifact) == manifest.slug   # not re-derived from filename
```
- The scaffolder (`doctrine.py::_artifact_filename`) and the engine (`project_registration.py`) both call `slug_for` — there is exactly one producer-side slug derivation.
- **Test**: a parametrized convergence test asserts scaffolder == engine == manifest slug for a SCREAMING directive id and for a kebab non-directive id.

## Non-directive preservation (C-002)
`slug_for("agent_profile", "retrospective-facilitator") == "retrospective-facilitator"` (already-kebab id, `quote` a no-op). No case-folding of non-directive kinds. For a namespaced id, `slug_for("agent_profile", "team/ops-responder") == "team%2Fops-responder"` (quoted — no path escape).
