# Implementation Plan: Single STATUS_STATE read-dir resolver with phantom-coord degrade

**Branch**: `claude/project-thread-5t7sqy` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/status-state-read-dir-dedup-01M3HNNV/spec.md` (issue #5180)

## Summary

Hoist the post-merge gate's handed-dir partition resolver — the one that carries the
#154 phantom-path `.exists()` degrade — to a single public function on the read-path
owner module, then repoint the two CLI-layer STATUS_STATE copies (render feedback path,
move-task verdict path) onto it. Red-first with the #154 ambient-ancestor fixture, which
today makes the render feedback lookup silently return "no feedback".

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mission_runtime.resolve_artifact_surface` (placement seam), `specify_cli.core.paths.resolve_canonical_root`
**Storage**: filesystem (`status.events.jsonl`)
**Testing**: pytest; targeted files + owning module fast tier (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: no measurable change (≤ 1 extra `exists()` per resolution; NFR-001)
**Constraints**: C-001..C-005 in spec; complexity ≤ 15; no new suppressions
**Scale/Scope**: 3 source modules + 1 owner module, ~40 net lines removed

## Charter Check

- **Single canonical authority** — this mission *is* the unification: three copies → one. PASS.
- **Architectural alignment** — resolver lands in `specify_cli.missions._read_path_resolver`, the existing read-path owner; no new cross-layer edge (`mission_runtime` import stays lazy, as in the canonical copy). PASS.
- **ATDD / red-first** — issue-pinned `@pytest.mark.regression` repro lands RED before the fix, then is converted to focused unit tests. PASS.
- **Campsite** — the touched functions' docstrings shrink to point at the one authority; no other debt in the file set is domain-matched.
- **No full heavy suites** — only named architectural gate files are run. PASS.

## Research (Phase 0)

See [research.md](research.md). All questions resolved; no NEEDS CLARIFICATION.

## Design (Phase 1)

No data model, API contract or quickstart: this is an internal resolver dedup with no
new entity, schema or operator-facing surface.

### The one resolver

```
resolve_partition_read_dir(feature_dir: Path, kind: MissionArtifactKind) -> Path
  1. repo_root = resolve_canonical_root(feature_dir)   # WorkspaceRootNotFound -> feature_dir
  2. resolved  = resolve_artifact_surface(repo_root, feature_dir.name, kind).path
                                                       # CoordinationBranchDeleted propagates (C-002)
  3. if not resolved.exists() and feature_dir.exists(): return feature_dir   # #154 / #5180 degrade
  4. return resolved
```

### Call-site map

| Site | Today | After |
|------|-------|-------|
| `post_merge/review_artifact_consistency.py::_resolve_partition_read_dir` | canonical body | deleted; `_resolve_lane_state_read_dir` delegates |
| `cli/commands/agent/workflow_cores.py::_resolve_status_state_read_dir` | copy w/o degrade | deleted; `latest_review_feedback_reference` + `has_prior_rejection` call the resolver |
| `cli/commands/agent/tasks_verdict_persistence.py::_resolve_verdict_read_feature_dir` | copy w/o degrade | one-line adapter (`wp_path.parent.parent`) onto the resolver |

The render split (C-001) is untouched: `review_feedback_root` / `resolve_review_feedback_pointer`
/ `_resolve_review_cycle_sub_artifact_dir` keep their PRIMARY resolution.

### Structural guard (FR-004)

A focused AST test asserts that none of the three owning modules calls
`resolve_artifact_surface` or `placement_seam(...).read_dir(...)` with
`MissionArtifactKind.STATUS_STATE`, and that the three entry points reach
`resolve_partition_read_dir`. A poison arm proves the scan reds on a re-introduced copy.

## Project Structure

```
kitty-specs/status-state-read-dir-dedup-01M3HNNV/
├── spec.md, plan.md, research.md, tasks.md, tasks/
├── checklists/requirements.md
└── traces/ (approach, design-decisions, tooling-friction)

src/specify_cli/missions/_read_path_resolver.py          # + resolve_partition_read_dir
src/specify_cli/post_merge/review_artifact_consistency.py # - private copy
src/specify_cli/cli/commands/agent/workflow_cores.py      # - private copy
src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py  # adapter

tests/missions/ (or nearest mirror) test_partition_read_dir.py   # unit + phantom
tests/agent/test_status_state_phantom_degrade.py                 # red-first repro → converted
```

**Structure Decision**: single project; tests mirror the owning module.

## Complexity Tracking

None.

## Implementation Concern Map

- **IC-01 Resolver authority** — public resolver + unit tests (flat self-home, phantom degrade, both-missing, materialised coord, deleted-coord propagates).
- **IC-02 Repoint consumers** — render + verdict + gate delegate; red-first repro goes green; structural guard.
