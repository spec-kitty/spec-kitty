"""``accept`` refuses an approved work package with no implementation or no independent review (#6715).

The preflight runs after the origin-freshness gate and before the acceptance summary is
collected, whatever ``--lenient`` says, so nothing is written on a refusal. It reads the shared
predicate (``consolidation.wp_evidence.mission_evidence_report``) that consolidate and
orchestrator-api read. ``--attest-no-implementation <WP> --attest-reason "<why>"`` records the
WP02 attestation first (validated as a whole, nothing recorded on a refusal); ``--no-commit`` and
``--diagnose`` are read-only, so they refuse the flag and still report the evidence refusal.

Only module attributes of ``specify_cli.cli.commands.accept`` are patched (the
``test_accept_decomposition`` harness plus the evidence collaborators).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from specify_cli.acceptance import AcceptanceCheckDiagnostic, AcceptanceSummary, WorkPackageState
from specify_cli.acceptance.gates_core import PLANNING_ARTIFACT_ONLY_SKIP_REASON
from specify_cli.cli.commands import accept as accept_module
from specify_cli.task_utils import LANES
from specify_cli.consolidation.canceled_attestation import AttestationError
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.consolidation.wp_evidence import EvidenceReport
from specify_cli.lanes.persistence import CorruptLanesError
from specify_cli.status import StoreError
from tests.specify_cli.cli.commands.test_accept_decomposition import _SLUG, Harness, _flat, _patch_owned_entry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REFUSAL = (
    f"Mission {_SLUG}: work packages cannot be landed as reviewed:\n"
    "IMPLEMENTATION_MISSING: WP02 was approved with no change to its owned_files in its evidence window p..b (lane-b).\n"
    "REVIEW_NOT_INDEPENDENT: WP03 was approved without a confirmable independent review."
)


def _ready_planning_summary(repo_root: Path) -> AcceptanceSummary:
    """A real serialized report with an approved planning WP and the legitimate matrix exemption."""
    mission_dir = repo_root / "kitty-specs" / _SLUG
    summary = AcceptanceSummary(
        feature=_SLUG,
        repo_root=repo_root,
        feature_dir=mission_dir,
        tasks_dir=mission_dir / "tasks",
        branch="main",
        worktree_root=repo_root,
        primary_repo_root=repo_root,
        lanes={lane: ["WP01"] if lane == "approved" else [] for lane in LANES},
        work_packages=[
            WorkPackageState(
                work_package_id="WP01",
                lane="approved",
                title="Planning deliverable",
                path=f"kitty-specs/{_SLUG}/tasks/WP01.md",
                has_lane_entry=True,
                latest_lane="approved",
                metadata={"execution_mode": "planning_artifact", "agent": "planner"},
            )
        ],
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
        skipped_checks=[
            AcceptanceCheckDiagnostic(
                check="acceptance_matrix_presence",
                detail="planning_artifact-only missions do not produce acceptance-matrix.json",
            )
        ],
        acceptance_matrix_gate_skip_reason=PLANNING_ARTIFACT_ONLY_SKIP_REASON,
    )
    assert summary.ok, "the fixture must expose unknown evidence as the only readiness failure"
    return summary


@dataclass
class Evidence:
    """The evidence collaborators' knobs and what they were asked."""

    harness: Harness
    report: EvidenceReport = field(default_factory=EvidenceReport)
    report_error: Exception | None = None
    lanes: object | None = field(default_factory=object)
    lanes_error: Exception | None = None
    status_dir: Path | None = None
    status_dir_error: Exception | None = None
    plan_error: Exception | None = None
    planned: list[tuple[tuple[str, ...], str | None]] = field(default_factory=list)
    recorded: list[dict[str, Any]] = field(default_factory=list)

    def read_lanes(self, _mission_dir: Path) -> object | None:
        if self.lanes_error is not None:
            raise self.lanes_error
        return self.lanes

    def resolve_status_dir(self, _run: object) -> Path:
        if self.status_dir_error is not None:
            raise self.status_dir_error
        assert self.status_dir is not None
        return self.status_dir

    def mission_report(self, *_args: object, **_kwargs: object) -> EvidenceReport:
        self.harness.events.append("evidence")
        if self.report_error is not None:
            raise self.report_error
        return self.report

    def plan(self, _status_dir: Path, _manifest: object, wp_ids: tuple[str, ...], reason: str | None, **_kwargs: object) -> dict[str, str]:
        self.planned.append((tuple(wp_ids), reason))
        if self.plan_error is not None:
            raise self.plan_error
        return dict.fromkeys(wp_ids, "approved")

    def record(self, **kwargs: Any) -> None:
        self.harness.events.append(f"record:{kwargs['wp_id']}")
        self.recorded.append(kwargs)


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Evidence:
    h = Harness(root=tmp_path)
    mission_dir = tmp_path / "kitty-specs" / _SLUG
    for name, value in (
        ("show_banner", lambda: None),
        ("find_repo_root", h.find_repo_root),
        ("resolve_mission_dir_with_bare_modern_fold", lambda *_a, **_k: mission_dir),
        ("choose_mode", h.choose_mode),
        ("_stranded_verdict_provenance_note", lambda _dir: None),
        ("_collect_summary_with_optional_repair", h.collect),
        ("perform_acceptance", h.perform),
        ("resolve_acceptance_actor", lambda _actor: "tester"),
        ("_stamp_birth_cutover_for_accept", h.stamp),
        ("_record_pr_merge_for_accept", h.record_pr_merge),
        ("_run_residual_acceptance_commit", h.residual),
        ("run_origin_gate", h.origin_gate),
    ):
        monkeypatch.setattr(accept_module, name, value)
    _patch_owned_entry(monkeypatch, h)
    ev = Evidence(harness=h, status_dir=mission_dir)
    monkeypatch.setattr(accept_module, "read_lanes_json", ev.read_lanes)
    monkeypatch.setattr(accept_module, "mission_evidence_report", ev.mission_report)
    monkeypatch.setattr(accept_module, "acceptably_canceled_wp_ids", lambda _repo, _slug, **_kw: set())
    monkeypatch.setattr(accept_module, "_evidence_status_dir", ev.resolve_status_dir)
    monkeypatch.setattr(accept_module, "plan_no_implementation_attestations", ev.plan)
    monkeypatch.setattr(accept_module, "record_no_implementation_attestation", ev.record)
    monkeypatch.setattr(accept_module, "_attestation_primary_dir", lambda _run: mission_dir)
    monkeypatch.setattr(accept_module, "_resolve_merge_actor", lambda _repo: "operator")
    return ev


