---
title: finalize-tasks internals reference
description: 'finalize-tasks internals: empty owned_files, lane-depth cycle safety, the planning-pin refresh (override and automatic), and the LANE_MEMBERSHIP_FROZEN refusal.'
doc_status: active
updated: '2026-10-04'
---
# `finalize-tasks` internals reference

Five non-obvious behaviours an operator may encounter when running
`spec-kitty agent mission finalize-tasks`. All have regression tests
under `tests/specify_cli/cli/commands/` and `tests/specify_cli/lanes/`.

## 1. Explicit empty `owned_files`

The finalize-tasks linter normally infers `owned_files` from path-like
strings in the WP body. This is helpful when the author never set the
field. It surprises an operator who EXPLICITLY set `owned_files: []`
because the WP is a triage / planning-artifact / acceptance task that
owns no source or test files.

The fix at commit `0f4e1a383` adds a pre-check: when the frontmatter
contains the literal pattern `^owned_files:\s*\[\s*\]\s*$`, inference
is skipped for that field. Authors who legitimately own no files write:

```yaml
---
work_package_id: WP01
execution_mode: planning_artifact
owned_files: []
authoritative_surface: docs/triage/
---
```

The ownership validator still rejects this if the WP is marked
`execution_mode: code_change` (a code-change WP that owns no files is
suspicious by definition).

## 2. Lane-depth cycle safety

`_compute_lane_depths` walks the lane-dependency DAG and assigns each
lane a depth (parallel group). The original implementation recursed
without cycle detection: any self-loop or cycle in `lane_deps` blew the
recursion stack with `maximum recursion depth exceeded`.

The fix at commit `72ff0d723` adds an `in_progress` guard and a
self-reference filter. Cycle detection is best-effort:

- A lane currently being computed is treated as depth-0 when
  re-encountered (breakpoint).
- Self-references in `lane_deps` are filtered before the recursion.

For a clean DAG (the common case) output is unchanged. For a cyclic
graph, the function returns a dict with each lane present and an
integer depth — but the depth value may not reflect graph reality. The
proper fix for a cyclic lane graph is to validate the inputs upstream
(in the WP-dependency parser), not to "solve" the cycle in the depth
function.

Both fixes are locked by tests in:

- `tests/specify_cli/cli/commands/test_finalize_tasks_explicit_empty_owned_files.py`
- `tests/specify_cli/lanes/test_compute_lane_depths_cycle_safety.py`

Removing those tests, or weakening their assertions to permit recursion,
is a regression.

## 3. Refreshing the recorded planning commit after an amendment (#4141)

