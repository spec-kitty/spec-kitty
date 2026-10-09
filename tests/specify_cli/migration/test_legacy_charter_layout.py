"""The cheap legacy charter-layout predicate (FR-011 / FR-012, #3732, T060)."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import pytest

from specify_cli.migration import legacy_charter_layout as layout
from specify_cli.migration.legacy_charter_layout import (
    UNREADABLE_CONFIG,
    UNREADABLE_GOVERNANCE_FILE,
    UNREADABLE_PROJECT_ROOT,
    detect_legacy_charter_layout,
    is_convertible_organisation_pack,
)

# The finding names are a stable contract (the CLI gate names them); spelled
# here as literals so a rename in the module reds this file.
LEGACY_PROJECT_ROOT = "legacy_project_root"
LEGACY_GOVERNANCE_FILE = "legacy_governance_file"
LEGACY_ORG_PACKS_KEY = "legacy_org_packs_key"
LEGACY_ORGANISATION_PACKS_KEY = "legacy_organisation_packs_key"
LEGACY_GOVERNANCE_SELECTION_KEY = "legacy_governance_selection_key"
LEGACY_TRACKER_OWNERSHIP_KEY = "legacy_tracker_ownership_key"

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CANONICAL_CONFIG = """\
# the doctrine word in a comment is not a key
charter_packs:
  org:
    packs:
    - name: acme
      local_path: packs/doctrine-foo
