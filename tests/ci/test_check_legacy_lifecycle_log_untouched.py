"""Tests for the per-PR guard ``scripts/ci/check_legacy_lifecycle_log_untouched.py``.

Since #7006 ``main`` never writes ``kitty-ops/lifecycle.jsonl``; a pull request whose net
diff modifies it is refused, with the per-record remedy. Skipped on every non-PR event.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ci import check_legacy_lifecycle_log_untouched as guard

pytestmark = pytest.mark.fast

LEGACY = "kitty-ops/lifecycle.jsonl"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)


@pytest.fixture()
def pr_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    (root / "kitty-ops" / "lifecycle").mkdir(parents=True)
    (root / LEGACY).write_text('{"id": "old"}\n', encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    monkeypatch.setattr(guard, "REPO_ROOT", root)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    return root


def _commit(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "pr")


def test_main_refuses_a_pr_that_appends_to_the_legacy_log(pr_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with (pr_repo / LEGACY).open("a", encoding="utf-8") as log:
        log.write('{"id": "new"}\n')
    _commit(pr_repo)
    assert guard.main() == 1
    err = capsys.readouterr().err
    assert LEGACY in err
    assert "kitty-ops/lifecycle/<ulid>.json" in err
    assert "append_lifecycle_record" in err


def test_main_passes_a_pr_that_adds_only_per_record_files(pr_repo: Path) -> None:
    (pr_repo / "kitty-ops" / "lifecycle" / "01KTEST.json").write_text('{"id": "new"}\n', encoding="utf-8")
    _commit(pr_repo)
    assert guard.main() == 0


def test_main_skips_a_push(pr_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (pr_repo / LEGACY).write_text("changed\n", encoding="utf-8")
    _commit(pr_repo)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    assert guard.main() == 0
