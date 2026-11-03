---
work_package_id: WP01
title: Pin the twelve lifecycle constants to spec_kitty_events
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6876-lifecycle-vocabulary-parity
merge_target_branch: issue-6876-lifecycle-vocabulary-parity
branch_strategy: Planning artifacts for this mission were generated on issue-6876-lifecycle-vocabulary-parity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6876-lifecycle-vocabulary-parity unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Guard
history:
- at: '2026-11-03T13:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/status/
create_intent:
- tests/status/test_lifecycle_events_package_parity.py
- docs/changelog/unreleased/6876-lifecycle-vocabulary-parity.internal.md
execution_mode: code_change
model: sonnet
owned_files:
- tests/status/test_lifecycle_events_package_parity.py
- docs/changelog/unreleased/6876-lifecycle-vocabulary-parity.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pin the twelve lifecycle constants to `spec_kitty_events`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- `tests/status/test_lifecycle_events_package_parity.py` exists, is marked `fast`, and fails —
  naming the constant and both values — when any one of the twelve lifecycle constants in
  `specify_cli.status.lifecycle_events` stops matching the same-named top-level attribute of
  `spec_kitty_events`.
- `LIFECYCLE_EVENT_TYPES` is asserted to be exactly the twelve canonical values and
  `POST_MISSION_LIFECYCLE_EVENT_TYPES` exactly the two post-mission values, with the post-mission
  pair a subset of the twelve.
- The CLI's twelve are asserted to be a *strict* subset of the package's wide vocabulary
  (`CANONICAL_LIFECYCLE_EVENT_TYPES | MISSION_EVENT_TYPES`, 22 values on the pinned 11.3.0), with
  the reason the CLI is narrower recorded in the module docstring.
- The module passes unchanged when the twelve literals are replaced by the #6447 import — it
  compares values, never syntax.
- `src/specify_cli/status/lifecycle_events.py` is byte-identical to `origin/main` in the final
  diff.

## Context

