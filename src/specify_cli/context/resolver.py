"""Context resolution: raw arguments to persisted MissionContext.

The resolver reads identity from project metadata and WP frontmatter.
It does NOT use branch names, environment variables, or directory walking.
Both ``wp_code`` and ``mission_slug`` are REQUIRED -- there is no scanning,
no heuristic fallback, and no single-feature auto-detection.
"""

from __future__ import annotations

from pathlib import Path

from ulid import ULID
from ruamel.yaml import YAML

from mission_runtime import ActionContextError
from specify_cli.context.errors import (
    FeatureNotFoundError,
    MissingArgumentError,
    MissingIdentityError,
    WorkPackageNotFoundError,
)
from charter.activation.mission_type_key import read_mission_type
from specify_cli.context.models import MissionContext
from specify_cli.context.store import load_context as _load_context
from specify_cli.context.store import save_context
from specify_cli.core.git_ops import resolve_primary_branch
from specify_cli.core.paths import load_meta_fail_closed, read_target_branch_from_meta
from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.persistence import require_lanes_json
from specify_cli.mission_metadata import mission_identity_fields
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission
from specify_cli.status import WPMetadata, read_authored_wp_frontmatter


def _generate_token() -> str:
    """Generate an opaque context token: ctx- prefix + ULID."""
    return f"ctx-{ULID()}"


def _read_project_uuid(repo_root: Path) -> str:
    """Read project_uuid from .kittify/config.yaml."""
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        msg = f"Project config not found at {config_path}. Run `spec-kitty init` to initialize the project."
        raise MissingIdentityError(msg)

    yaml = YAML()
    data = yaml.load(config_path.read_text(encoding="utf-8"))

    project_section = data.get("project", {}) if data else {}
    uuid_val = project_section.get("uuid")
    if not uuid_val:
        msg = "project.uuid not found in .kittify/config.yaml. Run `spec-kitty init` to assign a project identity."
        raise MissingIdentityError(msg)
    return str(uuid_val)


def _read_meta_json(feature_dir: Path, repo_root: Path) -> dict[str, str]:
    """Read mission identity and target_branch from meta.json.

    Legacy missions authored before the identity backfill may lack
    ``mission_id``. In that case, fall back to ``feature_dir.name`` so
    context-bound commands can still operate deterministically on a
    single explicit mission directory.
    """
    # FR-005 / post-#2091 + FR-007 / #3162: this site hard-fails on a missing
    # meta.json (MissingIdentityError) and propagates a malformed-JSON failure
    # (now the typed MissionMetaReadError via the ONE fail-closed reader)
    # rather than silently tolerating it -- allow_missing=True or
    # on_malformed="empty" would MASK that guard and silently re-introduce the
    # removed legacy tolerance. The fail-closed reader returns None only for a
    # missing file, which maps to the same MissingIdentityError diagnostic.
    data = load_meta_fail_closed(feature_dir)
    if data is None:
        msg = f"meta.json not found at {feature_dir / 'meta.json'}."
        raise MissingIdentityError(msg)

    mission_id = data.get("mission_id") or feature_dir.name
    # FR-008 / #2139: delegate to the single read_target_branch_from_meta
    # authority instead of re-embedding a local "main" default here. The
    # authority itself owns the field-absent-vs-corrupt distinction; we only
    # apply the documented primary-branch fallback when the field is
    # genuinely absent (None), matching resolve_target_branch/
    # get_feature_target_branch in core/git_ops.py and core/paths.py.
    target_branch = read_target_branch_from_meta(feature_dir)
    if target_branch is None:
        target_branch = resolve_primary_branch(repo_root)

    identity = mission_identity_fields(
        str(data.get("mission_slug") or data.get("slug") or feature_dir.name),
        str(data.get("mission_number") or data.get("feature_number") or "").strip() or None,
        read_mission_type(data),  # rc3 M5 (FR-002): canonical field only; legacy retired
    )

    fields = {
        "mission_id": mission_id,
        "target_branch": target_branch,
        "mission_number": identity["mission_number"],
        "mission_type": identity["mission_type"],
    }
    # WP08 (#5100): carry the protected-target mint through to resolve_context
    # (this hydrated dict otherwise drops every field it does not name).
    raw_mission_branch = data.get("mission_branch")
    if isinstance(raw_mission_branch, str) and raw_mission_branch:
        fields["mission_branch"] = raw_mission_branch
    return fields


