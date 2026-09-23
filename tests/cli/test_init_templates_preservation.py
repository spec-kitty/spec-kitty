"""WP03 — #4931 `init` must never silently destroy `.kittify/templates/` (P0).

`spec-kitty init` on a project with no `.kittify/config.yaml` destroyed a
user-authored `.kittify/templates/` tree with no backup, exit 0. There are
TWO distinct destroyers (do not conflate the mechanisms):

  1. **Removal seam** — `init.py`'s cleanup loop proved `.kittify/templates`
     package-owned by PATH NAME (`ManagedPathProver(managed_relpaths={...})`),
     so the guard removed it even when this invocation never created it.
  2. **Overwrite seam** (full-copy path only) — `template/manager.py` did an
     unconditional `shutil.rmtree(templates_dest)` + `copytree` in BOTH
     `copy_specify_base_from_local` and `copy_specify_base_from_package` (the
     pip-installed default `init` path) before the guard is ever reached.

Each arm below exercises the REAL `init` CLI entry point (through
`register_init_command` + `CliRunner`, per repo convention — see
`tests/init/test_init_command_templates_preservation.py`), never a
hand-rolled reimplementation. The package-copy arm additionally calls
`copy_specify_base_from_package` DIRECTLY (T010): inside a spec-kitty
checkout, `get_local_repo_root()` resolves to the LOCAL path, so patching
only `get_local_repo_root` to return a fake local repo (rather than `None`)
exercises `copy_specify_base_from_local`, not the package function — the
package arm must be forced explicitly or the pip-default destroyer hides.

Spec IDs: FR-001, FR-005, NFR-001, NFR-002, C-002, C-003, C-004.
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
from specify_cli.template import manager
from specify_cli.template.manager import TemplateCopyResult

pytestmark = [pytest.mark.integration, pytest.mark.regression]

_OPERATOR_BYTES = "<!-- #4931 hand-authored operator template -->\nunique-marker-4931\n"
_OPERATOR_REL = Path(".kittify") / "templates" / "spec-template.md"


def _make_init_app() -> tuple[Typer, io.StringIO]:
    """A minimal Typer app with `init` registered against a captured console.

    `init` prints diagnostics through the injected ``_console`` (not click's
    stdout), so the returned :class:`io.StringIO` — not ``result.output`` —
    is where a preservation diagnostic surfaces.
    """
    app = Typer()
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=240)
    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda _proj, _mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda _path, tracker=None: None,
    )
    return app, buffer


def _seed_operator_templates(project: Path, *, extra: dict[str, str] | None = None) -> Path:
    """Seed `.kittify/templates/spec-template.md` with known operator bytes."""
    target = project / _OPERATOR_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_OPERATOR_BYTES, encoding="utf-8")
    for rel_name, content in (extra or {}).items():
        (target.parent / rel_name).write_text(content, encoding="utf-8")
    return target


def _fake_copy_pkg_noop_templates(project_path: Path) -> TemplateCopyResult:
    """Package-mode base copy that creates only the empty `.kittify/` root.

    Does NOT touch `.kittify/templates` at all — used to isolate the
    **removal seam** (init.py's cleanup guard) from the **overwrite seam**
    (manager.py's copy functions), which is exercised separately below.
    """
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=False)


def _fake_copy_pkg_creates_templates(project_path: Path) -> TemplateCopyResult:
    """Package-mode base copy that genuinely creates `.kittify/templates` this run.

    Used by the run-created CONTROL arm: a tree this invocation creates must
    still be cleaned up (US1 #3), proving the fix is not a blanket refusal.
    """
    kittify = project_path / ".kittify"
    templates = kittify / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "base.md").write_text("regenerable base template\n", encoding="utf-8")
    return TemplateCopyResult(templates / "command-templates", templates_created=True)


def _patch_package_init(monkeypatch: pytest.MonkeyPatch, copy_fake: object) -> None:
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", copy_fake)


def _build_local_repo(repo_root: Path) -> None:
    """Build a minimal local-checkout template source tree for `copy_specify_base_from_local`."""
    templates_src = repo_root / "src" / "charter" / "offering" / "templates" / "command-templates"
    templates_src.mkdir(parents=True)
    (templates_src / "sample.md").write_text("fresh local content\n", encoding="utf-8")
    (repo_root / "src" / "charter" / "offering" / "templates" / "AGENTS.md").write_text("agents\n", encoding="utf-8")


def _find_backed_up(backup_root: Path, *relative_parts: str) -> Path | None:
    """Locate a file by its trailing path parts anywhere under `backup_root`."""
    for candidate in backup_root.rglob(relative_parts[-1]):
        if candidate.parts[-len(relative_parts) :] == relative_parts:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Arm 1 — the REMOVAL seam (init.py's cleanup guard proves-by-name)
# ---------------------------------------------------------------------------


def test_guard_path_preserves_pre_existing_operator_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#4931 arm 1 (RED-on-base): a pre-existing `.kittify/templates/` this
    invocation never created must survive `init`'s cleanup guard — no
    `config.yaml`, package-mode base copy faked to a no-op so only the
    removal seam is under test."""
    app, buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg_noop_templates)

    project = tmp_path / "proj-guard"
    project.mkdir()
    _seed_operator_templates(project)
    assert not (project / ".kittify" / "config.yaml").exists()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    preserved = project / _OPERATOR_REL
    backup_dirs = [p for p in (project / ".kittify").glob(".backup-*") if p.is_dir()]
    survived_in_place = preserved.is_file() and preserved.read_text(encoding="utf-8") == _OPERATOR_BYTES
    survived_in_backup = any(_find_backed_up(b, "templates", "spec-template.md") is not None for b in backup_dirs)
    assert survived_in_place or survived_in_backup, "init's cleanup guard destroyed the pre-existing operator .kittify/templates/ tree (removal seam, #4931)"


# ---------------------------------------------------------------------------
# Arm 2 — the OVERWRITE seam, LOCAL full-copy path
# ---------------------------------------------------------------------------


def test_local_full_copy_backs_up_pre_existing_operator_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#4931 arm 2 (RED-on-base): `copy_specify_base_from_local` must back up
    a pre-existing operator `.kittify/templates/` before its rmtree+copytree,
    not destroy it outright."""
    app, buffer = _make_init_app()

    repo_root = tmp_path / "repo"
    _build_local_repo(repo_root)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: repo_root)

    project = tmp_path / "proj-local"
    project.mkdir()
    _seed_operator_templates(project)
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    backup_dirs = [p for p in (project / ".kittify").glob(".backup-*") if p.is_dir()]
    assert backup_dirs, "expected a .kittify/.backup-<ts>/ directory preserving the pre-existing operator templates/ before the local full-copy overwrite"
    preserved = None
    for backup_dir in backup_dirs:
        preserved = preserved or _find_backed_up(backup_dir, "templates", "spec-template.md")
    assert preserved is not None, "operator's spec-template.md was not preserved before the LOCAL full-copy overwrite (manager.py:copy_specify_base_from_local)"
    assert preserved.read_text(encoding="utf-8") == _OPERATOR_BYTES


# ---------------------------------------------------------------------------
# Arm 3 — the OVERWRITE seam, PACKAGE full-copy path (the pip-installed
# default `init`) — called DIRECTLY so the LOCAL-path resolution inside a
# spec-kitty checkout cannot hide this destroyer.
# ---------------------------------------------------------------------------


def test_package_full_copy_backs_up_pre_existing_operator_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#4931 arm 3 (RED-on-base, the P0's most common path): calls
    `copy_specify_base_from_package` DIRECTLY — inside a spec-kitty checkout,
    resolving through the real `init` CLI would silently fall through to
    `copy_specify_base_from_local` instead (because `get_local_repo_root()`
    finds this very checkout), hiding the pip-installed default's destroyer."""
    fake_pkg = tmp_path / "package_data"
    templates_root = fake_pkg / "templates" / "command-templates"
    templates_root.mkdir(parents=True)
    (templates_root / "sample.md").write_text("fresh packaged content\n", encoding="utf-8")
    (fake_pkg / "templates" / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    monkeypatch.setattr(manager, "files", lambda _: fake_pkg)

    project_path = tmp_path / "pkg-project"
    kittify_root = project_path / ".kittify"
    kittify_root.mkdir(parents=True)
    _seed_operator_templates(project_path)

    manager.copy_specify_base_from_package(project_path)

    backup_dirs = [p for p in kittify_root.glob(".backup-*") if p.is_dir()]
    assert backup_dirs, "expected a .kittify/.backup-<ts>/ directory preserving the pre-existing operator templates/ before the PACKAGE full-copy overwrite"
    preserved = None
    for backup_dir in backup_dirs:
        preserved = preserved or _find_backed_up(backup_dir, "templates", "spec-template.md")
    assert preserved is not None, (
        "operator's spec-template.md was not preserved before the PACKAGE full-copy overwrite "
        "(manager.py:copy_specify_base_from_package, the pip-installed default init path)"
    )
    assert preserved.read_text(encoding="utf-8") == _OPERATOR_BYTES

    # Fresh packaged content still landed -- this is a backup-then-proceed,
    # not a refusal.
    assert (kittify_root / "templates" / "command-templates" / "sample.md").read_text(encoding="utf-8") == "fresh packaged content\n"


# ---------------------------------------------------------------------------
# Arm 4 — RE-ARM (pre-PR squad BLOCKER): `init.py` set
# `templates_dir_created_this_run` UNCONDITIONALLY right after calling
# `copy_specify_base_from_local`/`copy_specify_base_from_package`, even when
# the templates SOURCE was absent and the copy function's templates branch
# never ran (manager.py's `if templates_src.exists():` / `_resource_exists`
# guard skips it entirely -- no backup, no copytree). The unconditional flag
# then fed `ManagedPathProver(run_created={...})`, which "proved" a
# pre-existing operator `.kittify/templates/` run-created, and the cleanup
# guard deleted it -- no backup, exit 0, no diagnostic. This exercises the
# REAL `copy_specify_base_from_local` (not a fake), matching the local-mode
# reproduction: a partial checkout lacking
# `src/charter/offering/templates`.
# ---------------------------------------------------------------------------


def test_local_full_copy_source_absent_preserves_pre_existing_operator_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#4931 re-arm (RED-on-base): when the LOCAL templates SOURCE is absent,
    `init` must not treat `.kittify/templates/` as run-created just because
    the (no-op) copy step ran -- the pre-existing operator tree must survive
    with a preserved/not-package-owned diagnostic."""
    app, buffer = _make_init_app()

    repo_root = tmp_path / "repo-no-templates-src"
    repo_root.mkdir()
    # Deliberately do NOT create src/charter/offering/templates -- the
    # templates SOURCE is absent, so copy_specify_base_from_local's
    # templates branch is skipped entirely (no backup, no copytree).
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: repo_root)

    project = tmp_path / "proj-local-source-absent"
    project.mkdir()
    _seed_operator_templates(project)
    assert not (project / ".kittify" / "config.yaml").exists()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    preserved = project / _OPERATOR_REL
    backup_dirs = [p for p in (project / ".kittify").glob(".backup-*") if p.is_dir()]
    survived_in_place = preserved.is_file() and preserved.read_text(encoding="utf-8") == _OPERATOR_BYTES
    survived_in_backup = any(_find_backed_up(b, "templates", "spec-template.md") is not None for b in backup_dirs)
    assert survived_in_place or survived_in_backup, (
        "init destroyed the pre-existing operator .kittify/templates/ tree when the LOCAL templates "
        "SOURCE was absent -- templates_dir_created_this_run was set unconditionally instead of "
        "reflecting whether copy_specify_base_from_local actually created it (#4931 re-arm)"
    )
    # The copy step never touched templates/, so nothing was backed up --
    # the tree must survive IN PLACE via the removal guard's "not
    # package-owned" diagnostic, not via manager.py's backup-then-proceed.
    assert survived_in_place, "expected the untouched operator templates/ to survive IN PLACE (removal guard), not merely in a backup"
    assert "not package-owned" in diagnostics, f"expected a 'not package-owned' preserved diagnostic (#4931); got:\n{diagnostics}"


# ---------------------------------------------------------------------------
# CONTROLS — a genuinely run-created tree is still cleaned; legacy
# command-templates/ remains preserved (US1 #3, NFR-002).
# ---------------------------------------------------------------------------


def test_control_run_created_templates_still_cleaned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Control: a `.kittify/templates/` this invocation genuinely creates
    (never pre-existing) must still be removed by the cleanup guard --
    otherwise the fix would be a blanket refusal, not provenance-accurate."""
    app, _buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg_creates_templates)

    project = tmp_path / "proj-control"
    project.mkdir()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    assert result.exit_code == 0, f"init failed: {result.output}"
    assert not (project / ".kittify" / "templates").exists(), "a run-created .kittify/templates/ tree must still be removed by the cleanup guard (control, US1 #3)"


def test_control_command_templates_still_preserved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Control (NFR-002): the pre-existing `command-templates` preservation
    behavior (#4861) must remain green alongside the #4931 fix."""
    app, buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg_noop_templates)

    project = tmp_path / "proj-command-templates"
    project.mkdir()
    custom = project / ".kittify" / "command-templates" / "custom.md"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("hand-authored\n", encoding="utf-8")
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"
    assert custom.is_file()
    assert custom.read_text(encoding="utf-8") == "hand-authored\n"


# ---------------------------------------------------------------------------
# probe_cfgdel arm (T014) — config.yaml removed after a prior init leaves
# .kittify/templates populated; a re-run without config.yaml must still
# preserve the operator tree, not just the never-configured case.
# ---------------------------------------------------------------------------


def test_probe_cfgdel_config_removed_still_preserves_operator_templates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """probe_cfgdel: config.yaml was deleted (e.g. to reset configuration)
    but `.kittify/templates/` from the prior init survives on disk -- the
    guard path must preserve it exactly as in the never-configured case."""
    app, buffer = _make_init_app()
    _patch_package_init(monkeypatch, _fake_copy_pkg_noop_templates)

    project = tmp_path / "proj-cfgdel"
    project.mkdir()
    _seed_operator_templates(project)
    assert not (project / ".kittify" / "config.yaml").exists()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(app, ["init", "--ai", "codex", "--non-interactive"])

    diagnostics = buffer.getvalue()
    assert result.exit_code == 0, f"init failed: {result.output}\n{diagnostics}"

    preserved = project / _OPERATOR_REL
    backup_dirs = [p for p in (project / ".kittify").glob(".backup-*") if p.is_dir()]
    survived_in_place = preserved.is_file() and preserved.read_text(encoding="utf-8") == _OPERATOR_BYTES
    survived_in_backup = any(_find_backed_up(b, "templates", "spec-template.md") is not None for b in backup_dirs)
    assert survived_in_place or survived_in_backup, "config.yaml-absent (post-delete) re-run destroyed the operator's pre-existing .kittify/templates/ tree"
