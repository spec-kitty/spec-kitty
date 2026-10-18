---
work_package_id: WP02
title: charter pack vendor command (+ --check)
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-010
- SC-002
planning_base_branch: feat/builtin-revendor-pin-gate
merge_target_branch: feat/builtin-revendor-pin-gate
branch_strategy: Planning artifacts for this mission were generated on feat/builtin-revendor-pin-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/builtin-revendor-pin-gate unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 1 - Implementation
history:
- at: '2026-10-17T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- src/specify_cli/cli/commands/charter/pack_vendor.py
- tests/charter_offering/test_pack_vendor.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/charter/pack_vendor.py
- src/specify_cli/cli/commands/charter/_app.py
- tests/charter_offering/test_pack_vendor.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3504'
---

# Work Package Prompt: WP02 – charter pack vendor command (+ --check)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Deliver `spec-kitty charter pack vendor [--check]`:

- **`vendor`** resolves the pinned open-packs ref **by SHA**, copies its **`built-in` subtree only**
  into `packs/built-in/`, then asserts the recomputed clean-tree digest equals the lockfile digest
  AND `check_requires_core` passes. On any failure (unreachable/unverifiable ref, digest mismatch,
  incompatible `requires_core`) it **fails closed**: `packs/built-in/` is left unchanged and the
  command exits non-zero. A **tag** supplied as the ref is resolved to a SHA and the resolved SHA is
  what gets written to the lockfile — the tag is never persisted (FR-002).
- **`vendor --check`** verifies only: it compares the committed `packs/built-in/` to the committed
  lockfile (digest comparison) and exits 0 in-sync / non-zero on drift, **mutating nothing**. The
  drift message names the `vendor` remedy (FR-010). This mode is **offline** — it touches no network.

Success = FR-003, FR-004, FR-005, FR-006, FR-007, FR-010, SC-002 in [spec.md](../spec.md) hold.

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-02. **Research**: [research.md](../research.md) D3, D4. **Charter**: `.kittify/charter/charter.md`.
- **Reuse, do NOT re-author (C-004)**:
  - **Fetch/clone + SHA checkout**: `from specify_cli.charter_packs.sources.git_source import GitSource`.
    Construct `GitSource(url=<pin.repository>, ref=<pin.commit or a tag input>)` and call
    `.fetch(target_dir)` into an **empty** scratch dir (`_first_install` refuses a non-empty dir by
    design — pass a fresh `mkdtemp`). It returns a `FetchResult` (`.ok`, `.errors`). On `ok == False`
    this is the unreachable/unverifiable-ref path → fail closed (FR-006). It already clones through the
    kernel's timeout-bounded, token-redacting owner — do not shell out to `git` yourself.
  - **Lockfile model**: `from charter.offering.packs.built_in_pin import load_built_in_pin, verify_built_in_pin, write_built_in_pin` (WP01).
  - **Digest**: via WP01's `verify_built_in_pin` (which wraps `clean_tree_digest(..., level=BUILT_IN)`); do not call a second digest.
  - **Compat**: `from charter.offering.packs.core_compat import check_requires_core`; load the vendored
    tree's descriptor with `charter.offering.packs.pack_descriptor.load_pack_descriptor` and pass the
    running core version (`importlib.metadata.version("spec-kitty-cli")`). Refuse with a clear non-zero
    error naming the incompatibility, tree unchanged (FR-005).
- **Built-in subtree only (C-006)**: copy only the open-packs ref's `built-in` subtree into core's
  `packs/built-in/`, not the open-packs repo root. open-packs uses a per-pack `packs/<name>/` layout;
  confirm the exact subpath against the tagged `v0.1.0` tree at implement time (expected
  `packs/built-in/` within open-packs). Content elsewhere in open-packs must not affect the vendored
  tree or the digest.
- **Atomic / never-partial (FR-006)**: copy into a scratch dir and verify the digest BEFORE replacing
  `packs/built-in/`; only swap in on success. A failed verify leaves the live tree untouched — never
  a partial or empty write.
- **Registration (small out-of-map edit in the shared `_app.py`)**: `pack_vendor.py` is a new sibling
  of `pack_tooling.py` exporting a `pack_vendor` command function (and `__all__`). Register it on the
  existing group exactly like `regenerate-graph`: in `src/specify_cli/cli/commands/charter/_app.py`,
  import `pack_vendor` alongside the `pack_tooling` imports (line ~31) and add one line next to the
  `charter_pack_app.command("regenerate-graph")(regenerate_graph)` block (lines 79–81):
  `charter_pack_app.command("vendor")(pack_vendor)`. This 2–3 line edit to a shared file is the only
  out-of-ownership-map touch; it is justified and minimal (DIRECTIVE_024 locality). Do NOT restructure
  `_app.py`.
- **CLI/logic split (Structure Decision in the plan)**: keep the typer command thin; put the
  resolve→copy→verify logic in `pack_vendor.py` as a testable function the command calls, so tests can
  drive it without the full CLI where convenient (but the red-first drift control in T005 drives the
  REAL CLI command — see below).
- Complexity ≤15 per function (extract helpers); no blanket `# noqa`/`# type: ignore`; mypy --strict clean.

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout; no lane worktree)
- **Planning base branch**: feat/builtin-revendor-pin-gate
- **Merge target branch**: feat/builtin-revendor-pin-gate (PR → main)

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first CLI repros (RED before the command)

- **Purpose**: ADR `2026-07-17-1`. Prove the verify/drift behaviour through the REAL CLI entry point
  before the command exists (FR-004, FR-007).
