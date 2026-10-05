# Contract: seam decisions the implement phases call

This is the internal interface contract between the implement phase sequence (command package)
and the seams. Names are proposals; a WP may rename a function if it records the final name here
and in its tracer entry. Signatures and behaviour are binding.

"Moved verbatim" means the body is unchanged except for removing printing and `typer.Exit` in favour
of the typed error named here. That second step happens in the adjust commit (C-002).

## core/dependency_graph.py

```python
def ensure_wp_claim_preconditions(
    wp_id: str,
    declared_deps: Sequence[str] | Any,
    work_packages: Mapping[str, Mapping[str, Any]],  # reduced snapshot .work_packages
) -> None:
    """Raise WorkPackageStartRejected for an unseeded (genesis) WP, or
    ValueError('dependencies_not_satisfied: ...') when a dependency is not
    approved/done. Pure: no event I/O (the caller reads + reduces)."""
```
- The lane map is built exactly as today: `state.get("lane", Lane.GENESIS)`.
- Provenance is threaded as today: `provenance=work_packages`.

## workspace/context.py

```python
def find_wp_file(repo_root: Path, mission_slug: str, wp_id: str) -> Path: ...        # moved verbatim
def resolve_lane_state_dir(repo_root: Path, mission_slug: str) -> Path: ...            # was implement._resolve_lanes_dir (distinct from lanes.persistence.resolve_lanes_dir)
def resolve_mission_target_branch(mission_slug: str, repo_root: Path) -> str: ...      # was resolve_feature_target_branch
```
- Same exceptions (`FileNotFoundError` texts) as today.
- `find_wp_file` keeps an `__all__` entry, and its now-stale dead-symbol allow-list row is removed (the symbol is live through `__all__`).

## lanes/implement_support.py

```python
class BaseRefUnresolved(StructuredError): base_ref: str
def resolve_base_ref(repo_root: Path, base_ref: str) -> tuple[str, str] | None: ...   # origin-preferred (#4969), verbatim
# _validate_base_ref / _raise_base_ref_unresolved stay CLI-side as thin translators (tests pin typer.Exit)
def resolve_effective_base(repo_root: Path, base: str | None, resolved_workspace) -> tuple[str | None, bool]:
    """(effective_base, ignored_on_planning_lane). Raises BaseRefUnresolved."""
def resolve_execution_lane(resolved_workspace, lanes_feature_dir: Path, wp_id: str) -> tuple[LanesManifest | None, ExecutionLane | None]:
    """(None, None) for a repo-root planning workspace; raises ValueError / MissingLanesError as today."""
def refuse_repo_root_checkout_if_unavailable(repo_root, mission_slug, wp_id, resolved_workspace) -> bool: ...
def ensure_vcs_locked(feature_dir: Path) -> bool:   # True when it wrote the lock; typed errors for missing / invalid meta.json
def git_stdout(repo_root: Path, args: list[str]) -> str: ...   # was implement._git_stdout (moved by WP05); not lifecycle_sync._git_stdout
```
- The command keeps the tracker step text, the "--base is ignored …" warning and
  `_BASE_REF_UNRESOLVED_MSG`.
- The `→ VCS locked to git in meta.json` line keeps its order relative to the other output.

## coordination/planning_commit.py (new sibling in the existing package)

```python
def partition_files_for_commit(files: list[str]) -> tuple[list[str], list[str]]: ...           # verbatim
def guard_planning_commit_partition(files: list[str], *, destination_is_coord: bool) -> None:    # verbatim, raises PrimaryKindReachedCoordStagingError
def meta_json_demotion_refusal(repo_root, mission_slug, meta_path, rel_path) -> str | None: ... # verbatim (+ _read_json_at_ref)
def resolve_bookkeeping_transaction_identifiers(feature_dir, mission_slug, repo_root=None) -> BookkeepingTransactionIdentifiers  # C-006 5-tuple
def feature_dir_file_paths(repo_root: Path, feature_dir: Path) -> list[str]: ...               # verbatim, raises SafeCommitPathPolicyError
def planning_artifact_source_dir(repo_root: Path, feature_dir: Path, mission_slug: str) -> Path: ...
```
- No `console`, `typer` or `cli` imports.
- The adapter `cli/commands/implement_planning_commit.py` keeps the following unchanged:
  `_ensure_planning_artifacts_committed_git`, `_commit_planning_artifacts_transaction`,
  `_run_planning_artifact_commit`, the print helpers, `_refuse_on_unreadable_planning_status`
  and `_planning_commit_branch`.

## status facade

```python
def claim_policy_metadata(shell_pid: int, agent: str) -> dict[str, Any]: ...  # one definition, used by implement and workflow_executor
```

## cli/commands/implement_claim.py

```python
def claim_commit_paths(*, repo_root, feature_dir, wp_file, status_artifacts: Iterable[Path], routes_through_coord: bool) -> list[Path]:
    """Pure: the exact ordered path tuple the claim commit stages today (wp_file, filtered status
    artifacts, meta.json if present, .kittify/config.yaml if present). #5673 changes only this."""
```

## Placement (FR-008, research.md R-1b = B2**)

In `coordination/planning_commit.py`:

```python
@dataclass(frozen=True)
class PlanningPlacement:
    """resolved=True  -> ref is the context placement ref (artifact_placement.placement_ref);
       resolved=False -> the WP action context did not resolve (ActionContextError); the adapter asks
                         the seam for the declared coordination ref *after* the structural check."""
    resolved: bool
    ref: CommitTarget | None          # set iff resolved

def resolve_planning_placement(repo_root, *, mission_slug, wp_id) -> PlanningPlacement:
    """Context first; non-ActionContextError errors propagate unchanged (today's pre-commit gate)."""

def declared_coordination_ref(feature_dir, mission_slug, repo_root) -> str | None:
    """The seam-owned degrade (#5232 shape 2): the mission's declared coordination-branch value via
    the identity cascade. No topology gate, no existence probe, never raises on a missing branch.
    Equal by construction to the value today's adapter read."""

def coordination_filter(repo_root, mission_slug, placement, *, feature_dir) -> str | None:
    """resolved -> placement_coord_filter(ref); unresolved -> declared_coordination_ref(...).
    Called by the adapter where today's code computed `coord_branch_for_filter` (after the
    #1598 structural check)."""
```

- The adapter's arms are keyed on `placement.resolved` and the filter value, with the same four
  outcomes as today.
- `PlacementResolutionRequired` keeps its single remedy definition (FR-018) and is raised only where
  it is raised today (arm b).
