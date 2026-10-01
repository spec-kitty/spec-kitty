"""Direct unit tests for the record-analysis seam (#2056 WP04, Seam A).

Exercises the relocated helpers in
``specify_cli.cli.commands.agent.mission_record_analysis`` directly: the
dirty-tree write preflight (clean / dirty / coord-residue-drop branches), the
placement-ref resolver's conservative None-on-failure contract, and the
``_git_dirty_paths`` git helper. The end-to-end command behavior remains pinned
by the existing ``test_record_analysis_coord_worktree.py`` and the WP01 golden
harness; these add the missing focused branch coverage.
"""

from __future__ import annotations

from pathlib import Path
import re
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import ActionContextError, CommitTarget, MissionTopology
from specify_cli.cli.commands.agent import mission_record_analysis as seam
from specify_cli.cli.commands.agent.mission import app as mission_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# _git_dirty_paths
# ---------------------------------------------------------------------------


def test_git_dirty_paths_empty_outside_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: False)
    assert seam._git_dirty_paths(tmp_path) == []


def test_git_dirty_paths_parses_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Real git (the probe now asks ``kernel.git`` for NUL-delimited entries, so a
    # mocked ``subprocess.run`` no longer reaches it).
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@e.c", "-c", "user.name=T", "commit", "-qm", "i"], cwd=tmp_path, check=True)
    (tmp_path / "src" / "a.py").write_text("y\n", encoding="utf-8")
    (tmp_path / "new.txt").write_text("n\n", encoding="utf-8")
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    assert seam._git_dirty_paths(tmp_path) == ["src/a.py", "new.txt"]


def test_git_dirty_paths_raises_on_git_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    # ``tmp_path`` is not a repository, so the real git probe fails.
    with pytest.raises(RuntimeError, match="not a git repository"):
        seam._git_dirty_paths(tmp_path)


# ---------------------------------------------------------------------------
# _resolve_record_analysis_placement_ref (conservative None on failure)
# ---------------------------------------------------------------------------


def test_placement_ref_none_on_resolution_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A resolution failure degrades to None (conservative; never breaks the lifecycle)."""
    import mission_runtime
    from mission_runtime import ActionContextError

    def _boom(*_a: object, **_k: object) -> object:
        raise ActionContextError("X", "no context")

    # The helper lazily imports placement_seam from mission_runtime and calls
    # write_target(ANALYSIS_REPORT); a raised ActionContextError must degrade to
    # None (unchanged Optional contract).
    monkeypatch.setattr(mission_runtime, "placement_seam", _boom, raising=False)
    assert seam._resolve_record_analysis_placement_ref(tmp_path, tmp_path / "001-demo") is None


# ---------------------------------------------------------------------------
# _enforce_analysis_report_write_preflight
# ---------------------------------------------------------------------------


def test_preflight_noop_outside_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: False)
    # Must return without raising even with a dirty stub (not consulted).
    seam._enforce_analysis_report_write_preflight(tmp_path, json_output=True)


def test_preflight_clean_tree_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(seam, "_git_dirty_paths", lambda _root: [])
    seam._enforce_analysis_report_write_preflight(tmp_path, json_output=True)


def test_preflight_dirty_tree_gates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(seam, "_git_dirty_paths", lambda _root: ["src/dirty.py"])
    with pytest.raises(typer.Exit):
        seam._enforce_analysis_report_write_preflight(tmp_path, json_output=True)


def test_preflight_coord_drops_residue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(seam, "_git_dirty_paths", lambda _root: ["kitty-specs/001-demo/spec.md"])
    monkeypatch.setattr(
        seam, "is_coord_residue_churn", lambda _p, *, mission_slug=None: True
    )
    monkeypatch.setattr(seam, "resolve_topology", lambda _r, _s: MissionTopology.COORD)
    # Residue dropped → empty dirty set → no gate.
    seam._enforce_analysis_report_write_preflight(
        tmp_path,
        json_output=True,
        placement_ref=CommitTarget(ref="kitty/mission-001-demo-AAAA1111"),
        mission_slug="001-demo",
    )


def test_preflight_non_coord_keeps_residue_and_gates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(seam, "_git_dirty_paths", lambda _root: ["kitty-specs/001-demo/spec.md"])
    monkeypatch.setattr(
        seam, "is_coord_residue_churn", lambda _p, *, mission_slug=None: True
    )
    monkeypatch.setattr(seam, "resolve_topology", lambda _r, _s: MissionTopology.SINGLE_BRANCH)
    with pytest.raises(typer.Exit):
        seam._enforce_analysis_report_write_preflight(
            tmp_path,
            json_output=True,
            placement_ref=CommitTarget(ref="main"),
            mission_slug="001-demo",
        )


def test_preflight_no_slug_skips_residue_filter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without a mission_slug the residue filter is skipped → full dirty set gates."""
    monkeypatch.setattr(seam, "is_git_repo", lambda _root: True)
    monkeypatch.setattr(seam, "_git_dirty_paths", lambda _root: ["kitty-specs/001-demo/spec.md"])
    with pytest.raises(typer.Exit):
        seam._enforce_analysis_report_write_preflight(
            tmp_path,
            json_output=True,
            placement_ref=CommitTarget(ref="kitty/mission-001-demo-AAAA1111"),
            mission_slug=None,
        )


# ---------------------------------------------------------------------------
# record_analysis command — error / edge branches via CliRunner
# ---------------------------------------------------------------------------


_RUNNER = CliRunner()


def test_command_project_root_not_found_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seam, "locate_project_root", lambda: None)
    result = _RUNNER.invoke(
        mission_app, ["record-analysis", "--json"], catch_exceptions=False
    )
    assert result.exit_code == 1
    assert seam.PROJECT_ROOT_NOT_FOUND in result.stdout


