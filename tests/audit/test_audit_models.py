"""Tests for src/specify_cli/audit/models.py (T001–T004)."""

from __future__ import annotations

import operator
from pathlib import Path

import pytest

from specify_cli.audit.models import (
    TEAMSPACE_BLOCKER_CODES,
    AuditOptions,
    MissionAuditResult,
    MissionFinding,
    RepoAuditReport,
    Severity,
    is_teamspace_blocker,
)

# ---------------------------------------------------------------------------
# T001: Severity StrEnum
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

class TestSeverity:
    def test_has_exactly_three_members(self) -> None:
        members = list(Severity)
        assert frozenset(member.name for member in members) == frozenset(
            {"ERROR", "WARNING", "INFO"}
        )

    def test_member_names(self) -> None:
        assert Severity.ERROR
        assert Severity.WARNING
        assert Severity.INFO

    def test_string_values(self) -> None:
        assert Severity.ERROR == "error"
        assert Severity.WARNING == "warning"
        assert Severity.INFO == "info"

    def test_ordering_error_lt_warning(self) -> None:
        assert Severity.ERROR < Severity.WARNING

    def test_ordering_warning_lt_info(self) -> None:
        assert Severity.WARNING < Severity.INFO

    def test_ordering_error_lt_info(self) -> None:
        assert Severity.ERROR < Severity.INFO

    def test_le_same_member(self) -> None:
        assert Severity.ERROR <= Severity.ERROR
        assert Severity.WARNING <= Severity.WARNING
        assert Severity.INFO <= Severity.INFO

    def test_le_across_members(self) -> None:
        assert Severity.ERROR <= Severity.WARNING
        assert Severity.ERROR <= Severity.INFO
        assert Severity.WARNING <= Severity.INFO

    def test_not_lt_reversed(self) -> None:
        assert not (Severity.WARNING < Severity.ERROR)
        assert not (Severity.INFO < Severity.ERROR)
        assert not (Severity.INFO < Severity.WARNING)

    def test_not_le_reversed(self) -> None:
        assert not (Severity.WARNING <= Severity.ERROR)
        assert not (Severity.INFO <= Severity.ERROR)
        assert not (Severity.INFO <= Severity.WARNING)

    def test_gt_ge_follow_severity_rank_not_str_order(self) -> None:
        # ``str`` order would say "warning" > "info"; the rank says a warning
        # is MORE severe than info, so it sorts before it (S8500, #4695).
        assert not (Severity.WARNING > Severity.INFO)
        assert not (Severity.WARNING >= Severity.INFO)
        assert Severity.INFO > Severity.WARNING
        assert Severity.INFO >= Severity.WARNING
        assert Severity.WARNING > Severity.ERROR
        assert Severity.INFO > Severity.ERROR
        assert Severity.ERROR >= Severity.ERROR
        assert not (Severity.ERROR > Severity.ERROR)

    def test_rank_orders_most_severe_first(self) -> None:
        assert [s.rank for s in (Severity.ERROR, Severity.WARNING, Severity.INFO)] == [0, 1, 2]

    def test_str_operand_follows_rank_on_both_sides(self) -> None:
        # ``Severity`` is a ``str``: returning NotImplemented for a plain value
        # would hand the comparison to ``str`` and its alphabetical order.
        assert Severity.WARNING <= "info"
        assert Severity.WARNING < "info"
        assert not (Severity.WARNING > "info")
        # Plain value on the left: Python asks the ``Severity`` subclass first.
        assert operator.gt("info", Severity.WARNING)
        assert operator.ge("info", Severity.WARNING)
        assert not operator.lt("info", Severity.WARNING)

    @pytest.mark.parametrize("op", ["__lt__", "__le__", "__gt__", "__ge__"])
    def test_unknown_str_operand_raises(self, op: str) -> None:
        with pytest.raises(ValueError, match="critical"):
            getattr(Severity.ERROR, op)("critical")

    @pytest.mark.parametrize("op", ["__lt__", "__le__", "__gt__", "__ge__"])
    def test_non_str_operand_is_not_implemented(self, op: str) -> None:
        assert getattr(Severity.ERROR, op)(1) is NotImplemented

    def test_all_four_operators_agree_with_sorting(self) -> None:
        members = sorted([Severity.INFO, Severity.ERROR, Severity.WARNING])
        assert members == [Severity.ERROR, Severity.WARNING, Severity.INFO]
        assert max(Severity) is Severity.INFO
        assert min(Severity) is Severity.ERROR

    def test_is_str(self) -> None:
        assert isinstance(Severity.ERROR, str)

    def test_fail_on_threshold_pattern(self) -> None:
        """Verify the --fail-on threshold idiom works correctly."""
        findings = [
            MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="a.md"),
            MissionFinding(code="CORRUPT_JSONL", severity=Severity.ERROR, artifact_path="b.jsonl"),
        ]
        # fail_on=ERROR: only errors trigger failure
        assert any(f.severity <= Severity.ERROR for f in findings)
        # fail_on=WARNING: errors and warnings trigger failure
        assert any(f.severity <= Severity.WARNING for f in findings)
        # fail_on=INFO: everything triggers failure
        assert any(f.severity <= Severity.INFO for f in findings)


