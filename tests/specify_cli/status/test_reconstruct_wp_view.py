"""Canonical WP-view reconstruction reader (WP11 / IC-07 / FR-012).

Pins the load-bearing contract for :func:`specify_cli.status.reconstruct_wp_view`
and the reroute of the three hand-rolled snapshot gates onto it:

* **SC-007 parity** — the ``agent tasks status`` board runtime fields and
  :class:`~specify_cli.task_utils.support.WorkPackage` return the SAME resolved runtime state for one WP, because they share one
  reconstruction path.
* **SC-008 latest-actual + byte-stability** — implement-claim (P1/M1) then
  review-claim (P2/M2) reconstructs the CURRENT actual (P2/M2, latest-wins) with
  0 bytes written to ``tasks/WP##.md``.
* **Tolerate-absent (INV-7)** — a never-reclaimed WP yields a populated
  ``authored`` group and an EMPTY ``resolved`` group; the authored value NEVER
  appears in the ``resolved`` group (no masquerade).

Fixtures seed synthetic event logs (the real dogfood re-seed rides ``feat``, not
this lane) via the production emit seams.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status import (
    ResolvedBinding,
    WPInnerStateDelta,
    emit_inner_state_changed,
    emit_resolved_binding,
    reconstruct_wp_view,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.models import ReviewOverride
from specify_cli.status.reducer import wp_snapshot_state
from specify_cli.status.resolved_binding import RESOLVED_MODEL_ABSENT
from specify_cli.status.store import append_event
from specify_cli.status.wp_view import (
    AuthoredGroup,
    ResolvedGroup,
    WPView,
    _authored_group,
    _resolved_group,
)
from specify_cli.status.wp_metadata import WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "001-reconstruct-view"
_MISSION_ID = "01RECONSTRUCTVIEW00000000A"
_WP_ID = "WP01"

# Authored recommendation — deliberately distinct from every resolved value so a
# masquerade (authored leaking into the resolved group) fails loudly.
_AUTHORED_ROLE = "authored-role"
_AUTHORED_PROFILE = "authored-frontmatter-profile"
_AUTHORED_MODEL = "authored-frontmatter-model"
_AUTHORED_AGENT = "authored-agent"


def _make_feature_dir(root: Path, *, status_phase: int | None = None) -> Path:
    """Minimal ``kitty-specs/<slug>`` feature dir; ``status_phase`` turns the
    consumer flag ON when set (the reader itself is unconditional)."""
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
    }
    if status_phase is not None:
        meta["status_phase"] = str(status_phase)
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return feature_dir


def _write_wp_file(feature_dir: Path) -> Path:
    """WP file whose frontmatter authors a recommendation distinct from any
    resolved value, plus static planning fields for the authored group."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{_WP_ID}-core.md"
    wp_file.write_text(
        "\n".join(
            [
                "---",
                f"work_package_id: {_WP_ID}",
                "title: Core WP",
                "execution_mode: code_change",
                f"role: {_AUTHORED_ROLE}",
                f"agent_profile: {_AUTHORED_PROFILE}",
                f"model: {_AUTHORED_MODEL}",
                f"agent: {_AUTHORED_AGENT}",
                "subtasks:",
                "- T001",
                "- T002",
                "owned_files:",
                "- src/a.py",
                "- src/b.py",
                "dependencies:",
                "- WP00",
                "requirement_refs:",
                "- FR-012",
                "---",
                "",
                "# Work Package Prompt: Core WP",
                "",
                "Body text.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return wp_file


def _seed_claim(
    feature_dir: Path,
    *,
    agent: str,
    shell_pid: int,
    at: str,
    shell_pid_created_at: str | None = None,
) -> None:
    """Append a planned→claimed transition carrying agent/shell_pid (FR-004)."""
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-claim-{at}",
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            wp_id=_WP_ID,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at=at,
            actor="fixture",
            force=True,
            execution_mode="worktree",
            policy_metadata={
                "agent": agent,
                "shell_pid": shell_pid,
                **(
                    {"shell_pid_created_at": shell_pid_created_at}
                    if shell_pid_created_at is not None
                    else {}
                ),
            },
        ),
    )


def _seed_binding(
    feature_dir: Path,
    root: Path,
    *,
    role: str,
    profile: str,
    model: str | None,
    actor: str,
    tool: str,
    profile_version: str | None = None,
    provider: str | None = None,
) -> None:
    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor=actor,
        role=role,
        binding=ResolvedBinding(
            agent_profile=profile,
            agent_profile_version=profile_version,
            model=model,
            provider=provider,
        ),
        tool=tool,
        repo_root=root,
    )