`finalize-tasks` freezes `planning_commit_sha` into `lanes.json` at first
run. Once execution has begun (any WP past `planned`), a re-finalize
PRESERVES that recorded SHA (#3311) — correct for an ownership-only
amendment, which must not silently clobber established planning provenance.
But preserve-only left no sanctioned way to advance the SHA after a
legitimate planning amendment (a WP dependency-field fix, an `/spec-kitty
.analyze` remediation) landed mid-execution: every subsequently allocated
lane kept merging the stale planning snapshot, the `move-task` gates
(branch-currency / `kitty-specs/` contamination / uncommitted-changes) fired
on the resulting drift, and the only in-tool path was `--force` on every
transition.

The fix adds an explicit, advance-only override:

```bash
spec-kitty agent mission finalize-tasks --mission <slug> --refresh-planning-commit
```

- With execution begun, the recorded SHA is re-pointed to the current
  target-branch tip, so lanes merge the amended planning state at their next
  allocation/reuse.
- The override is refused (exit 1, `lanes.json` untouched) when the recorded
  SHA is not an *ancestor* of the tip — a history rewrite or a foreign
  provenance SHA, not an amendment. Resolve the divergence manually instead.
- Without the flag, the #3311 preserve behavior is unchanged, but a
  re-finalize that detects drift (recorded SHA ≠ branch tip) now warns on
  the console and names the flag; the `--json` success payload carries the
  decision structurally under `planning_commit`
  (`action` / `sha` / `previous_sha` / `branch_tip`).

Locked by tests in:

- `tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py`
- `tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py` (the
  `_preserve_or_capture_planning_commit_sha` / `_report_planning_sha_decision`
  branch tests)

Weakening the ancestor refusal, or making the refresh the default (no flag),
is a regression.

## 4. Automatic planning-pin refresh and `planning_commit_refresh`

Without `--refresh-planning-commit`, a re-finalize after execution has begun no longer only
preserves the recorded pin. It classifies the recorded `planning_commit_sha` against the
target-branch tip (`PinClass` in `src/specify_cli/lanes/planning_commit_classify.py`) and
acts on the class:

| Pin class | Meaning | Result (exit code) |
|---|---|---|
| `ADVANCED` | The recorded object is present and an ancestor of the tip | Refreshed to the tip **only when** a PRIMARY planning file changed since the pin for a reason other than finalize's own earlier bookkeeping commits; otherwise preserved (0) |
| `ORPHANED` | Present but not an ancestor (a mid-Mission rebase, #4827) | Fails closed before any write; `lanes.json` untouched; use `--refresh-planning-commit --allow-orphaned` (1) |
| `FOREIGN` | The recorded object is absent from this repository | Kept, with a visible warning when the tip has advanced (0) |
| `INDETERMINATE` | Nothing can be inspected (tip not capturable, or no recorded SHA) | Kept, with a visible warning and reason `indeterminate_tip_uncapturable`; never a silent preserve (0) |

The `--json` success payload carries the automatic decision in an additive field:

```json
"planning_commit_refresh": {
  "status": "refreshed",
  "recorded": "<previous sha>",
  "candidate": "<branch tip>",
  "pin_class": "advanced",
  "reason": null
}
```

`status` is `preserved`, `refreshed` or `kept_with_warning`; `reason` is set only for
`kept_with_warning`. The field is `null` before execution begins and for an explicit
`--refresh-planning-commit` run, which keeps reporting through `planning_commit` (section 3).
The explicit flag and its refusals are unchanged. Code: `PlanningCommitResolution` and
`_planning_commit_refresh_payload` in
`src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py`.

## 5. Started work packages keep their lane (`LANE_MEMBERSHIP_FROZEN`)

A re-finalize (any run on a Mission that already has a `lanes.json`) keeps every
[started work package](../context/topology.md#started-work-package) on its recorded
lane, or refuses before writing anything (#5573). Design and rationale: ADR
[4.x `2026-10-04-2`](../adr/4.x/2026-10-04-2-started-work-package-lane-membership-is-frozen.md);
the lane-id rule is explained in
[Execution Lanes](../architecture/execution-lanes.md#re-finalizing-an-active-mission).

### Where the check runs

`_preflight_frozen_lane_membership` (`mission_finalize_lanes.py`) runs in
`finalize_tasks` after the ownership gates (`_run_finalize_ownership_gates`) and
before the first status write (`_emit_tasks_started`). It is read-only: it builds
the frozen membership and dry-runs `compute_lanes` with it against the previous
`lanes.json`.

- A first finalize (no `lanes.json`) reads nothing and constrains nothing.
- A `single_branch` Mission skips the check: its one repo-root lane has nothing to move.
- A `--refresh-planning-commit` run skips the check: it never recomputes lane membership.
- A lane dependency cycle (`LaneDependencyCycleError`, `LANE_DEPENDENCY_CYCLE`) is
  raised here too, with its existing envelope: keeping started lane-mates together can
  close a lane cycle that the unfrozen inputs would not have, and the real lane write
  would raise it only after the status writes.
- Any other lane-computation failure is left to the real lane write, which reports it
  with its existing text.
- The lane writer (`compute_and_write_lanes`) re-checks the invariant with
  `assert_frozen_membership_honoured` before it writes `lanes.json`.

### Evidence

| Evidence | Source | Notes |
|---|---|---|
| Started work packages | The status event log, read from the resolved status surface (`_resolve_status_read_dir`: the placement seam for an owned checkout, otherwise the coordination-aware status surface) | History-based (`started_wp_ids`): any event into `claimed`, `in_progress`, `for_review`, `in_review`, `approved` or `done`. A status directory that exists but holds no event log means nothing started. When the status directory does not exist because the coordination worktree is not materialized (`CoordinationWorktreeUnmaterialized`), the log committed on the local coordination branch is read instead (`_started_on_coordination_branch`: `git ls-tree` + `git cat-file` on `refs/heads/<coordination branch>`, parsed with `read_events_from_text`). That read refuses (`status_unreadable`) when the branch is not a local head, carries no committed log, or the log is malformed. Any other missing status directory refuses: an absent surface is not an absent log. Never calls `materialize()` and never materializes the worktree. The read uses the local coordination branch only and never fetches, so a WP started in another clone whose coordination commits were not fetched can look unstarted; the lane-work-tip fallback still freezes a lane with recorded work in this clone. This is an accepted, documented limit. |
| Lane work tips (fallback) | `recorded_tip_branches`: one `git for-each-ref refs/spec-kitty/lane-tip/` call | Read only when a prior code lane has no history-started member; such a lane with a recorded tip counts as wholly started. A git failure yields no fallback evidence. `lane-planning` is never tip-frozen. |
| Retired work packages | The cancellation projection (present work packages minus lane inputs) | A missing started work package that was retired is leaving, not moving: no conflict, and its lane id stays reserved. |

### `--validate-only`

The preflight runs before the validate-only report, so `--validate-only` refuses
in exactly the cases a real run refuses. Its lane preview now passes the previous
`lanes.json` and the frozen membership to `compute_lanes`, so the previewed
`lane_ids` match what a real run writes. Before #5573 the preview minted lane ids
positionally.

### Refusal envelope

Exit code `1`. Nothing is written: no status event, no `lanes.json`, no commit, and
finalize's write-scope restore leaves work package files, `tasks.md` and `meta.json`
byte-identical. With `--json`:

```json
{
  "error": "Cannot re-finalize: started work packages would change lane. WP01 (lane-a) and WP02 (lane-b) would be merged into one lane.",
  "error_code": "LANE_MEMBERSHIP_FROZEN",
  "reason": "started_lanes_collapsed",
  "conflicts": [
    {
      "reason": "started_lanes_collapsed",
      "wp_ids": ["WP01", "WP02"],
      "recorded_lanes": ["lane-a", "lane-b"],
      "remedy": "Remove the overlap that forces WP01 and WP02 into one lane (for example, move the shared path into a new work package that depends on them, or drop it from one of them), then re-run finalize-tasks."
    }
  ],
  "next_step": "Remove the overlap that forces WP01 and WP02 into one lane (...), then re-run finalize-tasks.",
  "spec_kitty_version": "..."
}
```

- Always present: `error`, `error_code`, `reason`, `conflicts`, `next_step`,
  plus the standard `spec_kitty_version`. Finalize's existing extra keys may also
  appear when they apply: `target_branch_override_revert_error`,
  `status_commits_not_undone`, and `stale_repository_root_copy` (owned checkouts).
- `conflicts` lists every conflict found. Each has `reason`, `wp_ids`,
  `recorded_lanes` (both sorted) and `remedy`.
- `reason` is the first conflict reason in the order `started_lanes_collapsed`,
  `started_wp_removed`, `started_wp_kind_changed`, `status_unreadable`.
  `next_step` lists the distinct remedies, one per line, in the same order.

Without `--json` the console prints the error, then one line per conflict and its
remedy:

```text
Error: Cannot re-finalize: started work packages would change lane. WP01 (lane-a) and WP02 (lane-b) would be merged into one lane.
  started_lanes_collapsed: WP01 (lane-a), WP02 (lane-b)
  Remedy: Remove the overlap that forces WP01 and WP02 into one lane (...), then re-run finalize-tasks.
```

### Reasons and remedies

Code: `LaneMembershipFrozenError` (`src/specify_cli/lanes/compute.py`); conflicts and
remedy texts: `src/specify_cli/lanes/frozen_membership.py`.

| `reason` | Trigger | Remedy (as printed) |
|---|---|---|
| `started_lanes_collapsed` | One computed group holds started work packages recorded in two or more lanes | Remove the overlap that forces {WPs} into one lane (for example, move the shared path into a new work package that depends on them, or drop it from one of them), then re-run finalize-tasks. |
| `started_wp_removed` | A started work package is missing from the plan, and the cancellation projection did not retire it | Restore the task file of {WPs}. To retire a started work package instead, cancel it with `spec-kitty agent tasks move-task <WP> --to canceled --mission <handle>` without clearing its owned files, then re-run finalize-tasks. |
| `started_wp_kind_changed` | A started work package's `execution_mode` now puts it on the other side of `lane-planning` | Restore the `execution_mode` of {WPs}, put the new kind of work in a new work package, then re-run finalize-tasks. |
| `status_unreadable` | A `lanes.json` exists, the coordination worktree of a `lanes_with_coord` or `coord` Mission is not materialized (`CoordinationWorktreeUnmaterialized`), and its committed status log cannot be read because the coordination branch is not a local head (for example it exists only on a remote) | Materialize the coordination worktree, then re-run finalize-tasks. {next step} — the canonical `CoordinationWorktreeUnmaterialized` guidance: run `spec-kitty doctor coordination --mission <slug> --fix` (if that command cannot, materialize it manually with `git -C <repo> worktree add <coordination worktree> <coordination branch>`); when the coordination branch exists only on a remote, it first says to run `git fetch origin <coordination branch>`. |
| `status_unreadable` | A `lanes.json` exists, but the preflight cannot resolve the status surface, the status directory is missing for another reason, the local coordination branch carries no committed status log, or the event log cannot be read | Repair the status log (`spec-kitty agent status validate --mission <handle>` reports the problem; `spec-kitty agent status doctor` checks status hygiene), then re-run finalize-tasks. Cause: {the error's message, plus its next step when the message does not already carry it} |

No remedy suggests deleting `lanes.json`, a force flag, `git reset`, `git restore`,
`git checkout -- .`, or removing worktrees or branches.

`status_unreadable` in practice: a malformed line in the status log that finalize's
work-package read already uses (`read_wp_frontmatter`) is refused earlier, by that read,
with its existing store error (`Invalid JSON on line N: ...`). The preflight's own
`status_unreadable` appears when its separate read fails: the coordination status
surface of a coordination Mission cannot be resolved (for example a deleted
coordination branch), the coordination worktree is not materialized and its branch is
not a local head, the committed log is missing or malformed, or the log cannot be
read. Each `status_unreadable` remedy carries its cause: the remote-only case leads
with materializing the worktree (after fetching the branch), every other case appends
` Cause: ` and the underlying message. Its message reads `Cannot re-finalize: the
status log is unreadable, so started work cannot be determined.`: it does not claim
that a lane would change. Code: `_read_started_wp_ids`,
`_started_on_coordination_branch` and `_status_unreadable_error` in
`mission_finalize_lanes.py`.

### Not the planning-pin probe

The planning-pin preservation (section 3, #3311) asks "has execution begun?" through
`_execution_has_begun`: it is true when any work package's *current* lane is not
`planned` (`blocked` and `canceled` included), and it degrades to "not begun" when the
status surface or log cannot be read. The started-work-package predicate asks which
work packages have *ever* entered a working lane, and fails closed. The two answer
different questions and can disagree: a work package reset to `planned` is still
started, while a work package moved from `planned` straight to `blocked` makes
execution "begun" for the pin without being started. Moving the pin probe onto the
history-based predicate is Follow-up: #5702.

Locked by tests in:

- `tests/lanes/test_frozen_lane_membership.py` and
  `tests/lanes/test_frozen_lane_membership_sweep.py`
- `tests/specify_cli/cli/commands/agent/test_finalize_frozen_lane_preflight.py`
- `tests/integration/test_refinalize_keeps_started_lanes.py` and
  `tests/integration/test_refinalize_frozen_lane_refusals.py`

## Module map

`finalize-tasks` is split across sibling modules in
`src/specify_cli/cli/commands/agent/` (#5627). `mission_finalize.py` is the
facade: it keeps the command, and every other phase lives in its own module:

| Module | Owns |
| --- | --- |
| `mission_finalize.py` | The `finalize_tasks` command, its context (`_resolve_finalize_context`), the branch-setup phase (`_run_finalize_branch_setup`), the validation-gate and ownership-gate runners, and the helpers `_meta_json_delta_is_finalize_attributable` and `_collect_finalize_artifacts`; re-exports every name below |
| `mission_finalize_seams.py` | Constants, the owned-envelope `ContextVar`, `_emit_json` and the `mission`-routed patch seams |
| `mission_finalize_branch_contract.py` | Target-branch resolution, branch-contract persistence, the `--target-branch` override |
| `mission_finalize_validation.py` | Requirement-ID, dependency, requirement-mapping and issue-matrix gates |
| `mission_finalize_bootstrap.py` | The per-WP frontmatter bootstrap loop, ownership gates, lane-input projection, the `--validate-only` report, local canonical status events |
| `mission_finalize_planning_pin.py` | The planning-commit pin: preserve-or-capture, `--refresh-planning-commit` and the automatic refresh |
| `mission_finalize_lanes.py` | Lane computation, the frozen-lane preflight (`_preflight_frozen_lane_membership`, section 5) and the acceptance-matrix scaffold |
| `mission_finalize_commit.py` | The commit pipeline, the success report and the refusal-time rollback guards; wraps the status-surface guard with `_capture_status_surface`, `_restore_status_surface`, `_restore_mission_write_scope_beside_status` and `_report_status_surface_leftover` |

`finalize_status_surface.py` is not a phase module. It owns `StatusSurfaceGuard`
and `StatusSurfaceLeftover`, which `mission_finalize_commit.py` wraps.

`mission_finalize` re-exports every name the phase modules define, so
`mission_finalize.<name>` stays importable. How a phase module reaches a name
decides whether a patch on `mission_finalize.<name>` intercepts the call. The
module goes through `mission_finalize` at call time with a lazy in-function
import (`_mf.<name>`), under three rules:

1. A call to a function another finalize module owns always goes through `_mf`.
2. A call to a name that tests patch on `mission_finalize` goes through `_mf`.
3. Any other call inside a phase module is direct. To intercept it, patch the
   phase module that makes the call, not `mission_finalize`.

`tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py`
pins the re-exports, the lazy import, and both routing rules (patched names and
cross-module functions are never referenced bare in a phase module). When a test
starts patching another name on `mission_finalize`, add it to `_ROUTED_NAMES`
there: the gate does not read the tests, so a newly patched name that a phase
module calls directly would not be intercepted and nothing would fail. Structural pins that read the source use `tests/_support/finalize_source.py`,
which reads the whole module family.
