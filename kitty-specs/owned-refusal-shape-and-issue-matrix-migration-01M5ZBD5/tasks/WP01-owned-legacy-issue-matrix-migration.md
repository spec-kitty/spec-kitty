---
work_package_id: WP01
title: Owned-aware legacy issue-matrix migration
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-004
- C-003
- SC-001
planning_base_branch: issue-6354-owned-issue-verdict-cleanup
merge_target_branch: issue-6354-owned-issue-verdict-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-6354-owned-issue-verdict-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6354-owned-issue-verdict-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
base_commit: 5223857cbb53f30bf2cd02fd6d8020c062e9708e
created_at: '2026-10-27T19:14:38.577791+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Migration placement
history:
- at: '2026-10-27T19:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/integration/test_owned_issue_verdict_legacy_migration_6354.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tasks/issue_matrix_migration.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- tests/integration/test_owned_issue_verdict_legacy_migration_6354.py
- tests/specify_cli/tasks/test_issue_matrix_structured.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Owned-aware legacy issue-matrix migration

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP01 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

Issue #6354. When an owned Mission still holds a legacy `issue-matrix.md` in its owned
checkout and an issue verdict is recorded (explicit `--owned-checkout <P>` or flagless
from inside `P`), the one-shot legacy migration must write `issue-matrix.json` into the
owned checkout. Today it resolves the write against the repository root checkout and the
command exits 1 with `FileNotFoundError` (reproduced on `581b5c46`, research.md §1.1).

Done when:
- FR-001: the command exits 0 and `P/kitty-specs/<slug>/issue-matrix.json` exists.
- FR-002: that JSON holds every legacy row plus the new verdict.
- FR-003: a non-owned Mission's legacy migration is unchanged (repository root write).
- NFR-004: the repository root checkout holds no `kitty-specs/<slug>` after the owned run.
- C-003: the issue-matrix terminality tests (ADR 2026-10-26-1; see #6653) stay green.

## Context & Constraints

- Spec: `kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/spec.md` (User Story 1).
- Plan IC-01 and research §1.1 (file:line grounding).
- Charter: ATDD / red-first. Commit the failing test (T001) as its own commit **before** any implementation commit.
- Do not change the owned refusal shape here; that is WP02. Do not touch
  `resolve_owned_or_refuse` / `success_false_envelope` in `issue_verdict.py`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6354-owned-issue-verdict-cleanup`
- **Merge target branch**: `issue-6354-owned-issue-verdict-cleanup`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement WP01 --agent claude --mission owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first integration test (owned legacy `.md`)

- **Purpose**: pin the user-observable behaviour through the real CLI entry point.
- **File**: create `tests/integration/test_owned_issue_verdict_legacy_migration_6354.py`.
- **Fixture**: reuse `checkouts` from `tests/integration/test_explicit_checkout_commands.py`
  exactly as `tests/integration/test_owned_issue_verdict_authority_6320.py` does
  (`from tests.integration.test_explicit_checkout_commands import SLUG, checkouts as checkouts  # noqa: F401 -- pytest fixture`;
  copy that import line's existing rationale verbatim; it is the established pattern,
  not a new suppression). `checkouts` yields `(primary, owned, sibling)`.
- **Markers**: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.
- **Legacy fixture content** (the validator accepts this header; see
  `tests/specify_cli/tasks/test_issue_matrix_structured.py:350-354`):

  ```python
  _LEGACY_MD = (
      "| Issue | Title | Verdict | Evidence ref |\n"
      "|-------|-------|---------|--------------|\n"
      "| #1 | legacy row | fixed | commit abc123 |\n"
  )
  ```

  Write it to `owned / "kitty-specs" / SLUG / "issue-matrix.md"` and make sure no
  `issue-matrix.json` exists there first (assert it).
- **Tests**:
  1. `test_owned_flag_migrates_legacy_matrix_into_owned_checkout`: invoke
     `agent_app` `["issue-verdict", "--mission", SLUG, "--issue", "#2", "--verdict", "fixed", "--actor", "codex", "--evidence-ref", "PR #1", "--json", "--owned-checkout", str(owned)]`;
     assert `exit_code == 0` (print `res.output` on failure), load
     `owned/kitty-specs/SLUG/issue-matrix.json`, assert both `#1` and `#2` rows are present
     and `#1` keeps verdict `fixed` + evidence `commit abc123`.
  2. `test_owned_migration_never_touches_the_repository_root`: same run; assert
     `not (primary / "kitty-specs" / SLUG).exists()`.
  3. `test_flagless_adoption_migrates_legacy_matrix_into_owned_checkout`:
     `monkeypatch.chdir(owned)`, no `--owned-checkout`; same assertions as 1.
- **Speed**: the fixture setup is ~170 s per module. Keep all owned tests in this one
  module so the fixture is reused where its scope allows; do not add a second module.
- **Red evidence**: run it before T003; record the failing output (expected exit 1,
  `FileNotFoundError`) in `spec-kitty agent tasks add-history WP01 --note`.
- Commit: `test(issue-verdict): red owned legacy issue-matrix migration (#6354)`.

