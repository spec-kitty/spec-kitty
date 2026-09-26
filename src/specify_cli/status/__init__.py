"""Canonical status engine for spec-kitty work package lifecycle.

Public API surface — all consumers import from this package.

The event log (status.events.jsonl) is the sole authority for mutable
WP state. No frontmatter reads or writes occur in this module.
"""

from pathlib import Path

from .models import (
    AgentAssignment,
    CurrentWpState,
    DoneEvidence,
    EventStream,
    GuardContext,
    InnerStateChanged,
    Lane,
    NON_DISPLAY_LANES,
    RepoEvidence,
    ReviewApproval,
    ReviewOverride,
    ReviewResult,
    Status,
    StatusEvent,
    StatusSnapshot,
    TransitionRequest,
    ULID_PATTERN,
    VerificationResult,
    WPInnerStateDelta,
    actor_identity_str,
    get_all_lanes,
    get_all_lane_values,
)
from .reducer import (
    SNAPSHOT_FILENAME,
    ReviewResultLookup,
    event_sourced_review_result,
    materialize,
    materialize_snapshot,
    materialize_to_json,
    reduce,
    review_result_from_state,
    wp_snapshot_state,
)
from .store import (
    is_non_lane_event,
    is_retrospective_lifecycle_event,
    ANNOTATION_KIND,
    EVENTS_FILENAME,
    EventPersistenceError,
    StoreError,
    # WP03 (fsm-write-path-integrity-01M1TZV6, FR-010): the raw append
    # primitives (append_event, append_event_verified,
    # append_event_stream_atomic_verified, append_events_atomic_verified,
    # append_primary_checkout_event_verified,
    # append_primary_checkout_events_atomic_verified,
    # append_annotations_atomic_verified, append_raw_rows_atomic) are NO
    # LONGER exported here. They were promoted onto this facade by WP02 of
    # verdict-seam-boundary-hardening-01KZG179 (FR-004/T006, so
    # coordination/status_service.py could avoid a deep ``status.store``
    # import) and by WP01 of this mission (append_raw_rows_atomic, for the
    # hardened retrospective writers). Both promotions handed an unlocked,
    # unvalidated write door to any importer; they now live behind
    # ``specify_cli.status._unsafe`` with an enumerated, shrink-only
    # ``ALLOWED_CALLERS`` set gated by
    # tests/architectural/test_status_unsafe_allowlist.py.
    read_event_stream,
    read_event_stream_from_text,
    read_events,
    read_events_from_text,
    read_events_raw,
)
from .transitions import (
    # Non-authoritative derived projection (NFR-002, I1): re-exported for tests
    # and graph tooling only. Never consult it as an edge/transition gate; route
    # edge questions through wp_state_for(from).may_transition_to(to).
    ALLOWED_TRANSITIONS,
    CANONICAL_LANES,
    LANE_ALIASES,
    TERMINAL_LANES,
    is_terminal,
    resolve_lane_alias,
    validate_transition,
)
from .verdict_vocab import (
    # 2026-08-07 (landing fix, verdict-seam-write-unification #3245): promoted
    # onto the facade so the four repo-wide callers of the artifact<->event
    # verdict bridge (agent_utils.status, tasks_parsing_validation,
    # tasks_verdict_persistence) resolve it WITHOUT a direct
    # ``specify_cli.status.verdict_vocab`` import
    # (test_status_module_boundary.py SR-2).
    is_changes_requested,
    to_artifact_verdict,
    # WP01 (verdict-seam-boundary-hardening-01KZG179, FR-001/FR-006): promoted
    # the REST of the verdict_vocab public surface onto the facade -- WP02's
    # consumer migration needs EventVerdict (proof/events.py) and the three
    # constants (tasks_move_task.py, verdict_provenance_backfill.py) resolvable
    # WITHOUT a direct ``specify_cli.status.verdict_vocab`` import, same as the
    # two symbols promoted above.
    APPROVED,
    CHANGES_REQUESTED,
    EventVerdict,
    REJECTED,
    artifact_verdicts,
    emission_artifact_verdicts,
    emission_event_verdict,
    event_verdicts,
    is_approved,
    to_event_verdict,
)
from .review_result_parse import (
    # WP08 (worktree-root-resolution, FR-010/FR-011): promoted onto the facade
    # so both verdict surfaces (``orchestrator-api transition`` and ``agent
    # status emit``) validate ``--review-result-json`` through the SAME parser
    # WITHOUT a direct ``specify_cli.status.review_result_parse`` import
    # (test_status_module_boundary.py). Depends only on .models/.verdict_vocab,
    # both imported above -- no cycle.
    parse_review_result_json,
)
from .transition_context import (
    TransitionContext,
)
from .wp_state import (
    InvalidTransitionError,
    WPState,
    annotate,
    wp_state_for,
)
from .emit import (
    TransitionError,
    build_claim_policy_metadata,
    build_resolved_actor,
    build_self_asserting_actor,
    emit_inner_state_changed,
    emit_resolved_binding,
    emit_status_transition,
    parse_agent_boundary_string,
)
from .resolved_binding import (
    ResolvedBinding,
)
from .wp_view import (
    AuthoredGroup,
    ResolvedGroup,
    WPView,
    reconstruct_wp_view,
)
from .wp_metadata import (
    WPMetadata,
    _Builder,
    read_authored_wp_frontmatter,
    read_authored_wp_frontmatter_lenient,
    read_wp_frontmatter,
)
from .wp_status_metadata import (
    WPStatusChangeMetadata,
)
from .wp_review import (
    resolve_event_stream_review,
    resolve_snapshot_review,
)
from .lane_reader import (
    CanonicalStatusNotFoundError,
    LEGACY_UNINITIALIZED_SENTINEL,
    get_all_wp_lanes,
    get_all_wp_snapshots,
    get_wp_lane,
    has_event_log,
)
from .views import (
    generate_status_view,
    git_operation_in_progress,
    materialize_if_stale,
    write_derived_views,
)
from .progress import (
    DEFAULT_LANE_WEIGHTS,
    PROGRESS_SEMANTICS,
    ProgressResult,
    WPProgress,
    compute_done_percentage,
    compute_weighted_progress,
    generate_progress_json,
)
from .adapters import (
    ensure_runtime_moment_producer,
    fire_lifecycle_saas_fanout,
    fire_resolved_binding_fanout,
    fire_saas_fanout,
    register_lifecycle_saas_fanout_handler,
    register_resolved_binding_fanout_handler,
    register_saas_fanout_handler,
)
from .bootstrap import (
    BootstrapResult,
    bootstrap_canonical_state,
)
from .event_log_merge import (
    EventLogMergeError,
    merge_event_log_files,
    merge_event_log_texts,
)
from .identity_audit import (
    IdentityState,
    audit_repo,
    classify_mission,
    find_ambiguous_selectors,
    find_duplicate_prefixes,
    summarize,
)
from .locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
)
from .preflight import (
    is_dossier_snapshot,
)
from .lifecycle import (
    DERIVED_LIFECYCLE_FILENAME,
    MISSION_ABANDONED_THRESHOLD_DAYS,
    MISSION_RECENT_COMPLETION_WINDOW_DAYS,
    MISSION_STALE_THRESHOLD_DAYS,
    MissionLifecycleResult,
    derive_mission_lifecycle,
    generate_lifecycle_json,
    is_mission_completed,
    is_mission_merged,
)
from .validate import (
    StatusValidationReadError,
    ValidationResult,
    validate_derived_views,
    validate_done_evidence,
    validate_event_schema,
    validate_materialization_drift,
    validate_transition_legality,
)
from .aggregate import (
    ActiveWPStatus,
    CoordAuthorityUnavailable,
    InvalidMissionSlug,
    MissionMetadataUnavailable,
    MissionStatus,
)
from .lifecycle_events import (
    AUTHORITATIVE_NON_LANE_EVENT_TYPES,
    FOLLOW_UP_RECORDED,
    LIFECYCLE_EVENT_TYPES,
    LOCAL_ONLY_LIFECYCLE_EVENT_TYPES,
    MISSION_CREATED,
    MISSION_REOPENED,
    PLAN_COMPLETED,
    PLAN_STARTED,
    REVIEWER_SELF_APPROVAL,
    SPECIFY_COMPLETED,
    SPECIFY_STARTED,
    TASKS_COMPLETED,
    TASKS_STARTED,
    WP_CREATED,
    MissionNotCompletedError,
    build_saas_lifecycle_queue_event,
    emit_artifact_phase,
    emit_artifact_phase_local,
    fanout_lifecycle_event_hosted,
    emit_follow_up_recorded,
    emit_mission_created_local,
    emit_mission_reopened,
    emit_project_initialized,
    emit_reviewer_self_approval,
    emit_wp_created_local,
    has_non_bootstrap_status_history,
    is_authoritative_non_lane_event_type,
    _resolve_local_actor,
    mission_event_log_path,
    project_event_log_path,
    read_lifecycle_events,
    repo_root_for_lifecycle_log,
)
from .tail_reader import (
    EMPTY_DIGEST,
    ResumeRefused,
    TailCursor,
    poll_once,
    tail_events,
    validate_resume_cursor,
)