# ---------------------------------------------------------------------------
# T002: MissionFinding frozen dataclass
# ---------------------------------------------------------------------------


class TestMissionFinding:
    def test_basic_construction(self) -> None:
        f = MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="tasks/WP01.md")
        assert f.code == "LEGACY_KEY"
        assert f.severity == Severity.WARNING
        assert f.artifact_path == "tasks/WP01.md"
        assert f.detail is None

    def test_with_detail(self) -> None:
        f = MissionFinding(
            code="CORRUPT_JSONL",
            severity=Severity.ERROR,
            artifact_path="status.events.jsonl",
            detail="line 7 is not valid JSON",
        )
        assert f.detail == "line 7 is not valid JSON"

    def test_frozen_immutable(self) -> None:
        f = MissionFinding(code="X", severity=Severity.INFO, artifact_path="foo")
        with pytest.raises((AttributeError, TypeError)):
            f.code = "Y"  # type: ignore[misc]

    def test_hashable(self) -> None:
        f = MissionFinding(code="X", severity=Severity.INFO, artifact_path="foo")
        assert hash(f) is not None
        s: set[MissionFinding] = {f}
        assert f in s

    def test_to_dict_keys(self) -> None:
        f = MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="meta.json")
        d = f.to_dict()
        assert set(d.keys()) == {"code", "severity", "artifact_path", "detail"}

    def test_to_dict_severity_is_string(self) -> None:
        f = MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="meta.json")
        d = f.to_dict()
        assert d["severity"] == "warning"
        assert isinstance(d["severity"], str)

    def test_to_dict_detail_none(self) -> None:
        f = MissionFinding(code="X", severity=Severity.INFO, artifact_path="foo")
        assert f.to_dict()["detail"] is None

    def test_to_dict_detail_present(self) -> None:
        f = MissionFinding(code="X", severity=Severity.INFO, artifact_path="foo", detail="some detail")
        assert f.to_dict()["detail"] == "some detail"

    def test_to_dict_values(self) -> None:
        f = MissionFinding(
            code="IDENTITY_MISSING",
            severity=Severity.ERROR,
            artifact_path="meta.json",
            detail="mission_id field absent",
        )
        d = f.to_dict()
        assert d["code"] == "IDENTITY_MISSING"
        assert d["severity"] == "error"
        assert d["artifact_path"] == "meta.json"
        assert d["detail"] == "mission_id field absent"


