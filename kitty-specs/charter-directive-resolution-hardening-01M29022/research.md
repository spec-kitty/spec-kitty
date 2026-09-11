# Research: charter directive-resolution hardening

## Decision 1 — Memoization scope for directive resolution (#4239)

**Decision**: Memoize the per-layer artifact scan keyed on `(resolved_path, mtime_ns)`
so repeated `resolve_artifact_urn` calls within one `resolve_config_id` pass reuse a
single walk per layer. A resolution-pass-scoped cache is the fallback if a global
`(path, mtime)` cache proves fiddly, since the acceptance test only requires "each
layer walked once per pass" + mtime-correct invalidation across passes.

**Rationale**: `resolve_config_id`'s directive branch round-trips every candidate stem
through `resolve_artifact_urn`, which re-globs all layers each time (O(D×S)). The
scan result is a pure function of `(path, directory mtime)`; memoizing it is safe and
outcome-preserving. mtime keying makes a later pass observe on-disk changes
(edge case 3 in the spec).

**Alternatives considered**: (a) do nothing — rejected, the repeated I/O is the issue.
(b) Precompute the whole stem→id map once and thread it everywhere — heavier surface
change; `_directive_ids_by_stem` already exists and can be lifted/reused. (c) `lru_cache`
without mtime — rejected, cannot invalidate on file change (correctness across passes).

**Constraint**: MUST NOT introduce a second ordering. `_iter_artifact_paths` stays the
sole high→low precedence authority (C-002); the memo caches its output, not a new order.

## Decision 2 — Diagnostic mechanism for the unresolvable-token fallback (#4240)

**Decision**: On `resolver.directives`' `except UnknownArtifactIdError` branch, when the
token is neither a known id nor stem-resolvable (the fully-unresolvable fallback that
calls `normalize_directive_id`), emit `logging.getLogger(__name__).warning(...)` naming
the raw token and the normalized form. The resolution result is unchanged.

**Rationale**: The fallback is best-effort legacy compat; the gap is observability, not
correctness — so a WARNING (not an exception/gate) is the right signal (C-003). Standard
`logging` matches the module's siblings and is testable via `caplog`.

**Alternatives considered**: (a) raise/refuse — rejected, would change resolution
outcome and break legacy-compat activation. (b) Print to stderr — rejected, not
capturable/structured like `logging`. (c) Surface only in `doctor doctrine` — deferred
as a possible follow-up; the per-resolution WARNING is the minimal fix the issue asks for.

**Test**: warning fires ONLY on the fully-unresolvable path; a token resolving by stem,
exact id, or known catalog id emits nothing (FR-004).

## Supply-chain

No dependency added/upgraded/removed — stdlib `logging` only. Supply-chain install-safety
directive (051) N/A for this mission.
