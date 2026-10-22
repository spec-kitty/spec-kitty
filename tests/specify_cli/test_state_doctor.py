"""Tests for the state-roots doctor diagnostic."""

from __future__ import annotations

import json
from pathlib import Path

from specify_cli.state.doctor import check_state_roots


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

def test_roots_resolved(tmp_path):
    """check_state_roots resolves three roots with correct names."""
    (tmp_path / ".kittify").mkdir()
    report = check_state_roots(tmp_path)
    root_names = [r.name for r in report.roots]
    assert "project" in root_names
    assert "global_runtime" in root_names
    assert "global_sync" in root_names


def test_project_root_exists(tmp_path):
    """Project root detected as existing when .kittify/ directory is present."""
    (tmp_path / ".kittify").mkdir()
    report = check_state_roots(tmp_path)
    project = next(r for r in report.roots if r.name == "project")
    assert project.exists is True


def test_project_root_absent(tmp_path):
    """Project root detected as absent when .kittify/ directory is missing."""
    report = check_state_roots(tmp_path)
    project = next(r for r in report.roots if r.name == "project")
    assert project.exists is False


def test_surface_present(tmp_path):
    """Present surfaces are detected when the file exists on disk."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("agents: {}")
    report = check_state_roots(tmp_path)
    config_check = next(
        (s for s in report.surfaces if s.surface.name == "project_config"),
        None,
    )
    assert config_check is not None
    assert config_check.present is True


def test_surface_absent(tmp_path):
    """Absent surfaces are detected when the file does not exist."""
    report = check_state_roots(tmp_path)
    config_check = next(
        (s for s in report.surfaces if s.surface.name == "project_config"),
        None,
    )
    assert config_check is not None
    assert config_check.present is False


def test_absent_runtime_no_warning(tmp_path):
    """Absent runtime surfaces are not warnings (lazily created)."""
    (tmp_path / ".kittify").mkdir()
    report = check_state_roots(tmp_path)
    runtime_checks = [
        s for s in report.surfaces if s.surface.name == "runtime_feature_index"
    ]
    for check in runtime_checks:
        assert check.warning is None  # Absent = no warning


def test_report_to_dict_serializable(tmp_path):
    """Report to_dict() output is JSON-serializable."""
    report = check_state_roots(tmp_path)
    d = report.to_dict()
    json.dumps(d)  # Must not raise
    assert "healthy" in d
    assert "roots" in d
    assert "surfaces" in d
    assert "warnings" in d


def test_healthy_when_no_warnings(tmp_path):
    """Report is healthy when there are no warnings."""
    report = check_state_roots(tmp_path)
    # With no runtime surfaces on disk, no warnings expected
    assert report.healthy is True


def test_warning_for_unignored_runtime(tmp_path, monkeypatch):
    """Present runtime surface not covered by gitignore produces warning."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "merge-state.json").write_text("{}")

    # Mock _is_gitignore_covered to return False
    from specify_cli.state import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_is_gitignore_covered", lambda *a: False)

    report = check_state_roots(tmp_path)
    merge_check = next(
        (s for s in report.surfaces if s.surface.name == "merge_resume_state"),
        None,
    )
    assert merge_check is not None
    assert merge_check.warning is not None
    assert "merge-state.json" in merge_check.warning
    assert not report.healthy


