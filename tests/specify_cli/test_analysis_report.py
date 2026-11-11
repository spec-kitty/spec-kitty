from __future__ import annotations

from pathlib import Path
import subprocess
import traceback
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

from specify_cli.analysis_report import (
    ANALYSIS_REPORT_FILENAME,
    check_analysis_report_current,
    write_analysis_report,
)
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.workflow import _require_current_analysis_report
from specify_cli.frontmatter import FrontmatterManager


def _write_required_artifacts(feature_dir):
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")


def _init_committed_git_project(repo_root: Path, *, branch: str = "feature") -> None:
    (repo_root / ".kittify").mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
    subprocess.run(["git", "branch", "-M", branch], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True)


_CARRIER_READY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


def test_write_analysis_report_records_input_hashes(tmp_path):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    result = write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body=_CARRIER_READY,
        analyzer_agent="codex",
    )

    assert result.path == feature_dir / ANALYSIS_REPORT_FILENAME
    frontmatter, body = FrontmatterManager().read(result.path)
    assert frontmatter["artifact_type"] == "spec-kitty.analysis-report"
    assert frontmatter["command"] == "/spec-kitty.analyze"
    assert frontmatter["analyzer_agent"] == "codex"
    assert frontmatter["input_artifacts"]["spec.md"]["sha256"]
    assert frontmatter["verdict"] == "ready"
    # The carrier frontmatter is consumed by the recorder; the persisted body is
    # the human-readable report only.
    assert "# Specification Analysis Report" in body
    assert "schema: analysis-findings/v1" not in body


def test_analysis_report_freshness_detects_stale_inputs(tmp_path):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Report\n\nPASS\n",
    )

    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    (feature_dir / "tasks.md").write_text("# Tasks\n\nChanged.\n", encoding="utf-8")
    freshness = check_analysis_report_current(feature_dir, repo_root)
    assert freshness.ok is False
    assert freshness.reason == "stale_analysis_report"
    assert "tasks.md" in freshness.mismatches


def test_analysis_report_survives_subtask_checkbox_churn(tmp_path):
    """#1764: ``mark-status``/``move-task`` flipping subtask checkboxes in tasks.md
    must NOT invalidate a recorded analysis (only substantive changes should)."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n- [ ] T001 Do the thing (WP01)\n- [ ] T002 Do the other thing (WP01)\n",
        encoding="utf-8",
    )
    write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body="# Report\n\nPASS\n")
    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    # Status churn: a subtask is marked done (mark-status flips [ ] -> [x]).
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n- [x] T001 Do the thing (WP01)\n- [ ] T002 Do the other thing (WP01)\n",
        encoding="utf-8",
    )
    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    # Substantive change to a task definition: still goes stale.
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n- [x] T001 Do a DIFFERENT thing (WP01)\n- [ ] T002 Do the other thing (WP01)\n",
        encoding="utf-8",
    )
    freshness = check_analysis_report_current(feature_dir, repo_root)
    assert freshness.ok is False
    assert "tasks.md" in freshness.mismatches


def test_analysis_report_survives_pipe_table_status_churn(tmp_path):
    """#2493.1/#1862: ``mark-status`` flipping a pipe-table status cell
    (`[ ]`/`[x]`/`[X]`/`[D]`/`[P]`, written by
    ``tasks_materialization.py``'s pipe-table row updater) must NOT
    invalidate a recorded analysis. A mixed bullet+pipe-table churn must
    also stay current."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] T003 Do a bullet thing (WP01)\n\n"
        "| ID | Description | Status |\n"
        "|----|--------------|--------|\n"
        "| T001 | Do the thing | [ ] |\n"
        "| T002 | Do the other thing | [ ] |\n",
        encoding="utf-8",
    )
    write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body="# Report\n\nPASS\n")
    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    # Pipe-table status churn only: mark-status flips [ ] -> [D]/[P]/[x].
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [ ] T003 Do a bullet thing (WP01)\n\n"
        "| ID | Description | Status |\n"
        "|----|--------------|--------|\n"
        "| T001 | Do the thing | [D] |\n"
        "| T002 | Do the other thing | [P] |\n",
        encoding="utf-8",
    )
    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    # Mixed churn: the existing bullet checkbox AND pipe-table cells both flip.
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "- [x] T003 Do a bullet thing (WP01)\n\n"
        "| ID | Description | Status |\n"
        "|----|--------------|--------|\n"
        "| T001 | Do the thing | [x] |\n"
        "| T002 | Do the other thing | [X] |\n",
        encoding="utf-8",
    )
    assert check_analysis_report_current(feature_dir, repo_root).ok is True


