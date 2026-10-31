---
work_package_id: WP01
title: Envelope identity for the seed claim carrier, proved red-first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6689-backfill-claim-slots
merge_target_branch: issue-6689-backfill-claim-slots
branch_strategy: Planning artifacts for this mission were generated on issue-6689-backfill-claim-slots. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6689-backfill-claim-slots unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-backfill-runtime-state-idempotent-claim-slots-01M67HR8
base_commit: dc7290b7fb2383b0c8fba5ac121f1162d40febf4
created_at: '2026-10-30T23:24:37.840366+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - The fix and its proof
history:
- at: '2026-10-30T23:25:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/migration/backfill_runtime_state.py
- tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Envelope identity for the seed claim carrier, proved red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Run `spec-kitty agent profile show python-pedro` and
`spec-kitty charter context --action implement --include agent-profile:python-pedro`
before reading the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."` as you go.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Fix `spec-kitty/spec-kitty#6689`: `migrate backfill-runtime-state` (and therefore
`upgrade --project`'s runtime-state cutover) fails closed forever on a legacy Mission whose
`meta.json` `mission_id` equals its own slug and whose WP frontmatter already carries claim
slots. After this WP:

- SC-001: that Mission shape reaches `status_phase` snapshot authority through
  `spec-kitty migrate backfill-runtime-state --mission <slug>` with exit code 0.
- SC-002: a second consecutive run appends 0 events and exits 0.
- SC-003: tampered payload, missing seed and strip-before-verify still abort with their
  specific errors, on the *same* fixture that now passes.
- SC-004: existing backfill/cutover test files covering the untouched shapes pass unchanged.

## Context & Constraints

**Grounding is done; do not re-derive it.** Reproduced on `main` `512567eee7` with the exact
Mission shape from the issue report. The fixture mints the seed id
`0RWXZFHX7REDZWCZC43GQB3SPF`, byte-identical to the id quoted in the report.

**The mechanism.** `_claim_carrier` (`src/specify_cli/migration/backfill_runtime_state.py`)
sets the seed row's envelope `mission_id` to `None` whenever the resolved mission id equals
the Mission slug (`mission_id if mission_id != slug else None`). `StatusEvent.to_dict()`
omits a `None` `mission_id`, so the persisted row has no `mission_id` key. On read-back,
`_partition_event_stream_from_text` → `_resolve_mission_id_from_dict`
(`src/specify_cli/status/store.py`) resolves a row with no `mission_id` through
`_SlugResolver` → `meta.json` and *injects* the declared value — the slug. So:

| | `mission_id` |
| --- | --- |
| rebuilt expectation (`_build_seed_events`) | `None` |
| row read back off disk | `'cache-known-card-ceo-checks'` |

`_seed_row_mismatch` therefore reports `WP01: claim mismatch (deterministic seed payload
diverged)` on every run, forever. Nothing the operator writes to disk can satisfy it.

**The fix (IC-01 in plan.md).** Separate the two values `_mission_id` conflates:

- **seed namespace root** — the deterministic-id input, *unchanged*:
  declared id, else the directory name. Seed `event_id`s must not change for any corpus, or
  an already-seeded project would gain a duplicate row per WP.
- **envelope identity** — what the row declares on disk: the `mission_id` `meta.json`
  declares, or nothing at all when it declares none (never a fabricated id).

`_claim_carrier` stays the single envelope authority (C-001).

**Hard constraints.**

- C-002: do not reinterpret a slug-valued `mission_id` as absent, and do not change
  `backfill-identity`.
- C-003: do not add, widen or relax any tolerance in `_seed_row_mismatch` /
  `_verify_expected_seed_events`; the fix is writer-side only.
- NFR-004: `src/specify_cli/status/store.py` must not appear in your diff.
- C-004: out of scope — `archive create`, the "WP file with no YAML frontmatter" read error,
  `wp_status_backfill.py`, and any `upgrade` command-surface change.

