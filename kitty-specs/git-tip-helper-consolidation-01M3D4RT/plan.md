# Implementation Plan: Consolidate target-branch tip-capture helper + reclaim tasks-lifecycle squad MINORs

**Branch**: `fix/git-tip-helper-consolidation` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/git-tip-helper-consolidation-01M3D4RT/spec.md`

## Summary

Give the target-branch tip that `classify_recorded_pin` classifies against **one canonical capture authority** that resolves `refs/heads/{branch}`, replacing the two helpers (`lanes/merge._rev_parse` and `mission_finalize._capture_target_branch_tip`). **Premise correction (adversarial squad, empirically verified on git 2.43.0):** the two helpers are behaviourally identical — bare `rev-parse` and `--verify` both resolve a branch+tag name collision to the *tag* and exit 0; the env difference is inert. The REAL defect both share is bare-name resolution: a tag colliding with the target-branch name misresolves the pin to the tag. The fix resolves `refs/heads/{branch}` (as `merge/preflight.py` and `_coordination_doctor.py` already do), proven RED-first by a branch/tag-collision test. Fold two adjacent, low-risk squad tidies sharing the same blast radius: `--full-history` accuracy on the move-task behind-count (#4593 item 1), and a dead-guard removal + a load-bearing test-assertion fix in the finalize dependency path (#4152 items 2 & 3).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib `subprocess`, git; internal `core/vcs/git.py`, `lanes/`, `cli/commands/agent/`
**Storage**: N/A (git refs)
**Testing**: pytest (`.venv/bin/python -m pytest <file> -q`, file-scoped, foreground)
**Target Platform**: Linux/macOS/Windows dev + CI
**Project Type**: single (CLI/tooling)
**Performance Goals**: N/A (one extra `rev-parse` per capture at most; unchanged)
**Constraints**: no behaviour change for valid refs; preserve the FR-008b merge-env ratchet; complexity ≤ 15; diff-cover ≥ 90%
**Scale/Scope**: 6 tip-capture call sites across 6 modules + 1 shared git primitive + 2 finalize tidies

## Design

### D1 — Canonical helper `capture_branch_tip` in `core/vcs/git.py`

Introduce one helper (canonical git-wrapper home, beside `git_rev_list_count`):

```
capture_branch_tip(repo: Path, branch: str, *, env: dict[str,str] | None = None) -> str | None
```

- Form: `git rev-parse --verify refs/heads/{branch}` — the correctness fix. Verified on
  git 2.43.0: bare `dup`→tag SHA, `refs/heads/dup`→branch SHA. Resolving `refs/heads/`
  deterministically returns the **branch** tip, never a same-named tag; `--verify` keeps
  the single-object guarantee and clean non-zero-on-missing. Matches the pattern
  `merge/preflight.py:240` and `_coordination_doctor.py:587,636` already use.
- Contract (documented in the docstring — FR-002): returns the branch tip SHA on success;
  returns `None` (never raises) on a missing branch or any git failure. One stated
  authority for "what is the target-branch tip".
- `env`: optional pass-through so a merge-pipeline caller can hand it `_make_merge_env()`.
  The PATH-prepend is inert for `rev-parse` (no merge driver invoked), so this is
  behaviour-neutral; it only keeps the merge pipeline's single-env discipline intact.
- Callers pass a plain local branch name (verified — never a SHA/qualified/remote ref).

### D2 — Reroute the six classifier-tip capture sites

| # | Site | Current | After |
|---|------|---------|-------|
| 1 | `lanes/worktree_allocator.py:548` | `_rev_parse(repo_root, target_branch)` | `capture_branch_tip(repo_root, target_branch)` |
| 2 | `lanes/implement_support.py:382` | `_rev_parse_or_none(...)` | `capture_branch_tip(...)` |
| 3 | `lanes/implement_support.py:506` | `_rev_parse_or_none(...)` | `capture_branch_tip(...)` |
| 4 | `cli/commands/agent/tasks_move_task.py:724` | `_rev_parse_or_none(...)` | `capture_branch_tip(...)` |
| 5 | `cli/commands/agent/mission_finalize.py:2295,2338` | `_capture_target_branch_tip(...)` | `capture_branch_tip(...)` |
| 6 | `cli/commands/agent/tasks_finalize.py:380` and `migration/mission_state.py:1620` | `_capture_target_branch_tip(...)` | `capture_branch_tip(...)` |

Then **delete** `_capture_target_branch_tip` from `mission_finalize.py` (its docstring
contract migrates to the canonical helper), and drop the now-unused cross-module
imports of it in `tasks_finalize.py` and `migration/mission_state.py`.

`mission_finalize` imports the helper module-level and **unqualified**
(`from ...core.vcs.git import capture_branch_tip`; call `capture_branch_tip(...)`), so the
existing monkeypatch seam in `test_mission_finalize_phases.py` (repointed to
`capture_branch_tip`) still intercepts the production call. Drop the now-unused tip imports
(`worktree_allocator.py:33`, `implement_support.py:22` alias, `tasks_move_task.py:692`
local) — ruff F401 — but KEEP the local `implement_support._rev_parse` (:277, used at :224).
Refresh the two stale prose refs to `_capture_target_branch_tip` in
`planning_commit_classify.py:28,119` (campsite; owned).

### D3 — Scope boundaries (what we do NOT touch)

- `lanes/merge._rev_parse` **stays** — it still serves non-classifier uses:
  `implement_support.py:224` (base-branch commit, not a tip), `merge.py:398`
  (internal bookkeeping), and the `_coordination_doctor.py` coord/target SHA
  comparisons. Rerouting those is out of scope (locality / smallest-viable-diff);
  they are not the tip `classify_recorded_pin` classifies against.
- `implement_support._rev_parse` (the distinct **third** helper, `"unknown"`
  sentinel, base-branch not tip) is **excluded** — C-001.
- FR-008b ratchet (`tests/architectural/test_merge_pipeline_ratchets.py`): the new
  helper lives in `core/vcs/git.py`, so its `subprocess.run` is outside the AST
  scan of `lanes/merge.py`; `_rev_parse` remains in `merge.py` routing through
  `_make_merge_env`. Ratchet stays green — C-002.

### D4 — #4593 item 1: `--full-history` on the behind-count

Add an optional `full_history: bool = False` param to `git_rev_list_count`
(`core/vcs/git.py:1137`); when set, insert `--full-history` after `--count` (compatible
with `--count -- <pathspecs>`). The single caller `tasks_dependency_graph.py:260` passes
`full_history=True` so history-simplification no longer prunes TREESAME merges of source
commits. Note (verified): `--full-history` WITHOUT `--simplify-merges` also counts the
source-relevant **merge commits themselves**, so the count is a conservative upper bound,
not an exact source-commit count — acceptable because it is message-only and fail-open
(C-003); ledger-only merges stay excluded (TREESAME to all parents under the exclude
pathspec). The regression must assert inclusion / the constructed count-with-merges, not
a naive exact equality. The fail-open fallback (raw behind count) is preserved.

### D5 — #4152 item 2 & 3 (behaviour-preserving tidies)

- item 2: in `mission_finalize._resolve_dependencies_and_refs` (~L1067-1069) replace
  `frontmatter_deps = list(wp_meta.dependencies) if _raw_frontmatter_has_field(raw_content, "dependencies") else []`
  with `frontmatter_deps = list(wp_meta.dependencies)` and drop the now-unused
  `raw_content = wp_file.read_text(...)` read. `WPMetadata.dependencies` is
  `Field(default_factory=list)`, so an absent field already yields `[]`; the guarded
  expression equals the bare one for all three cases {absent, present-empty,
  present-non-empty} (C-004). **KEEP** the `_raw_frontmatter_has_field` import — it is
  still used at `mission_finalize.py:1515-1516` (verified); only the :1069 use + the
  `raw_content` read are removed.
- item 3: in `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py:764`
  — `typer.Exit` exposes `.exit_code`, NOT `.code` (verified), so the current
  `getattr(exc, "code", 1) or 1` is ALWAYS `1` (blind), and `getattr(exc,"code",None)`
  would red the correct `Exit(1)` path. Correct fix:
  `exit_code = exc.exit_code if isinstance(exc, typer.Exit) else exc.code` so `Exit(1)`→1
  (pass) and `Exit(0)`→0 (assert fails — load-bearing).
- item 1 is **declined** (see spec issue-matrix): it needs the guard item 2 removes
  and would warn on the intended #4135 path.

## Constitution Check

- **Single canonical authority (DIRECTIVE_044)**: PASS — this mission *creates* one
  where two existed; no new parallel authority introduced.
- **Architectural alignment (DIRECTIVE_001)**: PASS — helper lands in the canonical
  git-wrapper module; layer direction (`specify_cli`/`lanes` → `core`) preserved.
- **Tiered rigour**: WP treated at CORE tier (error-handling contract blast radius).
- **ATDD / red-first (DIRECTIVE_034/041)**: the #4857 regression is RED on the
  branch/tag-collision case against a bare-name resolution (returns the tag, not the
  branch tip); #4593 regression is RED on the history-simplified undercount pre-fix;
  #4152 item3 test is RED on a forced `Exit(0)` once made load-bearing.
- **Locality / smallest-viable-diff (DIRECTIVE_024 / change-apply-smallest-viable-diff)**:
  reroute only the classifier-tip sites; leave general `_rev_parse` uses.
- **Complexity ceiling ≤ 15; new-code coverage**: enforced per NFR-002/003.

No violations → Complexity Tracking table empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/git-tip-helper-consolidation-01M3D4RT/
├── spec.md              # committed
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── checklists/requirements.md
└── tracer-*.md          # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/
├── core/vcs/git.py                       # NEW capture_branch_tip (refs/heads/); #4593 full_history param
├── lanes/
│   ├── planning_commit_classify.py       # docstring refresh (deleted-symbol refs)
│   ├── worktree_allocator.py             # reroute site 1
│   └── implement_support.py              # reroute sites 2,3
├── cli/commands/agent/
│   ├── mission_finalize.py               # reroute site 5 + delete _capture_target_branch_tip + #4152 item2
│   ├── tasks_finalize.py                 # reroute site 6a
│   ├── tasks_move_task.py                # reroute site 4
│   └── tasks_dependency_graph.py         # #4593 item1 caller
└── migration/mission_state.py            # reroute site 6b

tests/
├── core/ (or tests/**/*git*)             # capture_branch_tip unit + agreement test; full_history test
├── lanes/                                # allocator/implement_support tip regressions
└── specify_cli/cli/commands/agent/       # finalize/move-task regressions; test_feature_finalize_bootstrap.py (#4152 item3)
```

**Structure Decision**: single-project CLI layout; the canonical helper belongs in
`src/specify_cli/core/vcs/git.py` (the git-wrapper SSOT, beside `git_rev_list_count`).

## Parallel Work Analysis

### Dependency Graph

```
WP01 (all code) — single cohesive WP; no cross-WP dependencies.
```

### Work Distribution

- **Sequential work**: none beyond WP01's own internal ordering (add helper →
  reroute callers → delete old helper → fold #4593/#4152).
- **Parallel streams**: none — the file blast radius (`core/vcs/git.py` shared by
  #4857+#4593; `mission_finalize.py` shared by #4857+#4152 item2) means any split
  would violate the non-overlapping-owned_files finalize gate. One WP is the honest
  decomposition after the governance pruning (#4611 dropped, #4152 item1 declined).
- **Agent assignments**: WP01 → implementer (sonnet), CORE rigour; review → opus.

### Coordination Points

- **Integration test**: the agreement test (FR-003) is the cross-call-path
  coordination proof — both former paths resolve identically post-consolidation.
- No lane coordination needed (single WP).
