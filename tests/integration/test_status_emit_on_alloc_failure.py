"""Integration tests for allocation-failure status handling (F-50, #3937).

``create_lane_workspace`` runs BEFORE the claim transition, so the WP is still
``planned`` when allocation raises; the allocator self-cleans (abort +
``reset --hard``, no ``lanes.json`` write). Manufacturing a ``planned -> blocked``
transition on that failure created an unrecoverable state (``blocked -> planned``
is illegal), so ``implement`` must instead leave the WP ``planned`` and surface
the exception's actionable ``next_step`` — at parity with the orchestrator-api
path, which never emits ``blocked``.

These tests pin observable STATE (the reduced lane and the event log), not
message substrings, so a cosmetic message edit cannot fake them (NFR-001).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands import implement as implement_mod
from specify_cli.cli.commands.implement import implement
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    PlanningCommitMergeConflictError,
)
from specify_cli.status.reducer import wp_snapshot_state

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the test hermetic; the fixture targets protected ``main``.

    The documented operator escape hatch is the ONE sanctioned waiver for
    status commits on a protected branch (``SPEC_KITTY_TEST_MODE`` no longer
    waives the pre-check — PR #1850 guard-bypass fix).
    """
    import specify_cli.status.emit as status_emit

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


def _create_meta(feature_dir: Path) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "feature_number": feature_dir.name.split("-")[0],
                "mission_slug": feature_dir.name,
                "created_at": "2026-04-26T00:00:00Z",
                "friendly_name": feature_dir.name,
                "mission": "software-dev",
                "slug": feature_dir.name,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return meta_path


def _create_lanes(feature_dir: Path) -> None:
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=feature_dir.name,
            mission_id=f"mission-{feature_dir.name}",
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-26T10:00:00Z",
            computed_from="test",
        ),
    )