def _refuse(evidence: Evidence) -> None:
    evidence.report = EvidenceReport(refusal=_REFUSAL)


# ---------------------------------------------------------------- the preflight


@pytest.mark.parametrize("extra", [(), ("--lenient",)])
def test_a_refusal_exits_1_with_the_codes_before_anything_is_collected(evidence: Evidence, extra: tuple[str, ...]) -> None:
    _refuse(evidence)

    result = evidence.harness.invoke("--mission", _SLUG, *extra)

    assert result.exit_code == 1, result.output
    assert json.loads(result.output) == {
        "error": _REFUSAL,
        "error_code": "IMPLEMENTATION_MISSING",
        "error_codes": ["IMPLEMENTATION_MISSING", "REVIEW_NOT_INDEPENDENT"],
    }
    assert evidence.harness.events == ["origin_gate", "evidence"], "after the origin gate, before the summary"
    assert evidence.harness.calls == []


def test_a_refusal_is_printed_in_human_mode(evidence: Evidence) -> None:
    _refuse(evidence)

    result = evidence.harness.invoke("--mission", _SLUG, json_output=False)

    assert result.exit_code == 1
    assert "IMPLEMENTATION_MISSING: WP02 was approved with no change to its owned_files" in _flat(result.output)


def test_no_commit_reports_the_refusal(evidence: Evidence) -> None:
    _refuse(evidence)

    result = evidence.harness.invoke("--mission", _SLUG, "--no-commit")

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "IMPLEMENTATION_MISSING"
    assert evidence.harness.calls == []


