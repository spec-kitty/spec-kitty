"""Red-first regression: top-level ``spec-kitty plan`` forwards ``--owned-checkout``.

Issue #5882 (slice B). The agent-facing ``agent mission setup-plan`` gained an
owned selector in PR #6002, but the top-level ``spec-kitty plan`` wrapper
(``lifecycle.plan``) is a thin delegate to that same ``setup_plan`` seam and
never exposed/forwarded ``--owned-checkout`` — so the literal
"``spec-kitty plan --help`` exposes no owned selector" complaint stood. These
tests pin the forwarding contract through the real ``plan`` entry point.

RED on base: ``--owned-checkout`` is ``No such option`` on the top-level ``plan``.
"""

from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import lifecycle as lifecycle_mod


def _plan_app() -> typer.Typer:
    app = typer.Typer()
    app.command(name="plan")(lifecycle_mod.plan)
    return app


def test_plan_help_lists_owned_checkout() -> None:
    """``spec-kitty plan --help`` advertises the owned selector (FR-004, SC-003)."""
    result = CliRunner().invoke(_plan_app(), ["--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "--owned-checkout" in result.output


def test_plan_forwards_owned_checkout_to_setup_plan(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """The top-level ``plan`` wrapper forwards the owned fact to the ``setup_plan`` seam (FR-004)."""
    captured: dict[str, object] = {}

    def _fake_setup_plan(*, feature: str, json_output: bool, owned_checkout=None, **_kw):  # type: ignore[no-untyped-def]
        captured["feature"] = feature
        captured["owned_checkout"] = owned_checkout

    monkeypatch.setattr(lifecycle_mod, "_enforce_initialized", lambda **_k: None)
    monkeypatch.setattr(lifecycle_mod.agent_feature, "setup_plan", _fake_setup_plan)

    owned_path = str(tmp_path / "owned-producer")
    result = CliRunner().invoke(
        _plan_app(),
        ["--mission", "demo-01ABCDEF", "--owned-checkout", owned_path, "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert captured["feature"] == "demo-01ABCDEF"
    assert str(captured["owned_checkout"]) == owned_path


def test_plan_with_owned_checkout_does_not_run_repository_root_interview(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Interactive ``plan --owned-checkout P`` never opens Decision Moments in the repository root checkout.

    The widen interview resolves its repository from the repository root checkout and
    has no owned seam, so running it would write ``decisions/index.json`` into R's copy
    of the Mission while ``plan.md`` went to P.
    """
    interview_calls: list[dict[str, object]] = []

    monkeypatch.setattr(lifecycle_mod, "_enforce_initialized", lambda **_k: None)
    monkeypatch.setattr(lifecycle_mod.agent_feature, "setup_plan", lambda **_k: None)
    monkeypatch.setattr(lifecycle_mod, "locate_project_root", lambda *a, **k: tmp_path)

    import specify_cli.cli.commands.agent.context as context_mod
    import specify_cli.missions.plan.plan_interview as interview_mod

    monkeypatch.setattr(context_mod, "_find_feature_directory", lambda *a, **k: tmp_path / "kitty-specs" / "demo-01ABCDEF")
    monkeypatch.setattr(interview_mod, "run_plan_interview", lambda **kw: interview_calls.append(kw) or {})

    result = CliRunner().invoke(
        _plan_app(),
        ["--mission", "demo-01ABCDEF", "--owned-checkout", str(tmp_path / "owned-producer")],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert interview_calls == []