# NOTE (WIRE-M2-03, 2026-08-22, rework cycle 2): ``migrate_lifecycle_envelope``
# (the F2-T1 rewrite entry point) is deliberately NOT promoted onto this
# facade, even though ``project_event_log_path`` above was. Its bare name is
# IDENTICAL to its own home submodule's filename
# (``status/migrate_lifecycle_envelope.py``). Promoting it here would make
# ``from specify_cli.status import migrate_lifecycle_envelope`` resolve to
# the FUNCTION (the last name bound in this module's namespace wins over the
# submodule attribute Python's import system auto-sets on this package) --
# which silently breaks the two pre-existing tests
# (tests/status/test_migrate_lifecycle_envelope.py,
# tests/status/test_migrate_lifecycle_envelope_node_id_parity.py) that
# already use that exact import shape to reach the MODULE (via Python's
# implicit "attribute not found on package -> import as submodule"
# fallback, e.g. to monkeypatch ``migrate_lifecycle_envelope_module.os.replace``
# or call the private ``_generate_node_id`` helper). The sole src/ caller
# (upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope) reaches the
# function via a direct submodule import instead, and that one file is a
# documented, temporary entry in
# tests/architectural/test_status_module_boundary.py's
# ``_WP10_DEFERRED_FILES`` pending a follow-up bead to either rename the
# function or teach the AST scanner about this name collision.
from .views import (
    format_post_mission_events,
)
from .work_package_lifecycle import (
    GENERIC_IMPLEMENTATION_ACTORS,
    WorkPackageClaimConflict,
    WorkPackageStartRejected,
    _actor_key,
    start_implementation_status,
    start_review_status,
)
from .doctor import (
    run_doctor,
)
from .doctor_husks import (
    WORKTREES_DIRNAME,
    RegisteredWorktreePaths,
    WorkspaceHuskRegistrationError,
    fix_workspace_husks,
    registered_worktree_paths,
    scan_workspace_husks,
)
from .dup_key_repair import (
    DuplicateKeyRepairError,
    detect_duplicate_key_artifacts,
    find_duplicate_keys_in_text,
    plan_artifact_repair,
)

