"""#7308: a ``deferred`` acceptance-criterion verdict.

A criterion the mission explicitly defers (with a reason and a follow-up
reference) must not hold ``overall_verdict`` at ``pending`` forever, but it
must never be silent either: an unjustified deferral is refused, and every
deferred row is disclosed in ``accept`` output (human and ``--json``).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import typer
from rich.console import Console

from specify_cli.acceptance.gates_core import AcceptanceCheckDiagnostic, _judge_acceptance_matrix
from specify_cli.acceptance.matrix import (
    CRITERION_VERDICTS,
    DEFERRAL_FOLLOW_UP_KEY,
    DEFERRAL_REASON_KEY,
    AcceptanceCriterion,
    AcceptanceMatrix,
    read_acceptance_matrix,
    validate_matrix_evidence,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.agent.acceptance_verdict import acceptance_verdict
from tests.specify_cli.acceptance.test_acceptance_verdict_command import _git, _init_flat_mission

_SLUG = "deferred-verdict-mission"


def _criterion(cid: str, verdict: str, **extras: str) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        criterion_id=cid,
        description=f"{cid} behaves as specified",
        proof_type="automated_test",
        pass_fail=verdict,
        extras=dict(extras),
    )


def _deferred(cid: str = "FR-002") -> AcceptanceCriterion:
    return _criterion(
        cid,
        "deferred",
        **{DEFERRAL_REASON_KEY: "needs the hosted read service", DEFERRAL_FOLLOW_UP_KEY: "#7400"},
    )


def _matrix(*criteria: AcceptanceCriterion) -> AcceptanceMatrix:
    return AcceptanceMatrix(mission_slug=_SLUG, criteria=list(criteria))


@pytest.mark.unit
class TestDeferredVerdictSemantics:
    def test_deferred_is_a_criterion_verdict(self) -> None:
        assert "deferred" in CRITERION_VERDICTS

    def test_pass_plus_justified_deferral_passes(self) -> None:
        matrix = _matrix(_criterion("FR-001", "pass"), _deferred())
        assert matrix.overall_verdict == "pass"
        assert validate_matrix_evidence(matrix) == []

    def test_deferral_without_reason_or_follow_up_is_refused(self) -> None:
        for extras in ({}, {DEFERRAL_REASON_KEY: "why"}, {DEFERRAL_FOLLOW_UP_KEY: "#1"}):
            matrix = _matrix(_criterion("FR-001", "pass"), _criterion("FR-002", "deferred", **extras))
            assert matrix.overall_verdict == "pending"
            errors = validate_matrix_evidence(matrix)
            assert any("FR-002" in err and "deferred" in err for err in errors)

    def test_pending_still_dominates_a_deferral(self) -> None:
        assert _matrix(_criterion("FR-001", "pending"), _deferred()).overall_verdict == "pending"

    def test_fail_still_dominates_a_deferral(self) -> None:
        assert _matrix(_criterion("FR-001", "fail"), _deferred()).overall_verdict == "fail"

    def test_deferral_round_trips(self, tmp_path: Path) -> None:
        write_acceptance_matrix(tmp_path, _matrix(_deferred()))
        reloaded = read_acceptance_matrix(tmp_path)
        assert reloaded is not None
        assert reloaded.criteria[0].extras[DEFERRAL_FOLLOW_UP_KEY] == "#7400"


@pytest.mark.unit
class TestDeferralDisclosure:
    def test_judge_discloses_each_deferred_row(self) -> None:
        issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        _judge_acceptance_matrix(_matrix(_criterion("FR-001", "pass"), _deferred()), issues, skipped)
        assert issues == []
        deferred = [item for item in skipped if item.check == "criteria_deferred"]
        assert len(deferred) == 1
        assert "FR-002" in deferred[0].detail and "#7400" in deferred[0].detail

    def test_no_disclosure_without_deferrals(self) -> None:
        skipped: list[AcceptanceCheckDiagnostic] = []
        _judge_acceptance_matrix(_matrix(_criterion("FR-001", "pass")), [], skipped)
        assert not any(item.check == "criteria_deferred" for item in skipped)

    def test_human_summary_prints_deferred_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import accept as accept_cmd

        buf = io.StringIO()
        monkeypatch.setattr(accept_cmd, "console", Console(file=buf, width=200))
        summary = SimpleNamespace(
            lanes={},
            outstanding=dict,
            warnings=[],
            skipped_checks=[AcceptanceCheckDiagnostic(check="criteria_deferred", detail="FR-002 deferred (#7400)")],
        )
        accept_cmd._print_acceptance_summary(cast(Any, summary))
        out = buf.getvalue()
        assert "Deferred criteria" in out and "FR-002 deferred (#7400)" in out


@pytest.mark.integration
@pytest.mark.git_repo
class TestAcceptanceVerdictDeferredFlag:
    def _seed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        repo_root, feature_dir = _init_flat_mission(tmp_path, _SLUG)
        write_acceptance_matrix(
            feature_dir,
            AcceptanceMatrix(
                mission_slug=_SLUG,
                criteria=[
                    AcceptanceCriterion(
                        criterion_id="FR-001",
                        description="Verify FR-001",
                        proof_type="automated_test",
                        notes="TODO",
                    )
                ],
            ),
        )
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "seed acceptance-matrix")
        monkeypatch.chdir(repo_root)
        return feature_dir

    def test_deferred_without_reason_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._seed(tmp_path, monkeypatch)
        with pytest.raises(typer.Exit) as exc:
            acceptance_verdict(mission=_SLUG, criterion="FR-001", result="deferred", follow_up="#7400", json_output=True)
        assert exc.value.exit_code == 2
        assert "--reason" in json.loads(capsys.readouterr().out)["error"]

    def test_deferred_without_follow_up_refused(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        self._seed(tmp_path, monkeypatch)
        with pytest.raises(typer.Exit) as exc:
            acceptance_verdict(mission=_SLUG, criterion="FR-001", result="deferred", reason="later", json_output=True)
        assert exc.value.exit_code == 2
        assert "--follow-up" in json.loads(capsys.readouterr().out)["error"]

    def test_reason_rejected_for_non_deferred(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._seed(tmp_path, monkeypatch)
        with pytest.raises(typer.Exit) as exc:
            acceptance_verdict(mission=_SLUG, criterion="FR-001", result="pass", reason="x", json_output=True)
        assert exc.value.exit_code == 2

    def test_deferred_recorded_with_description_and_notes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        feature_dir = self._seed(tmp_path, monkeypatch)
        try:
            acceptance_verdict(
                mission=_SLUG,
                criterion="FR-001",
                result="deferred",
                reason="needs the hosted read service",
                follow_up="https://github.com/spec-kitty/spec-kitty/issues/7400",
                description="The read API answers status queries",
                notes="Deferred by operator ruling",
                json_output=True,
            )
        except typer.Exit as exc:
            assert exc.exit_code in (0, None)
        payload = json.loads(capsys.readouterr().out)
        assert payload["result"] == "deferred"
        assert payload["overall_verdict"] == "pass"
        row = read_acceptance_matrix(feature_dir)
        assert row is not None
        crit = row.criteria[0]
        assert crit.pass_fail == "deferred"
        assert crit.extras[DEFERRAL_REASON_KEY] == "needs the hosted read service"
        assert crit.extras[DEFERRAL_FOLLOW_UP_KEY].endswith("/7400")
        assert crit.description == "The read API answers status queries"
        assert crit.notes == "Deferred by operator ruling"

    def test_leaving_deferred_clears_deferral_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = self._seed(tmp_path, monkeypatch)
        calls: tuple[dict[str, Any], ...] = (
            {"result": "deferred", "reason": "later", "follow_up": "#7400"},
            {"result": "pass"},
        )
        for kwargs in calls:
            try:
                acceptance_verdict(mission=_SLUG, criterion="FR-001", json_output=True, **kwargs)
            except typer.Exit as exc:
                assert exc.exit_code in (0, None)
        reloaded = read_acceptance_matrix(feature_dir)
        assert reloaded is not None
        assert reloaded.criteria[0].pass_fail == "pass"
        assert DEFERRAL_REASON_KEY not in reloaded.criteria[0].extras
        assert DEFERRAL_FOLLOW_UP_KEY not in reloaded.criteria[0].extras