def test_command_project_root_not_found_human(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seam, "locate_project_root", lambda: None)
    result = _RUNNER.invoke(mission_app, ["record-analysis"], catch_exceptions=False)
    assert result.exit_code == 1
    assert seam.PROJECT_ROOT_NOT_FOUND in result.stdout


def test_command_feature_detection_error_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(seam, "get_main_repo_root", lambda _r: tmp_path)

    def _raise(*_a: object, **_k: object) -> Path:
        raise ActionContextError("FEATURE_CONTEXT_UNRESOLVED", "no mission")

    monkeypatch.setattr(seam, "_find_feature_directory", _raise)
    result = _RUNNER.invoke(
        mission_app, ["record-analysis", "--json", "--mission", "nope"], catch_exceptions=False
    )
    assert result.exit_code == 1
    assert "FEATURE_CONTEXT_UNRESOLVED" in result.stdout


def test_command_empty_body_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    feature_dir = tmp_path / "001-demo"
    feature_dir.mkdir()
    monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(seam, "get_main_repo_root", lambda _r: tmp_path)
    monkeypatch.setattr(seam, "_find_feature_directory", lambda *_a, **_k: feature_dir)
    # WP03 / D11: placement must resolve for the command to reach the empty-body
    # check at all -- a ``None`` placement now fails closed BEFORE this branch
    # (see test_record_analysis_placement.py). This test is about the empty-body
    # validation, so it supplies a resolved placement to reach that branch.
    monkeypatch.setattr(
        seam,
        "_resolve_record_analysis_placement_ref",
        lambda *_a, **_k: CommitTarget(ref="main"),
    )
    monkeypatch.setattr(seam, "_enforce_analysis_report_write_preflight", lambda *_a, **_k: None)
    # Empty stdin → empty body.
    result = _RUNNER.invoke(
        mission_app, ["record-analysis", "--json"], input="   \n", catch_exceptions=False
    )
    assert result.exit_code == 1
    assert "empty" in result.stdout.lower()