- **Steps**:
  1. In `tests/charter_offering/test_pack_vendor.py`, add tests that invoke
     `spec-kitty charter pack vendor --check` through the typer app (`CliRunner().invoke(app, ["charter","pack","vendor","--check"])`,
     using the same `app`-resolution idiom sibling charter CLI tests use):
     - **in-sync** committed tree → exit 0, no mutation;
     - a one-byte edit to any `packs/built-in/` file (in a copied fixture repo root) → exit non-zero
       with the FR-010 remedy substring (names `vendor`, says "bump the pin, do not hand-edit").
  2. Confirm RED on current code (command absent → non-zero/usage error that is NOT the drift message).
     Record the red output.
- **Files**: `tests/charter_offering/test_pack_vendor.py`
- **Parallel?**: No.
- **Notes**: Use a copied/tmp repo-root fixture so the edited-byte case does not dirty the real tree.

### Subtask T006 – The `pack_vendor` command (+ `--check`)

- **Purpose**: FR-003, FR-004, FR-007, FR-002.
- **Steps**:
  1. Create `src/specify_cli/cli/commands/charter/pack_vendor.py`. A `pack_vendor` typer command with
     a `--check` flag (verify-only) and the resolve→copy→verify core function.
  2. Full path: `GitSource(...).fetch(scratch)` → locate the `built-in` subtree in the fetched tree →
     copy into a staging dir → `verify_built_in_pin(pin, staging)` AND `check_requires_core` →
     on success atomically replace `packs/built-in/` and (for a pin bump) `write_built_in_pin` with
     the resolved SHA + freshly recomputed digest.
  3. `--check` path: load the pin, `verify_built_in_pin(pin, <repo>/packs/built-in)`, exit 0/ non-zero;
     no fetch, no network, no mutation.
  4. Make the in-sync and edited-byte repros from T005 GREEN.
- **Files**: `src/specify_cli/cli/commands/charter/pack_vendor.py`
- **Parallel?**: No.

### Subtask T007 – Register `vendor` on the group

- **Purpose**: FR-003 (the command is reachable as `spec-kitty charter pack vendor`).
- **Steps**:
  1. In `_app.py`, add `pack_vendor` to the `from ...pack_tooling import ...` sibling import area
     (a new `from ...pack_vendor import pack_vendor`), and register
     `charter_pack_app.command("vendor")(pack_vendor)` beside the existing pack-tooling registrations.
  2. Verify `spec-kitty charter pack --help` now lists `vendor`, and the other pack subcommands are
     unchanged.
- **Files**: `src/specify_cli/cli/commands/charter/_app.py`
- **Parallel?**: No (depends on T006).

### Subtask T008 – Fail-closed controls (positive + negative, non-vacuous)

- **Purpose**: FR-005, FR-006, and the non-vacuity of the "tree unchanged" assertions (US2-S4).
- **Steps**:
  1. **Stale-pin rewrites (positive control, FR-004 / US2 Independent Test)**: point the command at a
     deliberately stale pin on a fixture and assert `vendor` DOES rewrite `packs/built-in/` and
     refreshes the lockfile digest — proving the vendor path mutates on this harness, so the
     "tree unchanged" assertions below are non-vacuous. A **tag** input resolves to a SHA and only the
     SHA is written (FR-002).
  2. **Unreachable/unverifiable ref (FR-006)**: a bogus repo URL / unresolvable ref → `FetchResult.ok
     == False` → exit non-zero, `packs/built-in/` byte-identical afterwards (assert via digest).
  3. **Digest mismatch (FR-004)**: a fetched tree whose content does not match the lockfile digest →
     refuse non-zero, tree unchanged.
  4. **Incompatible `requires_core` (FR-005)**: a vendored `pack.yaml` whose `requires_core` excludes
     the running core version → refuse with a clear error naming the incompatibility, tree unchanged.
  5. Keep the network-touching tests hermetic: monkeypatch/stub `GitSource.fetch` to materialize a
     controlled scratch tree (and to simulate the unreachable case) rather than hitting the network in
     unit tests. Record which tests, if any, are marked network/integration.
- **Files**: `tests/charter_offering/test_pack_vendor.py`
- **Parallel?**: No.

## Test Strategy

- Red-first CLI repros (T005) RED before the command, GREEN after T006.
- Paired non-vacuity: stale-pin REWRITES (positive control) vs in-sync NO-OP, unreachable/digest/compat
  REFUSE (tree unchanged) — all on the same harness.
- Targeted surface: `tests/charter_offering/test_pack_vendor.py`, plus the owning trees
  `tests/charter_offering/` and `tests/charter/`, and the charter CLI tests that exercise the app
  (`tests/agent/cli/commands/test_charter_cli.py`) to confirm the registration did not disturb the
  group. Record commands + counts in the PR. NO full `tests/architectural/` sweep.

## Risks & Mitigations

- **Partial/empty write on failure (FR-006)**: stage-then-swap; verify before replacing the live tree.
- **Copying the whole open-packs repo (C-006)**: copy only the `built-in` subtree; confirm the subpath.
- **Persisting a tag (FR-002)**: resolve to a SHA before any write; the stale-pin test asserts a SHA.
- **Network flake in unit tests**: stub `GitSource.fetch`; gate any real-network test behind a marker.
- **`_app.py` churn**: limit the edit to the import line + the one registration line.

## Review Guidance

- Confirm `--check` performs no fetch and no mutation (offline).
- Confirm fail-closed on all three failure modes with the live tree byte-identical.
- Confirm the FR-010 remedy message names `vendor` and discourages hand-editing.
- Confirm only the `built-in` subtree is copied and only the resolved SHA is persisted.
- Confirm the `_app.py` edit is the minimal 2–3 line registration mirroring `regenerate-graph`.

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP02 --to <status>`
- View: `spec-kitty agent tasks status`