Read first: `kitty-specs/backfill-runtime-state-idempotent-claim-slots-01M67HR8/spec.md`,
`plan.md` (IC-01/IC-02), `research.md` (Decisions 1–6), `data-model.md` (INV-1 – INV-5),
`quickstart.md`.

## Branch Strategy

- **Strategy**: Current branch at workflow start: issue-6689-backfill-claim-slots. Planning/base branch for this mission: issue-6689-backfill-claim-slots. Completed changes must merge into issue-6689-backfill-claim-slots.
- **Planning base branch**: `issue-6689-backfill-claim-slots`
- **Merge target branch**: `issue-6689-backfill-claim-slots`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Execution worktrees are allocated per computed lane from `lanes.json`; never build a
> workspace path by hand.

## Subtasks & Detailed Guidance

### T001 – Red-first: build the reported Mission fixture and observe the engine-level failure

- **Purpose**: Pin the defect through the pre-existing entry point before touching the fix,
  so the PR can show a genuine red.
- **Steps**:
  1. Create `tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py`
     with a fixture builder that writes the reported shape into `tmp_path`:
     - `kitty-specs/cache-known-card-ceo-checks/meta.json` with
       `"mission_id": "cache-known-card-ceo-checks"` (a slug), `mission_slug`,
       `mission_type: software-dev`, `created_at`, `accepted_at`, `accepted_by`,
       `accept_commit`.
     - `tasks/WP01-known-card-fast-path.md` with **no** `lane:` key, `assignee: root`,
       `agent: "codex"`, `shell_pid: "21224"` and no `shell_pid_created_at`.
     - `status.events.jsonl` whose history starts at `claimed -> in_progress` (no initial
       `planned -> claimed`), actor `codex`, `+00:00` timestamps.
  2. Add a row asserting `backfill_runtime_state(feature_dir)` then
     `verify_backfill(feature_dir).ok is True`.
  3. Run it against the **pre-fix** tree (`git stash` the fix, or run before writing it) and
     capture the exact output for the PR: action `wrote`, `seeded_count 3`, and
     `('WP01: claim mismatch (deterministic seed payload diverged)',)`.
- **Files**: `tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py`
- **Parallel?**: no (first).
- **Notes**: Mark the module `pytestmark = [pytest.mark.fast]` only if it needs no git/CLI;
  the CLI row in T002 does, so keep the module marker honest (`pytest.mark.git_repo`,
  `pytest.mark.non_sandbox`) or split markers per test. Follow the existing
  `tests/specify_cli/migration/` conventions; do not modify the shared fixture builders in
  `tests/unit/migration/_backfill_fixture.py` or `tests/_support/legacy_mission.py`.

### T002 – Red-first: prove the CLI entry point exits 1 on that fixture

- **Purpose**: FR-008 — the fix must be proven on the production entry point, not only on a
  library helper.
- **Steps**:
  1. Add a row that invokes the real command for the fixture's project root. Prefer the
     in-process Typer runner (see how other `tests/specify_cli/cli/` suites invoke commands)
     or a `subprocess` run of `spec-kitty migrate backfill-runtime-state --mission
     cache-known-card-ceo-checks`, whichever the existing suite already uses for this
     command.
  2. Assert exit code 0 and that `meta.json` `status_phase` is flipped to the
     snapshot-authority value, plus a summary line naming the Mission under `Flipped`.
  3. Capture the pre-fix failure (exit 1, Mission listed under "Failed (status_phase left
     untouched)") for the PR body.
- **Files**: same file as T001.
- **Notes**: `--mission` goes through `resolve_mission_handle`, so a raw slug is fine. If the
  command needs a git repo, reuse the harness primitives other CLI suites use rather than
  hand-rolling `git init`.

### T003 – Fix: split declared mission id from seed namespace

