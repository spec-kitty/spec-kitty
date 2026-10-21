---
work_package_id: WP13
title: 'CANCELED (mission_pivot_option_b) — Fixture sweep 3: every remaining tree and the YAML fixtures'
dependencies:
- WP12
requirement_refs:
- FR-017
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T073
- T074
- T075
- T076
- T077
phase: Phase 8 - Fixture sweep
history:
- at: '2026-10-19T12:17:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (sweep split by the post-tasks squad, D1)
agent_profile: python-pedro
authoritative_surface: kitty-specs/persistent-deactivation-ledger-01M59YAA/tasks/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/persistent-deactivation-ledger-01M59YAA/tasks/WP13-fixture-sweep-remaining.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

> **CANCELED (2026-10-20, operator ruling `mission_pivot_option_b`).** The fixture sweep moves to the charter-contract alignment epic (epic child #6535: retire the legacy activation reader). SC-004 is re-homed to WP14; the FR-017 ref stays only because finalize-tasks requires every WP, canceled ones included, to carry one (it points at the read half that moved to the epic). Do not implement. Its ownership was reduced to this prompt file on cancellation, because finalize-tasks checks canceled WPs for overlap too; the original tree globs are in git history.

# Work Package Prompt: WP13 – Fixture sweep 3: every remaining tree and the YAML fixtures

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Load the `spk-practice-bulk-edit` skill **for its occurrence-classification discipline only**.
This sweep is deliberately *not* `change_mode: bulk_edit` (plan resolved point 6): the
classification lives in this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP13 --note "..."`.

---

## Objective

Sweep every remaining test tree and the YAML fixtures onto the ledger, and put them under strict test mode, so that after this WP every test that touches activation is swept and WP14 can flip.

## Context

- Plan IC-12 (revised, D0); research.md D-15 (revised); FR-017; SC-004 (0 new failures vs the base).
- Mission order: WP13 of 15, strictly linear. The fixture sweep is split in three: WP11
  (`tests/charter`, `tests/charter_offering`), WP12 (`tests/specify_cli`), WP13 (every other
  tree plus the YAML fixtures). WP14 then makes strict mode unconditional.
- Tooling from WP02: `tests/_factories/activation_ledger.py` (`seed_activation_ledger`,
  `read_activation_ledger`, `legacy_seed`) and the `SWEPT_PREFIXES` fixture in `tests/conftest.py`.
- Ownership: this WP owns its trees by glob. All earlier WPs are its ancestors (linear chain), so
  overlap with their test files is permitted. Never change a test's *intent*: a seed changes
  location, and an assertion changes the file it reads.
- Shared cross-tree helpers (including `tests/_factories/**`, `tests/git/protected_target_fixtures.py` and the helper functions in `tests/integration/test_placement_partition_golden_path.py`) were re-seeded by **WP11 step 0** and work in both modes. This WP never edits them; if one still misbehaves, stop and hand it back.
- No `src/` change. If a test cannot be swept without a production fix, stop, record it in
  `traces/tooling-friction.md`, and hand it back to the orchestrator.

## Occurrence classification (binding for WP11–WP13)

| Class | What it is | Action |
|---|---|---|
| **A — legacy-by-design** | A test whose subject *is* the legacy surface: a migration or upgrade test, or a test of the legacy branch of the resolver | **Keep** the legacy seed (`tests/_factories/activation_ledger.legacy_seed`). Its legacy reads run inside the upgrade scope: either through a migration, the registry, the runner or `spec-kitty upgrade` (which enter it), or by wrapping the read in `with legacy_activation_scope(repo_root):` explicitly. A module-level opt-out flag such as `LEGACY_ACTIVATION_FIXTURE` is **forbidden** (D0) |
| **B — runtime seed** | A fixture writes `activated_<kind>`, `deactivated_<kind>`, `mission_type_activations` or `activated_kinds` into `config.yaml` / `charter.yaml` (Python or YAML fixture) to set up an ordinary command | Replace it with `seed_activation_ledger(repo_root, ...)` from `tests/_factories/activation_ledger.py`. Drop the legacy keys from the seeded YAML and keep the non-activation keys |
| **C — post-write assertion** | The test reads `config.yaml` / `charter.yaml` after a command to check activation keys | Assert against `read_activation_ledger(repo_root)`. Where the test previously read the legacy file, also assert that file has **no** activation key (C-003) |
| **D — direct `PackContext`** | Builds `PackContext(...)` directly, with no files | **Unchanged**. Only pass the default if construction breaks |
| **E — prose** | Docstrings, comments, test ids and message strings that mention the old location | **Unchanged**, except a comment that is now false about where activation lives: fix that one line |

Record the per-file class in the Mission trace
`kitty-specs/persistent-deactivation-ledger-01M59YAA/traces/fixture-census.md`, as a table with
the columns file, class, action, WP and done. It is Mission bookkeeping, not an owned file.
WP11 creates it, and WP12 and WP13 append to it.

## Red signal (D0, binding)

- `tests/conftest.py` holds `SWEPT_PREFIXES` (created empty by WP02, and appended to by WP02–WP10 with the exact paths of their new test files) and two hooks (M1).
  A `pytest_runtest_setup` hookimpl (`tryfirst=True`) sets `SPEC_KITTY_ACTIVATION_STRICT=test` for every test
  whose path starts with a listed prefix (and clears it otherwise) **before any fixture of the item runs**, so function- and
  module-scoped fixtures see the item's mode; `pytest_runtest_teardown` restores the value.
  A session-scoped fixture is set up once, in its first user's mode. None that seeds activation exists today; any future one
  must be function-scoped or use the WP11 step-0 helpers, which work in both modes (L1). An environment variable reaches CLI subprocesses and
  threads.
- Under `test`, the resolver is strict:
  - an un-swept legacy seed on a project with no ledger fails closed (`UNMIGRATED`);
  - a legacy seed beside a ledger raises (stray keys);
  - `init` and `provision_test_charter` write the ledger.

  A missed fixture therefore goes red inside the sweep WP.
- **Procedure per tree**:
  1. Add the prefix locally.
  2. Run the tree and record the red count in `traces/fixture-census.md`. This is the red-first evidence.
  3. Re-seed until the tree is green.
  4. Commit the prefix addition **together with** the re-seeding, so the main branch never carries a red list.
- Strict test mode stays on for every listed tree until WP14 deletes the variable, the fixture and the list.


## Branch Strategy

- **Strategy**: single_branch; sequential in the repository root checkout on `core-align-3-persistent-deactivation`.
- **Planning base branch**: `core-align-3-persistent-deactivation`
- **Merge target branch**: `core-align-3-persistent-deactivation`

```bash
spec-kitty agent action implement WP13 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

Adding this WP's prefixes to `SWEPT_PREFIXES` is the acceptance test. Every un-swept class B or
class C fixture in these trees must go red under it. Record the red count per tree **before**
re-seeding (in `traces/fixture-census.md` and in your history note). The commit that lands the
prefixes also lands the re-seeding (see the procedure above).

## Subtasks

### Subtask T073: Refresh the census for the remaining trees

**Steps**: re-run WP11's census for every tree not covered by WP11 or WP12, including `status`, `consolidation`, `coordination`, `contract`, `doctor`, `kernel`, `unit`, `init`, `missions`, `regressions`, `audit`, `context` and `performance`, plus the YAML fixtures and the four architectural files. A tree the census finds that is not in this WP's globs is swept as a recorded out-of-map edit, with a one-line rationale.

### Subtask T074: Sweep `acceptance`, `upgrade`, `integration`, `runtime`

**Steps**: add the prefixes locally and record the red counts. `tests/upgrade/**` is mostly class A: `_legacy_upgrade_fixture.py` stays legacy, and its non-migration reads are wrapped in `legacy_activation_scope`. Commit in batches; the first batch commit lands the prefixes.

### Subtask T075: Sweep every other Python tree and the shared factories

**Steps**:
- Trees: `core`, `agent`, `cli`, `review`, `next`, `git`, `compat`, `test_template`, `status`, `consolidation`, `coordination`, `contract`, `doctor`, `kernel`, `unit`, `init`, `missions`, `regressions`, `audit`, `context`, `performance`.
- The shared factories were fixed by WP11 step 0 (H2); do not edit them here.
- The four architectural files: only their class B or C content.
- Add every swept tree's prefix in the same commit as its re-seeding.

### Subtask T076: YAML fixtures

**Steps**:
- `tests/fixtures/mission_type_canonical/{{project_override/legacy,project_override/canonical,org_activated_custom_type}}/.kittify/config.yaml`: move `mission_type_activations` and any activation key into a sibling `.kittify/charter/activation.yaml`, unless the fixture is deliberately legacy (`project_override/legacy` is class A: keep it and confirm that its consumers read it inside the scope).
- `tests/fixtures/charter_pack_cutover/default_yaml_snapshots.yaml` is a frozen cutover snapshot (class A, unchanged).
- `tests/architectural/global_state_allowlist/S5.yaml`: update only if it names a moved location.
- Add `"tests/fixtures/"` to the prefixes only if tests live there.

### Subtask T077: Verification

**Steps**:
- Run every swept tree under strict test mode and compare with the base (SC-004; classify base-red failures per the baseline-red gotcha in `CLAUDE.md`).
- Confirm that the census has no un-swept B or C row left across all three sweeps.
- Confirm `git diff --stat -- src/` is empty.


## Validation / targeted test surface (C1: no heavy sweeps)

```bash
cd /home/user/spec-kitty
# the exact files this WP re-seeds or classifies (recorded in traces/fixture-census.md, rows tagged WP13)
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" $(awk -F'|' '/\| *WP13 *\|/ {gsub(/ /,"",$2); print $2}' kitty-specs/persistent-deactivation-ledger-01M59YAA/traces/fixture-census.md | grep '\.py$' | sort -u)
# consumers whose seeding this WP actually changes, as tagged WP13-consumer in the census (never tests/performance/, never tests/integration as a directory)
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" $(awk -F'|' '/\| *WP13-consumer *\|/ {gsub(/ /,"",$2); print $2}' kitty-specs/persistent-deactivation-ledger-01M59YAA/traces/fixture-census.md | grep '\.py$' | grep -v '^tests/performance/' | sort -u)
.venv/bin/python -m pytest -q tests/architectural/test_kind_table_derivation.py tests/architectural/test_no_production_worktree_guard_bypass.py tests/architectural/test_org_activation_seam.py tests/architectural/test_json_contract_enumeration.py
.venv/bin/python -m pytest -q tests/architectural/test_deny_list_survives_upgrade.py tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_ruff_format_enforcement.py
make test-fast
uv run --frozen ruff check <every edited test file>
uv run --frozen ruff format --check --force-exclude <every edited test file>
```

Run only the files this WP re-seeds (grep-derived and recorded in the census), the consumers
whose seeding it changes (census tag `WP13-consumer`), `make test-fast` and the named gates. Never run a whole tree such as
`tests/integration/`, never the bare `tests/architectural/` directory, and never
`make test-full` (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`). Record the counts.

## Standing orders

- Follow python-pedro. Keep ruff and format (`--force-exclude`) clean on every edited test file.
- Append dated entries to the Mission's `traces/approach.md`, `traces/tooling-friction.md` and `traces/fixture-census.md`.
- Do not edit shipped migrations or any `src/` file.

## Definition of Done

- Every class B or C file in this WP's trees seeds and asserts through the factory.
- Class A files run their legacy reads inside the scope. Class D and E files are untouched.
- This WP's prefixes are in `SWEPT_PREFIXES`, and those trees are green under strict test mode.
- 0 new failures vs the base (SC-004).
- Every subtask is marked done.

## Risks

- Hidden seeders in shared helpers: grep the helpers first and fix at the helper (if the helper is outside this WP's globs, record the out-of-map edit with a one-line rationale).
- Subprocess tests read the environment variable. Check that they are covered by the prefix, not skipped.

## Reviewer Guidance

- Sample ten files per class from `traces/fixture-census.md` and check that the action matches the class.
- Confirm that the prefixes are listed, that no opt-out flag exists, and that `git diff --stat -- src/` is empty.
