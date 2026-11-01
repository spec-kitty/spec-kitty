---
work_package_id: WP02
title: Observable substantive-gate fallback and the advisory wp_driven contract
dependencies: []
requirement_refs:
- FR-002
- FR-003
- NFR-003
- SC-002
- SC-003
planning_base_branch: issue-6330-run-dir-threading
merge_target_branch: issue-6330-run-dir-threading
branch_strategy: Planning artifacts for this mission were generated on issue-6330-run-dir-threading. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6330-run-dir-threading unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-type-capability-hardening-01M6BTT4
base_commit: 11fa6a74e3cd8c09264a7e1803437737eb42f9d5
created_at: '2026-11-01T16:53:33.119396+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Charter facet
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/runtime/test_wp_driven_parity.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/mission_type_profiles.py
- tests/charter/test_resolved_mission_type_context.py
- tests/runtime/test_wp_driven_parity.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Observable substantive-gate fallback and the advisory `wp_driven` contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission mission-type-capability-hardening-01M6BTT4`) and address every item before handing back.

## Objectives & Success Criteria

Items 2 and 3 of GitHub issue #6330.

**Item 2 — observable fail-open.** `requires_substantive_spec_for`
(`src/charter/activation/mission_type_profiles.py:1042-1055`) catches every
exception and silently returns the built-in default (`False` for a custom type).
A type that authored `requires_substantive_spec: true` and whose resolution
transiently throws therefore lets a stub spec pass with no trace. Keep the
non-crashing contract, add the WARNING. The CLI helper
(`mission_check_prerequisites._requires_substantive_spec`) delegates to this
seam, so fixing it here fixes the probe; do **not** add a second copy there.

**Item 3 — advisory facet.** `ResolvedMissionType.wp_driven` is derived from the
curated `action_sequence`; the guard derives the same kernel rule from the frozen
runtime DAG. They agree for every built-in. The runtime side is authoritative;
say so on the field and pin it with a curated-away fixture.

FR-002, FR-003; SC-002, SC-003; NFR-003 (changed-line coverage).

## Context

- `src/charter/activation/mission_type_profiles.py:387` —
  `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`.
- `:1020-1039` — `_resolve_requires_substantive_spec` (declared → built-in → False).
- `:1042-1055` — `requires_substantive_spec_for` (the broad silent `except`).
- `:433` and `:708` — the `wp_driven` field and its derivation.
- `src/runtime/next/runtime_bridge_io.py:1490-1499` —
  `mission_declares_wp_iteration` (the authoritative runtime side).
- `tests/runtime/_next_mission_scaffold.py` — `scaffold_custom_analyze_mission`
  builds an activated custom family with a real frozen DAG; the family's
  `mission_types/<id>.yaml` currently declares no `action_sequence`.
- `tests/charter/test_resolved_mission_type_context.py:520-585` — the existing
  capability-facet tests to extend.

## Detailed Guidance

### T006 — Red: the fail-open is logged

In `tests/charter/test_resolved_mission_type_context.py`, add a test that
patches `charter.activation.mission_type_profiles.resolve_mission_type_context`
to raise (a transient `ValueError`/`RuntimeError` stands in for a malformed
layer) and calls `requires_substantive_spec_for(repo, "qa")`:

- the call returns `False` (built-in default; no raise),
- **one** WARNING record is emitted on the
  `charter.activation.mission_type_profiles` logger whose message names the
  mission type key and the failure.

Positive control on the same fixture: the healthy path (no patch, or a patch
returning a bundle) emits **no** warning, so the assertion can observe both
states.

### T007 — Log the fallback

In `requires_substantive_spec_for`:

- keep the same try/except boundary and the same returned value;
- log `logger.warning("requires_substantive_spec resolution failed for mission type %r; falling back to the built-in default (%s): %s", mission_type, default, exc)`
  (name the module's existing `logger`; add one if absent);
- update the docstring: the fallback is deliberate, non-crashing, and now
  observable.

Do not narrow the catch in a way that lets a new exception class escape — the
probe must never crash (NFR-002).

### T008 — Red: the curated-away parity fixture

New file `tests/runtime/test_wp_driven_parity.py`:

1. Build an activated custom family whose **frozen DAG declares `implement`**
   (reuse `scaffold_custom_analyze_mission`) but whose mission-type YAML declares
   an explicit `action_sequence` **without** `implement` (write it in the type
   file the scaffold creates, or extend the scaffold in your own test module —
   do not modify the shared scaffold).
2. Assert the charter DTO reports `wp_driven is False` **and**
   `resolve_mission_type_context(...).action_sequence` omits `implement`
   (advisory value).
3. Assert `_check_composed_action_guard("implement", feature_dir, mission=<family>,
   repo_root=<repo>, run_dir=<real run dir>)` returns the pending-WP failure:
   the run's frozen DAG wins.
4. Same-fixture control: a family whose DAG has no `implement` returns `[]`.

Mark `pytestmark = [pytest.mark.git_repo]` like the neighbouring guard tests.
The advisory clause is pinned mechanically: assert
`"advisory" in ResolvedMissionType.__doc__.lower()` and that the same docstring
names the frozen runtime DAG, so T009's documentation change is what makes that
assertion pass (it is red before T009, green after).

### T009 — Document and changelog

- On the `wp_driven` field (and the class docstring if it reads better), state:
  derived from the curated `action_sequence`; **advisory** for CLI/external
  consumers; the frozen runtime DAG is authoritative for the guard, and the two
  are kept in parity by `tests/runtime/test_wp_driven_parity.py`.
- Add one `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root
  `CHANGELOG.md` is a symlink): a bold impact-first lead with `(#6330)`, a
  before/after, under 1,200 characters. Cover both the guard fail-open and the
  observable fallback; mention the advisory facet in one clause. Follow the
  surrounding entries' shape exactly (section ordering, link targets).

## Branch Strategy

- Planning base and merge target: `issue-6330-run-dir-threading`.
- Execution worktrees are allocated per computed lane from `lanes.json`.
- Run `spec-kitty agent action implement WP02 --agent <name> --mission mission-type-capability-hardening-01M6BTT4`.

## Test Strategy

- `uv run pytest tests/charter/test_resolved_mission_type_context.py -q`
- `uv run pytest tests/runtime/test_wp_driven_parity.py -q`
- `uv run pytest tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py -q`
  (the resume probe still behaves; the CLI helper is not modified).
- No full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- Both new tests fail before the fix and pass after; the positive controls prove
  they are not vacuous.
- The returned values of `requires_substantive_spec_for` are unchanged for every
  non-raising path (T007 changes observability only).
- No new external reach into `charter.activation` internals (C-002): tests import
  the public seam where they speak for a consumer.
- Changelog entry present and under the 1,200-character cap.
- ruff / ruff format / mypy clean on the touched module.

## Risks & Reviewer Guidance

- **Risk**: logging on every probe could be noisy. It fires only on an exception;
  reviewer: confirm there is no per-call success-path log.
- **Risk**: the parity fixture accidentally proves the guard by re-resolving from
  the directory name (i.e. it would pass even without WP01). Reviewer: the call
  must pass `run_dir=` explicitly, and the fixture's directory name must be the
  real slug so the assertion is about the DAG, not the directory.
- **Reviewer**: confirm the changelog entry names the user-visible effect (the
  guard no longer fail-opens; a failed capability resolution is now logged), not
  the implementation.
