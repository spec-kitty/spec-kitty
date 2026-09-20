"""Unit tests for the WP04 (coord-authority-trio-degod-01KX7094) extraction seams.

Direct in->out characterization of the NEW pure helpers extracted from
``acceptance/__init__.py`` in T021 (``summary_core``) and T022 (``gates_core``):

* ``summary_core.build_work_package_state`` -- the per-WP bucketing/metadata-issue
  computation ``collect_feature_summary``'s loop body used to run inline.
* ``summary_core.evaluate_path_conventions`` / ``build_warnings`` -- the mission
  path-convention block and the final warnings assembly.
* ``summary_core._has_blocked_check`` / ``_has_non_terminal_lane`` /
  ``_has_issue_containing`` -- the predicates ``_build_recommended_fix_order``'s
  data table now delegates to (replacing the CC22 if-chain).
* ``gates_core._resolve_lanes_manifest_or_stop`` / ``_evaluate_branch_gate`` /
  ``_evaluate_acceptance_matrix`` -- the three guard-clause stages
  ``_check_lane_gates`` (CC19) now delegates to.

These are additive coverage for the NEW branches introduced by the extraction;
the pre-existing end-to-end behaviour of ``collect_feature_summary`` /
``_check_lane_gates`` / ``_build_recommended_fix_order`` stays pinned by the
WP01 characterization suite (``tests/characterization/test_trio_pure_cores.py``),
which this PR keeps green unmodified.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.acceptance.gates_core import (
    AcceptanceCheckDiagnostic,
    _evaluate_acceptance_matrix,
    _evaluate_branch_gate,
    _resolve_lanes_manifest_or_stop,
)
from specify_cli.acceptance.summary_core import (
    _has_blocked_check,
    _has_issue_containing,
    _has_non_terminal_lane,
    build_warnings,
    build_work_package_state,
    evaluate_path_conventions,
)
from specify_cli.acceptance import (
    _gather_primary_encoding_candidates,
    _recover_normalized_text,
)
from specify_cli.task_utils import WorkPackage

pytestmark = [pytest.mark.unit]


def _wp(
    *,
    path: Path,
    agent: str | None = "claude",
    assignee: str | None = "claude",
    shell_pid: str | None = "123",
    title: str = "Demo WP",
) -> WorkPackage:
    lines = [f"title: {title}"]
    if agent is not None:
        lines.append(f"agent: {agent}")
    if assignee is not None:
        lines.append(f"assignee: {assignee}")
    if shell_pid is not None:
        lines.append(f"shell_pid: {shell_pid}")
    frontmatter = "\n".join(lines) + "\n"
    return WorkPackage(
        feature="trio-mission",
        path=path,
        current_lane="approved",
        relative_subpath=Path("WP01.md"),
        frontmatter=frontmatter,
        body="",
        padding="",
    )


# ===========================================================================
# summary_core.build_work_package_state
# ===========================================================================


class TestBuildWorkPackageState:
    def test_active_lane_missing_all_three_flags_all_issues(self, tmp_path: Path) -> None:
        wp = _wp(path=tmp_path / "tasks" / "WP01.md", agent=None, assignee=None, shell_pid=None)

        state, issues = build_work_package_state(
            wp,
            "WP01",
            {"lane": "in_progress"},
            repo_root=tmp_path,
            strict_metadata=True,
        )

        assert issues == [
            "WP01: missing agent in canonical runtime state "
            "(never claimed; run `spec-kitty agent tasks move-task WP01 "
            "--to in_progress --agent <name>` to repair)",
            "WP01: missing assignee in canonical runtime state",
            "WP01: missing shell_pid in canonical runtime state",
        ]
        assert state.lane == "in_progress"
        assert state.has_lane_entry is True
        assert state.latest_lane == "in_progress"
        assert state.metadata == {"lane": "in_progress", "agent": None, "assignee": None, "shell_pid": None}

    def test_terminal_lane_missing_assignee_and_shell_pid_is_exempt(self, tmp_path: Path) -> None:
        """#2369: a done/approved WP has no live shell -- only ``agent`` is
        still required; assignee/shell_pid are exempt outside active lanes."""
        wp = _wp(path=tmp_path / "tasks" / "WP01.md", agent="claude", assignee=None, shell_pid=None)

        _state, issues = build_work_package_state(
            wp,
            "WP01",
            {"lane": "done", "agent": "claude"},
            repo_root=tmp_path,
            strict_metadata=True,
        )

        assert issues == []

    def test_terminal_lane_still_requires_canonical_runtime_agent(self, tmp_path: Path) -> None:
        wp = _wp(path=tmp_path / "tasks" / "WP01.md", agent="authored-only")

        _state, issues = build_work_package_state(
            wp, "WP01", {"lane": "approved"}, repo_root=tmp_path, strict_metadata=True
        )

        assert issues == [
            "WP01: missing agent in canonical runtime state "
            "(never claimed; run `spec-kitty agent tasks move-task WP01 "
            "--to approved --agent <name>` to repair)"
        ]

    def test_non_strict_metadata_suppresses_all_issues(self, tmp_path: Path) -> None:
        wp = _wp(path=tmp_path / "tasks" / "WP01.md", agent=None, assignee=None, shell_pid=None)

        _state, issues = build_work_package_state(
            wp,
            "WP01",
            {"lane": "in_progress"},
            repo_root=tmp_path,
            strict_metadata=False,
        )

        assert issues == []

    def test_runtime_metadata_comes_only_from_snapshot(self, tmp_path: Path) -> None:
        wp = _wp(
            path=tmp_path / "tasks" / "WP01.md",
            agent="legacy-agent",
            assignee="legacy-assignee",
            shell_pid="111",
        )

        state, issues = build_work_package_state(
            wp,
            "WP01",
            {
                "lane": "in_progress",
                "agent": "resolved-agent",
                "assignee": "resolved-assignee",
                "shell_pid": "222",
            },
            repo_root=tmp_path,
            strict_metadata=True,
        )

        assert issues == []
        assert state.metadata == {
            "lane": "in_progress",
            "agent": "resolved-agent",
            "assignee": "resolved-assignee",
            "shell_pid": "222",
        }

    def test_canonical_lane_none_buckets_to_planned(self, tmp_path: Path) -> None:
        wp = _wp(path=tmp_path / "tasks" / "WP01.md")

        state, _issues = build_work_package_state(
            wp, "WP01", None, repo_root=tmp_path, strict_metadata=True
        )

        assert state.lane == "planned"
        assert state.has_lane_entry is False
        assert state.latest_lane is None

    def test_path_is_relative_to_repo_root(self, tmp_path: Path) -> None:
        wp_path = tmp_path / "kitty-specs" / "trio-mission" / "tasks" / "WP01.md"
        wp = _wp(path=wp_path)

        state, _issues = build_work_package_state(
            wp, "WP01", {"lane": "approved"}, repo_root=tmp_path, strict_metadata=True
        )

        assert state.path == str(Path("kitty-specs") / "trio-mission" / "tasks" / "WP01.md")

    def test_title_strips_surrounding_quotes(self, tmp_path: Path) -> None:
        wp = _wp(path=tmp_path / "WP01.md", title='"Quoted Title"')

        state, _issues = build_work_package_state(
            wp, "WP01", {"lane": "approved"}, repo_root=tmp_path, strict_metadata=True
        )

        assert state.title == "Quoted Title"


# ===========================================================================
# summary_core.evaluate_path_conventions / build_warnings
# ===========================================================================


class TestEvaluatePathConventions:
    def test_mission_none_is_a_noop(self, tmp_path: Path) -> None:
        result = evaluate_path_conventions(None, tmp_path, tmp_path, tmp_path, strict_metadata=True)

        assert result == ([], None, frozenset())

    def test_mission_without_path_conventions_is_a_noop(self, tmp_path: Path) -> None:
        mission = SimpleNamespace(config=SimpleNamespace(paths=None), domain="software-dev")

        result = evaluate_path_conventions(mission, tmp_path, tmp_path, tmp_path, strict_metadata=True)

        assert result == ([], None, frozenset())

    def test_no_missing_paths_is_a_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission = SimpleNamespace(config=SimpleNamespace(paths=["src/"]), domain="software-dev")
        monkeypatch.setattr(
            "specify_cli.acceptance.summary_core.validate_mission_paths",
            lambda *_a, **_k: SimpleNamespace(missing_paths=[], missing_artifact_tokens=[]),
        )

        result = evaluate_path_conventions(mission, tmp_path, tmp_path, tmp_path, strict_metadata=True)

        assert result == ([], None, frozenset())

    def test_strict_metadata_true_blocks_with_violation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission = SimpleNamespace(
            config=SimpleNamespace(
                paths=["src/"],
                artifacts=SimpleNamespace(optional=("contracts/",), required=()),
            ),
            domain="software-dev",
        )
        monkeypatch.setattr(
            "specify_cli.acceptance.summary_core.validate_mission_paths",
            lambda *_a, **_k: SimpleNamespace(
                missing_paths=["src/"],
                missing_artifact_tokens=["contracts", "src"],
                format_errors=lambda: "missing src/",
            ),
        )

        violations, warning, dedup_tokens = evaluate_path_conventions(
            mission, tmp_path, tmp_path, tmp_path, strict_metadata=True
        )

        assert violations == ["missing src/"]
        assert warning is None
        assert dedup_tokens == frozenset({"contracts"})

    def test_strict_metadata_false_downgrades_to_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission = SimpleNamespace(config=SimpleNamespace(paths=["src/"]), domain="software-dev")
        monkeypatch.setattr(
            "specify_cli.acceptance.summary_core.validate_mission_paths",
            lambda *_a, **_k: SimpleNamespace(
                missing_paths=["src/"],
                missing_artifact_tokens=[],
                format_warnings=lambda: "missing src/ (advisory)",
            ),
        )

        violations, warning, dedup_tokens = evaluate_path_conventions(
            mission, tmp_path, tmp_path, tmp_path, strict_metadata=False
        )

        assert violations == []
        assert warning == "missing src/ (advisory)"
        assert dedup_tokens == frozenset()

    def test_empty_format_errors_falls_back_to_default_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission = SimpleNamespace(config=SimpleNamespace(paths=["src/"]), domain="software-dev")
        monkeypatch.setattr(
            "specify_cli.acceptance.summary_core.validate_mission_paths",
            lambda *_a, **_k: SimpleNamespace(
                missing_paths=["src/"],
                missing_artifact_tokens=[],
                format_errors=lambda: "",
            ),
        )

        violations, _warning, dedup_tokens = evaluate_path_conventions(
            mission, tmp_path, tmp_path, tmp_path, strict_metadata=True
        )

        assert violations == ["Path conventions not satisfied."]
        assert dedup_tokens == frozenset()


class TestBuildWarnings:
    def test_no_inputs_yields_no_warnings(self) -> None:
        result = build_warnings(missing_optional=[], path_violations=[], path_convention_warning=None)

        assert result == []

    def test_missing_optional_only(self) -> None:
        result = build_warnings(missing_optional=["quickstart.md"], path_violations=[], path_convention_warning=None)

        assert result == ["Optional artifacts missing: quickstart.md"]

    def test_path_violations_wins_over_convention_warning(self) -> None:
        result = build_warnings(missing_optional=[], path_violations=["bad"], path_convention_warning="advisory")

        assert result == ["Path conventions not satisfied."]

    def test_convention_warning_alone_is_surfaced(self) -> None:
        result = build_warnings(missing_optional=[], path_violations=[], path_convention_warning="advisory")

        assert result == ["advisory"]


# ===========================================================================
# summary_core predicates powering _build_recommended_fix_order's data table
# ===========================================================================


class TestFixOrderPredicates:
    def test_has_blocked_check_true(self) -> None:
        checks = [AcceptanceCheckDiagnostic(check="mission_branch", detail="x")]

        assert _has_blocked_check(checks, "mission_branch") is True
        assert _has_blocked_check(checks, "acceptance_matrix") is False

    def test_has_non_terminal_lane(self) -> None:
        assert _has_non_terminal_lane({"approved": ["WP01"], "in_review": []}) is False
        assert _has_non_terminal_lane({"approved": [], "in_review": ["WP01"]}) is True

    def test_has_issue_containing(self) -> None:
        assert _has_issue_containing(["Evidence: WP01 missing"], "Evidence:") is True
        assert _has_issue_containing(["unrelated"], "Evidence:") is False


# ===========================================================================
# gates_core guard-clause stages
# ===========================================================================


class TestResolveLanesManifestOrStop:
    def test_missing_manifest_returns_none_with_no_side_effects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        result = _resolve_lanes_manifest_or_stop(tmp_path, activity_issues, skipped, blocked)

        assert result is None
        assert activity_issues == [] and skipped == [] and blocked == []

    def test_corrupt_manifest_returns_none_with_blocked_and_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.lanes.persistence import CorruptLanesError

        def _raise(_fd: Path) -> Any:
            raise CorruptLanesError("lanes.json: invalid JSON")

        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", _raise)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        result = _resolve_lanes_manifest_or_stop(tmp_path, activity_issues, skipped, blocked)

        assert result is None
        assert len(blocked) == 1 and blocked[0].check == "lanes_manifest"
        assert len(skipped) == 4

    def test_valid_manifest_is_returned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x")
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: manifest)

        result = _resolve_lanes_manifest_or_stop(tmp_path, [], [], [])

        assert result is manifest


class TestEvaluateBranchGate:
    def _manifest(self) -> SimpleNamespace:
        return SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x")

    def test_target_branch_mismatch_stops(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.acceptance._target_branch_for_feature", lambda _fd: "main")
        activity_issues: list[str] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        should_continue = _evaluate_branch_gate(self._manifest(), tmp_path, "feat/target", activity_issues, [], blocked)

        assert should_continue is False
        assert len(blocked) == 1 and blocked[0].check == "mission_branch"
        assert "target branch mismatch" in activity_issues[0]

    def test_branch_outside_allowed_set_stops(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.acceptance._target_branch_for_feature", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)
        activity_issues: list[str] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        should_continue = _evaluate_branch_gate(self._manifest(), tmp_path, "some-other-branch", activity_issues, [], blocked)

        assert should_continue is False
        assert "must run on mission or target branch" in activity_issues[0]

    def test_planning_artifact_only_stops_with_skip_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.acceptance._target_branch_for_feature", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: True)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        should_continue = _evaluate_branch_gate(self._manifest(), tmp_path, "feat/target", activity_issues, skipped, blocked)

        assert should_continue is False
        assert activity_issues == [] and blocked == []
        assert len(skipped) == 4

    def test_all_gates_pass_continues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.acceptance._target_branch_for_feature", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)

        should_continue = _evaluate_branch_gate(self._manifest(), tmp_path, "kitty/mission-x", [], [], [])

        assert should_continue is True


class TestEvaluateAcceptanceMatrix:
    def test_missing_matrix_blocks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: None)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        _evaluate_acceptance_matrix(tmp_path, tmp_path, activity_issues, skipped, blocked, mutate_matrix=True)

        assert len(blocked) == 1 and blocked[0].check == "acceptance_matrix"
        assert len(skipped) == 3

    def test_missing_matrix_message_names_regenerate_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Field report: the missing-file message gave no next step, so an
        operator hand-authored a matrix by copying an unrelated mission's file.
        The message must name the actual regenerate command."""
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: None)
        feature_dir = tmp_path / "kitty-specs" / "demo"
        feature_dir.mkdir(parents=True)
        activity_issues: list[str] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        _evaluate_acceptance_matrix(tmp_path, feature_dir, activity_issues, [], blocked, mutate_matrix=True)

        assert "spec-kitty agent mission finalize-tasks --mission demo" in blocked[0].detail
        assert "spec-kitty agent mission finalize-tasks --mission demo" in activity_issues[0]

    def test_negative_invariants_enforced_when_mutate_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = SimpleNamespace(negative_invariants=[SimpleNamespace(name="no-secrets")], overall_verdict="pass")
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])
        enforce_calls: list[Any] = []
        write_calls: list[Any] = []
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.enforce_negative_invariants",
            # ``context`` is the WP04 gate-context kwarg (deferral + provenance).
            lambda _repo, invariants, **_kw: enforce_calls.append(invariants) or invariants,
        )
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, m: write_calls.append(m))

        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], [], [], mutate_matrix=True)

        assert enforce_calls and write_calls

    def test_populate_criteria_from_review_evidence_called_when_mutate_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-008 (IC-04, T3): ``_evaluate_acceptance_matrix`` threads the
        matrix's ``criteria`` and the coord-resolved status surface into
        :func:`~specify_cli.acceptance.matrix.populate_criteria_from_review_
        evidence` BEFORE the verdict is read, when ``mutate_matrix=True``."""
        original_criteria = [SimpleNamespace(criterion_id="AC-001")]
        populated_criteria = [SimpleNamespace(criterion_id="AC-001", pass_fail="pass")]
        matrix = SimpleNamespace(
            criteria=original_criteria, negative_invariants=[], overall_verdict="pass"
        )
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, _m: None)
        populate_calls: list[Any] = []

        def _populate(status_dir: Path, criteria: Any) -> Any:
            populate_calls.append((status_dir, criteria))
            return populated_criteria

        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.populate_criteria_from_review_evidence", _populate
        )

        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], [], [], mutate_matrix=True)

        assert populate_calls
        assert populate_calls[0][1] is original_criteria
        assert matrix.criteria is populated_criteria

    def test_populate_criteria_from_review_evidence_skipped_when_mutate_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Diagnose mode (``mutate_matrix=False``) never mutates the matrix --
        the population call must not fire either, symmetric with the
        negative-invariants arm."""
        original_criteria = [SimpleNamespace(criterion_id="AC-001")]
        matrix = SimpleNamespace(
            criteria=original_criteria, negative_invariants=[], overall_verdict="pass"
        )
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])

        def _fail(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("must not populate/write in diagnose mode")

        monkeypatch.setattr("specify_cli.acceptance.matrix.populate_criteria_from_review_evidence", _fail)
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", _fail)

        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], [], [], mutate_matrix=False)

        assert matrix.criteria is original_criteria

    def test_negative_invariants_skipped_when_mutate_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = SimpleNamespace(negative_invariants=[SimpleNamespace(name="no-secrets")], overall_verdict="pass")
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])

        def _fail(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("must not enforce/write in diagnose mode")

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _fail)
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", _fail)
        skipped: list[AcceptanceCheckDiagnostic] = []

        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], skipped, [], mutate_matrix=False)

        assert any(item.check == "negative_invariants" for item in skipped)

    @pytest.mark.parametrize(
        ("verdict", "expected_fragment"),
        [
            ("fail", "verdict is 'fail'"),
            ("pending", "verdict is 'pending'"),
        ],
    )
    def test_verdict_fail_and_pending_become_activity_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verdict: str, expected_fragment: str) -> None:
        matrix = SimpleNamespace(negative_invariants=[], overall_verdict=verdict)
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])
        # WP04 / T016 (#2318): the gate now persists the recomputed verdict
        # unconditionally when mutate_matrix=True, not only when negative
        # invariants are present. This test's fixture is a bare SimpleNamespace
        # (no ``to_dict``), so the real writer is stubbed out here -- the write
        # itself is covered by ``test_acceptance_verdict_command.py``.
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, _m: None)
        activity_issues: list[str] = []

        _evaluate_acceptance_matrix(tmp_path, tmp_path, activity_issues, [], [], mutate_matrix=True)

        assert any(expected_fragment in issue for issue in activity_issues)

    def test_verdict_pass_is_silent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = SimpleNamespace(negative_invariants=[], overall_verdict="pass")
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: [])
        # WP04 / T016: see the comment in the parametrized test above.
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, _m: None)
        activity_issues: list[str] = []

        _evaluate_acceptance_matrix(tmp_path, tmp_path, activity_issues, [], [], mutate_matrix=True)

        assert activity_issues == []