def _write_wp_file(feature_dir: Path) -> Path:
    wp_file = feature_dir / "tasks" / "WP01-fixture.md"
    wp_file.parent.mkdir(parents=True, exist_ok=True)
    wp_file.write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nexecution_mode: code_change\nowned_files:\n  - src/wp01/**\nauthoritative_surface: src/wp01/\n---\n# WP01\n",
        encoding="utf-8",
    )
    return wp_file


def _seed_planned(feature_dir: Path, feature_slug: str) -> Path:
    """Seed WP01 into 'planned' (as finalize-tasks does) via a genesis->planned
    event, so the alloc-failure path acts on a genuinely-planned WP."""
    events_log = feature_dir / "status.events.jsonl"
    events_log.write_text(
        json.dumps(
            {
                "actor": "seed",
                "at": "2026-04-25T00:00:00+00:00",
                "event_id": "01HXYZ0123456789ABCDEFGS01",
                "evidence": None,
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "genesis",
                "mission_slug": feature_slug,
                "reason": "seed",
                "review_ref": None,
                "to_lane": "planned",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return events_log


def _build_fixture(tmp_path: Path, feature_slug: str) -> tuple[Path, Path]:
    feature_dir = tmp_path / "kitty-specs" / feature_slug
    _create_meta(feature_dir)
    _create_lanes(feature_dir)
    _write_wp_file(feature_dir)
    events_log = _seed_planned(feature_dir, feature_slug)
    return feature_dir, events_log


def _implement_transitions(events_log: Path) -> list[tuple[str, str]]:
    """The implement-emitted (from, to) transitions, excluding the seed."""
    events = _read_events(events_log)
    return [(e["from_lane"], e["to_lane"]) for e in events if e["from_lane"] != "genesis"]


def _read_events(events_log: Path) -> list[dict[str, object]]:
    if not events_log.exists():
        return []
    return [json.loads(line) for line in events_log.read_text(encoding="utf-8").splitlines() if line.strip()]


@contextmanager
def _patched_implement(
    tmp_path: Path,
    feature_slug: str,
    *,
    alloc: MagicMock,
) -> Iterator[MagicMock]:
    """Patch the ``implement`` collaborators up to (and including) the workspace
    allocator, yielding the recording ``console.print`` mock."""
    with (
        patch.object(implement_mod.console, "print") as mock_print,
        patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
        patch("specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort"),
        patch(
            "specify_cli.cli.commands.implement.detect_feature_context",
            return_value=(feature_slug.split("-")[0], feature_slug),
        ),
        patch(
            "specify_cli.cli.commands.implement.resolve_feature_target_branch",
            return_value="main",
        ),
        patch("specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git"),
        patch("specify_cli.cli.commands.implement._ensure_vcs_in_meta") as mock_ensure_vcs,
        patch(
            "specify_cli.cli.commands.implement.create_lane_workspace",
            new=alloc,
        ),
    ):
        mock_ensure_vcs.return_value = MagicMock(value="git")
        yield mock_print


def _printed_text(mock_print: MagicMock) -> str:
    return "\n".join(" ".join(str(arg) for arg in call.args) for call in mock_print.call_args_list)


@pytest.mark.parametrize(
    ("feature_slug", "exc"),
    [
        (
            "010-dep-lane-conflict-fixture",
            DependencyLaneMergeConflictError("lane-a", "lane-b", "kitty/dep-branch"),
        ),
        (
            "011-planning-commit-conflict-fixture",
            PlanningCommitMergeConflictError("lane-a", "deadbeefcafef00d"),
        ),
    ],
)
def test_alloc_conflict_leaves_wp_planned_and_prints_next_step(
    tmp_path: Path,
    feature_slug: str,
    exc: DependencyLaneMergeConflictError | PlanningCommitMergeConflictError,
) -> None:
    """F-50 (C1): a conflicting allocation leaves the WP ``planned``, emits NO
    ``planned -> blocked`` event, and prints the exception's actionable
    ``next_step`` (not a generic 're-run')."""
    feature_dir, events_log = _build_fixture(tmp_path, feature_slug)
    alloc = MagicMock(side_effect=exc)

    with (
        _patched_implement(tmp_path, feature_slug, alloc=alloc) as mock_print,
        pytest.raises(typer.Exit),
    ):
        implement("WP01", mission=feature_slug, recover=False)
    assert alloc.called

    # Observable STATE 1: the reduced lane is still ``planned`` — recoverable.
    reduced = wp_snapshot_state(feature_dir, "WP01")
    assert reduced is not None
    assert reduced["lane"] == "planned"

    # Observable STATE 2: NO manufactured ``planned -> blocked`` transition, and
    # no ``blocked`` lane was ever entered for this WP.
    transitions = _implement_transitions(events_log)
    assert ("planned", "blocked") not in transitions
    assert all(e["to_lane"] != "blocked" for e in _read_events(events_log))
    # The failure emits NO lifecycle transition at all (only the seed remains).
    assert transitions == []

    # Observable STATE 3: the actionable next_step is surfaced verbatim.
    assert exc.next_step
    assert exc.next_step in _printed_text(mock_print)


def test_rerun_after_resolution_acquires_no_review_cycle_pointer(
    tmp_path: Path,
) -> None:
    """F-50 (C2): once the conflict is resolved, re-running ``implement`` on the
    still-``planned`` WP proceeds through the normal claim — with NO intermediate
    unblock step and NO ``review-cycle://`` feedback pointer (Fix mode is not
    triggered)."""
    feature_slug = "012-rerun-clean-fixture"
    feature_dir, events_log = _build_fixture(tmp_path, feature_slug)

    # Run 1: allocation conflicts -> WP stays planned, nothing emitted.
    alloc_fail = MagicMock(
        side_effect=DependencyLaneMergeConflictError("lane-a", "lane-b", "kitty/dep-branch"),
    )
    with (
        _patched_implement(tmp_path, feature_slug, alloc=alloc_fail),
        pytest.raises(typer.Exit),
    ):
        implement("WP01", mission=feature_slug, recover=False)

    assert (wp_snapshot_state(feature_dir, "WP01") or {}).get("lane") == "planned"

    # Run 2: conflict resolved -> allocation succeeds; let the REAL claim emit
    # run, stubbing only the git-touching side effects.
    alloc_ok = MagicMock(return_value=MagicMock(workspace_path=tmp_path, branch_name="kitty/lane-a"))
    with (
        _patched_implement(tmp_path, feature_slug, alloc=alloc_ok),
        patch("specify_cli.cli.commands.implement._commit_wp_claim_status"),
        patch("specify_cli.cli.commands.implement._report_workspace_created"),
        patch("specify_cli.cli.commands.implement._print_workspace_ready_banner"),
    ):
        implement(
            "WP01",
            mission=feature_slug,
            recover=False,
            base=None,
            json_output=False,
            auto_commit=False,
        )

    events = _read_events(events_log)
    # The normal claim actually happened (proceeded, not an unblock detour).
    assert (wp_snapshot_state(feature_dir, "WP01") or {}).get("lane") == "in_progress"
    # No ``blocked`` lane was ever entered across both runs.
    assert all(e["to_lane"] != "blocked" for e in events)
    # Fix mode was never triggered: no event carries a ``review-cycle://`` pointer.
    assert all(not str(e.get("review_ref") or "").startswith("review-cycle://") for e in events)
