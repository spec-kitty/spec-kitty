---
work_package_id: WP01
title: Typed registry error at the fail-closed seam
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6772-charter-packs-refusal-code
merge_target_branch: issue-6772-charter-packs-refusal-code
branch_strategy: Planning artifacts for this mission were generated on issue-6772-charter-packs-refusal-code. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6772-charter-packs-refusal-code unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-packs-refusal-code-convergence-01M66FC9
base_commit: af6f5e6cd10bb908ad1fe0b009b3b4f7c02f05d1
created_at: '2026-10-30T13:31:16.324403+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/drg/org_pack_config.py
- src/charter/activation/activation_ledger.py
- src/charter/activation/layer_roots.py
- tests/specify_cli/cli/commands/charter/test_activation_json_6525.py
- tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Typed registry error at the fail-closed seam

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

## Markdown Formatting

Wrap HTML/XML tags in backticks: `<div>`, `<script>`
Use language identifiers in code blocks: `python`, `bash`

---

## Objectives & Success Criteria

`charter activate KIND ID` and `charter deactivate KIND ID` refuse a malformed `charter_packs`
registry in `.kittify/config.yaml` (e.g. `charter_packs: [1, 2]`) with the **same** code,
`ACTIVE_CHARTER_CONFIG_INVALID`, in both text and `--json` form (exit 1, nothing written). The
convergence comes from typing the error at the one shared fail-closed registry read —
NOT from per-verb mapping in the CLI. The "declared pack not fetched" refusal keeps its
current shape (`ACTIVATION_FAILED` on activate, naming `spec-kitty charter fetch`).

Success criteria: SC-001, SC-002, SC-003 of the spec; FR-001..FR-004, NFR-001, NFR-002.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6772. Spec: `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/spec.md`.
- Plan: `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/plan.md` (IC-01).
- Research (READ FIRST): `kitty-specs/charter-packs-refusal-code-convergence-01M66FC9/research.md`
  — the cause chain, decisions D1–D3, and the rejected alternatives.
- Cause (verified): `charter deactivate` refuses through the strict required-floor read
  (`org_pack_discovery._strict_error` → `ActiveCharterConfigError`), while `charter activate`
  refuses earlier through `resolve_pack_chain(strict=True)` →
  `require_declared_org_roots` (`src/charter/offering/drg/org_pack_config.py`), which re-raises
  the registry-read `ValueError` as a plain `ValueError`; the CLI maps generic `ValueError` to
  `ACTIVATION_FAILED`.
- **Constraints**:
  - C-001: `charter.offering` must not import `charter.activation` at module load — import
    `ActiveCharterConfigError` lazily inside the helper, exactly as
    `charter.activation.org_pack_discovery._strict_error` does in the other direction.
  - C-002: refusal codes stay local UPPER_SNAKE CLI codes.
  - C-003: smallest viable diff — the fix is one exception class and one raise-site change.
  - `__all__` convention (charter C-007): export the new name from `org_pack_config` if the
    module maintains `__all__` (it does — add it).
  - No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION): run the targeted suites named in
    T004 only.

## Branch Strategy

- **Strategy**: populated automatically by `spec-kitty agent mission finalize-tasks`
- **Planning base branch**: `issue-6772-charter-packs-refusal-code`
- **Merge target branch**: `issue-6772-charter-packs-refusal-code`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Re-pin the CLI refusal test red-first

- **Purpose**: The defect's acceptance test, driven through the pre-existing CLI entry point,
  must fail before the fix (ATDD-first; DIRECTIVE_034 test-first-bug-fixing).
