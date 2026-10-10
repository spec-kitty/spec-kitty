"""Tests for ``load_requirement_kinds`` tier walk (#5956 loader seam, #6006 chain authority)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.manifest_loader import (
    RequirementKindsSchemaError,
    clear_cache,
    load_requirement_kinds,
)
from charter.offering.missions.repository import MalformedManifestError
from charter.offering.missions.requirement_kinds import default_requirement_kinds
from kernel.charter_pack_paths import project_pack_root

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_TYPE = "research"


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    clear_cache()


def _config(repo: Path, packs: list[tuple[str, Path]]) -> None:
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, path in packs:
        lines += [f"      - name: {name}", f"        local_path: {path}"]
    (repo / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _body(prefix: str, label: str, term: str, must: bool) -> str:
    return (
        f'schema_version: "1"\nmission_type: {_TYPE}\nkinds:\n'
        f"  - prefix: {prefix}\n    label: {label}\n    glossary_term: {term}\n    must_map_to_wp: {str(must).lower()}\n"
    )


def _put(root: Path, text: str) -> Path:
    path = root / "missions" / _TYPE / "requirement-kinds.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _two_packs(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    p1, p2 = tmp_path / "p1", tmp_path / "p2"
    p1.mkdir()
    p2.mkdir()
    _config(repo, [("p1", p1), ("p2", p2)])
    return repo, p1, p2


def test_absence_everywhere_returns_default_constant(tmp_path: Path) -> None:
    repo, _, _ = _two_packs(tmp_path)
    assert load_requirement_kinds(_TYPE, repo) == default_requirement_kinds(_TYPE)


def test_no_config_at_all_returns_default(tmp_path: Path) -> None:
    assert load_requirement_kinds(_TYPE, tmp_path) == default_requirement_kinds(_TYPE)


@pytest.mark.regression
def test_pack2_file_overrides_pack1_whole_file(tmp_path: Path) -> None:
    repo, p1, p2 = _two_packs(tmp_path)
    _put(p1, _body("AA", "Alpha", "alpha term", True))
    _put(p2, _body("BB", "Beta", "beta term", False))
    kind = load_requirement_kinds(_TYPE, repo).kinds[0]
    assert (kind.prefix, kind.label, kind.glossary_term, kind.must_map_to_wp) == ("BB", "Beta", "beta term", False)
    assert len(load_requirement_kinds(_TYPE, repo).kinds) == 1  # replaced, not merged


@pytest.mark.regression
def test_pack1_file_survives_when_pack2_has_none(tmp_path: Path) -> None:
    repo, p1, _ = _two_packs(tmp_path)
    _put(p1, _body("AA", "Alpha", "alpha term", True))
    assert load_requirement_kinds(_TYPE, repo).kinds[0].prefix == "AA"


@pytest.mark.regression
def test_project_file_overrides_both_packs(tmp_path: Path) -> None:
    repo, p1, p2 = _two_packs(tmp_path)
    _put(p1, _body("AA", "Alpha", "alpha term", True))
    _put(p2, _body("BB", "Beta", "beta term", False))
    _put(project_pack_root(repo), _body("PP", "Project", "project term", True))
    kinds = load_requirement_kinds(_TYPE, repo).kinds
    assert [(k.prefix, k.label, k.glossary_term) for k in kinds] == [("PP", "Project", "project term")]


@pytest.mark.regression
def test_corrupted_file_refuses_while_valid_sibling_loads(tmp_path: Path) -> None:
    repo, p1, p2 = _two_packs(tmp_path)
    good = _body("AA", "Alpha", "alpha term", True)
    _put(p1, good)
    assert load_requirement_kinds(_TYPE, repo).kinds[0].prefix == "AA"  # positive control
    clear_cache()
    _put(p2, good.replace("label:", "lable:"))  # one field corrupted
    with pytest.raises(RequirementKindsSchemaError) as info:
        load_requirement_kinds(_TYPE, repo)
    assert info.value.mission_type == _TYPE
    assert "lable" in str(info.value)


def test_unparseable_and_non_mapping_files_refuse(tmp_path: Path) -> None:
    repo, p1, _ = _two_packs(tmp_path)
    _put(p1, "- just\n- a list\n")
    with pytest.raises(MalformedManifestError):
        load_requirement_kinds(_TYPE, repo)
    clear_cache()
    _put(p1, "a: [unclosed\n")
    with pytest.raises(MalformedManifestError):
        load_requirement_kinds(_TYPE, repo)


def test_invalid_project_file_refuses_not_falls_through(tmp_path: Path) -> None:
    repo, p1, _ = _two_packs(tmp_path)
    _put(p1, _body("AA", "Alpha", "alpha term", True))
    _put(project_pack_root(repo), "mission_type: research\nkinds: []\n")
    with pytest.raises(RequirementKindsSchemaError):
        load_requirement_kinds(_TYPE, repo)


@pytest.mark.regression
def test_declared_but_missing_pack_refuses(tmp_path: Path) -> None:
    repo, p1, p2 = _two_packs(tmp_path)
    _put(p1, _body("AA", "Alpha", "alpha term", True))
    p2.rmdir()
    with pytest.raises(ValueError, match="p2"):
        load_requirement_kinds(_TYPE, repo)


def test_cache_does_not_leak_across_projects(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _put(project_pack_root(a), _body("PP", "Project", "project term", True))
    assert load_requirement_kinds(_TYPE, a).kinds[0].prefix == "PP"
    assert load_requirement_kinds(_TYPE, b) == default_requirement_kinds(_TYPE)
    assert load_requirement_kinds(_TYPE, a) is load_requirement_kinds(_TYPE, a)
