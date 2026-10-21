---
work_package_id: WP11
title: 'CANCELED (mission_pivot_option_b) — Fixture sweep 1: tests/charter and tests/charter_offering'
dependencies:
- WP10
requirement_refs:
- FR-017
planning_base_branch: core-align-3-persistent-deactivation
merge_target_branch: core-align-3-persistent-deactivation
branch_strategy: Planning artifacts for this mission were generated on core-align-3-persistent-deactivation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into core-align-3-persistent-deactivation unless the human explicitly redirects the landing branch.
subtasks:
- T064
- T065
- T066
- T067
- T068
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
- kitty-specs/persistent-deactivation-ledger-01M59YAA/tasks/WP11-fixture-sweep-charter.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

> **CANCELED (2026-10-20, operator ruling `mission_pivot_option_b`).** The fixture sweep moves to the charter-contract alignment epic (epic child #6535: retire the legacy activation reader). SC-004 is re-homed to WP14; the FR-017 ref stays only because finalize-tasks requires every WP, canceled ones included, to carry one (it points at the read half that moved to the epic). Do not implement. Its ownership was reduced to this prompt file on cancellation, because finalize-tasks checks canceled WPs for overlap too; the original tree globs are in git history.

# Work Package Prompt: WP11 – Fixture sweep 1: tests/charter and tests/charter_offering

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

- Check `review_ref` in the event log; address every item; record with `spec-kitty agent tasks add-history WP11 --note "..."`.

---

## Objective

Move every activation fixture in `tests/charter/` and `tests/charter_offering/` (about 125 files) onto `.kittify/charter/activation.yaml`, and put both trees under strict test mode, so a missed fixture goes red here and not at the flip (WP14). This WP also takes the Mission-wide census that WP12 and WP13 use.

## Context

- Plan IC-12 (revised, D0); research.md D-15 (revised); FR-017; SC-004 (0 new failures vs the base).
- Mission order: WP11 of 15, strictly linear. The fixture sweep is split in three: WP11
  (`tests/charter`, `tests/charter_offering`), WP12 (`tests/specify_cli`), WP13 (every other
  tree plus the YAML fixtures). WP14 then makes strict mode unconditional.
- Tooling from WP02: `tests/_factories/activation_ledger.py` (`seed_activation_ledger`,
  `read_activation_ledger`, `legacy_seed`) and the `SWEPT_PREFIXES` fixture in `tests/conftest.py`.
- Ownership: this WP owns its trees by glob. All earlier WPs are its ancestors (linear chain), so
  overlap with their test files is permitted. Never change a test's *intent*: a seed changes
  location, and an assertion changes the file it reads.
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
spec-kitty agent action implement WP11 --agent claude --mission persistent-deactivation-ledger-01M59YAA
```

## ATDD (red first)

Adding this WP's prefixes to `SWEPT_PREFIXES` is the acceptance test. Every un-swept class B or
class C fixture in these trees must go red under it. Record the red count per tree **before**
re-seeding (in `traces/fixture-census.md` and in your history note). The commit that lands the
prefixes also lands the re-seeding (see the procedure above).

## Subtasks

### Subtask T064: Step 0 — re-seed every shared, cross-tree activation helper (H2)

**Purpose**: WP12 and WP13 must never depend on a helper they cannot edit. That is why this WP
owns and fixes every helper that seeds activation and is imported from another tree, before any
tree is swept.

**Measured list** (grep 2026-10-19: test modules that write an activation key and are imported
from a different top-level test tree; the number is cross-tree importer files), plus the
per-tree conftests that seed activation:
   - `tests/_factories/__init__.py` — 64 cross-tree importers; `make_mission`, `provision_test_charter`
   - `tests/_factories/coord_mission.py` — 41
   - `tests/integration/test_placement_partition_golden_path.py` — 18 (helper functions only)
   - `tests/runtime/_next_mission_scaffold.py` — 11
   - `tests/git/protected_target_fixtures.py` — 10
   - `tests/charter/skill_pack_support.py` — 6
   - `tests/specify_cli/cli/commands/_implement_fixtures.py` — 6
   - `tests/charter/org_pack_identity_support.py` — 2
   - `tests/integration/test_explicit_checkout_commands.py` — 2 (helper functions only)
   - `tests/charter/test_resolver.py` — 1 (helper functions only)
   - `tests/review/test_pre_review_gate_integration.py` — 1 (helper functions only)
   - `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py` — 1 (helper functions only)
   - `tests/specify_cli/next/test_wp_prompt_governance_contract.py` — 1 (helper functions only)
   - `tests/specify_cli/test_specify_topology_flag.py` — 1 (helper functions only)
   - `tests/acceptance/charter_pack_cutover/legacy_fixtures.py` — 1; class A (cutover legacy shapes): keep legacy, confirm consumers read inside the scope
   - `tests/specify_cli/cli/commands/conftest.py` — per-tree conftest fixture seeding activation
   - `tests/acceptance/charter_pack_cutover/conftest.py` — per-tree conftest; class A: keep legacy

**Steps**:
1. Re-derive the list with the grep recorded in `traces/fixture-census.md` (helper modules that
   write `activated_*` / `mission_type_activations` / `deactivated_*` and are imported from
   another tree, plus every `conftest.py` that seeds them). Add any new hit to this WP as a
   recorded out-of-map edit.
2. Add a **mode-following** helper `seed_activation(repo_root, **keys)` to
   `tests/_factories/activation_ledger.py`. It writes through the production writer
   (`prepare_activation_write` / the resolver's target), so it lands on the legacy surface in
   tolerant mode and on the ledger in strict mode.
3. Route each helper through the production provisioner (`provision_mission_type_activations`
   for `mission_type_activations`) or that mode-following helper, so it works in **both** modes:
   - un-swept consumers keep running tolerant;
   - swept ones run strict.
   - Never write a ledger unconditionally: in tolerant mode a ledger would turn every later
     legacy seed of an un-swept consumer into an ignored stray key.
4. For helper functions inside test modules (`test_placement_partition_golden_path.py` and
   others), edit only the helper functions, never the test cases.
5. **Prove both modes per helper (M1).** The `pytest_runtest_setup` hook clears the variable for
   un-swept paths, so un-swept consumers cannot be run strict directly. Instead:
   - add a new file, `tests/charter/test_step0_helpers_both_modes.py`, listed in `SWEPT_PREFIXES`.
     For each step-0 helper it runs a `pytester` inner test twice: once with the inner conftest
     listing the inner test in `SWEPT_PREFIXES` (strict `test` mode) and once without (tolerant).
     Each run calls the helper and asserts the resulting store (the ledger in strict mode; the
     legacy surface in tolerant mode, with no ledger created). The file never references the
     variable directly;
   - run the consumers once, in tolerant mode (the default for un-swept paths): the 92
     `make_mission` / `provision_test_charter` consumer files (measured, outside
     `tests/_factories/`) plus the cross-tree importers above. Use the marker-filtered command in
     Validation, never `tests/performance/`, and record the pass/fail counts in
     `traces/approach.md`;
   - never edit `SWEPT_PREFIXES` locally without committing the edit.

### Subtask T065: Mission-wide census (all trees, Python and YAML)

**Steps**:
1. Python:
   ```bash
   grep -rlE "(activated|deactivated)_(directives|tactics|styleguides|toolguides|paradigms|procedures|agent_profiles|mission_step_contracts|glossary_packs|anti_patterns|skills|kinds)|mission_type_activations" tests --include='*.py' | sort
   ```
   Derive the plural list from `charter.activation.activation_ledger.LEDGER_KEYS` if it changed.
2. YAML and JSON fixtures: the same pattern with `--include='*.yaml' --include='*.yml' --include='*.json'`. Today that is `tests/fixtures/mission_type_canonical/**/.kittify/config.yaml` (3), `tests/fixtures/charter_pack_cutover/default_yaml_snapshots.yaml` and `tests/architectural/global_state_allowlist/S5.yaml`.
3. `make_mission` / `provision_test_charter` consumers: `grep -rlE "make_mission|provision_test_charter" tests --include='*.py' | grep -v ^tests/_factories/` (92 files measured on 2026-10-19). After step 0 they follow the mode automatically.
4. Classify every hit A–E and write `traces/fixture-census.md`, tagging each row with its sweep WP (WP11, WP12 or WP13).
   - **Exclude** the two repository-reading tests that WP08 owns and re-pointed (`tests/charter/test_config_stem_parity.py`, `tests/charter_offering/test_project_charter_single_owner.py`; H1).
   - Rows for the step-0 helpers are tagged WP11-step0.

### Subtask T066: Sweep `tests/charter/`

**Steps**: add `"tests/charter/"` to `SWEPT_PREFIXES` locally, then run the tree and record the red count. Apply the B and C actions file by file and run each file after editing. Commit in batches of 25 files or fewer; the **first** batch commit also lands the prefix, and its message lists the files.

### Subtask T067: Sweep `tests/charter_offering/`

**Steps**: the same procedure for `"tests/charter_offering/"`. Repository-reading tests that read this repository's own `.kittify/` (for example `test_project_charter_single_owner.py`) were already adjusted by WP08 and must stay green.

### Subtask T068: Verification

**Steps**:
- Run both trees under strict test mode (the fixture applies it) and compare with the base.
- Tolerant mode stays covered by the un-swept trees, which keep running without the variable until WP12 and WP13.
- Confirm `git diff --stat -- src/` is empty.

## Validation / targeted test surface

```bash
cd /home/user/spec-kitty
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" tests/charter tests/charter_offering
# step-0 helper consumers (92 make_mission/provision_test_charter files + the cross-tree importers), excluding tests/performance/; tolerant (default) run
.venv/bin/python -m pytest -q -n auto --dist loadfile -m "not timing and not stress" $( (grep -rlE "make_mission|provision_test_charter|coord_mission|protected_target_fixtures|_next_mission_scaffold|_implement_fixtures|skill_pack_support|org_pack_identity_support|test_placement_partition_golden_path|test_explicit_checkout_commands" tests --include='*.py') | grep -v '^tests/_factories/' | grep -v '^tests/performance/' | sort -u)
.venv/bin/python -m pytest -q tests/charter/test_step0_helpers_both_modes.py
.venv/bin/python -m pytest -q tests/architectural/test_deny_list_survives_upgrade.py tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_ruff_format_enforcement.py
make test-fast
uv run --frozen ruff check tests/charter tests/charter_offering tests/conftest.py <every step-0 helper>
uv run --frozen ruff format --check --force-exclude <every edited test file>
```

The trees above are this WP's owning subsystem directories and its whole blast radius. Do
**not** run `make test-full` or the bare `tests/architectural/` directory. Record the counts
for each command.

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
