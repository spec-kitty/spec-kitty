"""Option-injection guard on ``implement_support._rev_parse`` (Sonar S6350, #79).

``_rev_parse`` passes a caller-supplied revision as a positional ``git
rev-parse`` argument. The ``--verify --end-of-options`` guard keeps that value
positional, so a ref beginning with ``-`` can never be parsed as a git option.
These tests pin the observable behaviour, not the argv shape:

* a real branch still resolves to one clean SHA (the plain ``--end-of-options``
  form, by contrast, echoes the flag itself as a first output line); and
* a value that is actually a ``git rev-parse`` option is refused rather than
  executed. Unguarded, ``git rev-parse --local-env-vars`` runs that option and
  prints the process's git env-var names at exit 0 — a real option injection —
  whereas the guard makes it an unresolvable revision, so ``_rev_parse`` reports
  ``"unknown"``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.implement_support import _rev_parse

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(r)], check=True, capture_output=True)
    _git(r, "config", "user.email", "test@test.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    _git(r, "commit", "-q", "--allow-empty", "-m", "init")
    return r


def test_rev_parse_resolves_a_branch_to_a_single_clean_sha(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    resolved = _rev_parse(repo, "main")
    assert resolved == head
    # Guards the naive `--end-of-options` (no `--verify`) regression, which
    # prepends a literal "--end-of-options" line to rev-parse's output.
    assert "\n" not in resolved
    assert resolved != "unknown"


def test_rev_parse_refuses_a_git_option_supplied_as_a_ref(repo: Path) -> None:
    # `--local-env-vars` is a real `git rev-parse` option. Without the guard it
    # executes and leaks env-var names at exit 0; with it, the value is a bad
    # revision and _rev_parse returns the sentinel instead.
    assert _rev_parse(repo, "--local-env-vars") == "unknown"