"""


def _project(tmp_path: Path, config: str | None = None) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    if config is not None:
        (kittify / "config.yaml").write_text(config, encoding="utf-8")
    return tmp_path


def test_clean_project_has_no_findings(tmp_path: Path) -> None:
    assert detect_legacy_charter_layout(_project(tmp_path, "vcs:\n  type: git\n")) == ()


def test_project_without_kittify_has_no_findings(tmp_path: Path) -> None:
    assert detect_legacy_charter_layout(tmp_path) == ()


def test_canonical_layout_with_the_word_in_comments_and_values_has_no_findings(tmp_path: Path) -> None:
    """Positive control: the substring prefilter hits, the parse finds nothing legacy."""
    project = _project(tmp_path, _CANONICAL_CONFIG)
    (project / ".kittify" / "charter-packs").mkdir()
    assert detect_legacy_charter_layout(project) == ()


def test_legacy_project_root(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / ".kittify" / "doctrine").mkdir()
    assert detect_legacy_charter_layout(project) == (LEGACY_PROJECT_ROOT,)


def test_legacy_project_root_symlink(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "elsewhere").mkdir()
    (project / ".kittify" / "doctrine").symlink_to(project / "elsewhere")
    assert detect_legacy_charter_layout(project) == (LEGACY_PROJECT_ROOT,)


def test_legacy_governance_file(tmp_path: Path) -> None:
    project = _project(tmp_path)
    charter = project / ".kittify" / "charter"
    charter.mkdir()
    (charter / "governance.yaml").write_text("doctrine:\n  selected_directives: [X]\n", encoding="utf-8")
    assert detect_legacy_charter_layout(project) == (LEGACY_GOVERNANCE_FILE,)


def test_canonical_governance_file_is_not_a_finding(tmp_path: Path) -> None:
    project = _project(tmp_path)
    charter = project / ".kittify" / "charter"
    charter.mkdir()
    (charter / "governance.yaml").write_text("charter:\n  selected_directives: [doctrine-x]\n", encoding="utf-8")
    assert detect_legacy_charter_layout(project) == ()


def test_unreadable_governance_file(tmp_path: Path) -> None:
    project = _project(tmp_path)
    charter = project / ".kittify" / "charter"
    charter.mkdir()
    (charter / "governance.yaml").write_text("doctrine: [unclosed\n", encoding="utf-8")
    assert detect_legacy_charter_layout(project) == (UNREADABLE_GOVERNANCE_FILE,)


@pytest.mark.parametrize(
    ("config", "finding"),
    [
        ("doctrine:\n  org:\n    packs:\n    - name: a\n      local_path: a\n", LEGACY_ORG_PACKS_KEY),
        ("doctrine:\n  org:\n    local_path: org-packs\n", LEGACY_ORG_PACKS_KEY),
        ("organisation_packs:\n- name: a\n  path: a\n", LEGACY_ORGANISATION_PACKS_KEY),
        ("governance:\n  doctrine:\n    selected_directives: [X]\n", LEGACY_GOVERNANCE_SELECTION_KEY),
        ("tracker:\n  doctrine:\n    mode: external_authoritative\n", LEGACY_TRACKER_OWNERSHIP_KEY),
    ],
)
def test_each_config_finding(tmp_path: Path, config: str, finding: str) -> None:
    assert detect_legacy_charter_layout(_project(tmp_path, config)) == (finding,)


def test_config_findings_are_reported_cheapest_first(tmp_path: Path) -> None:
    config = "tracker:\n  doctrine: {}\ngovernance:\n  doctrine: {}\norganisation_packs:\n- name: a\n  path: a\ndoctrine:\n  org:\n    packs: []\n"
    project = _project(tmp_path, config)
    (project / ".kittify" / "doctrine").mkdir()
    findings = detect_legacy_charter_layout(project)
    assert findings == (
        LEGACY_PROJECT_ROOT,
        LEGACY_ORG_PACKS_KEY,
        LEGACY_ORGANISATION_PACKS_KEY,
        LEGACY_GOVERNANCE_SELECTION_KEY,
        LEGACY_TRACKER_OWNERSHIP_KEY,
    )
    assert list(findings) == [f for f in layout._STRUCTURAL_FINDINGS if f in findings]


def test_doctrine_section_without_an_org_pack_form_is_not_a_finding(tmp_path: Path) -> None:
    assert detect_legacy_charter_layout(_project(tmp_path, "doctrine:\n  org:\n    notes: x\n  other: 1\n")) == ()


def test_unconvertible_organisation_packs_alone_is_not_a_finding(tmp_path: Path) -> None:
    """Entries the migration keeps for review must not re-select it forever."""
    config = "organisation_packs:\n- name: a\n  path: a\n  source: git\n"
    assert detect_legacy_charter_layout(_project(tmp_path, config)) == ()


def test_unreadable_config(tmp_path: Path) -> None:
    project = _project(tmp_path, "doctrine: [unclosed\n")
    assert detect_legacy_charter_layout(project) == (UNREADABLE_CONFIG,)


def test_config_that_cannot_be_read_is_a_finding(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / ".kittify" / "config.yaml").mkdir()  # reading a directory raises OSError
    assert detect_legacy_charter_layout(project) == (UNREADABLE_CONFIG,)


def test_non_mapping_config_is_not_a_finding(tmp_path: Path) -> None:
    assert detect_legacy_charter_layout(_project(tmp_path, "- doctrine\n- organisation_packs\n")) == ()


def test_charter_yaml_is_never_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path, "doctrine:\n  org:\n    packs: []\n")
    charter = project / ".kittify" / "charter"
    charter.mkdir()
    charter_yaml = charter / "charter.yaml"
    charter_yaml.write_text("governance:\n  doctrine: {}\n", encoding="utf-8")
    real_read_bytes = Path.read_bytes

    def guarded_read_bytes(self: Path) -> bytes:
        assert self.name != "charter.yaml", "the predicate must never read charter.yaml"
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: pytest.fail(f"unexpected read_text of {self}"))
    assert detect_legacy_charter_layout(project) == (LEGACY_ORG_PACKS_KEY,)


def test_predicate_module_imports_nothing_from_charter() -> None:
    tree = ast.parse(Path(layout.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert not {name for name in imported if name == "charter" or name.startswith("charter.")}
    assert "kernel.charter_pack_paths" in imported  # control: the scan sees imports


@pytest.mark.parametrize(
    ("entry", "convertible"),
    [
        ({"name": "a", "path": "p"}, True),
        ({"name": "a", "path": "p", "source": "local_path"}, True),
        ({"name": "a", "path": "p", "source": "git"}, False),
        ({"name": "a"}, False),
        ("a", False),
    ],
)
def test_is_convertible_organisation_pack(entry: object, convertible: bool) -> None:
    assert is_convertible_organisation_pack(entry) is convertible


# --------------------------------------------------------------------------- #
# Totality under EACCES (review cycle 1, finding 4): on Python 3.11
# Path.is_dir()/is_symlink() re-raise PermissionError, so every probe is guarded.
# --------------------------------------------------------------------------- #


def test_unreadable_project_root_is_a_finding_not_a_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path, "vcs:\n  type: git\n")
    real_lstat = os.lstat
    legacy = project / ".kittify" / "doctrine"

    def lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if Path(str(path)) == legacy:
            raise PermissionError(13, "Permission denied", str(path))
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(layout.os, "lstat", lstat)
    assert detect_legacy_charter_layout(project) == (UNREADABLE_PROJECT_ROOT,)


@pytest.mark.parametrize(
    ("filename", "finding"),
    [("config.yaml", UNREADABLE_CONFIG), ("charter/governance.yaml", UNREADABLE_GOVERNANCE_FILE)],
)
def test_permission_denied_read_is_a_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str, finding: str) -> None:
    project = _project(tmp_path, "vcs:\n  type: git\n")
    denied = project / ".kittify" / filename
    real_read_bytes = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self == denied:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert detect_legacy_charter_layout(project) == (finding,)


def test_every_probe_denied_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """EACCES on every stat and read under ``.kittify`` (the reviewer's reproduction, widened)."""
    project = _project(tmp_path, "doctrine:\n  org:\n    packs: []\n")
    kittify = project / ".kittify"
    real_lstat, real_stat, real_read_bytes = os.lstat, Path.stat, Path.read_bytes

    def under_kittify(path: Any) -> bool:
        return isinstance(path, (str, os.PathLike)) and Path(path).is_relative_to(kittify)

    def lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if under_kittify(path):
            raise PermissionError(13, "Permission denied", str(path))
        return real_lstat(path, *args, **kwargs)

    def path_stat(self: Path, *args: Any, **kwargs: Any) -> os.stat_result:
        if under_kittify(self):
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, *args, **kwargs)

    def read_bytes(self: Path) -> bytes:
        if under_kittify(self):
            raise PermissionError(13, "Permission denied", str(self))
        return real_read_bytes(self)

    monkeypatch.setattr(layout.os, "lstat", lstat)
    monkeypatch.setattr(Path, "stat", path_stat)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert detect_legacy_charter_layout(project) == (UNREADABLE_PROJECT_ROOT, UNREADABLE_GOVERNANCE_FILE, UNREADABLE_CONFIG)
