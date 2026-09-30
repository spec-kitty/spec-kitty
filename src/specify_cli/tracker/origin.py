"""Service-layer orchestration for ticket-first mission origin binding.

Provides :func:`bind_mission_origin`, which persists an origin binding
(SaaS-first, local-second). It is consumed by ``tracker/origin_consumer.py``
after ``spec-kitty mission create --from-ticket`` fetches the ticket.

All errors surface as :class:`OriginBindingError`.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from pathlib import Path
from typing import Any

from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed, locate_project_root
from specify_cli.mission_metadata import set_origin_ticket
from specify_cli.tracker.config import TrackerProjectConfig, load_tracker_config
from specify_cli.tracker.origin_models import OriginCandidate
from specify_cli.tracker.saas_client import SaaSTrackerClient, SaaSTrackerClientError


# Re-export dataclasses for public API surface
__all__ = [
    "OriginBindingError",
    "OriginCandidate",
    "bind_mission_origin",
]


class OriginBindingError(RuntimeError):
    """Raised when origin binding operations fail."""


# ---------------------------------------------------------------------------
# bind_mission_origin
# ---------------------------------------------------------------------------


def bind_mission_origin(
    feature_dir: Path,
    candidate: OriginCandidate,
    provider: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    *,
    client: SaaSTrackerClient | None = None,
) -> tuple[dict[str, Any], bool]:
    """Bind an origin ticket to a mission. SaaS-first, local-second.

    **CRITICAL**: The SaaS call is the authoritative write. If it fails,
    no local state is written. The service MUST NOT inspect local
    meta.json to short-circuit the SaaS bind.

    Parameters
    ----------
    feature_dir:
        Path to the feature directory containing ``meta.json``.
    candidate:
        The confirmed origin candidate.
    provider:
        Tracker provider (``"jira"`` or ``"linear"``).
    resource_type:
        Resource type (e.g. ``"linear_team"``, ``"jira_project"``).
    resource_id:
        Resource identifier.
    client:
        Optional injected client for testability.

    Returns
    -------
    tuple[dict, bool]
        (Updated meta.json contents, whether MissionOriginBound event was emitted).

    Raises
    ------
    OriginBindingError
        On SaaS failure, missing metadata, or write failure.
    """
    # 1. Load meta.json to get mission identity (needed for SaaS call)
    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        raise OriginBindingError(f"Failed to load meta.json from {feature_dir}: {exc}") from exc
    if meta is None:
        raise OriginBindingError(f"No meta.json found in {feature_dir}")
    mission_id = str(meta.get("mission_id") or "").strip()
    mission_slug = meta.get("mission_slug")
    if not mission_id:
        raise OriginBindingError(f"meta.json in {feature_dir} missing mission_id")
    if not mission_slug:
        raise OriginBindingError(f"meta.json in {feature_dir} missing mission_slug")

    # 2. Resolve routing + local resource context from tracker config
    #    Walk up from feature_dir to find .kittify/config.yaml
    repo_root = _resolve_repo_root(feature_dir)
    # #3030 FR-029: the client is told which project owns this mission, resolved
    # from the mission's own ``feature_dir`` — never from the process's cwd. This
    # is the non-interactive reach (mission creation → consume_pending_origin →
    # here), so nothing downstream would have prompted an operator to notice.
    actual_client = client or SaaSTrackerClient(project_root=repo_root)
    tracker_config = _resolve_tracker_config_for_origin(
        repo_root=repo_root,
        provider=provider,
        client=actual_client,
    )
    project_slug = tracker_config.project_slug
    binding_ref = tracker_config.binding_ref
    resolved_resource_type, resolved_resource_id = _resolve_origin_resource_context(
        provider=provider,
        tracker_config=tracker_config,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    # 3. Call SaaS FIRST — if this fails, STOP. No local state written.
    try:
        actual_client.bind_mission_origin(
            provider,
            project_slug,
            binding_ref=binding_ref,
            mission_id=mission_id,
            mission_slug=mission_slug,
            external_issue_id=candidate.external_issue_id,
            external_issue_key=candidate.external_issue_key,
            external_issue_url=candidate.url,
            title=candidate.title,
            external_status=candidate.status,
        )
    except SaaSTrackerClientError as exc:
        raise OriginBindingError(str(exc)) from exc

    # 4. Build origin_ticket dict from candidate + routing context
    origin_ticket: dict[str, Any] = {
        "provider": provider,
        "resource_type": resolved_resource_type,
        "resource_id": resolved_resource_id,
        "external_issue_id": candidate.external_issue_id,
        "external_issue_key": candidate.external_issue_key,
        "external_issue_url": candidate.url,
        "title": candidate.title,
    }

    # 5. Write to meta.json (local-second)
    updated_meta = set_origin_ticket(feature_dir, origin_ticket)

    # 6. Return the updated meta dict (the MissionOriginBound SaaS emission
    # was removed with the sync transport, issue #5).
    return updated_meta, False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_repo_root(feature_dir: Path) -> Path:
    """Walk up from feature_dir to find the repo root (.kittify/ parent)."""
    resolved = feature_dir.resolve()

    for parent in [resolved.parent, *resolved.parents]:
        if parent.name == KITTY_SPECS_DIR:
            repo_root = parent.parent
            if (repo_root / ".kittify").is_dir():
                return repo_root

    # Feature directories also contain a local ``.kittify`` directory, so
    # prefer the real project root resolver before falling back to heuristics.
    project_root = locate_project_root(resolved)
    if project_root is not None:
        return project_root

    # Fall back: assume feature_dir is inside kitty-specs/<slug>/
    # so repo_root is two levels up
    return resolved.parent.parent


def _project_identity_payload(repo_root: Path) -> dict[str, Any]:
    """Build the SaaS project-identity payload for bind resolution calls.

    Resolves identity WITHOUT persisting (#2263, FR-002/FR-003): this payload is sent
    to the SaaS bind-resolve/bind-validate endpoint to *look up* hosted routing, not to
    locally persist identity. Origin binding persists its result to ``meta.json``
    (``set_origin_ticket``), never to ``.kittify/config.yaml`` via this call, so the
    identity read here must not dirty the working tree.
    """
    from specify_cli.identity.project import resolve_identity

    identity = resolve_identity(repo_root)
    if (
        identity.project_uuid is None
        or not identity.project_slug
        or not identity.node_id
        or not identity.build_id
    ):
        raise OriginBindingError(
            "Current checkout has no complete project identity. Run `spec-kitty init` first."
        )
    return {
        "uuid": str(identity.project_uuid),
        "slug": identity.project_slug,
        "node_id": identity.node_id,
        "repo_slug": identity.repo_slug,
        "build_id": identity.build_id,
    }


def _resolve_tracker_config_for_origin(
    *,
    repo_root: Path,
    provider: str,
    client: SaaSTrackerClient,
) -> TrackerProjectConfig:
    """Resolve hosted routing for mission-origin binding.

    Preference order:
    1. Local tracker config when it already routes to the requested provider.
    2. Hosted bind-resolve/bind-validate for the current project identity.

    This lets ticket-origin flows work from repos that are remotely mapped in
    SaaS but have not yet persisted a local ``tracker:`` block in
    ``.kittify/config.yaml``.
    """
    tracker_config = load_tracker_config(repo_root)
    if tracker_config.provider and tracker_config.provider != provider:
        raise OriginBindingError(
            f"This repo is bound to '{tracker_config.provider}', not '{provider}'. "
            f"Run `spec-kitty tracker bind --provider {provider}`."
        )
    if tracker_config.provider == provider and (
        tracker_config.binding_ref or tracker_config.project_slug
    ):
        return tracker_config

    project_identity = _project_identity_payload(repo_root)
    try:
        resolution = client.bind_resolve(provider, project_identity)
    except SaaSTrackerClientError as exc:
        raise OriginBindingError(str(exc)) from exc

    binding_ref = resolution.get("binding_ref")
    project_slug = resolution.get("project_slug")
    if resolution.get("match_type") != "exact" or not (binding_ref or project_slug):
        raise OriginBindingError("No tracker bound. Run `spec-kitty tracker bind` first.")

    provider_context: dict[str, str] | None = None
    display_label = resolution.get("display_label")
    if binding_ref:
        try:
            validation = client.bind_validate(provider, binding_ref, project_identity)
        except SaaSTrackerClientError as exc:
            raise OriginBindingError(str(exc)) from exc
        validation_context = validation.get("provider_context")
        if isinstance(validation_context, dict):
            provider_context = {
                str(key): str(value)
                for key, value in validation_context.items()
            }
        if validation.get("display_label"):
            display_label = validation["display_label"]

    return TrackerProjectConfig(
        provider=provider,
        binding_ref=str(binding_ref).strip() if binding_ref else None,
        project_slug=str(project_slug).strip() if project_slug else None,
        display_label=str(display_label).strip() if isinstance(display_label, str) and display_label.strip() else None,
        provider_context=provider_context,
    )


def _resolve_origin_resource_context(
    *,
    provider: str,
    tracker_config: TrackerProjectConfig,
    resource_type: str | None,
    resource_id: str | None,
) -> tuple[str, str]:
    """Resolve local origin_ticket routing context.

    The authoritative SaaS bind call routes by ``binding_ref`` or ``project_slug``.
    ``resource_type`` / ``resource_id`` are kept locally for provenance and may need
    to be derived from the persisted tracker config when the caller does not have an
    explicit discovery response in hand.
    """
    explicit_type = (resource_type or "").strip()
    explicit_id = (resource_id or "").strip()
    if explicit_type and explicit_id:
        return explicit_type, explicit_id

    provider_context = tracker_config.provider_context or {}

    if provider == "linear":
        return (
            explicit_type or "linear_team",
            explicit_id
            or provider_context.get("workspace_id")
            or provider_context.get("team_id")
            or tracker_config.binding_ref
            or tracker_config.project_slug
            or "",
        )

    if provider == "jira":
        return (
            explicit_type or "jira_project",
            explicit_id
            or provider_context.get("project_key")
            or provider_context.get("key")
            or tracker_config.binding_ref
            or tracker_config.project_slug
            or "",
        )

    if provider == "github":
        return (
            explicit_type or "github_repo",
            explicit_id
            or provider_context.get("repository")
            or provider_context.get("repo")
            or tracker_config.binding_ref
            or tracker_config.project_slug
            or "",
        )

    if provider == "gitlab":
        return (
            explicit_type or "gitlab_project",
            explicit_id
            or provider_context.get("project_path")
            or provider_context.get("project_id")
            or tracker_config.binding_ref
            or tracker_config.project_slug
            or "",
        )

    return explicit_type, explicit_id
