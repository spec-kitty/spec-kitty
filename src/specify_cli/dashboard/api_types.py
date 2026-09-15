"""TypedDict response shapes for dashboard JSON endpoints.

These types document the exact JSON structure returned by each dashboard
handler method.  They serve as machine-readable contracts consumed by the
JS-to-Python contract test (``test_api_contract.py``) and by ``mypy`` for
return-type validation on handler methods.

The definitions below are derived from the *actual* handler output in
``handlers/features.py``, ``handlers/api.py``, ``scanner.py``, and
``diagnostics.py``.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Leaf / reusable types (alphabetical)
# ---------------------------------------------------------------------------


class ArtifactDirectoryFile(TypedDict):
    """Single file entry in an artifact directory listing."""

    name: str
    path: str
    icon: str


class ArtifactDirectoryResponse(TypedDict):
    """Response from ``/api/contracts/{id}`` and ``/api/checklists/{id}``."""

    files: list[ArtifactDirectoryFile]


class ArtifactInfo(TypedDict):
    """Per-artifact existence / stat metadata produced by ``scanner.py``."""

    exists: bool
    mtime: float | None
    size: int | None


class ErrorResponse(TypedDict):
    """Generic error envelope returned by ``_send_json`` on failure."""

    error: str
    detail: NotRequired[str]
    status: NotRequired[int]


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class HealthResponse(TypedDict, total=False):
    """Response from ``GET /api/health``."""

    status: str
    project_path: str
    token: str  # conditionally present
    preflight_warning: str  # FR-006 banner; blocking reason or passed advisory


# ---------------------------------------------------------------------------
# Kanban endpoint
# ---------------------------------------------------------------------------


class KanbanTaskData(TypedDict, total=False):
    """Single work-package card on the kanban board.

    The ``encoding_error`` variant (produced when ``read_file_resilient``
    fails) omits ``agent_profile`` and ``role`` and adds
    ``encoding_error: True``.
    """

    id: str
    title: str
    lane: str
    subtasks: list[Any]
    # Progress from the canonical checkbox rows in the WP body (#2504);
    # (0, 0) when the WP doesn't track completion via checkboxes.
    subtasks_done: int
    subtasks_total: int
    agent: str
    model: str
    agent_profile: str
    role: str
    assignee: str
    phase: str
    prompt_markdown: str
    prompt_path: str
    encoding_error: bool  # present only on decode-failure variant


class KanbanStats(TypedDict, total=False):
    """Per-feature kanban summary counts.

    ``error`` is present only when the event log is missing or unreadable.
    """

    total: int
    planned: int
    doing: int
    for_review: int
    approved: int
    done: int
    error: str


class KanbanResponse(TypedDict):
    """Response from ``GET /api/kanban/{feature_id}``."""

    lanes: dict[str, list[KanbanTaskData]]
    is_legacy: bool
    upgrade_needed: bool
    weighted_percentage: float | None


# ---------------------------------------------------------------------------
# Research endpoint
# ---------------------------------------------------------------------------


class ResearchArtifact(TypedDict):
    """Single artifact entry in the research response."""

    name: str
    path: str
    icon: str


class ResearchResponse(TypedDict):
    """Response from ``GET /api/research/{feature_id}``."""

    main_file: str | None
    artifacts: list[ResearchArtifact]


# ---------------------------------------------------------------------------
# Mission registry types (T048, WP09)
# ---------------------------------------------------------------------------


class MissionRecord(TypedDict, total=False):
    """Single mission record from :func:`scanner.build_mission_registry`.

    This is the canonical wire shape for per-mission data keyed by
    ``mission_id`` (a ULID) or a pseudo-key (``legacy:<slug>`` or
    ``orphan:<path.name>``).

    Fields
    ------
    mission_id
        The registry key itself.  For assigned/pending missions this is the
        ULID from ``meta.json``.  For legacy missions it is ``legacy:<slug>``;
        for orphan missions it is ``orphan:<dir-name>``.
    mission_slug
        Directory name (e.g. ``"080-foo"``).  Used for display and URL routing.
    display_number
        Integer numeric prefix (e.g. ``80`` for ``080-foo``), or ``None`` for
        pre-merge missions.  This is a *display* metadata field — it is NOT
        the identity key.
    mid8
        First 8 characters of the ULID ``mission_id``, precomputed for compact
        display.  ``None`` for pseudo-key (legacy/orphan) records.
    feature_dir
        Absolute path to the mission directory as a string.
    """

    mission_id: str  # ULID or pseudo-key
    mission_slug: str  # directory name
    display_number: int | None  # numeric prefix for display sort; None = pre-merge
    mid8: str | None  # first 8 chars of mission_id; None for pseudo-keys
    feature_dir: str  # absolute path as string


# ---------------------------------------------------------------------------
# Features-list endpoint (the largest shape)
# ---------------------------------------------------------------------------


class WorktreeInfo(TypedDict):
    """Per-feature worktree metadata."""

    path: str | None
    exists: bool


class WorkflowStatus(TypedDict):
    """Workflow progression status (specify → plan → tasks → implement)."""

    specify: str
    plan: str
    tasks: str
    implement: str


class FeatureItem(TypedDict):
    """Single feature entry produced by ``scan_all_features``."""

    id: str
    name: str
    display_name: str
    path: str
    artifacts: dict[str, ArtifactInfo]
    workflow: WorkflowStatus
    kanban_stats: KanbanStats
    mission_status: str  # "active" | "planned" | "done" | "draft" | "discarded"
    next_action: NotRequired[str | None]
    meta: dict[str, Any]
    worktree: WorktreeInfo
    is_legacy: bool  # added by handler, not scanner


class MissionContext(TypedDict, total=False):
    """Active mission context block in the features-list response.

    ``feature`` is present only when an active feature is detected.
    ``path`` may be ``None`` when produced by ``format_path_for_display``.
    """

    name: str
    domain: str
    version: str
    slug: str
    description: str
    path: str | None
    feature: str  # absent when no active feature


class FeaturesListResponse(TypedDict):
    """Response from ``GET /api/features``."""

    features: list[FeatureItem]
    active_feature_id: str | None
    project_path: str | None
    worktrees_root: str | None
    active_worktree: str | None
    active_mission: MissionContext


class FeaturesListErrorResponse(TypedDict):
    """Error variant of the features-list response (HTTP 500)."""

    error: str
    detail: str


# ---------------------------------------------------------------------------
# Glossary endpoints (WP02)
# ---------------------------------------------------------------------------


class GlossaryTermRecord(TypedDict):
    """Single glossary term returned by ``GET /api/glossary-terms``."""

    surface: str
    definition: str
    status: str  # "active" | "draft" | "deprecated"
    confidence: float  # 0.0–1.0


class GlossaryHealthResponse(TypedDict, total=False):
    """Response from ``GET /api/glossary-health``."""

    total_terms: int
    active_count: int
    draft_count: int
    deprecated_count: int
    high_severity_drift_count: int
    orphaned_term_count: int
    entity_pages_generated: bool
    entity_pages_path: str | None
    last_conflict_at: str | None
    validation_errors: list[dict[str, Any]] | None


# ---------------------------------------------------------------------------
# Decay watch tile (WP05)
# ---------------------------------------------------------------------------


class DecayWatchTileResponse(TypedDict, total=False):
    """Response from ``GET /api/charter-lint``."""

    has_data: bool
    scanned_at: str | None
    orphan_count: int
    contradiction_count: int
    staleness_count: int
    reference_integrity_count: int
    high_severity_count: int
    total_count: int
    feature_scope: str | None
    duration_seconds: float | None


# ---------------------------------------------------------------------------
# Diagnostics endpoint (complex, many nested types)
# ---------------------------------------------------------------------------


class FileIntegrity(TypedDict):
    """File-integrity section of the diagnostics response."""

    total_expected: int
    total_present: int
    total_missing: int
    missing_files: list[str]


class DiagnosticsFeatureStatus(TypedDict):
    """Per-feature status in the diagnostics all_features list."""

    name: str
    state: str
    branch_exists: bool
    branch_merged: bool
    worktree_exists: bool
    worktree_path: str | None
    artifacts_in_main: bool
    artifacts_in_worktree: bool


class CurrentFeatureDetected(TypedDict):
    """current_feature block when detection succeeds."""

    detected: bool  # True
    name: str
    state: str
    branch_exists: bool
    branch_merged: bool
    worktree_exists: bool
    worktree_path: str | None
    artifacts_in_main: bool
    artifacts_in_worktree: bool


class CurrentFeatureNotDetected(TypedDict):
    """current_feature block when detection fails."""

    detected: bool  # False
    error: str


class DashboardHealthInfo(TypedDict, total=False):
    """Dashboard health section of the diagnostics response."""

    metadata_exists: bool
    can_start: bool | None
    startup_test: str | None
    url: str
    port: int
    pid: int | None
    has_pid: bool
    responding: bool
    parse_error: str
    test_url: str
    test_port: int
    startup_error: str


class DiagnosticsResponse(TypedDict):
    """Response from ``GET /api/diagnostics``."""

    project_path: str
    current_working_directory: str
    git_branch: str | None
    in_worktree: bool
    worktrees_exist: bool
    active_mission: str | None
    file_integrity: FileIntegrity
    worktree_overview: dict[str, Any]
    current_feature: CurrentFeatureDetected | CurrentFeatureNotDetected
    all_features: list[DiagnosticsFeatureStatus]
    dashboard_health: DashboardHealthInfo
    observations: list[str]
    issues: list[str]


class DiagnosticsErrorResponse(TypedDict):
    """Error variant of the diagnostics response (HTTP 500)."""

    error: str
    traceback: str


# ---------------------------------------------------------------------------
# Public API – convenient re-export tuple for import * and contract tests
# ---------------------------------------------------------------------------

__all__ = [
    "ArtifactDirectoryFile",
    "ArtifactDirectoryResponse",
    "ArtifactInfo",
    "CurrentFeatureDetected",
    "CurrentFeatureNotDetected",
    "DashboardHealthInfo",
    "DecayWatchTileResponse",
    "DiagnosticsErrorResponse",
    "DiagnosticsFeatureStatus",
    "DiagnosticsResponse",
    "ErrorResponse",
    "FeatureItem",
    "FeaturesListErrorResponse",
    "FeaturesListResponse",
    "FileIntegrity",
    "GlossaryHealthResponse",
    "GlossaryTermRecord",
    "HealthResponse",
    "KanbanResponse",
    "KanbanStats",
    "KanbanTaskData",
    "MissionContext",
    "MissionRecord",
    "ResearchArtifact",
    "ResearchResponse",
    "WorkflowStatus",
    "WorktreeInfo",
]
