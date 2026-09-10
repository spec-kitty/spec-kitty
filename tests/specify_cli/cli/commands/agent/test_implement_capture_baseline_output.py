"""``implement_capture_baseline`` renders its notices through the CLI console (#4163).

The baseline notices were written with the builtin ``print``, so the Rich
markup (``[dim]…[/dim]``, ``[yellow]…[/yellow]``) reached the terminal
literally. They now go through the canonical console seam like every other
CLI line, which renders the markup instead of echoing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import workflow_executor
from specify_cli.review.baseline import BaselineTestResult


def _baseline(failed: int) -> BaselineTestResult:
    return BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-09-10T00:00:00Z",
        base_branch="main",
        base_commit="abc1234",
        test_runner="pytest",
        total=3,
        passed=3 - max(failed, 0),
        failed=failed,
        skipped=0,
    )


@pytest.mark.parametrize(
    ("failed", "expected"),
    [
        (1, "Baseline: 1 pre-existing test failure(s) captured"),
        (-1, "Warning: baseline test capture failed"),
    ],
)
def test_baseline_notice_is_rendered_not_echoed_as_markup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failed: int, expected: str
) -> None:
    monkeypatch.setattr("specify_cli.review.baseline.capture_baseline", lambda **kwargs: _baseline(failed))
    monkeypatch.setattr("specify_cli.review.scope_source.resolve_scope_source", lambda root: None)

    workflow_executor.implement_capture_baseline(
        workspace_path=tmp_path,
        target_branch="main",
        normalized_wp_id="WP01",
        mission_slug="m-01ABCDEF",
        feature_dir=tmp_path / "kitty-specs" / "m-01ABCDEF",
        wp_slug="WP01-thing",
        main_repo_root=tmp_path,
    )

    out = capsys.readouterr().out
    assert expected in out
    assert "[dim]" not in out
    assert "[yellow]" not in out


def test_commit_refusal_reason_is_shown_verbatim_not_parsed_as_markup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The artifact-not-committed warning carries arbitrary git text; it must be escaped."""
    feature_dir = tmp_path / "kitty-specs" / "m-01ABCDEF"
    artifact = feature_dir / "tasks" / "WP01-thing" / "baseline-tests.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}")

    monkeypatch.setattr("specify_cli.review.baseline.capture_baseline", lambda **kwargs: _baseline(0))
    monkeypatch.setattr("specify_cli.review.scope_source.resolve_scope_source", lambda root: None)
    monkeypatch.setattr(workflow_executor, "_baseline_artifact_needs_commit", lambda root, art: True)
    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow._resolve_workflow_placement", lambda **kwargs: None)

    def _refuse(**kwargs: object) -> None:
        raise RuntimeError("! [rejected] main -> main (protected) [/]")

    monkeypatch.setattr("specify_cli.cli.commands.agent.workflow.safe_commit", _refuse)

    workflow_executor.implement_capture_baseline(
        workspace_path=tmp_path,
        target_branch="main",
        normalized_wp_id="WP01",
        mission_slug="m-01ABCDEF",
        feature_dir=feature_dir,
        wp_slug="WP01-thing",
        main_repo_root=tmp_path,
    )

    out = capsys.readouterr().out
    assert "Warning: baseline artifact was not committed" in out
    # Without escaping, Rich eats ``[rejected]`` and raises on the stray ``[/]``.
    assert "! [rejected] main -> main (protected) [/]" in out
    assert "[yellow]" not in out
