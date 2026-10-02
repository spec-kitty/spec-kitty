"""WP14 (coord-artifact-single-home-01M3V4BE): planning-command consumers render per-surface outcomes.

Covers T074 (setup-plan masking), T075 (setup-plan's two discarded-result
sites) and T078 (consumer tests + C-008 controls + JSON additivity) for the
``mission_setup_plan.py`` surface (contracts/commit-outcome.md).

``_commit_to_branch`` never naturally splits a single planning-artifact file
across the PRIMARY/COORDINATION partitions (``spec.md``/``plan.md``/
``tasks.md`` are always PRIMARY-kind), so a genuinely mixed-surface batch is
reproduced here by monkeypatching ``commit_for_mission`` at its owning module
(``specify_cli.coordination.commit_router``) to return a crafted
:class:`CommitRouterResult` carrying two surfaces -- a committed PRIMARY
surface alongside a COORDINATION surface refused with ``STATUS_LOCK_HELD``.
This is the same "test via a stubbed CommitRouterResult, labelled as a unit
test" escape hatch the WP prompt names for the report-transaction consumer
(T076 edge cases), applied here for the identical reason.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import specify_cli.coordination.commit_router as commit_router_module
from specify_cli.cli.commands.agent.mission_setup_plan import (
    CommitToBranchResult,
    _build_setup_plan_result,
    _commit_to_branch,
    _warn_on_incomplete_surfaces,
)
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome, commit_outcome_payload
from specify_cli.coordination.commit_router import CommitRouterResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_COORD_BRANCH = "kitty/mission-demo-01TESTPLAN"
_TARGET_BRANCH = "topic"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _git(repo, "add", "plan.md")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "seed")


def _mixed_surfaces_result(*, primary_ref: str) -> CommitRouterResult:
    """A split batch: PRIMARY committed cleanly, COORDINATION refused by a contended status lock."""
    primary = SurfaceOutcome(
        surface="primary",
        branch=primary_ref,
        status="committed",
        commit_hash="abc1234567890",
        committed=("kitty-specs/demo/plan.md",),
    )
    coordination = SurfaceOutcome(
        surface="coordination",
        branch=_COORD_BRANCH,
        status="error",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
        diagnostic="status lock held by another writer",
    )
    return CommitRouterResult(
        status="committed",
        placement_ref=primary_ref,
        commit_hash="abc1234567890",
        surfaces=(primary, coordination),
    )


# ---------------------------------------------------------------------------
# T075 -- _commit_to_branch carries the router's full surfaces tuple through.
# ---------------------------------------------------------------------------


def test_commit_to_branch_carries_router_surfaces_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: mixed)

    result = _commit_to_branch(plan_file, "demo", "plan", tmp_path, _TARGET_BRANCH, json_output=True)

    assert result.status == "committed"
    assert result.surfaces == mixed.surfaces
    # Load-bearing (T074): the non-caller COORDINATION surface's STATUS_LOCK_HELD
    # refusal reaches the JSON payload even though the top-level/caller status
    # is "committed" -- the exact masking this WP cures (#5513, #5501).
    payload = commit_outcome_payload(result)
    surface_names = {entry["surface"] for entry in payload["surfaces"]}
    assert surface_names == {"primary", "coordination"}
    coordination_payload = next(entry for entry in payload["surfaces"] if entry["surface"] == "coordination")
    assert coordination_payload["refused"][0]["reason"] == "STATUS_LOCK_HELD"


def test_commit_to_branch_unchanged_arm_carries_surfaces_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage: the genuine-no-op ``unchanged`` arm also carries the router's ``surfaces`` through."""
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    single = CommitRouterResult(
        status="unchanged",
        placement_ref=_TARGET_BRANCH,
        reason="no_op_already_committed",
        surfaces=(SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="unchanged", commit_hash=None),),
    )
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: single)

    result = _commit_to_branch(plan_file, "demo", "plan", tmp_path, _TARGET_BRANCH, json_output=True)

    assert result.status == "unchanged"
    assert result.surfaces == single.surfaces


