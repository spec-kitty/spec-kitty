---
work_package_id: WP02
title: Reader content-source + shared two-partition split helper (IC-01b + IC-shared)
dependencies:
- WP01
requirement_refs:
- FR-005
- NFR-001
planning_base_branch: claude/spec-kitty-ci-failures-r0xui3
merge_target_branch: claude/spec-kitty-ci-failures-r0xui3
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-ci-failures-r0xui3. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-ci-failures-r0xui3 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-matrix-partition-integrity-01M3H10A
base_commit: 991a46898e5b50c080ad2865490cadb284941e78
created_at: '2026-09-27T10:17:07.376663+00:00'
subtasks:
- T005
- T006
- T007
- T008
history:
- Created by /spec-kitty.tasks 2026-09-27
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/tasks/issue_matrix_migration.py
create_intent:
- src/mission_runtime/issue_matrix_partition.py
- tests/specify_cli/tasks/test_issue_matrix_content_source.py
execution_mode: code_change
owned_files:
- src/mission_runtime/issue_matrix_partition.py
- src/specify_cli/tasks/issue_matrix_migration.py
- src/specify_cli/cli/commands/review/_issue_matrix.py
- src/specify_cli/status/doctor.py
- tests/specify_cli/tasks/test_issue_matrix_content_source.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Two things: (1) extend the dir-based issue-matrix readers to accept a coordination-ref **content
source** (from WP01) so they can read post-consolidation content that has no on-disk directory; and
(2) factor the `(primary_discovery_dir, coord_matrix_source)` two-partition split into ONE shared helper
that review (WP03) and merge (WP04) both call, so the split is not re-authored three times.

Depends on WP01's ref-content read authority. Read `../plan.md` (IC-01b, IC-shared), `../data-model.md`
(read-source resolution), `../contracts/issue-matrix-read.md`.

## Context (confirmed live code)

- Reference pattern: `src/specify_cli/status/doctor.py::check_issue_matrix` (:384-456) — discovery from
  PRIMARY `feature_dir` (comment: "discovery ALWAYS reads feature_dir"), verdicts from the coord dir via
  `coord_read_dir_for`.
- Readers today are dir-based: `load_issue_matrix(feature_dir)` (`tasks/issue_matrix_migration.py:177`,
  does `feature_dir / issue-matrix.json` then `.md`), `issue_matrix_artifact_present(feature_dir)` (:209),
  `validate_issue_matrix(path)` (`review/_issue_matrix.py:210`, reads a `.md` path).
- An UNMATERIALIZED coord surface has no on-disk dir — content comes from WP01's ref read.

## Subtasks

### T005 — Failing-first test (RED before T006-T008)
Create `tests/specify_cli/tasks/test_issue_matrix_content_source.py`: on a post-consolidation coord
fixture (worktree gone, coord branch retained, `#11 -> fixed` on the branch), assert
`load_issue_matrix` / `issue_matrix_artifact_present` / `validate_issue_matrix` / `check_issue_matrix`
resolve the verdict via the content source (return `fixed` / present / valid), and that a flat-topology
fixture is unchanged. RED on base.

### T006 — Shared two-partition split helper (IC-shared)
Create `src/mission_runtime/issue_matrix_partition.py` (new module in the seam layer — NOT specify_cli):
a helper that, given `repo_root`/`mission_slug`, returns the primary discovery dir AND the coord matrix
source. It DISPATCHES the matrix source: try the materialized coord dir (`coord_read_dir_for`); when that
returns `None` (unmaterialized/post-consolidation), call **WP01's standalone ref-content read** directly to
get the content (do NOT let the `None` fall back to `feature_dir` — that is the residue bug). So the
matrix source is a dir when materialized and ref-content otherwise. Thin composition of the seam; not a
second authority. (Layer note: fine to live in mission_runtime; specify_cli consumers import it.)

### T007 — Extend the migration readers
Give `load_issue_matrix` / `issue_matrix_artifact_present` a content-source path (in addition to the dir
path) so callers can pass WP01's ref content. Keep the dir fast-path unchanged.

### T008 — Extend validate_issue_matrix + check_issue_matrix
Extend `validate_issue_matrix` (`review/_issue_matrix.py`) to validate from a content source, and adopt
the shared helper + content source in `check_issue_matrix` (`doctor.py`) so the reference consumer also
reads post-consolidation content. Keep flat-topology behavior byte-for-byte.

## Definition of Done
- T005 RED on base, GREEN on final; flat-topology unchanged.
- The shared helper is the single split site; review/merge WPs will consume it (do not inline the split).
- `ruff`/`ruff format`/mypy clean.
- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/tasks tests/status -q`.

## Reviewer guidance
Confirm the helper lives in mission_runtime and is a thin composition (no second resolution authority,
C-001). Confirm readers still take the dir fast-path unchanged and only gain an additional content source.