- **Steps**:
  1. In `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`, find
     `test_a_malformed_charter_packs_config_is_refused`. It is parametrized
     `("command", "code")` with the asymmetric expectation
     (`activate` → `ACTIVATION_FAILED`, `deactivate` → `ACTIVE_CHARTER_CONFIG_INVALID`) and a
     comment explaining the asymmetry.
  2. Re-pin: both verbs expect `ACTIVE_CHARTER_CONFIG_INVALID`. Collapse the parametrize to
     `@pytest.mark.parametrize("command", ["activate", "deactivate"])` (the code is now
     constant), and replace the stale comment with one naming issue #6772 and the typed
     registry error. Keep the `"org pack registry"` message assertion — it must hold for both
     verbs.
  3. Run it: `uv run pytest "tests/specify_cli/cli/commands/charter/test_activation_json_6525.py::test_a_malformed_charter_packs_config_is_refused" -q`.
     EXPECT RED on the `activate` parametric (it still reports `ACTIVATION_FAILED`). Record
     the red run (this is the red-first proof for the PR body).
- **Files**: `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`
- **Parallel?**: No — first.
- **Notes**: Do not weaken `_assert_refusal`; it already checks exit codes, the JSON envelope,
  the text form and that `.kittify/` is byte-identical.

### Subtask T002 – The typed registry error

- **Purpose**: Type the unreadable-registry refusal at the shared seam so the CLI's existing
  `ActiveCharterConfigError` mapping reports `ACTIVE_CHARTER_CONFIG_INVALID`.
- **Steps**:
  1. **(Revised at implementation — traces/design-decisions.md D4.)** In
     `src/charter/activation/activation_ledger.py` (the `ActiveCharterConfigError`
     family's documented error home), add next to the base:
     ```python
     class OrgPackRegistryUnreadableError(ActiveCharterConfigError, ValueError):
         """The org pack registry in .kittify/config.yaml cannot be read (issue #6772). ..."""
     ```
     The class definition must live there, not in `org_pack_config`: subclassing needs
     the base at class-definition time, and an eager import of `activation_ledger` from
     `org_pack_config` cycles the import graph (verified: `activation_ledger`
     transitively imports `org_pack_config`). Because
     `ActiveCharterConfigError.__init__(body)` sets code `ACTIVE_CHARTER_CONFIG_INVALID`,
     the subclass inherits it; keep the `ValueError` base so every strict reader's
     `except ValueError` keeps firing (FR-004; research.md D1). Override `__str__` to
     return `self.body` (strict readers interpolate `str(exc)`; the family default is
     the code). Document BOTH bases and why in the docstring, and export the name in
     `__all__`.
  2. In `src/charter/offering/drg/org_pack_config.py`, add a private
     `_refuse_unreadable_registry(cause: ValueError) -> NoReturn` helper that lazily
     imports `OrgPackRegistryUnreadableError` (C-001 — the error crosses the
     offering→activation seam only at raise time) and raises it with the message
     `f"the org pack registry cannot be read: {cause}"` (keep the existing message
     lead verbatim), mirroring `org_pack_discovery._strict_error`'s lazy-import shape.
  3. In `require_declared_org_roots`, change ONLY the registry-read failure arm:
     `raise ValueError(f"the org pack registry cannot be read: {exc}") from exc` becomes
     `_refuse_unreadable_registry(exc)`. The "declared org pack ... is
     not fetched" arm keeps raising plain `ValueError` (FR-003, research.md D2). Update the
     docstring's `Raises` note. Also note the typed registry error in
     `layer_roots.resolve_pack_chain`'s `strict=True` docstring bullet.
- **Files**: `src/charter/offering/drg/org_pack_config.py`,
  `src/charter/activation/activation_ledger.py`,
  `src/charter/activation/layer_roots.py` (docstring only)
- **Parallel?**: No — after T001.
- **Notes**: The CLI (`activate.py`/`deactivate.py`) needs NO change: in
  `_apply_direct_activation`, `except ActiveCharterConfigError` (→ `config_refusal`, its own
  code) already precedes `except (ValueError, DRGLoadError)` (→ `ACTIVATION_FAILED`). Verify
  that ordering while you are there; do not reorder it. `org_pack_config.py` is on the
  formatter-debt ratchet (pyproject `[tool.ruff.format]` exclude): do NOT run
  `ruff format` on the whole file — formatter-only churn on legacy lines trips the
  shrink-only ratchet test; keep the diff to the edited lines only.

### Subtask T003 – Seam-level test

- **Purpose**: Pin the exception contract at the seam so a future refactor cannot silently
  drop the `ValueError` base (which would change three strict readers) or re-widen the
  not-fetched arm.
- **Steps**:
  1. In `tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py`, the existing
     `test_unnamed_single_pack_block_is_a_config_error` already asserts
     `pytest.raises(ValueError, match="cannot be read")` for `require_declared_org_roots`.
     Extend or add a test that asserts, for a malformed registry (e.g. the same
     `charter_packs: [1, 2]` shape or the unnamed single-pack block):
     - `require_declared_org_roots` raises `OrgPackRegistryUnreadableError`;
     - the raised error `isinstance` of BOTH `ActiveCharterConfigError` and `ValueError`;
     - `error.code == "ACTIVE_CHARTER_CONFIG_INVALID"`.
  2. Add (or extend) the counterpart for the not-fetched case: a declared pack whose
     `local_path` does not exist raises plain `ValueError` (NOT the typed error), matching
     "is not fetched". If a fixture for a declared-but-missing pack already exists in this
     file or a sibling, reuse it.
- **Files**: `tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py`
- **Parallel?**: After T002.
- **Notes**: Import `ActiveCharterConfigError` from `charter.activation.activation_ledger` in
  the test (tests may import across the seam).

### Subtask T004 – Regression guards

- **Purpose**: FR-004 — every strict reader of the org-pack chain keeps its documented
  refusal behaviour.
- **Steps**: Run the targeted suites (fast marks where the suite defines them) and confirm
  green:
  ```bash
  uv run pytest tests/specify_cli/cli/commands/charter/test_activation_json_6525.py -q
  uv run pytest tests/charter_offering/drg/test_org_pack_config_cr04_charter_packs.py -q
  uv run pytest tests/charter/activation -q -k "effective_set or preset or requirement_kinds or manifest"
  uv run pytest tests/specify_cli/cli/commands/charter/test_activation_text_golden.py -q
  ```
  Also run the repo's lint/type gates that CI enforces on changed files (ruff, mypy per
  repo config; see CLAUDE.md). If a red is pre-existing on pristine main (reproduce in a
  clean worktree of origin/main), do NOT fix or skip it here — report it (Pre-existing
  Failure Reporting Rule) and cite it.
