"""Charter-pack cutover: stale lists, kind gates and ``[]`` resets (#3732, T062).

Each test builds an activation surface under ``tmp_path``, runs the step
(directly through :mod:`._charter_pack_cutover_resets`, or through the
migration's ``apply()``), and asserts the file, the report line and, where the
migration runs, that a second ``apply()`` changes 0 bytes with ``detect()`` False.
The released lists come from the frozen snapshot module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from kernel.clock import datetime
from ruamel.yaml import YAML

from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations._charter_pack_cutover_resets import ResetOutcome, apply_resets, plan_resets
from specify_cli.upgrade.migrations._charter_pack_cutover_snapshots import DEFAULT_SNAPSHOTS, MINIMAL_SNAPSHOTS
from specify_cli.upgrade.migrations.base import MigrationResult, MigrationStateUnreadableError
from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration

pytestmark = [pytest.mark.unit]

CONFIG = ".kittify/config.yaml"
CHARTER = ".kittify/charter/charter.yaml"
POINTER = f"charter: {CHARTER}\n"
EIGHT_KINDS = ["directives", "tactics", "styleguides", "toolguides", "paradigms", "procedures", "agent_profiles", "mission_step_contracts"]


def _write(project: Path, rel: str, text: str) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _block(key: str, ids: Any) -> str:
    if not ids:
        return f"{key}: []\n"
    return f"{key}:\n" + "".join(f"- {item}\n" for item in ids)


def _load(path: Path) -> Any:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}


def _report(result: MigrationResult) -> dict[str, list[str]]:
    report: dict[str, list[str]] = json.loads(result.changes_made[0])
    return report


def _digest(project: Path) -> dict[str, bytes]:
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


def _snapshot(key: str, size: int) -> list[str]:
    return sorted(next(s for s in DEFAULT_SNAPSHOTS[key] if len(s) == size))


def _apply_twice(project: Path) -> MigrationResult:
    """Apply as the runner does (record the migration), then prove the re-run is a no-op."""
    migration = CharterPackCutoverMigration()
    assert migration.detect(project) is True, "control: the fixture carries something to reset"
    first = migration.apply(project)
    assert first.success, first.errors
    _record(project)
    after_first = _digest(project)
    second = migration.apply(project)
    assert second.success
    assert _digest(project) == after_first
    assert migration.detect(project) is False
    return first


def _record(project: Path) -> None:
    metadata = ProjectMetadata.load(project / ".kittify")
    if metadata is None:
        metadata = ProjectMetadata(version="4.0.0rc6", initialized_at=datetime(2026, 1, 1), python_version="3.11", platform="t", platform_version="t")
    metadata.record_migration("charter_pack_cutover", "success")
    metadata.save(project / ".kittify")


# --------------------------------------------------------------------------- #
# Stale lists: every released default list per key resets
# --------------------------------------------------------------------------- #


_STALE_CASES = [pytest.param(key, sorted(snapshot), id=f"{key}-{len(snapshot)}") for key, snapshots in DEFAULT_SNAPSHOTS.items() for snapshot in snapshots]


@pytest.mark.parametrize(("key", "ids"), _STALE_CASES)
def test_every_released_default_list_resets(tmp_path: Path, key: str, ids: list[str]) -> None:
    _write(tmp_path, CONFIG, "vcs:\n  type: git\n" + _block(key, ids) + "mission_type_activations:\n- software-dev\n")
    report = _report(_apply_twice(tmp_path))
    data = _load(tmp_path / CONFIG)
    assert key not in data
    assert data == {"vcs": {"type": "git"}, "mission_type_activations": ["software-dev"]}
    assert report["reset"] == [f"{CONFIG}: {key} (matched a released default list; now absent, every built-in available)"]


def test_reset_is_order_insensitive_and_untouched_lines_are_byte_identical(tmp_path: Path) -> None:
    ids = list(reversed(_snapshot("activated_paradigms", 8)))
    head = "# operator comment\nvcs:\n  type: git  # keep me\n"
    tail = "mission_type_activations: [software-dev]\n"
    _write(tmp_path, CONFIG, head + _block("activated_paradigms", ids) + tail)
    _apply_twice(tmp_path)
    assert (tmp_path / CONFIG).read_text(encoding="utf-8") == head + tail


def test_directive_ids_compare_equal_to_stems(tmp_path: Path) -> None:
    ids = [f"DIRECTIVE_{stem[:3]}" if index % 2 else stem for index, stem in enumerate(_snapshot("activated_directives", 19))]
    _write(tmp_path, CONFIG, _block("activated_directives", ids))
    _apply_twice(tmp_path)
    assert "activated_directives" not in _load(tmp_path / CONFIG)


@pytest.mark.parametrize("variant", ["minus_one", "plus_one"])
def test_near_miss_is_kept_for_review(tmp_path: Path, variant: str) -> None:
    ids = _snapshot("activated_tactics", 95)
    ids = ids[1:] if variant == "minus_one" else [*ids, "my-custom-tactic"]
    _write(tmp_path, CONFIG, _block("activated_tactics", ids) + _block("activated_paradigms", _snapshot("activated_paradigms", 8)))
    report = _report(_apply_twice(tmp_path))
    assert sorted(_load(tmp_path / CONFIG)["activated_tactics"]) == sorted(ids)
    assert report["kept_for_review"] == [f"{CONFIG}: activated_tactics customised; not changed"]
    assert "activated_paradigms" not in _load(tmp_path / CONFIG), "control: the snapshot key beside it reset"


def test_kept_list_alone_never_selects_the_migration(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, _block("activated_tactics", ["my-custom-tactic"]))
    assert CharterPackCutoverMigration().detect(tmp_path) is False


# --------------------------------------------------------------------------- #
# Kind gates
# --------------------------------------------------------------------------- #


def test_default_kind_gate_resets(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, _block("activated_kinds", EIGHT_KINDS))
    report = _report(_apply_twice(tmp_path))
    assert (tmp_path / CONFIG).read_text(encoding="utf-8") == "{}\n", "removing every key leaves an empty mapping"
    assert report["reset"] == [f"{CONFIG}: activated_kinds (matched the released default kind gate; now absent)"]


def test_minimal_kind_gate_resets_with_a_warning_and_minimal_lists_are_kept(tmp_path: Path) -> None:
    directives = sorted(next(iter(MINIMAL_SNAPSHOTS["activated_directives"])))
    text = (
        _block("activated_kinds", ["tactics", "directives"]) + _block("activated_directives", directives) + _block("activated_tactics", ["acceptance-test-first"])
    )
    _write(tmp_path, CONFIG, text)
    result = _apply_twice(tmp_path)
    report = _report(result)
    data = _load(tmp_path / CONFIG)
    assert "activated_kinds" not in data
    assert data["activated_directives"] == directives and data["activated_tactics"] == ["acceptance-test-first"]
    assert report["reset"] == [f"{CONFIG}: activated_kinds [directives, tactics] (the released minimal kind gate; now absent)"]
    assert report["matches_minimal"] == [
        f"{CONFIG}: activated_directives matches preset minimal; not changed",
        f"{CONFIG}: activated_tactics matches preset minimal; not changed",
    ]
    defect = [w for w in result.warnings if "defect" in w]
    assert len(defect) == 1 and CONFIG in defect[0] and "minimal" in defect[0]
    assert result.manual_review_required


def test_other_kind_gate_is_kept(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, _block("activated_kinds", ["directives"]) + _block("activated_paradigms", _snapshot("activated_paradigms", 8)))
    report = _report(_apply_twice(tmp_path))
    assert _load(tmp_path / CONFIG)["activated_kinds"] == ["directives"]
    assert report["kept_for_review"] == [f"{CONFIG}: activated_kinds customised; not changed"]


# --------------------------------------------------------------------------- #
# [] lists
# --------------------------------------------------------------------------- #

_EMPTY_KEYS = [
    "activated_directives",
    "activated_tactics",
    "activated_styleguides",
    "activated_toolguides",
    "activated_paradigms",
    "activated_procedures",
    "activated_agent_profiles",
    "activated_mission_step_contracts",
    "activated_glossary_packs",
    "activated_skills",
    "activated_anti_patterns",
]


@pytest.mark.parametrize("key", _EMPTY_KEYS)
def test_empty_list_resets_with_restore_hint(tmp_path: Path, key: str) -> None:
    _write(tmp_path, CONFIG, f"{key}: []\nmission_type_activations: []\n")
    result = _apply_twice(tmp_path)
    data = _load(tmp_path / CONFIG)
    assert key not in data
    assert data == {"mission_type_activations": []}, "mission_type_activations: [] is never reset"
    (line,) = _report(result)["reset"]
    assert line.startswith(f"{CONFIG}: {key} was [] (nothing active); now absent (")
    (hint,) = [w for w in result.warnings if "To switch the kind off again" in w]
    assert hint.endswith(f"To switch the kind off again, set {key}: [] in {CONFIG}.")
    assert hint.startswith(f"{CONFIG}: {key} was []")


def test_empty_skills_hint_names_the_required_set(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, "activated_skills: []\nactivated_paradigms: []\n")
    reset = _report(_apply_twice(tmp_path))["reset"]
    assert reset == [
        f"{CONFIG}: activated_paradigms was [] (nothing active); now absent (all paradigms available)",
        f"{CONFIG}: activated_skills was [] (nothing active); now absent (only the skills your org packs require are in force)",
    ]


def test_mission_type_activations_is_never_reported(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, "mission_type_activations: []\n")
    assert plan_resets(tmp_path) == []
    assert CharterPackCutoverMigration().detect(tmp_path) is False


# --------------------------------------------------------------------------- #
# Surfaces: pointed charter.yaml and a leftover config.yaml mirror
# --------------------------------------------------------------------------- #


def test_pointed_charter_yaml_and_config_mirror_both_reset(tmp_path: Path) -> None:
    tactics = _snapshot("activated_tactics", 94)
    charter_text = "schema_version: 2.0.0\ngovernance: {}\n" + _block("activated_tactics", tactics) + _block("activated_kinds", EIGHT_KINDS)
    _write(tmp_path, CHARTER, charter_text)
    _write(tmp_path, CONFIG, POINTER + _block("activated_toolguides", _snapshot("activated_toolguides", 9)))
    report = _report(_apply_twice(tmp_path))
    assert _load(tmp_path / CHARTER) == {"schema_version": "2.0.0", "governance": {}}
    assert _load(tmp_path / CONFIG) == {"charter": CHARTER}
    assert report["reset"] == [
        f"{CHARTER}: activated_kinds (matched the released default kind gate; now absent)",
        f"{CHARTER}: activated_tactics (matched a released default list; now absent, every built-in available)",
        f"{CONFIG}: activated_toolguides (matched a released default list; now absent, every built-in available)",
    ]


def test_dangling_pointer_still_resets_the_config_mirror(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, POINTER + "activated_paradigms: []\n")
    actions = plan_resets(tmp_path)
    assert [a.key for a in actions] == ["activated_paradigms"]
    fragment = apply_resets(tmp_path, actions, dry_run=False)
    assert not fragment.errors
    assert _load(tmp_path / CONFIG) == {"charter": CHARTER}


def test_malformed_yaml_raises_unreadable(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, "activated_tactics: [unclosed\n")
    with pytest.raises(MigrationStateUnreadableError, match=r"\.kittify/config\.yaml could not be read"):
        plan_resets(tmp_path)


def test_unwritable_surface_is_a_report_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, CONFIG, "activated_paradigms: []\n")

    def refuse(*_args: object, **_kwargs: object) -> bool:
        raise OSError("read-only file system")

    monkeypatch.setattr("charter.activation.charter_yaml_io.apply_yaml_write", refuse)
    fragment = apply_resets(tmp_path, plan_resets(tmp_path), dry_run=False)
    assert fragment.errors == [f"{CONFIG} could not be written (read-only file system); fix the file, then run `spec-kitty upgrade` again"]


@pytest.mark.parametrize(("text", "line"), [("activated_tactics: none\n", "is not a list"), ("activated_tactics: [1, 2]\n", "holds a non-string id")])
def test_odd_values_are_kept_for_review(tmp_path: Path, text: str, line: str) -> None:
    _write(tmp_path, CONFIG, text)
    (action,) = plan_resets(tmp_path)
    assert action.outcome is ResetOutcome.KEPT_FOR_REVIEW and line in action.line


def test_no_config_means_nothing_to_plan(tmp_path: Path) -> None:
    assert plan_resets(tmp_path) == []


# --------------------------------------------------------------------------- #
# Dry run, first application only
# --------------------------------------------------------------------------- #


def test_dry_run_reports_the_same_lines_and_writes_nothing(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, _block("activated_kinds", EIGHT_KINDS) + "activated_glossary_packs: []\n")
    before = _digest(tmp_path)
    dry = CharterPackCutoverMigration().apply(tmp_path, dry_run=True)
    assert _digest(tmp_path) == before
    real = CharterPackCutoverMigration().apply(tmp_path)
    assert _report(dry) == _report(real)
    assert all(line.startswith("Would ") for line in dry.changes_made[1:])
    assert all(line.startswith("Reset ") for line in real.changes_made[1:])


def test_recorded_migration_never_resets_a_deliberate_empty_list(tmp_path: Path) -> None:
    """Structural re-selection (legacy key back) after the first application keeps a post-cutover []."""
    _write(tmp_path, CONFIG, "activated_paradigms: []\norganisation_packs:\n- name: acme\n  path: org/acme\n  source: local_path\n")
    _record(tmp_path)
    migration = CharterPackCutoverMigration()
    assert migration.is_first_application(tmp_path) is False
    assert migration.structural_detect(tmp_path) is True, "control: the legacy key re-selects the migration"
    report = _report(migration.apply(tmp_path))
    assert report["reset"] == []
    assert _load(tmp_path / CONFIG)["activated_paradigms"] == []
    assert "organisation_packs" not in _load(tmp_path / CONFIG), "control: the structural row still ran"
    assert migration.detect(tmp_path) is False


def test_unrecorded_migration_resets_on_first_application(tmp_path: Path) -> None:
    _write(tmp_path, CONFIG, "activated_paradigms: []\n")
    assert CharterPackCutoverMigration().is_first_application(tmp_path) is True
    assert _report(CharterPackCutoverMigration().apply(tmp_path))["reset"]