Issue #6876 was filed because two frozen in-core contract tools (`contracts/tools/event_mapping_check.py`,
`contracts/tools/citation_check.py`) parsed `status/lifecycle_events.py` with `ast` and rejected
imported names, which blocked #6447's "delete the literals" change. Grounding for this mission
(full detail in `research.md`) established that both tools — and the D-9 freeze gate that pinned
them — were removed from core by `a212ccdf55` (*"refactor!: remove core's copies of the events
service and contracts"*, 2026-11-01, `Refs #6915`, `Refs #6117`). The import is no longer blocked
in core, and that deletion is #6447's change.

What the removal left behind is an unguarded copy: nothing in `tests/` compares the CLI's twelve
lifecycle strings with the values `spec_kitty_events` publishes, so a package rename or a drifted
local literal reaches consumers as an event type their validator rejects. This work package lands
that comparison as a local, fast pin, and deliberately does so without re-introducing static
source parsing.

Read first: `kitty-specs/lifecycle-vocabulary-parity-01M6GSPC/spec.md` (FR/NFR/SC),
`research.md` (D-1 .. D-5), `plan.md` (IC-01 .. IC-03, including the measured correction about the
package's two vocabularies), and `docs/adr/4.x/2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md`
(D-9 and its exit clause).

## Detailed Guidance per Subtask

### T001 — The per-constant parity cases

- Source the CLI side from the module: `import specify_cli.status.lifecycle_events as lifecycle`.
- Source the package side **by name**: `getattr(spec_kitty_events, name)`. All twelve exist at the
  package top level on `spec-kitty-events>=11.3.0,<12` (`PROJECT_INITIALIZED`, `MISSION_CREATED`,
  `SPECIFY_STARTED`, `SPECIFY_COMPLETED`, `PLAN_STARTED`, `PLAN_COMPLETED`, `TASKS_STARTED`,
  `TASKS_COMPLETED`, `WP_CREATED`, `REVIEWER_SELF_APPROVAL`, `MISSION_REOPENED`,
  `FOLLOW_UP_RECORDED`).
- FR-004: resolve with an explicit existence check first
  (`if not hasattr(spec_kitty_events, name): pytest.fail(...)` naming the symbol and the pinned
  floor), so a rename in a future release reads as a named failure rather than an `AttributeError`
  from inside the assertion.
- Parameterize over a module-level tuple of the twelve names; assert equality with both values in
  the assertion message (`f"{name}: CLI {cli_value!r} != package {pkg_value!r}"`). Do not assert
  `is` (identity), and do not assert the literal text anywhere.

### T002 — Membership exactness

- `LIFECYCLE_EVENT_TYPES` equals the set of the twelve package values (built from the same
  parameterized tuple, so there is one list of names in the module).
- `POST_MISSION_LIFECYCLE_EVENT_TYPES` equals exactly the two post-mission values, and is a subset
  of `LIFECYCLE_EVENT_TYPES`.
- Assert `len(...) == 12` / `== 2` separately: a set comparison alone hides a duplicate-name typo
  only if the package values collide, and the count states the intent plainly.

### T003 — Narrower by design

- Wide set: `spec_kitty_events.CANONICAL_LIFECYCLE_EVENT_TYPES | spec_kitty_events.MISSION_EVENT_TYPES`.
  Measured on 11.3.0: 13 + 9 = 22, disjoint, so the CLI's twelve are a strict subset and the
  package is wider by ten — the comparison the issue records.
- Assert `CLI < wide` (strict subset). Do **not** assert the exact ten-member difference: a future
  package addition is legitimate and must stay green.
- Docstring must say why the CLI is narrower: `LIFECYCLE_EVENT_TYPES` feeds
  `AUTHORITATIVE_NON_LANE_EVENT_TYPES` (what repair preserves) and the append guard, so deriving it
  from the package's wide vocabulary would change behaviour (#6447 triage, 2026-10-19).

### T004 — Prove the teeth (SC-001)

Do this by hand, record the commands and the output excerpts in the PR body's `## Tests run`:

1. `cp src/specify_cli/status/lifecycle_events.py /tmp/le.bak`
2. Change `TASKS_STARTED = "TasksStarted"` to `"TaskStarted"`.
3. `uv run pytest tests/status/test_lifecycle_events_package_parity.py -q` → exactly the
   `TASKS_STARTED` case fails and the message shows both values.
4. `git checkout -- src/specify_cli/status/lifecycle_events.py`, re-run → green.
5. Drop `WP_CREATED` from `LIFECYCLE_EVENT_TYPES`, re-run → the membership case fails; restore.

Never leave the mutation in the diff; verify with `git diff origin/main -- src/` being empty.

### T005 — Prove declaration-agnosticism (SC-003 / FR-005)

Apply the #6447 import locally (replace the twelve literal assignments with
`from spec_kitty_events import (...)`), re-run the module → green, then restore. This is the
proof that the pin does not re-create the deadlock #6876 records. Do not commit it.

### T006 — Changelog fragment

`docs/changelog/unreleased/6876-lifecycle-vocabulary-parity.internal.md` (rename to `<pr>.internal.md`
once the PR number exists; see `docs/changelog/unreleased/README.md`). `internal` section: this is
test-only, no user-facing behaviour change. One entry, bold impact-first lead with `(#6876)`, style
checked by `uv run --frozen python -m scripts.docs.check_changelog_style`.

### T007 — Targeted verification

- `uv run pytest tests/status/test_lifecycle_events_package_parity.py tests/status/test_lifecycle_events.py -q`
- `uv run ruff check tests/status/test_lifecycle_events_package_parity.py`
- `uv run ruff format --check tests/status/test_lifecycle_events_package_parity.py`
- `uv run --frozen python -m scripts.docs.check_changelog_style`
- Record a `Self-review:` block: what you checked, what you deliberately did not change, and any
  residual risk.

## Branch Strategy

Planning artifacts were generated on `issue-6876-lifecycle-vocabulary-parity`; this WP's completed
change merges back into the same branch (single-branch mission, `lanes.json` allocates the lane).
The PR is opened from that branch to `main` by the orchestrator; do not push `main`.

## Definition of Done

- The module and fragment exist, are committed on the mission branch, and the module is green on
  the unmodified tree.
- The three mutation/import probes in T004/T005 are recorded with their outputs, and the tree
  carries none of them.
- `git diff origin/main -- src/` is empty.
- Ruff and the changelog style check pass on the touched files.

## Reviewer Guidance

- Confirm the test would actually fail on a drift: read the assertion, not just the green run, and
  check the parameterized names cover all twelve.
- Confirm nothing asserts source shape/declaration (that is the #6876 failure mode returning).
- Confirm `src/` is untouched and `#6447`'s file is not edited.
- Confirm the subset assertion cannot pass vacuously (an empty or one-member CLI set must still
  fail the exact-membership case).
