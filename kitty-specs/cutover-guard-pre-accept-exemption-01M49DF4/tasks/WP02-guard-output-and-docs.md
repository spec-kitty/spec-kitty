---
work_package_id: WP02
title: Actionable guard output and docs
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- SC-004
planning_base_branch: fix/cutover-guard-pre-accept-exemption
merge_target_branch: fix/cutover-guard-pre-accept-exemption
branch_strategy: Planning artifacts for this mission were generated on fix/cutover-guard-pre-accept-exemption. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/cutover-guard-pre-accept-exemption unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cutover-guard-pre-accept-exemption-01M49DF4
base_commit: d25935d1b7da594907260ca52bc08481fe3c0c78
created_at: '2026-10-06T22:07:45.534627+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Operator surface
history:
- at: '2026-10-06T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/cutover_guard.py
- tests/specify_cli/cli/commands/test_cutover_guard.py
- docs/development/how-to/cutover-guard.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Actionable guard output and docs

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission cutover-guard-pre-accept-exemption-01M49DF4`). If present, every feedback item is your TODO list.

---

## Objective

WP01 added a pre-accept exemption to `is_cut_over` (a PASS may now carry the `PRE_ACCEPT_EXEMPT_NOTE` reason) and reason-specific FAIL constants in `src/specify_cli/status/cutover_eligibility.py`. Make the `spec-kitty cutover-guard` operator surface use them (FR-002, FR-007), and document the behaviour (FR-008). Read `spec.md`, `plan.md` (IC-02), and WP01's merged diff in your lane base first.

## Hard constraints

- JSON payload changes are **additive only**: never rename or remove `passed`, `touched_slugs`, `non_mission_slugs`, `failures[].slug|reasons|remedy`.
- Reuse WP01's reason constants. Never re-type the strings.
- Complexity ≤ 15; ruff, format (`--force-exclude`) and mypy clean. Terminology: "Mission".
- Targeted tests only.

## Branch Strategy

- Planning base and final merge target: `fix/cutover-guard-pre-accept-exemption`. The PR later goes to upstream `main`.
- Prepare your workspace with `spec-kitty agent action implement WP02 --agent claude --mission cutover-guard-pre-accept-exemption-01M49DF4`. It depends on WP01 and is allocated per computed lane from `lanes.json`. Use the returned path.

## Subtasks

### T007 — Guard report and payload

**File**: `src/specify_cli/cli/commands/cutover_guard.py` (`GuardVerdict` `:69`, `evaluate_touched_missions` `:169`, `remedy_command` `:241`, `_print_report` `:250`, `_payload` `:272`).

1. Add `exempt: tuple[CutOverVerdict, ...] = ()` to `GuardVerdict`. In `evaluate_touched_missions`, collect passing verdicts whose reasons contain `PRE_ACCEPT_EXEMPT_NOTE`.
2. `_print_report`:
   - Add a count line `Pre-accept (exempt)`.
   - When there are exempt Missions, list each as `<slug>: <note>` under a neutral (not red) heading, in both the passing and the failing branch.
   - The final passing line must not claim the exempt Missions are "cut over". Wording such as "All diff-touched Missions pass the cut-over check" is fine.
3. Make the remedy per reason. Keep `remedy_command(slug)` as it is for backwards compatibility, and add `remedy_for(verdict) -> str` that maps the first reason:
   - terminal-unstamped or legacy-frontmatter (and the legacy generic `status_phase not flipped…` prefix) → `spec-kitty migrate backfill-runtime-state --mission <slug>`
   - phase malformed → `fix meta.json status_phase in kitty-specs/<slug>/ (expected an integer, e.g. "1"), then rerun`
   - meta unreadable / legacy undecidable → `repair kitty-specs/<slug>/meta.json or the unreadable WP file, then rerun`
   - `absent mission_id` → `spec-kitty migrate backfill-identity`
   - anything else → the existing backfill remedy

   Use it in both `_print_report` and `_payload`. Keep the mapping a dict lookup or a short loop so complexity stays low.
4. `_payload`: add `"exempt": [{"slug":..., "reasons": [...]}]`. Leave the existing keys exactly as they are.

### T008 — Guard CLI tests

**File**: `tests/specify_cli/cli/commands/test_cutover_guard.py` (existing; follow its CliRunner/fixture patterns).

- Exempt Mission: exit 0. The human output lists the slug with the note; `--json` has `exempt[0].slug` and `passed: true`.
- An accepted, unstamped Mission: exit non-zero, and the remedy is the backfill command.
- Malformed phase: the remedy names `meta.json`.
- Absent mission_id: the remedy is `backfill-identity`.
- Existing tests stay green. If one asserted exact old wording that you deliberately changed (the "All diff-touched missions are cut over." line), update it and say why in the commit body.

### T009 — Docs

**File**: `docs/development/how-to/cutover-guard.md`. Add a section "Pre-accept Missions" that covers:
- why in-flight Missions carry no stamp (deferred to accept/consolidate, #2917);
- the exemption's conditions: event-log evidence, no or well-formed `< 1` phase, no terminal evidence (`accepted_at`/`merged_at`/`mission_number`), no legacy WP-frontmatter runtime;
- that it fails closed on undecidable input;
- the per-reason remedies;
- the accepted residual: a Mission merged mid-flight without accept and with no legacy runtime is not caught;
- a note that a coordination-topology Mission's event log may be absent from a PR head (pre-existing; follow-up).

Remove or correct any sentence that says every touched Mission must be stamped. Plain, active voice; terminology "Mission".

Also fix the stale doc path in the comment at `.github/workflows/release-readiness.yml:194` (`docs/development/cutover-guard.md` → `docs/development/how-to/cutover-guard.md`). Comment-only; do not change the job. This file is outside `owned_files`: record it as a one-line out-of-map rationale in the commit body.

### T010 — Changelog

**File**: `docs/changelog/CHANGELOG.md` (canonical; the root `CHANGELOG.md` is a symlink). Under `[Unreleased]`, in the right subsection (Fixed), add one bold impact-first lead with `(#5835, #5300)`, then before → after. Example shape:

`**In-flight PR-bound Missions no longer fail the cutover guard on their first push (#5835, #5300).** Before: once a work package was claimed, `spec-kitty cutover-guard` (and the dogfood corpus check) failed every Mission not yet accepted, until someone ran `migrate backfill-runtime-state` by hand. After: a Mission that is not yet accepted, has no `status_phase` stamp and carries no legacy WP-frontmatter runtime passes with a "pre-accept" note; accepted or merged Missions without the stamp, legacy Missions and malformed metadata still fail, each with a specific remedy.`

Then check the docs gates:
```bash
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```
If the freshness check asks for an index regen, run `.venv/bin/python scripts/docs/docs_index.py --write` and commit the regenerated index. That index path is a small out-of-map edit; record a one-line rationale.

## Test commands (targeted only)

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_cutover_guard.py tests/specify_cli/cli/commands/test_cutover_guard_pre_accept.py tests/status/test_cutover_eligibility.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/cutover_guard.py tests/specify_cli/cli/commands/test_cutover_guard.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/cli/commands/cutover_guard.py tests/specify_cli/cli/commands/test_cutover_guard.py
uv run --frozen mypy src/specify_cli/cli/commands/cutover_guard.py
```

## Definition of Done

- Exempt Missions are visible in human and JSON output. Each failure has a reason-specific remedy. The payload is backward-compatible.
- The docs and changelog entry are written; the freshness and terminology gates pass.
- Subtasks marked done via `spec-kitty agent tasks mark-status`. One conventional commit per concern is fine (`feat(cli): ...`, `docs: ...`), each citing #5835.

## Risks / reviewer guidance

- A CI log parser or other tooling may grep the old "All diff-touched missions are cut over." string: `grep -rn "are cut over" .github scripts src tests`.
- Don't let the exempt listing render red; it is not a failure.

## Activity Log

