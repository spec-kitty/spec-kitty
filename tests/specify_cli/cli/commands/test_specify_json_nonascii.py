"""Regression net for #4720 (mission cli-error-surface-seam-01M2WJD2, WP06):
``spec-kitty specify <name>`` must reject a non-ASCII (or empty/whitespace)
name EXPLICITLY -- never silently truncate/slugify it -- and route the
rejection through the WP01 global error hook so ``--json`` gets a single
parseable JSON error object on stdout at exit 1, consistent with every other
``specify --json`` error path.

Before this fix, ``_slugify_feature_input`` (``lifecycle.py``) produced three
different wrong shapes depending on the input's script:

1. ``日本語`` (all non-Latin) -- the slugify regex strips every character,
   leaving an empty slug, which raised ``typer.BadParameter``. Typer
   intercepts ``BadParameter`` BEFORE the global hook, forcing a Rich usage
   panel on stderr, exit 2, and EMPTY stdout under ``--json``.
2. ``Ünïcödé`` (accented Latin) -- the regex silently stripped the
   diacritics and ACCEPTED the mangled result (``n-c-d``) with no error.
3. ``auth日本`` (mixed ASCII + non-Latin) -- silently accepted and truncated
   to ``auth``, dropping the non-ASCII suffix without any indication.

Decision 01M2WJE53KMFBGEJX8JMFT71EE: all three must now reject explicitly,
named in the error, via a single ``NonAsciiNameError`` (a ``GuardedReadError``
subclass) the WP01 hook renders -- never a Typer usage error (exit 2) for
this validation.

These tests drive the REAL ``spec-kitty specify`` command through
``specify_cli._run_app_with_error_hook`` (mirrors
``tests/specify_cli/test_error_hook.py`` and
``tests/specify_cli/cli/commands/test_mission_close_guard.py``'s pattern) --
not bare ``typer.testing.CliRunner``, which calls the Click app object
directly and never passes through the hook (that wrapping happens one layer
up, in ``specify_cli.main()``).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli import _argv_requests_json_mode, _run_app_with_error_hook, app

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

_NO_NAME_GIVEN = "no name given"

# The three named scenarios from #4720 -- exact code points, do not substitute
# equivalent-but-different ones (spec pins these for reproducibility and for
# the NFR-005 accented-Latin + non-Latin-script regression matrix).
_ALL_NON_LATIN = "日本語"
_ACCENTED_LATIN = "Ünïcödé"
_MIXED_ASCII_NON_LATIN = "auth日本"
_REJECTED_NAMES = (_ALL_NON_LATIN, _ACCENTED_LATIN, _MIXED_ASCII_NON_LATIN)


# ---------------------------------------------------------------------------
# Project fixture -- a real, minimal git repo (needed because ``specify``
# routes through ``assert_initialized`` -> ``resolve_canonical_root``, which
# requires an actual ``.git`` ancestor, not merely a ``.kittify`` marker).
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], repo)


def _init_project(tmp_path: Path) -> Path:
    """Initialize a real Spec Kitty project: a git repo on ``main`` with the
    ``.kittify/config.yaml`` marker ``specify`` requires (``require_specs``
    is ``False`` for ``specify``, so ``kitty-specs/`` is created lazily --
    but we still create it up front so the NFR-005 no-write assertions have
    a concrete, empty directory to assert stays empty)."""
    repo = tmp_path / "project"
    repo.mkdir(parents=True)
    _run(["git", "init", "-qb", "main", str(repo)], repo)
    _git(repo, "config", "user.email", "wp06-fixture@spec-kitty.test")
    _git(repo, "config", "user.name", "WP06 Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    kittify = repo / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "project_slug: nonascii-fixture\nprotection:\n  protected_branches: []\nmission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    (repo / "kitty-specs").mkdir()
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "chore: bootstrap spec-kitty project")
    return repo


def _mission_dirs(repo: Path) -> list[Path]:
    specs = repo / "kitty-specs"
    if not specs.is_dir():
        return []
    return sorted(p for p in specs.iterdir() if p.is_dir())


def _branch_list(repo: Path) -> list[str]:
    result = _git(repo, "branch", "--list", "--format=%(refname:short)")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _meta_json_files(repo: Path) -> list[Path]:
    specs = repo / "kitty-specs"
    if not specs.is_dir():
        return []
    return sorted(specs.rglob("meta.json"))


def _invoke(monkeypatch: pytest.MonkeyPatch, repo: Path, argv: list[str]) -> int | str | None:
    """Run *argv* through the real app + global hook, cwd inside *repo*."""
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION", "1")
    full_argv = ["spec-kitty", *argv]
    monkeypatch.setattr(sys, "argv", full_argv)
    json_mode = _argv_requests_json_mode(full_argv)
    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=json_mode)
    return exc_info.value.code


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _init_project(tmp_path)


# ---------------------------------------------------------------------------
# --json contract: exactly one JSON error object on stdout, exit 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", _REJECTED_NAMES, ids=["all-non-latin", "accented-latin", "mixed-ascii-non-latin"])
def test_specify_json_rejects_nonascii_name_with_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo: Path,
    name: str,
) -> None:
    """#4720: each of the 3 named non-ASCII scenarios exits 1 (not 2, not 0)
    with a single parseable JSON error object on stdout naming the value."""
    before_dirs = _mission_dirs(repo)
    before_branches = _branch_list(repo)

    exit_code = _invoke(monkeypatch, repo, ["specify", name, "--json"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one line of JSON on stdout, got: {captured.out!r}"
    payload = json.loads(lines[0])
    assert payload["kind"] == "NonAsciiNameError"
    assert payload["path"] == name
    assert name in payload["error"]

    # NFR-005: nothing written for a rejected name.
    assert _mission_dirs(repo) == before_dirs
    assert _branch_list(repo) == before_branches
    assert _meta_json_files(repo) == []


def test_specify_no_json_rejects_nonascii_name_clean_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo: Path,
) -> None:
    """Non-``--json`` path: a clean ``Error: <reason>`` line on stderr, exit
    1, no traceback -- not Typer's exit-2 usage-error panel."""
    exit_code = _invoke(monkeypatch, repo, ["specify", _ACCENTED_LATIN])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert captured.err.strip().startswith("Error:")
    assert _ACCENTED_LATIN in captured.err


