---
work_package_id: WP02
title: Mission base authority
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-002
- NFR-003
- SC-004
planning_base_branch: fix/7560-dependency-ref-spine-base
merge_target_branch: fix/7560-dependency-ref-spine-base
branch_strategy: Planning artifacts for this mission were generated on fix/7560-dependency-ref-spine-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7560-dependency-ref-spine-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-base-window-bound-01M78XB4
base_commit: 9488e7c2970ffb38ab97b5057d3bf142e3dcf534
created_at: '2026-11-12T22:28:49.460259+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Foundation
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/mission_base.py
create_intent:
- src/specify_cli/consolidation/mission_base.py
- tests/consolidation/test_mission_base.py
- tests/specify_cli/core/test_mission_base_recording.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/mission_base.py
- src/specify_cli/meta_keys.py
- src/specify_cli/mission_metadata.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_meta.py
- tests/consolidation/test_mission_base.py
- tests/specify_cli/core/test_mission_base_recording.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Mission base authority

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`, and address every item. Record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

The tidy-first enabler. It adds **one** authority for "the commit this Mission branch was cut from" (the *Mission base*) and changes no verdict. FR-001, FR-002, NFR-002, NFR-003.

- New Missions record `meta.json` `mission_base_sha` where their Mission branch is created.
- `resolve_mission_base(...)` returns a `MissionBase` whose provenance is `recorded`, else `derived`, else `unavailable`. It is fail-closed: any probe error, or any candidate that is not an ancestor of the Mission branch, never yields a base.
- `pre_mission_history(repo_root, window_base, base)` returns `rev-list <window_base>..<base>`. That is empty when the target reaches the base, or when the base is unavailable.
- Nothing calls these yet (WP03 does). Zero behaviour change for consolidation.

## Context & Constraints

- Operator rulings (`decisions/`): DM `01M78XBQS8NE8PPMSTZHMDJ610` (record + derive) and DM `01M78XBWYTWJ6TZJVF4GWQMCQF` (derive = first parent of the earliest first-parent commit on the Mission branch adding `kitty-specs/<slug>/`). The lane creation base is **not** a valid source: it sits above the planning and pre-implement Mission commits.
- [data-model.md](../data-model.md) defines `MissionBase`.
- Terminology: the *Mission base* is never the "claim base" (`reconciliation_bound._bound_claim_base`), which is a different authority. Do not reuse or rename that.
- `meta.json` keys written outside the TypedDicts live in `src/specify_cli/meta_keys.py`; follow `CREATE_RETURN_BRANCH_KEY`.
- Complexity ≤ 15, ruff, ruff format, mypy clean, no suppressions.

## Branch Strategy

- **Planning base branch**: `fix/7560-dependency-ref-spine-base`
- **Merge target branch**: `fix/7560-dependency-ref-spine-base`
- Run `spec-kitty agent action implement WP02 --agent claude --mission mission-base-window-bound-01M78XB4`.

## Subtasks & Detailed Guidance

### Subtask T006 – Meta key

- Add `MISSION_BASE_SHA_KEY = "mission_base_sha"` to `meta_keys.py`, with a comment: the commit the Mission branch was cut from, written once at create/mint (#7560); absent on Missions created earlier.
- Add `mission_base_sha: str` to the `NotRequired`/total=False part of the relevant TypedDict in `mission_metadata.py`, wherever `create_return_branch` is declared. Check whether a meta-key registry or shape gate (`audit/shape_registry.py`, any `tests/architectural/*meta*`) enumerates keys; register the new key there if one does. Grep for `create_return_branch` in `src/` and `tests/architectural/`.

### Subtask T007 – Record the base where the Mission branch is created

1. **Topic / protected mint**: `core/mission_creation_protected_mint.py`, where `meta["mission_branch"] = branch_name` is set after `switch_write_checkout(..., start_point=target_branch, ...)`. Record the SHA the branch was created at: read the new branch's tip right after the switch, using the existing helpers (`capture_branch_tip` from `specify_cli.core.vcs.git`, or the module's own probe). That equals the start point at creation. If the read fails, do not write the key. Never raise from a failed read; derivation covers the gap.
2. **Coordination-branch create**: `core/mission_creation_meta.py::_build_create_meta` already computes `coordination_branch_creation_base` when the coordination branch is newly created. When no mint has recorded the key (`MISSION_BASE_SHA_KEY not in meta`) and a coordination branch was created this run, record that SHA. A reused coordination branch records nothing, because its base is unknown here.
- Never overwrite an existing value (write-once).

### Subtask T008 – `consolidation/mission_base.py`

```python
class MissionBaseProvenance(StrEnum): RECORDED = "recorded"; DERIVED = "derived"; UNAVAILABLE = "unavailable"

@dataclass(frozen=True)
class MissionBase:
    sha: str | None
    provenance: MissionBaseProvenance
    reason: str | None = None   # why derived / unavailable, one short clause

def resolve_mission_base(repo_root: Path, feature_dir: Path | None, *, mission_branch: str, mission_slug: str) -> MissionBase: ...
```

Order:

1. **Recorded**: read `feature_dir / "meta.json"` (an absent or unreadable file, or an absent key, means "not recorded"). Validate that the value resolves to a commit (`git_probes.resolve_commit`) and is an ancestor of, or equal to, `mission_branch` (`git merge-base --is-ancestor`). Use an existing probe if there is one: grep `is-ancestor` in `consolidation/git_probes.py` and `lanes/_git.py`. If valid, return it as `RECORDED`. If invalid, remember the reason and continue.
2. **Derived**: `git log --first-parent --reverse --diff-filter=A --format=%H <mission_branch> -- kitty-specs/<mission_slug>/`. Take the first line, the earliest commit on the first-parent spine that adds a file under the Mission directory, and use its first parent `<sha>^1`. If there is no such commit, or it has no parent (a root commit), the base is unavailable. Validate it the same way as in step 1. Return it as `DERIVED` with a reason such as `"no mission_base_sha recorded"` or `"recorded mission_base_sha <short> is not on the Mission branch"`.
   - Pass `--diff-merges=first-parent` explicitly, so a merge commit is diffed against its first parent on every git version.
3. **Unavailable**: `MissionBase(None, UNAVAILABLE, reason)`.

Every `GitProbeError` or subprocess failure maps to `UNAVAILABLE`, with the probe failure as the reason. Use `run_command` / the `git_probes` style. Keep each step its own helper (`_recorded_base`, `_derived_base`, `_is_on_branch`) so complexity stays low.

### Subtask T009 – `pre_mission_history`

```python
def pre_mission_history(repo_root: Path, window_base: str | None, base: MissionBase) -> tuple[str, ...]:
    """Commits reachable from the Mission base and not from the window base (``rev-list window_base..base``)."""
```

- Return `()` when `window_base is None` or `base.sha is None`. Otherwise call `commits_in_range(repo_root, window_base, base.sha)`.
- A `GitProbeError` **propagates**. The caller (WP03) turns it into the existing fail-closed refusal path; an empty tuple would hide an error.
- Stay within NFR-002: resolving the base plus this range must cost at most 3 git invocations in the common recorded case (rev-parse, is-ancestor, rev-list). Document that.

### Subtask T010 – Unit tests

`tests/consolidation/test_mission_base.py` (real tmp git repos, `pytest.mark.git_repo`):

- Recorded and valid → `RECORDED`.
- Recorded but not an ancestor (the branch was rebased elsewhere) → falls through to `DERIVED`, and the reason names the recorded sha.
- Not recorded; scaffold commit on the Mission branch → `DERIVED`, base == scaffold commit's first parent.
- Not recorded; scaffold commit is a root commit → `UNAVAILABLE`.
- Not recorded; the scaffold arrived through a second-parent merge, so it is not on the first-parent spine → the derivation must not pick a commit above Mission work. Assert `UNAVAILABLE`, or a base that is an ancestor of the merge's first parent. Document the behaviour you get.
- An unresolvable `mission_branch` → `UNAVAILABLE` (probe failure), never raises.
- `pre_mission_history`: an empty tuple when the target reaches the base; the exact commits when it does not; `()` for `UNAVAILABLE`; a probe error propagates.

`tests/specify_cli/core/test_mission_base_recording.py`: drive the real create path (`spec-kitty agent mission create` through the CLI runner, or the creation API the existing create tests use: find a sibling test with `grep -rl "_build_create_meta\|mission_create" tests/`). Assert that `meta.json` carries `mission_base_sha` equal to the target tip at create, for both the default topic mint and an explicit `--topology coord` create. Also assert write-once.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/consolidation/test_mission_base.py tests/specify_cli/core/test_mission_base_recording.py -q
# blast radius: the create path
.venv/bin/python -m pytest tests/specify_cli/core -q -k "mission_creation or protected_mint or create" -n auto --dist loadfile
uv run --frozen ruff check <changed files>; uv run --frozen ruff format --check --force-exclude <changed files>; uv run --frozen mypy <changed src files>
```

## Risks & Mitigations

- **Creation path regressions**: the mint and create paths are heavily tested. Run their tests, and keep the recording side-effect-free on failure.
- **A wrong derived base above Mission work** would silently exempt Mission commits. Pin it with the second-parent-scaffold test.

## Review Guidance

- One authority: no other module computes a Mission base.
- Every failure path yields `UNAVAILABLE`, never a guessed sha.
- No consolidation behaviour changed in this WP.
