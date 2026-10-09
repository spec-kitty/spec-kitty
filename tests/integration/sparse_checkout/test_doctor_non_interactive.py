"""Integration test: ``doctor sparse-checkout --fix`` in non-interactive mode (FR-023).

The FR-023 contract requires that, in CI or any environment where stdin
is not a TTY, the ``--fix`` action prints a remediation pointer and
exits non-zero **without mutating repo state**. This is the guardrail
that keeps unattended pipelines from silently altering an operator's
repo configuration.

Two scenarios:

1. ``stdin.isatty() == False`` (simulated via monkeypatching
   ``sys.stdin.isatty``). No CI env var set.
2. Real ``isatty`` may be True, but ``CI=true`` is exported. This models
   GitHub Actions / other CI runners that leave stdin attached.

Both must:
- Emit a remediation pointer mentioning the ``--fix`` action.
- Exit with a non-zero status.
- Leave ``git config --get core.sparseCheckout`` returning ``true`` (no mutation).
- Leave the pattern file in place with its original body.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_sparse_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sparse"
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test User"])
    (repo / "README.md").write_text("# Hello\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "-A"])
    _run(["git", "-C", str(repo), "commit", "-m", "seed"])
    (repo / ".kittify").mkdir()

    _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
    pf = repo / ".git" / "info" / "sparse-checkout"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text("README.md\n", encoding="utf-8")
    return repo


def _assert_state_unchanged(repo: Path) -> None:
    cfg = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "core.sparseCheckout"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cfg.returncode == 0
    assert cfg.stdout.strip() == "true", f"sparse config mutated: {cfg.stdout!r}"
    pf = repo / ".git" / "info" / "sparse-checkout"
    assert pf.exists(), "pattern file was removed in non-interactive mode"
    assert pf.read_text(encoding="utf-8") == "README.md\n"


def _force_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override the command's interactivity probe to return True.

    Under :class:`typer.testing.CliRunner`, ``sys.stdin`` is replaced with a
    non-TTY ``StringIO``, so monkeypatching ``sys.stdin.isatty`` on the
    real module-level stdin is a no-op. We instead patch the command's
    own helper, which is the only path the command consults.
    """
    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor._is_interactive_environment",
        lambda: True,
    )


def _force_non_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor._is_interactive_environment",
        lambda: False,
    )


def test_non_interactive_stdin_not_tty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When stdin is not a TTY, --fix prints a pointer and exits non-zero."""
    repo = _seed_sparse_repo(tmp_path)

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root", lambda: repo
    )
    _force_non_interactive(monkeypatch)

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout", "--fix"])
    assert result.exit_code == 1, result.stdout
    assert "spec-kitty doctor sparse-checkout --fix" in result.stdout
    # FR-023 fast-follow: non-interactive output must be a single-line
    # pointer so CI log readers / grep invocations get a deterministic
    # surface. Rich/console may append a trailing newline — splitlines
    # strips it, so the expected count is 1 content line.
    non_empty_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, (
        f"expected single-line pointer, got {len(non_empty_lines)} lines: {result.stdout!r}"
    )
    _assert_state_unchanged(repo)


def test_non_interactive_via_helper_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``_is_interactive_environment`` helper itself respects CI env vars.

    Direct unit-level check — independent of CliRunner — verifying that
    setting ``CI=true`` flips the helper to False even when stdin is a TTY.
    The ``SPEC_KITTY_NON_INTERACTIVE`` / ``SPEC_KITTY_FORCE_INTERACTIVE`` escape
    hatches (#2912) are cleared up front so the baseline does not depend on the
    ambient shell — agent harnesses and cloud sessions export
    ``SPEC_KITTY_NON_INTERACTIVE=1`` (#5872). Hatch precedence itself is pinned in
    ``tests/specify_cli/cli/commands/test_doctor_shared.py``.
    """
    from specify_cli.cli.commands import doctor as doctor_mod

    # Simulate real TTY attached.
    class _FakeStdin:
        def isatty(self) -> bool:  # noqa: D401
            return True

    monkeypatch.setattr(doctor_mod.sys, "stdin", _FakeStdin())
    # The helper routes through ``core.env.is_interactive`` (#2912), so the
    # escape hatches must be cleared alongside the CI vars (#5872).
    monkeypatch.delenv("SPEC_KITTY_FORCE_INTERACTIVE", raising=False)
    monkeypatch.delenv("SPEC_KITTY_NON_INTERACTIVE", raising=False)
    for var in (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "BUILDKITE",
        "JENKINS_URL",
        "CIRCLECI",
    ):
        monkeypatch.delenv(var, raising=False)

    # Baseline: TTY, no CI → interactive.
    assert doctor_mod._is_interactive_environment() is True

    # CI=true flips it.
    monkeypatch.setenv("CI", "true")
    assert doctor_mod._is_interactive_environment() is False

    # Unsetting CI restores.
    monkeypatch.delenv("CI")
    assert doctor_mod._is_interactive_environment() is True

    # GITHUB_ACTIONS=1 also triggers non-interactive.
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    assert doctor_mod._is_interactive_environment() is False

    # Non-TTY always non-interactive regardless of env.
    monkeypatch.delenv("GITHUB_ACTIONS")

    class _FakeStdinNoTty:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(doctor_mod.sys, "stdin", _FakeStdinNoTty())
    assert doctor_mod._is_interactive_environment() is False


def test_interactive_yes_remediates_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Interactive 'y' response runs the full five-step remediation.

    This is the WP04 complement to WP03's API-level primary test: we
    drive ``doctor sparse-checkout --fix`` through the CLI, feed 'y' to
    the prompt, and verify the primary ends up clean.
    """
    repo = _seed_sparse_repo(tmp_path)

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root", lambda: repo
    )
    _force_interactive(monkeypatch)

    # Feed 'y' to the single consent prompt via builtins.input.
    monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "y")

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout", "--fix"])
    assert result.exit_code == 0, f"stdout:\n{result.stdout}"
    assert "remediated" in result.stdout

    # Post-conditions: sparse is gone.
    cfg = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "core.sparseCheckout"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cfg.returncode != 0 or cfg.stdout.strip() in ("", "false")
    assert not (repo / ".git" / "info" / "sparse-checkout").exists()


def test_interactive_no_aborts_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-'y' response aborts with exit 0 and leaves state untouched."""
    repo = _seed_sparse_repo(tmp_path)

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root", lambda: repo
    )
    _force_interactive(monkeypatch)

    # Empty response aborts.
    monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout", "--fix"])
    assert result.exit_code == 0, result.stdout
    assert "Aborted" in result.stdout or "no changes" in result.stdout.lower()
    _assert_state_unchanged(repo)


def test_interactive_dirty_refusal_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dirty working tree produces the 'commit or stash' refusal message."""
    repo = _seed_sparse_repo(tmp_path)
    # Introduce an uncommitted modification to a tracked file.
    (repo / "README.md").write_text("# Hello — edited\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.cli.commands._sparse_checkout_doctor.locate_project_root", lambda: repo
    )
    _force_interactive(monkeypatch)

    monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "y")

    runner = CliRunner()
    result = runner.invoke(doctor_app, ["sparse-checkout", "--fix"])
    assert result.exit_code == 1, result.stdout
    assert "uncommitted" in result.stdout.lower()
    assert "commit" in result.stdout.lower() or "stash" in result.stdout.lower()

    # Operator edit survives the refusal.
    assert (
        (repo / "README.md").read_text(encoding="utf-8")
        == "# Hello — edited\n"
    )
