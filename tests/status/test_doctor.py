"""Tests for the status doctor health check framework."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from kernel.clock import now_utc, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.runtime.doctor import DoctorCheck
from specify_cli.status.doctor import (
    Category,
    DoctorResult,
    Finding,
    Severity,
    check_drift,
    check_issue_matrix,
    check_orphan_workspaces,
    check_wp_file_reconciliation,
    check_reviewer_self_approval,
    check_sparse_checkout,
    check_stale_claims,
    run_doctor,
)
from specify_cli.status.lifecycle_events import emit_reviewer_self_approval

pytestmark = pytest.mark.fast


def _create_events_file(
    feature_dir: Path,
    wp_states: dict[str, str],
    timestamp: str,
    mission_slug: str = "034-test",
    *,
    create_prompts: bool = True,
) -> None:
    """Create a minimal status.events.jsonl matching the given WP states.

    Prevents doctor from flagging 'status.json exists but events file missing'.
    """
    events = []
    for wp_id, lane in wp_states.items():
        events.append(
            json.dumps(
                {
                    "event_id": f"01EVT{wp_id}",
                    "mission_slug": mission_slug,
                    "wp_id": wp_id,
                    "from_lane": "planned",
                    "to_lane": lane,
                    "at": timestamp,
                    "actor": "agent",
                    "force": False,
                    "execution_mode": "worktree",
                }
            )
        )
    (feature_dir / "status.events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
    if create_prompts:
        for wp_id in wp_states:
            _create_wp_prompt(feature_dir, wp_id)


def _create_wp_prompt(feature_dir: Path, wp_id: str) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / f"{wp_id}-work.md").write_text(f"---\nwork_package_id: {wp_id}\n---\n", encoding="utf-8")


def _healthy_global_checks() -> list[DoctorCheck]:
    """Return deterministic pass-state global checks for CLI unit tests."""
    return [
        DoctorCheck(
            name="global_runtime_exists",
            passed=True,
            message="global runtime ready",
            severity="info",
        ),
        DoctorCheck(
            name="version_lock",
            passed=True,
            message="version lock matches",
            severity="info",
        ),
        DoctorCheck(
            name="mission_integrity",
            passed=True,
            message="mission directories present",
            severity="info",
        ),
        DoctorCheck(
            name="stale_legacy",
            passed=True,
            message="no stale assets",
            severity="info",
        ),
        DoctorCheck(
            name="governance_resolution",
            passed=True,
            message="governance resolved",
            severity="info",
        ),
    ]


# ---------------------------------------------------------------------------
# DoctorResult and Finding dataclass tests
# ---------------------------------------------------------------------------


class TestFinding:
    """Tests for the Finding dataclass."""

    def test_finding_construction(self):
        finding = Finding(
            severity=Severity.WARNING,
            category=Category.STALE_CLAIM,
            wp_id="WP01",
            message="Test message",
            recommended_action="Test action",
        )
        assert finding.severity == Severity.WARNING
        assert finding.category == Category.STALE_CLAIM
        assert finding.wp_id == "WP01"
        assert finding.message == "Test message"
        assert finding.recommended_action == "Test action"

    def test_finding_with_none_wp_id(self):
        finding = Finding(
            severity=Severity.ERROR,
            category=Category.ORPHAN_WORKSPACE,
            wp_id=None,
            message="Orphan detected",
            recommended_action="Clean up",
        )
        assert finding.wp_id is None


class TestDoctorResult:
    """Tests for the DoctorResult dataclass."""

    def test_healthy_result(self):
        result = DoctorResult(mission_slug="034-test")
        assert result.is_healthy is True
        assert result.has_errors is False
        assert result.has_warnings is False
        assert result.findings == []

    def test_result_with_warnings(self):
        result = DoctorResult(
            mission_slug="034-test",
            findings=[
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id="WP01",
                    message="stale",
                    recommended_action="fix",
                ),
            ],
        )
        assert result.is_healthy is False
        assert result.has_warnings is True
        assert result.has_errors is False

    def test_result_with_errors(self):
        result = DoctorResult(
            mission_slug="034-test",
            findings=[
                Finding(
                    severity=Severity.ERROR,
                    category=Category.MATERIALIZATION_DRIFT,
                    wp_id=None,
                    message="drift",
                    recommended_action="fix",
                ),
            ],
        )
        assert result.is_healthy is False
        assert result.has_errors is True

    def test_result_with_mixed_severity(self):
        result = DoctorResult(
            mission_slug="034-test",
            findings=[
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id="WP01",
                    message="stale",
                    recommended_action="fix",
                ),
                Finding(
                    severity=Severity.ERROR,
                    category=Category.MATERIALIZATION_DRIFT,
                    wp_id=None,
                    message="drift",
                    recommended_action="fix",
                ),
            ],
        )
        assert result.has_warnings is True
        assert result.has_errors is True

    def test_findings_by_category(self):
        result = DoctorResult(
            mission_slug="034-test",
            findings=[
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id="WP01",
                    message="stale claim",
                    recommended_action="fix",
                ),
                Finding(
                    severity=Severity.WARNING,
                    category=Category.ORPHAN_WORKSPACE,
                    wp_id=None,
                    message="orphan",
                    recommended_action="clean",
                ),
                Finding(
                    severity=Severity.WARNING,
                    category=Category.STALE_CLAIM,
                    wp_id="WP02",
                    message="another stale",
                    recommended_action="fix",
                ),
            ],
        )
        stale = result.findings_by_category(Category.STALE_CLAIM)
        assert len(stale) == 2
        orphan = result.findings_by_category(Category.ORPHAN_WORKSPACE)
        assert len(orphan) == 1
        drift = result.findings_by_category(Category.MATERIALIZATION_DRIFT)
        assert len(drift) == 0


# ---------------------------------------------------------------------------
# Severity and Category enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_severity_values(self):
        assert Severity.WARNING == "warning"
        assert Severity.ERROR == "error"

    def test_category_values(self):
        assert Category.STALE_CLAIM == "stale_claim"
        assert Category.ORPHAN_WORKSPACE == "orphan_workspace"
        assert Category.MATERIALIZATION_DRIFT == "materialization_drift"
        assert Category.DERIVED_VIEW_DRIFT == "derived_view_drift"
        assert Category.REVIEW_INDEPENDENCE == "review_independence"
        assert Category.ISSUE_MATRIX == "issue_matrix"


def test_check_reviewer_self_approval_reports_independence_risk(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    emit_reviewer_self_approval(
        feature_dir,
        mission_slug="034-test",
        wp_id="WP02",
        implementing_actor="codex:gpt-5:implementer",
        intended_reviewer="claude:sonnet:reviewer",
        failure_reason="exit 1",
    )

    findings = check_reviewer_self_approval(feature_dir)

    assert len(findings) == 1
    assert findings[0].category == Category.REVIEW_INDEPENDENCE
    assert findings[0].wp_id == "WP02"
    assert "self-review fallback" in findings[0].message


def test_check_issue_matrix_reports_missing_and_unknown(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Addresses Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    missing = check_issue_matrix(feature_dir)
    assert len(missing) == 1
    assert missing[0].category == Category.ISSUE_MATRIX
    assert "#1582" in missing[0].message

    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue | verdict | evidence_ref |",
                "| --- | --- | --- |",
                "| #1582 | unknown | tests/test_demo.py |",
            ]
        ),
        encoding="utf-8",
    )
    unresolved = check_issue_matrix(feature_dir)
    assert len(unresolved) == 1
    assert "verdict 'unknown'" in unresolved[0].message

    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue | verdict | evidence_ref |",
                "| --- | --- | --- |",
                "| #1111 | fixed | tests/test_demo.py |",
            ]
        ),
        encoding="utf-8",
    )
    missing_row = check_issue_matrix(feature_dir)
    assert len(missing_row) == 1
    assert "missing rows" in missing_row[0].message
    assert "#1582" in missing_row[0].message


def test_check_issue_matrix_reports_evaluation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Addresses Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    def _boom(_path: Path):
        raise RuntimeError("parser unavailable")

    monkeypatch.setattr("specify_cli.tasks.issue_matrix.detect_issue_references", _boom)

    findings = check_issue_matrix(feature_dir)

    assert len(findings) == 1
    assert findings[0].category == Category.ISSUE_MATRIX
    assert "could not be evaluated" in findings[0].message
    assert "parser unavailable" in findings[0].message


def test_check_issue_matrix_no_refs_is_clean(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("No GitHub issue references here.\n", encoding="utf-8")

    assert check_issue_matrix(feature_dir) == []


def test_check_issue_matrix_discovers_reference_only_in_wp_file(tmp_path: Path) -> None:
    """WP08/T029/FR-004: a ref buried in ``tasks/WP01.md`` alone is discovered.

    Prior to the multi-file discovery module, ``check_issue_matrix`` only
    ever scanned ``spec.md``, so an issue referenced solely inside a WP
    prompt file was invisible to this health check.
    """
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("No GitHub issue references here.\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text("This WP fixes #7777.\n", encoding="utf-8")

    findings = check_issue_matrix(feature_dir)

    assert len(findings) == 1
    assert "#7777" in findings[0].message


def test_check_issue_matrix_json_only_mission_is_not_falsely_flagged_missing(
    tmp_path: Path,
) -> None:
    """WP08/T043 (C-008/B-1): a JSON-only matrix is no longer a false "missing".

    Before the reader switch, the ``.md``-only ``.exists()`` precheck made a
    greenfield JSON-only mission (B3) look like the issue-matrix was
    missing, even though ``issue-matrix.json`` already carried the row.
    """
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Addresses issue #1582.\n", encoding="utf-8")
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {
                    "#1582": {
                        "verdict": "fixed",
                        "evidence_ref": "tests/test_demo.py",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert check_issue_matrix(feature_dir) == []


# ---------------------------------------------------------------------------
# check_stale_claims tests
# ---------------------------------------------------------------------------


class TestCheckStaleClaims:
    """Tests for stale claim detection."""

    def _make_snapshot(self, wp_states: dict) -> dict:
        """Helper to create a snapshot dict."""
        return {"work_packages": wp_states}

    def test_stale_claimed_detected(self, tmp_path: Path):
        """WP in claimed for 10 days with threshold 7 -> finding."""
        ten_days_ago = (now_utc() - timedelta(days=10)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "claude-agent",
                    "last_transition_at": ten_days_ago,
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot, claimed_threshold_days=7)
        assert len(findings) == 1
        assert findings[0].category == Category.STALE_CLAIM
        assert findings[0].wp_id == "WP01"
        assert "claimed" in findings[0].message
        assert "10 days" in findings[0].message
        assert "claude-agent" in findings[0].message

    def test_stale_in_progress_detected(self, tmp_path: Path):
        """WP in in_progress for 20 days with threshold 14 -> finding."""
        twenty_days_ago = (now_utc() - timedelta(days=20)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP02": {
                    "lane": "in_progress",
                    "actor": "codex-agent",
                    "last_transition_at": twenty_days_ago,
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot, in_progress_threshold_days=14)
        assert len(findings) == 1
        assert findings[0].wp_id == "WP02"
        assert "in_progress" in findings[0].message
        assert "20 days" in findings[0].message

    def test_no_stale_within_threshold(self, tmp_path: Path):
        """WP in claimed for 3 days with threshold 7 -> no finding."""
        three_days_ago = (now_utc() - timedelta(days=3)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": three_days_ago,
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot, claimed_threshold_days=7)
        assert len(findings) == 0

    def test_non_active_lanes_are_never_stale(self, tmp_path: Path):
        """Only claimed/in-progress lanes participate in stale detection."""
        hundred_days_ago = (now_utc() - timedelta(days=100)).isoformat()
        counts = {}
        for lane in ("done", "canceled", "blocked", "for_review"):
            snapshot = self._make_snapshot(
                {
                    "WP01": {
                        "lane": lane,
                        "actor": "agent",
                        "last_transition_at": hundred_days_ago,
                    }
                }
            )
            counts[lane] = len(check_stale_claims(tmp_path, snapshot))

        assert counts == {"done": 0, "canceled": 0, "blocked": 0, "for_review": 0}

    def test_custom_thresholds(self, tmp_path: Path):
        """Custom thresholds are respected."""
        two_days_ago = (now_utc() - timedelta(days=2)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": two_days_ago,
                }
            }
        )
        # With default threshold (7 days), no finding
        findings_default = check_stale_claims(tmp_path, snapshot)
        assert len(findings_default) == 0

        # With custom threshold (1 day), finding
        findings_custom = check_stale_claims(tmp_path, snapshot, claimed_threshold_days=1)
        assert len(findings_custom) == 1

    def test_missing_last_transition_at(self, tmp_path: Path):
        """WP without last_transition_at is skipped, no crash."""
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot)
        assert len(findings) == 0

    def test_malformed_timestamp(self, tmp_path: Path):
        """WP with malformed timestamp is skipped, no crash."""
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": "not-a-date",
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot)
        assert len(findings) == 0

    def test_empty_work_packages(self, tmp_path: Path):
        """Empty work_packages dict -> no findings."""
        snapshot = self._make_snapshot({})
        findings = check_stale_claims(tmp_path, snapshot)
        assert len(findings) == 0

    def test_multiple_stale_wps(self, tmp_path: Path):
        """Multiple stale WPs produce multiple findings."""
        old = (now_utc() - timedelta(days=15)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "actor": "a1",
                    "last_transition_at": old,
                },
                "WP02": {
                    "lane": "in_progress",
                    "actor": "a2",
                    "last_transition_at": old,
                },
                "WP03": {
                    "lane": "done",
                    "actor": "a3",
                    "last_transition_at": old,
                },
            }
        )
        findings = check_stale_claims(
            tmp_path,
            snapshot,
            claimed_threshold_days=7,
            in_progress_threshold_days=14,
        )
        assert len(findings) == 2
        wp_ids = {f.wp_id for f in findings}
        assert wp_ids == {"WP01", "WP02"}

    def test_actor_unknown_when_missing(self, tmp_path: Path):
        """Actor defaults to 'unknown' in message when not in snapshot."""
        old = (now_utc() - timedelta(days=10)).isoformat()
        snapshot = self._make_snapshot(
            {
                "WP01": {
                    "lane": "claimed",
                    "last_transition_at": old,
                }
            }
        )
        findings = check_stale_claims(tmp_path, snapshot, claimed_threshold_days=7)
        assert len(findings) == 1
        assert "unknown" in findings[0].message


# ---------------------------------------------------------------------------
# check_orphan_workspaces tests
# ---------------------------------------------------------------------------


class TestCheckOrphanWorkspaces:
    """Tests for orphan workspace detection."""

    def test_orphan_worktree_detected(self, tmp_path: Path):
        """All WPs done + worktree exists -> finding."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "034-test-feature-lane-a").mkdir()
        (worktrees_dir / "034-test-feature-lane-b").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
                "WP02": {"lane": "done"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 2
        assert all(f.category == Category.ORPHAN_WORKSPACE for f in findings)

    def test_no_orphan_active_wps(self, tmp_path: Path):
        """Worktree exists, but WP01 is still in_progress -> no finding."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "034-test-feature-lane-a").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "in_progress"},
                "WP02": {"lane": "done"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 0

    def test_no_worktrees_directory(self, tmp_path: Path):
        """No .worktrees/ directory -> no finding."""
        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 0

    def test_mixed_terminal_states(self, tmp_path: Path):
        """Some done, some canceled (all terminal) + worktree -> finding."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "034-test-feature-lane-a").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
                "WP02": {"lane": "canceled"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 1

    def test_empty_work_packages(self, tmp_path: Path):
        """Empty work_packages -> no findings."""
        snapshot = {"work_packages": {}}
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 0

    def test_worktree_file_not_dir_ignored(self, tmp_path: Path):
        """Worktree path that is a file (not directory) is filtered out."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        # Create a file, not a directory
        (worktrees_dir / "034-test-feature-lane-a").write_text("not a dir")

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 0

    def test_unrelated_worktrees_not_flagged(self, tmp_path: Path):
        """Worktrees for other features are not flagged."""
        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "999-other-feature-lane-a").mkdir()

        snapshot = {
            "work_packages": {
                "WP01": {"lane": "done"},
            }
        }
        findings = check_orphan_workspaces(tmp_path, "034-test-feature", snapshot)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# check_drift tests
# ---------------------------------------------------------------------------


class TestCheckDrift:
    """Tests for drift detection delegation."""

    def test_no_validation_engine_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When validation engine is not available -> empty findings, no crash."""
        # The default state is that specify_cli.status.validate doesn't exist.
        # We patch the import to raise ImportError.  A None sys.modules entry forces
        # ImportError on import; single-key setitem keeps teardown eviction-free (#89/#99).
        monkeypatch.setitem(sys.modules, "specify_cli.status.validate", None)
        findings = check_drift(tmp_path)
        assert findings == []

    def test_import_error_graceful(self, tmp_path: Path):
        """ImportError during validation import -> empty findings."""
        # This is the natural case - WP11 not merged yet
        findings = check_drift(tmp_path)
        assert findings == []


# ---------------------------------------------------------------------------
# check_sparse_checkout tests
# ---------------------------------------------------------------------------


class TestCheckSparseCheckout:
    def test_import_error_returns_empty(self, tmp_path: Path):
        real_import = __import__

        def fake_import(name, *args, **kwargs):  # noqa: ANN001
            if name == "specify_cli.git.sparse_checkout":
                raise ImportError("missing sparse-checkout module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert check_sparse_checkout(tmp_path) == []

    def test_scan_failure_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        fake_module = SimpleNamespace(scan_repo=lambda _repo_root: (_ for _ in ()).throw(RuntimeError("boom")))

        # setitem rather than a whole-dict sys.modules mock: teardown restores exactly
        # this one key, so modules first-imported in the window are not evicted (#89/#99).
        monkeypatch.setitem(sys.modules, "specify_cli.git.sparse_checkout", fake_module)
        assert check_sparse_checkout(tmp_path) == []

    def test_inactive_repo_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        fake_report = SimpleNamespace(any_active=False, any_blocking=False)
        fake_module = SimpleNamespace(scan_repo=lambda _repo_root: fake_report)

        monkeypatch.setitem(sys.modules, "specify_cli.git.sparse_checkout", fake_module)
        assert check_sparse_checkout(tmp_path) == []

    def test_active_primary_and_worktree_emit_finding(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        primary_pattern = tmp_path / ".git" / "info" / "sparse-checkout"
        primary = SimpleNamespace(
            is_active=True,
            is_blocking=True,
            path=tmp_path,
            pattern_file_present=True,
            pattern_file_path=primary_pattern,
            pattern_line_count=3,
        )
        lane_path = tmp_path / ".worktrees" / "mission-lane-a"
        lane = SimpleNamespace(is_active=True, is_blocking=True, path=lane_path)
        fake_report = SimpleNamespace(
            any_active=True,
            any_blocking=True,
            affected_paths=(tmp_path, lane_path),
            primary=primary,
            worktrees=(lane,),
        )
        fake_module = SimpleNamespace(scan_repo=lambda _repo_root: fake_report)

        monkeypatch.setitem(sys.modules, "specify_cli.git.sparse_checkout", fake_module)
        findings = check_sparse_checkout(tmp_path)

        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == Severity.WARNING
        assert finding.category == Category.SPARSE_CHECKOUT
        assert f"Primary: {tmp_path}" in finding.message
        assert str(primary_pattern) in finding.message
        assert "Lane worktrees affected: 1" in finding.message
        assert str(lane_path) in finding.message
        assert "spec-kitty/spec-kitty#588" in finding.message
        assert "spec-kitty doctor sparse-checkout --fix" in finding.recommended_action
        assert str(tmp_path) in finding.recommended_action
        assert str(lane_path) in finding.recommended_action


# ---------------------------------------------------------------------------
# run_doctor integration tests
# ---------------------------------------------------------------------------


class TestRunDoctor:
    """Tests for the main run_doctor entry point."""

    def test_feature_dir_not_exist_raises(self, tmp_path: Path):
        """Feature directory does not exist -> FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError, match="does not exist"):
            run_doctor(
                feature_dir=nonexistent,
                mission_slug="034-test",
                repo_root=tmp_path,
            )

    def test_clean_feature_healthy(self, tmp_path: Path):
        """Feature with no events and no status.json -> healthy (nothing to check)."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
        )
        assert result.is_healthy is True
        assert result.mission_slug == "034-test"

    def test_healthy_feature_with_active_wps(self, tmp_path: Path):
        """Active WPs within thresholds, no worktrees -> healthy."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        recent = (now_utc() - timedelta(hours=1)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": recent,
            "event_count": 2,
            "last_event_id": "01ABC",
            "work_packages": {
                "WP01": {
                    "lane": "in_progress",
                    "actor": "agent",
                    "last_transition_at": recent,
                    "last_event_id": "01ABC",
                    "force_count": 0,
                },
            },
            "summary": {"in_progress": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        # Doctor checks for events file existence alongside status.json
        events = [
            json.dumps(
                {
                    "event_id": "01AAA",
                    "mission_slug": "034-test",
                    "wp_id": "WP01",
                    "from_lane": "planned",
                    "to_lane": "claimed",
                    "at": recent,
                    "actor": "agent",
                    "force": False,
                    "execution_mode": "worktree",
                }
            ),
            json.dumps(
                {
                    "event_id": "01ABC",
                    "mission_slug": "034-test",
                    "wp_id": "WP01",
                    "from_lane": "claimed",
                    "to_lane": "in_progress",
                    "at": recent,
                    "actor": "agent",
                    "force": False,
                    "execution_mode": "worktree",
                }
            ),
        ]
        (feature_dir / "status.events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
        _create_wp_prompt(feature_dir, "WP01")

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
        )
        assert result.is_healthy is True

    def test_stale_claim_detected_via_status_json(self, tmp_path: Path):
        """Stale claimed WP detected via status.json."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        old = (now_utc() - timedelta(days=10)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": old,
            "event_count": 1,
            "last_event_id": "01ABC",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": old,
                    "last_event_id": "01ABC",
                    "force_count": 0,
                },
            },
            "summary": {"claimed": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        # Create events file so doctor doesn't flag missing events
        events = [
            json.dumps(
                {
                    "event_id": "01ABC",
                    "mission_slug": "034-test",
                    "wp_id": "WP01",
                    "from_lane": "planned",
                    "to_lane": "claimed",
                    "at": old,
                    "actor": "agent",
                    "force": False,
                    "execution_mode": "worktree",
                }
            ),
        ]
        (feature_dir / "status.events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
        _create_wp_prompt(feature_dir, "WP01")

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
            stale_claimed_days=7,
        )
        assert result.is_healthy is False
        assert result.has_warnings is True
        assert len(result.findings) == 1
        assert result.findings[0].category == Category.STALE_CLAIM

    def test_orphan_detected_via_status_json(self, tmp_path: Path):
        """Orphan worktree detected when all WPs are terminal."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "034-test-lane-a").mkdir()

        status_data = {
            "mission_slug": "034-test",
            "materialized_at": "2026-01-01T00:00:00Z",
            "event_count": 1,
            "last_event_id": "01ABC",
            "work_packages": {
                "WP01": {
                    "lane": "done",
                    "actor": "reviewer",
                    "last_transition_at": "2026-01-01T00:00:00Z",
                    "last_event_id": "01ABC",
                    "force_count": 0,
                },
            },
            "summary": {"done": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "done"}, "2026-01-01T00:00:00Z")

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
        )
        assert result.is_healthy is False
        assert len(result.findings_by_category(Category.ORPHAN_WORKSPACE)) == 1

    def test_stale_and_orphan_combined(self, tmp_path: Path):
        """Multiple issues detected in a single doctor run."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        worktrees_dir = tmp_path / ".worktrees"
        worktrees_dir.mkdir()
        (worktrees_dir / "034-other-lane-a").mkdir()

        old = (now_utc() - timedelta(days=10)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": old,
            "event_count": 2,
            "last_event_id": "01ABC",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": old,
                    "last_event_id": "01ABC",
                    "force_count": 0,
                },
                "WP02": {
                    "lane": "in_progress",
                    "actor": "agent2",
                    "last_transition_at": old,
                    "last_event_id": "01DEF",
                    "force_count": 0,
                },
            },
            "summary": {"claimed": 1, "in_progress": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "claimed", "WP02": "in_progress"}, old)

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
            stale_claimed_days=7,
            stale_in_progress_days=7,
        )
        # Should have stale claims for WP01 (claimed) and WP02 (in_progress)
        # No orphan because not all WPs are terminal
        stale_findings = [f for f in result.findings if f.category == Category.STALE_CLAIM]
        assert len(stale_findings) == 2

    def test_corrupted_status_json_returns_healthy(self, tmp_path: Path):
        """Corrupted status.json with no event log -> healthy (nothing to check)."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)
        (feature_dir / "status.json").write_text("not valid json", encoding="utf-8")

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
        )
        # snapshot is None because JSON is corrupt and no events exist
        assert result.is_healthy is True

    def test_snapshot_from_events_when_no_status_json(self, tmp_path: Path):
        """When status.json missing but events exist, snapshot is built from events."""
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        old = (now_utc() - timedelta(days=10)).isoformat()
        event = {
            "event_id": "01HXYZ0123456789ABCDEFGHJK",
            "mission_slug": "034-test",
            "wp_id": "WP01",
            "from_lane": "planned",
            "to_lane": "claimed",
            "at": old,
            "actor": "agent",
            "force": False,
            "execution_mode": "worktree",
        }
        events_file = feature_dir / "status.events.jsonl"
        events_file.write_text(json.dumps(event) + "\n", encoding="utf-8")

        result = run_doctor(
            feature_dir=feature_dir,
            mission_slug="034-test",
            repo_root=tmp_path,
            stale_claimed_days=7,
        )
        assert result.is_healthy is False
        stale_findings = [f for f in result.findings if f.category == Category.STALE_CLAIM]
        assert len(stale_findings) == 1
        assert stale_findings[0].wp_id == "WP01"


def test_doctor_reports_event_wp_without_prompt_even_when_snapshot_is_stale(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    (feature_dir / "tasks").mkdir(parents=True)
    _create_events_file(feature_dir, {"WP08": "planned"}, "2026-01-01T00:00:00Z", create_prompts=False)
    (feature_dir / "status.json").write_text(json.dumps({"work_packages": {}}), encoding="utf-8")

    result = run_doctor(feature_dir, "034-test", tmp_path)

    findings = result.findings_by_category(Category.WP_FILE_DRIFT)
    assert len(findings) == 1
    assert findings[0].wp_id == "WP08"
    assert "tasks/" in findings[0].message
    assert result.has_errors


def test_wp_reconciliation_reports_prompt_without_event_and_ignores_readme(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP02-work.md").write_text("---\nwork_package_id: WP02\n---\n", encoding="utf-8")
    (tasks_dir / "README.md").write_text("work_package_id: WP03\n", encoding="utf-8")

    findings = check_wp_file_reconciliation(tmp_path, {"WP01"})

    assert [(finding.wp_id, finding.severity) for finding in findings] == [
        ("WP01", Severity.ERROR),
        ("WP02", Severity.ERROR),
    ]


def test_doctor_reports_prompt_without_event_status(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    _create_events_file(feature_dir, {"WP01": "planned"}, "2026-01-01T00:00:00Z")
    _create_wp_prompt(feature_dir, "WP02")

    result = run_doctor(feature_dir, "034-test", tmp_path)

    findings = result.findings_by_category(Category.WP_FILE_DRIFT)
    assert [finding.wp_id for finding in findings] == ["WP02"]
    assert result.has_errors


# ---------------------------------------------------------------------------
# CLI tests (unit-level, not requiring full project)
# ---------------------------------------------------------------------------


class TestDoctorCLI:
    """Tests for the CLI doctor command."""

    def test_doctor_cli_json_output(self, tmp_path: Path):
        """CLI doctor --json produces parseable JSON."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        # Mock the resolution chain to use our temp directory
        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        recent = (now_utc() - timedelta(hours=1)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": recent,
            "event_count": 1,
            "last_event_id": "01EVTWP01",
            "work_packages": {
                "WP01": {
                    "lane": "in_progress",
                    "actor": "agent",
                    "last_transition_at": recent,
                    "last_event_id": "01EVTWP01",
                    "force_count": 0,
                },
            },
            "summary": {"in_progress": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "in_progress"}, recent)

        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result = runner.invoke(app, ["doctor", "--json"])

        # Exit code 0 for healthy
        assert result.exit_code == 0
        # Output should contain valid JSON
        output = result.output.strip()
        parsed = json.loads(output)
        assert parsed["healthy"] is True
        assert parsed["mission_slug"] == "034-test"
        assert parsed["findings"] == []

    def test_doctor_cli_healthy_exit_0(self, tmp_path: Path):
        """Healthy feature -> exit code 0."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "Healthy" in result.output

    def test_doctor_cli_issues_exit_1(self, tmp_path: Path):
        """Stale claim -> exit code 1."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        old = (now_utc() - timedelta(days=10)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": old,
            "event_count": 1,
            "last_event_id": "01EVTWP01",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": old,
                    "last_event_id": "01EVTWP01",
                    "force_count": 0,
                },
            },
            "summary": {"claimed": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "claimed"}, old)

        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 1
        assert "Issues found" in result.output

    def test_doctor_cli_json_with_findings(self, tmp_path: Path):
        """CLI --json with findings produces structured output."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        old = (now_utc() - timedelta(days=10)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": old,
            "event_count": 1,
            "last_event_id": "01EVTWP01",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": old,
                    "last_event_id": "01EVTWP01",
                    "force_count": 0,
                },
            },
            "summary": {"claimed": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "claimed"}, old)

        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result = runner.invoke(app, ["doctor", "--json"])

        assert result.exit_code == 1
        output = result.output.strip()
        parsed = json.loads(output)
        assert parsed["healthy"] is False
        assert len(parsed["findings"]) == 1
        finding = parsed["findings"][0]
        assert finding["severity"] == "warning"
        assert finding["category"] == "stale_claim"
        assert finding["wp_id"] == "WP01"
        assert "claimed" in finding["message"]
        assert finding["recommended_action"]  # Non-empty

    def test_doctor_cli_feature_flag_removed(self, tmp_path: Path):
        """`doctor` no longer accepts `--feature` (#1060-A).

        The hidden alias was retired from the internal/agent cluster (doctor
        lives in agent/status.py), so the parser now rejects `--feature` with
        exit code 2 — the old `--mission`+`--feature` JSON-conflict path is gone.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        with patch(
            "specify_cli.cli.commands.agent.status.locate_project_root",
            return_value=tmp_path,
        ):
            result = runner.invoke(
                app,
                ["doctor", "--feature", "077-b", "--json"],
            )

        assert result.exit_code == 2, result.output
        assert "No such option" in result.output

    def test_doctor_cli_feature_not_found(self, tmp_path: Path):
        """Feature directory not found -> exit code 1."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        nonexistent = tmp_path / "kitty-specs" / "999-missing"

        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(nonexistent, "999-missing", tmp_path),
            ),
        ):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_doctor_cli_custom_thresholds(self, tmp_path: Path):
        """Custom threshold flags are passed through."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent.status import app

        runner = CliRunner()

        feature_dir = tmp_path / "kitty-specs" / "034-test"
        feature_dir.mkdir(parents=True)

        # 2 days ago - below default 7-day threshold but above custom 1-day
        two_days_ago = (now_utc() - timedelta(days=2)).isoformat()
        status_data = {
            "mission_slug": "034-test",
            "materialized_at": two_days_ago,
            "event_count": 1,
            "last_event_id": "01EVTWP01",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": two_days_ago,
                    "last_event_id": "01EVTWP01",
                    "force_count": 0,
                },
            },
            "summary": {"claimed": 1},
        }
        (feature_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")
        _create_events_file(feature_dir, {"WP01": "claimed"}, two_days_ago)

        # Default threshold: healthy
        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result_default = runner.invoke(app, ["doctor", "--json"])
        assert result_default.exit_code == 0

        # Custom threshold: finding
        with (
            patch(
                "specify_cli.runtime.doctor.run_global_checks",
                return_value=_healthy_global_checks(),
            ),
            patch(
                "specify_cli.cli.commands.agent.status._resolve_status_surface",
                return_value=(feature_dir, "034-test", tmp_path),
            ),
        ):
            result_custom = runner.invoke(
                app,
                ["doctor", "--json", "--stale-claimed-days", "1"],
            )
        assert result_custom.exit_code == 1