class TestRecoverNormalizedText:
    """F1 campsite (#2464 squad): the encoding-recovery decision extracted from
    ``normalize_feature_encoding`` into a pure ``bytes -> str | None`` core."""

    def test_valid_utf8_returns_none(self) -> None:
        assert _recover_normalized_text(b"already clean\n") is None

    def test_cp1252_smart_punctuation_is_mapped_to_ascii(self) -> None:
        # Right single quote (’), em dash (—), ellipsis (…) in cp1252.
        data = "it’s — done…".encode("cp1252")
        assert _recover_normalized_text(data) == "it's -- done..."

    def test_utf8_bom_file_is_already_valid_and_skipped(self) -> None:
        # A leading UTF-8 BOM is itself valid UTF-8, so such a file needs no
        # recovery -- the decoder returns None (skip) before the defensive
        # BOM-lstrip, which only guards the legacy-decode fallback path.
        data = "﻿heading".encode()
        assert _recover_normalized_text(data) is None

    def test_undecodable_bytes_fall_back_to_lossy_replace(self) -> None:
        # 0x81 is undefined in cp1252 -> latin-1 decodes it, no crash.
        result = _recover_normalized_text(b"plain \x81 tail")
        assert result is not None and "plain" in result and "tail" in result


class TestGatherPrimaryEncodingCandidates:
    """F1 campsite: the candidate-gathering walk (primary docs + tasks/research/
    checklists markdown) extracted as a pure filesystem helper."""

    def test_gathers_existing_primary_docs_and_markdown_subtrees(self, tmp_path: Path) -> None:
        (tmp_path / "spec.md").write_text("s", encoding="utf-8")
        (tmp_path / "plan.md").write_text("p", encoding="utf-8")
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        (tasks / "WP01.md").write_text("w", encoding="utf-8")
        (tmp_path / "research").mkdir()
        (tmp_path / "research" / "note.md").write_text("r", encoding="utf-8")

        found = {p.name for p in _gather_primary_encoding_candidates(tmp_path)}
        assert {"spec.md", "plan.md", "WP01.md", "note.md"} <= found

    def test_absent_subtrees_are_skipped(self, tmp_path: Path) -> None:
        # No tasks/research/checklists dirs and no primary docs -> empty result.
        assert _gather_primary_encoding_candidates(tmp_path) == []