### Subtask T002 – Non-owned positive control and forwarding unit test

- **Purpose**: the same-fixture positive control the non-vacuity tactic requires, plus a
  fast unit pin on the forwarding.
- **Files**: `tests/specify_cli/tasks/test_issue_matrix_structured.py` (class
  `TestMigrateIssueMatrixToJson`, ~line 343).
- **Steps**:
  1. Add `test_owned_fact_is_forwarded_to_the_writer`: stub `write_issue_matrix` in
     `specify_cli.tasks.issue_matrix_migration` (monkeypatch the name the module imported)
     with a recorder; call `migrate_issue_matrix_to_json(feature_dir, repo_root=tmp_path, mission_slug=_MISSION_SLUG, policy=_Policy(), owned=sentinel)`
     on a valid legacy `.md`; assert the recorder saw `owned is sentinel`.
  2. Add `test_owned_defaults_to_none_for_existing_callers`: same call without `owned`;
     assert the recorder saw `owned is None` (pins FR-003 / NFR-006 back-compat).
  3. In the integration module from T001, add
     `test_non_owned_legacy_migration_still_writes_to_the_repository_root` only if the
     `checkouts` fixture can host a non-owned Mission cheaply; otherwise rely on the
     existing `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py` as the
     non-owned control and say so in the history note. Do not build a second slow fixture.
- `_Policy` and `_stub_write_artifact_committed` already exist in that test module; reuse them.

### Subtask T003 – Thread `owned` through the migration

- **File**: `src/specify_cli/tasks/issue_matrix_migration.py`, `migrate_issue_matrix_to_json` (~line 301).
- **Steps**:
  1. Add a keyword-only parameter `owned: OwnedCheckout | None = None` (after `actor`).
     Import `OwnedCheckout` under `TYPE_CHECKING` (match how `issue_matrix.py` imports it;
     check `src/specify_cli/tasks/issue_matrix.py` header) to respect the module's
     cold-import discipline.
  2. Forward it: `write_issue_matrix(..., target_branch=target_branch, owned=owned)`.
     Do **not** pass `matrix_dir`; `write_issue_matrix` resolves the owned write dir lazily
     from `owned` (its docstring, `issue_matrix.py:415-450`).
  3. Extend the docstring with one paragraph: "`owned` (#6354): the validated owned-checkout
     fact; forwarded to the writer so an owned Mission's migrated matrix lands in its owned
     checkout. `None` (default) keeps the repository-root write for every existing caller,
     including the bulk `issue-matrix migrate` command."
  4. Leave the bulk command (`~line 408`) untouched (`owned` stays `None`).

### Subtask T004 – Forward from `_migrate_if_needed`

- **File**: `src/specify_cli/cli/commands/agent/issue_verdict.py`, `_migrate_if_needed` (~line 178-226).
- **Step**: pass `owned=owned` to `migrate_issue_matrix_to_json(...)` (~line 208-215).
  Nothing else in this file changes in WP01.
- Run T001 and T002: both must go green. Commit:
  `fix(issue-verdict): migrate an owned mission's legacy issue matrix into its owned checkout (#6354)`.

### Subtask T005 – Blast-radius run

Run and record counts in the history note:

```bash
uv run --frozen pytest tests/integration/test_owned_issue_verdict_legacy_migration_6354.py \
  tests/integration/test_owned_issue_verdict_authority_6320.py \
  tests/integration/test_p0_repro_6320_owned_issue_verdict.py \
  tests/integration/test_issue_verdict_coord_legacy_md_preservation.py \
  tests/specify_cli/tasks/ -q
uv run --frozen pytest tests -q -k "terminal and issue_matrix" --co -q | tail -3   # locate the ADR 2026-10-26-1 terminality tests, then run them
uv run --frozen ruff check src/specify_cli/tasks/issue_matrix_migration.py src/specify_cli/cli/commands/agent/issue_verdict.py tests/integration/test_owned_issue_verdict_legacy_migration_6354.py
uv run --frozen ruff format --check --force-exclude <same files>
uv run --frozen mypy src/specify_cli/tasks/issue_matrix_migration.py src/specify_cli/cli/commands/agent/issue_verdict.py
```

Also confirm the malformed-legacy edge still fails loudly: an owned run against a
malformed `.md` exits 1 with code `malformed_legacy_matrix` and writes nothing (an existing
non-owned test covers the raise; add an owned assertion to the T001 module only if it
costs no extra fixture).

## Test Strategy

Red-first integration (T001) through `agent_app`, unit forwarding pins (T002), the
existing non-owned migration tests as positive control. `mypy` on both touched source files.

## Risks & Mitigations

- Cold-import boundary: `issue_matrix_migration.py` may be imported cold; use a
  `TYPE_CHECKING` import for `OwnedCheckout`.
- Do not widen into WP02's refusal-shape change in `issue_verdict.py`.

## Review Guidance

- Verify T001 was committed red before T003/T004 (commit order) and is green now.
- Verify the bulk migrate command still passes `owned=None` implicitly.
- Verify no file under the repository root checkout is written in the owned tests.
- Confirm ruff, format (`--force-exclude`) and mypy were run on the touched files.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
