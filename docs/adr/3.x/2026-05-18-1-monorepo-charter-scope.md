---
title: 'ADR-8: Monorepo charter scope via `CharterScope` abstraction'
description: 'Introduces CharterScope to resolve the nearest enclosing configured scope in a monorepo, while single-project behaviour stays byte-identical to the prior path.'
status: Accepted
date: '2026-05-18'
doc_status: active
kind: ADR
updated: '2026-05-18T00:00:00Z'
---

## Context

Slice F lifts spec-kitty's governance surface beyond a single repository.
Axis 1 (org-tier doctrine, WP04–WP08) lets organisations layer doctrine on top
of the shipped catalog. Axis 2 — the subject of this ADR — addresses the
operator request from issue #522: monorepos that ship multiple deployable
packages each want their **own** charter, scoped by the filesystem location of
the mission rather than by the repository root.

Concretely:

- A monorepo `myorg-platform/` contains `packages/auth/` and `packages/web/`.
- The auth team owns `packages/auth/.kittify/charter/charter.md` describing
  their security posture, language standards, and review policy.
- The web team owns `packages/web/.kittify/charter/charter.md` describing
  their frontend conventions.
- When a developer runs `spec-kitty implement WP01` from inside
  `packages/auth/some/deep/dir/`, the prompt must surface the **auth**
  charter, not the platform root.

Before WP09, `build_charter_context(repo_root, ...)` read the charter only
from `repo_root / .kittify / charter / charter.md`. Monorepo teams could
work around this with `cd packages/auth && spec-kitty implement WP01` (which
made `packages/auth` look like the root), but that fights every other
mechanism in the system (mission discovery, status events, worktrees) which
all consult the **actual** git root.

We need a first-class abstraction for "which charter applies to this
filesystem path", with a hard **byte-stability** guarantee for single-project
repositories — the 23 governance-contract fixtures locked by NFR-001 must
not change a single byte.

---

## Decision

Introduce a new abstraction at the charter layer: **`CharterScope`**, modelled
as a frozen dataclass living in `src/charter/scope.py`. It has exactly two
constructors and a small failure-mode surface:

1. `CharterScope.default(repo_root)` — single-project constructor.
   - `root = repo_root`
   - `name = None`
   - `config_source = "repo_root_default"`
   - Behaviour is **byte-identical to today** (NFR-001 binding).

2. `CharterScope.resolve(repo_root, feature_dir)` — monorepo-aware resolver.
   - If `repo_root/.kittify/config.yaml` is absent OR its `charter_scopes:`
     key is empty/missing, return `CharterScope.default(repo_root)`.
   - Otherwise, walk the configured scopes and return the **nearest enclosing
     ancestor** of `feature_dir`.
   - Raise `CharterScopeConflict` if two configured scopes have incompatible
     nesting depths (one is an ancestor of another and the feature_dir is
     under the deeper one — both scopes claim it).
   - Raise `CharterScopeNotFound` if `feature_dir` is not under any
     configured scope.

The operator-facing configuration shape lives in `.kittify/config.yaml`:

```yaml
charter_scopes:
  - root: packages/auth
    name: auth
  - root: packages/web
    name: web
```

It is opt-in. Repositories that omit `charter_scopes:` get exactly the
behaviour they have today.

To thread the resolver through the rendering pipeline without disturbing
`build_charter_context`'s signature (WP07's ownership boundary), we ship a
new thin wrapper module `src/charter/scope_router.py` exposing:

```python
def build_with_scope(repo_root: Path, feature_dir: Path, **kwargs) -> CharterContextResult:
    """Resolve the scope, then delegate to build_charter_context."""
    scope = CharterScope.resolve(repo_root, feature_dir)
    return build_charter_context(scope.root, feature_dir, **kwargs)
```

For single-project repos, `scope.root == repo_root` and the wrapper is a
no-op pass-through. For monorepos, the wrapper redirects to the
package-scoped charter root.

The Pydantic model `CharterScopeConfig` (plus the inner `_CharterScopeEntry`)
ships alongside in the same module. It validates the YAML payload at config
load time, rejecting empty `root` fields and surfacing structural errors with
a stable error shape. This satisfies the FR-140 round-trip case
`charter.scope.CharterScopeConfig` in `contracts/charter-scope-resolution.md`.

---

## Consequences

### Positive

