from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console

from specify_cli.template import manager, get_local_repo_root
from specify_cli.template.manager import copy_specify_base_from_local


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_get_local_repo_root_prefers_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    templates_dir = tmp_path / "src" / "charter" / "offering" / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "AGENTS.md").write_text("# agents", encoding="utf-8")
    (tmp_path / "packs" / "built-in" / "missions").mkdir(parents=True)

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(tmp_path))
    try:
        repo_root = get_local_repo_root()
        assert repo_root == tmp_path.resolve()
    finally:
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)


def test_get_local_repo_root_invalid_env_clarifies_packaged_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = io.StringIO()
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(tmp_path))
    monkeypatch.setattr(manager, "console", Console(file=output, force_terminal=False, width=240))

    repo_root = get_local_repo_root()

    assert repo_root is None or repo_root.exists()
    assert "not a Spec Kitty checkout/template root" in output.getvalue()
    assert "using packaged templates" in output.getvalue()


def test_copy_specify_base_from_local_copies_expected_assets(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Memory is still copied from .kittify/memory/ (project-specific content)
    memory_src = repo_root / ".kittify" / "memory"
    memory_src.mkdir(parents=True, exist_ok=True)
    (memory_src / "seed.txt").write_text("hello", encoding="utf-8")

    templates_src = repo_root / "src" / "charter" / "offering" / "templates" / "command-templates"
    templates_src.mkdir(parents=True)
    (templates_src / "sample.md").write_text("content", encoding="utf-8")
    (repo_root / "src" / "charter" / "offering" / "templates" / "AGENTS.md").write_text("agents", encoding="utf-8")

    missions_src = repo_root / "packs" / "built-in" / "missions" / "default"
    missions_src.mkdir(parents=True)
    (missions_src / "rules.md").write_text("rules", encoding="utf-8")

    project_path = tmp_path / "project"
    project_path.mkdir()

    result = copy_specify_base_from_local(repo_root, project_path)

    assert result.command_templates_dir.exists()
    assert result.templates_created is True
    assert (project_path / ".kittify" / "memory" / "seed.txt").read_text(encoding="utf-8") == "hello"
    assert (project_path / ".kittify" / "templates" / "command-templates" / "sample.md").exists()
    assert (project_path / ".kittify" / "missions" / "default" / "rules.md").exists()


def test_copy_specify_base_from_package_uses_packaged_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pkg = tmp_path / "package_data"
    (fake_pkg / "memory").mkdir(parents=True)
    (fake_pkg / "memory" / "seed.txt").write_text("seed", encoding="utf-8")

    # Package uses templates/command-templates
    templates_root = fake_pkg / "templates" / "command-templates"
    templates_root.mkdir(parents=True)
    (templates_root / "sample.md").write_text("demo", encoding="utf-8")
    (fake_pkg / "templates" / "AGENTS.md").write_text("rules", encoding="utf-8")

    missions_root = fake_pkg / "missions" / "default"
    missions_root.mkdir(parents=True)
    (missions_root / "rules.md").write_text("mission rules", encoding="utf-8")

    monkeypatch.setattr(manager, "files", lambda _: fake_pkg)

    project_path = tmp_path / "pkg-project"
    project_path.mkdir()

    result = manager.copy_specify_base_from_package(project_path)

    assert result.command_templates_dir.exists()
    assert result.templates_created is True
    assert (result.command_templates_dir / "sample.md").exists()
    assert (project_path / ".kittify" / "memory" / "seed.txt").exists()


# ---------------------------------------------------------------------------
# FR-001(b)/#4931 — BOTH full-copy functions back up a pre-existing operator
# templates/ before overwriting it, mirroring the in-file memory/ precedent
# (#4759). Missing either arm leaves the P0 destroyer live.
# ---------------------------------------------------------------------------


def test_copy_specify_base_from_local_backs_up_pre_existing_templates(tmp_path: Path) -> None:
    """#4931: `copy_specify_base_from_local` must back up (not rmtree) a
    pre-existing operator `.kittify/templates/` before its full-copy refresh."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    templates_src = repo_root / "src" / "charter" / "offering" / "templates" / "command-templates"
    templates_src.mkdir(parents=True)
    (templates_src / "sample.md").write_text("fresh content", encoding="utf-8")
    (repo_root / "src" / "charter" / "offering" / "templates" / "AGENTS.md").write_text("agents", encoding="utf-8")

    project_path = tmp_path / "project"
    kittify_root = project_path / ".kittify"
    operator_file = kittify_root / "templates" / "spec-template.md"
    operator_file.parent.mkdir(parents=True)
    operator_bytes = "<!-- operator-authored -->\n"
    operator_file.write_text(operator_bytes, encoding="utf-8")

    result = manager.copy_specify_base_from_local(repo_root, project_path)

    assert result.templates_created is True
    # Fresh content landed.
    assert (kittify_root / "templates" / "command-templates" / "sample.md").read_text(encoding="utf-8") == "fresh content"

    # Operator's pre-existing templates/ bytes survive under a backup dir.
    backup_dirs = [p for p in kittify_root.iterdir() if p.is_dir() and p.name.startswith(".backup-")]
    assert backup_dirs, "expected a .kittify/.backup-<ts>/ directory preserving the pre-existing templates/"
    preserved = None
    for backup_dir in backup_dirs:
        candidate = backup_dir / "templates" / "spec-template.md"
        if candidate.is_file():
            preserved = candidate
            break
    assert preserved is not None, "operator's spec-template.md was not preserved before the LOCAL full-copy overwrite"
    assert preserved.read_text(encoding="utf-8") == operator_bytes


def test_copy_specify_base_from_package_backs_up_pre_existing_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4931: `copy_specify_base_from_package` (the pip-installed default
    `init` path) must back up (not rmtree) a pre-existing operator
    `.kittify/templates/` before its full-copy refresh."""
    fake_pkg = tmp_path / "package_data"
    templates_root = fake_pkg / "templates" / "command-templates"
    templates_root.mkdir(parents=True)
    (templates_root / "sample.md").write_text("fresh packaged content", encoding="utf-8")
    (fake_pkg / "templates" / "AGENTS.md").write_text("agents", encoding="utf-8")
    monkeypatch.setattr(manager, "files", lambda _: fake_pkg)

    project_path = tmp_path / "pkg-project"
    kittify_root = project_path / ".kittify"
    operator_file = kittify_root / "templates" / "spec-template.md"
    operator_file.parent.mkdir(parents=True)
    operator_bytes = "<!-- operator-authored -->\n"
    operator_file.write_text(operator_bytes, encoding="utf-8")

    result = manager.copy_specify_base_from_package(project_path)

    assert result.templates_created is True
    # Fresh content landed.
    assert (kittify_root / "templates" / "command-templates" / "sample.md").read_text(encoding="utf-8") == "fresh packaged content"

    # Operator's pre-existing templates/ bytes survive under a backup dir.
    backup_dirs = [p for p in kittify_root.iterdir() if p.is_dir() and p.name.startswith(".backup-")]
    assert backup_dirs, "expected a .kittify/.backup-<ts>/ directory preserving the pre-existing templates/"
    preserved = None
    for backup_dir in backup_dirs:
        candidate = backup_dir / "templates" / "spec-template.md"
        if candidate.is_file():
            preserved = candidate
            break
    assert preserved is not None, "operator's spec-template.md was not preserved before the PACKAGE full-copy overwrite (the pip-installed default init path)"
    assert preserved.read_text(encoding="utf-8") == operator_bytes


# ---------------------------------------------------------------------------
# Pre-PR squad BLOCKER (#4931 re-arm) — `templates_created` must reflect
# whether the templates SOURCE existed, not just whether the function ran.
# A caller (init.py) that treats a missing source as "created" re-arms the
# #4931 P0: a pre-existing operator `.kittify/templates/` gets proven
# run-created and silently deleted with no backup.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_copy_specify_base_from_local_reports_not_created_when_source_absent(tmp_path: Path) -> None:
    """#4931 re-arm: when the LOCAL templates SOURCE is absent, the templates
    branch never runs (no backup, no copytree) and `templates_created` must
    be False -- never unconditionally True."""
    repo_root = tmp_path / "repo-no-templates-src"
    repo_root.mkdir()
    # Deliberately no src/charter/offering/templates/ under repo_root.

    project_path = tmp_path / "project"
    project_path.mkdir()

    result = manager.copy_specify_base_from_local(repo_root, project_path)

    assert result.templates_created is False, "templates_created must be False when the local templates source is absent (#4931 re-arm)"


@pytest.mark.regression
def test_copy_specify_base_from_package_reports_not_created_when_source_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4931 re-arm: when NO packaged templates resource exists (all
    candidates absent), the templates branch never runs and
    `templates_created` must be False -- never unconditionally True."""
    fake_pkg = tmp_path / "package_data_no_templates"
    fake_pkg.mkdir(parents=True)
    # Deliberately no templates/ subdirectory under fake_pkg.
    monkeypatch.setattr(manager, "files", lambda _: fake_pkg)

    project_path = tmp_path / "pkg-project"
    project_path.mkdir()

    result = manager.copy_specify_base_from_package(project_path)

    assert result.templates_created is False, "templates_created must be False when no packaged templates resource exists (#4931 re-arm)"
