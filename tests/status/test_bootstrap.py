"""Tests for the canonical bootstrap helper (status/bootstrap.py).

Verifies that bootstrap_canonical_state() correctly seeds planned events
for uninitialized WPs, skips already-initialized ones, respects dry_run,
and handles edge cases gracefully.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.status.bootstrap import (
    BootstrapResult,
    bootstrap_canonical_state,
)
from specify_cli.status.store import EVENTS_FILENAME, read_events
from specify_cli.status.models import StatusEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _write_wp_file(tasks_dir: Path, wp_id: str, title: str = "Test WP") -> Path:
    """Create a minimal WP markdown file with valid frontmatter."""
    wp_file = tasks_dir / f"{wp_id}.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {title}\n---\n\n# {title}\n",
        encoding="utf-8",
    )
    return wp_file


def _write_event(feature_dir: Path, wp_id: str, mission_slug: str = "test-feature") -> None:
    """Append a minimal planned event to the JSONL log."""
    event = {
        "event_id": f"01TEST{wp_id}00000000000000",
        "mission_slug": mission_slug,
        "wp_id": wp_id,
        "from_lane": "planned",
        "to_lane": "planned",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "test-setup",
        "force": True,
        "execution_mode": "worktree",
        "reason": "test pre-seed",
        "review_ref": None,
        "evidence": None,
        "policy_metadata": None,
    }
    events_path = feature_dir / EVENTS_FILENAME
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _disable_saas_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap tests assert local state seeding, not SaaS sync behavior."""
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *args, **kwargs: None)


class TestBootstrapCoordinationBranchPersistence:
    """Regression (#1589): bootstrap on a coordination-branch mission must
    persist real lane-state seed events that the lane-state readers can see,
    not silently report success while persisting nothing."""

    def test_coordination_branch_persists_seed_events(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.invalid")
        _git(repo, "config", "user.name", "Test")

        mission_slug = "060-test"
        mid8 = "01COORD0"
        mission_dirname = f"{mission_slug}-{mid8}"
        coord_branch = f"kitty/mission-{mission_dirname}"
        feature_dir = repo / "kitty-specs" / mission_dirname
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_slug": mission_slug,
                    "mission_id": "01COORD000000000000000000",
                    "mid8": mid8,
                    "coordination_branch": coord_branch,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "seed mission")
        _git(repo, "branch", coord_branch)

        result = bootstrap_canonical_state(feature_dir, mission_slug)

        assert result.newly_seeded == 2

        # The seeded events MUST be readable via the same transactional target
        # the writer used. Before the fix these silently vanished (0 events).
        from specify_cli.coordination.status_transition import (
            read_events_transactional,
        )

        events = read_events_transactional(
            feature_dir=feature_dir, mission_slug=mission_slug
        )
        seeded = {e.wp_id: str(e.to_lane) for e in events if e.wp_id}
        assert seeded == {"WP01": "planned", "WP02": "planned"}, (
            f"bootstrap reported {result.newly_seeded} seeded but the "
            f"transactional read target shows {seeded}"
        )


