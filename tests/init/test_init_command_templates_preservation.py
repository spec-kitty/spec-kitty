"""WP03 — `init` preserves user-authored `.kittify/command-templates/` (#4861).

`.kittify/command-templates/` is the operator-authorable LEGACY resolver tier:
the package no longer ships it (WP10 generates shims straight to agent dirs), so
a `command-templates/` present at init time is user content, never package
scratch. The init cleanup loop
(``for cleanup_name in ("templates", "command-templates", ".scratch")``) used to
``shutil.rmtree`` all three unconditionally, silently deleting that user content.

These behavioural tests pin US2's three scenarios (contract C4 US2, data-model
census row 1) against the **real** `init` CLI entry point:

* **Case A — config.yaml ABSENT** carries the RED-on-base evidence: init falls
  through to the cleanup loop, which on base ``rmtree``s the user template.
* **Case B — config.yaml PRESENT** is a GREEN-on-base wiring/invariant guard, not
  a RED repro: init's idempotency ``raise typer.Exit(0)`` makes the cleanup loop
  unreachable, so the template survives trivially on base too. It proves the fix
  is not gated on config.yaml-absence.
* **Never-seeded control** proves the guard still removes genuinely regenerable
  ``templates``/``.scratch`` this run created, and a project that never authored
  ``command-templates/`` still ends without one.

Spec IDs: FR-005, NFR-001, NFR-006, C-006.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command

pytestmark = [pytest.mark.integration]

_CUSTOM_BYTES = "<!-- my hand-authored command template -->\ncustom body\n"
_CUSTOM_REL = Path(".kittify") / "command-templates" / "custom.md"


def _make_init_app() -> tuple[Typer, io.StringIO]:
    """A minimal Typer app with `init` registered against a captured console.

    The init command prints diagnostics through the injected ``_console`` (not
    click's stdout), so the returned :class:`io.StringIO` — not
    ``result.output`` — is where a preservation diagnostic surfaces.
    """
    app = Typer()
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False)
    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda _proj, _mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda _path, tracker=None: None,
    )
    return app, buffer


def _fake_copy_pkg(project_path: Path) -> Path:
    """Package-mode base copy that creates only the empty `.kittify/` root."""
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return kittify / "templates" / "command-templates"


def _fake_copy_pkg_with_scratch(project_path: Path) -> Path:
    """Package-mode base copy that also stages regenerable scratch this run.

    ``.kittify/templates`` and ``.kittify/.scratch`` are the package-managed
    regenerable locations the cleanup loop legitimately removes — seed them so
    the never-seeded control can assert they are still deleted.
    """
    kittify = project_path / ".kittify"
    templates = kittify / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "base.md").write_text("regenerable base template\n", encoding="utf-8")
    scratch = kittify / ".scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "staged.md").write_text("staged scratch\n", encoding="utf-8")
    return templates / "command-templates"


def _seed_command_template(project: Path) -> Path:
    """Seed `.kittify/command-templates/custom.md` with known operator bytes."""
    target = project / _CUSTOM_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_CUSTOM_BYTES, encoding="utf-8")
    return target


def _patch_package_init(monkeypatch: pytest.MonkeyPatch, copy_fake: object) -> None:
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", copy_fake)


def test_case_a_config_absent_preserves_user_command_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Case A (RED-on-base): with no config.yaml, init reaches the cleanup loop;
    the user's `command-templates/custom.md` must SURVIVE in place, init exits 0,
    and a diagnostic names the preserved path."""
    app, buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg)

    # "Here" mode (no positional name, cwd == the seeded project) is the only
    # way init runs into an existing directory; a positional name onto an
    # existing dir is refused with a Directory Conflict.
    project = tmp_path / "proj-a"
    project.mkdir()
    _seed_command_template(project)
    assert not (project / ".kittify" / "config.yaml").exists()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    preserved = project / _CUSTOM_REL
    assert preserved.is_file(), "init cleanup deleted the user-authored command-templates/custom.md"
    assert preserved.read_text(encoding="utf-8") == _CUSTOM_BYTES

    assert "command-templates" in diagnostics and "Preserved" in diagnostics, f"expected a preservation diagnostic naming command-templates; got:\n{diagnostics}"


def test_case_b_config_present_preserves_user_command_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Case B (GREEN-on-base invariant guard, NOT red-on-base): with config.yaml
    present, init exits 0 early via idempotency — the cleanup loop is unreachable,
    so the user template must be preserved regardless of config.yaml presence."""
    app, buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg)

    project = tmp_path / "proj-b"
    (project / ".kittify").mkdir(parents=True)
    _seed_command_template(project)
    (project / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n  auto_commit: true\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "claude", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    preserved = project / _CUSTOM_REL
    assert preserved.is_file(), "init deleted the user-authored command-templates/custom.md (config present)"
    assert preserved.read_text(encoding="utf-8") == _CUSTOM_BYTES


def test_never_seeded_still_removes_regenerable_scratch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Control: a project that never authored `command-templates/` still ends with
    none, while the guard still removes the package-managed `templates`/`.scratch`
    this run created (owned-delete non-vacuity for US2)."""
    app, _buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg_with_scratch)

    project = tmp_path / "proj-c"
    project.mkdir()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    assert result.exit_code == 0, f"init failed: {result.output}"
    assert not (project / ".kittify" / "command-templates").exists(), "a never-seeded project must not end with a command-templates/ directory"
    assert not (project / ".kittify" / "templates").exists(), "regenerable .kittify/templates/ this run created must still be removed"
    assert not (project / ".kittify" / ".scratch").exists(), "regenerable .kittify/.scratch/ this run created must still be removed"
