"""#4141 — the ``--refresh-planning-commit`` re-point affordance.

`finalize-tasks` freezes ``planning_commit_sha`` into ``lanes.json`` at first
run and — correctly, per #3311 — PRESERVES it once execution has begun, so an
ownership-only amendment cannot silently clobber established planning
provenance. But preserve-only left no sanctioned way to advance the recorded
SHA after a legitimate planning amendment landed mid-execution: every
subsequently allocated lane kept merging the STALE planning snapshot
(``_merge_recorded_planning_commit`` merges the recorded, never re-derived
SHA), the ``move-task`` gates fired on the resulting drift, and the only
in-tool path was ``--force`` on every transition (a real 9-WP mission needed
18 overrides).

The fix (#4141) adds ``--refresh-planning-commit`` to ``finalize-tasks``: with
execution begun, it re-points the recorded SHA to the current target-branch
tip — advance-only, refused when the recorded SHA is not an ANCESTOR of the
tip (a history rewrite, not an amendment). Without the flag the #3311 preserve
behavior is unchanged, but the re-finalize now DETECTS the drift (recorded SHA
vs branch tip) and tells the operator the flag exists, on the console
(human mode) and structurally in the ``--json`` success payload
(``planning_commit``).

These tests drive the REAL ``finalize_tasks`` entry point against a REAL git
repo (so ``capture_branch_tip`` and the ancestor check resolve actual
SHAs), mirroring ``test_finalize_provenance_guard.py``'s harness:

* ``test_refresh_repoints_recorded_sha_to_amended_tip`` — the crux: after
  execution has begun and the branch has advanced, a refresh run writes the
  NEW tip into ``lanes.json`` and reports ``action: "refreshed"`` with the
  previous SHA in the JSON payload.
* ``test_refresh_refused_when_recorded_sha_not_ancestor`` — the safety gate:
  a recorded SHA that DIVERGED from the branch (a real commit on a side
  branch, not a fake string) is refused — ``lanes.json`` is left untouched
  and the refusal names the divergence.
* ``test_preserve_path_warns_on_drift_without_flag`` — the detect-and-offer
  half: the default (no-flag) run still preserves (#3311) but now WARNS that
  the branch has advanced and names ``--refresh-planning-commit``.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
    _setup_lane_based_feature,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SEAM = "specify_cli.cli.commands.agent.mission_finalize"


def _run_finalize(
    mission_slug: str,
    patches: dict[str, object],
    *,
    refresh: bool = False,
    json_output: bool = True,
) -> None:
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    ctx_patches = {k: patch(k, v) for k, v in patches.items()}
    for p in ctx_patches.values():
        p.start()
    try:
        finalize_tasks(
            feature=mission_slug,
            json_output=json_output,
            validate_only=False,
            refresh_planning_commit=refresh,
        )
    except (typer.Exit, SystemExit):
        pass  # finalize-tasks may exit; the file writes / captured emissions
        # are what we assert on (a refusal path deliberately exits non-zero).
    finally:
        for p in ctx_patches.values():
            p.stop()


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_init_with_first_commit(repo_root: Path) -> None:
    """Real git repo so SHA capture + the ancestor check resolve real SHAs."""
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _git_commit_marker(repo_root: Path, name: str, message: str) -> str:
    """Commit one marker file on the CURRENT branch and return its tip SHA."""
    marker = repo_root / name
    marker.write_text(f"{name}\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)
    return _git(repo_root, "rev-parse", "--verify", "HEAD")


def _seed_execution_begun_event(repo_root: Path, mission_slug: str, wp_id: str) -> None:
    """Append a real WP-past-``planned`` event (the #3311 execution-begun signal)."""
    read_dir = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    append_event(
        read_dir,
        StatusEvent(
            event_id="01HXYZ4141EXECUTIONBEGUNEVT",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-09T00:00:00Z",
            actor="claude-sonnet",
            force=False,
            execution_mode="worktree",
        ),
    )


def _amend_wp01_owned_files(feature_dir: Path) -> None:
    """The planning amendment on disk: WP01 additionally owns a WP02 path."""
    wp01 = feature_dir / "tasks" / "WP01-test.md"
    wp01.write_text(
        wp01.read_text(encoding="utf-8").replace(
            "owned_files:\n  - src/alpha.py\n",
            "owned_files:\n  - src/alpha.py\n  - src/beta.py\n",
        ),
        encoding="utf-8",
    )


def _base_patches(tmp_path: Path, mission_slug: str, feature_dir: Path) -> dict[str, object]:
    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())
    return patches


