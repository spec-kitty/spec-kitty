"""Unit tests for merge-time hollow review warnings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.consolidate import (
    _collect_hollow_review_warnings,
    _warn_or_confirm_hollow_reviews,
)
from specify_cli.status.lifecycle_events import emit_reviewer_self_approval

pytestmark = pytest.mark.fast


def test_collect_hollow_review_warnings_reads_force_count_and_self_approval(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 3}, "WP02": {"force_count": 0}}}),
        encoding="utf-8",
    )
    emit_reviewer_self_approval(
        feature_dir,
        mission_slug="034-test",
        wp_id="WP02",
        implementing_actor="codex",
        intended_reviewer="claude",
        failure_reason="exit 1",
    )

    warnings = _collect_hollow_review_warnings(feature_dir, ["WP01", "WP02", "WP03"])

    assert warnings["WP01"] == ["force_count=3"]
    assert warnings["WP02"] == ["ReviewerSelfApproval (claude failed: exit 1; codex self-reviewed)"]
    assert "WP03" not in warnings


def test_warn_or_confirm_hollow_reviews_assume_yes_does_not_prompt(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--yes`` skips the confirm prompt even at an interactive terminal.

    The terminal is forced interactive and the prompt would decline, so the
    merge proceeds only because ``assume_yes`` short-circuits the prompt (under
    pytest's non-TTY stdin the non-interactive arm alone would proceed).
    """
    monkeypatch.setenv("SPEC_KITTY_FORCE_INTERACTIVE", "1")
    prompts: list[str] = []

    def _declining_confirm(text: str, **_kwargs: object) -> bool:
        prompts.append(text)
        return False

    monkeypatch.setattr(typer, "confirm", _declining_confirm)
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 2}}}),
        encoding="utf-8",
    )

    _warn_or_confirm_hollow_reviews(feature_dir=feature_dir, wp_ids=["WP01"], assume_yes=True)

    out = capsys.readouterr().out
    assert "Hollow reviews detected" in out
    assert "Proceeding without interactive confirmation" in out
    assert prompts == []


def test_warn_or_confirm_hollow_reviews_non_interactive_env_does_not_prompt(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2912: with SPEC_KITTY_NON_INTERACTIVE set the hollow-review gate
    auto-proceeds without a confirm prompt even without --yes. Before routing
    through is_interactive(), the bare ``sys.stdin.isatty()`` check would prompt
    (and could hang an agent) whenever stdin merely looked like a TTY."""
    monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
    feature_dir = tmp_path / "kitty-specs" / "034-test"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.json").write_text(
        json.dumps({"work_packages": {"WP01": {"force_count": 2}}}),
        encoding="utf-8",
    )

    _warn_or_confirm_hollow_reviews(feature_dir=feature_dir, wp_ids=["WP01"], assume_yes=False)

    out = capsys.readouterr().out
    assert "Hollow reviews detected" in out
    assert "Proceeding without interactive confirmation" in out
