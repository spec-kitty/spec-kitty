"""#6277 regression: `charter synthesize --json` reports POSIX repo-relative paths.

On Windows the envelope spelled its repository-relative paths with ``\\``
(``.kittify\\charter-packs\\PROVENANCE.md``) because the fresh-seed helpers and the
manifest record used ``str(Path.relative_to(...))``, whose separator follows the host OS.
A consumer of the envelope then reads a different path spelling per platform, and the
committed ``.kittify/charter/synthesis-manifest.yaml`` is OS-dependent too.

Windows path rendering is simulated on POSIX, the same way
``tests/runtime/test_windows_readonly_asset_delete.py`` simulates Windows delete
semantics: the simulation patches ``Path.relative_to`` so it returns a Windows-flavoured
path (``str()`` renders ``\\``, ``as_posix()`` still renders ``/``). Faking ``os.name``
is not an option — see ``tests/kernel/test_is_windows_seam.py``: it flips ``pathlib`` to
``WindowsPath`` mid-run and crashes pytest.

The control test proves the harness genuinely reproduces the defect (a bare
``str(relative_to(...))`` under the simulation yields a backslash), so this module cannot
pass vacuously.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import _synthesis
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Windows path-rendering simulation
# ---------------------------------------------------------------------------


def install_windows_path_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``Path.relative_to`` render Windows-style path strings.

    Only paths under ``.kittify`` are re-flavoured: that is the surface this issue is
    about (charter state), and restricting it keeps unrelated callers — which may use the
    result as an access path — on real :class:`Path` objects.
    """
    real_relative_to = Path.relative_to

    def windows_relative_to(self: Path, *args: Any, **kwargs: Any) -> Path:
        result = real_relative_to(self, *args, **kwargs)
        if result.parts and result.parts[0] == ".kittify":
            return PureWindowsPath(*result.parts)  # type: ignore[return-value]
        return result

    monkeypatch.setattr(Path, "relative_to", windows_relative_to)


# ---------------------------------------------------------------------------
# Project fixtures (mirror tests/integration/test_charter_synthesize_fresh.py)
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _write_minimal_interview(repo: Path) -> None:
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: Test charter for the #6277 reported-path regression suite.\n",
        encoding="utf-8",
    )


def _run_generate(project: Path) -> None:
    with contextlib.chdir(project):
        result = runner.invoke(charter_app, ["generate", "--from-interview"], catch_exceptions=False)
    assert result.exit_code == 0, f"charter generate failed: {result.stdout!r}"


def _run_synthesize(project: Path, *args: str) -> Any:
    with contextlib.chdir(project):
        return runner.invoke(charter_app, ["synthesize", *args], catch_exceptions=False)


def _fresh_project(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)
    return tmp_path


def _reported_paths(payload: dict[str, Any]) -> list[str]:
    """Every repository-relative path string the envelope reports."""
    paths: list[str] = []
    for key in ("files_written", "files_planned", "planned_deletes"):
        paths.extend(payload.get(key) or [])
    paths.extend(entry["path"] for entry in payload.get("written_artifacts") or [])
    return paths


# ---------------------------------------------------------------------------
# The control: the simulation really does reproduce the defect
# ---------------------------------------------------------------------------


def test_simulation_renders_backslashes_for_a_bare_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity control: without a fix, ``str(relative_to(...))`` is Windows-style."""
    install_windows_path_rendering(monkeypatch)
    relative = (tmp_path / ".kittify" / "charter-packs" / "PROVENANCE.md").relative_to(tmp_path)
    assert "\\" in str(relative), "the Windows path-rendering simulation is vacuous: str() produced no backslash, so this module could never catch the #6277 defect"
    assert relative.as_posix() == ".kittify/charter-packs/PROVENANCE.md"


# ---------------------------------------------------------------------------
# Fresh seed: reported paths are POSIX on every platform
# ---------------------------------------------------------------------------


def test_fresh_seed_json_reports_only_posix_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _fresh_project(tmp_path)
    install_windows_path_rendering(monkeypatch)

    result = _run_synthesize(project, "--json")
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)

    assert payload["mode"] == "fresh_project_seed"
    reported = _reported_paths(payload)
    assert reported, "the fresh-seed envelope must report at least one path"
    assert [path for path in reported if "\\" in path] == []
    assert sorted(set(reported)) == [
        ".kittify/charter-packs/PROVENANCE.md",
        ".kittify/charter/synthesis-manifest.yaml",
    ]
    for path in reported:
        assert (project / path).exists(), f"reported path does not resolve on disk: {path}"


def test_fresh_seed_dry_run_and_real_run_report_identical_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _fresh_project(tmp_path)
    install_windows_path_rendering(monkeypatch)

    dry = _run_synthesize(project, "--dry-run", "--json")
    assert dry.exit_code == 0, dry.stdout
    dry_payload = json.loads(dry.stdout)
    assert dry_payload["mode"] == "fresh_project_seed_dry_run"
    assert [path for path in _reported_paths(dry_payload) if "\\" in path] == []

    real = _run_synthesize(project, "--json")
    assert real.exit_code == 0, real.stdout
    real_payload = json.loads(real.stdout)

    assert dry_payload["files_planned"] == real_payload["files_written"]
    assert [entry["path"] for entry in dry_payload["written_artifacts"]] == [entry["path"] for entry in real_payload["written_artifacts"]]


def test_fresh_seed_planned_deletes_are_posix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _fresh_project(tmp_path)
    doctrine_dir = project / ".kittify" / "charter-packs"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    (doctrine_dir / "graph.yaml").write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")
    install_windows_path_rendering(monkeypatch)

    result = _run_synthesize(project, "--dry-run", "--json")
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)

    assert payload["planned_deletes"] == [".kittify/charter-packs/graph.yaml"]


# ---------------------------------------------------------------------------
# Real run: the recorded manifest and the projection it feeds are POSIX
# ---------------------------------------------------------------------------


def test_manifest_projection_normalises_a_windows_style_recorded_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An older Windows-written manifest must not re-leak a backslash into the envelope."""
    entries = [
        SimpleNamespace(
            kind="tactic",
            slug="portable-paths",
            path=".kittify\\charter-packs\\tactic\\portable-paths.tactic.yaml",
            provenance_path=".kittify/charter/provenance/tactic-portable-paths.yaml",
        ),
        SimpleNamespace(
            kind="styleguide",
            slug="nested",
            path=".kittify/charter-packs/styleguide/nested.styleguide.yaml",
            provenance_path=".kittify/charter/provenance/styleguide-nested.yaml",
        ),
    ]
    fake_manifest = SimpleNamespace(artifacts=entries)

    monkeypatch.setattr(
        "charter.activation.synthesizer.manifest.load_yaml",
        lambda _path: fake_manifest,
    )
    monkeypatch.setattr(
        "charter.activation.synthesizer.manifest.MANIFEST_PATH",
        ".kittify/charter/synthesis-manifest.yaml",
    )
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    artifacts = _synthesis._load_written_artifacts_from_manifest(Path("/repo"))

    assert [entry["path"] for entry in artifacts] == [
        ".kittify/charter-packs/tactic/portable-paths.tactic.yaml",
        ".kittify/charter-packs/styleguide/nested.styleguide.yaml",
    ]
    assert [entry["path"] for entry in artifacts if "\\" in entry["path"]] == []
