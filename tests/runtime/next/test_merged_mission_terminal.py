"""RED-first regression repro for #2947 (WP02 T008) — the ``next`` control
loop recognizes a merged mission in BOTH entry points via WP01's
committed-authority module (``mission_terminal_verdict``), instead of
fabricating an unstarted/in-flight run from a stale coordination workspace.

Mission next-committed-state-authority-01M1CA8W. Constructs a deliberate
two-surface split (D8/D9/D13 in ``tracer-design-decisions.md``): a PRIMARY
surface carrying the committed ``mission_number`` + all-accepted status (the
merged-mission truth), and a SEPARATE, empty "coordination" read surface
standing in for a stale/deleted coordination checkout that ``next``'s
existing workspace-selection machinery (``mission_context_for`` /
``_resolve_runtime_feature_dir``) would otherwise land on and fabricate an
unstarted run from — the exact #2947 bug. The two surfaces are isolated via
direct patching (mirroring WP01's own ``test_committed_authority.py``
technique of patching ``runtime_bridge_identity._primary_runtime_feature_dir``
directly) so this file does not need a full git-worktree coordination
topology just to prove the pre-check fires on the PRIMARY-only
committed-authority verdict, never the coordination surface.

See ``research.md`` / ``tracer-design-decisions.md`` (D8, D9, D13, F5) for the
full disambiguation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixture scaffolding
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, capture_output=True, check=True)


def _provision_mission_type_activations(repo_root: Path, mission_type: str) -> None:
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (kittify_dir / "config.yaml").write_text(f"mission_type_activations:\n  - {mission_type}\n", encoding="utf-8")


def _seed(
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    *,
    from_lane: Lane,
    to_lane: Lane,
) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{to_lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _write_meta(
    feature_dir: Path,
    mission_slug: str,
    *,
    mission_number: int | None,
    mission_type: str = "software-dev",
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_id": "01KZEE00000000000000000EE",
                "mission_number": mission_number,
                "mission_type": mission_type,
            }
        ),
        encoding="utf-8",
    )


def _mission_context_for_coord(mission_slug: str, coord_dir: Path, mission_type: str = "software-dev"):
    from mission_runtime import MissionArtifactKind, MissionContext, MissionTopology
    from mission_runtime.context import MissionArtifactContext

    return MissionContext(
        mission_slug=mission_slug,
        mission_type=mission_type,
        topology=MissionTopology.SINGLE_BRANCH,
        artifacts=(
            MissionArtifactContext(kind=MissionArtifactKind.PRIMARY_METADATA, read_dir=coord_dir, write_dir=coord_dir, commit_target=None),
            MissionArtifactContext(kind=MissionArtifactKind.WORK_PACKAGE_TASK, read_dir=coord_dir, write_dir=coord_dir, commit_target=None),
            MissionArtifactContext(kind=MissionArtifactKind.STATUS_STATE, read_dir=coord_dir, write_dir=coord_dir, commit_target=None),
        ),
    )


def _build_repo(tmp_path: Path, mission_slug: str, *, mission_number: int | None, wps: dict[str, Lane]) -> tuple[Path, Path, Path]:
    """Build the two-surface split fixture.

    Returns ``(repo_root, primary_dir, coord_dir)``. ``primary_dir`` is the
    default ``kitty-specs/<slug>`` composition (so ``read_primary_meta``'s
    pure path-join finds ``meta.json`` with no patching needed) and carries
    the committed ``mission_number`` + the seeded WP endings. ``coord_dir``
    is a SEPARATE, empty directory standing in for a stale/artifact-missing
    coordination checkout.
    """
    repo_root = tmp_path
    _init_git_repo(repo_root)
    _provision_mission_type_activations(repo_root, "software-dev")

    primary_dir = repo_root / "kitty-specs" / mission_slug
    _write_meta(primary_dir, mission_slug, mission_number=mission_number)
    for wp_id, lane in wps.items():
        from_lane = Lane.APPROVED if lane in (Lane.DONE,) else Lane.GENESIS
        _seed(primary_dir, mission_slug, wp_id, from_lane=from_lane, to_lane=lane)

    coord_dir = repo_root / "coord-worktree" / mission_slug
    coord_dir.mkdir(parents=True)

    _commit_all(repo_root, "seed merged-mission-terminal fixture")
    return repo_root, primary_dir, coord_dir


# ---------------------------------------------------------------------------
# Scenario 1/2: mission_number assigned, all WPs acceptable -> terminal verdict
# ---------------------------------------------------------------------------


class TestMergedMissionAdvancingMode:
    """#2947: ``decide_next_via_runtime`` (``spec-kitty next --result success``,
    the issue's actual repro) on a merged mission returns ``kind: terminal``
    and creates NO run (SHOULD-FIX-5 — observable via
    ``.kittify/runtime/feature-runs.json``)."""

    @pytest.mark.regression
    def test_merged_mission_returns_terminal_and_creates_no_run(self, tmp_path: Path) -> None:
        from runtime.next.decision import DecisionKind
        from runtime.next.runtime_bridge import decide_next_via_runtime
        from runtime.next.runtime_bridge_io import _feature_runs_path

        mission_slug = "042-merged-terminal"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=7,
            wps={"WP01": Lane.DONE, "WP02": Lane.APPROVED},
        )
        runs_path = _feature_runs_path(repo_root)
        assert not runs_path.exists()

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._resolve_runtime_feature_dir",
                return_value=coord_dir,
            ),
        ):
            decision = decide_next_via_runtime("claude", mission_slug, "success", repo_root)

        assert decision.kind == DecisionKind.terminal
        assert not runs_path.exists(), "a merged mission must not fabricate a runtime run (#2947)"


class TestMergedMissionQueryMode:
    """#2947: ``query_current_state`` (bare ``spec-kitty next --json``) on a
    merged mission returns ``kind: query`` with ``mission_state: "done"`` —
    query mode is structurally ``kind: query`` only (D13); it must NOT emit
    ``kind: terminal``."""

    @pytest.mark.regression
    def test_merged_mission_returns_query_done(self, tmp_path: Path) -> None:
        from runtime.next.decision import DecisionKind
        from runtime.next.runtime_bridge import query_current_state

        mission_slug = "042-merged-terminal-query"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=7,
            wps={"WP01": Lane.DONE, "WP02": Lane.APPROVED},
        )

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "mission_runtime.mission_context_for",
                return_value=_mission_context_for_coord(mission_slug, coord_dir),
            ),
        ):
            decision = query_current_state("claude", mission_slug, repo_root)

        assert decision.kind == DecisionKind.query
        assert decision.mission_state == "done"


# ---------------------------------------------------------------------------
# Scenario 3: mission_number assigned, NOT all WPs acceptable -> blocked_conflict
# ---------------------------------------------------------------------------


class TestMergedMissionConflict:
    """FR-009: a committed ``mission_number`` whose WPs are NOT all an
    acceptable ending is a conflict — ``kind: blocked`` in BOTH modes, never
    a silent terminal."""

    @pytest.mark.regression
    def test_advancing_mode_returns_blocked(self, tmp_path: Path) -> None:
        from runtime.next.decision import DecisionKind
        from runtime.next.runtime_bridge import decide_next_via_runtime

        mission_slug = "042-merged-conflict-advance"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=9,
            wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED},
        )

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._resolve_runtime_feature_dir",
                return_value=coord_dir,
            ),
        ):
            decision = decide_next_via_runtime("claude", mission_slug, "success", repo_root)

        assert decision.kind == DecisionKind.blocked

    @pytest.mark.regression
    def test_query_mode_returns_blocked(self, tmp_path: Path) -> None:
        from runtime.next.decision import DecisionKind
        from runtime.next.runtime_bridge import query_current_state

        mission_slug = "042-merged-conflict-query"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=9,
            wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED},
        )

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "mission_runtime.mission_context_for",
                return_value=_mission_context_for_coord(mission_slug, coord_dir),
            ),
        ):
            decision = query_current_state("claude", mission_slug, repo_root)

        # Query mode is structurally kind:query — a conflict surfaces as
        # mission_state:"blocked" (the finalized-override precedent), NOT
        # kind:blocked, preserving the is_query invariant. Advancing mode
        # (test_advancing_mode_returns_blocked) emits the actionable kind:blocked.
        assert decision.kind == DecisionKind.query
        assert decision.mission_state == "blocked"
        assert decision.is_query is True


# ---------------------------------------------------------------------------
# Scenario 5 (C-003): never-started mission -> unchanged, not spuriously terminal
# ---------------------------------------------------------------------------


class TestNeverStartedMissionUnaffected:
    """F5/C-003: a mission with no committed status log at all (never
    finalized; no ``meta.json`` at all here) must NOT be spuriously read as
    terminal — ``mission_terminal_verdict`` returns ``"none"`` (mission_number
    absent) and downstream behavior is byte-identical to today: the
    pre-existing ``MissionNotFoundError`` still raises."""

    def test_missing_mission_still_raises_mission_not_found(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import MissionNotFoundError, query_current_state

        with pytest.raises(MissionNotFoundError, match="042-never-started"):
            query_current_state("claude", "042-never-started", tmp_path)


# ---------------------------------------------------------------------------
# Scenario 6 (F4): mission_number assigned, PRIMARY event log absent ->
# "none" fall-through (distinct from Scenario 5, where mission_number itself
# is absent)
# ---------------------------------------------------------------------------


class TestMissionNumberAssignedEventLogAbsent:
    """F4 pin: ``mission_terminal_verdict`` declines (returns ``"none"``, not
    ``"terminal"``/``"blocked_conflict"``) when ``meta.json.mission_number``
    is assigned but the committed PRIMARY ``status.events.jsonl`` is
    genuinely absent (``has_event_log`` False). This is distinct from
    Scenario 5 (``TestNeverStartedMissionUnaffected``), which covers
    ``mission_number`` itself being absent.

    Scenario 1 (``TestMergedMissionAdvancingMode.
    test_merged_mission_returns_terminal_and_creates_no_run``) already pins
    the sibling "number present + folded log all-accepted -> terminal" case;
    this test only adds the absent-log leg of that same short-circuit
    (``_merged_mission_short_circuit`` in ``runtime_bridge.py`` returns
    ``None`` for a ``"none"`` verdict, F5), so a future merge-fold change to
    the short-circuit or to ``mission_terminal_verdict`` cannot silently
    re-open #2947 by treating an absent log as terminal/blocked instead of
    falling through to legacy (byte-identical, fail-safe) behavior."""

    @pytest.mark.regression
    def test_verdict_is_none_when_number_present_but_log_absent(self, tmp_path: Path) -> None:
        from runtime.next.committed_authority import mission_terminal_verdict
        from specify_cli.status import has_event_log

        mission_slug = "042-merged-number-only"
        primary_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(primary_dir, mission_slug, mission_number=13)
        # Deliberately no _seed() call -- no status.events.jsonl is written.
        assert not has_event_log(primary_dir)

        with patch(
            "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
            return_value=primary_dir,
        ):
            verdict = mission_terminal_verdict(tmp_path, mission_slug)

        assert verdict == "none"


# ---------------------------------------------------------------------------
# #3829 item 1: the short-circuit declines on handle-form errors so the
# entry points' own typed classification shapes are restored byte-for-byte
# (pre-#3825 baseline verified against commit cf341341c).
# ---------------------------------------------------------------------------


class TestHandleFormErrorsFallThrough:
    """A traversal-unsafe / empty handle must surface the SAME error the
    entry point produced BEFORE the #2947 short-circuit was added — the
    short-circuit's ``read_primary_meta`` pre-empted those with a raw
    ``ValueError`` raised ahead of ``query_current_state``'s typed
    ``MissionNotFoundError`` / read-path classification."""

    @pytest.mark.regression
    def test_query_empty_handle_is_typed_mission_not_found(self, tmp_path: Path) -> None:
        """Pre-#3825 baseline: ``query_current_state('')`` raised the typed
        ``MissionNotFoundError`` (the resolver's ``require_explicit_feature``
        arm). The #3825 short-circuit turned it into a raw
        ``UnsafePathSegmentError`` from ``_compose_primary_feature_dir``."""
        from runtime.next.runtime_bridge import MissionNotFoundError, query_current_state

        with pytest.raises(MissionNotFoundError, match="''"):
            query_current_state("claude", "", tmp_path)

    @pytest.mark.regression
    def test_query_traversal_handle_raises_the_path_guard_from_the_resolver(self, tmp_path: Path) -> None:
        """Pre-#3825 baseline: a traversal handle raised the path-guard
        ``ValueError`` from the read-side resolver — never from the
        short-circuit. With the decline, the raise comes from the same
        resolver the pre-#3825 code reached."""
        from specify_cli.core.paths import UnsafePathSegmentError
        from runtime.next.runtime_bridge import query_current_state

        with pytest.raises(UnsafePathSegmentError, match="traversal guard"):
            query_current_state("claude", "../foo", tmp_path)

    @pytest.mark.regression
    def test_advance_traversal_handle_still_raises_path_guard(self, tmp_path: Path) -> None:
        from specify_cli.core.paths import UnsafePathSegmentError
        from runtime.next.runtime_bridge import decide_next_via_runtime

        with pytest.raises(UnsafePathSegmentError, match="traversal guard"):
            decide_next_via_runtime("claude", "../foo", "success", tmp_path)


