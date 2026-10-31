"""``validate_release.py`` checks the companion's three-place version lock (#6904, WP04).

ADR 2026-10-29-1, Amendment 2026-10-31: the ``spec-kitty-cli`` version, the
``services`` extra pin and ``packages/spec-kitty-services/pyproject.toml`` agree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release.validate_release import validate_companion_version_sync, validate_version_source_consistency

pytestmark = [pytest.mark.fast]

_VERSION = "4.0.0rc8"


def _repo(tmp_path: Path, *, extra: str | None = f"spec-kitty-services=={_VERSION}", companion: str | None = _VERSION) -> Path:
    extras = "" if extra is None else f'[project.optional-dependencies]\nservices = ["{extra}"]\n'
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "spec-kitty-cli"\nversion = "{_VERSION}"\n{extras}', encoding="utf-8")
    if companion is not None:
        project = tmp_path / "packages" / "spec-kitty-services"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text(f'[project]\nname = "spec-kitty-services"\nversion = "{companion}"\n', encoding="utf-8")
    return tmp_path


def test_the_three_versions_agree(tmp_path: Path) -> None:
    assert validate_companion_version_sync(_VERSION, _repo(tmp_path)) is None


def test_a_companion_on_another_version_is_an_issue(tmp_path: Path) -> None:
    issue = validate_companion_version_sync(_VERSION, _repo(tmp_path, companion="4.0.0rc7"))
    assert issue is not None
    assert "packages/spec-kitty-services/pyproject.toml" in issue.message
    assert "4.0.0rc7" in issue.message


@pytest.mark.parametrize("extra", ["spec-kitty-services==4.0.0rc7", "spec-kitty-services>=4.0.0rc8", "spec-kitty-services"])
def test_an_extra_pin_other_than_exactly_the_cli_version_is_an_issue(tmp_path: Path, extra: str) -> None:
    issue = validate_companion_version_sync(_VERSION, _repo(tmp_path, extra=extra))
    assert issue is not None
    assert "services" in issue.message


def test_the_extra_without_the_companion_project_is_an_issue(tmp_path: Path) -> None:
    issue = validate_companion_version_sync(_VERSION, _repo(tmp_path, companion=None))
    assert issue is not None
    assert "packages/spec-kitty-services/pyproject.toml" in (issue.hint or "") + issue.message


def test_without_the_extra_there_is_nothing_to_lock(tmp_path: Path) -> None:
    assert validate_companion_version_sync(_VERSION, _repo(tmp_path, extra=None, companion=None)) is None


def test_a_companion_project_without_the_extra_is_an_issue(tmp_path: Path) -> None:
    """WP04 review: a dropped extra must not make the check vacuous while the companion still ships."""
    issue = validate_companion_version_sync(_VERSION, _repo(tmp_path, extra=None))
    assert issue is not None
    assert "services" in issue.message


def test_the_check_is_part_of_the_release_consistency_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.release.validate_release as validator

    for name in (
        "validate_metadata_yaml_version_sync",
        "validate_uv_lock_version_sync",
        "validate_release_covers_migration_targets",
        "validate_changelog_latest_version_sync",
    ):
        monkeypatch.setattr(validator, name, lambda *args, **kwargs: None)
    issues = validate_version_source_consistency(_VERSION, _repo(tmp_path, companion="9.9.9"), tmp_path / "uv.lock", "")
    assert [issue.message for issue in issues if "spec-kitty-services" in issue.message]