def test_command_unexpected_exception_human(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The top-level except handler renders a human error and exits 1."""
    monkeypatch.setattr(seam, "locate_project_root", lambda: tmp_path)

    def _boom(_r: object) -> Path:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(seam, "get_main_repo_root", _boom)
    result = _RUNNER.invoke(mission_app, ["record-analysis"], catch_exceptions=False)
    assert result.exit_code == 1
    assert "kaboom" in result.stdout


# ---------------------------------------------------------------------------
# record_analysis command — commit-subject conventional-commit shape (#3678)
# ---------------------------------------------------------------------------
#
# commitlint.config.cjs's `type-enum`/`type-case`/`type-empty`/`subject-empty`
# rules reject the pre-fix subject `f"Add analysis report for mission {slug}"`
# outright (no recognized `type(scope):` prefix at all). Per spec.md's
# Grounding Correction 4 / ledger SK-64, the fix direction is: give the
# `commit_for_mission(...)` call a REAL conventional-commit subject
# (`docs(<scope>): <subject>`) -- commitlint.config.cjs (C-004) is untouched.
#
# This test captures the REAL `message=` kwarg `commit_for_mission` receives
# (mocked at its canonical import path -- the same
# `specify_cli.coordination.commit_router.commit_for_mission` patch target
# used by `test_record_analysis_coord_worktree.py`'s materialise-then-retry
# test) via a real end-to-end CLI invocation of `record-analysis` -- never a
# second, independently-typed literal -- so it fails if
# `mission_record_analysis.py`'s construction is reverted (non-vacuous).
#
# The regex below is a unit-level, offline proxy for commitlint's four active
# rules (a member of `type-enum`'s allowlist, `type-case: lower-case`,
# `type-empty`/`subject-empty`: never). The authoritative evidence -- the
# real `npx --yes @commitlint/cli@19.8.1 --config commitlint.config.cjs`
# invocation -- was run directly against both the pre-fix and post-fix
# subject strings during this WP (see the WP completion report); it is not
# re-encoded as a pytest function here because it needs real subprocess/
# network access, which the `unit`/`fast` markers on this module (pytest.ini:
# "no subprocess ... no network") explicitly exclude, and this file may not
# gain a second module per WP03's own task scope.

_COMMITLINT_TYPE_ENUM = {
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "lint",
    "perf",
    "plan",
    "refactor",
    "revert",
    "spec",
    "style",
    "test",
}

# Mirrors the `type(scope): subject` shape commitlint's `type-enum`/
# `type-case`/`type-empty`/`subject-empty` rules require -- see
# `commitlint.config.cjs`.
_CONVENTIONAL_COMMIT_RE = re.compile(r"^(?P<type>[a-z]+)\((?P<scope>[^)]+)\):\s+(?P<subject>\S.*)$")


def _make_primary_feature_dir(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")


_CARRIER_READY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


def test_record_analysis_commit_subject_is_conventional_commit_shaped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#3678 / FR-006: the real captured `message=` kwarg must be a
    ``docs(<scope>): <subject>`` conventional-commit subject.

    RED-first: against the pre-fix
    ``f"Add analysis report for mission {slug}"`` construction, the captured
    message has no ``type(scope):`` prefix at all, so
    ``_CONVENTIONAL_COMMIT_RE`` does not match and this test fails -- the
    same failure mode commitlint's ``type-empty``/``subject-empty`` rules
    report (confirmed via a live ``commitlint`` run during this WP). GREEN
    after the fix: the captured message matches, with ``type`` pinned to the
    literal ``docs``.
    """
    from specify_cli.analysis_report import ANALYSIS_REPORT_FILENAME
    from specify_cli.coordination.commit_router import CommitRouterResult

    slug = "sample-01KS"
    repo_root = tmp_path
    primary_feature_dir = repo_root / "kitty-specs" / slug
    _make_primary_feature_dir(primary_feature_dir)

    input_file = tmp_path.parent / f"{tmp_path.name}-analysis-subject.md"
    input_file.write_text(_CARRIER_READY, encoding="utf-8")

    monkeypatch.setattr(seam, "locate_project_root", lambda: repo_root)
    monkeypatch.setattr(seam, "get_main_repo_root", lambda _path: repo_root)
    monkeypatch.setattr(seam, "_find_feature_directory", lambda *_a, **_k: primary_feature_dir)

    emitted: dict[str, object] = {}
    monkeypatch.setattr(seam, "_emit_json", lambda payload: emitted.update(payload))

    captured_calls: list[dict[str, object]] = []

    def _fake_commit_for_mission(**kwargs: object) -> CommitRouterResult:
        captured_calls.append(kwargs)
        return CommitRouterResult(status="committed", placement_ref="main", commit_hash="abc1234")

    with patch(
        "specify_cli.coordination.commit_router.commit_for_mission",
        side_effect=_fake_commit_for_mission,
    ):
        result = _RUNNER.invoke(
            mission_app,
            ["record-analysis", "--mission", slug, "--input-file", str(input_file), "--json"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, emitted
    assert emitted.get("success") is True
    assert (primary_feature_dir / ANALYSIS_REPORT_FILENAME).exists()
    assert len(captured_calls) == 1, "commit_for_mission was not called exactly once"

    message = captured_calls[0]["message"]
    assert isinstance(message, str)

    match = _CONVENTIONAL_COMMIT_RE.match(message)
    assert match is not None, f"not a conventional-commit subject: {message!r}"
    assert match.group("type") == "docs", message
    assert match.group("type") in _COMMITLINT_TYPE_ENUM, message
    assert match.group("subject").strip() != ""
    assert slug in message
