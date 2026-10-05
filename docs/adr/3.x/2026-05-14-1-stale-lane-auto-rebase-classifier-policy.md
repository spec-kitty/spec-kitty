---
title: 'ADR: Stale-Lane Auto-Rebase Classifier Policy'
description: 'Auto-rebase may resolve a stale lane only through a closed list of file-and-conflict-shape rules; anything unmatched falls back to manual handling and halts.'
status: Accepted
date: '2026-05-14'
---

## Context

`spec-kitty merge` currently fail-stops on stale lanes — i.e. when a lane
branch has not incorporated changes from the mission branch that conflict
with files the lane also touched. Pre-mission analysis
(`work/findings/771-auto-rebase-stale-lanes.md`) documented a 30-minute
rote-merge cost per 10-WP mission, all of which is on additive-only
conflict shapes that a machine can resolve safely.

The user-facing risk of attempting to auto-merge is that a wrongly-classified
semantic conflict silently combines incompatible code. The classifier MUST
default to **fail-safe**: when no rule matches, halt and surface the conflict
to the operator.

## Decision

Adopt a **closed-list rule classifier** plus a fail-safe default. Each rule
is keyed on:

1. **File pattern** (glob or specific path).
2. **Conflict shape** (what the conflict markers contain).
3. **Resolution** (the merged output the auto-rebase orchestrator writes back,
   plus an audit-log rule ID).

Any file or conflict shape not matching an explicit rule resolves to `Manual`
and halts.

## Rules (initial set)

### R-PYPROJECT-DEPS-UNION

