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

## Implementation notes — SonarCloud review findings (post-landing)

SonarCloud analysis of the integrated change (PR #4241). The per-PR `SonarCloud`
job is `continue-on-error` / outside `quality-gate.needs` — reported, not
required — and the **enforced** per-PR coverage gate (`ci-aggregate.yml`
diff-cover ≥90%) passed; the notes below are the standing Sonar findings and
their disposition.

### F1 — `python:S3776` [CRITICAL] `kind_vocabulary.resolve_config_id` cognitive complexity 19 > 15

- **Cause:** WP01's per-resolution memo threads cache-key build + cache-hit
  early-return + cache-miss scan-then-store branches **nested inside** the
  existing directive round-trip / ambiguity logic. Cognitive complexity
  penalises nesting, so it rose to 19.
- **Note the metric split:** `ruff` C901 (cyclomatic ≤15) is **clean** — the
  memo added little cyclomatic branching. Sonar S3776 is *cognitive*; the two
  diverge here (CLAUDE.md treats them as aligned, but nesting can separate
  them). This is not a ruff/mypy regression.
- **Disposition: REMEDIATED in this PR.** Extracted the directive round-trip +
  cross-layer ambiguity check into a flat helper `_directive_stem_represents`,
  inverted the id-match guard, and early-returned the non-directive case. This
  drops `resolve_config_id`'s nesting from 4 to 2 (the deep checks now live in a
  flat helper), reducing cognitive complexity ≤15 by inspection; behaviour is
  unchanged (the full directive suite stays green). Server-side S3776 confirmation
  will arrive via the nightly/main Sonar analysis once merged (the per-PR Sonar
  scan is blinded by #4248).

### F2 — `new_coverage` 65% < 80% (Sonar new-code threshold)

- **Where:** `kind_vocabulary.py` file coverage 95.1% (8 uncovered lines, ~4 of
  them in the new memo region — the cache-miss store path, the malformed-URN
  guard, and the `_directive_ids_by_stem` tail); `resolver.py` is **100%**
  covered (0 uncovered). The scan-count + mtime tests exercise the hit path and
  the outcome path but not every new guard/branch line.
- **Disposition: REMEDIATED in this PR.** Added focused tests for the previously
  new-uncovered branches (malformed-URN guard, unknown-kind guard, non-directive
  early-return); combined charter coverage of `kind_vocabulary.py` is now 95%, and
  every line this PR adds is covered (the 9 remaining uncovered lines are all
  pre-existing code outside this PR's diff). The enforced diff-cover ≥90% gate
  already passed; this closes the advisory Sonar `new_coverage` for the new code.

### F3 — No new bugs/vulnerabilities/hotspots

- Sonar reliability / security / maintainability / duplication / hotspots-reviewed
  conditions all **OK** on the new code; `resolver.py` carries 0 open issues.
  (Pre-existing `S1192` on `compiler.py` is unrelated main code, not this PR.)
