# Data model: implement phases, seam decisions and typed refusals

This mission adds no persisted data. The "entities" are the in-process values that flow between the
implement phases and the typed errors seams raise instead of printing. Persisted state (`meta.json`,
`status.events.jsonl`, `lanes.json`, git refs) is read and written exactly as today (C-001).

## Phase results (values passed along the sequence)

| Value | Produced by phase | Fields (existing names kept) | Consumed by |
|---|---|---|---|
| `ImplementContext` | context | `repo_root`, `auto_commit`, `mission_slug`, `feature_dir`, `wp_file`, `declared_deps` (today the 5-tuple from `_detect_wp_context` + `find_repo_root`) | every later phase |
| `ClaimPreflight` | claim preflight + dependency gate | `planning_branch`, `status_feature_dir`, `lanes_feature_dir` | planning commit, lane selection |
| *(none)* | planning-artifact commit | side effect only, or a refusal | — |
| `WorkspaceSelection` | workspace/lane selection | `resolved_workspace`, `lanes_manifest`, `lane` | allocate, record claim, present |
| `AllocationResult` | allocate | today's `LaneWorkspaceResult` (`workspace_path`, `branch_name`, `lane_id`, `is_reuse`, `mission_branch`, `execution_mode`, `lane_test_env`, `resolution_kind`) + `effective_base` | record claim, present |
| `status_result` | record claim | today's `start_implementation_status` return | claim commit |

Rules:
- Each value is built by exactly one phase and is immutable afterwards. Prefer a frozen dataclass
  or `NamedTuple` in `implement_phases.py`.
- The tracker step boundaries stay where they are today. `detect` wraps context. `validate` wraps
  preflight, the dependency gate, the planning commit, the bulk-edit gate, the operational context
  and workspace/lane selection. `create` wraps allocate and status start. The claim commit runs
  after `create`.
- Exception handling per tracker step is unchanged; data-model.md does not alter it.

## Seam decisions

See [`contracts/seam-decisions.md`](contracts/seam-decisions.md) for signatures. Each decision is pure
or takes an injected port, never prints, and raises one of the typed errors below or an exception
type it raises today.

## Typed refusals

| Error | Raised by | Rendered by (unchanged text) | Status |
|---|---|---|---|
| `WorkPackageStartRejected` ("WP … is not finalized; run …") | dependency-graph seam claim-precondition decision | validate tracker error | existing type, moved raise site |
| `ValueError("dependencies_not_satisfied: …")` | same | validate tracker error | existing type and text, moved raise site |
| `BaseRefUnresolved` (new, carries `base_ref`) | lanes seam base-ref resolution | command prints `_BASE_REF_UNRESOLVED_MSG` + exit 1 | new type replacing a `typer.Exit` inside a decision |
| `ValueError("… is not assigned to any lane in lanes.json")` | lanes seam lane lookup | validate tracker error | existing |
| `MissingLanesError`, `CorruptLanesError` | `lanes/persistence.py` (unchanged) | validate tracker error | unchanged (C-006) |
| `WriteCheckout{WrongBranch,Occupied,Dirty}Error` | `lanes/implement_support.py` (unchanged) | create tracker error | unchanged (C-006) |
| meta.json demotion / corrupt refusal (`str` verdict) | coordination planning-commit predicate | adapter prints `Error: <text>` + exit 1 | existing predicate returns `str | None` today; kept |
| structural planning change list | `implement_cores.detect_structural_planning_changes` (unchanged) | adapter prints the #1598 refusal | unchanged |
| `PrimaryKindReachedCoordStagingError` | coordination planning-commit partition guard | propagates (validate tracker error) | existing type, moved raise site |
| `PlacementResolutionRequired` | placement resolution (FR-008, one remedy definition, FR-018) | validate tracker error | existing type; single message definition |
| VCS-lock: meta missing / invalid JSON | lanes seam VCS-lock decision (typed) | command prints today's two messages + exit 1 | new types replacing `typer.Exit` inside a decision |

## Invariants

1. The side-effect order in plan.md "Engineering Alignment" holds (FR-009 pins it).
2. No lower package imports `specify_cli.cli` (C-004). The adapters in `cli/commands/` are the
   only printers.
3. The C-006 five-tuple `_BookkeepingTransactionIdentifiers` keeps its arity and order.
4. The claim commit propagates exactly `SafeCommitPathPolicyError`, `SafeCommitHeadMismatch` and
   `PlacementResolutionRequired`; everything else is a warning with exit 0.
