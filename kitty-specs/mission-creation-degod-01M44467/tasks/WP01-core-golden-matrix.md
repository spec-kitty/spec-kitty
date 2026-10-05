---
work_package_id: WP01
title: Core golden behaviour matrix
dependencies: []
requirement_refs:
- FR-001
- FR-011
- NFR-001
- NFR-002
- SC-001
- C-008
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Behaviour freeze
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/core/
create_intent:
- tests/core/golden/mission_create_flat.json
- tests/core/golden/mission_create_coord.json
- tests/core/golden/mission_create_protected.json
- tests/core/golden/mission_create_refusals.json
- tests/core/_mission_create_golden.py
- tests/core/test_mission_creation_golden_flat.py
- tests/core/test_mission_creation_golden_coord.py
- tests/core/test_mission_creation_golden_protected.py
- tests/core/test_mission_creation_golden_refusals.py
execution_mode: code_change
model: ''
owned_files:
- tests/core/golden/**
- tests/core/_mission_create_golden.py
- tests/core/test_mission_creation_golden_flat.py
- tests/core/test_mission_creation_golden_coord.py
- tests/core/test_mission_creation_golden_protected.py
- tests/core/test_mission_creation_golden_refusals.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Core golden behaviour matrix

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`, i.e. `spec-kitty agent profile show python-pedro`) to load the agent profile named in the frontmatter, and follow its guidance before you read the rest of this prompt. Then load governance: `spec-kitty charter context --action implement --json`.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this WP came back from review, the feedback reference is in the event log (`spec-kitty agent tasks status --mission mission-creation-degod-01M44467`) and in the Activity Log below. Address every item before handing back.

---

## Objectives & Success Criteria

Freeze today's observable behaviour of `specify_cli.core.mission_creation.create_mission_core` in a **zero-patch** golden matrix, captured on the **unchanged** code, so that every later WP of this mission can prove it is byte-identical (spec FR-001, NFR-001, SC-001).

Done means:

- At least **40 success cells** and the **13 named refusal cells** from SC-001, plus one malformed-protection-config cell, all pass on the unchanged base.
- The snapshots `tests/core/golden/mission_create_<family>.json` (one per golden module: `flat`, `coord`, `protected`, `refusals`) record the base commit it was captured on (`git rev-parse HEAD` of the lane base). Running the capture again on that base reproduces it byte for byte.
- **No `monkeypatch`, `mock.patch` or `patch.object` appears anywhere** in the golden files.
- The normaliser rewrites **only** mission_id (26-char ULID), mid8 (wherever it occurs: slug, dir name, branch names, meta values), ISO-8601 timestamps and absolute temp-dir paths. Everything else is compared verbatim.
- One planted break per captured dimension was observed to turn the matrix red (T005), and is recorded in the Activity Log.
- All golden files together run in ≤ 45 s wall under `-n 4 --dist loadfile` (NFR-002; WP02 adds its CLI cells to this budget).

**This WP freezes the harness.** After WP01 is approved, no later WP may edit the golden test modules, the normaliser or the snapshot (NFR-001). Design them so they never need to change.

## Context & Constraints

- Spec: `kitty-specs/mission-creation-degod-01M44467/spec.md` (FR-001, FR-011, SC-001, "Behaviour families", the edge cases).
- Plan: `plan.md` IC-01. Research: `research.md` R-3, R-4.
- Grounding: `research/test-remediation.md` §6 (golden design), §3 (the faked-`main` trap: **do not** reuse `tests/specify_cli/core/test_feature_creation.py::_init_git_repo`, because it leaves HEAD on `master` while tests patch `get_current_branch` to return `main`).
- Fixtures to reuse:
  - `tests/_support/git_template.clone_template(dest)`: a fast hardlinked repo on branch `main`, with an `origin`.
  - `tests._factories.provision_test_charter(repo)`.
  - `tests._factories.coord_mission._init_repo_with_target(tmp_path, target_branch=..., protected_primary=...)` and `_write_protected_branches(repo, branches)`. These are the canonical fixture builders: call them, do not copy them.
  - `tests/git/protected_target_fixtures.py::build_protected_target_repo`.
  - `specify_cli.core.owned_mission.resolve_owned_create_root`, for a real owned checkout from `git worktree add`.
- Call `create_mission_core(repo_root=repo, ..., allow_worktree_context=True)`. The test process may run inside a lane worktree, and the allow flag is the documented programmatic escape (see the docstring at `src/specify_cli/core/mission_creation.py` ~2101). Do not patch `is_worktree_context`.
- Each cell uses a unique slug, so the #4033 duplicate guard and mid8 collisions never interfere. You do not need `allow_duplicate` except in the duplicate cells.
- **Baseline-red: #5706.** The MissionCreated fan-out registry leaks state between files on one xdist worker. Do not capture fan-out call counts in the golden matrix; capture only repository state and the returned result.
- Lanes topology: you work in the lane worktree printed by `spec-kitty agent action implement`. Commit there. Never push.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-5634-mission-creation-degod`
- **Merge target branch**: `issue-5634-mission-creation-degod`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T001 – Golden harness: fixture, capture, normaliser, snapshot I/O

- **Purpose**: one small private module, `tests/core/_mission_create_golden.py`, that every golden file uses. Keeping capture and normalisation in one place makes the freeze enforceable.
- **Steps**:
  1. `build_repo(tmp_path, *, target: str, protected: bool, origin_head: bool = True) -> Path`. It wraps `_init_repo_with_target`. When `target != "main"` the factory checks out the topic branch.
  2. `capture(repo: Path, result_or_exc, *, write_checkout: Path | None = None) -> dict`. Record:
     - `meta`: the parsed `meta.json` of the created mission, if any, with keys sorted. Note that the ordering of keys *as written* is also observable, so capture `list(meta.keys())` in file order as a separate `meta_key_order` field.
     - `branches`: sorted `git for-each-ref --format=%(refname:short) refs/heads`.
     - `worktrees`: `git worktree list --porcelain` paths, made relative to the repo's parent.
     - `head`: `git rev-parse --abbrev-ref HEAD` in the repository root checkout and, if different, in the write checkout.
     - `new_commits`: for each branch whose tip moved during the cell, the list of `(subject, sorted changed paths)` for the new commits. Snapshot the tips before the call to compute this.
     - `status_log`: for every `status.events.jsonl` created under `kitty-specs/**`, including in a coordination worktree, record its location as a repo-relative path plus the checkout that holds it, and the sequence of `event_type` (or the equivalent key; inspect a real file first).
     - `porcelain`: `git status --porcelain=v1 --untracked-files=all` in the repository root checkout (and the write checkout), sorted.
     - `tree`: the sorted file list under the created mission directory, if it exists.
     - For refusals: `exc_type` (`type(exc).__qualname__` only; never the module path, because WP06 moves the error classes), `message` (normalised `str(exc)`) and `error_code` (`getattr(exc, "error_code", None)`).
     - For successes: the `MissionCreationResult` fields that are plain data (use `dataclasses.asdict` where possible; drop non-serialisable objects such as event objects, and keep their `event_type`).
  3. `normalise(obj, *, mission_id, tmp_root) -> obj`: whitelisted substitutions only:
     - each 26-char ULID becomes `<ULID>`;
     - mid8 (the first 8 chars of that mission_id, found anywhere in strings) becomes `<MID8>`;
     - ISO-8601 timestamps matching `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})` become `<TS>`;
     - `str(tmp_root)` becomes `<TMP>`.

     No other rewriting, and no key dropping beyond the non-serialisable result fields named above. Put the regexes in module constants with a comment saying "frozen after WP01 (NFR-001)".
  4. Snapshot I/O: `assert_golden(family: str, cell_id: str, observed: dict)`.
     - It loads `tests/core/golden/mission_create_<family>.json`, a dict `{"base_commit": ..., "cells": {cell_id: {...}}}`. There is one file per golden module, so `--dist loadfile` never has two workers writing the same file.
     - With `SPEC_KITTY_REGEN_GOLDEN=1` it writes the observed cell instead and records `base_commit`. Regeneration refuses to run under xdist (`PYTEST_XDIST_WORKER` set) to avoid read-modify-write races within one module.
     - Otherwise it compares exactly (`assert observed == expected`, with a readable diff).
     - Use `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False) + "\n"` so the file is stable.
- **Files**: `tests/core/_mission_create_golden.py`, `tests/core/golden/`.
- **Notes**: mark the golden test modules with the markers the neighbouring `tests/core/test_mission_creation_decomposition.py` uses (check its `pytestmark`), so the fast/slow tier selection stays consistent.

### Subtask T002 – Success cells: branch-flat and coordination-routed families

- **Purpose**: cover behaviour families 1 and 3 from the spec.
- **Steps**: parametrise over topology ∈ {`SINGLE_BRANCH`, `LANES`} (flat) and {`COORD`, `LANES_WITH_COORD`} (coordination-routed), on an **unprotected** topic branch `topic`, with flags:
  - none
  - `pr_bound=True`
  - `retain_branches=True, retain_worktrees=True`
  - `mission="documentation"` (if that mission type is activated by `provision_test_charter`; otherwise skip and note it)
  - a non-default `friendly_name`, `purpose_tldr` and `purpose_context`

  For coordination-routed cells, the capture must show the coordination branch, the coordination worktree path, and the status log living in the coordination worktree and not in the target checkout. That is the #5440 invariant.
- **Files**: `tests/core/test_mission_creation_golden_flat.py`, `tests/core/test_mission_creation_golden_coord.py`.
- **Parallel?**: yes, with T003.

### Subtask T003 – Success cells: protected single_branch, owned checkout, flag cross-products

- **Purpose**: cover behaviour families 2 and 4.
- **Steps**:
  - Protected target: `build_repo(target="main", protected=True)`.
    - `SINGLE_BRANCH` with no flag: a mission branch is minted and checked out. Capture the HEAD switch, the minted branch name and that the scaffold commit lands on the minted branch (FR-011).
    - `SINGLE_BRANCH, commit_to_target=True`: no mint; `commit_to_target: true` is in meta.
    - `LANES` and `COORD` on protected `main` (whatever happens today, including any skipped commit, is captured).
  - Unprotected `main` with no protection configured but primary: capture the protected-target decision, which uses `bias=False` primary resolution.
  - Owned checkout: create a sibling `git worktree add ../owned -b owned-topic`, resolve it with `resolve_owned_create_root`, and create `SINGLE_BRANCH` and `LANES_WITH_COORD` through it (FR-022 twin; see the comment block at `mission_creation.py` ~2189).
  - Cross-products: retention × {`SINGLE_BRANCH` protected, `COORD`}; `pr_bound` × {`SINGLE_BRANCH` protected}.
  - Aim for ≥ 40 success cells across T002 and T003 in total. List the cell ids in the module docstring.
- **Files**: `tests/core/test_mission_creation_golden_protected.py`.

### Subtask T004 – Refusal cells with post-state capture

- **Purpose**: pin refusal kind, message, error code and **residue** (spec US2 scenario 2, SC-001).
- **Steps**: one cell each, capturing the repo state before the call and after it (`pre` and `post` in the cell; the diff is part of the snapshot):
  1. live duplicate: create, **commit the first mission's `spec.md`**, then create the same slug and type again; the second raises `MissionAlreadyExistsError`. A genesis-only prior counts as abandoned and does NOT refuse.
  2. mission branch exists (pre-create `kitty/mission-<slug>-<mid8>`). Mid8 is unknown before the call, so instead freeze identity *only by choosing the slug*, and pre-create the branch via a first create plus deleting its directory. If no zero-patch route exists, document why and use the closest real reproduction.
  3. dirty checkout under the protected mint (an untracked `stray.txt` in the repository root checkout)
  4. protected target without a commit: the unborn `target_branch` must itself be **protected** (`protection.protected_branches: [main, release]`, target `release`); an unprotected unborn target just creates the mission
  5. invalid slug (`"Not_Kebab"`)
  6. empty friendly name (`friendly_name="   "`)
  7. `commit_to_target=True` with `topology=LANES`
  8. unborn HEAD (`git init -b main` with no commit, then the charter, with no commit)
  9. detached HEAD (`git checkout --detach`)
  10. worktree context **without** the allow flag. Run the create with `cwd` inside a real `git worktree add` checkout (use `monkeypatch.chdir`, which is a working-directory change, not a patch of the module; it is allowed), with `allow_worktree_context=False`.
  11. owned-root mismatch (an owned root whose repository differs, or whatever `resolve_owned_create_root` refuses; pick the refusal reachable without patches)
  12. protected recreate (`_refuse_protected_recreate`: re-run a protected `SINGLE_BRANCH` create into an existing scaffold with meta)
  13. **refused-mint orphan + retry** (baseline-red, follow-up: #5704): cell 3's repo, then remove `stray.txt`, then retry the same create. Capture the orphan directory (no `meta.json`) and the retry's `MISSION_ALREADY_EXISTS`.

  Then the extra cell: **malformed protection config** (write an invalid `protection:` block into `.kittify/config.yaml`). Capture where it raises and what residue is left behind. This is the cell WP07 relies on to prove error timing (C-001).
- **Files**: `tests/core/test_mission_creation_golden_refusals.py`.
- **Notes**: some refusals raise before any write, so their `post == pre`. That equality is the pinned rollback behaviour, so keep it in the snapshot and do not assert it separately in code.

### Subtask T005 – Capture on base, reproducibility, planted breaks

- **Steps**:
  1. Run with `SPEC_KITTY_REGEN_GOLDEN=1` serially (`-n0`), then run again without it and check the matrix is green.
  2. Regenerate a second time and check `git diff --exit-code tests/core/golden/`. The capture must be deterministic. If it is not, fix the capture; widening the normaliser is not allowed.
  3. Plant one break per dimension in `src/specify_cli/core/mission_creation.py`, temporarily and never committed:
     - change one refusal message character;
     - drop `retain_branches` from meta;
     - rename the minted branch prefix;
     - write the status log to the target dir instead of the coordination dir;
     - skip one scaffold commit;
     - stop restoring HEAD after a failed create.

     Confirm each turns at least one cell red, then `git checkout -- src/`. Record each break plus the failing cell ids in the Activity Log (reviewers re-run two of them).
  4. Time the run: `PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py -n 4 --dist loadfile -q --durations=10`. Record the wall time.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py -n 4 --dist loadfile -q
SPEC_KITTY_REGEN_GOLDEN=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py -n0 -q && git diff --exit-code tests/core/golden/
.venv/bin/python -m pytest tests/core/test_mission_creation_decomposition.py -q   # neighbour suite still green
uv run --frozen ruff check tests/core/_mission_create_golden.py tests/core/test_mission_creation_golden_*.py
uv run --frozen ruff format --check --force-exclude tests/core/_mission_create_golden.py tests/core/test_mission_creation_golden_*.py
.venv/bin/mypy tests/core/_mission_create_golden.py
make test-fast
```

## Risks & Mitigations

- **Non-determinism** (commit timestamps, hashes, ordering): capture subjects and paths, never SHAs; sort lists. Fix the capture, never the normaliser scope.
- **Fixture slowness**: `clone_template` is hardlinked; share nothing across cells (isolation beats speed), but keep the cell count focused.
- **Some refusal cells may be unreachable without patches.** Record the reason in the module docstring and the Activity Log, and choose the closest real reproduction. Do not add a patch.
- **Baseline-red #5706**: do not capture fan-out.

## Review Guidance

- `rg -n "monkeypatch\.setattr|mock\.patch|patch\.object|patch\(" tests/core/test_mission_creation_golden_*.py tests/core/_mission_create_golden.py` must return nothing (`monkeypatch.chdir` is allowed only in refusal cell 10).
- Check the normaliser whitelist line by line.
- Re-run two planted breaks from the Activity Log yourself.
- Confirm `base_commit` equals the lane base, and regenerate to check reproducibility.
- Count the cells: ≥ 40 success cells, the 13 named refusal cells, and the malformed-config cell.

## Post-tasks squad folds (binding; they supersede conflicting text above)

1. **Frozen builder, no shared factory.** The harness must **not** import `tests/_factories/coord_mission.py`, which WP08 edits. Vendor a minimal builder in `_mission_create_golden.py` using only `tests/_support/git_template.clone_template` and `tests._factories.provision_test_charter`, plus a local copy of the protected-branches YAML writer. The NFR-001 freeze set is: the golden modules, the snapshots, `_mission_create_golden.py`, `tests/_support/git_template/**` and `tests/_factories/__init__.py`. Later WPs check `git diff <WP01-commit> -- <freeze set>` is empty.
2. **Multi-mission normalisation.** Collect every mid8 in the post-state by matching `<known-slug>-([0-9A-Z]{8})$` across dir names, branch names and meta. Number them in order of first appearance as `<MID8#1>`, `<MID8#2>` …, and number ULIDs the same way (`<ULID#n>`). Still whitelist-only.
3. **mid8-dependent cells (#2 mission branch exists, #12 protected recreate): predict-then-plant.** mid8 is the ULID's millisecond timestamp in 1,024 ms buckets. The helper:
   - waits until `time_ms % 1024 < 100`;
   - predicts `str(ULID())[:8]`;
   - pre-creates `kitty/mission-<slug>-<mid8>` (#2) or `kitty-specs/<slug>-<mid8>/meta.json` via a first create with `allow_duplicate=True` (#12);
   - asserts after the call that the predicted mid8 was the one used, so a missed bucket fails loudly instead of snapshotting a wrong state.
4. **Malformed protection config is two cells**: (a) invalid YAML → `CharterPackConfigError` at governance resolution; (b) well-formed YAML with a wrong-shape `protection:` block → `ProtectionConfigError` at the protection check. WP07 relies on (b).
5. **One planted break per capture key** (`meta`, `meta_key_order`, `branches`, `worktrees`, `head`, `new_commits`, `status_log`, `porcelain`, `tree`, `exc_type`, `message`, `error_code`, result fields). Record each as a `git diff` patch block in the Activity Log, so a reviewer can `git apply` it, together with the failing cell ids.
6. **No padding.** Each success cell must exercise a distinct path, and cells that differ only in `friendly_name` count once. Record `--cov-branch` coverage of `mission_creation.py` under the golden run in the Activity Log.
7. **The "unreachable without patches" escape needs orchestrator sign-off.** Stop and report; do not choose a substitute on your own.
8. **Reviewer step:** `git diff --exit-code <base_commit> HEAD -- src/` (no src change) plus a serial regen and `git diff --exit-code tests/core/golden/`.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