# ---------------------------------------------------------------------------
# B6 (cycle 2 review): a text-mode (json_output=False) test for the
# render-every-arm guard (mission_setup_plan.py ~L283) -- every existing
# ``_commit_to_branch`` test runs with json_output=True, so mutant M2
# (replacing the render guard with ``if False``) survived the whole suite.
# ---------------------------------------------------------------------------


def test_commit_to_branch_renders_surface_lines_in_text_mode_on_committed_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Kills M2: with the render guard replaced by ``if False``, no surface
    line reaches stdout and this assertion fails."""
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: mixed)

    result = _commit_to_branch(plan_file, "demo", "plan", tmp_path, _TARGET_BRANCH, json_output=False)

    assert result.status == "committed"
    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


def test_commit_to_branch_renders_surface_lines_in_text_mode_on_no_op_wrong_surface_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same render-every-arm guard, exercised on the ``no_op_wrong_surface`` arm."""
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    primary = SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="committed", commit_hash="abc", committed=("plan.md",))
    coordination = SurfaceOutcome(
        surface="coordination",
        branch=_COORD_BRANCH,
        status="refused",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
    )
    wrong_surface = CommitRouterResult(
        status="no_op_wrong_surface",
        placement_ref=_TARGET_BRANCH,
        diagnostic="artifact absent at the resolved placement",
        surfaces=(primary, coordination),
    )
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: wrong_surface)

    result = _commit_to_branch(plan_file, "demo", "plan", tmp_path, _TARGET_BRANCH, json_output=False)

    assert result.status == "no_op_wrong_surface"
    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


# ---------------------------------------------------------------------------
# T075 -- the two discarded-result sites now warn via _warn_on_incomplete_surfaces.
# ---------------------------------------------------------------------------


def test_warn_on_incomplete_surfaces_silent_on_an_all_success_batch(capsys: pytest.CaptureFixture[str]) -> None:
    """D8 rule: an all-committed/unchanged batch prints nothing (C-008 control)."""
    all_ok = CommitRouterResult(
        status="committed",
        placement_ref=_TARGET_BRANCH,
        commit_hash="abc",
        surfaces=(SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="committed", commit_hash="abc", committed=("a",)),),
    )

    _warn_on_incomplete_surfaces(all_ok, json_output=False)

    assert capsys.readouterr().out == ""


def test_warn_on_incomplete_surfaces_silent_in_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)

    _warn_on_incomplete_surfaces(mixed, json_output=True)

    assert capsys.readouterr().out == ""


def test_warn_on_incomplete_surfaces_renders_the_refused_surface(capsys: pytest.CaptureFixture[str]) -> None:
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)

    _warn_on_incomplete_surfaces(mixed, json_output=False)

    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


# ---------------------------------------------------------------------------
# T074/T078 -- setup-plan's JSON envelope gains `surfaces` additively.
# ---------------------------------------------------------------------------


def _base_build_kwargs(tmp_path: Path, *, plan_commit_result: CommitToBranchResult | None) -> dict[str, Any]:
    return {
        "plan_file": tmp_path / "plan.md",
        "spec_file": tmp_path / "spec.md",
        "feature_dir": tmp_path / "kitty-specs" / "demo",
        "mission_slug": "demo",
        "plan_is_substantive": True,
        "plan_blocked_reason": None,
        "plan_commit_result": plan_commit_result,
        "gap_analysis_path": None,
        "generators_detected": [],
        "target_branch": _TARGET_BRANCH,
        "current_branch": _TARGET_BRANCH,
    }


def test_setup_plan_reports_skipped_surface_in_json(tmp_path: Path) -> None:
    """T074 (setup-plan half): a refused coordination surface reaches the JSON envelope.

    RED at the WP base: ``plan_commit_result`` was turned into ``commit_hash``/
    ``commit_status``/``commit_diagnostic`` alone -- the four legacy fields
    (contract rule 4) -- so a non-caller surface's refusal never reached the
    JSON payload at all.
    """
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    commit_result = CommitToBranchResult(status="committed", placement_ref=_TARGET_BRANCH, commit_hash="abc1234567890", surfaces=mixed.surfaces)

    outcome = _build_setup_plan_result(**_base_build_kwargs(tmp_path, plan_commit_result=commit_result))

    assert "surfaces" in outcome.payload
    surfaces = outcome.payload["surfaces"]
    assert isinstance(surfaces, list)
    surface_names = {entry["surface"] for entry in surfaces}
    assert surface_names == {"primary", "coordination"}
    coordination_payload = next(entry for entry in surfaces if entry["surface"] == "coordination")
    assert coordination_payload["refused"][0]["reason"] == "STATUS_LOCK_HELD"