- **Purpose**: The actual defect fix, in one place.
- **Steps**:
  1. Add `_declared_mission_id(read_dir: Path) -> str | None` returning the `meta.json`
     `mission_id` verbatim, or `None` when `meta.json` is missing/unparsable/declares none.
     Reuse the existing `load_meta(read_dir, allow_missing=True, on_malformed="none")` call
     shape and the `if raw: return str(raw)` guard already in `_mission_id`.
  2. Redefine `_mission_id(read_dir)` as `_declared_mission_id(read_dir) or read_dir.name`,
     keeping its current docstring intent (it is the **seed namespace root**) and stating
     explicitly that it is not the envelope value.
  3. Change `_claim_carrier` to take both values explicitly, e.g.
     `seed_namespace: str` (used only for `_seed_id`) and `mission_id: str | None` (put on
     the envelope verbatim). Delete the `mission_id if mission_id != slug else None` collapse.
     Document the distinction in its docstring — it is the canonical authority for the
     carrier's shape.
  4. Update the two callers: `_build_seed_events` (compute `namespace = _mission_id(read_dir)`
     for annotations/seeds and `declared = _declared_mission_id(read_dir)` for the envelope)
     and `_legacy_contract_carriers` (same two values).
- **Files**: `src/specify_cli/migration/backfill_runtime_state.py`
- **Notes**: `_seeded_frontmatter_slots` and `_verify_claim_slot_witnesses` look seeds up by
  `_seed_id(_mission_id(read_dir), ...)`; they must keep working with **no** edit — verify by
  running the existing unit suite. Do not add a parameter default that silently restores the
  collapse.

### T004 – Idempotency + namespace-stability rows

- **Purpose**: INV-2 and NFR-001/NFR-002. A namespace change would silently re-seed every
  already-migrated corpus, which is worse than the bug.
- **Steps**:
  1. Row: `_seed_id(_mission_id(feature_dir), "WP01", "claim")` for the reported fixture
     equals the literal `"0RWXZFHX7REDZWCZC43GQB3SPF"` (the pre-fix value), **and** the
     persisted row's `mission_id` now equals the slug. Both assertions in one row: the first
     alone would pass on a fix that also changed the namespace, the second alone on a fix
     that fabricated an id.
  2. Row: a second `backfill_runtime_state` call returns `action == "skip"`,
     `seeded_count == 0`, and the event log's line count is unchanged.
  3. Row: a **pre-fix** row (same event id, no `mission_id` key in the JSON) is accepted as
     sound — `verify_backfill(...).ok is True` — because read-back resolves it to the
     declared id (research Decision 5).
  4. Row: a declared **ULID** mission id still writes that ULID on the envelope and still
     verifies (ratchet, FR-002 side of the pair).
  5. Row: a `meta.json` that declares **no** `mission_id` still writes a row with no
     `mission_id` key and still verifies (FR-003, INV-3).
- **Files**: same test file.
- **Notes**: Build rows 1–3 from one shared fixture helper so the positive and negative cases
  cannot drift.

### T005 – Fail-closed controls on the same fixture

- **Purpose**: C-003 / NFR-003 / SC-003. The suite must fail if someone "fixes" the issue by
  widening the verifier's tolerance instead.
- **Steps**:
  1. Tampered payload: mutate the persisted claim row's `policy_metadata["agent"]`; assert
     `verify_backfill` returns `ok is False` with `claim mismatch` in the message.
  2. Missing seed: delete the claim row; assert `ok is False` with
     `deterministic seed missing`.
  3. Strip-before-verify: after a successful seed, call
     `strip_mutable_fields(...)` and assert `verify_backfill` raises
     `MigrationOrderingError` naming the stripped key.
  4. Positive control: on the untouched fixture, assert `verify_backfill(...).ok is True`
     (and that the claim row is still present) — in the same test module, ideally in the
     same test as its refusal sibling, per the tactic
     `acceptance-criteria-non-vacuity`.