class TestBootstrapSeedsUninitialized:
    """T002-a: Seeds planned events for uninitialized WPs."""

    def test_three_new_wps(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")
        _write_wp_file(tasks_dir, "WP03")

        result = bootstrap_canonical_state(feature_dir, "060-test-feature")

        assert result.total_wps == 3
        assert result.already_initialized == 0
        assert result.newly_seeded == 3
        assert result.skipped == 0

        # Verify events written
        events = read_events(feature_dir)
        wp_ids_in_events = {e.wp_id for e in events}
        assert wp_ids_in_events == {"WP01", "WP02", "WP03"}

        # All events should target "planned"
        for event in events:
            assert str(event.to_lane) == "planned"
            assert event.actor == "finalize-tasks"
            # T030: genesis->planned is a real allowed edge (no force needed)
            assert event.force is False

        # Verify status.json was materialized
        status_json = feature_dir / "status.json"
        assert status_json.exists()
        snapshot = json.loads(status_json.read_text(encoding="utf-8"))
        assert snapshot["summary"]["planned"] == 3
        assert set(snapshot["work_packages"].keys()) == {"WP01", "WP02", "WP03"}

    def test_wp_details_report(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.wp_details["WP01"] == "initialized"
        assert result.wp_details["WP02"] == "initialized"


class TestBootstrapSkipsInitialized:
    """T002-b: Skips already-initialized WPs."""

    def test_one_existing_one_new(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")

        # Pre-seed WP01 into the event log
        _write_event(feature_dir, "WP01", "060-test-feature")

        result = bootstrap_canonical_state(feature_dir, "060-test-feature")

        assert result.total_wps == 2
        assert result.already_initialized == 1
        assert result.newly_seeded == 1
        assert result.wp_details["WP01"] == "already_exists"
        assert result.wp_details["WP02"] == "initialized"

        # Only 2 events total: 1 pre-existing + 1 new
        events = read_events(feature_dir)
        assert len(events) == 2

    def test_all_already_initialized(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")

        _write_event(feature_dir, "WP01", "060-test")
        _write_event(feature_dir, "WP02", "060-test")

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 2
        assert result.already_initialized == 2
        assert result.newly_seeded == 0

    def test_uses_transactional_read_target(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")

        def fake_transactional_read(**kwargs: object) -> list[StatusEvent]:
            assert kwargs["feature_dir"] == feature_dir
            assert kwargs["mission_slug"] == "060-test"
            event = {
                "event_id": "01TESTWP0100000000000000",
                "mission_slug": "060-test",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "claimed",
                "at": "2026-01-01T00:00:00+00:00",
                "actor": "coord-branch",
                "force": True,
                "execution_mode": "worktree",
                "reason": "already initialized elsewhere",
                "review_ref": None,
                "evidence": None,
                "policy_metadata": None,
            }
            return [StatusEvent(**event)]

        # bootstrap_canonical_state imports read_events_transactional lazily at
        # call time (cycle-breaker), so patch it at the source module it resolves.
        monkeypatch.setattr(
            "specify_cli.coordination.status_transition.read_events_transactional",
            fake_transactional_read,
        )

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 1
        assert result.already_initialized == 1
        assert result.newly_seeded == 0


class TestBootstrapDryRun:
    """T002-c: Dry-run does not mutate."""

    def test_dry_run_no_events(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")

        result = bootstrap_canonical_state(feature_dir, "060-test", dry_run=True)

        assert result.total_wps == 2
        assert result.newly_seeded == 2
        assert result.wp_details["WP01"] == "would_seed"
        assert result.wp_details["WP02"] == "would_seed"

        # No event log should exist
        events_path = feature_dir / EVENTS_FILENAME
        assert not events_path.exists()

        # No status.json
        status_path = feature_dir / "status.json"
        assert not status_path.exists()

    def test_dry_run_coordination_branch_does_not_create_worktree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.invalid")
        _git(repo, "config", "user.name", "Test")

        mission_slug = "060-test"
        mid8 = "01DRYRUN"
        mission_dirname = f"{mission_slug}-{mid8}"
        coord_branch = f"kitty/mission-{mission_dirname}"
        feature_dir = repo / "kitty-specs" / mission_dirname
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_slug": mission_slug,
                    "mission_id": "01DRYRUN0000000000000000",
                    "mid8": mid8,
                    "coordination_branch": coord_branch,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        _write_wp_file(tasks_dir, "WP01")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "seed mission")
        _git(repo, "branch", coord_branch)

        result = bootstrap_canonical_state(feature_dir, mission_slug, dry_run=True)

        assert result.total_wps == 1
        assert result.newly_seeded == 1
        assert result.wp_details["WP01"] == "would_seed"
        assert not (repo / ".worktrees").exists()
        assert _git(repo, "status", "--short").stdout == ""

    def test_dry_run_with_existing_events(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        _write_wp_file(tasks_dir, "WP01")
        _write_wp_file(tasks_dir, "WP02")
        _write_event(feature_dir, "WP01", "060-test")

        result = bootstrap_canonical_state(feature_dir, "060-test", dry_run=True)

        assert result.total_wps == 2
        assert result.already_initialized == 1
        assert result.newly_seeded == 1
        assert result.wp_details["WP01"] == "already_exists"
        assert result.wp_details["WP02"] == "would_seed"

        # Event log should still have exactly 1 event (the pre-existing one)
        events = read_events(feature_dir)
        assert len(events) == 1


class TestBootstrapEmptyTasks:
    """T002-d: Empty tasks directory."""

    def test_no_tasks_directory(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        feature_dir.mkdir(parents=True)
        # No tasks/ subdirectory at all

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 0
        assert result.already_initialized == 0
        assert result.newly_seeded == 0
        assert result.wp_details == {}

    def test_empty_tasks_directory(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        # tasks/ exists but has no WP files

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 0
        assert result.already_initialized == 0
        assert result.newly_seeded == 0

    def test_non_wp_files_ignored(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        # These should NOT be picked up by the WP*.md glob
        (tasks_dir / "notes.md").write_text("# Notes\n", encoding="utf-8")
        (tasks_dir / "README.md").write_text("# README\n", encoding="utf-8")

        result = bootstrap_canonical_state(feature_dir, "060-test")
        assert result.total_wps == 0


class TestBootstrapMalformedFrontmatter:
    """T002-e: WP with missing work_package_id or malformed frontmatter."""

    def test_missing_work_package_id(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        # Valid WP
        _write_wp_file(tasks_dir, "WP01")

        # WP file without work_package_id in frontmatter
        bad_wp = tasks_dir / "WP02.md"
        bad_wp.write_text(
            "---\ntitle: Missing ID\n---\n\n# Bad WP\n",
            encoding="utf-8",
        )

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 1  # Only WP01 counted
        assert result.newly_seeded == 1
        assert result.skipped == 1
        assert result.wp_details["WP01"] == "initialized"
        assert result.wp_details["WP02"] == "skipped_malformed"

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        # Valid WP
        _write_wp_file(tasks_dir, "WP01")

        # WP file with no frontmatter at all
        bad_wp = tasks_dir / "WP02.md"
        bad_wp.write_text("# No frontmatter here\n", encoding="utf-8")

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 1
        assert result.newly_seeded == 1
        assert result.skipped == 1
        assert result.wp_details["WP02"] == "skipped_malformed"

    def test_empty_work_package_id(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        # Valid WP
        _write_wp_file(tasks_dir, "WP01")

        # WP with empty work_package_id
        bad_wp = tasks_dir / "WP02.md"
        bad_wp.write_text(
            "---\nwork_package_id: \"\"\ntitle: Empty ID\n---\n\n# Bad\n",
            encoding="utf-8",
        )

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 1
        assert result.skipped == 1

    def test_all_malformed(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "060-test"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        # Two WP files, both malformed
        (tasks_dir / "WP01.md").write_text("no frontmatter\n", encoding="utf-8")
        (tasks_dir / "WP02.md").write_text("also no frontmatter\n", encoding="utf-8")

        result = bootstrap_canonical_state(feature_dir, "060-test")

        assert result.total_wps == 0
        assert result.newly_seeded == 0
        assert result.skipped == 2


class TestBootstrapResultDataclass:
    """Verify BootstrapResult dataclass behavior."""

    def test_defaults(self) -> None:
        result = BootstrapResult()
        assert result.total_wps == 0
        assert result.already_initialized == 0
        assert result.newly_seeded == 0
        assert result.skipped == 0
        assert result.wp_details == {}

    def test_values(self) -> None:
        result = BootstrapResult(
            total_wps=3,
            already_initialized=1,
            newly_seeded=2,
            skipped=0,
            wp_details={"WP01": "already_exists", "WP02": "initialized", "WP03": "initialized"},
        )
        assert result.total_wps == 3
        assert result.already_initialized == 1


def test_bootstrap_threads_owned_mission_into_per_wp_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#3866 — every per-WP seed request carries the caller's validated value object.

    The per-WP identity derivation must not re-run ``resolve_owned_mission``
    for each seeded WP; the threaded ``owned_mission`` rides the request.
    """
    from specify_cli.coordination import status_transition
    from specify_cli.core.owned_mission import OwnedMission

    feature_dir = tmp_path / "kitty-specs" / "060-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")
    _write_wp_file(tasks_dir, "WP02")

    recorded: list = []

    def _record_emit(request, **_kwargs):
        recorded.append(request)
        return None

    def _must_not_run(*_a, **_k):
        raise AssertionError("per-WP seed must not re-run resolve_owned_mission")

    monkeypatch.setattr(status_transition, "emit_status_transition_transactional", _record_emit)
    monkeypatch.setattr(status_transition, "read_events_transactional", lambda **_k: [])
    monkeypatch.setattr("specify_cli.status.bootstrap.materialize", lambda *_a, **_k: None)
    monkeypatch.setattr("specify_cli.core.owned_mission.resolve_owned_mission", _must_not_run)

    owned = OwnedMission(
        primary=tmp_path, root=tmp_path / "owned", directory=feature_dir, slug="060-test", target="main"
    )
    result = bootstrap_canonical_state(
        feature_dir,
        "060-test",
        repo_root=tmp_path,
        effective_root=owned.root,
        owned_mission=owned,
    )

    assert result.newly_seeded == 2
    assert [request.wp_id for request in recorded] == ["WP01", "WP02"]
    assert all(request.owned_mission is owned for request in recorded)
    assert all(request.effective_root == owned.root for request in recorded)
