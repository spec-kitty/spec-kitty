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

from specify_cli.cli.commands import accept as accept_module
from specify_cli.consolidation.canceled_attestation import AttestationError
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


@dataclass
class Evidence:
    """The evidence collaborators' knobs and what they were asked."""

    harness: Harness
    report: EvidenceReport = field(default_factory=EvidenceReport)
    report_error: Exception | None = None
    lanes: object | None = field(default_factory=object)
    lanes_error: Exception | None = None
    plan_error: Exception | None = None
    planned: list[tuple[tuple[str, ...], str | None]] = field(default_factory=list)
    recorded: list[dict[str, Any]] = field(default_factory=list)

    def read_lanes(self, _mission_dir: Path) -> object | None:
        if self.lanes_error is not None:
            raise self.lanes_error
        return self.lanes

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
    ev = Evidence(harness=h)
    monkeypatch.setattr(accept_module, "read_lanes_json", ev.read_lanes)
    monkeypatch.setattr(accept_module, "mission_evidence_report", ev.mission_report)
    monkeypatch.setattr(accept_module, "acceptably_canceled_wp_ids", lambda _repo, _slug: set())
    monkeypatch.setattr(accept_module, "_evidence_status_dir", lambda _run: mission_dir)
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


def test_an_unreadable_status_surface_refuses(evidence: Evidence) -> None:
    evidence.report_error = StoreError("torn line")

    result = evidence.harness.invoke("--mission", _SLUG)

    assert result.exit_code == 1
    assert "could not be checked for implementation evidence" in json.loads(result.output)["error"]
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
