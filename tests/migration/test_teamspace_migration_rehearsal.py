"""Cross-repo TeamSpace mission-state migration rehearsal."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version
from pydantic import ValidationError

from specify_cli.migration.mission_state import FORBIDDEN_LEGACY_KEYS, repair_repo, teamspace_dry_run


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _has_events_5() -> bool:
    import spec_kitty_events

    return Version(spec_kitty_events.__version__) >= Version("5.0.0")


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_historical_fixture(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# historical migration rehearsal\n", encoding="utf-8")
    mission_a = repo / "kitty-specs" / "042-historical-shape"
    mission_b = repo / "kitty-specs" / "077-missing-event-id"
    mission_a.mkdir(parents=True)
    mission_b.mkdir(parents=True)

    _write_json(
        mission_a / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "feature_number": "042",
            "feature_slug": "042-historical-shape",
            "friendly_name": "Historical Shape",
            "mission": "software-dev",
            "slug": "042-historical-shape",
            "target_branch": "main",
        },
    )
    status_row = {
        "actor": {"display_name": "Claude Code", "model": "claude-sonnet"},
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
        "execution_mode": "worktree",
        "feature_slug": "042-historical-shape",
        "force": False,
        "from_lane": "doing",
        "legacy_aggregate_id": "feature:042-historical-shape",
        "reason": "ready for review",
        "to_lane": "in_review",
        "work_package_id": "WP01",
    }
    # A real DecisionPointOpened payload carries `mission_slug` (the canonical
    # field name), never the legacy `feature_slug` -- this row is preserved
    # in place, untouched, by the repair (#4897), so a legacy key embedded
    # here (rather than in a canonicalized lane row) would be unrealistic
    # test data, not a case the repair is expected to scrub.
    typed_side_log = {
        "at": "2026-01-01T00:00:01+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "event_type": "DecisionPointOpened",
        "payload": {"decision_point_id": "DP01", "mission_slug": "042-historical-shape"},
    }
    _write_jsonl(mission_a / "status.events.jsonl", [status_row, dict(status_row), typed_side_log])
    _write_jsonl(
        mission_a / "mission-events.jsonl",
        [{"event_type": "MissionNextInvoked", "payload": {"mission_slug": "042-historical-shape"}}],
    )

    _write_json(
        mission_b / "meta.json",
        {
            "created_at": "2026-01-02T00:00:00+00:00",
            "feature_number": "077",
            "feature_slug": "077-missing-event-id",
            "friendly_name": "Missing Event ID",
            "mission": "software-dev",
            "target_branch": "main",
        },
    )
    _write_jsonl(
        mission_b / "status.events.jsonl",
        [
            {
                "actor": "",
                "at": "2026-01-02T00:00:00+00:00",
                "feature_slug": "077-missing-event-id",
                "to_lane": "claimed",
                "work_package_id": "WP02",
            }
        ],
    )


def _init_clean_git_repo(repo: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-03T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-03T00:00:00+00:00",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "rehearsal@spec-kitty.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "migration rehearsal"], cwd=repo, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:Priivacy-ai/teamspace-rehearsal-fixture.git"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "historical fixture baseline"], cwd=repo, check=True, env=env)


def _commit_all(repo: Path, message: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-04T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-04T00:00:00+00:00",
    }
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True, env=env)


def _git_diff(repo: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "--", "kitty-specs", ".kittify/mission-state-audit"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _find_forbidden_keys(value: Any) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_LEGACY_KEYS:
                findings.append(key)
            findings.extend(_find_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            findings.extend(_find_forbidden_keys(child))
    return findings


@pytest.mark.skipif(not _has_events_5(), reason="TeamSpace rehearsal requires spec-kitty-events >= 5.0.0")
def test_teamspace_mission_state_rehearsal_is_deterministic_across_clones(tmp_path: Path) -> None:
    """Exercise the #932 launch rehearsal path on two cloned historical repos."""
    from spec_kitty_events import Event

    source = tmp_path / "source"
    clone_a = tmp_path / "clone-a"
    clone_b = tmp_path / "clone-b"
    _write_historical_fixture(source)
    shutil.copytree(source, clone_a)
    shutil.copytree(source, clone_b)
    _init_clean_git_repo(clone_a)
    _init_clean_git_repo(clone_b)

    raw_dry_run = teamspace_dry_run(clone_a)
    assert not raw_dry_run.valid
    assert {error["error"] for error in raw_dry_run.errors} == {
        "MISSION_STATE_AUDIT_BLOCKER",
    }
    finding_codes = {error["finding_code"] for error in raw_dry_run.errors}
    assert "LEGACY_KEY" in finding_codes
    assert "FORBIDDEN_KEY" not in finding_codes
    first_raw_row = _jsonl_rows(clone_a / "kitty-specs/042-historical-shape/status.events.jsonl")[0]
    with pytest.raises(ValidationError):
        Event.model_validate(first_raw_row)

    repair_a = repair_repo(clone_a)
    repair_b = repair_repo(clone_b)
    assert repair_a.to_dict()["summary"] == repair_b.to_dict()["summary"]
    assert repair_a.to_dict()["target_missions"] == repair_b.to_dict()["target_missions"]
    assert _git_diff(clone_a) == _git_diff(clone_b)

    _commit_all(clone_a, "commit deterministic mission-state repair")
    _commit_all(clone_b, "commit deterministic mission-state repair")

    second_a = repair_repo(clone_a)
    second_b = repair_repo(clone_b)
    assert [mission.status for mission in second_a.missions] == ["unchanged", "unchanged"]
    assert [mission.status for mission in second_b.missions] == ["unchanged", "unchanged"]

    dry_run_a = teamspace_dry_run(clone_a)
    dry_run_b = teamspace_dry_run(clone_b)
    assert dry_run_a.valid
    assert dry_run_b.valid
    assert dry_run_a.envelope_count == 2
    assert dry_run_a.to_dict() == dry_run_b.to_dict()

    for repo in (clone_a, clone_b):
        for status_path in sorted((repo / "kitty-specs").glob("*/status.events.jsonl")):
            rows = _jsonl_rows(status_path)
            assert rows
            for row in rows:
                assert not _find_forbidden_keys(row)
                if "event_type" in row:
                    # Preserved non-lane row (canonical lifecycle event or
                    # DecisionPoint mirror, #4897) -- kept byte-identical by
                    # the repair, not restamped with mission_id/mission_slug
                    # the way a canonicalized lane row is.
                    continue
                assert row["mission_id"]
                assert row["mission_slug"] == status_path.parent.name

        quarantine = repo / ".kittify/mission-state-audit/quarantine"
        assert list(quarantine.glob("*/042-historical-shape/status.events.jsonl"))