def test_setup_plan_json_is_additive_when_every_surface_committed(tmp_path: Path) -> None:
    """C-008 control: a non-coordination Mission's existing JSON keys are unchanged (plus the additive key)."""
    single = CommitRouterResult(
        status="committed",
        placement_ref=_TARGET_BRANCH,
        commit_hash="abc1234567890",
        surfaces=(SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="committed", commit_hash="abc1234567890", committed=("plan.md",)),),
    )
    commit_result = CommitToBranchResult(status="committed", placement_ref=_TARGET_BRANCH, commit_hash="abc1234567890", surfaces=single.surfaces)

    before = _build_setup_plan_result(**_base_build_kwargs(tmp_path, plan_commit_result=None))
    after = _build_setup_plan_result(**_base_build_kwargs(tmp_path, plan_commit_result=commit_result))

    # Every pre-existing key the no-commit-result payload carries is present,
    # byte-identical, in the single-surface payload too (JSON additivity).
    shared_keys = set(before.payload) & set(after.payload)
    for key in shared_keys:
        if key in ("commit_created", "commit_hash", "commit_status"):
            continue  # these three are populated BY plan_commit_result itself (unchanged shape)
        assert before.payload[key] == after.payload[key], key
    assert "surfaces" in after.payload


def test_setup_plan_json_omits_surfaces_when_commit_result_carries_none(tmp_path: Path) -> None:
    """A legacy/empty-``surfaces`` ``CommitToBranchResult`` adds no ``surfaces`` key (additive, never a crash)."""
    commit_result = CommitToBranchResult(status="unchanged", placement_ref=_TARGET_BRANCH)

    outcome = _build_setup_plan_result(**_base_build_kwargs(tmp_path, plan_commit_result=commit_result))

    assert "surfaces" not in outcome.payload


# ---------------------------------------------------------------------------
# B3 (cycle 2 review): record-analysis + report-transaction consumer tests,
# each with a one-surface-refused fixture asserting the surface name, fate
# and reason. Mutation-sensitive: kills M5-M8 from the review's mutation
# table (orchestrator _record_analysis_commit_surfaces_payload always `{}`;
# the deleted _print_report_transaction_payload always raw; record-analysis
# payload drops `surfaces`; record-analysis drops the warning).
# ---------------------------------------------------------------------------

_ANALYSIS_BODY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