@pytest.fixture(autouse=True)
def _disable_saas_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep finalize-tasks on the offline path (mirrors sibling finalize tests)."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def test_refresh_repoints_recorded_sha_to_amended_tip(tmp_path: Path) -> None:
    mission_slug = "064-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize the established lanes; execution has NOT begun, so
    # the real main tip is captured as the recorded planning SHA.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None, "a real git repo must yield a real captured tip"

    # Execution begins (WP01 claimed), then a planning amendment lands on the
    # planning branch: the branch tip advances past the recorded SHA.
    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")
    _amend_wp01_owned_files(feature_dir)
    amended_tip = _git_commit_marker(tmp_path, "AMENDMENT.txt", "planning amendment")
    assert amended_tip != recorded_tip

    # Run 2: the operator confirms the re-point with --refresh-planning-commit.
    emitted: list[dict[str, object]] = []
    capture_patches = {**patches, f"{SEAM}._emit_json": emitted.append}
    _run_finalize(mission_slug, capture_patches, refresh=True)

    after = read_lanes_json(feature_dir)
    assert after is not None
    assert after.planning_commit_sha == amended_tip, (
        "--refresh-planning-commit must advance the recorded planning_commit_sha "
        f"to the amended branch tip; went {recorded_tip!r} -> "
        f"{after.planning_commit_sha!r} (expected {amended_tip!r})"
    )

    # The JSON success payload carries the refresh decision structurally.
    success = next(e for e in emitted if e.get("result") == "success")
    planning_commit = success["planning_commit"]
    assert planning_commit["action"] == "refreshed"
    assert planning_commit["sha"] == amended_tip
    assert planning_commit["previous_sha"] == recorded_tip


def test_refresh_refused_when_recorded_sha_not_ancestor(tmp_path: Path) -> None:
    mission_slug = "065-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize lanes + capture the real recorded tip.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None

    # A REAL commit that diverged from the planning branch: a side branch off
    # the recorded tip, while main itself advances separately. The side SHA
    # exists in the repository but is NOT an ancestor of the new main tip —
    # the exact "history rewritten / diverged, not amended" shape the refresh
    # must refuse (a fake unknown SHA would only exercise the weaker
    # "object unknown" failure of the same git check).
    _git(tmp_path, "checkout", "-q", "-b", "side-branch")
    diverged_sha = _git_commit_marker(tmp_path, "DIVERGED.txt", "side branch")
    _git(tmp_path, "checkout", "-q", "main")
    amended_tip = _git_commit_marker(tmp_path, "AMENDMENT.txt", "planning amendment")
    assert diverged_sha != amended_tip

    established.planning_commit_sha = diverged_sha
    write_lanes_json(feature_dir, established)

    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")

    # Run 2: refresh requested against a diverged recorded SHA.
    emitted: list[dict[str, object]] = []
    capture_patches = {**patches, f"{SEAM}._emit_json": emitted.append}
    _run_finalize(mission_slug, capture_patches, refresh=True)

    # Refused BEFORE lanes.json was written: the recorded SHA is untouched.
    after = read_lanes_json(feature_dir)
    assert after is not None
    assert after.planning_commit_sha == diverged_sha, (
        "a refresh whose recorded SHA is not an ancestor of the tip must be "
        "refused before any lanes.json write; planning_commit_sha went "
        f"{diverged_sha!r} -> {after.planning_commit_sha!r}"
    )
    assert any("not an ancestor" in str(e.get("error", "")) for e in emitted), f"the refusal must name the divergence; emitted: {emitted}"


def test_preserve_path_warns_on_drift_without_flag(tmp_path: Path) -> None:
    mission_slug = "066-lane-feature"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git_init_with_first_commit(tmp_path)

    patches = _base_patches(tmp_path, mission_slug, feature_dir)

    # Run 1: materialize lanes; the real main tip is recorded.
    _run_finalize(mission_slug, patches)
    established = read_lanes_json(feature_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None

    # Execution begins, then the planning branch advances (an amendment the
    # operator has NOT yet chosen to re-point to).
    _seed_execution_begun_event(tmp_path, mission_slug, "WP01")
    amended_tip = _git_commit_marker(tmp_path, "AMENDMENT.txt", "planning amendment")

    # Run 2: NO flag — the #3311 preserve behavior must hold, but the drift
    # (recorded SHA vs branch tip) must be surfaced with the recovery command.
    buf = io.StringIO()
    human_console = Console(file=buf, force_terminal=False, width=200)
    human_patches = {**patches, f"{SEAM}.console": human_console}
    _run_finalize(mission_slug, human_patches, refresh=False, json_output=False)

    after = read_lanes_json(feature_dir)
    assert after is not None
    assert after.planning_commit_sha == recorded_tip, (
        f"without --refresh-planning-commit the #3311 preserve behavior must hold; planning_commit_sha went {recorded_tip!r} -> {after.planning_commit_sha!r}"
    )
    console_out = buf.getvalue()
    assert "--refresh-planning-commit" in console_out, (
        f"a preserved SHA against a moved branch tip must name the --refresh-planning-commit recovery command; console: {console_out!r}"
    )
    assert recorded_tip in console_out and amended_tip in console_out