def test_no_warning_for_tracked_surface(tmp_path, monkeypatch):
    """Tracked surfaces never produce gitignore warnings."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("agents: {}")

    # Even if gitignore says "not covered", tracked surfaces are fine
    from specify_cli.state import doctor as doctor_mod

    monkeypatch.setattr(doctor_mod, "_is_gitignore_covered", lambda *a: False)

    report = check_state_roots(tmp_path)
    config_check = next(
        (s for s in report.surfaces if s.surface.name == "project_config"),
        None,
    )
    assert config_check is not None
    assert config_check.warning is None


def test_surfaces_cover_all_state_surfaces(tmp_path):
    """Report surfaces list covers every entry in STATE_SURFACES."""
    from specify_cli.state.contract import STATE_SURFACES

    report = check_state_roots(tmp_path)
    assert len(report.surfaces) == len(STATE_SURFACES)
    report_names = {s.surface.name for s in report.surfaces}
    registry_names = {s.name for s in STATE_SURFACES}
    assert report_names == registry_names


def test_historical_sync_surfaces_report_as_deprecated(tmp_path):
    """The doctor report renders historical sync residue as deprecated."""
    from specify_cli.state.contract import AuthorityClass

    report = check_state_roots(tmp_path)
    surfaces_by_name = {check.surface.name: check for check in report.surfaces}
    historical_names = {
        "lamport_clock",
        "active_queue_scope",
        "sync_daemon_control",
        "legacy_queue",
        "scoped_queue",
        "project_sync_store",
        "project_sync_egress_lock",
        "project_sync_layout_generation",
        "project_sync_layout_generation_lock",
        "project_sync_layout_generation_marker",
        "project_sync_migration_reports",
    }
    for name in historical_names:
        check = surfaces_by_name[name]
        assert check.surface.authority is AuthorityClass.DEPRECATED
        assert check.surface.deprecated is True

    tracker_cache = surfaces_by_name["tracker_cache"]
    assert tracker_cache.surface.authority is AuthorityClass.AUTHORITATIVE
    assert tracker_cache.surface.deprecated is False


# ---------------------------------------------------------------------------
# Regression: Issue 1 -- Feature surfaces must detect presence via parent walk
# ---------------------------------------------------------------------------


def test_feature_surface_present_when_kitty_specs_exists(tmp_path):
    """Feature surfaces report present=True when kitty-specs/ has features.

    Regression for Codex review finding: _check_surface_present() returned
    False unconditionally for FEATURE root surfaces. The fix resolves the
    path under repo_root and falls through to the wildcard/placeholder
    parent-walk logic (kitty-specs/<feature>/meta.json -> kitty-specs/ exists).
    """
    feature_dir = tmp_path / "kitty-specs" / "test-feature"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"name": "test"}')

    report = check_state_roots(tmp_path)
    feature_meta = next(
        (s for s in report.surfaces if s.surface.name == "feature_metadata"),
        None,
    )
    assert feature_meta is not None
    assert feature_meta.present is True


def test_feature_surface_absent_when_no_kitty_specs(tmp_path):
    """Feature surfaces report present=False when kitty-specs/ does not exist."""
    report = check_state_roots(tmp_path)
    feature_meta = next(
        (s for s in report.surfaces if s.surface.name == "feature_metadata"),
        None,
    )
    assert feature_meta is not None
    assert feature_meta.present is False


# ---------------------------------------------------------------------------
# Regression: Issue 2 -- Global runtime staging dirs must resolve from home
# ---------------------------------------------------------------------------


def test_runtime_staging_dirs_detected_when_present(tmp_path, monkeypatch):
    """runtime_staging_dirs surface detects presence of ~/.kittify_update_* dirs.

    Regression for Codex review finding: GLOBAL_RUNTIME path normalization
    stripped ~/.kittify/ prefix, but runtime_staging_dirs has path pattern
    ~/.kittify_update_* which is a sibling of ~/.kittify/, not a child.
    The fix resolves all ~/ paths from Path.home() directly.
    """
    # Use tmp_path as a fake home directory
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    # Create a staging directory that matches the pattern
    (tmp_path / ".kittify_update_abc123").mkdir()

    report = check_state_roots(tmp_path)
    staging = next(
        (s for s in report.surfaces if s.surface.name == "runtime_staging_dirs"),
        None,
    )
    assert staging is not None
    # The glob logic should find .kittify_update_abc123 in tmp_path (home)
    assert staging.present is True


def test_runtime_staging_dirs_absent_when_no_match(tmp_path, monkeypatch):
    """Staging dirs should be absent when no .kittify_update_* exists.

    Regression for Codex review finding: wildcard surface presence check
    used parent-walk (parent.is_dir()) which gave false positives whenever
    the home directory existed. The fix uses glob to check for actual matches.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / ".kittify"))
    (tmp_path / ".kittify").mkdir()
    # Do NOT create any .kittify_update_* dirs

    report = check_state_roots(tmp_path)
    staging = next(
        (s for s in report.surfaces if s.surface.name == "runtime_staging_dirs"),
        None,
    )
    assert staging is not None
    assert staging.present is False  # No matching dirs exist


def test_global_sync_surfaces_resolve_from_home(tmp_path, monkeypatch):
    """Global sync surfaces resolve correctly from home directory.

    Ensures the ~/ prefix resolution handles ~/.spec-kitty/ paths properly.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    # Create the sync config file
    spec_kitty_dir = tmp_path / ".spec-kitty"
    spec_kitty_dir.mkdir()
    (spec_kitty_dir / "config.toml").write_text("[sync]")

    report = check_state_roots(tmp_path)
    sync_config = next(
        (s for s in report.surfaces if s.surface.name == "sync_config"),
        None,
    )
    assert sync_config is not None
    assert sync_config.present is True


def test_agent_block_surface_is_probed_with_a_reserved_name(tmp_path, monkeypatch):
    """#6474: `.agents/skills/` is ignored only for Spec Kitty's names, so the probe uses one."""
    from specify_cli.state import doctor as doctor_mod

    asked: list[str] = []
    monkeypatch.setattr(doctor_mod, "_is_gitignore_covered", lambda _root, path: asked.append(path) or True)

    check_state_roots(tmp_path)

    assert ".agents/skills/spec-kitty-doctor-probe/" in asked
    assert not any("<" in path for path in asked if path.startswith(".agents/"))


@pytest.mark.git_repo
def test_agent_block_covers_the_shared_skills_probe(tmp_path):
    """The probe really is ignored by the block a shared-root agent gets."""
    import subprocess

    from specify_cli.gitignore_manager import GitignoreManager

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    GitignoreManager(tmp_path).protect_all_agents(["codex"])
    (tmp_path / ".agents" / "skills" / "spec-kitty-plan").mkdir(parents=True)

    report = check_state_roots(tmp_path)

    check = next(s for s in report.surfaces if s.surface.name == "shared_skills_projection")
    assert check.gitignore_covered
    assert check.warning is None
