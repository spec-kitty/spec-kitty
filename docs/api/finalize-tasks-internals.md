---
title: finalize-tasks internals reference
description: 'finalize-tasks internals: empty owned_files, lane-depth cycle safety, the planning_commit_sha refresh override, and the automatic planning-pin refresh.'
doc_status: active
updated: '2026-10-04'
---
# `finalize-tasks` internals reference

Four non-obvious behaviours an operator may encounter when running
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
| `mission_finalize_lanes.py` | Lane computation and the acceptance-matrix scaffold |
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