- **Files**: none (verification only).
- **Parallel?**: Last.
- **Notes**: NEVER run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Test Strategy

- The re-pinned CLI test (T001) is the acceptance test; it must have been RED on `activate`
  before T002 and GREEN after.
- The seam test (T003) pins the exception contract (both bases, the code, the distinct
  not-fetched arm).
- diff-cover: the changed lines in `org_pack_config.py` must be covered — T003's assertions
  exercise both arms of `require_declared_org_roots`.

## Risks & Mitigations

- **Multiple inheritance looks unusual** → the docstring and T003 explain and pin WHY both
  bases exist (the `ValueError` base preserves three strict readers' `except ValueError`
  contracts; the `ActiveCharterConfigError` base carries the code and rides the CLI mapping).
- **Import cycle** → lazy import inside the helper only (C-001), mirroring
  `org_pack_discovery._strict_error`.
- **Message drift** → keep the "the org pack registry cannot be read: ..." lead verbatim.

## Review Guidance

- Confirm the red-first proof (T001 red on activate before the fix).
- Confirm no CLI-layer change and no message-text branching anywhere.
- Confirm the not-fetched arm still raises plain `ValueError` and activate still reports
  `ACTIVATION_FAILED` with the fetch remedy.
- Confirm ruff/mypy pass on the changed files.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) —
never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
