"""#7044 regression: every charter command reports repo-relative paths POSIX.

``charter generate --json`` (``charter_path``), ``charter interview --json``
(``interview_path``), their two text lines and the missing/malformed-interview error, plus
``_common._display_path()`` (which renders the path for the ``charter status`` family) all
spelled a repository-relative path with ``str(Path.relative_to(...))``. That rendering follows
the host OS, so Windows reported ``.kittify\\charter\\charter.md`` where Linux and macOS reported
``.kittify/charter/charter.md`` -- the same defect #6277 fixed for ``charter synthesize --json``
by introducing ``kernel.charter_pack_paths.repo_relative_posix()``.

``charter synthesize``'s own fresh-seed file lists keep the old spelling: that surface belongs
to #6277 / PR #7045, not to this module.

Windows path rendering is simulated on POSIX by patching ``Path.relative_to`` so results under
``.kittify`` come back as a :class:`PureWindowsPath` (``str()`` renders ``\\``, ``as_posix()``
still renders ``/``). Faking ``os.name`` is not an option -- see
``tests/kernel/test_is_windows_seam.py``: it flips ``pathlib`` to ``WindowsPath`` mid-run and
crashes pytest. The control test proves a bare ``str(relative_to(...))`` under the simulation
really produces a backslash, so this module cannot pass vacuously.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter._common import _display_path

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

runner = CliRunner()

INTERVIEW_REL = ".kittify/charter/interview/answers.yaml"
CHARTER_REL = ".kittify/charter/charter.md"


# ---------------------------------------------------------------------------
# Windows path-rendering simulation
# ---------------------------------------------------------------------------


def install_windows_path_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``Path.relative_to`` render Windows-style path strings for charter state.

    Only results under ``.kittify`` are re-flavoured: that is the surface this issue is about,
    and restricting it keeps every other caller -- which may use the result as an access path --
    on real :class:`Path` objects.
    """
    real_relative_to = Path.relative_to

    def windows_relative_to(self: Path, *args: Any, **kwargs: Any) -> Path:
        result = real_relative_to(self, *args, **kwargs)
        if result.parts and result.parts[0] == ".kittify":
            return PureWindowsPath(*result.parts)  # type: ignore[return-value]
        return result

    monkeypatch.setattr(Path, "relative_to", windows_relative_to)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=tmp_path, check=True, capture_output=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run(repo: Path, *args: str) -> Any:
    with contextlib.chdir(repo):
        return runner.invoke(charter_app, list(args), catch_exceptions=False)


def _json_payload(output: str) -> dict[str, Any]:
    return json.loads(output[output.index("{") :])


def _squashed_contains(output: str, phrase: str) -> bool:
    """Match *phrase* in *output* ignoring every whitespace run.

    Rich folds a long line at the console width and the fold lands mid-token
    (``.kittify/charter/interview/ answers.yaml``), so neither the raw text nor a
    space-joined reflow is a reliable container for one path. Dropping whitespace on
    both sides keeps the assertion about the rendered string.
    """
    return "".join(phrase.split()) in "".join(output.split())


def _interviewed_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = _repo(tmp_path, monkeypatch)
    interviewed = _run(repo, "interview", "--defaults", "--json")
    assert interviewed.exit_code == 0, interviewed.output
    return repo


# ---------------------------------------------------------------------------
# The control: the simulation really does reproduce the defect
# ---------------------------------------------------------------------------


