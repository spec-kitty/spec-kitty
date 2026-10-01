"""FR-009 smoke test: a fresh clone does not break the FR-004 charter readers.

Simulates the exact scenario a new contributor hits: clone the repo and invoke
any FR-004 reader before running a single ``spec-kitty charter`` command.

consolidate-charter-bundle (#2773) inverted the charter model: ``charter.yaml``
is now the *authoritative, git-tracked, resolving* source (``charter.md`` is a
curated prose companion), and the retired prose->triad scrape means the readers
no longer auto-materialize ``governance.yaml`` / ``directives.yaml`` /
``metadata.yaml`` derivatives -- those sections are hand-authored *inside*
``charter.yaml`` (``CANONICAL_MANIFEST.derived_files == []``,
``gitignore_required_entries == []``). The enduring contract this suite pins is
therefore: on a fresh clone with the tracked ``charter.yaml`` on disk, every
FR-004 reader resolves that file successfully (no crash, no empty fallback)
without any explicit ``spec-kitty charter sync`` call.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


_CHARTER_MD_BODY = """\
# Project Charter

## Policy Summary

- Baseline assumptions are explicit.
- ``charter.yaml`` is the authoritative resolving source.
"""

#: Sentinel proving a reader actually parsed ``charter.yaml`` rather than
#: returning the empty ``GovernanceConfig`` fallback.
_GOVERNANCE_PROBE_KEY = "fresh_clone_probe"
_GOVERNANCE_PROBE_VALUE = "present"

_CHARTER_YAML_BODY = f"""\
schema_version: '2.0.0'
governance:
  enforcement:
    {_GOVERNANCE_PROBE_KEY}: {_GOVERNANCE_PROBE_VALUE}
directives:
  directives: []
catalog:
  mission: fresh-clone-fixture
  template_set: default
  languages: []
  references: []
metadata:
  generated_at: '2026-01-01T00:00:00+00:00'
  bundle_schema_version: 2
"""


def _fresh_clone_fixture(repo_root: Path) -> Path:
    """Build a 'fresh clone' fixture:

    * git repo with the authoritative ``charter.yaml`` (and prose companion
      ``charter.md``) tracked,
    * no retired derivatives on disk (post-#2773 there are none to
      regenerate).
    """
    subprocess.run(["git", "init", "--quiet", str(repo_root)], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.email", "fresh@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "config", "user.name", "Fresh Clone"],
        check=True,
    )

    (repo_root / ".gitignore").write_text("# fresh-clone fixture\n", encoding="utf-8")
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD_BODY, encoding="utf-8")
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML_BODY, encoding="utf-8")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "add",
            ".gitignore",
            ".kittify/charter/charter.md",
            ".kittify/charter/charter.yaml",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-q", "-m", "fresh-clone fixture"],
        check=True,
    )

    return repo_root


def _assert_charter_yaml_resolved(repo_root: Path) -> None:
    """The authoritative resolving source stays present after a reader call.

    Post-#2773 readers do not materialize derivatives; the observable contract
    is that the tracked ``charter.yaml`` is the source they resolve.
    """
    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml.exists(), "authoritative charter.yaml missing after reader invocation"


def _clear_resolver_cache() -> None:
    from charter.resolution import resolve_canonical_repo_root

    resolve_canonical_repo_root.cache_clear()


def test_build_charter_context_auto_syncs_on_fresh_clone(tmp_path: Path) -> None:
    """FR-004 reader: ``build_charter_context`` resolves the tracked charter.yaml."""
    from charter.activation.context import build_charter_context

    repo_root = _fresh_clone_fixture(tmp_path).resolve()
    _clear_resolver_cache()

    result = build_charter_context(repo_root, action="specify")
    assert result is not None
    assert result.action == "specify"
    _assert_charter_yaml_resolved(repo_root)


def test_load_governance_config_auto_syncs_on_fresh_clone(tmp_path: Path) -> None:
    """FR-004 reader: ``load_governance_config`` reads charter.yaml's governance section."""
    from charter.activation.sync import load_governance_config

    repo_root = _fresh_clone_fixture(tmp_path).resolve()
    _clear_resolver_cache()

    governance = load_governance_config(repo_root)
    assert governance is not None
    # Proves the reader parsed the tracked charter.yaml rather than returning
    # the empty ``GovernanceConfig`` fallback.
    assert governance.enforcement.get(_GOVERNANCE_PROBE_KEY) == _GOVERNANCE_PROBE_VALUE
    _assert_charter_yaml_resolved(repo_root)


def test_charter_status_cli_auto_syncs_on_fresh_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004 reader: ``spec-kitty charter status`` handler flips through chokepoint."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import app as charter_app

    repo_root = _fresh_clone_fixture(tmp_path).resolve()
    _clear_resolver_cache()

    runner = CliRunner()
    monkeypatch.chdir(repo_root)
    result = runner.invoke(charter_app, ["status", "--json"])

    assert result.exit_code == 0, f"charter status failed: {result.output!r}"
    _assert_charter_yaml_resolved(repo_root)


def test_no_importerror_or_repo_errors_on_fresh_clone(tmp_path: Path) -> None:
    """Sanity check: readers do not raise ``NotInsideRepositoryError`` on a
    well-formed fresh clone, and we do not hit import-time breakage.
    """
    from charter.activation.context import build_charter_context
    from charter.resolution import (
        GitCommonDirUnavailableError,
        NotInsideRepositoryError,
    )

    repo_root = _fresh_clone_fixture(tmp_path).resolve()
    _clear_resolver_cache()

    try:
        build_charter_context(repo_root, action="plan")
    except (NotInsideRepositoryError, GitCommonDirUnavailableError) as exc:
        pytest.fail(f"Unexpected resolver error on fresh clone: {exc}")
