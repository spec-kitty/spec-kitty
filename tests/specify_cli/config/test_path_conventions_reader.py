"""Reader tests for the project ``path_conventions`` override (#3016, WP01 T003).

Covers FR-001 (read), FR-007 (validate keys), FR-008 (fail-closed section), C-010 (deliverables
excluded), C-011 (reads the subkey, not the whole ``project:`` block).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.config.path_conventions import (
    PathConventionsConfigError,
    ProjectPathConventions,
    load_project_path_conventions,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(repo_root: Path, body: str) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(body, encoding="utf-8")


def test_absent_config_returns_empty(tmp_path: Path) -> None:
    assert load_project_path_conventions(tmp_path) == {}


def test_absent_section_returns_empty(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  slug: demo\n")
    assert load_project_path_conventions(tmp_path) == {}


def test_valid_subset_returned(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: apps/\n    tests: tests/\n")
    assert load_project_path_conventions(tmp_path) == {"workspace": "apps/", "tests": "tests/"}


def test_identity_fields_alongside_override_not_rejected(tmp_path: Path) -> None:
    """C-011: the reader reads only the ``path_conventions`` subkey, so the real ``project:`` identity
    fields (uuid/slug/node_id/build_id) coexist without being rejected."""
    _write_config(
        tmp_path,
        "project:\n  uuid: 01ABC\n  slug: my-project\n  node_id: node-7\n  build_id: b-42\n  path_conventions:\n    workspace: apps/\n",
    )
    assert load_project_path_conventions(tmp_path) == {"workspace": "apps/"}


def test_typo_key_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    worksapce: apps/\n")
    with pytest.raises(PathConventionsConfigError, match="worksapce"):
        load_project_path_conventions(tmp_path)


def test_deliverables_key_ignored(tmp_path: Path) -> None:
    """C-010: overriding the artifact-routed ``deliverables`` key is warned-and-ignored, never applied."""
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    workspace: apps/\n    deliverables: build/\n",
    )
    with pytest.warns(UserWarning, match="deliverables"):
        result = load_project_path_conventions(tmp_path)
    assert result == {"workspace": "apps/"}


def test_section_not_a_mapping_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions: not-a-mapping\n")
    with pytest.raises(PathConventionsConfigError, match="must be a mapping"):
        load_project_path_conventions(tmp_path)


def test_non_string_value_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: 123\n")
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_null_value_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace:\n")
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_corrupt_file_is_lenient(tmp_path: Path) -> None:
    """A whole-file-corrupt ``config.yaml`` returns ``{}`` (lenient), matching the co-resident section
    readers — fail-closed is scoped to the section shape, not the file."""
    _write_config(tmp_path, "project: [this: is, : broken yaml\n  path_conventions\n")
    assert load_project_path_conventions(tmp_path) == {}


def test_empty_string_value_raises(tmp_path: Path) -> None:
    """MAJOR (adversarial squad, fix #1): an empty-string value must be rejected, not silently accepted.

    ``Path("")`` collapses to the repo root under ``validate_mission_paths`` (which always exists), so
    an empty override silently defeats strict enforcement (SC-006/SC-007) instead of naming a missing
    directory. See the red-first proof in ``tests/agent/test_validators_unit.py``.
    """
    _write_config(tmp_path, 'project:\n  path_conventions:\n    workspace: ""\n')
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_blank_string_value_raises(tmp_path: Path) -> None:
    """A whitespace-only value is just as empty as ``""`` once ``.strip()``-ped — must also raise."""
    _write_config(tmp_path, 'project:\n  path_conventions:\n    workspace: "   "\n')
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_absolute_path_value_raises(tmp_path: Path) -> None:
    """MINOR (fix #2): an absolute-path value would target an out-of-repo directory that always exists
    (e.g. ``/tmp``), making the gate trivially pass — ``path_conventions`` values are repo-relative
    layout directories only."""
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: /tmp\n")
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_dotdot_traversal_value_raises(tmp_path: Path) -> None:
    """A ``..``-traversal value could walk the check outside the repo — reject it, same as an
    absolute path."""
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: ../elsewhere\n")
    with pytest.raises(PathConventionsConfigError, match="workspace"):
        load_project_path_conventions(tmp_path)


def test_relative_trailing_slash_value_still_accepted(tmp_path: Path) -> None:
    """Non-regression: a normal repo-relative value with a trailing slash (e.g. ``apps/``) must still be
    accepted — it is later normalized by ``normalize_path_token`` at the merge site, not here."""
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: apps/\n")
    assert load_project_path_conventions(tmp_path) == {"workspace": "apps/"}


def test_surrounding_whitespace_value_is_trimmed(tmp_path: Path) -> None:
    _write_config(tmp_path, 'project:\n  path_conventions:\n    workspace: "  apps  "\n')
    assert load_project_path_conventions(tmp_path) == {"workspace": "apps"}


# ---------------------------------------------------------------------------
# #7748 / #7566: per-mission-type sections (Mission path-conventions-per-type-01M7VRQM, WP01).
# A mapping value keyed by a mission-type id is a per-type section; string values keep the flat
# meaning above. The roster is injected so these tests never read packs.
# ---------------------------------------------------------------------------

_ROSTER = frozenset({"software-dev", "documentation", "plan", "research", "docs-audit"})


def _roster() -> frozenset[str]:
    return _ROSTER


def _load(repo_root: Path) -> ProjectPathConventions:
    return load_project_path_conventions(repo_root, mission_type_ids=_roster)


def test_per_type_section_is_read_beside_an_empty_flat_mapping(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      workspace: packs/\n")
    result = _load(tmp_path)
    assert result == {}
    assert result.per_type == {"software-dev": {"workspace": "packs/"}}


def test_per_type_value_wins_for_its_type_only(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    workspace: apps/\n    software-dev:\n      workspace: packs/\n",
    )
    result = _load(tmp_path)
    assert result == {"workspace": "apps/"}
    assert result.for_mission_type("software-dev") == {"workspace": "packs/"}
    assert result.for_mission_type("documentation") == {"workspace": "apps/"}
    assert result.for_mission_type(None) == {"workspace": "apps/"}


def test_per_type_merges_with_flat_key_by_key(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    tests: t/\n    software-dev:\n      workspace: packs/\n",
    )
    assert _load(tmp_path).for_mission_type("software-dev") == {"tests": "t/", "workspace": "packs/"}


def test_org_mission_type_in_roster_is_accepted(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    docs-audit:\n      documentation: handbook/\n")
    assert _load(tmp_path).for_mission_type("docs-audit") == {"documentation": "handbook/"}


def test_unknown_mission_type_section_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    softwre-dev:\n      workspace: x/\n")
    with pytest.raises(PathConventionsConfigError, match="softwre-dev") as excinfo:
        _load(tmp_path)
    assert "software-dev" in str(excinfo.value)


def test_unknown_key_inside_section_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      workspce: x/\n")
    with pytest.raises(PathConventionsConfigError, match=r"software-dev\.workspce"):
        _load(tmp_path)


@pytest.mark.parametrize("value", ["1", "null", "[src/]", "{a: b}"])
def test_non_string_value_inside_section_raises(tmp_path: Path, value: str) -> None:
    _write_config(tmp_path, f"project:\n  path_conventions:\n    software-dev:\n      workspace: {value}\n")
    with pytest.raises(PathConventionsConfigError, match=r"software-dev\.workspace"):
        _load(tmp_path)


@pytest.mark.parametrize("value", ['""', '"   "'])
def test_blank_value_inside_section_raises(tmp_path: Path, value: str) -> None:
    _write_config(tmp_path, f"project:\n  path_conventions:\n    software-dev:\n      workspace: {value}\n")
    with pytest.raises(PathConventionsConfigError, match="empty or blank"):
        _load(tmp_path)


@pytest.mark.parametrize("value", ["/abs/src", "../outside"])
def test_absolute_or_traversal_value_inside_section_raises(tmp_path: Path, value: str) -> None:
    _write_config(tmp_path, f"project:\n  path_conventions:\n    software-dev:\n      workspace: {value}\n")
    with pytest.raises(PathConventionsConfigError, match="repo-relative"):
        _load(tmp_path)


def test_deliverables_inside_section_is_warned_and_ignored(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    software-dev:\n      deliverables: out/\n      workspace: packs/\n",
    )
    with pytest.warns(UserWarning, match=r"software-dev\.deliverables"):
        result = _load(tmp_path)
    assert result.per_type == {"software-dev": {"workspace": "packs/"}}


def test_section_that_is_not_a_mapping_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      - src/\n")
    with pytest.raises(PathConventionsConfigError, match="software-dev"):
        _load(tmp_path)


def test_flat_only_config_never_reads_the_roster(tmp_path: Path) -> None:
    def _must_not_be_called() -> frozenset[str]:
        raise AssertionError("roster read for a flat-only config")

    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace: apps/\n")
    assert load_project_path_conventions(tmp_path, mission_type_ids=_must_not_be_called) == {"workspace": "apps/"}


def test_unreadable_roster_fails_closed(tmp_path: Path) -> None:
    def _broken() -> frozenset[str]:
        raise RuntimeError("bad pack")

    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      workspace: packs/\n")
    with pytest.raises(PathConventionsConfigError, match="bad pack"):
        load_project_path_conventions(tmp_path, mission_type_ids=_broken)


def test_section_values_are_trimmed(tmp_path: Path) -> None:
    _write_config(tmp_path, 'project:\n  path_conventions:\n    software-dev:\n      workspace: "  packs/ "\n')
    assert _load(tmp_path).for_mission_type("software-dev") == {"workspace": "packs/"}


def test_default_roster_is_the_layered_roster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.cli.commands.charter.mission_type as mission_type_cmd

    seen: list[Path] = []

    def _fake_roster(repo_root: Path) -> dict[str, object]:
        seen.append(repo_root)
        return {"software-dev": object()}

    monkeypatch.setattr(mission_type_cmd, "resolve_layered_roster", _fake_roster)
    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      workspace: packs/\n")
    assert load_project_path_conventions(tmp_path).for_mission_type("software-dev") == {"workspace": "packs/"}
    assert seen == [tmp_path]


# Review cycle 1 (WP01): ``documentation`` is both a mission-type id and a path key. The value's
# shape decides: a string is the flat key, a mapping is the per-type section. A YAML mapping holds a
# key once, so one config cannot carry both a flat ``documentation`` and a ``documentation`` section.


def test_documentation_section_alone_is_a_per_type_section(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    documentation:\n      workspace: handbook/\n")
    result = _load(tmp_path)
    assert result == {}
    assert result.for_mission_type("documentation") == {"workspace": "handbook/"}
    assert result.for_mission_type("software-dev") == {}


def test_documentation_section_beside_flat_keys(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    workspace: apps/\n    documentation:\n      workspace: handbook/\n      documentation: manual/\n",
    )
    result = _load(tmp_path)
    assert result == {"workspace": "apps/"}
    assert result.for_mission_type("documentation") == {"workspace": "handbook/", "documentation": "manual/"}
    assert result.for_mission_type("research") == {"workspace": "apps/"}


def test_flat_documentation_string_stays_the_flat_key(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    documentation: manual/\n")
    result = _load(tmp_path)
    assert result == {"documentation": "manual/"}
    assert result.per_type == {}


def test_mapping_under_a_path_key_that_is_no_mission_type_raises(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    workspace:\n      a: b\n")
    with pytest.raises(PathConventionsConfigError, match="'workspace'") as excinfo:
        _load(tmp_path)
    assert "per-type section" in str(excinfo.value)


def test_list_valued_section_of_a_known_type_names_the_mapping_rule(tmp_path: Path) -> None:
    _write_config(tmp_path, "project:\n  path_conventions:\n    software-dev:\n      - src/\n")
    with pytest.raises(PathConventionsConfigError, match=r"software-dev must be a mapping"):
        _load(tmp_path)


def test_deliverables_warning_points_at_the_caller_for_sections_and_flat(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "project:\n  path_conventions:\n    deliverables: out/\n    software-dev:\n      deliverables: out/\n",
    )
    with pytest.warns(UserWarning, match="deliverables") as record:
        _load(tmp_path)
    assert [Path(w.filename).name for w in record] == [Path(__file__).name, Path(__file__).name]