def test_simulation_renders_backslashes_for_a_bare_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity control: an unfixed ``str(relative_to(...))`` is Windows-style."""
    install_windows_path_rendering(monkeypatch)
    relative = (tmp_path / ".kittify" / "charter" / "charter.md").relative_to(tmp_path)
    assert "\\" in str(relative), "the Windows path-rendering simulation is vacuous: str() produced no backslash, so this module could never catch the #7044 defect"
    assert relative.as_posix() == CHARTER_REL


# ---------------------------------------------------------------------------
# The two JSON envelopes
# ---------------------------------------------------------------------------


def test_interview_json_reports_a_posix_interview_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "interview", "--defaults", "--json")
    assert result.exit_code == 0, result.output
    payload = _json_payload(result.stdout)

    assert payload["interview_path"] == INTERVIEW_REL
    assert "\\" not in payload["interview_path"]
    assert (repo / payload["interview_path"]).exists(), "the reported path must still resolve on disk"


def test_generate_json_reports_a_posix_charter_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _interviewed_repo(tmp_path, monkeypatch)
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "generate", "--from-interview", "--json")
    assert result.exit_code == 0, result.output
    payload = _json_payload(result.stdout)

    assert payload["charter_path"] == CHARTER_REL
    assert "\\" not in payload["charter_path"]
    assert (repo / payload["charter_path"]).exists(), "the reported path must still resolve on disk"


# ---------------------------------------------------------------------------
# The human-readable lines and the interview error
# ---------------------------------------------------------------------------


def test_interview_text_reports_a_posix_interview_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, monkeypatch)
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "interview", "--defaults")
    assert result.exit_code == 0, result.output

    assert _squashed_contains(result.stdout, f"Interview file: {INTERVIEW_REL}")
    assert ".kittify\\" not in result.stdout


def test_generate_text_reports_a_posix_charter_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _interviewed_repo(tmp_path, monkeypatch)
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "generate", "--from-interview")
    assert result.exit_code == 0, result.output

    assert _squashed_contains(result.stdout, f"Charter: {CHARTER_REL}")
    assert ".kittify\\" not in result.stdout


def test_generate_missing_interview_names_the_posix_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The missing-answers message reaches both the text line and the ``--json`` error string."""
    repo = _repo(tmp_path, monkeypatch)
    install_windows_path_rendering(monkeypatch)

    text = _run(repo, "generate", "--from-interview")
    assert text.exit_code != 0
    assert _squashed_contains(text.stdout, INTERVIEW_REL)
    assert _squashed_contains(text.stdout.lower(), "no charter interview answers found")
    assert ".kittify\\" not in text.stdout

    structured = _run(repo, "generate", "--from-interview", "--json")
    assert structured.exit_code != 0
    assert INTERVIEW_REL in _json_payload(structured.stdout)["error"]


def test_generate_malformed_interview_names_the_posix_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``#2940`` sibling message (present but unreadable) carries the same POSIX path."""
    repo = _repo(tmp_path, monkeypatch)
    answers = repo / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True)
    answers.write_text("mission: [unclosed\n", encoding="utf-8")
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "generate", "--from-interview")
    assert result.exit_code != 0
    assert _squashed_contains(result.stdout, INTERVIEW_REL)
    assert _squashed_contains(result.stdout, "present but malformed")
    assert ".kittify\\" not in result.stdout


# ---------------------------------------------------------------------------
# The `charter status` family renders the path through the same helper
# ---------------------------------------------------------------------------


def test_status_json_reports_a_posix_charter_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins the `_status_collectors` consumers of `_display_path()`, not just the helper."""
    repo = _interviewed_repo(tmp_path, monkeypatch)
    generated = _run(repo, "generate", "--from-interview")
    assert generated.exit_code == 0, generated.output
    install_windows_path_rendering(monkeypatch)

    result = _run(repo, "status", "--json")
    assert result.exit_code == 0, result.output
    payload = _json_payload(result.stdout)

    assert payload["charter_sync"]["charter_path"] == CHARTER_REL
    assert "\\" not in payload["charter_sync"]["charter_path"]


# ---------------------------------------------------------------------------
# `_display_path()`: POSIX in-repo, unchanged fallback outside
# ---------------------------------------------------------------------------


def test_display_path_is_posix_in_repo_and_keeps_the_out_of_repo_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One fixture, both directions: the POSIX branch and the fallback it must not break."""
    repo = tmp_path / "repo"
    (repo / ".kittify" / "charter").mkdir(parents=True)
    in_repo = repo / ".kittify" / "charter" / "charter.md"
    out_of_repo = tmp_path / "elsewhere" / "charter.md"
    install_windows_path_rendering(monkeypatch)

    assert _display_path(in_repo, repo) == CHARTER_REL

    fallback = _display_path(out_of_repo, repo)
    assert fallback == str(out_of_repo), "an out-of-repo path keeps its native spelling"
    assert "charter.md" in fallback
