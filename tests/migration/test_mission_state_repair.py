"""Tests for deterministic mission-state repair."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from packaging.version import Version

from specify_cli.migration.mission_state import (
    MissionStateDryRunError,
    _repo_slug,
    deterministic_ulid,
    repair_repo,
    teamspace_dry_run,
)


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _has_events_5() -> bool:
    import spec_kitty_events

    return Version(spec_kitty_events.__version__) >= Version("5.0.0")


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, object], data)


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "repair-test@spec-kitty.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "repair test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True)


def test_repair_canonicalizes_historical_meta_and_status_events(tmp_path: Path) -> None:
    repo = tmp_path
    mission = repo / "kitty-specs" / "042-historical-shape"
    mission.mkdir(parents=True)
    _write_json(
        mission / "meta.json",
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
        "actor": "Claude Code",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
        "execution_mode": "worktree",
        "feature_slug": "042-historical-shape",
        "force": False,
        "from_lane": "doing",
        "legacy_aggregate_id": "feature:042-historical-shape",
        "to_lane": "in_review",
        "work_package_id": "WP01",
    }
    duplicate_row = dict(status_row)
    typed_row = {
        "at": "2026-01-01T00:00:01+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "event_type": "DecisionPointOpened",
        "payload": {"decision_point_id": "DP01"},
    }
    retrospective_row = {
        "at": "2026-01-01T00:00:02+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGT",
        "type": "RetrospectiveCaptured",
        "payload": {"mission_slug": "042-historical-shape"},
    }
    (mission / "status.events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in (status_row, duplicate_row, typed_row, retrospective_row)) + "\n",
        encoding="utf-8",
    )
    (mission / "mission-events.jsonl").write_text(
        json.dumps({"event_type": "MissionNextInvoked", "payload": {"mission_slug": "042-historical-shape"}}) + "\n",
        encoding="utf-8",
    )

    report = repair_repo(repo)

    report_dict = cast(dict[str, Any], report.to_dict())
    assert report_dict["summary"]["missions_updated"] == 1
    result = report.missions[0]
    assert result.status == "updated"
    # Only the dropped duplicate-event_id row is quarantined. The DecisionPoint
    # mirror row is preserved in place (#4897): it is authoritative per the
    # shared AUTHORITATIVE_NON_LANE_EVENT_TYPES registry, not a prunable mirror.
    assert result.quarantined_rows == 1
    meta = _read_json(mission / "meta.json")
    assert meta["mission_id"] == deterministic_ulid(
        json.dumps(
            {
                "first_event_at": "2026-01-01T00:00:00+00:00",
                "first_event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
                "meta": {
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "friendly_name": "Historical Shape",
                    "mission_slug": "042-historical-shape",
                    "mission_type": "software-dev",
                    "slug": "042-historical-shape",
                    "target_branch": "main",
                },
            },
            sort_keys=True,
        )
    )
    assert meta["mission_number"] == 42
    assert meta["mission_slug"] == "042-historical-shape"
    assert meta["mission_type"] == "software-dev"
    assert "feature_slug" not in meta
    assert "feature_number" not in meta
    assert "mission" not in meta

    rows = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 3
    row = rows[0]
    assert row["mission_slug"] == "042-historical-shape"
    assert row["mission_id"] == meta["mission_id"]
    assert row["wp_id"] == "WP01"
    assert row["from_lane"] == "in_progress"
    assert row["to_lane"] == "in_review"
    assert row["actor"] == "claude-code"
    assert "feature_slug" not in row
    assert "work_package_id" not in row
    assert "legacy_aggregate_id" not in row
    # The DecisionPoint mirror row is authoritative (#4897) -- preserved
    # in place, untouched, rather than quarantined.
    assert rows[1] == typed_row
    # Retrospective lifecycle rows are contracted provenance read back by
    # retrospective consumers — repair must preserve them untouched.
    assert rows[2] == retrospective_row

    status = _read_json(mission / "status.json")
    status_summary = cast(dict[str, object], status["summary"])
    assert status_summary["in_review"] == 1
    quarantine = repo / ".kittify" / "migrations" / "mission-state" / "quarantine" / report.run_id / "042-historical-shape" / "status.events.jsonl"
    quarantine_text = quarantine.read_text(encoding="utf-8")
    assert "DecisionPointOpened" not in quarantine_text
    assert "RetrospectiveCaptured" not in quarantine_text

    if not _has_events_5():
        with pytest.raises(MissionStateDryRunError, match="requires spec-kitty-events >= 5.0.0"):
            teamspace_dry_run(repo, mission="042-historical-shape")
        return

    dry_run = teamspace_dry_run(repo, mission="042-historical-shape")

    assert dry_run.valid
    assert dry_run.schema_version == "3.0.0"
    import spec_kitty_events

    assert dry_run.events_package_version == spec_kitty_events.__version__
    assert Version(dry_run.events_package_version) >= Version("5.0.0")
    assert dry_run.envelope_count == 1
    assert dry_run.errors == ()
    assert len(dry_run.row_mappings) == 1
    mapping = dry_run.row_mappings[0].to_dict()
    assert mapping["mission_slug"] == "042-historical-shape"
    assert mapping["artifact_path"] == "kitty-specs/042-historical-shape/status.events.jsonl"
    assert mapping["line_number"] == 1
    assert mapping["source_event_id"] == "01KQHRB8GCFJAX7HM4ZY52AQGR"
    assert mapping["synthesized_event_id"] == "01KQHRB8GCFJAX7HM4ZY52AQGR"
    assert mapping["synthesized_event_type"] == "WPStatusChanged"
    assert mapping["aggregate_id"] == "WP01"
    assert isinstance(mapping["row_sha256"], str)
    assert isinstance(mapping["envelope_sha256"], str)
    assert {warning["code"] for warning in dry_run.context_warnings} == {
        "TEAMSPACE_PROJECT_CONTEXT_MISSING",
        "TEAMSPACE_TEAM_CONTEXT_NOT_VALIDATED",
    }
    assert dry_run.side_logs == (
        {
            "artifact_path": "kitty-specs/042-historical-shape/mission-events.jsonl",
            "disposition": "skipped_local_side_log",
            "reason": "out_of_scope_for_launch_import",
            "row_count": 1,
        },
    )


@pytest.mark.regression
def test_repair_dedupes_duplicate_authoritative_event_id_without_erroring(tmp_path: Path) -> None:
    """#4938 (duplicate-drop false positive against the #4897 guard).

    Two byte-identical authoritative rows (``event_type`` in
    ``AUTHORITATIVE_NON_LANE_EVENT_TYPES``, e.g. a git-merge/replay artifact
    of an append-only log carrying the same ``DecisionPointOpened`` twice)
    sharing one ``event_id`` is an ordinary duplicate, not data loss: the
    survivor already carries the row in ``canonical_rows``.

    Before the #4938 fix, the T010 (#4897) fail-closed guard
    (``_registry_authoritative_quarantine_violations``) could not
    distinguish this "duplicate whose survivor made it to canonical_rows"
    shape from a genuinely dropped/foreign authoritative row, and hard-erred
    the whole mission repair (``status="error"``) instead of deduping it
    cleanly (``status="updated"``, ``errors=0``) the way it did before #4897
    shipped.
    """
    repo = tmp_path
    mission = repo / "kitty-specs" / "099-duplicate-authoritative-event"
    mission.mkdir(parents=True)
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "feature_number": "099",
            "feature_slug": "099-duplicate-authoritative-event",
            "friendly_name": "Duplicate Authoritative Event",
            "mission": "software-dev",
            "slug": "099-duplicate-authoritative-event",
            "target_branch": "main",
        },
    )
    decision_row = {
        "at": "2026-01-01T00:00:01+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGX",
        "event_type": "DecisionPointOpened",
        "payload": {"decision_point_id": "DP01"},
    }
    duplicate_decision_row = dict(decision_row)
    (mission / "status.events.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in (decision_row, duplicate_decision_row)) + "\n",
        encoding="utf-8",
    )

    report = repair_repo(repo)

    result = report.missions[0]
    assert result.status == "updated", f"expected a successful dedup, got validation_errors: {result.validation_errors}"
    assert result.validation_errors == []
    assert not any("registry_authoritative_row_quarantined" in e for e in result.validation_errors)
    # One copy survives on disk; the byte-identical duplicate is quarantined,
    # not lost -- the survivor is verified below.
    assert result.quarantined_rows == 1
    rows = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0] == decision_row


def test_repair_preserves_legacy_typed_wpstatuschanged_lane_transition(
    tmp_path: Path,
) -> None:
    """#3066 (FR-015): the mutating repair MUST NOT quarantine a legacy
    ``WPStatusChanged`` lane transition emitted by the mission's own writer
    (top-level ``wp_id`` / ``from_lane`` / ``to_lane``).

    Before the fix the repair quarantined that row and — because a preserved
    retrospective row keeps the log non-empty, so the #2376 all-dropped backstop
    never trips — *succeeded* while regenerating a **zero-WP** ``status.json``: a
    silent, data-destroying repair. After the fix the typed lane row is passed
    through, canonicalized to a flat lane event, and folded back into
    ``status.json`` (the WP is retained). A TeamSpace replay envelope (lane
    fields under ``payload``) MUST stay quarantined regardless; a
    ``DecisionPoint*`` mirror is now preserved in place (#4897), not
    quarantined.
    """
    repo = tmp_path
    mission = repo / "kitty-specs" / "042-legacy-typed"
    mission.mkdir(parents=True)
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "feature_number": "042",
            "feature_slug": "042-legacy-typed",
            "friendly_name": "Legacy Typed",
            "mission": "software-dev",
            "slug": "042-legacy-typed",
            "target_branch": "main",
        },
    )
    # The mission's own WPStatusChanged writer shape: event_type PLUS top-level
    # wp_id/from_lane/to_lane. This is the canonical-writer row that #3066 ate.
    legacy_typed_row = {
        "actor": "Claude Code",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
        "event_type": "WPStatusChanged",
        "execution_mode": "worktree",
        "from_lane": "in_progress",
        "mission_slug": "042-legacy-typed",
        "to_lane": "in_review",
        "wp_id": "WP01",
    }
    # TeamSpace replay envelope: same event_type, but lane fields nested under
    # payload (top level is aggregate_id/aggregate_type). MUST stay quarantined.
    teamspace_envelope_row = {
        "aggregate_id": "WP01",
        "aggregate_type": "WorkPackage",
        "at": "2026-01-01T00:00:01+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "event_type": "WPStatusChanged",
        "payload": {
            "from_lane": "in_progress",
            "to_lane": "in_review",
            "wp_id": "WP01",
        },
    }
    # Decision-Moment mirror: a different event_type. Preserved in place (#4897) --
    # authoritative per the shared registry, not a prunable mirror.
    decision_point_row = {
        "at": "2026-01-01T00:00:02+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGT",
        "event_type": "DecisionPointOpened",
        "payload": {"decision_point_id": "DP01"},
    }
    # Preserved retrospective lifecycle row: keeps the canonical log non-empty so
    # the #2376 all-dropped backstop does NOT trip and mask the real #3066 defect
    # (a *successful* repair that silently regenerates a zero-WP status.json).
    retrospective_row = {
        "at": "2026-01-01T00:00:03+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGU",
        "type": "RetrospectiveCaptured",
        "payload": {"mission_slug": "042-legacy-typed"},
    }
    (mission / "status.events.jsonl").write_text(
        "\n".join(
            json.dumps(row, sort_keys=True)
            for row in (
                legacy_typed_row,
                teamspace_envelope_row,
                decision_point_row,
                retrospective_row,
            )
        )
        + "\n",
        encoding="utf-8",
    )

    report = repair_repo(repo)

    result = report.missions[0]
    assert result.status == "updated"

    # status.json RETAINS the WP — the zero-WP regeneration is the #3066 defect.
    status = _read_json(mission / "status.json")
    work_packages = cast(dict[str, object], status["work_packages"])
    assert set(work_packages) == {"WP01"}
    status_summary = cast(dict[str, object], status["summary"])
    assert status_summary["in_review"] == 1

    # The legacy typed lane row survived, canonicalized to a flat lane event; the
    # preserved retrospective row is kept untouched.
    rows = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lane_rows = [row for row in rows if row.get("wp_id") == "WP01"]
    assert len(lane_rows) == 1
    canonical = lane_rows[0]
    assert canonical["from_lane"] == "in_progress"
    assert canonical["to_lane"] == "in_review"
    # The typed discriminator is stripped by the _build_canonical_row allowlist.
    assert "event_type" not in canonical
    assert retrospective_row in rows
    # The DecisionPoint mirror is preserved in place, untouched (#4897).
    assert decision_point_row in rows

    # Only the TeamSpace envelope stays quarantined; the canonical-writer
    # WPStatusChanged shape and the DecisionPoint mirror do NOT.
    assert result.quarantined_rows == 1
    quarantine = repo / ".kittify" / "migrations" / "mission-state" / "quarantine" / report.run_id / "042-legacy-typed" / "status.events.jsonl"
    quarantine_rows = [json.loads(line) for line in quarantine.read_text(encoding="utf-8").splitlines() if line.strip()]
    quarantined_event_ids = {row["event_id"] for row in quarantine_rows}
    assert quarantined_event_ids == {
        "01KQHRB8GCFJAX7HM4ZY52AQGS",  # TeamSpace envelope
    }
    assert "01KQHRB8GCFJAX7HM4ZY52AQGR" not in quarantined_event_ids
    assert "01KQHRB8GCFJAX7HM4ZY52AQGT" not in quarantined_event_ids  # DecisionPointOpened mirror


def test_repair_is_idempotent_after_first_canonicalization(tmp_path: Path) -> None:
    repo = tmp_path
    mission = repo / "kitty-specs" / "001-modern"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Modern",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-modern",
            "mission_type": "software-dev",
            "slug": "001-modern",
            "target_branch": "main",
        },
    )
    (mission / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "codex",
                "at": "2026-01-01T00:00:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "planned",
                "mission_id": mission_id,
                "mission_slug": "001-modern",
                "policy_metadata": None,
                "reason": None,
                "review_ref": None,
                "evidence": None,
                "to_lane": "claimed",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    first = repair_repo(repo)
    second = repair_repo(repo)

    assert first.missions[0].status == "updated"
    assert second.missions[0].status == "unchanged"
    assert second.missions[0].row_transformations == []


def test_deterministic_repair_ids_follow_fork_seed_material(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    mission_a = repo_a / "kitty-specs" / "001-historical"
    mission_b = repo_b / "kitty-specs" / "001-historical"
    mission_a.mkdir(parents=True)
    mission_b.mkdir(parents=True)
    for mission, event_id in (
        (mission_a, "01KQHRB8GCFJAX7HM4ZY52AQGR"),
        (mission_b, "01KQHRB8GCFJAX7HM4ZY52AQGS"),
    ):
        _write_json(
            mission / "meta.json",
            {
                "created_at": "2026-01-01T00:00:00+00:00",
                "feature_number": "001",
                "feature_slug": "001-historical",
                "friendly_name": "Historical",
                "mission": "software-dev",
                "target_branch": "main",
            },
        )
        (mission / "status.events.jsonl").write_text(
            json.dumps(
                {
                    "actor": "codex",
                    "at": "2026-01-01T00:00:00+00:00",
                    "event_id": event_id,
                    "from_lane": "planned",
                    "to_lane": "claimed",
                    "work_package_id": "WP01",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    repair_repo(repo_a)
    repair_repo(repo_b)

    assert _read_json(mission_a / "meta.json")["mission_id"] != _read_json(mission_b / "meta.json")["mission_id"]


def test_teamspace_dry_run_fails_when_status_rows_still_contain_legacy_keys(tmp_path: Path) -> None:
    if not _has_events_5():
        pytest.skip("TeamSpace dry-run validation requires spec-kitty-events >= 5.0.0")

    repo = tmp_path
    mission = repo / "kitty-specs" / "001-needs-repair"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Needs Repair",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-needs-repair",
            "mission_type": "software-dev",
            "slug": "001-needs-repair",
            "target_branch": "main",
        },
    )
    (mission / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "codex",
                "at": "2026-01-01T00:00:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "planned",
                "mission_id": mission_id,
                "mission_slug": "001-needs-repair",
                "to_lane": "claimed",
                "wp_id": "WP01",
                "nested": {"feature_slug": "001-needs-repair"},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    dry_run = teamspace_dry_run(repo, mission="001-needs-repair")

    assert not dry_run.valid
    assert dry_run.envelope_count == 0
    assert dry_run.errors == (
        {
            "artifact_path": "kitty-specs/001-needs-repair/status.events.jsonl",
            "error": "FORBIDDEN_LEGACY_KEY",
            "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
            "key": "feature_slug",
            "line_number": 1,
            "mission_slug": "001-needs-repair",
            "path": "$.nested.feature_slug",
        },
    )


def test_teamspace_dry_run_synthesizes_repo_evidence_for_historical_done_rows(tmp_path: Path) -> None:
    if not _has_events_5():
        pytest.skip("TeamSpace dry-run validation requires spec-kitty-events >= 5.0.0")

    repo = tmp_path
    mission = repo / "kitty-specs" / "001-historical-done"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Historical Done",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-historical-done",
            "mission_type": "software-dev",
            "slug": "001-historical-done",
            "target_branch": "main",
        },
    )
    (mission / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "codex",
                "at": "2026-01-01T00:00:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "approved",
                "mission_id": mission_id,
                "mission_slug": "001-historical-done",
                "policy_metadata": None,
                "reason": None,
                "review_ref": "review://historical",
                "evidence": {
                    "review": {
                        "reviewer": "historical-reviewer",
                        "verdict": "approved",
                        "reference": "review://historical",
                    }
                },
                "to_lane": "done",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    dry_run = teamspace_dry_run(repo, mission="001-historical-done")

    assert dry_run.valid
    assert dry_run.envelope_count == 1
    assert dry_run.errors == ()
    assert len(dry_run.row_mappings) == 1


def test_teamspace_dry_run_synthesizes_missing_historical_approval_evidence(tmp_path: Path) -> None:
    if not _has_events_5():
        pytest.skip("TeamSpace dry-run validation requires spec-kitty-events >= 5.0.0")

    repo = tmp_path
    mission = repo / "kitty-specs" / "001-historical-approval"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Historical Approval",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-historical-approval",
            "mission_type": "software-dev",
            "slug": "001-historical-approval",
            "target_branch": "main",
        },
    )
    rows = [
        {
            "actor": "codex",
            "at": "2026-01-01T00:00:00+00:00",
            "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
            "execution_mode": "worktree",
            "force": False,
            "from_lane": "for_review",
            "mission_id": mission_id,
            "mission_slug": "001-historical-approval",
            "policy_metadata": None,
            "reason": None,
            "review_ref": None,
            "evidence": None,
            "to_lane": "approved",
            "wp_id": "WP01",
        },
        {
            "actor": "codex",
            "at": "2026-01-01T00:00:01+00:00",
            "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGT",
            "execution_mode": "worktree",
            "force": False,
            "from_lane": "approved",
            "mission_id": mission_id,
            "mission_slug": "001-historical-approval",
            "policy_metadata": None,
            "reason": None,
            "review_ref": "review://historical",
            "evidence": None,
            "to_lane": "done",
            "wp_id": "WP01",
        },
    ]
    (mission / "status.events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    dry_run = teamspace_dry_run(repo, mission="001-historical-approval")

    assert dry_run.valid
    assert dry_run.envelope_count == 2
    assert dry_run.errors == ()
    assert len(dry_run.row_mappings) == 2


def test_repo_slug_preserves_https_remote_colon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_git(repo_root: Path, *args: str, check: bool = False) -> _Result:
        assert repo_root == tmp_path
        assert args == ("config", "--get", "remote.origin.url")
        assert check is False
        return _Result("https://github.com/spec-kitty/spec-kitty.git\n")

    monkeypatch.setattr("specify_cli.migration.mission_state._git", fake_git)

    assert _repo_slug(tmp_path) == "spec-kitty/spec-kitty"


def test_repair_refuses_when_common_git_lock_is_held(tmp_path: Path) -> None:
    """A second repair attempt is refused while the canonical lock is genuinely held.

    #4811 (T017): the lock now routes through ``kernel.locks.machine_file_lock``,
    which is advisory truncate-and-reuse rather than exclusive-create. A bare
    lock-path *file* with no live OS-level lock behind it (the pre-#4811
    shape this test used to plant) is no longer "held" -- that is exactly the
    stale-lock footgun advisory reuse fixes (an orphaned file from a crashed
    holder no longer blocks every future repair forever). Real contention --
    a genuine concurrent holder with the OS lock actively held -- is still
    refused immediately via a single non-blocking attempt, which is what this
    test now proves by holding the lock for real before invoking
    ``repair_repo``.
    """
    from kernel.locks import machine_file_lock

    repo = tmp_path
    mission = repo / "kitty-specs" / "001-modern"
    mission.mkdir(parents=True)
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Modern",
            "mission_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
            "mission_number": 1,
            "mission_slug": "001-modern",
            "mission_type": "software-dev",
            "slug": "001-modern",
            "target_branch": "main",
        },
    )
    _init_git_repo(repo)
    lock_path = repo / ".git" / "spec-kitty-mission-state.lock"
    holder = machine_file_lock(lock_path, blocking=False)
    holder.__enter__()
    try:
        with pytest.raises(Exception, match="Another mission-state repair appears to be running"):
            repair_repo(repo)
    finally:
        holder.__exit__(None, None, None)


def test_repair_checks_dirty_relevant_paths_in_linked_worktrees(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    mission = repo / "kitty-specs" / "001-modern"
    mission.mkdir(parents=True)
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Modern",
            "mission_id": "01KQHRB8GCFJAX7HM4ZY52AQGR",
            "mission_number": 1,
            "mission_slug": "001-modern",
            "mission_type": "software-dev",
            "slug": "001-modern",
            "target_branch": "main",
        },
    )
    _init_git_repo(repo)
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "linked-branch", str(linked)], cwd=repo, check=True)
    (linked / "kitty-specs" / "001-modern" / "meta.json").write_text(
        json.dumps({"mission_slug": "dirty"}, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="dirty relevant paths"):
        repair_repo(repo)

    report = repair_repo(repo, allow_dirty=True)
    assert report.missions[0].status == "unchanged"


# ---------------------------------------------------------------------------
# Mission 8 (#930) — secret scrubber for repair manifest command_args
# ---------------------------------------------------------------------------


class TestScrubSecretArgs:
    """``_scrub_secret_args`` must redact every documented secret shape so
    the manifest ``command_args`` field never leaks credentials."""

    def _scrub(self, *argv: str) -> list[str]:
        from specify_cli.migration.mission_state import _scrub_secret_args

        return _scrub_secret_args(list(argv))

    def test_benign_argv_passes_through_unchanged(self) -> None:
        argv = ["doctor", "mission-state", "--fix", "--json"]
        assert self._scrub(*argv) == argv

    def test_secret_flag_value_is_redacted_pair_form(self) -> None:
        assert self._scrub("doctor", "--token", "abc123") == [
            "doctor",
            "--token",
            "<redacted>",
        ]

    def test_secret_flag_value_is_redacted_equals_form(self) -> None:
        assert self._scrub("doctor", "--token=abc123") == [
            "doctor",
            "--token=<redacted>",
        ]

    def test_api_key_flag_redacted(self) -> None:
        assert self._scrub("--api-key", "sk-real-value") == [
            "--api-key",
            "<redacted>",
        ]

    def test_auth_password_secret_flags_redacted(self) -> None:
        out = self._scrub("--auth", "u:p", "--password", "hunter2", "--secret=top")
        assert out == ["--auth", "<redacted>", "--password", "<redacted>", "--secret=<redacted>"]

    def test_authorization_header_redacted(self) -> None:
        argv = ["curl", "-H", "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def"]
        out = self._scrub(*argv)
        assert "<redacted>" in out
        # The header itself is redacted as a standalone item
        assert "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def" not in out

    def test_github_token_redacted(self) -> None:
        token = "ghp_" + "A" * 40
        assert self._scrub("--repo", token) == ["--repo", "<redacted>"]

    def test_slack_token_redacted(self) -> None:
        token = "xoxb-1234-5678-abcdef0123456789"
        assert self._scrub(token) == ["<redacted>"]

    def test_jwt_shape_redacted(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        assert self._scrub(jwt) == ["<redacted>"]

    def test_bare_bearer_redacted(self) -> None:
        out = self._scrub("Bearer abcdefghijklmnopqrstuvwxyz")
        assert out == ["<redacted>"]

    def test_pure_function(self) -> None:
        """Same input list yields equal output every call (no hidden state)."""
        argv = ["--token", "abc123", "ghp_" + "B" * 40]
        a = self._scrub(*argv)
        b = self._scrub(*argv)
        assert a == b

    # ---------------------------------------------------------------------
    # PR #1031 follow-up: broadened flag set + env-var-style argv items.
    # Each test below covers a real-world pattern that the original WP02
    # helper missed.
    # ---------------------------------------------------------------------

    def test_access_token_flag_pair_form_redacted(self) -> None:
        assert self._scrub("--access-token", "sk-abc123") == [
            "--access-token",
            "<redacted>",
        ]

    def test_refresh_token_flag_equals_form_redacted(self) -> None:
        assert self._scrub("--refresh-token=xyz") == ["--refresh-token=<redacted>"]

    def test_id_token_flag_redacted(self) -> None:
        assert self._scrub("--id-token", "oidc-jwt-value") == [
            "--id-token",
            "<redacted>",
        ]

    def test_client_secret_flag_redacted(self) -> None:
        assert self._scrub("--client-secret", "shh") == [
            "--client-secret",
            "<redacted>",
        ]

    def test_client_id_flag_passes_through(self) -> None:
        """``--client-id`` is a public OAuth identifier, not a secret."""
        assert self._scrub("--client-id", "public-client-123") == [
            "--client-id",
            "public-client-123",
        ]

    def test_private_key_flag_redacted(self) -> None:
        assert self._scrub("--private-key", "-----BEGIN----") == [
            "--private-key",
            "<redacted>",
        ]

    def test_ssh_key_flag_redacted(self) -> None:
        assert self._scrub("--ssh-key=/path/to/id_rsa") == ["--ssh-key=<redacted>"]

    def test_aws_secret_access_key_flag_redacted(self) -> None:
        assert self._scrub("--aws-secret-access-key", "AKIA...") == [
            "--aws-secret-access-key",
            "<redacted>",
        ]

    def test_gh_token_flag_redacted(self) -> None:
        assert self._scrub("--gh-token", "ghp_xyz") == ["--gh-token", "<redacted>"]

    def test_flag_match_is_case_insensitive_pair_form(self) -> None:
        """Mixed-case secret flags must also be redacted; casing preserved."""
        assert self._scrub("--Access-Token", "sk-abc123") == [
            "--Access-Token",
            "<redacted>",
        ]

    def test_flag_match_is_case_insensitive_equals_form(self) -> None:
        assert self._scrub("--TOKEN=abc") == ["--TOKEN=<redacted>"]

    def test_env_var_style_token_redacted(self) -> None:
        assert self._scrub("SPEC_KITTY_TOKEN=foo") == ["SPEC_KITTY_TOKEN=<redacted>"]

    def test_env_var_style_github_token_redacted(self) -> None:
        assert self._scrub("GITHUB_TOKEN=bar") == ["GITHUB_TOKEN=<redacted>"]

    def test_env_var_style_api_key_redacted(self) -> None:
        assert self._scrub("OPENAI_API_KEY=sk-live-zzz") == [
            "OPENAI_API_KEY=<redacted>",
        ]

    def test_env_var_style_secret_redacted(self) -> None:
        assert self._scrub("DJANGO_SECRET=shh") == ["DJANGO_SECRET=<redacted>"]

    def test_env_var_style_password_redacted(self) -> None:
        assert self._scrub("DB_PASSWORD=hunter2") == ["DB_PASSWORD=<redacted>"]

    def test_env_var_style_passphrase_redacted(self) -> None:
        assert self._scrub("GPG_PASSPHRASE=open-sesame") == [
            "GPG_PASSPHRASE=<redacted>",
        ]

    def test_env_var_style_non_secret_passes_through(self) -> None:
        """Control case: env-style items that don't end in a sensitive
        suffix must NOT be redacted. ``GITHUB_USERNAME`` is public."""
        assert self._scrub("GITHUB_USERNAME=robert") == ["GITHUB_USERNAME=robert"]

    def test_combined_real_world_argv(self) -> None:
        """End-to-end check from the PR #1031 acceptance criterion."""
        out = self._scrub(
            "--access-token",
            "sk-abc123",
            "--refresh-token=xyz",
            "SPEC_KITTY_TOKEN=foo",
            "GITHUB_TOKEN=bar",
            "GITHUB_USERNAME=robert",
        )
        assert out == [
            "--access-token",
            "<redacted>",
            "--refresh-token=<redacted>",
            "SPEC_KITTY_TOKEN=<redacted>",
            "GITHUB_TOKEN=<redacted>",
            "GITHUB_USERNAME=robert",
        ]


# ---------------------------------------------------------------------------
# Mission 8 (#930) — expanded repair manifest fields
# ---------------------------------------------------------------------------


def _minimal_mission(repo: Path, slug: str = "999-mini") -> None:
    """Create a minimal mission directory the repair_repo will accept."""
    mission = repo / "kitty-specs" / slug
    mission.mkdir(parents=True, exist_ok=True)
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Mini",
            "mission_number": int(slug.split("-")[0]),
            "mission_slug": slug,
            "mission_type": "software-dev",
            "slug": slug,
            "target_branch": "main",
        },
    )
    (mission / "status.events.jsonl").write_text("", encoding="utf-8")