class TestTeamspaceBlockers:
    def test_all_errors_are_teamspace_blockers(self) -> None:
        f = MissionFinding(code="UNKNOWN", severity=Severity.ERROR, artifact_path="x")
        assert is_teamspace_blocker(f) is True

    def test_legacy_warning_is_teamspace_blocker(self) -> None:
        f = MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="x")
        assert is_teamspace_blocker(f) is True

    def test_non_blocking_warning_is_not_teamspace_blocker(self) -> None:
        f = MissionFinding(code="ACTOR_DRIFT", severity=Severity.WARNING, artifact_path="x")
        assert is_teamspace_blocker(f) is False

    def test_contract_codes_include_teamspace_import_risks(self) -> None:
        assert {
            "CORRUPT_JSONL",
            "DUPLICATE_MISSION_ID",
            "FORBIDDEN_KEY",
            "IDENTITY_MISSING",
            "LEGACY_KEY",
            "SNAPSHOT_DRIFT",
        }.issubset(TEAMSPACE_BLOCKER_CODES)


# ---------------------------------------------------------------------------
# T003: MissionAuditResult dataclass
# ---------------------------------------------------------------------------


def _make_result(
    slug: str = "my-feature",
    findings: list[MissionFinding] | None = None,
) -> MissionAuditResult:
    return MissionAuditResult(
        mission_slug=slug,
        mission_dir=Path("kitty-specs") / slug,
        findings=findings or [],
    )


class TestMissionAuditResult:
    def test_has_errors_false_when_empty(self) -> None:
        r = _make_result()
        assert r.has_errors is False

    def test_has_errors_false_with_only_warnings(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="x")]
        )
        assert r.has_errors is False

    def test_has_errors_true(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="CORRUPT_JSONL", severity=Severity.ERROR, artifact_path="x")]
        )
        assert r.has_errors is True

    def test_has_warnings_false_when_empty(self) -> None:
        r = _make_result()
        assert r.has_warnings is False

    def test_has_warnings_false_with_only_errors(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="CORRUPT_JSONL", severity=Severity.ERROR, artifact_path="x")]
        )
        assert r.has_warnings is False

    def test_has_warnings_true(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="x")]
        )
        assert r.has_warnings is True

    def test_has_teamspace_blockers_true_for_legacy_warning(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="x")]
        )
        assert r.has_teamspace_blockers is True

    def test_has_teamspace_blockers_false_for_non_blocking_warning(self) -> None:
        r = _make_result(
            findings=[MissionFinding(code="ACTOR_DRIFT", severity=Severity.WARNING, artifact_path="x")]
        )
        assert r.has_teamspace_blockers is False

    def test_finding_codes(self) -> None:
        r = _make_result(
            findings=[
                MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="a"),
                MissionFinding(code="CORRUPT_JSONL", severity=Severity.ERROR, artifact_path="b"),
                MissionFinding(code="LEGACY_KEY", severity=Severity.WARNING, artifact_path="c"),
            ]
        )
        assert r.finding_codes == {"LEGACY_KEY", "CORRUPT_JSONL"}

    def test_to_dict_keys(self) -> None:
        r = _make_result()
        d = r.to_dict()
        assert "mission_slug" in d
        assert "mission_dir" in d
        assert "findings" in d
        assert "finding_count" in d
        assert "has_errors" in d
        assert "has_teamspace_blockers" in d

    def test_to_dict_mission_dir_is_string(self) -> None:
        r = _make_result()
        d = r.to_dict()
        assert isinstance(d["mission_dir"], str)

    def test_to_dict_mission_dir_under_kitty_specs_is_repo_relative(self, tmp_path: Path) -> None:
        slug = "stable-mission"
        r = MissionAuditResult(
            mission_slug=slug,
            mission_dir=tmp_path / "repo-a" / "kitty-specs" / slug,
            findings=[],
        )

        mission_dir = r.to_dict()["mission_dir"]

        assert mission_dir == f"kitty-specs/{slug}"
        assert str(tmp_path) not in str(mission_dir)

    def test_to_dict_fixture_mission_dir_does_not_leak_absolute_root(self, tmp_path: Path) -> None:
        slug = "fixture-mission"
        r = MissionAuditResult(
            mission_slug=slug,
            mission_dir=tmp_path / "fixtures" / slug,
            findings=[],
        )

        mission_dir = r.to_dict()["mission_dir"]

        assert mission_dir == slug
        assert str(tmp_path) not in str(mission_dir)

    def test_to_dict_fixture_dir_under_unrelated_kitty_specs_ancestor_uses_slug(
        self, tmp_path: Path
    ) -> None:
        slug = "fixture-mission"
        r = MissionAuditResult(
            mission_slug=slug,
            mission_dir=tmp_path / "kitty-specs" / "install-root" / "fixtures" / slug,
            findings=[],
        )

        mission_dir = r.to_dict()["mission_dir"]

        assert mission_dir == slug
        assert "install-root" not in str(mission_dir)

    def test_to_dict_finding_count(self) -> None:
        r = _make_result(
            findings=[
                MissionFinding(code="X", severity=Severity.INFO, artifact_path="a"),
                MissionFinding(code="Y", severity=Severity.INFO, artifact_path="b"),
            ]
        )
        assert r.to_dict()["finding_count"] == 2