def _write_primary_mission(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")


def _patch_record_analysis_resolution(monkeypatch: pytest.MonkeyPatch, repo_root: Path, feature_dir: Path) -> None:
    import specify_cli.cli.commands.agent.mission_record_analysis as seam

    monkeypatch.setattr(seam, "locate_project_root", lambda: repo_root)
    monkeypatch.setattr(seam, "get_main_repo_root", lambda path: path)
    monkeypatch.setattr(seam, "_find_feature_directory", lambda *_args, **_kwargs: feature_dir)
    monkeypatch.setattr(seam, "get_feature_target_branch", lambda *_args, **_kwargs: _TARGET_BRANCH)


def test_commit_analysis_report_carries_router_surfaces_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3: ``_commit_analysis_report`` never discards the router's surfaces (T076 extraction)."""
    import specify_cli.coordination.commit_router as commit_router_mod
    from specify_cli.cli.commands.agent.mission_record_analysis import _commit_analysis_report

    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(commit_router_mod, "commit_for_mission", lambda **_kwargs: mixed)

    result = _commit_analysis_report(repo_root=tmp_path, mission_slug="demo", report_path=tmp_path / "analysis-report.md", target_branch=_TARGET_BRANCH)

    assert result is not None
    assert result.surfaces == mixed.surfaces
    coordination = next(s for s in result.surfaces if s.surface == "coordination")
    assert coordination.refused[0].reason == "STATUS_LOCK_HELD"


def test_commit_analysis_report_degrades_to_none_on_a_best_effort_commit_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3 coverage: the narrowed best-effort exception set degrades to ``None`` (the commit is never fatal)."""
    import specify_cli.coordination.commit_router as commit_router_mod
    from specify_cli.cli.commands.agent.mission_record_analysis import _commit_analysis_report

    def _boom(**_kwargs: object) -> None:
        raise RuntimeError("protected target ref")

    monkeypatch.setattr(commit_router_mod, "commit_for_mission", _boom)

    result = _commit_analysis_report(repo_root=tmp_path, mission_slug="demo", report_path=tmp_path / "analysis-report.md", target_branch=_TARGET_BRANCH)

    assert result is None


def test_record_analysis_warn_on_incomplete_surfaces_silent_in_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """B3 coverage: record-analysis's OWN ``_warn_on_incomplete_surfaces`` copy -- json_output short-circuit."""
    import specify_cli.cli.commands.agent.mission_record_analysis as seam

    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)

    seam._warn_on_incomplete_surfaces(mixed, json_output=True)

    assert capsys.readouterr().out == ""


def test_record_analysis_warn_on_incomplete_surfaces_silent_on_an_all_success_batch(capsys: pytest.CaptureFixture[str]) -> None:
    """B3 coverage: record-analysis's OWN ``_warn_on_incomplete_surfaces`` copy -- D8 all-success control."""
    import specify_cli.cli.commands.agent.mission_record_analysis as seam

    all_ok = CommitRouterResult(
        status="committed",
        placement_ref=_TARGET_BRANCH,
        commit_hash="abc",
        surfaces=(SurfaceOutcome(surface="primary", branch=_TARGET_BRANCH, status="committed", commit_hash="abc", committed=("a",)),),
    )

    seam._warn_on_incomplete_surfaces(all_ok, json_output=False)

    assert capsys.readouterr().out == ""


def test_record_analysis_json_carries_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3: record-analysis's JSON envelope gains ``surfaces`` (the main, non-report-only path)."""
    import specify_cli.cli.commands.agent.mission_record_analysis as seam

    slug = "demo-b3-json"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_primary_mission(feature_dir)
    _patch_record_analysis_resolution(monkeypatch, tmp_path, feature_dir)
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(seam, "_commit_analysis_report", lambda **_kwargs: mixed)
    input_file = tmp_path.parent / f"{tmp_path.name}-analysis.md"
    input_file.write_text(_ANALYSIS_BODY, encoding="utf-8")
    emitted: dict[str, object] = {}
    monkeypatch.setattr(seam, "_emit_json", lambda payload: emitted.update(payload))

    seam.record_analysis(feature=slug, input_file=str(input_file), analyzer_agent=None, json_output=True, report_only=False)

    assert emitted["success"] is True
    surfaces = emitted["surfaces"]
    assert isinstance(surfaces, list)
    surface_names = {entry["surface"] for entry in surfaces}
    assert surface_names == {"primary", "coordination"}
    coordination_payload = next(entry for entry in surfaces if entry["surface"] == "coordination")
    assert coordination_payload["refused"][0]["reason"] == "STATUS_LOCK_HELD"


def test_record_analysis_text_warns_on_incomplete_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """B3: record-analysis's text-mode warning names the refused surface and reason."""
    import specify_cli.cli.commands.agent.mission_record_analysis as seam

    slug = "demo-b3-text"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_primary_mission(feature_dir)
    _patch_record_analysis_resolution(monkeypatch, tmp_path, feature_dir)
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(seam, "_commit_analysis_report", lambda **_kwargs: mixed)
    input_file = tmp_path.parent / f"{tmp_path.name}-analysis-2.md"
    input_file.write_text(_ANALYSIS_BODY, encoding="utf-8")

    seam.record_analysis(feature=slug, input_file=str(input_file), analyzer_agent=None, json_output=False, report_only=False)

    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