def test_manifest_includes_cli_version_command_args_generated_ids_policy(
    tmp_path: Path,
) -> None:
    """All four Mission-8 manifest fields must be present, typed correctly,
    and round-trip through to_json/JSON parse."""
    repo = tmp_path
    _minimal_mission(repo, "001-fields")
    _init_git_repo(repo)

    report = repair_repo(repo)

    # In-memory shape
    assert isinstance(report.cli_version, str)
    assert report.cli_version  # non-empty
    assert isinstance(report.command_args, list)
    assert all(isinstance(item, str) for item in report.command_args)
    assert isinstance(report.generated_ids, list)
    assert all(isinstance(item, str) for item in report.generated_ids)
    assert report.run_id in report.generated_ids
    assert isinstance(report.policy, dict)
    assert set(report.policy.keys()) == {"tracked", "optional", "ignored"}
    for key, value in report.policy.items():
        assert isinstance(value, list), f"policy[{key!r}] must be a list"
        assert value == sorted(value), f"policy[{key!r}] must be sorted"

    # On-disk manifest matches the in-memory report
    manifest_files = sorted((repo / ".kittify" / "migrations" / "mission-state").glob("*.json"))
    assert manifest_files, "manifest file must be written to disk"
    persisted = _read_json(manifest_files[-1])

    assert persisted["cli_version"] == report.cli_version
    assert persisted["command_args"] == report.command_args
    assert persisted["generated_ids"] == report.generated_ids
    assert persisted["policy"] == report.policy

    # Pre-existing keys still present and shaped correctly
    for key in (
        "schema_version",
        "run_id",
        "repo_head",
        "target_missions",
        "manifest_path",
        "summary",
        "missions",
    ):
        assert key in persisted, f"pre-existing manifest key {key!r} missing"
    assert isinstance(persisted["summary"], dict)
    assert isinstance(persisted["missions"], list)