# ---------------------------------------------------------------------------
# T004: RepoAuditReport and AuditOptions
# ---------------------------------------------------------------------------


class TestRepoAuditReport:
    def _make_report(self) -> RepoAuditReport:
        return RepoAuditReport(
            missions=[_make_result("alpha"), _make_result("beta")],
            shape_counters={"CORRUPT_JSONL": 2, "LEGACY_KEY": 5, "ACTOR_DRIFT": 1},
            repo_summary={
                "total_missions": 2,
                "missions_with_errors": 0,
                "missions_with_warnings": 0,
                "total_findings": 0,
                "findings_by_severity": {"error": 0, "warning": 0, "info": 0},
            },
        )

    def test_to_dict_top_level_keys(self) -> None:
        d = self._make_report().to_dict()
        assert set(d.keys()) == {"missions", "shape_counters", "repo_summary"}

    def test_to_dict_shape_counters_sorted(self) -> None:
        report = self._make_report()
        d = report.to_dict()
        keys = list(d["shape_counters"].keys())  # type: ignore[union-attr]
        assert keys == sorted(keys)

    def test_to_dict_shape_counters_values(self) -> None:
        report = self._make_report()
        d = report.to_dict()
        sc = d["shape_counters"]
        assert sc == {"ACTOR_DRIFT": 1, "CORRUPT_JSONL": 2, "LEGACY_KEY": 5}  # type: ignore[comparison-overlap]

    def test_empty_missions(self) -> None:
        report = RepoAuditReport(
            missions=[],
            shape_counters={},
            repo_summary={},
        )
        d = report.to_dict()
        assert d["missions"] == []
        assert d["shape_counters"] == {}

    def test_missions_serialized(self) -> None:
        report = self._make_report()
        d = report.to_dict()
        assert isinstance(d["missions"], list)
        assert frozenset(m["mission_slug"] for m in d["missions"]) == frozenset(  # type: ignore[union-attr]
            {"alpha", "beta"}
        )


class TestAuditOptions:
    def test_required_repo_root(self) -> None:
        opts = AuditOptions(repo_root=Path("/repo"))
        assert opts.repo_root == Path("/repo")

    def test_defaults(self) -> None:
        opts = AuditOptions(repo_root=Path("/repo"))
        assert opts.scan_root is None
        assert opts.mission_filter is None
        assert opts.fail_on is None

    def test_with_all_fields(self) -> None:
        opts = AuditOptions(
            repo_root=Path("/repo"),
            scan_root=Path("/repo/kitty-specs"),
            mission_filter="my-feature",
            fail_on=Severity.ERROR,
        )
        assert opts.scan_root == Path("/repo/kitty-specs")
        assert opts.mission_filter == "my-feature"
        assert opts.fail_on == Severity.ERROR

    def test_fail_on_warning_threshold(self) -> None:
        opts = AuditOptions(repo_root=Path("/repo"), fail_on=Severity.WARNING)
        assert opts.fail_on == Severity.WARNING
        assert opts.fail_on <= Severity.WARNING
        # error is also <= warning (more severe)
        assert opts.fail_on >= Severity.ERROR  # type: ignore[operator]
