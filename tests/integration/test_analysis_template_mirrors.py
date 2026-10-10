"""Only canonically selected package-identical global templates are report inputs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.paths import get_package_asset_root
from specify_cli.analysis_inputs import collect_material_inputs
from specify_cli.analysis_report import check_analysis_report_current
from tests.specify_cli.cli.commands.agent.test_analysis_report_transaction import REPORT, SLUG, git, invoke, repo as repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture
def mirror(repo, tmp_path, monkeypatch):
    from specify_cli.runtime import resolver

    home = tmp_path / "global"
    monkeypatch.setattr(resolver, "get_kittify_home", lambda: home)
    return home


def install(home: Path, tier: str):
    directory = home / ("missions/software-dev/templates" if tier == "mission" else "templates")
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("spec-template.md", "plan-template.md"):
        (directory / name).write_bytes((get_package_asset_root() / "software-dev/templates" / name).read_bytes())
    return directory


@pytest.mark.parametrize("tier", ["mission", "general"])
def test_package_mirror_records_with_selection_identity(repo, mirror, tier):
    install(mirror, tier)
    app = repo / "application.txt"
    app.write_text("staged\n", encoding="utf-8")
    git(repo, "add", "application.txt")
    app.write_text("staged\nunstaged\n", encoding="utf-8")
    index = git(repo, "diff", "--cached")
    result = invoke("--report-only")
    assert result.exit_code == 0, result.output
    inputs = collect_material_inputs(repo / "kitty-specs" / SLUG, repo)
    selections = {key: value for key, value in inputs.items() if key.startswith("template-selection:")}
    assert selections
    assert all(value["path"] is None for value in selections.values())
    assert str(mirror) not in json.dumps(inputs)
    assert git(repo, "diff", "--cached") == index
    assert app.read_text() == "staged\nunstaged\n"
    assert check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok
    assert json.loads(invoke("--report-only").output)["commit_status"] == "unchanged"


@pytest.mark.parametrize("bad", ["custom", "file_symlink", "ancestor_symlink", "home_symlink"])
def test_global_template_refusal_is_before_write(repo, mirror, tmp_path, bad):
    directory = install(mirror, "mission")
    path = directory / "spec-template.md"
    if bad == "custom":
        path.write_text("custom mutable authority\n")
    elif bad == "file_symlink":
        path.unlink()
        path.symlink_to(get_package_asset_root() / "software-dev/templates/spec-template.md")
    else:
        destination = tmp_path / "relocated"
        moved = directory if bad == "ancestor_symlink" else mirror
        moved.rename(destination)
        moved.symlink_to(destination, target_is_directory=True)
    before = git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert not (repo / REPORT).exists()
    assert (git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD")) == before


@pytest.mark.parametrize("change", ["content", "tier", "override", "home"])
def test_template_selection_changes_invalidate_freshness(repo, mirror, change, tmp_path, monkeypatch):
    directory = install(mirror, "general")
    result = invoke("--report-only")
    assert result.exit_code == 0, result.output
    if change == "content":
        (directory / "spec-template.md").write_text("changed authority\n")
    elif change == "tier":
        install(mirror, "mission")
    elif change == "home":
        from specify_cli.runtime import resolver

        other_home = tmp_path / "other-global"
        install(other_home, "general")
        monkeypatch.setattr(resolver, "get_kittify_home", lambda: other_home)
    else:
        override = repo / ".kittify/overrides/missions/software-dev/templates"
        override.mkdir(parents=True)
        for source in directory.iterdir():
            (override / source.name).write_bytes(source.read_bytes())
        git(repo, "add", ".kittify/overrides")
        git(repo, "commit", "-qm", "pin project selection")
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok


@pytest.mark.parametrize("change", ["content", "tier"])
def test_template_selection_race_retains_unqualified_report(repo, mirror, monkeypatch, change):
    from specify_cli.git import report_transaction

    directory = install(mirror, "general")
    real_write = report_transaction.write_analysis_report

    def race(*args, **kwargs):
        result = real_write(*args, **kwargs)
        if change == "content":
            (directory / "spec-template.md").write_text("raced authority\n")
        else:
            install(mirror, "mission")
        return result

    monkeypatch.setattr(report_transaction, "write_analysis_report", race)
    head = git(repo, "rev-parse", "HEAD")
    result = invoke("--report-only")
    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["commit_status"] == "written_uncommitted"
    assert git(repo, "rev-parse", "HEAD") == head
    assert not check_analysis_report_current(repo / "kitty-specs" / SLUG, repo).ok