# ---------------------------------------------------------------------------
# T043 — reader assembles two DISTINCT groups
# ---------------------------------------------------------------------------


def test_reader_surfaces_resolved_and_authored_as_distinct_groups(tmp_path: Path) -> None:
    """A fully-seeded WP: resolved = the event-log actual; authored = frontmatter.
    The two groups never share a value (the split-brain the mission closes)."""
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)
    _seed_claim(
        feature_dir,
        agent="snapshot-agent",
        shell_pid=99999,
        shell_pid_created_at="2026-01-01T00:00:00+00:00",
        at="2026-01-01T00:00:01+00:00",
    )
    _seed_binding(
        feature_dir,
        tmp_path,
        role="implementer",
        profile="resolver-profile",
        model="resolver-model",
        actor="claude",
        tool="claude",
        profile_version="1.0",
        provider="resolver-provider",
    )
    emit_inner_state_changed(
        feature_dir,
        _WP_ID,
        WPInnerStateDelta(assignee="snapshot-assignee", subtasks={"T043": Lane.DONE, "T044": Lane.CLAIMED}),
        actor="fixture",
        mission_slug=_MISSION_SLUG,
        at="2026-01-01T00:00:02+00:00",
    )

    view = reconstruct_wp_view(feature_dir, _WP_ID)

    # resolved = event-sourced actual
    assert view.resolved.lane == str(Lane.CLAIMED)
    assert view.resolved.agent == "snapshot-agent"
    assert view.resolved.assignee == "snapshot-assignee"
    assert view.resolved.shell_pid == "99999"
    assert view.resolved.role == "implementer"
    assert view.resolved.agent_profile == "resolver-profile"
    assert view.resolved.model == "resolver-model"
    assert view.resolved.subtasks == {"T043": str(Lane.DONE), "T044": str(Lane.CLAIMED)}

    # authored = frontmatter recommendation (distinct)
    assert view.authored.role == _AUTHORED_ROLE
    assert view.authored.agent_profile == _AUTHORED_PROFILE
    assert view.authored.model == _AUTHORED_MODEL
    assert view.authored.owned_files == ("src/a.py", "src/b.py")
    assert view.authored.dependencies == ("WP00",)
    assert view.authored.requirement_refs == ("FR-012",)

    # C-008: no conflation — the resolved actual is never the authored string.
    assert view.resolved.role != view.authored.role
    assert view.resolved.agent_profile != view.authored.agent_profile
    assert view.resolved.model != view.authored.model


def test_reader_accepts_prepassed_metadata_without_reading_frontmatter_agent(tmp_path: Path) -> None:
    """When a consumer passes pre-parsed metadata, the authored group reads only
    frontmatter-canonical fields — a snapshot-re-pointed ``agent`` on the passed
    metadata never contaminates the authored group (it carries no ``agent``)."""
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)
    metadata = WPMetadata(work_package_id=_WP_ID, role="m-role", agent_profile="m-profile", model="m-model")

    view = reconstruct_wp_view(feature_dir, _WP_ID, metadata=metadata)

    assert view.authored.role == "m-role"
    assert view.authored.agent_profile == "m-profile"
    assert view.authored.model == "m-model"


# ---------------------------------------------------------------------------
# Tolerate-absent (INV-7) — no masquerade
# ---------------------------------------------------------------------------