# WP03/WP04 (runtime-state-birth-cutover-all-paths-01KYH654): the cut-over
# predicate reaches its src/ consumer (``cli.commands.cutover_guard``) through
# this package surface, not by importing the submodule directly -- the status
# boundary is load-bearing here, since ``cutover_eligibility`` already carries a
# deferred local import of ``migration.backfill_runtime_state`` to break a cycle.
# Only the two symbols an src/ caller actually consumes are re-exported; the
# corpus-lock helpers stay submodule-private so the dead-symbol gate keeps
# holding them honest.
from .cutover_eligibility import (
    CutOverVerdict,
    is_cut_over,
)


def uninitialized_status_error(mission_slug: str, wp_id: str, feature_dir: Path) -> str:
    """Return the cycle-aware missing-status message without eager dependency-graph imports."""
    from .uninitialized_hint import uninitialized_status_error as _uninitialized_status_error

    return str(_uninitialized_status_error(mission_slug, wp_id, feature_dir))


# WP13 (IC-07c) retired ``COORD_OWNED_STATUS_FILES`` -- the canonical status
# artifacts (event log + snapshot) frozenset -- onto the single canonical churn
# owner (``coordination.coherence.is_toolchain_generated_churn`` /
# ``mission_runtime.MissionArtifactKind.STATUS_STATE``, FR-012). Consumers that
# used to import this frozenset now classify by kind/path through that owner
# instead of a locally-duplicated basename set. ``EVENTS_FILENAME`` /
# ``SNAPSHOT_FILENAME`` remain -- only the derived exemption frozenset (and its
# 8 consumer call sites) was retired.