**File pattern**: `pyproject.toml` (top of repo).
**Conflict scope**: `[project.dependencies]` array entries,
`[project.optional-dependencies.*]` arrays, `[dependency-groups.*]` arrays.
**Conflict shape**: Both sides added distinct entries (by package name) to
the same array; no shared entry was modified.
**Resolution**: `Auto` — union of entries, deduplicated by package name
(case-insensitive). The union preserves the surrounding file's sort
convention: if the unmodified prefix of the conflicted region is
alphabetically sorted, the union is sorted; otherwise insertion order
(side A first, then side B's new entries) is preserved.
**Counter-example**: If both sides modified the version specifier on the
same package (e.g. one side `httpx >=0.27`, the other `httpx >=0.28`),
resolve to `Manual` — version conflicts are semantic.

### R-INIT-IMPORTS-UNION

**File pattern**: `**/__init__.py` (any package init).
**Conflict scope**: The block of `from X import Y` / `import X` statements
at the top of the file.
**Conflict shape**: Both sides added distinct import lines (different `X`
or different `Y`); no shared import was modified.
**Resolution**: `Auto` — union of import lines, sorted by `ruff` after the
union. The auto-rebase orchestrator runs `ruff --fix --select I001 <file>`
after writing the merged content, treating any non-zero exit from ruff as
a fallback to `Manual`.
**Counter-example**: If one side renamed an existing import target (e.g.
`from .auth import AuthFlow` → `from .auth import OAuthFlow`), the rule
does not match (it's a modify, not an add) — resolve to `Manual`.

### R-URLS-LIST-UNION

**File pattern**: `**/urls.py` (Django-style) or any file whose conflicting
region is bounded by a recognizable list constant (`_URLS = [`,
`URL_PATTERNS = [`, etc.).
**Conflict scope**: Entries inside the list constant.
**Conflict shape**: Both sides added distinct entries; no shared entry was
modified.
**Resolution**: `Auto` — union of entries, preserving the file's original
ordering convention (alphabetical if the unmodified prefix of the list is
sorted, insertion order otherwise).
**Counter-example**: If both sides modified the same entry's pattern or
handler, resolve to `Manual`.

### R-UVLOCK-REGENERATE

**File pattern**: `uv.lock` (exact path at repo top).
**Conflict scope**: Any.
**Resolution mode**: **special** — `uv.lock` is not classified as
`Auto`/`Manual` for textual merge. Instead, the auto-rebase orchestrator:

1. Holds a global file lock via `specify_cli.core.file_lock.MachineFileLock`
   to prevent concurrent regenerations across lanes.
2. Discards both sides of the conflict (the file is fully regenerated).
3. Runs `uv lock --no-upgrade` from the repo root.
4. Stages the regenerated `uv.lock`.

If `uv lock` exits non-zero, the orchestrator halts with the stderr surfaced
to the operator.

### R-DEFAULT-MANUAL

**File pattern**: any file not matched by the rules above.
**Conflict scope**: any.
**Resolution**: `Manual` with `reason="no classifier rule matched <file_path>"`.

This rule is **always last** in the rule list. It is the fail-safe default
mandated by NFR-005.

## Rule list ordering

```python
RULES: tuple[ClassifierRule, ...] = (
    R_PYPROJECT_DEPS_UNION,
    R_INIT_IMPORTS_UNION,
    R_URLS_LIST_UNION,
    R_UVLOCK_REGENERATE,      # special-cased in the orchestrator
    R_DEFAULT_MANUAL,
)
```

First match wins. `R_DEFAULT_MANUAL` is always reachable because no preceding
rule has an unbounded pattern.

## Fail-safe invariants (NFR-005)

1. Any input not exactly matching one of the named rules MUST resolve to
   `Manual`.
2. A rule MUST resolve to `Manual` if its conflict shape predicate raises
   ANY exception during evaluation. The classifier wraps each rule's shape
   predicate in a `try/except` that defaults to `Manual` on raise.
3. The orchestrator MUST verify, after applying an `Auto` resolution, that
   the resulting file is syntactically valid for its type. For
   `pyproject.toml`: `tomllib.loads` succeeds. For Python files: `ast.parse`
   succeeds. If validation fails, the orchestrator reverts the file to its
   pre-merge state and reports `Manual(reason="post-merge validation failed: ...")`.

## Operator-visible behavior

### When all conflicts in a lane resolve to `Auto`

The orchestrator:

1. Applies each `Auto` resolution by writing the merged text and staging
   the file.
2. Runs the orchestrator's post-merge step (`uv lock` if `uv.lock` was
   conflicted; `ruff --fix --select I001` if any `__init__.py` was
   conflicted).
3. Creates a merge commit on the lane branch with message
   `"auto-rebase(lane=<id>): <N> conflicts resolved by classifier rules
   [R-PYPROJECT-DEPS-UNION, ...]"`.
4. Continues the outer merge pipeline as if the lane had been merged
   cleanly.

### When any conflict in a lane resolves to `Manual`

The orchestrator:

1. Reverts any partial auto-resolutions in the lane worktree (`git merge
   --abort`).
2. Halts the outer merge pipeline.
3. Emits the same actionable error message that `spec-kitty merge` emits
   today: instructs the operator to run `git merge <mission-branch>` in
   the lane worktree and resolve manually.
4. Reports per-lane status in `AutoRebaseReport.classifications` for any
   future audit.

### When `uv.lock` regeneration fails

The orchestrator:

1. Aborts the lane merge.
2. Surfaces the `uv lock` stderr to the operator.
3. Records the failure in `AutoRebaseReport.halt_reason`.
4. Does NOT retry — operator intervention required (likely a `pyproject.toml`
   issue that survived `R-PYPROJECT-DEPS-UNION`).

## Resolved questions

The contracts-draft predecessor surfaced three open questions for the operator.
The operator has accepted Pedro's recommendations as written:

1. **Auto-rebase commit message format**: include `lane=<id>`. Message
   format: `auto-rebase(lane=<id>): <N> conflicts resolved by classifier
   rules [<rule_ids>]`.
2. **`ruff --fix --select I001` scope**: keep minimal. Do not broaden to
   `--select E,F` or similar without operator-requested evidence that the
   import-only fix is insufficient.
3. **`R-URLS-LIST-UNION` sort-convention detection**: sample the unmodified
   prefix of the list; if alphabetically sorted, sort the union; otherwise
   preserve insertion order.

These three resolutions are inlined into the rule definitions above. The
predecessor contracts draft is preserved for historical traceability.

## Examples

### Example 1: R-PYPROJECT-DEPS-UNION (auto-resolve)

Lane A's `pyproject.toml`:

```toml
[project]
dependencies = [
  "httpx>=0.27",
  "ruamel-yaml",
]
```

Lane B's `pyproject.toml`:

```toml
[project]
dependencies = [
  "httpx>=0.27",
  "freezegun",
  "ruamel-yaml",
]
```

Mission branch's `pyproject.toml` (after Lane A merged):

```toml
[project]
dependencies = [
  "httpx>=0.27",
  "ruamel-yaml",
  "requests-mock",
]
```

Lane B is stale; conflict on the `dependencies` array. R-PYPROJECT-DEPS-UNION
matches.

**Auto-resolved result** (sorted because the unmodified prefix of the
conflicting region was sorted):

```toml
[project]
dependencies = [
  "freezegun",
  "httpx>=0.27",
  "requests-mock",
  "ruamel-yaml",
]
```

### Example 2: Counter-example — version specifier conflict (Manual)

Lane A adds `httpx>=0.27`; Lane B adds `httpx>=0.28`.
R-PYPROJECT-DEPS-UNION does NOT match (the rule's shape predicate excludes
same-package version drift). Resolves to `Manual`. The orchestrator halts
and the operator decides.

### Example 3: R-INIT-IMPORTS-UNION (auto-resolve)

Lane A's `apps/collaboration/__init__.py`:

```python
from .auth import AuthFlow
from .flags import FeatureFlags
```

Lane B's `apps/collaboration/__init__.py`:

```python
from .flags import FeatureFlags
from .sync import SyncClient
```

R-INIT-IMPORTS-UNION matches.

**Auto-resolved result** (after `ruff --fix --select I001`):

```python
from .auth import AuthFlow
from .flags import FeatureFlags
from .sync import SyncClient
```

### Example 4: Counter-example — modification of an existing import (Manual)

Lane A changes `from .auth import AuthFlow` to `from .auth import OAuthFlow`.
Lane B adds `from .sync import SyncClient`. R-INIT-IMPORTS-UNION does NOT
match because Lane A modified an existing import (not added a new one).
Resolves to `Manual`.

## Consequences

- The lane→mission merge pipeline now attempts machine-driven recovery on
  the additive-only conflict shapes that constitute the bulk of observed
  stale-lane friction.
- The fail-safe default is preserved: any unrecognized conflict still halts
  and surfaces the existing actionable error message.
- Operators retain full audit trail via `AutoRebaseReport.classifications`
  and the commit-message rule-ID list.
- Future rule additions are localized to `conflict_classifier.py` and
  documented as ADR amendments.

## Testing contract

Per `function-over-form-testing`:

- **Per-rule unit tests** (`tests/integration/merge/test_conflict_classifier.py`):
  parametrized `(file_path, hunk_text, expected_resolution)` triples for each
  rule. Cover both happy auto-resolve and the rule's counter-example.
- **Orchestrator integration tests**
  (`tests/integration/lanes/test_auto_rebase_additive.py`): two-lane scenario
  with `pyproject.toml` adds; assert the resulting `pyproject.toml` parses
  as TOML and contains the union of dependencies.
- **Negative integration tests**: two-lane scenario with a semantic conflict;
  assert the orchestrator halts with the current actionable error message;
  assert no partial auto-resolution leaks to the lane worktree.
- **Fail-safe smoke**: feed the classifier a file pattern not covered by any
  rule; assert `R-DEFAULT-MANUAL` fires with the documented reason.

## References

- Predecessor draft: `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/contracts/stale-lane-auto-rebase-classifier-policy.md`
- Data model: `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/data-model.md` §3
- WP08: `kitty-specs/quality-devex-hardening-3-2-01KRJGKH/tasks/WP08-auto-rebase-classifier.md`
- Issue: [Priivacy-ai/spec-kitty#771](https://github.com/Priivacy-ai/spec-kitty/issues/771)

## Amendment 2026-10-04 (#5457)

**A managed-artifact rule for primary-owned bookkeeping.** `R-PRIMARY-OWNED-BOOKKEEPING` (`RULE_ID_PRIMARY_OWNED` in `src/specify_cli/lanes/auto_rebase.py`) resolves a conflict on a primary-owned path to the incoming side.

- **Distinction from `RULES`.** It is a **managed-artifact (whole-file) rule**. It is not a per-hunk entry in the `RULES` tuple above and it has no conflict-shape predicate. `_resolve_managed_artifact_conflicts` takes the whole file from the incoming side before the generic text rules run, in the same stage as the coordination-artifact and status rules.
- **File pattern.** `is_primary_owned_path` from the state contract (`src/specify_cli/state/contract.py`): an exact path declared `StateSurface.primary_owned`. Today that is `.kittify/metadata.yaml`. The set is declared in one place; this ADR does not list paths.
- **Resolution.** Stage 3, the incoming coordination or mission side, which is closer to the merge target branch. The file is generated and never authored by a work package.
- **Fail-safe.** `R-DEFAULT-MANUAL` is unchanged and remains the fail-safe default for every path the rules above and this managed-artifact stage do not match (NFR-005). Operator-editable project files such as `.gitattributes`, `.gitignore` and `.kittify/config.yaml` still resolve to `Manual`.

The decision and its merge-site table are recorded in [ADR 2026-10-04-4](../4.x/2026-10-04-4-upgrade-writes-project-global-state-once.md). The original decision text above is unchanged.