def test_never_reclaimed_wp_has_empty_resolved_and_populated_authored(tmp_path: Path) -> None:
    """A WP with no event log: resolved is EMPTY, authored is populated, and the
    authored value NEVER appears in the resolved group (INV-7, no masquerade)."""
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)

    view = reconstruct_wp_view(feature_dir, _WP_ID)

    assert view.resolved.is_empty
    assert view.resolved.role is None
    assert view.resolved.agent_profile is None
    assert view.resolved.model is None
    assert view.resolved.agent is None
    assert view.resolved.lane is None
    assert view.resolved.subtasks == {}

    # authored intact
    assert view.authored.role == _AUTHORED_ROLE
    assert view.authored.agent_profile == _AUTHORED_PROFILE
    assert view.authored.model == _AUTHORED_MODEL

    # No masquerade: the authored recommendation is not in the resolved group.
    assert view.resolved.role != _AUTHORED_ROLE
    assert view.resolved.agent_profile != _AUTHORED_PROFILE
    assert view.resolved.model != _AUTHORED_MODEL


def test_reader_does_not_crash_without_tasks_dir(tmp_path: Path) -> None:
    """No event log AND no WP file: both groups empty, no crash."""
    feature_dir = _make_feature_dir(tmp_path)
    view = reconstruct_wp_view(feature_dir, _WP_ID)
    assert view.resolved.is_empty
    assert view.authored == AuthoredGroup()


# ---------------------------------------------------------------------------
# SC-008 — latest-actual across implement-claim → review-claim + byte-stability
# ---------------------------------------------------------------------------


def test_latest_actual_after_review_claim_with_zero_bytes_to_wp_file(tmp_path: Path) -> None:
    """implement-claim (P1/M1) → review-claim (P2/M2): the reconstructed resolved
    view shows the CURRENT actual (P2/M2, latest-wins); the authored recommendation
    stays readable & distinct; 0 bytes are written to ``tasks/WP01.md``."""
    feature_dir = _make_feature_dir(tmp_path)
    wp_file = _write_wp_file(feature_dir)
    before = wp_file.read_bytes()

    _seed_claim(feature_dir, agent="claude", shell_pid=111, at="2026-01-01T00:00:01+00:00")
    _seed_binding(feature_dir, tmp_path, role="implementer", profile="profile-P1", model="model-M1", actor="claude", tool="claude")
    # review-claim: a later resolved binding folds latest-wins.
    _seed_binding(feature_dir, tmp_path, role="reviewer", profile="profile-P2", model="model-M2", actor="renata", tool="renata")

    view = reconstruct_wp_view(feature_dir, _WP_ID)

    assert view.resolved.role == "reviewer"
    assert view.resolved.agent_profile == "profile-P2"
    assert view.resolved.model == "model-M2"
    # authored still readable and distinctly labeled
    assert view.authored.agent_profile == _AUTHORED_PROFILE
    assert view.authored.model == _AUTHORED_MODEL

    # INV-8: the reconstruction + the claim-seam binding emits write to the event
    # log ONLY — 0 bytes to the WP file.
    assert wp_file.read_bytes() == before


def test_resolved_model_absent_sentinel_normalized_to_none_but_binding_present(tmp_path: Path) -> None:
    """A pick-up that resolved a profile but NO model records the explicit-absent
    sentinel in the snapshot; the reader normalizes ``model`` to ``None`` (never
    leaks the sentinel) while ``role``/``agent_profile`` stay resolved — so the
    resolved group is not empty and authored is not substituted."""
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)
    _seed_binding(feature_dir, tmp_path, role="implementer", profile="resolver-profile", model=None, actor="claude", tool="claude")

    # Snapshot slot really carries the sentinel (guards against a vacuous test).
    assert (wp_snapshot_state(feature_dir, _WP_ID) or {}).get("model") == RESOLVED_MODEL_ABSENT

    view = reconstruct_wp_view(feature_dir, _WP_ID)
    assert view.resolved.model is None
    assert view.resolved.model != RESOLVED_MODEL_ABSENT
    assert view.resolved.agent_profile == "resolver-profile"
    assert view.resolved.role == "implementer"
    assert not view.resolved.is_empty  # a binding WAS resolved


# ---------------------------------------------------------------------------
# Focused unit tests on the private assembly helpers (Sonar new-code coverage)
# ---------------------------------------------------------------------------


def test_resolved_group_helper_tolerates_absent_snapshot(tmp_path: Path) -> None:
    feature_dir = _make_feature_dir(tmp_path)
    group = _resolved_group(feature_dir, _WP_ID)
    assert isinstance(group, ResolvedGroup)
    assert group.is_empty


