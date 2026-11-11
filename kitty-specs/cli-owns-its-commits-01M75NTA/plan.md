# Implementation Plan: The CLI commits its own writes; dirty gates are Mission-scoped

**Branch**: `fix/7545-cli-owns-its-commits` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/cli-owns-its-commits-01M75NTA/spec.md`

Branch contract: the current branch is `fix/7545-cli-owns-its-commits`, and planning, base
and merge target are the same branch (`branch_matches_target: true`). The topology is
`single_branch`. `consolidate` lands locally on that branch; publishing is a draft pull
request to `main`, never a push to `main`.

## Summary

The command and gate inventory is in [research/code-grounding.md](research/code-grounding.md).
The scratch-repository observations are in [research.md](research.md). The work has five
concerns:

1. **Enabler (tidy-first):** add one structural rule, `coordination/mission_dirt.py`, that
   classifies an uncommitted path as this Mission's, another Mission's, or outside every
   Mission. Collapsed directory entries and Mission directory aliases are included. The
   private `coherence._is_other_mission_path` is rebuilt on it, with its behaviour pinned
   unchanged.
2. **#7556:** `record-analysis` refuses only on this Mission's own paths, after its existing
   bookkeeping filters, and warns about every other path. The single_branch claim warns about,
   and stops refusing on, another Mission's paths only. Both gates classify the paths they
   already listed, so they add no git call (NFR-001).
3. **#5938:** `emit_mission_next_invoked` returns the log path it appended to. When that path
   is in the coordination worktree, `next` commits that one file there. It uses the
   `_commit_status_artifacts_to_coord` shape: `resolve_placement_only(STATUS_STATE)` plus
   `safe_commit`. A refused or failed commit is a warning, never a `next` failure.
4. **#3933:** `setup-plan` emits PlanCompleted before it commits, then commits `plan.md`
   together with this Mission's lifecycle log. That covers SpecifyCompleted, PlanStarted and
   PlanCompleted, which are observed uncommitted today. It reports that commit's hash.
   `mark-status` commits its annotation on every topology when auto-commit is on, not only on
   single_branch: on coordination topologies the annotation is observed left modified in the
   coordination worktree.
5. **#7555:** `init` captures a git baseline before its first write and, after the last write,
   commits through the upgrade committer (`upgrade/autocommit.commit_touched_checkout`), with
   an init-specific message. `--no-commit` opts out. Outside a git repository nothing changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); git CLI through `kernel.git`; no new dependency
**Storage**: Files in git: Mission directories under `kitty-specs/`, `.kittify/`
**Testing**: pytest; red-first CLI-entry tests via `typer.testing.CliRunner` in real temporary git repositories; unit tests for the predicate
**Target Platform**: Linux, macOS, Windows 10+ (path handling uses `kernel.paths.to_posix`)
**Project Type**: single (the `spec-kitty` CLI)
**Performance Goals**: no added git subprocess in any gate (NFR-001); one extra commit per `next` call only when it wrote into a coordination worktree
**Constraints**: C-001..C-006 from spec.md: no operator-edit sweep, no protected-branch bypass, commits only through `safe_commit` and the router, no filename exemptions, no new ratchets, no pack edits
**Scale/Scope**: about 6 source modules and about 8 test files

## Charter Check

| Charter rule | How this plan complies |
|---|---|
| Single canonical authority | One new predicate module; the existing private other-Mission rule is rebuilt on it, not duplicated. The init commit reuses the upgrade committer instead of a second baseline committer. |
| Architectural alignment / layer rules | `mission_dirt.py` sits in `specify_cli.coordination` beside `coherence.py` and imports only `kernel`. `runtime.next` does not gain a module-level `specify_cli` import: the commit happens in `next_cmd.py`. |
| ATDD / red-first (SO #4, C-011) | Each WP lands a failing test through the pre-existing CLI entry point before its fix commit. The enabler WP is tidy-first and behaviour-preserving, with its own unit tests. |
| Architectural gate discipline (SO #5) | No new gate and no allowlist. The predicate is structural, so `test_exemption_registry_ratchet` stays green without a registry row. `UPGRADE_BOOKKEEPING` keeps its single holder (`upgrade/autocommit.py`). |
| Git discipline (SO #7) | Draft PR to `main`; the operator merges; local `consolidate` only. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted test files, owning directories, `make test-fast` and the named architectural gate files only. |
| Terminology canon | Mission, never "feature", in new prose and messages. |

No violations; Complexity Tracking is not needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/cli-owns-its-commits-01M75NTA/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── research/code-grounding.md
├── decisions/            # Decision Moments (specify)
├── checklists/requirements.md
└── tasks.md, tasks/      # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/
├── coordination/
│   ├── mission_dirt.py           # NEW: Mission-scoped dirt classification (IC-01)
│   └── coherence.py              # _is_other_mission_path rebuilt on mission_dirt (IC-01)
├── cli/commands/
│   ├── agent/mission_record_analysis.py   # gate scoped (IC-02)
│   ├── agent/mission_setup_plan.py        # PlanCompleted committed with plan (IC-04)
│   ├── agent/tasks_mark_status.py         # commit on every topology (IC-04)
│   ├── next_cmd.py                        # commit coordination event row (IC-03)
│   └── init.py                            # baseline + commit (IC-05)
├── lanes/implement_support.py             # claim gate scoped (IC-02)
└── upgrade/autocommit.py                  # optional message parameter (IC-05)
src/runtime/next/next_invocation_lifecycle.py   # return the written log path (IC-03)
tests/ ... mirrors of the above
```

