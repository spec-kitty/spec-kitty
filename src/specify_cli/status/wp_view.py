"""Canonical WP-view reconstruction reader (IC-07 / FR-012).

ONE reader — :func:`reconstruct_wp_view` — that assembles a work package's
runtime view from TWO distinct, never-conflated sources:

* ``resolved`` — the *actual* runtime state, event-sourced from the reduced
  snapshot (:func:`specify_cli.status.reducer.wp_snapshot_state`): ``lane``,
  ``agent``, ``assignee``, ``subtasks``, ``review``, and the resolved-binding
  actuals ``role`` / ``agent_profile`` (+ ``agent_profile_version``) / ``model``
  / ``provider``.
* ``authored`` — the *recommended* assignment, read from the WP frontmatter:
  authored ``role`` / ``agent_profile`` / ``model`` plus the static planning
  fields (``subtasks`` / ``owned_files`` / ``dependencies`` /
  ``requirement_refs``).

The single load-bearing rule (C-008 / INV-7): **authored intent and resolved
actual are NEVER conflated.** A WP with no resolved-binding slots yields a
populated ``authored`` group and an *empty* ``resolved`` group — the authored
value is NEVER returned inside the ``resolved`` group (no masquerade). This is
the split-brain the mission exists to close: three consumers (dashboard scanner,
``agent tasks status`` board, :class:`~specify_cli.task_utils.support.WorkPackage`)
previously hand-rolled their own snapshot gate; they now all reconstruct through
this single reader (SC-007), so they can never disagree.

The reader is **unconditional** against the snapshot (IC-03): it always reads
through ``wp_snapshot_state``; there is no phase-flag branch. Absent runtime
state degrades every ``resolved`` field to its empty value (tolerate-absent).

**Scope: identity/runtime fields ONLY.** Presentation concerns owned by the
dashboard consumer (``title`` regex, ``prompt_markdown``, ``prompt_path``) are
NOT produced here — pulling them into the reader would regress the dashboard
(they would be swallowed). The reader's contract is identity/runtime only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from specify_cli.core.subtask_rows import SubtaskRosterEntryError, normalize_authored_subtask_roster
from specify_cli.core.wp_task_files import match_wp_task_files, non_regular

from .reducer import wp_snapshot_state
from .resolved_binding import (
    RESOLVED_MODEL_ABSENT,
    RESOLVED_PROFILE_ABSENT,
    RESOLVED_PROFILE_VERSION_ABSENT,
    RESOLVED_PROVIDER_ABSENT,
)
from .wp_metadata import WPMetadata

__all__ = [
    "AuthoredGroup",
    "ResolvedGroup",
    "WPView",
    "reconstruct_wp_view",
]

@dataclass(frozen=True)
class ResolvedGroup:
    """The *actual* runtime state, event-sourced from the reduced snapshot.

    Every field degrades to its empty value (``None`` / empty mapping) when the
    snapshot carries no runtime state for the WP (tolerate-absent, INV-7) — the
    authored recommendation is NEVER substituted here.

    ``model`` normalizes the internal :data:`RESOLVED_MODEL_ABSENT` sentinel (a
    pick-up ran but resolved no model) to ``None`` so the sentinel string never
    leaks to a display consumer; the reduce layer keeps the three-way
    distinction it needs (latest-wins overwrite of a stale model).
    """

    lane: str | None = None
    agent: str | None = None
    assignee: str | None = None
    shell_pid: str | None = None
    shell_pid_created_at: str | None = None
    subtasks: Mapping[str, str] = field(default_factory=dict)
    review: Mapping[str, Any] | None = None
    role: str | None = None
    agent_profile: str | None = None
    agent_profile_version: str | None = None
    model: str | None = None
    provider: str | None = None

    @property
    def is_empty(self) -> bool:
        """True when the snapshot carried no runtime state for the WP.

        Lets a consumer branch "show resolved else fall back to authored" at the
        *presentation* boundary without ever conflating the two groups in the
        data model.
        """
        return (
            self.lane is None
            and self.agent is None
            and self.assignee is None
            and self.shell_pid is None
            and self.shell_pid_created_at is None
            and not self.subtasks
            and self.review is None
            and self.role is None
            and self.agent_profile is None
            and self.agent_profile_version is None
            and self.model is None
            and self.provider is None
        )


@dataclass(frozen=True)
class AuthoredGroup:
    """The *recommended* assignment, read from WP frontmatter (static).

    Always populated from frontmatter — distinct from the resolved actual
    (C-008). A consumer that needs "what was intended" reads here; "what ran"
    reads :class:`ResolvedGroup`. Reads only frontmatter-canonical fields
    (``role`` / ``agent_profile`` / ``model`` and the static planning lists),
    none of which :func:`read_wp_frontmatter` re-points to the snapshot, so the
    authored values are never silently snapshot-sourced.
    """

    role: str | None = None
    agent_profile: str | None = None
    model: str | None = None
    subtasks: tuple[str, ...] = ()
    owned_files: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class WPView:
    """A reconstructed work-package view: resolved actual + authored recommended.

    The two groups are separate attributes on the return type precisely so no
    consumer can accidentally treat authored intent as "what ran" (C-008).
    """

    wp_id: str
    resolved: ResolvedGroup
    authored: AuthoredGroup


def _opt_str(value: Any) -> str | None:
    """Coerce a snapshot slot to ``str | None`` — ``None`` and ``""`` stay empty."""
    if value is None:
        return None
    text = str(value)
    return text or None


def _resolved_group(feature_dir: Path, wp_id: str) -> ResolvedGroup:
    """Assemble the resolved (event-sourced) group for *wp_id*.

    Unconditional against the snapshot (no phase-flag branch): reads the shared
    ``wp_snapshot_state`` accessor and degrades every field to empty when there
    is no reduced entry (``None``) — the authored value is never substituted.
    """
    return resolved_group_from_state(wp_snapshot_state(feature_dir, wp_id))


def resolved_group_from_state(state: Mapping[str, Any] | None) -> ResolvedGroup:
    """The resolved group from one reduced WP state (``snapshot.work_packages[wp_id]``).

    For a reader that already reduced the log through the status read door
    (``read_status_stream`` + ``reduce``), so a ref-sourced surface needs no
    directory (#7335). ``None`` (no reduced entry) yields an empty group.
    """
    if state is None:
        return ResolvedGroup()

    subtasks_raw = state.get("subtasks") or {}
    subtasks = {str(key): str(value) for key, value in subtasks_raw.items()}

    review_raw = state.get("review")
    review = review_raw if isinstance(review_raw, Mapping) else None

    def normalized(slot: str, absent: str) -> str | None:
        value = _opt_str(state.get(slot))
        return None if value == absent else value

    return ResolvedGroup(
        lane=_opt_str(state.get("lane")),
        agent=_opt_str(state.get("agent")),
        assignee=_opt_str(state.get("assignee")),
        shell_pid=_opt_str(state.get("shell_pid")),
        shell_pid_created_at=_opt_str(state.get("shell_pid_created_at")),
        subtasks=subtasks,
        review=review,
        role=_opt_str(state.get("role")),
        agent_profile=normalized("agent_profile", RESOLVED_PROFILE_ABSENT),
        agent_profile_version=normalized(
            "agent_profile_version", RESOLVED_PROFILE_VERSION_ABSENT
        ),
        model=normalized("model", RESOLVED_MODEL_ABSENT),
        provider=normalized("provider", RESOLVED_PROVIDER_ABSENT),
    )


def _authored_group(metadata: WPMetadata | None) -> AuthoredGroup:
    """Assemble the authored (frontmatter) group from parsed WP metadata.

    Pure transform of a :class:`WPMetadata` — stable inputs/outputs, directly
    testable. ``None`` (no locatable/parsable WP file) yields an empty group so
    the reader never crashes on a WP with no frontmatter. Likewise a
    ``subtasks:`` entry that is not a task id (#7442) yields an empty authored
    subtask list while the other authored fields stay populated: the view only
    reports, and the gates (``for_review``, ``mark-status``) refuse such a roster.
    """
    if metadata is None:
        return AuthoredGroup()
    try:
        subtasks = tuple(normalize_authored_subtask_roster(metadata.subtasks))
    except SubtaskRosterEntryError:
        subtasks = ()
    return AuthoredGroup(
        role=metadata.role,
        agent_profile=metadata.agent_profile,
        model=metadata.model,
        subtasks=subtasks,
        owned_files=tuple(metadata.owned_files),
        dependencies=tuple(metadata.dependencies),
        requirement_refs=tuple(metadata.requirement_refs),
    )


def _locate_wp_metadata(feature_dir: Path, wp_id: str) -> WPMetadata | None:
    """Locate and parse the WP frontmatter for *wp_id* under ``feature_dir/tasks``.

    Reads the **raw** frontmatter (via ``FrontmatterManager``), NOT
    :func:`~specify_cli.status.wp_metadata.read_wp_frontmatter` — deliberately:
    ``read_wp_frontmatter`` unconditionally re-points the runtime fields
    (``agent``/``assignee``/``shell_pid``) to the snapshot, which the authored
    group must never surface, and it triggers a second reduce the reader does not
    need (``_resolved_group`` already owns the one snapshot read). The authored
    group reads only frontmatter-canonical fields, so the raw parse is both
    correct and cheaper.

    Returns ``None`` when the tasks dir is absent, no file matches, the match is
    ambiguous or not a regular file, or it is unparsable — the reader tolerates a
    missing authored source rather than raising. Matching is the one rule in
    :mod:`specify_cli.core.wp_task_files` (#7443).
    """
    matches = match_wp_task_files(feature_dir, wp_id)
    if len(matches) != 1 or non_regular(matches):
        return None

    from specify_cli.frontmatter import FrontmatterManager

    try:
        frontmatter_dict, _body = FrontmatterManager().read(matches[0])
        return WPMetadata.model_validate(frontmatter_dict, strict=False)
    except Exception:
        return None


def reconstruct_wp_view(
    feature_dir: Path,
    wp_id: str,
    *,
    metadata: WPMetadata | None = None,
) -> WPView:
    """Reconstruct the canonical view for *wp_id* — resolved actual + authored.

    The single assembly point for every WP-view consumer (SC-007). Resolved
    runtime state is event-sourced from *feature_dir*'s snapshot (the caller
    passes whichever surface carries the event log — the primary checkout for
    single-branch missions, the coordination surface for coord topologies).

    Args:
        feature_dir: The mission directory whose ``status.events.jsonl`` /
            reduced snapshot supplies the resolved actual.
        wp_id: Canonical WP id (e.g. ``"WP04"``).
        metadata: Optional pre-parsed WP frontmatter for the authored group. A
            consumer that already parsed the WP file (e.g. the dashboard scanner
            reading a planning-surface prompt under coord topology) passes it to
            avoid a re-read and to source authored intent from the correct
            surface; when ``None`` the reader locates the WP file under
            ``feature_dir/tasks`` itself. Only frontmatter-canonical fields are
            read from it, so a snapshot-re-pointed ``agent``/``assignee`` on the
            passed metadata never contaminates the authored group.

    Returns:
        A :class:`WPView` whose ``resolved`` and ``authored`` groups are
        distinct — a WP with no resolved-binding slots has a populated
        ``authored`` group and an empty ``resolved`` group (no masquerade).
    """
    authored_metadata = metadata if metadata is not None else _locate_wp_metadata(feature_dir, wp_id)
    return WPView(
        wp_id=wp_id,
        resolved=_resolved_group(feature_dir, wp_id),
        authored=_authored_group(authored_metadata),
    )