def test_diagnose_folds_the_refusal_into_the_report_as_a_blocked_check(evidence: Evidence) -> None:
    """Review cycle 1: the rest of the diagnosis stays visible; exit 1 is kept."""
    _refuse(evidence)

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose")

    payload = json.loads(result.output)
    assert result.exit_code == 1, result.output
    assert payload["diagnose"] is True
    assert payload["error_code"] == "IMPLEMENTATION_MISSING"
    assert payload["error_codes"] == ["IMPLEMENTATION_MISSING", "REVIEW_NOT_INDEPENDENT"]
    assert payload["feature"] == _SLUG, "the readiness report is there too"
    assert [(item.check, item.detail) for item in evidence.harness.summary.blocked_checks] == [("implementation_evidence", _REFUSAL)]
    assert evidence.harness.events == ["origin_gate", "evidence", "collect"]
    assert evidence.harness.calls == []


def test_diagnose_shows_the_blocked_check_in_human_mode(evidence: Evidence) -> None:
    _refuse(evidence)
    evidence.harness.summary.blocked_checks = []

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose", json_output=False)

    assert result.exit_code == 1, result.output
    assert "implementation_evidence" in _flat(result.output)


def test_a_pass_runs_acceptance(evidence: Evidence) -> None:
    result = evidence.harness.invoke("--mission", _SLUG)

    assert result.exit_code == 0, result.output
    assert evidence.harness.events == ["origin_gate", "evidence", "collect"]
    assert "perform_acceptance" in evidence.harness.calls


def test_no_lanes_manifest_leaves_the_readiness_check_in_charge(evidence: Evidence) -> None:
    evidence.lanes = None

    result = evidence.harness.invoke("--mission", _SLUG)

    assert result.exit_code == 0, result.output
    assert "evidence" not in evidence.harness.events


def test_a_corrupt_lanes_manifest_refuses_window_uncomputable(evidence: Evidence) -> None:
    evidence.lanes_error = CorruptLanesError("bad json")

    result = evidence.harness.invoke("--mission", _SLUG)

    payload = json.loads(result.output)
    assert result.exit_code == 1
    assert payload["error_code"] == "EVIDENCE_WINDOW_UNCOMPUTABLE"
    assert payload["error_codes"] == ["EVIDENCE_WINDOW_UNCOMPUTABLE"]
    assert payload["error"].startswith("EVIDENCE_WINDOW_UNCOMPUTABLE: ")
    assert evidence.harness.calls == []


def _unmaterialized(tmp_root: Path) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized(
        repo_root=tmp_root,
        mission_slug=_SLUG,
        mid8="01KYHP67",
        coordination_branch="kitty/mission-x-01KYHP67",
        coord_candidate=tmp_root / ".worktrees" / "x" / "kitty-specs" / _SLUG,
        primary_candidate=tmp_root / "kitty-specs" / _SLUG,
    )


# #7222 / #7223: corrupt manifests and unmaterialized coordination yield a visible evidence
# skip under --diagnose; other modes refuse with a typed code. An unreadable status log is
# never downgraded to a skip, including in diagnosis (narrow #7247 landing scope).


def test_diagnose_skips_the_evidence_check_on_a_corrupt_lanes_manifest(evidence: Evidence) -> None:
    evidence.lanes_error = CorruptLanesError("bad json")
    evidence.harness.summary = _ready_planning_summary(evidence.harness.root)

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose")

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert payload["diagnose"] is True
    assert "error_code" not in payload, "no computed evidence verdict: the readiness report owns the blocker"
    skipped = [item for item in payload["skipped_checks"] if item["check"] == "implementation_evidence"]
    assert len(skipped) == 1
    assert skipped[0]["detail"].startswith("implementation_evidence skipped: EVIDENCE_WINDOW_UNCOMPUTABLE: ")
    assert "bad json" in skipped[0]["detail"]
    assert payload["ok"] is False, "unknown evidence cannot leave an otherwise-ready report ready"
    assert any("could not be evaluated" in issue for issue in payload["activity_issues"])
    assert any(item["check"] == "acceptance_matrix_presence" for item in payload["skipped_checks"])
    assert payload["blocked_checks"] == [], "do not manufacture a matrix refusal for its legitimate exemption"
    assert evidence.harness.events == ["origin_gate", "collect"]
    assert evidence.harness.calls == []


