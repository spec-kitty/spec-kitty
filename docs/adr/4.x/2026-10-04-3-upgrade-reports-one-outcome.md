---
title: 'ADR: a completed upgrade run reports one outcome'
description: 'The upgrade outcome owns the kind, reasons, messages, JSON status, closing line and exit code of a run; presentation code reads them and cannot build its own.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-05'
---

**Status:** Accepted, except the exit-code rule for unresolved drift, which is the current contract and is **pending operator confirmation** in [#5745](https://github.com/spec-kitty/spec-kitty/issues/5745) (see [Open decision](#open-decision-exit-code-for-unresolved-drift)).

**Date:** 2026-10-04

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** [#4925](https://github.com/spec-kitty/spec-kitty/issues/4925), Mission `upgrade-outcome-single-rendering-01M444Q6`. The misleading "drift in 0 file(s)" message is the first part of [#4893](https://github.com/spec-kitty/spec-kitty/issues/4893); the ordering defect in that issue is not addressed here.

**Reader:** a maintainer changing `spec-kitty upgrade` or its tests.

---

## Context and Problem Statement

`spec-kitty upgrade` already decided its exit code in one place, a `derive_exit_code` method on `UpgradeOutcome`, after the exit-honesty fixes (#3392, #5575). The text the operator reads was not decided there. Each presentation path built its own error list, and the path taken when no migrations are pending printed `Project is already up to date!` without asking the outcome anything.

The result on an up-to-date project with one hand-edited managed file:

- the text output said the project was up to date and gave no reason;
- the exit code was 1;
- `--json` said `status: failed` with the drift error.

Automation that gates on the exit code, and an operator reading the screen, got contradictory answers. A second problem sat next to it: one boolean stood for three different conditions (unresolved drift, a repair that was not applied, an incomplete dry-run preview), so a repair failure was worded `Unresolved tool-surface drift in 0 file(s)` and sent the operator to review drift that did not exist.

## Decision

`UpgradeOutcome` (`src/specify_cli/upgrade/outcome.py`) is the only object that says what an upgrade run amounted to. It owns:

- the **kind**: `applied`, `no_op`, `drift_unresolved` or `failed`;
- the **reasons** a run is not a success (`UpgradeFailureReason`), in declaration order;
- the ordered, de-duplicated list of **errors** and the **warnings**. The step that fails still words its own diagnostic; the outcome owns the order, the de-duplication and the fallback lines;
- the JSON **status** word (`success`, `up_to_date`, `failed`);
- the **closing line** of the text output;
- the **exit code**, a read-only property of the kind (`0` for `applied` and `no_op`, `1` otherwise). It is not stored, so it cannot disagree with the kind, the status or the closing line.

Precedence: any reason other than drift makes the kind `failed`. Drift alone makes it `drift_unresolved`. With no reason, the kind is `applied` if migrations ran, otherwise `no_op`. Every reason is still listed in `failure_reasons`, and every message in `errors`.

| Kind | Exit | JSON `status` | JSON `outcome` | Text closing line |
|------|------|---------------|----------------|-------------------|
| applied | 0 | `success` | `applied` | `Upgrade complete! <from> -> <to>` |
| no-op | 0 | `up_to_date` | `no_op` | `Project is already up to date!` |
| drift-unresolved | 1 | `failed` | `drift_unresolved` | `Upgrade finished, but N managed file(s) with local edits were not updated.` |
| failed | 1 | `failed` | `failed` | `Upgrade failed.` |

`no_op` means no migration ran. It does not mean nothing changed: a run with no pending migration can still create missing managed files and commit them, and it then closes with the no-op line followed by the auto-commit line.

The reasons, as they appear in JSON `failure_reasons`:

| Reason | Holds when |
|--------|------------|
| `migration_failed` | a migration did not complete |
| `activation_error` | provisioning the Mission-type activations failed |
| `worktree_failure` | a worktree could not be upgraded |
| `commit_recovery_failed` | the upgrade's auto-commit could not be completed or cleanly recovered |
| `repair_preparation_failed` | the tool-surface repair could not be prepared or its preflight failed (an unreadable agent config, a broken `charter:` pointer, two tools claiming one path) |
| `surface_repair_failed` | a prepared tool-surface repair was not applied |
| `preview_incomplete` | a dry-run preview could not be completed |
| `surface_drift` | managed files with local edits were kept and not updated ([tool-surface drift](../../context/execution.md#tool-surface-drift)) |

Rules that follow:

1. Text and JSON exit codes are equal for the same project state.
2. A non-zero exit prints every entry of JSON `errors` and never a success closing line, and it always has at least one error. A surface-repair or preview reason that recorded no message of its own always gets a generic line; a migration or commit-recovery reason gets one only when the list would otherwise be empty.
3. A completed dry run exits 0 and, on the migrations path, ends on `Dry run complete — no changes applied. (<from> -> <to> previewed)`. An incomplete preview is `failed`, and its notice is printed once. A dry run does not predict the drift exit: on a project with edited managed files it prints `Would preserve N paths requiring separate consent` and exits 0, while the real run exits 1.
4. A mission-state repair (the separately consented step) never changes the kind or the exit code. A failure of it that the repair gate did not already show is listed as a warning.
5. Drift is reported per file, in plain words. Each kept file gets one line, `Not updated, your local edit was kept: <path relative to the project> (<reason>)`, for at most 20 files and then `... and N more`. One guidance line follows: `To take the current version of a file, delete it and run 'spec-kitty upgrade' again. To keep your edit, leave the file as it is. 'spec-kitty doctor tool-surfaces' shows each file's state.` The guidance never recommends an option that overwrites the operator's edit (#5677); in particular it does not mention `spec-kitty doctor tool-surfaces --fix`, which replaces an edited file with the generated version.

Presentation code (`_display*`, `_render*`, `_build_*`, `_print*` in `cli/commands/upgrade.py`) may not build any of these itself. It asks the outcome: `outcome.errors()`, `outcome.warnings()`, `outcome.status`, `outcome.closing_line()`. The exit code is raised once, as `typer.Exit(outcome.exit_code)`, after the finalizer has run.

The contract applies to every run that reaches the finalizer, on both the migrations path and the no-migrations path. The JSON keys `outcome` and `failure_reasons` are present only on those runs. Outside the contract, each with its own output:

- the planner and compatibility paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, the agent-check flags), which keep their own exit vocabulary;
- a refused downgrade target, which emits `status: "failed"` with exit 1 and no `outcome` key;
- `--project` outside a project, which emits `{"error": …}` with exit 1;
- a declined or unanswerable confirmation prompt, which prints `Upgrade cancelled.` and exits 0 with nothing applied, also under `--json` without `--yes`.

### Open decision: exit code for unresolved drift

**Pending operator confirmation, tracked in [#5745](https://github.com/spec-kitty/spec-kitty/issues/5745).** The current contract is that unresolved tool-surface drift exits 1, on both paths. That keeps the behaviour earlier missions and tests pinned (#3392, #5575, and `agent-profile-projection-plugin-production-01KV3NGS`).

The alternative is exit 0 with a warning on a run that applied nothing. It is not chosen here. The known cost of keeping the current rule: until the drift classification issue ([#702](https://github.com/spec-kitty/spec-kitty/issues/702)) is fixed, untouched generated files can be classified as drift, so an unattended upgrade can exit 1 without any real edit. Because the kind is a value, reversing the rule later is a one-line change to `SUCCESS_KINDS` and to the table above; no presentation code changes.

Two facts the decision should weigh. An operator has no way to accept an edit and stop the flag: `upgrade` has no accept or overwrite option, so a project with one customised managed file gets exit 1 from every later upgrade. And the run has already applied and committed its migrations when it exits 1.

## Considered Options

1. **Fix only the no-migrations path.** Rejected. It would add a third place that builds an error list and leave the next path to diverge the same way.
2. **Exit 0 with a warning on drift.** Not chosen; see the open decision above.
3. **The outcome owns kind, reasons, messages, status, closing line and exit code, and a gate keeps presentation from rebuilding them (chosen).**

## Consequences

- JSON gains two keys, `outcome` and `failure_reasons`. No existing key is removed or renamed.
- A run with pending migrations and unresolved drift now closes with the drift closing line, as the no-migrations path does. It used to close with `Upgrade failed.`. The exit code is unchanged.
- After a failed commit recovery, the optional mission-state repair is not offered. A commit that could not be recovered is a failure reason (`commit_recovery_failed`) and the run should not go on to ask for another consent.
- A surface-repair or preview reason that recorded no message gets its own generic error line, even when other messages exist, so no reason is silent.
- A broken charter pack config (for example a `charter:` pointer to a missing file) is reported as an upgrade error with its remediation, in text and JSON. It used to end in a traceback with no JSON.
- When the auto-commit landed but its recovery step failed, JSON `auto_committed` is true and the text still says the commit landed.
- **Residual, not fixed here:** a worktree migration that could not be detected or applied is recorded as an error line but not as a failure reason, so that run still exits 0 with a success closing line above an `Errors:` section ([#5746](https://github.com/spec-kitty/spec-kitty/issues/5746)).
- The `drift in 0 file(s)` wording is gone: a repair that was not applied is reported as a repair failure. [#4893](https://github.com/spec-kitty/spec-kitty/issues/4893) stays open for its other defect, the ordering that makes a first run fail on some old projects. That is now reported honestly and is not fixed.
- The `upgrade` help text and the exit-code docstring now describe the dry-run exit codes as they are.
- `UpgradeResult.worktree_failures` stays a list of strings; the sibling work on `runner.py` and `assessment.py` is untouched.

### Enforcement

`tests/architectural/test_upgrade_outcome_single_rendering.py` fails when:

- closing-line text appears in `cli/commands/upgrade.py`;
- a JSON builder takes `status` from anything but `outcome.status`, `errors` from anything but the call `outcome.errors()`, or `warnings` from anything but the call `outcome.warnings()`, omits one of the three, or assigns one of them by subscript after the dict literal;
- the tail renderer never reaches a `closing_line()` call;
- a presentation function reads message state directly, fetches it with `getattr(<x>, "<name>")`, or takes an `errors` or `effective_success` parameter. A presentation function is one named `_display*`, `_render*`, `_build_*` or `_print*`, or any function with an `outcome` parameter that calls `console.print` or `print`;
- a function that must not exit does so (`typer.Exit`, `raise SystemExit`, `sys.exit` or `os._exit`). That covers every presentation function, every function that takes an `outcome`, every `_finalizer_step*` function, every function reachable from the tail of `upgrade()` after the finalizer call, and every function in `upgrade/finalize.py` and `upgrade/outcome.py`;
- anything but `raise typer.Exit(outcome.exit_code)` exits after the finalizer call in `upgrade()`.

The kind-to-exit mapping needs no shape rule: the exit code is a property, and the truth table in `tests/upgrade/test_upgrade_outcome_kind.py` pins it for every reachable combination of reasons.

It has no allowlist. Floor assertions name the real renderers, builders and exit sites, and synthetic violations prove every check can fail.

### Follow-ups, not in scope

- The planner and compatibility paths use a different exit-code vocabulary (2, 4, 5, 6). Folding them under one outcome is a separate decision.
- `repair_stale_manifest` and `remove_unsafe_symlinks` in `src/specify_cli/skills/manifest_store.py` had no production caller since the unreachable legacy branch of the surface-repair helper was removed. They were deleted as dead code; the repairs they performed are tracked in issue 5710.
- The exit code for unresolved drift, and a way for an operator to accept an edit: [#5745](https://github.com/spec-kitty/spec-kitty/issues/5745).
- A worktree migration failure that still exits 0, a confirmation prompt under `--json`, and files left behind by a failed auto-commit: [#5746](https://github.com/spec-kitty/spec-kitty/issues/5746).
- The reason shown for each kept file comes from the tool-surface provider and still uses internal wording such as "requires exact-path consent".