# ---------------------------------------------------------------------------
# NFR-005: no mission dir / branch / meta.json for ANY rejected name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", _REJECTED_NAMES, ids=["all-non-latin", "accented-latin", "mixed-ascii-non-latin"])
def test_specify_rejects_nonascii_name_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    name: str,
) -> None:
    """NFR-005 negative assertion, isolated from the JSON-shape test above:
    no mission directory, no git branch, and no ``meta.json`` anywhere under
    ``kitty-specs/`` after a rejected non-ASCII name -- and no trace of the
    rejected name's slug survives on disk."""
    before_dirs = _mission_dirs(repo)
    before_branches = _branch_list(repo)

    _invoke(monkeypatch, repo, ["specify", name, "--json"])

    after_dirs = _mission_dirs(repo)
    assert after_dirs == before_dirs, f"a rejected name must create no mission directory, found: {after_dirs!r}"
    assert _branch_list(repo) == before_branches, "a rejected name must create no git branch"
    assert _meta_json_files(repo) == [], "a rejected name must write no meta.json"


# ---------------------------------------------------------------------------
# Distinct-message assertion: "no name given" != "no usable ASCII characters"
# ---------------------------------------------------------------------------


def test_no_name_given_and_nonascii_messages_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo: Path,
) -> None:
    """The whitespace-only ("no name given") rejection must stay worded
    differently from the non-ASCII ("no usable ASCII characters")
    rejection -- a caller debugging automation needs to tell them apart."""
    _invoke(monkeypatch, repo, ["specify", "   ", "--json"])
    empty_payload = json.loads(capsys.readouterr().out.strip())

    _invoke(monkeypatch, repo, ["specify", _ALL_NON_LATIN, "--json"])
    nonascii_payload = json.loads(capsys.readouterr().out.strip())

    assert empty_payload["error"] != nonascii_payload["error"]
    assert _NO_NAME_GIVEN in empty_payload["error"]
    assert _NO_NAME_GIVEN not in nonascii_payload["error"]
    assert empty_payload["path"] == "   "
    assert nonascii_payload["path"] == _ALL_NON_LATIN


# ---------------------------------------------------------------------------
# Happy-path regression: a valid ASCII name is unaffected by the fix
# ---------------------------------------------------------------------------


def test_specify_ascii_name_still_slugifies_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    repo: Path,
) -> None:
    """Guards against over-rejection: a normal ASCII name still creates a
    mission scaffold exactly as before the fix."""
    exit_code = _invoke(monkeypatch, repo, ["specify", "Auth Refactor", "--json"])

    assert exit_code == 0, capsys.readouterr().out
    dirs = _mission_dirs(repo)
    assert len(dirs) == 1
    assert dirs[0].name.startswith("auth-refactor")
