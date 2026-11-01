# Implementation Plan: `doctor ops` sweeps Op records in every checkout

**Branch**: `issue-6661-doctor-ops-sweep-linked-worktrees` (planning base and merge target: the same branch; it reaches `main` through a PR) | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/doctor-ops-sweep-linked-worktrees-01M66YNF/spec.md`

**Branch contract (repeated per the plan prompt):** planning artifacts are on
`issue-6661-doctor-ops-sweep-linked-worktrees`, this mission's planning base branch
and merge target are `issue-6661-doctor-ops-sweep-linked-worktrees`, and completed
work merges into that branch — never into `main`.

## Summary

Op records are owned by the checkout that invoked the command (#6564, #6664), but
`spec-kitty doctor ops` still lists and sweeps one directory,
`<project root>/kitty-ops`. A record opened in a linked worktree is therefore
invisible, and `--close-stale` never closes it.

The fix makes the sweep ask the checkout enumeration that already exists for Op
custody (`git worktree list --porcelain` in `invocation/op_custody.py`) for every
checkout, collects orphan records from each checkout's own `kitty-ops/` and
closure spine, and closes each one through an executor whose `record_root` is the
checkout that owns it — so the spine append and its auto-commit land on that
checkout's branch. Governance still reads from the project root. Listing paths
are reported relative to the project root (`../lane/kitty-ops/<id>.jsonl`) with no
JSON shape change. The session-presence reminder keeps its single-checkout,
git-free scan; that boundary becomes explicit in the docstring and in a test.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git CLI (subprocess); no new package dependency
**Storage**: files — `kitty-ops/<invocation_id>.jsonl` records and the append-only closure spine `kitty-ops/op-closures.jsonl`, per checkout
**Testing**: pytest. A red-first test drives the pre-existing `spec-kitty doctor ops` CLI entry point against a real git repository with a linked worktree; focused unit tests cover the enumeration, the per-checkout executor selection, the degraded paths and the session-presence boundary
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single
**Performance Goals**: at most one `git worktree list` subprocess per `doctor ops` run (NFR-001); no git process per record; session-start/stop reminder stays < 0.5 s at 1,000 Op files with zero git calls
**Constraints**: `doctor ops --json` payload shape frozen and the sweep report's entry keys unchanged (C-001); closure only through `complete_invocation`, spine only (C-004); no new flag, config key or transport (C-003); ruff and mypy clean, cyclomatic complexity ≤ 15, diff-cover ≥ 90 % on changed lines
**Scale/Scope**: 4 source files, 1 promoted symbol in `op_custody`, 2 test files (one new git-backed module), 3 docs plus the changelog

Supply chain: no dependency decision, so DIRECTIVE_051 controls are not triggered.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority.** The checkout set has exactly one owner: the
  existing enumeration in `specify_cli/invocation/op_custody.py`, promoted from
  private to public and reused. `doctor/ops.py` gains no walk of its own (pinned by
  a test). The record/spine semantics stay those of `InvocationWriter` and
  `ProfileInvocationExecutor`; the sweep invents no second close path. Status: pass.
- **ATDD-first (ATDD-First Discipline, DIRECTIVE_034).** The defect gets a failing
  test through the real CLI before the fix, committed red first. Status: pass.
- **Locality of change (DIRECTIVE_024).** The diff stays in `doctor/ops.py`,
  `cli/commands/doctor.py`, the `op_custody` visibility change, and a docstring in
  `session_presence/open_ops.py`. The mission-step half (#6664) is not reopened.
  Status: pass.
- **Terminology.** Mission, Op, Op record, closure spine, checkout, worktree. No
  "feature". Status: pass.
- **Archive freeze (#4397).** The sweep keeps closing on the append-only spine and
  never mutates a per-record file. Status: pass.
- **No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION).** Targeted suites only:
  invocation, doctor and session-presence modules. Status: pass.
- **Pre-existing Failure Reporting Rule.** Any red on the PR not attributable to this
  diff is reproduced on pristine `origin/main` and cited or filed. Status: to be
  applied at CI time.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-ops-sweep-linked-worktrees-01M66YNF/
├── spec.md
├── research.md
├── reasons-canvas.md
├── plan.md            # this file
├── traces/            # approach, design-decisions, tooling-friction
└── tasks.md / tasks/  # from the tasks step
```

### Source Code (repository root)

```
src/specify_cli/invocation/op_custody.py      # promote _repository_checkouts -> repository_checkouts (public)
src/specify_cli/doctor/ops.py                 # checkout-aware orphan listing; one executor per owning checkout
src/specify_cli/cli/commands/doctor.py        # root-relative path rendering in table and --json
src/specify_cli/session_presence/open_ops.py  # docstring: the scan is deliberately single-checkout and git-free
tests/specify_cli/invocation/test_doctor_ops.py          # unit coverage: ordering, degraded paths, executor selection
tests/specify_cli/invocation/test_doctor_ops_worktrees.py # NEW: git-backed multi-worktree red-first repro
tests/specify_cli/session_presence/test_open_ops.py      # pin: no git call, root checkout only
```