def test_manifest_command_args_are_scrubbed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hostile sys.argv must never make it into the manifest verbatim."""
    repo = tmp_path
    _minimal_mission(repo, "002-scrub")
    _init_git_repo(repo)

    hostile = [
        "spec-kitty",
        "doctor",
        "mission-state",
        "--fix",
        "--token",
        "supersecret",
        "--api-key=sk-live-AAAAAAAAAAAAAAAA",
        "ghp_" + "C" * 40,
    ]
    monkeypatch.setattr("sys.argv", hostile)

    report = repair_repo(repo)

    # No raw secret should appear anywhere in command_args
    joined = "\n".join(report.command_args)
    assert "supersecret" not in joined
    assert "sk-live-AAAAAAAAAAAAAAAA" not in joined
    assert "ghp_CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC" not in joined
    # The scrubbed marker must be present in at least one slot
    assert any("<redacted>" in arg for arg in report.command_args)
    # The flag names themselves are preserved so reviewers know what was passed
    assert "--token" in report.command_args
    assert any(arg.startswith("--api-key") for arg in report.command_args)


def test_manifest_top_level_keys_remain_sorted(tmp_path: Path) -> None:
    """``to_json`` must emit top-level keys in sorted order."""
    repo = tmp_path
    _minimal_mission(repo, "003-sortkeys")
    _init_git_repo(repo)

    report = repair_repo(repo)
    rendered = report.to_json()
    parsed = json.loads(rendered)
    assert list(parsed.keys()) == sorted(parsed.keys())


# ---------------------------------------------------------------------------
# FR-001 traversal guard — mission_slug from meta.json rejected in quarantine path (WP03)
# ---------------------------------------------------------------------------


def test_repair_rejects_traversal_mission_slug_from_meta(tmp_path: Path) -> None:
    """A traversal mission_slug read from meta.json must raise ValueError before
    writing the quarantine path.

    Mutation check: removing assert_safe_path_segment from the quarantine-path
    block in _repair_mission would cause this test to fail (no ValueError raised).

    The test injects a traversal mission_slug via meta.json and ensures that
    when quarantine rows are produced, repair_repo raises ValueError rather than
    writing an escaped path.
    """
    repo = tmp_path
    # Use a valid directory name so the mission dir is discovered
    mission_dir = repo / "kitty-specs" / "safe-mission-slug"
    mission_dir.mkdir(parents=True)

    # Write meta.json with a traversal mission_slug (untrusted content from disk)
    _write_json(
        mission_dir / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "mission_slug": "../../escaped",  # traversal slug in untrusted meta content
            "mission_type": "software-dev",
            "friendly_name": "Test",
            "target_branch": "main",
        },
    )

    # Write a typed event row (event_type present) which the repair quarantines
    # (see _rule_filter_typed_rows in mission_state.py).
    # This ensures quarantine_lines is non-empty, triggering the slug validation
    # in the quarantine path code.
    status_row: dict[str, Any] = {
        "actor": "test",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AAAA",
        "execution_mode": "worktree",
        "feature_slug": "safe-mission-slug",
        "force": False,
        "from_lane": "planned",
        "to_lane": "claimed",
        "wp_id": "WP01",
    }
    # A typed side-log row with an event_type OUTSIDE the shared
    # AUTHORITATIVE_NON_LANE_EVENT_TYPES registry (#4897) → still quarantined
    # by _rule_reject_non_status_event (a DecisionPointOpened row would no
    # longer be, since it is now preserved in place as authoritative).
    typed_row: dict[str, Any] = {
        "at": "2026-01-01T00:00:01+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52BBBB",
        "event_type": "SomeUnrecognizedSideLogEvent",
        "payload": {"detail": "unrelated side log"},
    }
    (mission_dir / "status.events.jsonl").write_text(
        json.dumps(status_row, sort_keys=True) + "\n" + json.dumps(typed_row, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _init_git_repo(repo)

    # The traversal slug causes assert_safe_path_segment to raise ValueError inside
    # _repair_mission.  Because _repair_mission catches all exceptions and returns
    # a MissionRepairResult with status="error", repair_repo completes without
    # propagating the exception.  Verify that:
    #   (a) the mission result carries status="error" (guard fired)
    #   (b) no file was written at an escaped path outside the repo root.
    result = repair_repo(repo)

    assert len(result.missions) == 1, "Expected exactly one mission result"
    mission_result = result.missions[0]
    assert mission_result.status == "error", f"Expected error status when traversal slug fires guard, got: {mission_result.status!r}"
    # The validation_errors list must contain the slug-validation message
    assert any("safe path segment" in e or "traversal" in e for e in mission_result.validation_errors), (
        f"Expected traversal-guard error in validation_errors, got: {mission_result.validation_errors}"
    )

    # Verify nothing was written at an escaped path
    quarantine_root = repo / ".kittify" / "migrations" / "mission-state" / "quarantine"
    if quarantine_root.exists():
        for path in quarantine_root.rglob("*"):
            assert ".." not in str(path.relative_to(repo)), f"Escaped path found: {path}"


def test_repair_preserves_review_result_on_in_review_transitions(tmp_path: Path) -> None:
    """``review_result`` must survive the canonical rebuild (#3003 corpus regression).

    ``review_result`` is a first-class ``StatusEvent`` field and a hard FSM guard
    input: every transition out of ``in_review`` is rejected without it. Dropping
    it during repair silently converts valid history into events the reducer can
    no longer validate.
    """
    repo = tmp_path
    mission = repo / "kitty-specs" / "001-reviewed"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Reviewed",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-reviewed",
            "mission_type": "software-dev",
            "slug": "001-reviewed",
            "target_branch": "main",
        },
    )
    review_result = {
        "reference": "APPROVE: all criteria met",
        "reviewer": "reviewer-renata",
        "verdict": "approved",
    }
    (mission / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "codex",
                "at": "2026-01-01T00:00:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "in_review",
                "mission_id": mission_id,
                "mission_slug": "001-reviewed",
                "policy_metadata": None,
                "reason": None,
                "review_ref": "APPROVE: all criteria met",
                "review_result": review_result,
                "evidence": None,
                "to_lane": "approved",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    repair_repo(repo)

    rows = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0].get("review_result") == review_result


def test_canonical_row_allowlist_covers_every_status_event_field() -> None:
    """``_build_canonical_row`` is a closed allowlist over ``StatusEvent``.

    Any field added to the model but not to the allowlist is dropped silently,
    with no error, no action string and no quarantine (#3003). This gate makes
    that failure mode impossible to reintroduce unnoticed.
    """
    from dataclasses import fields

    from specify_cli.migration.mission_state import _build_canonical_row
    from specify_cli.status.models import StatusEvent

    row = {
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "mission_slug": "001-x",
        "wp_id": "WP01",
        "from_lane": "in_review",
        "to_lane": "approved",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "codex",
        "force": False,
        "execution_mode": "worktree",
    }
    canonical = _build_canonical_row(row, "01KQHRB8GCFJAX7HM4ZY52AQGR")

    assert {f.name for f in fields(StatusEvent)} <= set(canonical)


def test_repair_orders_lifecycle_rows_by_timestamp_not_to_the_top(tmp_path: Path) -> None:
    """Rows carrying ``timestamp`` (not ``at``) must not be hoisted to the head.

    Lifecycle rows use a ``timestamp`` envelope. Sorting solely on ``at`` maps
    them all to ``""``, which reorders an append-only log (#3003).
    """
    repo = tmp_path
    mission = repo / "kitty-specs" / "001-ordered"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Ordered",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-ordered",
            "mission_type": "software-dev",
            "slug": "001-ordered",
            "target_branch": "main",
        },
    )
    lane_row = {
        "actor": "codex",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "planned",
        "mission_id": mission_id,
        "mission_slug": "001-ordered",
        "to_lane": "claimed",
        "wp_id": "WP01",
    }
    lifecycle_row = {
        "aggregate_id": "001-ordered",
        "aggregate_type": "Mission",
        "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGT",
        "event_type": "WPCreated",
        "payload": {"mission_slug": "001-ordered"},
        "timestamp": "2026-06-01T00:00:00Z",
    }
    (mission / "status.events.jsonl").write_text(
        json.dumps(lane_row, sort_keys=True) + "\n" + json.dumps(lifecycle_row, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    repair_repo(repo)

    rows = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    # The lifecycle row is chronologically later; it must stay last.
    assert [r.get("event_type", "lane") for r in rows] == ["lane", "WPCreated"]


def test_repair_quarantines_dropped_duplicate_event_rows(tmp_path: Path) -> None:
    """A dropped duplicate ``event_id`` row must be quarantined, not just hashed.

    Divergent duplicates would otherwise be deleted from an append-only log with
    only a sha256 left as evidence (#3003).
    """
    repo = tmp_path
    mission = repo / "kitty-specs" / "001-dup"
    mission.mkdir(parents=True)
    mission_id = "01KQHRB8GCFJAX7HM4ZY52AQGR"
    _write_json(
        mission / "meta.json",
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "friendly_name": "Dup",
            "mission_id": mission_id,
            "mission_number": 1,
            "mission_slug": "001-dup",
            "mission_type": "software-dev",
            "slug": "001-dup",
            "target_branch": "main",
        },
    )

    def _row(reason: str) -> str:
        return json.dumps(
            {
                "actor": "codex",
                "at": "2026-01-01T00:00:00+00:00",
                "event_id": "01KQHRB8GCFJAX7HM4ZY52AQGS",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "planned",
                "mission_id": mission_id,
                "mission_slug": "001-dup",
                "reason": reason,
                "to_lane": "claimed",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )

    # Second row shares the event_id but DIVERGES in payload.
    (mission / "status.events.jsonl").write_text(_row("original") + "\n" + _row("divergent") + "\n", encoding="utf-8")

    repair_repo(repo)

    rows = [line for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1

    quarantined = list((repo / ".kittify" / "migrations" / "mission-state" / "quarantine").rglob("*"))
    quarantined_text = "\n".join(p.read_text(encoding="utf-8") for p in quarantined if p.is_file())
    assert "divergent" in quarantined_text