- **Files**: same test file.
- **Notes**: Do not assert on a helper-only path for the refusal rows if a public/production
  path exists; prefer `verify_backfill` / `run_backfill_and_verify`, which is what the cutover
  calls.

### T006 – Green through the CLI entry point, plus whole-shape regression

- **Purpose**: Demonstrate the same rows that were red are now green, without editing their
  assertions.
- **Steps**:
  1. Re-run T001/T002 rows; they must pass with **no** change to their assertions.
  2. Confirm `status_phase` flips and the summary reports the Mission as flipped.
  3. Re-run the second-run row to confirm convergence.
- **Files**: same test file.
- **Notes**: If a row needs its assertion changed to pass, the fix is wrong — stop and
  re-read `plan.md` IC-01.

### T007 – Local gates

- **Purpose**: Catch typing/lint/regression breakage before review.
- **Steps**:
  1. `uv run ruff check src/specify_cli/migration/backfill_runtime_state.py tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py`
  2. `uv run ruff format --check` on the same files.
  3. `uv run mypy src/specify_cli/migration/backfill_runtime_state.py`
  4. `uv run pytest tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py -q`
  5. `uv run pytest tests/unit/migration/test_backfill_runtime_state.py -q`
  6. `uv run pytest tests/specify_cli/migration/test_runtime_state_cutover.py tests/specify_cli/migration/test_mission_id_primary_leg.py tests/specify_cli/migration/test_seed_anchor_determinism.py -q`
     (the mission-id/ordering neighbours of the changed seam).
  7. `uv run pytest tests/regression tests/migration -q` only if it is already part of your
     normal blast-radius run; **never** a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Notes**: Record every command and its pass/fail counts for the PR's `## Tests run`.
  A red you cannot attribute: reproduce it on pristine `origin/main` in a clean worktree
  before deciding it is pre-existing, then name it in `## Deferred` with its issue number.

## Test Strategy

Required. The new file is the red-first proof and the standing ratchet:

| Row | Kind | Proves |
| --- | --- | --- |
| engine convergence on the reported shape | positive | FR-001, FR-002, SC-001 |
| CLI exit 0 + `status_phase` flip | positive (production path) | FR-008, SC-001 |
| second run seeds 0 | positive | FR-005, SC-002, NFR-001/2 |
| seed id unchanged | ratchet | FR-004, INV-2 |
| pre-fix row sound | positive | FR-009 |
| declared ULID / undeclared id | ratchet | FR-002/FR-003, INV-3 |
| tampered / missing seed / strip-before-verify | refusal + positive control | FR-006, FR-007, NFR-003, SC-003 |

Commands are listed in T007; typecheck is part of the gate because this module is typed.

## Risks & Mitigations

- **Accidental namespace change** → T004 row 1 pins the literal pre-fix seed id.
- **Widened tolerance instead of a fix** → T005 refusal rows plus their positive controls.
- **Reader change snuck in** → NFR-004: `src/specify_cli/status/store.py` must not be in the
  diff; a reviewer will check.
- **Fixture drift from the report** → the fixture is transcribed from the issue body; the
  seed id it mints (`0RWXZFHX7REDZWCZC43GQB3SPF`) is the cross-check.
- **Shared machine**: other agents are running; do not rebuild the whole CLI docs reference
  or race the installed CLI's global asset cache.

## Review Guidance

- Confirm the diff is writer-side only, one predicate plus one helper plus the two callers.
- Confirm `_seed_row_mismatch`, `_verify_expected_seed_events`,
  `_verify_claim_slot_witnesses` and `status/store.py` are untouched.
- Confirm every refusal row has a positive control built from the same fixture.
- Confirm the new test file's assertions were not edited to reach green (compare against the
  pre-fix run recorded in the PR body).
- Confirm no new tolerance/`xfail`/`skip` was introduced anywhere in the diff.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in
this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