def test_analysis_report_stales_on_pipe_table_description_change(tmp_path):
    """A substantive change to a pipe-table row's DESCRIPTION cell (not the
    status cell) must still stale the report — guards against an over-broad
    pipe-table normalizer (#2493.1)."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "| ID | Description | Status |\n"
        "|----|--------------|--------|\n"
        "| T001 | Do the thing | [ ] |\n",
        encoding="utf-8",
    )
    write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body="# Report\n\nPASS\n")
    assert check_analysis_report_current(feature_dir, repo_root).ok is True

    # Substantive change to the row's description text: still goes stale.
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n"
        "| ID | Description | Status |\n"
        "|----|--------------|--------|\n"
        "| T001 | Do a DIFFERENT thing | [ ] |\n",
        encoding="utf-8",
    )
    freshness = check_analysis_report_current(feature_dir, repo_root)
    assert freshness.ok is False
    assert "tasks.md" in freshness.mismatches


def test_charter_hash_resolves_canonical_root_from_worktree(tmp_path):
    """#1823: analysis reports read from a linked worktree must hash the
    canonical (main checkout) charter, not the worktree-local copy."""
    from charter.bundle import CHARTER_YAML
    from charter.resolution import resolve_canonical_repo_root

    from specify_cli.analysis_report import _sha256_file, collect_input_artifact_hashes

    main = tmp_path / "main"
    charter_file = main / CHARTER_YAML
    charter_file.parent.mkdir(parents=True)
    charter_file.write_text("charter_version: 1\n", encoding="utf-8")
    _init_committed_git_project(main)

    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-b", "lane", str(worktree)],
        cwd=main, check=True, capture_output=True,
    )
    # Diverge the worktree-local copy: hashing it instead of the canonical
    # charter is exactly the #1823 bug.
    worktree_charter = worktree / CHARTER_YAML
    worktree_charter.parent.mkdir(parents=True, exist_ok=True)
    worktree_charter.write_text("charter_version: 2\nmodified: true\n", encoding="utf-8")

    feature_dir = worktree / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    resolve_canonical_repo_root.cache_clear()
    hashes = collect_input_artifact_hashes(feature_dir, worktree)

    # FR-007/NFR-001: recorded path is repo-relative (relative to the resolved
    # canonical root -- the MAIN checkout here, not the worktree), never absolute.
    assert hashes["charter"]["path"] == str(charter_file.resolve().relative_to(main.resolve()))
    assert hashes["charter"]["sha256"] == _sha256_file(charter_file)
    assert hashes["charter"]["sha256"] != _sha256_file(worktree_charter)


def test_charter_hash_falls_back_to_repo_root_outside_git(tmp_path):
    """Outside any git repo the resolver cannot run; the charter probe must
    degrade to the passed repo_root instead of raising."""
    from charter.bundle import CHARTER_YAML
    from charter.resolution import resolve_canonical_repo_root

    from specify_cli.analysis_report import collect_input_artifact_hashes

    charter_file = tmp_path / CHARTER_YAML
    charter_file.parent.mkdir(parents=True)
    charter_file.write_text("charter_version: 1\n", encoding="utf-8")
    feature_dir = tmp_path / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    resolve_canonical_repo_root.cache_clear()
    hashes = collect_input_artifact_hashes(feature_dir, tmp_path)

    # FR-007/NFR-001: outside git, canonical_root falls back to repo_root
    # (tmp_path here), so the recorded path is relative to tmp_path.
    assert hashes["charter"]["path"] == str(charter_file.relative_to(tmp_path))
    assert hashes["charter"]["sha256"] is not None


def test_charter_hash_propagates_git_common_dir_unavailable(tmp_path):
    """If git/common-dir resolution is unavailable, do not synthesize a local
    charter hash that pretends canonical evidence was available."""
    from charter.bundle import CHARTER_YAML
    from charter.resolution import GitCommonDirUnavailableError, resolve_canonical_repo_root

    from specify_cli.analysis_report import collect_input_artifact_hashes

    charter_file = tmp_path / CHARTER_YAML
    charter_file.parent.mkdir(parents=True)
    charter_file.write_text("charter_version: 1\n", encoding="utf-8")
    feature_dir = tmp_path / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    resolve_canonical_repo_root.cache_clear()
    with (
        patch("kernel.git_topology.subprocess.run", side_effect=FileNotFoundError("git")),
        pytest.raises(GitCommonDirUnavailableError),
    ):
        collect_input_artifact_hashes(feature_dir, tmp_path)


def test_implement_gate_blocks_missing_analysis_report(tmp_path, capsys):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    with pytest.raises(typer.Exit):
        _require_current_analysis_report(feature_dir, repo_root, "sample-01KS")

    out = capsys.readouterr().out
    assert "analysis_report_required" in out
    # Missing-report branch now emits a two-step recovery (WP03 / FR-005).
    assert "Run step 1: /spec-kitty.analyze" in out
    assert (
        "Run step 2: spec-kitty agent mission record-analysis "
        "--mission sample-01KS --input-file -"
    ) in out


def test_require_analysis_report_missing_emits_two_step_recovery(tmp_path, capsys):
    """_require_current_analysis_report emits two-step recovery for a missing report."""
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "my-mission"
    _write_required_artifacts(feature_dir)
    # Do NOT write analysis-report.md.

    with pytest.raises(typer.Exit):
        _require_current_analysis_report(feature_dir, repo_root, "my-mission")

    out = capsys.readouterr().out
    assert "Error: analysis_report_required:" in out
    assert "Run step 1: /spec-kitty.analyze" in out
    assert (
        "Run step 2: spec-kitty agent mission record-analysis "
        "--mission my-mission --input-file -"
    ) in out


def test_require_analysis_report_carrier_format_emits_recovery_command(tmp_path, capsys):
    """_require_current_analysis_report emits the exact carrier-format recovery command."""
    from specify_cli.analysis_report import ANALYSIS_REPORT_FILENAME

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "my-mission"
    _write_required_artifacts(feature_dir)

    # Write a carrier-format file (analysis-findings/v1 schema, not outer-wrapper).
    carrier_content = (
        "---\n"
        "schema: analysis-findings/v1\n"
        "findings: []\n"
        "counts:\n"
        "  critical: 0\n"
        "  high: 0\n"
        "  medium: 0\n"
        "  low: 0\n"
        "verdict_hint: ready\n"
        "---\n\n"
        "Report body.\n"
    )
    report_path = feature_dir / ANALYSIS_REPORT_FILENAME
    report_path.write_text(carrier_content, encoding="utf-8")

    with pytest.raises(typer.Exit):
        _require_current_analysis_report(feature_dir, repo_root, "my-mission")

    out = capsys.readouterr().out
    assert "Error: analysis_report_required:" in out
    # The raw reason code must NOT be shown; the explanatory message is shown instead.
    assert "carrier_format_not_wrapped" not in out
    assert "carrier format (analysis-findings/v1)" in out
    assert "Recovery: spec-kitty agent mission record-analysis" in out
    assert "--mission my-mission" in out
    assert str(report_path) in out


def test_implement_gate_allows_current_analysis_report(tmp_path):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Report\n\nPASS\n",
    )

    _require_current_analysis_report(feature_dir, repo_root, "sample-01KS")


def test_record_analysis_command_persists_report(tmp_path, monkeypatch):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    input_file = tmp_path / "analysis.md"
    input_file.write_text("# Analysis\n\nCritical Issues Count: 0\nPASS\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.mission_record_analysis.locate_project_root",
        lambda: repo_root,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.mission_record_analysis.get_main_repo_root",
        lambda path: path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.mission.resolve_mission_handle",
        lambda _handle, _repo_root: SimpleNamespace(feature_dir=feature_dir),
    )
    emitted: dict[str, object] = {}
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.mission_record_analysis._emit_json",
        lambda payload: emitted.update(payload),
    )

    result = CliRunner().invoke(
        mission_app,
        [
            "record-analysis",
            "--mission",
            feature_dir.name,
            "--input-file",
            str(input_file),
            "--agent",
            "codex",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert emitted["success"] is True
    report_path = feature_dir / ANALYSIS_REPORT_FILENAME
    assert emitted["path"] == str(report_path)
    frontmatter, body = FrontmatterManager().read(report_path)
    assert frontmatter["analyzer_agent"] == "codex"
    assert frontmatter["input_artifacts"]["tasks.md"]["sha256"]
    assert "# Analysis" in body


def test_write_analysis_report_raises_on_unrelativizable_path(tmp_path):
    """NFR-002 / spec.md Acceptance Scenario 3: when a hash-input artifact path
    cannot be relativized against ``repo_root`` (e.g. it lies outside it
    entirely), ``write_analysis_report`` must raise/surface an explicit error
    rather than silently writing an absolute path."""
    from specify_cli.analysis_report import AnalysisReportError, write_analysis_report

    feature_dir = tmp_path / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    # repo_root deliberately does NOT contain feature_dir, so spec.md/plan.md/
    # tasks.md cannot be relativized against it.
    unrelated_repo_root = tmp_path / "unrelated-repo-root"
    unrelated_repo_root.mkdir()

    with pytest.raises(AnalysisReportError) as exc_info:
        write_analysis_report(
            feature_dir=feature_dir,
            repo_root=unrelated_repo_root,
            body="# Report\n\nPASS\n",
        )

    # pr-fresh-001: the raised message must stay diagnosable WITHOUT embedding
    # either absolute path -- this mission exists to stop local paths
    # (/home/<user>/...) leaking out of spec-kitty, and this fail-loud path is
    # an operator-visible surface (CLI error output, CI logs on a public repo)
    # just like the committed artifact channel WP01 already closed. Assert
    # both halves: no absolute-path leak, and the message still names the
    # failing artifact so it stays debuggable.
    message = str(exc_info.value)
    assert str(feature_dir) not in message
    assert str(unrelated_repo_root) not in message
    assert str(tmp_path) not in message
    assert "spec.md" in message

    rendered_traceback = "".join(
        traceback.format_exception(
            exc_info.type,
            exc_info.value,
            exc_info.value.__traceback__,
        )
    )
    assert str(feature_dir) not in rendered_traceback
    assert str(unrelated_repo_root) not in rendered_traceback
    assert str(tmp_path) not in rendered_traceback


def test_write_analysis_report_rejects_symlink_escape(tmp_path):
    """FR-007/NFR-002: resolved inputs outside the governing root fail closed."""
    from specify_cli.analysis_report import AnalysisReportError, write_analysis_report

    repo_root = tmp_path / "repo"
    linked_feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    external_feature_dir = tmp_path / "external" / "sample-01KS"
    _write_required_artifacts(external_feature_dir)
    linked_feature_dir.parent.mkdir(parents=True)
    try:
        linked_feature_dir.symlink_to(external_feature_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(AnalysisReportError, match="spec.md"):
        write_analysis_report(
            feature_dir=linked_feature_dir,
            repo_root=repo_root,
            body="# Report\n\nPASS\n",
        )


def test_write_analysis_report_preserves_in_repo_symlink_identity(tmp_path):
    """Resolved containment checks do not rewrite a valid logical artifact path."""
    repo_root = tmp_path / "repo"
    linked_feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    real_feature_dir = repo_root / "stored-missions" / "sample-01KS"
    _write_required_artifacts(real_feature_dir)
    linked_feature_dir.parent.mkdir(parents=True)
    try:
        linked_feature_dir.symlink_to(real_feature_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    result = write_analysis_report(
        feature_dir=linked_feature_dir,
        repo_root=repo_root,
        body="# Report\n\nPASS\n",
    )

    assert result.input_artifacts["spec.md"]["path"] == "kitty-specs/sample-01KS/spec.md"


def test_check_analysis_report_current_reports_relativization_failure_without_raising(tmp_path):
    """NFR-002: unlike ``write_analysis_report``, ``check_analysis_report_current``
    must NEVER raise -- the same unrelativizable-path condition must be caught
    and surfaced as a typed ``AnalysisFreshness(ok=False, ...)`` result instead
    of propagating into its caller (``_require_current_analysis_report``)."""
    from specify_cli.analysis_report import check_analysis_report_current, write_analysis_report

    feature_dir = tmp_path / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    # First write a legitimate report with a repo_root that DOES relativize,
    # so a real, valid `analysis-report.md` exists on disk to check freshness of.
    write_analysis_report(feature_dir=feature_dir, repo_root=tmp_path, body="# Report\n\nPASS\n")

    # Now check freshness with a repo_root that does NOT contain feature_dir --
    # the same unrelativizable-path condition as the write-side test above.
    unrelated_repo_root = tmp_path / "unrelated-repo-root"
    unrelated_repo_root.mkdir()

    freshness = check_analysis_report_current(feature_dir, unrelated_repo_root)

    assert freshness.ok is False
    assert freshness.stale is True
    assert freshness.missing is False
    assert freshness.reason.startswith("path_relativization_failed:")
    assert str(tmp_path) not in freshness.reason


def test_check_analysis_report_current_reports_symlink_escape_without_raising(tmp_path):
    """NFR-002: freshness maps a resolved-path escape to a typed failure."""
    from specify_cli.analysis_report import check_analysis_report_current, write_analysis_report

    repo_root = tmp_path / "repo"
    linked_feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    external_feature_dir = tmp_path / "external" / "sample-01KS"
    _write_required_artifacts(external_feature_dir)
    write_analysis_report(
        feature_dir=external_feature_dir,
        repo_root=tmp_path,
        body="# Report\n\nPASS\n",
    )
    linked_feature_dir.parent.mkdir(parents=True)
    try:
        linked_feature_dir.symlink_to(external_feature_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    freshness = check_analysis_report_current(linked_feature_dir, repo_root)

    assert freshness.ok is False
    assert freshness.stale is True
    assert freshness.missing is False
    assert freshness.reason.startswith("path_relativization_failed:")
    assert str(tmp_path) not in freshness.reason


def test_record_analysis_refuses_dirty_worktree_before_write(tmp_path, monkeypatch):
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    _init_committed_git_project(repo_root, branch="feature")
    # #7556: the gate refuses only on THIS Mission's own uncommitted paths; a
    # root-level scratch file is now a warning (pinned in
    # tests/specify_cli/cli/commands/agent/test_record_analysis_mission_scoped_7556.py).
    # The dirt here is therefore an uncommitted edit inside the Mission directory.
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001. Edited, not committed.\n", encoding="utf-8")
    input_file = tmp_path.parent / f"{tmp_path.name}-analysis.md"
    input_file.write_text("# Analysis\n\nPASS\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis.locate_project_root", lambda: repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis.get_main_repo_root", lambda path: path)
    emitted: dict[str, object] = {}
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis._emit_json", lambda payload: emitted.update(payload))

    result = CliRunner().invoke(
        mission_app,
        ["record-analysis", "--mission", feature_dir.name, "--input-file", str(input_file), "--json"],
    )

    assert result.exit_code == 1
    assert emitted["error_code"] == "DIRTY_WORKTREE"
    assert not (feature_dir / ANALYSIS_REPORT_FILENAME).exists()


def test_record_analysis_succeeds_on_protected_branch_via_materialize(tmp_path, monkeypatch):
    """record-analysis no longer REFUSES on a protected primary (01KVMBD6 / WP02).

    The protected-branch hard-refusal was removed: the report is written to the
    primary checkout (a plain file write, not a git op) and the commit is routed
    best-effort through ``commit_for_mission`` (materialize-then-retry). So on a
    protected ``main`` the command now SUCCEEDS (exit 0, report written) rather
    than failing with ``PROTECTED_BRANCH_REFUSED``. (Was
    ``test_record_analysis_refuses_protected_branch_before_write`` — renamed; the
    old refuse contract is superseded by the materialize-then-retry contract that
    ``test_accept_protected_branch_materialize_then_retry`` pins for accept.)
    """
    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)
    _init_committed_git_project(repo_root, branch="main")
    input_file = tmp_path.parent / f"{tmp_path.name}-analysis.md"
    input_file.write_text("# Analysis\n\nPASS\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis.locate_project_root", lambda: repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis.get_main_repo_root", lambda path: path)
    emitted: dict[str, object] = {}
    monkeypatch.setattr("specify_cli.cli.commands.agent.mission_record_analysis._emit_json", lambda payload: emitted.update(payload))

    result = CliRunner().invoke(
        mission_app,
        ["record-analysis", "--mission", feature_dir.name, "--input-file", str(input_file), "--json"],
    )

    assert result.exit_code == 0, result.output
    assert emitted["success"] is True
    assert (feature_dir / ANALYSIS_REPORT_FILENAME).exists()


# --- analysis-findings/v1 structured carrier (FR-004 / #1819) ----------------


def _carrier(findings_yaml: str, counts_yaml: str, *, hint: str | None = None) -> str:
    hint_line = f"verdict_hint: {hint}\n" if hint else ""
    return (
        "---\n"
        "schema: analysis-findings/v1\n"
        f"findings:\n{findings_yaml}"
        f"counts: {counts_yaml}\n"
        f"{hint_line}"
        "---\n\n"
    )


def test_find1_verdict_ignores_scary_prose_when_no_blocking_findings(tmp_path):
    """C-FIND-1: clean frontmatter + scary prose ("CRITICAL"/"HIGH"/"BLOCK") → ready."""
    from specify_cli.analysis_report import VERDICT_READY

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    body = _carrier(
        "  - {id: A1, severity: low, category: style, summary: nit}\n"
        "  - {id: A2, severity: medium, category: coverage, summary: gap}\n",
        "{critical: 0, high: 0, medium: 1, low: 1, info: 0}",
    ) + "We found CRITICAL HIGH issues that BLOCK everything (prose only).\n"

    result = write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert result.verdict == VERDICT_READY
    frontmatter, _ = FrontmatterManager().read(result.path)
    assert frontmatter["verdict"] == "ready"
    assert frontmatter["issue_counts"]["medium"] == 1


def test_find1_verdict_blocked_despite_reassuring_prose(tmp_path):
    """C-FIND-1: one critical finding + "ready for implementation" prose → blocked."""
    from specify_cli.analysis_report import VERDICT_BLOCKED

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    body = _carrier(
        "  - {id: C1, severity: critical, category: charter, summary: violation}\n",
        "{critical: 1, high: 0, medium: 0, low: 0, info: 0}",
    ) + "No issues at all. PASS. READY FOR IMPLEMENTATION.\n"

    result = write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert result.verdict == VERDICT_BLOCKED
    frontmatter, _ = FrontmatterManager().read(result.path)
    assert frontmatter["verdict"] == "blocked"


def test_find2_unknown_severity_fails_loudly_on_write(tmp_path):
    """C-FIND-2: unknown severity value → structured validation error on write."""
    from specify_cli.analysis_report import FindingsCarrierError

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    body = _carrier(
        "  - {id: X1, severity: catastrophic, category: x, summary: y}\n",
        "{critical: 0, high: 0, medium: 0, low: 0, info: 0}",
    )
    with pytest.raises(FindingsCarrierError, match="severity"):
        write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert not (feature_dir / ANALYSIS_REPORT_FILENAME).exists()


def test_find2_counts_mismatch_fails_loudly_on_write(tmp_path):
    """C-FIND-2: counts not equal to findings[] tally → loud error."""
    from specify_cli.analysis_report import FindingsCarrierError

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    body = _carrier(
        "  - {id: H1, severity: high, category: x, summary: y}\n",
        "{critical: 0, high: 0, medium: 0, low: 0, info: 0}",  # claims 0 high, but 1 present
    )
    with pytest.raises(FindingsCarrierError, match="tally"):
        write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert not (feature_dir / ANALYSIS_REPORT_FILENAME).exists()


def test_find2_verdict_hint_disagreement_fails_loudly(tmp_path):
    """C-FIND-2: verdict_hint disagreeing with computed verdict → loud error."""
    from specify_cli.analysis_report import FindingsCarrierError

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    body = _carrier(
        "  - {id: H1, severity: high, category: x, summary: y}\n",
        "{critical: 0, high: 1, medium: 0, low: 0, info: 0}",
        hint="ready",  # computed verdict is blocked
    )
    with pytest.raises(FindingsCarrierError, match="verdict_hint"):
        write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert not (feature_dir / ANALYSIS_REPORT_FILENAME).exists()


def test_find3_legacy_report_records_unknown_without_exception(tmp_path):
    """C-FIND-3: a pre-v1 report (no carrier) records verdict unknown, never raises."""
    from specify_cli.analysis_report import VERDICT_UNKNOWN

    repo_root = tmp_path
    feature_dir = repo_root / "kitty-specs" / "sample-01KS"
    _write_required_artifacts(feature_dir)

    # No carrier; prose says scary things — must NOT be substring-inferred.
    body = "# Report\n\nCRITICAL issues, BLOCK, no go.\n"
    result = write_analysis_report(feature_dir=feature_dir, repo_root=repo_root, body=body)
    assert result.verdict == VERDICT_UNKNOWN
    assert all(v is None for v in result.issue_counts.values())
    # Read/freshness path tolerates the legacy report (no exception, stays current).
    assert check_analysis_report_current(feature_dir, repo_root).ok is True


def test_no_substring_inference_symbols_remain():
    """T025: the prose substring inference is deleted — no magic strings remain."""
    import specify_cli.analysis_report as module

    assert not hasattr(module, "infer_verdict")
    assert not hasattr(module, "infer_issue_counts")
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "READY FOR IMPLEMENTATION" not in source


def test_implement_gate_detects_carrier_format_file(tmp_path):
    """check_analysis_report_current returns carrier_format_not_wrapped for v1 carrier files."""
    from specify_cli.analysis_report import (
        ANALYSIS_REPORT_FILENAME,
        ANALYSIS_REPORT_REASON_CARRIER_FORMAT,
        check_analysis_report_current,
    )

    feature_dir = tmp_path / "kitty-specs" / "my-mission"
    feature_dir.mkdir(parents=True)

    # Write a carrier-format file (analysis-findings/v1 schema, not outer-wrapper)
    carrier_content = (
        "---\n"
        "schema: analysis-findings/v1\n"
        "findings: []\n"
        "counts:\n"
        "  critical: 0\n"
        "  high: 0\n"
        "  medium: 0\n"
        "  low: 0\n"
        "verdict_hint: ready\n"
        "---\n\n"
        "Report body.\n"
    )
    (feature_dir / ANALYSIS_REPORT_FILENAME).write_text(carrier_content, encoding="utf-8")

    result = check_analysis_report_current(feature_dir, tmp_path)

    assert result.ok is False
    assert result.stale is True
    assert result.missing is False
    assert result.reason == ANALYSIS_REPORT_REASON_CARRIER_FORMAT


def test_implement_gate_returns_generic_reason_for_arbitrary_frontmatter(tmp_path):
    """Arbitrary frontmatter (no schema, no artifact_type) falls through to the generic reason."""
    from specify_cli.analysis_report import check_analysis_report_current

    feature_dir = tmp_path / "kitty-specs" / "my-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "analysis-report.md").write_text(
        "---\ntitle: Some Random File\nauthor: Alice\n---\n\nBody.\n",
        encoding="utf-8",
    )

    result = check_analysis_report_current(feature_dir, tmp_path)

    assert result.reason == "invalid_analysis_report_artifact_type"