def _read_wp_metadata(feature_dir: Path, wp_code: str) -> WPMetadata:
    """Read WP frontmatter as a typed WPMetadata model.

    Scans tasks/ directory for a file matching the wp_code pattern
    (e.g., WP01-*.md or WP01.md), then parses the authored metadata only.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        msg = f"tasks/ directory not found at {tasks_dir}."
        raise WorkPackageNotFoundError(msg)

    # Find matching WP file: WP01-*.md or WP01.md
    candidates = list(tasks_dir.glob(f"{wp_code}-*.md")) + list(tasks_dir.glob(f"{wp_code}.md"))
    if not candidates:
        msg = f"No task file found for '{wp_code}' in {tasks_dir}. Expected a file matching {wp_code}-*.md or {wp_code}.md."
        raise WorkPackageNotFoundError(msg)

    wp_path = candidates[0]
    try:
        metadata, _body = read_authored_wp_frontmatter(wp_path)
    except Exception as exc:
        msg = f"WP file {wp_path} has invalid or missing frontmatter: {exc}"
        raise WorkPackageNotFoundError(msg) from exc

    return metadata


def resolve_context(
    wp_code: str,
    mission_slug: str,
    agent: str,
    repo_root: Path,
) -> MissionContext:
    """Resolve a MissionContext from explicit arguments.

    Both ``wp_code`` and ``mission_slug`` are REQUIRED. This function
    does NOT scan, auto-detect, or fall back to heuristics.

    Args:
        wp_code: Work package display alias (e.g., "WP01").
        mission_slug: Mission handle (full slug such as
            "057-canonical-context-architecture-cleanup", bare mid8, or
            numeric prefix). Canonicalized to the resolved mission
            directory name before anything is composed or persisted (F-001).
        agent: Name of the agent creating this context.
        repo_root: Absolute path to the repository root.

    Returns:
        A persisted MissionContext.

    Raises:
        MissingArgumentError: If wp_code or mission_slug is empty.
        MissingIdentityError: If project_uuid or mission_id is not assigned.
        FeatureNotFoundError: If the feature slug doesn't match a kitty-specs/ dir.
        WorkPackageNotFoundError: If the wp_code is not found in tasks/.
    """
    if not wp_code:
        msg = "wp_code is required. Provide the work package code (e.g., --wp WP01). No scanning or auto-detection is performed."
        raise MissingArgumentError(msg)

    if not mission_slug:
        msg = (
            "mission_slug is required. Provide the feature slug "
            "(e.g., --mission 057-canonical-context-architecture-cleanup). "
            "No scanning or auto-detection is performed."
        )
        raise MissingArgumentError(msg)

    # 1. Read project_uuid
    project_uuid = _read_project_uuid(repo_root)

    # 2. Locate feature directory — primary-anchor pattern (implement.py:1018).
    # ``resolve_feature_dir_for_mission`` is coord-aware: it resolves the
    # canonical directory for F-001 slug canonicalization. Reads that follow
    # (meta.json, WP frontmatter, lanes.json) are PRIMARY-partition artifacts
    # and are routed through ``resolve_planning_read_dir`` so they are
    # topology-blind (C-007: no consolidation of the coord-aware resolver).
    # C-001 honesty note (WP06): this call stays on the kind-blind primitive
    # by design — it exists to canonicalize the caller's HANDLE (bare mid8 /
    # numeric prefix / full slug) to a directory NAME, not to read a
    # PRIMARY-partition artifact off the returned dir. ``_canon_dir`` itself
    # is never opened for content; every actual read below is separately
    # kind-routed through ``resolve_planning_read_dir``. Re-routing this site
    # too would over-claim a single funnel over the ``*_feature_dir_for_mission``
    # primitives beyond what the gate enforces.
    try:
        _canon_dir = resolve_feature_dir_for_mission(repo_root, mission_slug)
    except ActionContextError as exc:
        # FR-001 / M1 (T038): preserve the resolver's typed read-path signal
        # instead of flattening it into "Check that the mission slug is correct."
        # The resolver produces a precise code (e.g. COORDINATION_BRANCH_DELETED /
        # STATUS_READ_PATH_NOT_FOUND) plus the real read-path remediation; a
        # generic "check the slug" mis-routes the operator (the mission is not
        # missing — its read path is broken). Mirror the agent/context.py
        # translation: carry ``exc.code`` + the resolver message through verbatim.
        msg = (
            f"[{exc.code}] Read path could not be resolved for mission "
            f"'{mission_slug}'. {exc}"
        )
        raise FeatureNotFoundError(msg) from exc

    # F-001 boundary canonicalization (the finalize-tasks pattern): the
    # caller-supplied ``mission_slug`` is an operator HANDLE (full slug, bare
    # mid8, numeric prefix). The directory resolution above already
    # canonicalized it, so key everything composed and persisted downstream —
    # the lane-branch ``authoritative_ref`` (``lane_branch_name``) and the
    # MissionContext token fields — by the resolved directory name, never the
    # raw handle. A raw mid8 here composes a wrong-but-plausible
    # ``kitty/mission-<mid8>-…`` ref and persists a raw ``mission_slug``.
    mission_slug = _canon_dir.name

    # Route all PRIMARY-partition reads (meta.json, WP frontmatter) through the
    # seam so they always resolve to the primary checkout under coord topology
    # (coord husk carries STATUS events only, not planning artifacts).
    # read-side-placement-seam-migration WP07: routed through
    # ``placement_seam`` (fail-loud on a deleted-coord mismatch, NFR-002)
    # instead of the kind-blind ``resolve_planning_read_dir`` — a single
    # anchor also used for the immediately-following ``meta.json`` read (both
    # WORK_PACKAGE_TASK and PRIMARY_METADATA are PRIMARY-partition and resolve
    # to the identical dir).
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    if not feature_dir.exists():
        msg = f"Feature directory not found: {feature_dir}. Check that '{mission_slug}' is the correct feature slug."
        raise FeatureNotFoundError(msg)

    # 3. Read meta.json
    meta = _read_meta_json(feature_dir, repo_root)

    # 4. Read WP frontmatter as typed WPMetadata
    wp_meta = _read_wp_metadata(feature_dir, wp_code)

    # Extract fields from typed metadata
    work_package_id = wp_meta.work_package_id or wp_code
    execution_mode = wp_meta.execution_mode or "code_change"
    owned_files: tuple[str, ...] = tuple(wp_meta.owned_files)
    dependencies = list(wp_meta.dependencies)

    # Compute authoritative_ref: uniform lane lookup for ALL WPs (including planning_artifact).
    # After T010, planning_artifact WPs are assigned to the "lane-planning" lane in lanes.json.
    # lane_branch_name() returns target_branch for lane-planning (T011).
    # lanes.json is LANE_STATE (PRIMARY-partition) — use its truthful kind so a
    # future LANE_STATE re-partition does not silently misroute.
    # OUT of FR-008 / #2139 routing (by design, per D-03/squad triage): this is
    # a hard-KeyError read of the already-hydrated `meta` dict built by
    # `_read_meta_json` above (which itself now routes through the
    # read_target_branch_from_meta authority and always populates the key) --
    # a construction-time dataclass-hydration read, not a meta.json field read.
    target_branch = meta["target_branch"]
    # read-side-placement-seam-migration WP07: routed through
    # ``placement_seam`` (fail-loud on a deleted-coord mismatch, NFR-002)
    # instead of the kind-blind ``resolve_planning_read_dir``.
    _lanes_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.LANE_STATE
    )
    lane = require_lanes_json(_lanes_dir).lane_for_wp(wp_code)
    if lane is None:
        msg = (
            f"WP {wp_code!r} has no lane assignment in {_lanes_dir / 'lanes.json'}. "
            f"Run 'spec-kitty agent mission finalize-tasks --mission {mission_slug}' "
            f"to compute lanes."
        )
        raise MissingIdentityError(msg)
    # WP08 (#5100 FR-007/012, IC-05): a protected-target single_branch
    # mission's mint records `meta.mission_branch`; `lane_branch_name`'s
    # `lane-planning` arm otherwise returns `target_branch` verbatim, which
    # would name the PROTECTED branch here. Route through it only for the
    # composer, never touching `context.target_branch` below (that field
    # stays the mission's real target).
    raw_mission_branch = meta.get("mission_branch")
    authoritative_target = str(raw_mission_branch) if isinstance(raw_mission_branch, str) and raw_mission_branch else target_branch
    authoritative_ref = lane_branch_name(
        mission_slug,
        lane.lane_id,
        target_branch=authoritative_target,
    )

    # Compute dependency_mode
    dependency_mode = "chained" if dependencies else "independent"

    # Generate opaque token
    token = _generate_token()
    now = now_utc_iso()

    # Build context
    context = MissionContext(
        token=token,
        project_uuid=project_uuid,
        mission_id=meta["mission_id"],
        work_package_id=work_package_id,
        wp_code=wp_code,
        mission_slug=mission_slug,
        # OUT of FR-008 / #2139 routing (same rationale as above): hard-KeyError
        # hydration of the already-resolved `meta` dict, not a raw meta.json read.
        target_branch=meta["target_branch"],
        authoritative_repo=str(repo_root),
        authoritative_ref=authoritative_ref,
        owned_files=owned_files,
        execution_mode=execution_mode,
        dependency_mode=dependency_mode,
        created_at=now,
        created_by=agent,
        mission_number=meta["mission_number"],
        mission_type=meta["mission_type"],
    )

    # Persist
    save_context(context, repo_root)

    return context


def resolve_or_load(
    token: str | None,
    wp_code: str | None,
    mission_slug: str | None,
    agent: str,
    repo_root: Path,
) -> MissionContext:
    """Main entry point: load from token or resolve from arguments.

    - If ``token`` is provided: load the persisted context directly.
    - If ``token`` is None and both ``wp_code`` and ``mission_slug`` are
      provided: resolve a new context.
    - If ``token`` is None and either ``wp_code`` or ``mission_slug`` is
      missing: raise ``MissingArgumentError``.

    This function never scans or guesses.

    Args:
        token: Existing context token, or None.
        wp_code: Work package code (e.g., "WP01"), or None.
        mission_slug: Feature slug, or None.
        agent: Agent name for new context creation.
        repo_root: Repository root path.

    Returns:
        The loaded or newly resolved MissionContext.

    Raises:
        MissingArgumentError: If neither token nor both wp_code/mission_slug
            are provided.
        ContextNotFoundError: If the token file does not exist.
        ContextCorruptedError: If the token file is invalid.
    """
    if token:
        return _load_context(token, repo_root)

    if wp_code and mission_slug:
        return resolve_context(wp_code, mission_slug, agent, repo_root)

    missing: list[str] = []
    if not wp_code:
        missing.append("--wp <WP_CODE>")
    if not mission_slug:
        missing.append("--mission <MISSION_SLUG>")

    msg = (
        f"Missing required argument(s): {', '.join(missing)}. "
        "Either provide a --context <token> or both --wp and --mission. "
        "No scanning or auto-detection is performed."
    )
    raise MissingArgumentError(msg)