def test_diagnose_skips_the_evidence_check_on_an_unmaterialized_coordination_worktree(evidence: Evidence) -> None:
    evidence.status_dir_error = _unmaterialized(evidence.harness.root)
    evidence.harness.summary = _ready_planning_summary(evidence.harness.root)

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose")

    payload = json.loads(result.output)
    assert result.exit_code == 0, result.output
    assert payload["diagnose"] is True
    skipped = [item for item in payload["skipped_checks"] if item["check"] == "implementation_evidence"]
    assert len(skipped) == 1
    assert "COORDINATION_WORKTREE_UNMATERIALIZED" in skipped[0]["detail"]
    assert payload["ok"] is False, "the planning-only matrix exemption does not imply evidence was readable"
    assert any("could not be evaluated" in issue for issue in payload["activity_issues"])
    assert any(item["check"] == "acceptance_matrix_presence" for item in payload["skipped_checks"])
    assert "evidence" not in evidence.harness.events, "the verdict is never judged on a substitute surface"
    assert evidence.harness.calls == []


def test_diagnose_shows_the_skip_note_in_human_mode(evidence: Evidence, monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console
    from specify_cli.lanes.persistence import read_lanes_json

    malformed_dir = evidence.harness.root / "repo[/red]"
    malformed_dir.mkdir(parents=True)
    manifest_path = malformed_dir / "lanes.json"
    manifest_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(CorruptLanesError) as caught:
        read_lanes_json(malformed_dir)
    evidence.lanes_error = caught.value
    evidence.harness.summary = _ready_planning_summary(evidence.harness.root)
    # Keep the real renderer, but prevent terminal wrapping from splitting a long temp path.
    monkeypatch.setattr(accept_module, "console", Console(width=4096, highlight=False))

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose", json_output=False)

    assert result.exit_code == 0, result.output
    output = _flat(result.output)
    assert "implementation_evidence skipped: EVIDENCE_WINDOW_UNCOMPUTABLE: " in output
    assert str(caught.value) in output, "the complete real parser reason/path must remain literal"
    assert manifest_path.read_text(encoding="utf-8") == "{not-json"


@pytest.mark.parametrize(
    "extra",
    [
        (),
        ("--no-commit",),
        ("--attest-no-implementation", "WP02", "--attest-reason", "the deliverable already exists upstream"),
    ],
)
def test_an_unmaterialized_coordination_worktree_refuses_with_a_typed_code(evidence: Evidence, extra: tuple[str, ...]) -> None:
    exc = _unmaterialized(evidence.harness.root)
    evidence.status_dir_error = exc

    result = evidence.harness.invoke("--mission", _SLUG, *extra)

    payload = json.loads(result.output)
    assert result.exit_code == 1, result.output
    assert payload["error_code"] == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert payload["error_codes"] == ["COORDINATION_WORKTREE_UNMATERIALIZED"]
    assert payload["next_step"] == exc.next_step
    assert payload["error"].startswith("COORDINATION_WORKTREE_UNMATERIALIZED: ")
    assert "evidence" not in evidence.harness.events
    assert evidence.recorded == []
    assert evidence.planned == []
    assert evidence.harness.calls == []


_UNREADABLE_LOGS = [StoreError("torn line"), OSError("permission denied")]


@pytest.mark.parametrize("error", _UNREADABLE_LOGS)
@pytest.mark.parametrize("extra", [(), ("--no-commit",)])
def test_an_unreadable_status_surface_refuses_with_a_typed_code(evidence: Evidence, error: Exception, extra: tuple[str, ...]) -> None:
    """The status log cannot be read: exit 1 with ``EVIDENCE_STATUS_UNREADABLE``."""
    evidence.report_error = error

    result = evidence.harness.invoke("--mission", _SLUG, *extra)

    payload = json.loads(result.output)
    assert result.exit_code == 1, result.output
    assert payload["error_code"] == "EVIDENCE_STATUS_UNREADABLE"
    assert payload["error_codes"] == ["EVIDENCE_STATUS_UNREADABLE"]
    assert payload["error"].startswith("EVIDENCE_STATUS_UNREADABLE: ")
    assert "could not be checked for implementation evidence" in payload["error"]
    assert str(error) in payload["error"]
    assert evidence.harness.calls == []


@pytest.mark.parametrize("error", _UNREADABLE_LOGS)
def test_diagnose_refuses_an_unreadable_status_log_with_the_typed_code(evidence: Evidence, error: Exception) -> None:
    """Diagnosis does not bypass unreadable canonical status (narrow #7247 scope)."""
    evidence.report_error = error

    result = evidence.harness.invoke("--mission", _SLUG, "--diagnose")

    payload = json.loads(result.output)
    assert result.exit_code == 1, result.output
    assert payload["error_code"] == "EVIDENCE_STATUS_UNREADABLE"
    assert payload["error_codes"] == ["EVIDENCE_STATUS_UNREADABLE"]
    assert str(error) in payload["error"]
    assert "skipped_checks" not in payload, "an unreadable log does not yield a readiness report"
    assert evidence.harness.calls == []


def test_an_invalid_utf8_status_log_refuses_with_the_typed_code(evidence: Evidence, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real store decoder's failure is translated, not left as a raw CLI exception."""
    from specify_cli.consolidation.wp_evidence import mission_evidence_report
    from specify_cli.lanes.persistence import read_lanes_json
    from tests.lane_test_utils import write_single_lane_manifest

    assert evidence.status_dir is not None
    evidence.status_dir.mkdir(parents=True, exist_ok=True)
    write_single_lane_manifest(evidence.status_dir)
    evidence.lanes = read_lanes_json(evidence.status_dir)
    status_log = evidence.status_dir / "status.events.jsonl"
    invalid_log = b'{"event_id": "\xff\xfe"}\n'
    status_log.write_bytes(invalid_log)
    monkeypatch.setattr(accept_module, "mission_evidence_report", mission_evidence_report)

    result = evidence.harness.invoke("--mission", _SLUG)

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["error_code"] == "EVIDENCE_STATUS_UNREADABLE"
    assert payload["error_codes"] == ["EVIDENCE_STATUS_UNREADABLE"]
    assert "utf-8" in payload["error"]
    assert status_log.read_bytes() == invalid_log
    assert evidence.harness.calls == []


# ---------------------------------------------------------------- --attest-no-implementation


def test_the_attestation_is_recorded_before_the_preflight(evidence: Evidence) -> None:
    result = evidence.harness.invoke("--mission", _SLUG, "--attest-no-implementation", "WP02", "--attest-no-implementation", "WP04", "--attest-reason", "docs-only")

    assert result.exit_code == 0, result.output
    assert evidence.planned == [(("WP02", "WP04"), "docs-only")]
    assert evidence.harness.events[:4] == ["origin_gate", "record:WP02", "record:WP04", "evidence"]
    assert [(r["wp_id"], r["current_lane"], r["reason"], r["actor"], r["mission_slug"]) for r in evidence.recorded] == [
        ("WP02", "approved", "docs-only", "operator", _SLUG),
        ("WP04", "approved", "docs-only", "operator", _SLUG),
    ]


def test_an_attestation_without_a_reason_exits_2_and_records_nothing(evidence: Evidence) -> None:
    result = evidence.harness.invoke("--mission", _SLUG, "--attest-no-implementation", "WP02", "--attest-reason", "  ")

    assert result.exit_code == 2, result.output
    assert "--attest-no-implementation requires --attest-reason" in _flat(result.output)
    assert evidence.recorded == [] and evidence.planned == []
    assert evidence.harness.calls == []


@pytest.mark.parametrize("mode", ["--no-commit", "--diagnose"])
def test_the_read_only_modes_refuse_the_attestation(evidence: Evidence, mode: str) -> None:
    result = evidence.harness.invoke("--mission", _SLUG, mode, "--attest-no-implementation", "WP02", "--attest-reason", "docs-only")

    assert result.exit_code == 2, result.output
    assert f"would record a no-implementation attestation; {mode} is read-only" in _flat(result.output)
    assert evidence.recorded == [] and evidence.planned == []


def test_a_refused_attestation_request_records_nothing(evidence: Evidence) -> None:
    evidence.plan_error = AttestationError("--attest-no-implementation applies only to an approved work package; not approved: WP09. Nothing was recorded.")

    result = evidence.harness.invoke("--mission", _SLUG, "--attest-no-implementation", "WP09", "--attest-reason", "docs-only")

    assert result.exit_code == 1
    assert "not approved: WP09" in json.loads(result.output)["error"]
    assert evidence.recorded == []
    assert "evidence" not in evidence.harness.events