def test_record_analysis_report_only_renders_surfaces_in_text_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """B3 / B4: the ``--report-only`` text render prints the payload AND the surface lines, additively."""
    import specify_cli.cli.commands.agent.mission_record_analysis as seam
    from specify_cli.git.report_transaction import ReportTransactionOutcome

    slug = "demo-b3-report-only"
    feature_dir = tmp_path / "kitty-specs" / slug
    _write_primary_mission(feature_dir)
    _patch_record_analysis_resolution(monkeypatch, tmp_path, feature_dir)
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    stub_outcome = ReportTransactionOutcome({"success": True, "commit_status": "committed", "commit_hash": "abc1234567890"}, router_result=mixed)
    import specify_cli.git.report_transaction as report_transaction_mod

    monkeypatch.setattr(report_transaction_mod, "record_report_transaction", lambda **_kwargs: stub_outcome)
    input_file = tmp_path.parent / f"{tmp_path.name}-analysis-3.md"
    input_file.write_text(_ANALYSIS_BODY, encoding="utf-8")

    seam.record_analysis(feature=slug, input_file=str(input_file), analyzer_agent=None, json_output=False, report_only=True)

    out = capsys.readouterr().out
    # The raw payload still prints (additive, never replaced -- B4).
    assert "commit_status" in out
    assert "committed" in out
    # PLUS the surface lines naming the refused surface and reason.
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


# ---------------------------------------------------------------------------
# Coverage: setup-plan's two discarded-result sites (T075) -- the gap-analysis
# and generator-config commits, each calling _warn_on_incomplete_surfaces on a
# surface that is neither committed nor unchanged.
# ---------------------------------------------------------------------------


def test_run_documentation_gap_analysis_warns_on_incomplete_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from kernel.clock import now_utc
    from specify_cli.cli.commands.agent.mission_setup_plan import _run_documentation_gap_analysis

    repo_root = tmp_path
    (repo_root / "docs").mkdir()
    feature_dir = repo_root / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    meta_file = feature_dir / "meta.json"
    meta_file.write_text('{"mission_type": "documentation", "documentation_state": {"iteration_mode": "gap_filling"}}', encoding="utf-8")

    class _FakeCoverageMatrix:
        def get_coverage_percentage(self) -> float:
            return 0.5

    class _FakeAnalysis:
        analysis_date = now_utc()
        coverage_matrix = _FakeCoverageMatrix()

    monkeypatch.setattr("specify_cli.doc_analysis.gap_analysis.generate_gap_analysis_report", lambda *_a, **_k: _FakeAnalysis())
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: mixed)

    result = _run_documentation_gap_analysis(feature_dir, "demo", repo_root, meta_file, target_branch=_TARGET_BRANCH, json_output=False)

    assert result is not None
    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out


def test_detect_and_configure_generators_warns_on_incomplete_surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.agent.mission_setup_plan import _detect_and_configure_generators

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    meta_file = feature_dir / "meta.json"
    meta_file.write_text('{"mission_type": "documentation", "documentation_state": {"iteration_mode": "gap_filling"}}', encoding="utf-8")

    monkeypatch.setattr("specify_cli.doc_analysis.doc_generators.SphinxGenerator.detect", lambda self, _project_root: True)
    monkeypatch.setattr("specify_cli.doc_analysis.doc_generators.JSDocGenerator.detect", lambda self, _project_root: False)
    monkeypatch.setattr("specify_cli.doc_analysis.doc_generators.RustdocGenerator.detect", lambda self, _project_root: False)
    mixed = _mixed_surfaces_result(primary_ref=_TARGET_BRANCH)
    monkeypatch.setattr(commit_router_module, "commit_for_mission", lambda **_kwargs: mixed)

    detected = _detect_and_configure_generators("demo", repo_root, meta_file, target_branch=_TARGET_BRANCH, json_output=False)

    assert [entry["name"] for entry in detected] == ["sphinx"]
    out = capsys.readouterr().out
    assert "coordination" in out
    assert "STATUS_LOCK_HELD" in out