__all__ = [
    "ActiveWPStatus",
    "CutOverVerdict",
    # WP05 (verdict-seam-write-unification-01KZ9Q35, out-of-map): promoted onto
    # the facade so every verdict-authority reader (tasks_verdict_persistence,
    # agent_utils.status, tasks_parsing_validation, workflow_cores/executor)
    # can resolve the event-sourced verdict WITHOUT a direct
    # ``specify_cli.status.reducer`` import (SR-2, test_status_module_boundary.py).
    # This file is not in WP05's owned_files, but the promotion is a single,
    # mechanical two-name addition required by the contract's own stated public
    # API (contracts/verdict-authority-read.md names
    # ``event_sourced_review_result``/``ReviewResultLookup`` as the read seam);
    # without it the reader collapse cannot happen through the facade at all.
    "ReviewResultLookup",
    "event_sourced_review_result",
    # WP01 (verdict-seam-boundary-hardening-01KZG179, FR-006): promoted beside
    # its sibling ``event_sourced_review_result`` above -- the
    # snapshot-in-hand variant of the same read seam
    # (contracts/verdict-authority-read.md) so
    # ``post_merge/review_artifact_consistency.py`` can resolve it through
    # the facade instead of re-implementing the decode locally (C-002).
    "review_result_from_state",
    # WP08 (worktree-root-resolution, FR-010/FR-011): the canonical
    # ``--review-result-json`` parser, promoted onto the facade so both verdict
    # surfaces validate through it without a direct submodule import.
    "parse_review_result_json",
    "AgentAssignment",
    "CurrentWpState",
    "actor_identity_str",
    "_actor_key",
    "ALLOWED_TRANSITIONS",
    "EventStream",
    "InnerStateChanged",
    "ReviewOverride",
    "Status",
    "WPInnerStateDelta",
    "annotate",
    "build_claim_policy_metadata",
    "build_resolved_actor",
    "is_cut_over",
    "parse_agent_boundary_string",
    "emit_inner_state_changed",
    "emit_resolved_binding",
    "ResolvedBinding",
    "AuthoredGroup",
    "ResolvedGroup",
    "WPView",
    "reconstruct_wp_view",
    "resolve_event_stream_review",
    "read_event_stream",
    "read_event_stream_from_text",
    "read_authored_wp_frontmatter",
    "read_authored_wp_frontmatter_lenient",
    "CoordAuthorityUnavailable",
    "EventLogMergeError",
    "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS",
    "FeatureStatusLockTimeoutError",
    "GuardContext",
    "IdentityState",
    "InvalidMissionSlug",
    "MissionMetadataUnavailable",
    "ANNOTATION_KIND",
    "LIFECYCLE_EVENT_TYPES",
    "AUTHORITATIVE_NON_LANE_EVENT_TYPES",
    "is_authoritative_non_lane_event_type",
    "LOCAL_ONLY_LIFECYCLE_EVENT_TYPES",
    "FOLLOW_UP_RECORDED",
    "MISSION_CREATED",
    "MISSION_REOPENED",
    "WP_CREATED",
    "mission_event_log_path",
    "project_event_log_path",
    "read_lifecycle_events",
    "MissionStatus",
    "PLAN_COMPLETED",
    "PLAN_STARTED",
    "REVIEWER_SELF_APPROVAL",
    "SPECIFY_COMPLETED",
    "SPECIFY_STARTED",
    "TASKS_COMPLETED",
    "TASKS_STARTED",
    "MissionNotCompletedError",
    "TransitionRequest",
    "GENERIC_IMPLEMENTATION_ACTORS",
    "WorkPackageClaimConflict",
    "WorkPackageStartRejected",
    "build_saas_lifecycle_queue_event",
    "emit_artifact_phase",
    "emit_artifact_phase_local",
    "fanout_lifecycle_event_hosted",
    "emit_follow_up_recorded",
    "emit_mission_created_local",
    "emit_mission_reopened",
    "emit_project_initialized",
    "_resolve_local_actor",
    "emit_reviewer_self_approval",
    "emit_wp_created_local",
    "format_post_mission_events",
    "has_non_bootstrap_status_history",
    "is_non_lane_event",
    "is_retrospective_lifecycle_event",
    "materialize_snapshot",
    "repo_root_for_lifecycle_log",
    "EMPTY_DIGEST",
    "ResumeRefused",
    "TailCursor",
    "poll_once",
    "tail_events",
    "validate_resume_cursor",
    "run_doctor",
    "DuplicateKeyRepairError",
    "detect_duplicate_key_artifacts",
    "find_duplicate_keys_in_text",
    "plan_artifact_repair",
    "start_implementation_status",
    "start_review_status",
    "CanonicalStatusNotFoundError",
    "LEGACY_UNINITIALIZED_SENTINEL",
    "DEFAULT_LANE_WEIGHTS",
    "DERIVED_LIFECYCLE_FILENAME",
    "InvalidTransitionError",
    "MISSION_ABANDONED_THRESHOLD_DAYS",
    "MISSION_RECENT_COMPLETION_WINDOW_DAYS",
    "MISSION_STALE_THRESHOLD_DAYS",
    "MissionLifecycleResult",
    "ProgressResult",
    "ReviewResult",
    "TransitionContext",
    "WPProgress",
    "WPState",
    "PROGRESS_SEMANTICS",
    "compute_done_percentage",
    "compute_weighted_progress",
    "derive_mission_lifecycle",
    "generate_lifecycle_json",
    "generate_progress_json",
    "is_mission_completed",
    "is_mission_merged",
    "materialize_if_stale",
    "CANONICAL_LANES",
    "DoneEvidence",
    "EVENTS_FILENAME",
    "EventPersistenceError",
    "Lane",
    "NON_DISPLAY_LANES",
    "get_all_lanes",
    "get_all_lane_values",
    "LANE_ALIASES",
    "RepoEvidence",
    "ReviewApproval",
    "SNAPSHOT_FILENAME",
    "StatusEvent",
    "StatusSnapshot",
    "StoreError",
    "TERMINAL_LANES",
    "TransitionError",
    "ULID_PATTERN",
    "ValidationResult",
    "VerificationResult",
    "WORKTREES_DIRNAME",
    "RegisteredWorktreePaths",
    "WorkspaceHuskRegistrationError",
    "WPMetadata",
    "_Builder",
    "BootstrapResult",
    "audit_repo",
    "bootstrap_canonical_state",
    "classify_mission",
    "feature_status_lock",
    "find_ambiguous_selectors",
    "find_duplicate_prefixes",
    "fix_workspace_husks",
    "is_dossier_snapshot",
    "merge_event_log_files",
    "merge_event_log_texts",
    "register_lifecycle_saas_fanout_handler",
    "register_resolved_binding_fanout_handler",
    "register_saas_fanout_handler",
    "summarize",
    "uninitialized_status_error",
    # WP03 (fsm-write-path-integrity-01M1TZV6, FR-010): the raw append
    # primitives are not facade exports -- see ``status/_unsafe.py`` and the
    # provenance note on the ``.store`` import block above.
    "build_self_asserting_actor",
    "emit_status_transition",
    "generate_status_view",
    "get_all_wp_lanes",
    "get_all_wp_snapshots",
    "get_wp_lane",
    "git_operation_in_progress",
    "has_event_log",
    "is_terminal",
    "materialize",
    "materialize_to_json",
    "ensure_runtime_moment_producer",
    "fire_lifecycle_saas_fanout",
    "fire_resolved_binding_fanout",
    "fire_saas_fanout",
    "WPStatusChangeMetadata",
    "read_events",
    "read_events_from_text",
    "read_events_raw",
    "read_wp_frontmatter",
    "reduce",
    "resolve_lane_alias",
    "resolve_snapshot_review",
    # WP01 (verdict-seam-boundary-hardening-01KZG179, FR-001/FR-006): promoted
    # the REST of the verdict_vocab public surface onto the facade -- mirrors
    # the comment on the ``is_changes_requested``/``to_artifact_verdict``
    # import above (test_status_module_boundary.py SR-2).
    "APPROVED",
    "CHANGES_REQUESTED",
    "EventVerdict",
    "REJECTED",
    "artifact_verdicts",
    "emission_artifact_verdicts",
    "emission_event_verdict",
    "event_verdicts",
    "is_approved",
    "to_event_verdict",
    "is_changes_requested",
    "to_artifact_verdict",
    "StatusValidationReadError",
    "validate_derived_views",
    "validate_done_evidence",
    "validate_event_schema",
    "validate_materialization_drift",
    "validate_transition",
    "validate_transition_legality",
    "wp_snapshot_state",
    "wp_state_for",
    "registered_worktree_paths",
    "scan_workspace_husks",
    "write_derived_views",
]


def _retired_dossier_sync_noop(*_args: object, **_kwargs: object) -> None:
    """Compatibility target for the retired dossier fan-out API."""


def __getattr__(name: str) -> object:
    """Preserve the 3.2.6 import seam without reviving its retired registry."""
    if name in {"fire_dossier_sync", "register_dossier_sync_handler"}:
        return _retired_dossier_sync_noop
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