def test_resolved_group_helper_reads_snapshot_slots(tmp_path: Path) -> None:
    feature_dir = _make_feature_dir(tmp_path)
    _seed_claim(feature_dir, agent="snap-agent", shell_pid=7, at="2026-01-01T00:00:01+00:00")
    group = _resolved_group(feature_dir, _WP_ID)
    assert group.agent == "snap-agent"
    assert group.shell_pid == "7"
    assert group.lane == str(Lane.CLAIMED)
    assert not group.is_empty


def test_authored_group_helper_is_pure_transform() -> None:
    metadata = WPMetadata(
        work_package_id=_WP_ID,
        role="r",
        agent_profile="p",
        model="m",
        subtasks=["T001"],
        owned_files=["x.py"],
        dependencies=["WP00"],
        requirement_refs=["FR-1"],
    )
    group = _authored_group(metadata)
    assert group == AuthoredGroup(
        role="r",
        agent_profile="p",
        model="m",
        subtasks=("T001",),
        owned_files=("x.py",),
        dependencies=("WP00",),
        requirement_refs=("FR-1",),
    )


def test_authored_group_helper_none_metadata_is_empty() -> None:
    assert _authored_group(None) == AuthoredGroup()


def test_authored_group_normalizes_subtask_roster_like_transition_guard() -> None:
    metadata = WPMetadata.model_validate(
        {
            "work_package_id": "WP01",
            "title": "Normalize roster",
            "subtasks": [" T01 ", "T01", "T02"],
        },
        strict=False,
    )

    assert _authored_group(metadata).subtasks == ("T01", "T02")


def test_wpview_type_holds_both_groups(tmp_path: Path) -> None:
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)
    view = reconstruct_wp_view(feature_dir, _WP_ID)
    assert isinstance(view, WPView)
    assert view.wp_id == _WP_ID
    assert isinstance(view.resolved, ResolvedGroup)
    assert isinstance(view.authored, AuthoredGroup)


# ---------------------------------------------------------------------------
# SC-007 — the THREE rerouted consumers agree (one reconstruction path)
# ---------------------------------------------------------------------------


def _make_work_package(wp_file: Path, *, status_dir: Path | None = None):  # type: ignore[no-untyped-def]
    """Build a WorkPackage from a WP file (mirrors the status suite helper)."""
    from specify_cli.task_utils import WorkPackage

    content = wp_file.read_text(encoding="utf-8")
    _, _, body = content.partition("---\n")
    front, _, body_text = body.partition("\n---\n")
    return WorkPackage(
        feature=_MISSION_SLUG,
        path=wp_file,
        current_lane="claimed",
        relative_subpath=Path("tasks") / wp_file.name,
        frontmatter=front,
        body=body_text,
        padding="",
        status_dir=status_dir,
    )


def _seed_parity_mission(tmp_path: Path) -> tuple[Path, Path]:
    """Flag-ON mission with a claimed WP carrying a resolved binding (P/M)."""
    feature_dir = _make_feature_dir(tmp_path, status_phase=1)
    wp_file = _write_wp_file(feature_dir)
    _seed_claim(
        feature_dir,
        agent="snapshot-agent",
        shell_pid=99999,
        shell_pid_created_at="2026-01-01T00:00:00+00:00",
        at="2026-01-01T00:00:01+00:00",
    )
    _seed_binding(
        feature_dir,
        tmp_path,
        role="implementer",
        profile="resolver-profile",
        model="resolver-model",
        actor="claude",
        tool="claude",
        profile_version="1.0",
        provider="resolver-provider",
    )
    emit_inner_state_changed(
        feature_dir,
        _WP_ID,
        WPInnerStateDelta(
            assignee="snapshot-assignee",
            subtasks={"T001": Lane.DONE, "T002": Lane.PLANNED},
            review=ReviewOverride(
                at="2026-01-01T00:00:02+00:00",
                actor="reviewer",
                wp_id=_WP_ID,
                reason="parity",
            ),
        ),
        actor="fixture",
        mission_slug=_MISSION_SLUG,
        at="2026-01-01T00:00:02+00:00",
    )
    return feature_dir, wp_file


