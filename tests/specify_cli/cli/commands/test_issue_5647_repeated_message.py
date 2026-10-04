"""#5647: repeated ``-m`` builds a multi-paragraph message, as ``git commit`` does.

Before the fix ``-m`` was a scalar option, so ``-m subject -m trailer`` kept
only the trailer and exited 0.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.cli.commands._commit_message import join_message_paragraphs

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

_BRANCH = "kitty/mission-test-01ABCDEF"
_TRAILER = "Co-Authored-By: Name <name@example.invalid>"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", f"--initial-branch={_BRANCH}")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".kittify/config.json")
    _git(repo, "commit", "-q", "-m", "initial commit")


def test_safe_commit_keeps_every_repeated_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    (tmp_path / "x.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli_app,
        ["safe-commit", "x.py", "-m", "test(x): subject", "-m", "Body paragraph.", "-m", _TRAILER, "--to-branch", _BRANCH],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    message = _git(tmp_path, "log", "-1", "--format=%B").strip()
    assert message == f"test(x): subject\n\nBody paragraph.\n\n{_TRAILER}"


def test_safe_commit_single_message_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    (tmp_path / "x.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli_app, ["safe-commit", "x.py", "-m", "one line", "--to-branch", _BRANCH], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert _git(tmp_path, "log", "-1", "--format=%B").strip() == "one line"


def test_safe_commit_refuses_an_empty_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_repo(tmp_path)
    (tmp_path / "x.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    head = _git(tmp_path, "rev-parse", "HEAD")

    result = runner.invoke(cli_app, ["safe-commit", "x.py", "-m", "  ", "--to-branch", _BRANCH], catch_exceptions=False)

    assert result.exit_code == 1
    assert "Commit message is empty" in result.output
    assert _git(tmp_path, "rev-parse", "HEAD") == head


def test_spec_commit_passes_the_joined_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.cli.commands import spec_commit_cmd

    seen: list[str] = []

    def _fake_commit(repo_root, mission_slug, abs_files, message, target_branch, owned):  # type: ignore[no-untyped-def]
        seen.append(message)
        raise ValueError("stop after capture")

    monkeypatch.setattr(spec_commit_cmd, "_current_repo_root", lambda: tmp_path)
    monkeypatch.setattr(spec_commit_cmd, "resolve_owned_or_refuse", lambda *a, **k: None)
    monkeypatch.setattr(spec_commit_cmd, "_resolve_commit_inputs", lambda *a, **k: ("m-slug", [tmp_path / "spec.md"]))
    monkeypatch.setattr(spec_commit_cmd, "_commit_spec_files", _fake_commit)

    runner.invoke(cli_app, ["spec-commit", "spec.md", "-m", "docs: subject", "-m", _TRAILER, "--mission", "m-slug"])

    assert seen == [f"docs: subject\n\n{_TRAILER}"]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["a"], "a"),
        (["a", "b"], "a\n\nb"),
        (["a", "", "  ", "b\n"], "a\n\nb"),
    ],
)
def test_join_message_paragraphs(values: list[str], expected: str) -> None:
    assert join_message_paragraphs(values) == expected


def test_join_message_paragraphs_rejects_all_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        join_message_paragraphs(["", " "])