- **Per-package charter scoping unblocked** for monorepo operators (issue
  #522). Auth and web teams own their own `charter.md` and the prompt
  renderer surfaces the right one based on `feature_dir`.
- **Zero impact on single-project repos** — NFR-001 binding. The 23
  `test_wp_prompt_governance_contract.py` fixtures pass unchanged because
  `CharterScope.default(repo_root)` produces byte-identical output.
- **Layer-rule clean** (NFR-003). `scope.py` and `scope_router.py` live in
  the charter layer and do not import from `specify_cli.*`. The
  prompt-builder wiring (WP11) reverses the dependency direction:
  `specify_cli.next.prompt_builder` calls into `charter.scope_router`, not
  the other way around.
- **Ownership clean.** `context.py` (owned by WP07) is untouched.
  `scope_router.py` is a new module owned by WP09. No cross-WP file
  conflicts.
- **Round-trip gate strengthened** (FR-140). The
  `charter.scope.CharterScopeConfig` round-trip case flips from `SKIPPED` to
  `PASSED`, removing one entry from the deferred-skips ledger.

### Negative

- **Operators must learn a new config key.** `charter_scopes:` is documented
  in `docs/explanation/charter-scope.md` (follow-up) and in the contract
  file. The single-project default behaviour means existing operators see
  nothing new until they choose to opt in.
- **Modest read-time cost.** Every `build_with_scope` call reads
  `.kittify/config.yaml`. Single-project repos pay one extra `stat` per
  prompt build (the file is absent and `Path.exists()` returns quickly).
  NFR-002 caps prompt-build latency regression at 20%; if measurement shows
  perceptible regression a module-level cache keyed by `repo_root` is a
  drop-in mitigation (deferred until measured).
- **Two ways to reach the same place.** Existing callers of
  `build_charter_context(repo_root, ...)` continue to work and continue to
  use the repo-root charter; only callers migrated to `build_with_scope`
  get monorepo support. This is intentional — the migration is
  call-site-by-call-site rather than a forced cutover.

### Neutral

- **`CharterScope` is a frozen dataclass, not a Pydantic model.** The
  validated configuration shape (`CharterScopeConfig`) is the Pydantic
  surface; the resolved runtime value is a small immutable record. This
  matches the data-model conventions in §4 of the data-model.md.

---

## Alternatives Considered

### A. Repo-root only forever (the status quo)

**Rejected.** Issue #522 is a real operator pain point and the
"`cd packages/auth`" workaround breaks every other mechanism that uses the
true git root.

### B. Per-mission `charter_root:` frontmatter field

The mission's `spec.md` would declare its charter root explicitly:

```yaml
charter_root: packages/auth
```

**Rejected.** Pushes the choice into per-mission metadata, which means every
new mission requires the operator to remember to set the field. Easy to
forget; hard to validate; reproduces the "I forgot to set the canonical
attribute" failure mode the org-DRG work was trying to solve.

### C. Auto-discovery of `.kittify/charter/` directories

Walk the tree upward from `feature_dir`, return the first ancestor that
contains a `.kittify/charter/` directory.

**Rejected.** Two problems:

1. **Ambiguity surface.** A repo might contain `.kittify/charter/`
   directories used for documentation, examples, fixtures, or vendored
   third-party packages. Auto-discovery would pick those up silently.
2. **No name.** The auto-discovered scope has no human-meaningful identifier
   to surface in prompts, catalog-miss warnings, or diagnostics. The
   operator-facing `name:` field becomes important the moment we have more
   than one charter — it shows up in `spec-kitty doctor`, in
   `CatalogMissEvent.extra["scope"]`, and in error messages.

### D. Modify `build_charter_context`'s signature directly

Add `scope: CharterScope | None = None` as a kwarg.

**Rejected for this mission.** Would force WP07 and WP09 to share file
ownership on `src/charter/context.py`, creating the kind of cross-WP
serialisation point we explicitly designed lanes to avoid. The
`scope_router.py` wrapper achieves the same effect from outside, leaves
`context.py` untouched, and gives us a clean place to add scope-aware
features (caching, telemetry, fallback warnings) without further mutating
the rendering core.

---

## Related Decisions

- [ADR Phase 2 of Slice F]: org-tier doctrine pack
  (axis 1, WP04–WP08). Charter scoping (axis 2) and org-tier doctrine
  (axis 1) are orthogonal and compose: a monorepo's per-package charter
  can layer an org-tier doctrine pack the same way a single-project
  charter does.
- C-007 (binding `__all__` declarations) — both new modules expose
  `__all__`.
- C-011 (ATDD-first per WP) — WP09 lands its failing tests as the first
  commit, the model and wrapper turn them GREEN.
- FR-140 round-trip frontmatter convention — `CharterScopeConfig` joins
  the round-trip-validated Pydantic surfaces.

## Out of Scope

- **Charter caching** (deferred until NFR-002 measurement shows it
  matters).
- **`spec-kitty charter scope list/show` CLI surfaces** (deferred to a
  follow-up; the runtime resolver is the primary deliverable).
- **Scope-aware glossary contexts.** Glossary contexts already have their
  own scope mechanism; monorepo-aware glossary scoping is its own design
  conversation.
- **Cross-scope dependency resolution.** If a `packages/auth` mission
  needs to consult the `packages/platform` charter, the operator either
  declares the dependency explicitly or runs the mission from the
  platform scope. No automatic multi-scope merge in this iteration.