def test_two_consumers_return_same_resolved_state(tmp_path: Path) -> None:
    """SC-007: the ``agent tasks status`` board row and ``WorkPackage`` surface
    the SAME resolved runtime state for one WP -- because they both reconstruct through the ONE ``reconstruct_wp_view`` reader."""
    from specify_cli.cli.commands.agent.tasks_status_cmd import _st_runtime_row

    feature_dir, wp_file = _seed_parity_mission(tmp_path)
    view = reconstruct_wp_view(feature_dir, _WP_ID)

    board_row = _st_runtime_row(feature_dir, _WP_ID)
    wp = _make_work_package(wp_file)

    # Every dynamic field comes from the same reconstructed resolved group.
    assert board_row["lane"] == wp.lane == view.resolved.lane == "claimed"
    assert board_row["agent"] == wp.agent == view.resolved.agent == "snapshot-agent"
    assert board_row["assignee"] == wp.assignee == view.resolved.assignee == "snapshot-assignee"
    assert board_row["shell_pid"] == wp.shell_pid == view.resolved.shell_pid == "99999"
    assert (
        board_row["shell_pid_created_at"]
        == wp.shell_pid_created_at
        == view.resolved.shell_pid_created_at
        == "2026-01-01T00:00:00+00:00"
    )
    assert board_row["subtasks"] == wp.subtasks == view.resolved.subtasks
    assert board_row["review"] == wp.review == view.resolved.review
    assert board_row["resolved_agent_profile"] == wp.agent_profile == "resolver-profile"
    assert board_row["resolved_agent_profile_version"] == wp.agent_profile_version == "1.0"
    assert board_row["resolved_role"] == wp.role == "implementer"
    assert board_row["resolved_model"] == wp.model == "resolver-model"
    assert board_row["resolved_provider"] == wp.provider == "resolver-provider"


def test_board_authored_profile_is_distinct_from_resolved(tmp_path: Path) -> None:
    """C-008 on the board: the authored ``agent_profile`` (fed to the HiC marker)
    is a SEPARATE row field from the resolved actual; they are never conflated."""
    from specify_cli.cli.commands.agent.tasks_status_cmd import _st_runtime_row
    from specify_cli.task_utils import extract_scalar, split_frontmatter

    feature_dir, wp_file = _seed_parity_mission(tmp_path)
    front, _body, _pad = split_frontmatter(wp_file.read_text(encoding="utf-8"))

    board_row = _st_runtime_row(feature_dir, _WP_ID)
    authored_profile = extract_scalar(front, "agent_profile")

    assert authored_profile == _AUTHORED_PROFILE
    assert board_row["resolved_agent_profile"] == "resolver-profile"
    assert board_row["resolved_agent_profile"] != authored_profile


def test_workpackage_authored_accessors_stay_frontmatter(tmp_path: Path) -> None:
    """WorkPackage exposes the resolved actual AND a distinct authored_* accessor;
    the authored recommendation never leaks into the resolved property (C-008)."""
    feature_dir, wp_file = _seed_parity_mission(tmp_path)
    wp = _make_work_package(wp_file)

    assert wp.agent_profile == "resolver-profile"  # resolved actual
    assert wp.authored_agent_profile == _AUTHORED_PROFILE  # frontmatter recommendation
    assert wp.role == "implementer"
    assert wp.authored_role == _AUTHORED_ROLE
    assert wp.model == "resolver-model"
    assert wp.authored_model == _AUTHORED_MODEL


def test_workpackage_reads_runtime_from_separate_status_partition(tmp_path: Path) -> None:
    """Primary planning metadata and coord runtime state remain separate."""
    primary_dir = _make_feature_dir(tmp_path / "primary")
    wp_file = _write_wp_file(primary_dir)
    status_dir = _make_feature_dir(tmp_path / "coord")
    _seed_claim(
        status_dir,
        agent="coord-agent",
        shell_pid=4242,
        at="2026-01-01T00:00:01+00:00",
    )

    wp = _make_work_package(wp_file, status_dir=status_dir)

    assert wp.lane == "claimed"
    assert wp.agent == "coord-agent"
    assert wp.shell_pid == "4242"
    assert wp.authored_agent_profile == _AUTHORED_PROFILE


# ---------------------------------------------------------------------------
# Presentation-fields-not-swallowed + scanner tolerate-absent (no masquerade)
# ---------------------------------------------------------------------------