**Structure Decision**: single project; changes stay inside the existing modules, plus one
new small module.

## Implementation Concern Map

### IC-01 — Mission-scoped dirt predicate

- **Purpose**: One structural answer to "whose dirt is this path?", which every gate can reuse.
- **Relevant requirements**: FR-001, NFR-001, C-004
- **Affected surfaces**: `src/specify_cli/coordination/mission_dirt.py` (new), `src/specify_cli/coordination/coherence.py`
- **Sequencing/depends-on**: none
- **Risks**: `_is_other_mission_path` feeds the destructive guards. Its result must stay
  byte-identical: the collapsed-directory case stays `False` there, because the destructive
  guard lists with `--untracked-files=all` and never sees a collapsed entry. The new module
  exposes a separate, gate-oriented classification.

### IC-02 — Gates count only this Mission's dirt (#7556)

- **Purpose**: `record-analysis` and the single_branch claim stop refusing on another Mission's files.
- **Relevant requirements**: FR-002, FR-003, FR-008
- **Affected surfaces**: `cli/commands/agent/mission_record_analysis.py`, `lanes/implement_support.py`, tests in `tests/specify_cli/test_analysis_report.py` and `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: re-pinning `test_record_analysis_refuses_dirty_worktree_before_write` (a root
  `dirty.txt` becomes a warning). Its intent is kept by a same-fixture own-Mission edit that
  still refuses.

### IC-03 — `next` commits its coordination event row (#5938)

- **Purpose**: A `next`-driven coordination Mission consolidates without a hand commit.
- **Relevant requirements**: FR-004, C-001, C-003, C-004
- **Affected surfaces**: `src/runtime/next/next_invocation_lifecycle.py`, `src/specify_cli/cli/commands/next_cmd.py`
- **Sequencing/depends-on**: none
- **Risks**: the coordination worktree may hold other uncommitted status files.
  `safe_commit` with an explicit single path stages only that path. Concurrent writers hold
  the status lock; the commit runs after the append, outside the decision-log wrap.

### IC-04 — setup-plan and mark-status commit their writes (#3933)

- **Purpose**: No plan-phase or subtask-annotation write is left dirty with auto-commit on.
- **Relevant requirements**: FR-005, FR-006
- **Affected surfaces**: `cli/commands/agent/mission_setup_plan.py`, `cli/commands/agent/tasks_mark_status.py`
- **Sequencing/depends-on**: none
- **Risks**: the lifecycle log of a coordination Mission is still the PRIMARY copy for
  lifecycle events (#3933 comment). The commit router partitions by kind, so the test covers
  both a single_branch and a coordination Mission.

### IC-05 — init commits what it wrote (#7555)

- **Purpose**: A fresh project starts with a clean tree.
- **Relevant requirements**: FR-007, C-001, C-002
- **Affected surfaces**: `cli/commands/init.py`, `upgrade/autocommit.py`
- **Sequencing/depends-on**: none
- **Risks**: the comment "init is file-creation-only" (T001 of mission `01KQ84P1`) changes
  meaning: init still never runs `git init`, but it now commits inside an existing repository.
  An unborn HEAD (no commits yet) must work. A protected branch is handled by the existing
  upgrade capability (Decision Moment `01M75NY6CET5GK3CZ4QEEBJXGC`, flagged for review).

## Stretch (only if covered without widening)

- #5515 (`safe_commit` swallows git's stderr) and #5744 (`base_commit` vs the lane guard)
  are not on the IC paths above, so they stay `Refs`.