# ---------------------------------------------------------------------------
# #3829 item 2: the blocked_conflict reason carries an operator remediation
# affordance (the board command + the move-task that resolves a straggler).
# ---------------------------------------------------------------------------


class TestBlockedConflictRemediationAffordance:
    @pytest.mark.regression
    def test_advance_mode_reason_names_recovery_commands(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import decide_next_via_runtime

        mission_slug = "042-conflict-remediation"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=9,
            wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED},
        )

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "runtime.next.runtime_bridge._resolve_runtime_feature_dir",
                return_value=coord_dir,
            ),
        ):
            decision = decide_next_via_runtime("claude", mission_slug, "success", repo_root)

        assert decision.kind == "blocked"
        assert "spec-kitty agent tasks status --mission 042-conflict-remediation" in (decision.reason or "")
        assert "spec-kitty agent tasks move-task <wp> --to approved" in (decision.reason or "")

    @pytest.mark.regression
    def test_query_mode_reason_names_recovery_commands(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state

        mission_slug = "042-conflict-remediation-query"
        repo_root, primary_dir, coord_dir = _build_repo(
            tmp_path,
            mission_slug,
            mission_number=9,
            wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED},
        )

        with (
            patch(
                "runtime.next.runtime_bridge_identity._primary_runtime_feature_dir",
                return_value=primary_dir,
            ),
            patch(
                "mission_runtime.mission_context_for",
                return_value=_mission_context_for_coord(mission_slug, coord_dir),
            ),
        ):
            decision = query_current_state("claude", mission_slug, repo_root)

        assert decision.kind == "query"
        assert decision.mission_state == "blocked"
        assert "spec-kitty agent tasks status --mission 042-conflict-remediation-query" in (decision.reason or "")
        assert "spec-kitty agent tasks move-task <wp> --to approved" in (decision.reason or "")
