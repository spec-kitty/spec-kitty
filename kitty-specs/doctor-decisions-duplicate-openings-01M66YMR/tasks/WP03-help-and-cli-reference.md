---
work_package_id: WP03
title: Document the finding in the command help and regenerate the CLI reference
dependencies:
- WP01
requirement_refs:
- FR-002
- C-002
planning_base_branch: issue-6764-doctor-decisions-duplicate-openings
merge_target_branch: issue-6764-doctor-decisions-duplicate-openings
branch_strategy: Planning artifacts for this mission were generated on issue-6764-doctor-decisions-duplicate-openings. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6764-doctor-decisions-duplicate-openings unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-decisions-duplicate-openings-01M66YMR
base_commit: 2fa76e51d1db3ab91bdac6fc0a3ea99e9933a7cd
created_at: '2026-10-30T18:42:08.389169+00:00'
subtasks:
- T010
- T011
- T012
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T18:30:00Z'
  actor: system
  action: 'Prompt generated via /spec-kitty.tasks (split out of WP02: the help body lives in src/)'
agent_profile: reviewer-renata
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/doctor.py
- docs/api/cli-commands.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Document the finding in the command help and regenerate the CLI reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `reviewer-renata`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `specify-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check `spec-kitty agent tasks status`.
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

`spec-kitty doctor decisions --help` — and therefore the generated
`docs/api/cli-commands.md` section — describes the new informational finding, and the
documented example of a malformed fold is no longer the stale "`open -> open` corruption"
that #4848 made legal.

- The `doctor decisions` docstring in `src/specify_cli/cli/commands/doctor.py` names the
  informational finding, the `duplicate_openings_tolerated` `--json` key, and states that
  the exit code and the clean verdict are unaffected.
- `docs/api/cli-commands.md` is REGENERATED (never hand-edited) and its diff touches only
  the `doctor decisions` section.
- `check_docs_freshness --ci` reports `errors=0` with no HELP-DRIFT finding for
  `doctor decisions`, and the help-snapshot golden test passes.

## Context & Constraints

- `docs/api/cli-commands.md` is a hybrid document: command sections live inside the
  `<!-- BEGIN GENERATED -->` / `<!-- END GENERATED -->` envelope and are produced by
  `scripts/docs/build_cli_reference.py` from the live Typer surface. A hand edit inside the
  envelope is overwritten on the next regeneration and shows up as HELP-DRIFT.
- The `doctor decisions` shell is `@app.command("decisions")` in
  `src/specify_cli/cli/commands/doctor.py`; it delegates to
  `specify_cli.cli.commands._decisions_doctor.run_decisions_reconciliation` (WP01).
- `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` pins each doctor
  subcommand's `--help` body as a whitespace-normalized snapshot. If it fails after your
  docstring edit, update the snapshot it records for `doctor decisions` — that is the
  intended, reviewed way to change help text, not a gate to weaken.
- Wording must stay in the operator's voice and must not promise anything WP01 does not do.

## Branch Strategy

- **Strategy**: coord topology; completed changes merge into the mission's target branch.
- **Planning base branch**: `issue-6764-doctor-decisions-duplicate-openings`
- **Merge target branch**: `issue-6764-doctor-decisions-duplicate-openings`

Claim and run this package with:

```bash
spec-kitty agent action implement WP03 --agent reviewer-renata --mission doctor-decisions-duplicate-openings-01M66YMR
```

## Subtasks & Detailed Guidance

### Subtask T010 – Update the `doctor decisions` help body

- **Purpose**: The help body is the source of truth for both `--help` and the committed
  reference.
- **Steps**:
  1. Open `src/specify_cli/cli/commands/doctor.py`, find `def decisions(` and its docstring
     (starts "Diagnose or repair divergence between ``decisions/index.json``").
  2. Extend the "Diagnose (default)" paragraph: it also prints an **informational** finding
     naming each decision whose event log holds several `DecisionPointOpened` rows that are
     equal apart from their recorded time. State that such rows are tolerated (the fold
     keeps the earliest, #4848), that the log is left unchanged, and that the finding never
     affects the exit code or the clean verdict. Name the `duplicate_openings_tolerated`
     `--json` key.
  3. Fix the stale malformed example: an identical `open -> open` pair is tolerated since
     #4848; the malformed case is openings that DIFFER beyond their recorded time.
  4. Keep the paragraph widths and voice consistent with the rest of the docstring; keep
     lines wrapped like their neighbours.
- **Files**: `src/specify_cli/cli/commands/doctor.py`
- **Parallel?**: no — T011 consumes it.
- **Notes**: docstring-only change to a CLI shell; do not alter the delegation line.

### Subtask T011 – Regenerate the CLI reference

- **Purpose**: Keep the committed reference byte-identical to the live surface.
- **Steps**:
  1. Run `uv run python -m scripts.docs.build_cli_reference` (default hybrid mode writes
     `docs/api/cli-commands.md` and `docs/api/agent-subcommands.md`).
  2. Inspect `git diff --stat` and `git diff docs/api/cli-commands.md`: the ONLY changed
     section must be `## spec-kitty doctor decisions`. If the regeneration rewrites
     unrelated sections, stop and report — that means the committed reference was already
     stale, which is a separate finding, not something to sweep into this PR.
  3. Confirm `docs/api/agent-subcommands.md` is unchanged (no agent path moved).
- **Files**: `docs/api/cli-commands.md`
- **Parallel?**: no — needs T010.
- **Notes**: the generator refuses to overwrite a dirty target; commit nothing mid-way, or
  pass `--force` only if you understand why it refused.

### Subtask T012 – Verify the docs and help gates

- **Purpose**: Prove the reference, help and golden snapshot agree.
- **Steps**:
  1. `uv run python -m scripts.docs.check_docs_freshness --ci` — expect `errors=0` and no
     HELP-DRIFT/HEX-DRIFT finding for `doctor decisions`.
  2. `uv run python -m pytest tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py -q`.
     If it fails on the `decisions` help snapshot, update that snapshot from the live help
     and re-run; record the change in your hand-off note.
  3. `uv run python -m pytest tests/architectural/test_docs_cli_reference_parity.py tests/architectural/test_no_legacy_terminology.py -q`.
  4. Record the exact commands and results in your hand-off note.
- **Files**: none (verification; plus the golden snapshot file if T012 step 2 requires it)
- **Parallel?**: no — last.
- **Notes**: do not weaken or skip a gate; if the golden snapshot legitimately changes, that
  is a reviewed snapshot update, not a skip.

## Test Strategy

The gates in T012 are the tests. No new behavioural test in this package: WP01 owns the
behavioural proof.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Regeneration rewrites unrelated sections because the committed reference was already stale | Stop and report as a separate finding; do not ship unrelated churn in this PR. |
| Help text promises a warning/exit-code change the implementation does not make | Say "informational" and that exit codes are unaffected. |
| Golden help snapshot fails | Update the recorded snapshot for `doctor decisions` only. |

## Review Guidance

- The help text matches WP01's actual behaviour exactly.
- `git diff docs/api/cli-commands.md` touches one section only.
- No gate skipped or weakened.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