**Structure Decision**: single project, existing layout. Production changes sit in
the `specify_cli` CLI tree they already belong to (`invocation`, `doctor`,
`cli/commands`), and tests stay beside the existing invocation test package, which
already owns the git-backed Op fixtures in `tests/specify_cli/invocation/_op_git.py`.

## Design detail

### Enumeration

`op_custody.repository_checkouts(project_root)` yields the resolved checkout paths
`git worktree list --porcelain` reports, and yields nothing when git is absent or
the command fails. `doctor/ops.py` composes the set as
`[project_root, *repository_checkouts(project_root)]`, de-duplicated by resolved
path, preserving that order (root first, then git order) — NFR-003.

### Listing

`doctor/ops.py` gains `list_orphan_ops_across_checkouts(repo_root)`:

```
def list_orphan_ops_across_checkouts(repo_root: Path) -> list[Path]:
    records = []
    for checkout in _checkouts(repo_root):
        records.extend(list_orphan_ops(checkout))
    return records
```

`list_orphan_ops` keeps its signature and behavior — one directory, that
checkout's own closure spine — so the session-start path is untouched (C-002). The
owning checkout of a record is `record.parent.parent`, so no tuple return type or
new entity is needed.

### Sweep

`close_stale_ops(repo_root, ...)` enumerates with
`list_orphan_ops_across_checkouts`, keeps one
`ProfileInvocationExecutor` per owning checkout in a dict keyed by resolved
checkout path (`record_root=checkout`, `propagator=InvocationSaaSPropagator(repo_root)`),
and otherwise runs the identical per-op loop: age, staleness, `parse_warning`,
`complete_invocation(outcome="abandoned", closed_by="doctor_sweep")`,
`already_closed`, per-op `error`, and the `commit` value vocabulary. The
per-checkout executor also keeps the #4424 property: each spine is read once per
sweep because the executor caches its closed-id snapshot.

### Reporting

`doctor.py` renders each record with a path relative to the project root:
`os.path.relpath(record, repo_root)` formatted with `/` separators, so a worktree
record shows as `../lane/kitty-ops/<id>.jsonl` and a root record is unchanged
(`kitty-ops/<id>.jsonl`). The JSON payload stays a list of `{"path": ...}`. The
human table gains no column; the `../` prefix already names the checkout.

### Degraded paths (FR-005)

- Not a git checkout, git missing, timeout, or `git worktree list` failure →
  `repository_checkouts` yields nothing → the set is `[project_root]` → today's
  behavior and exit code.
- A listed checkout without `kitty-ops/` → `list_orphan_ops` returns `[]`.
- A listed checkout that no longer exists → same, nothing to read; not pruned.
- An invalid record id → skipped by `InvocationWriter.invocation_path` as today.

## Complexity Tracking

*No charter-check violations.*

## Implementation Concern Map

### IC-01 — One checkout enumeration, shared with custody

- **Purpose**: Make the sweep see every checkout without inventing a second walk.
- **Relevant requirements**: FR-001, FR-006, NFR-001, NFR-003, C-002.
- **Affected surfaces**: `src/specify_cli/invocation/op_custody.py`, `src/specify_cli/doctor/ops.py`, `src/specify_cli/session_presence/open_ops.py` (docstring only).
- **Sequencing/depends-on**: none.
- **Risks**: widening `list_orphan_ops` by accident would put git on the
  session-start path; the test in IC-03 guards it. Ordering must be deterministic
  so `--json` output is stable across runs.

### IC-02 — Close each Op in the checkout that owns it

- **Purpose**: Land each closure spine append and its commit where the record lives.
- **Relevant requirements**: FR-002, NFR-002, C-001, C-004.
- **Affected surfaces**: `src/specify_cli/doctor/ops.py`, `src/specify_cli/cli/commands/doctor.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: building one executor without `record_root` and reusing it would
  silently write every closure into the root checkout — the defect one layer down.
  Per-checkout failure must stay a per-entry error, never an abort.

### IC-03 — Prove it red-first and pin the boundaries

- **Purpose**: Show the multi-worktree case failing today and passing after, and
  pin the three boundaries (root-relative paths, session-presence scan, degraded git).
- **Relevant requirements**: FR-001..FR-006, SC-001..SC-005.
- **Affected surfaces**: `tests/specify_cli/invocation/test_doctor_ops.py`, `tests/specify_cli/invocation/test_doctor_ops_worktrees.py` (new), `tests/specify_cli/session_presence/test_open_ops.py`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: a fixture that writes the worktree record through the CLI would fail
  for custody reasons before it ever reached the sweep; seed the record on disk
  directly (as `_op_git.track_op_record_on_current_branch` does) so the test fails
  on the enumeration, not on setup.
