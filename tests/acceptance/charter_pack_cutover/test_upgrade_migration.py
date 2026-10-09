"""The one cutover upgrade migration: FR-012, NFR-001, NFR-004, US2, SC-002 (#3732, T005).

Every test drives ``spec-kitty upgrade`` through the CLI and asserts on its
``--json`` result (``migration_reports.charter_pack_cutover``, contracts/upgrade-migration.md)
or on the files it leaves, never on private migration functions.

FR-012 inventory row -> test(s)

=========================================  ==================================================
Org packs list                             test_fr012_legacy_keys_rewritten[org_packs]
Single-pack legacy form                    test_fr012_legacy_keys_rewritten[single_pack]
Flat org list                              test_fr012_legacy_keys_rewritten[organisation_packs]
Governance selection                       test_fr012_legacy_keys_rewritten[governance_*]
Tracker ownership                          test_fr012_legacy_keys_rewritten[tracker]
Interview answers                          test_fr012_legacy_keys_rewritten[answers]
Activation entry key                       test_fr012_doctrine_pack_id_renamed
Project layer                              test_fr012_project_root_moved, test_fr012_collision_refuses_and_moves_nothing
Synthesis manifest / Provenance sidecars   test_fr012_path_references_rewritten
Pack-skill manifest / Ignore rules         test_fr012_path_references_rewritten
Stale activation lists / Stale kind gate   test_fr012_stale_list_reset[*]
Released `minimal` kind gate               test_fr012_minimal_kind_gate_removed_lists_reported
Normalizer empty lists                     test_fr012_normalizer_empty_lists_reset_and_reported
Installed skills                           test_fr012_installed_removed_skills
Customised lists, `minimal`-equal lists    test_fr012_near_miss_and_customised_kept_and_reported
=========================================  ==================================================
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ._effective_set import ALL_BUILTIN, builtin_inventory, effective_set, expand
from ._requirements import REPO_ROOT
from ._support import active_charter, covers, describe, git, git_init_commit, load_yaml, pending_until, read_json_output, run_cli, tree_digest
from .legacy_fixtures import (
    COLLISION_PATH,
    EDITED_SKILL,
    EXPECTED_RELATION,
    LANE_LEGACY_LAYER,
    MANIFESTED_SKILL,
    NFR001_FIXTURES,
    NORMALIZER_RESET_KEYS,
    ORG_PACK_DIR,
    STALE_FIXTURES,
    STALE_KEYS_KEPT,
    UNMANIFESTED_EQUAL_SKILL,
    USER_PACK_DIR,
    build_lane_project,
    UpgradedTemplate,
    project_from_template,
    upgraded_copy,
    snapshot_lists,
    write_text,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

CUTOVER_ID = "charter_pack_cutover"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "charter_pack_cutover" / "golden_before"
DEFAULT_PRESET = REPO_ROOT / "packs" / "built-in" / "presets" / "default.yaml"
REPORT_KEYS = ("moved", "rewritten", "reset", "kept_for_review", "matches_minimal", "skills_removed", "skills_kept", "errors")


def first_upgrade(name: str, tmp_path: Path) -> tuple[Path, UpgradedTemplate, dict[str, Any]]:
    """A private copy of fixture *name* after its first ``upgrade --json`` (run once per session)."""
    project, outcome = upgraded_copy(name, tmp_path / name)
    assert isinstance(outcome.payload, dict), f"exit={outcome.exit_code}\n{outcome.output}"
    return project, outcome, outcome.payload


def upgrade(project: Path, *flags: str) -> tuple[Result, dict[str, Any]]:
    result = run_cli(["upgrade", "--yes", "--json", "--no-worktrees", *flags], project)
    payload = read_json_output(result)
    assert isinstance(payload, dict), describe(result)
    return result, payload


def cutover_report(payload: dict[str, Any]) -> dict[str, list[str]]:
    report: dict[str, list[str]] = payload["migration_reports"][CUTOVER_ID]
    assert set(REPORT_KEYS) <= set(report), sorted(report)
    return report


def report_text(report: dict[str, list[str]], key: str) -> str:
    return "\n".join(report[key])


def config(project: Path) -> dict[str, Any]:
    data = load_yaml(project / ".kittify" / "config.yaml")
    return data if isinstance(data, dict) else {}


def charter_yaml(project: Path) -> dict[str, Any]:
    data = load_yaml(project / ".kittify" / "charter" / "charter.yaml")
    return data if isinstance(data, dict) else {}


def build(name: str, tmp_path: Path) -> Path:
    return project_from_template(name, tmp_path / name)


def cutover_migration() -> Any:
    """The cutover migration instance, located by its id (imported lazily)."""
    package = importlib.import_module("specify_cli.upgrade.migrations")
    for info in pkgutil.iter_modules(package.__path__):
        if "charter_pack_cutover" not in info.name:
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        for value in vars(module).values():
            if isinstance(value, type) and getattr(value, "migration_id", None) == CUTOVER_ID:
                return value()
    raise LookupError("no migration with id charter_pack_cutover")


# --------------------------------------------------------------------------------------
# Ordering and neutralised migrations (WP10)
# --------------------------------------------------------------------------------------


@covers("FR-012")
def test_fr012_cutover_runs_first(tmp_path: Path) -> None:
    project = build("legacy_keys_only", tmp_path)
    result = run_cli(["upgrade", "--dry-run", "--json"], project)
    assert result.exit_code == 0, describe(result)
    pending = [m["migration_id"] for m in read_json_output(result)["pending_migrations"]]
    assert pending, "control: the legacy fixture has pending migrations"
    assert pending[0] == CUTOVER_ID, pending


@covers("FR-012", "US2-6")
def test_fr012_rc35_and_normalizer_recorded_skipped(tmp_path: Path) -> None:
    project = build("pre_rc35", tmp_path)
    result, payload = upgrade(project)
    assert result.exit_code == 0, describe(result)
    skipped = set(payload["migrations_skipped"])
    assert {"3.2.0rc35_default_charter_pack", "normalize_activation_absence"} <= skipped, sorted(skipped)
    metadata = (project / ".kittify" / "metadata.yaml").read_text(encoding="utf-8")
    assert "3.2.0rc35_default_charter_pack" in metadata and "normalize_activation_absence" in metadata
    assert "activated_tactics" not in active_charter(project), "the rc35 copy of default.yaml was written"


# --------------------------------------------------------------------------------------
# Keys, project root and path references (WP11)
# --------------------------------------------------------------------------------------


def _org_packs_row(tmp_path: Path) -> None:
    project = build("legacy_keys_only", tmp_path)
    upgrade(project)
    data = config(project)
    assert "doctrine" not in data
    assert data["charter_packs"]["org"]["packs"] == [{"name": "acme", "local_path": ORG_PACK_DIR}]


def _single_pack_row(tmp_path: Path) -> None:
    project = build("single_pack_legacy_form", tmp_path)
    upgrade(project)
    data = config(project)
    assert "doctrine" not in data
    (pack,) = data["charter_packs"]["org"]["packs"]
    assert pack["name"] != "default" and pack["local_path"] == "org-packs" and pack["subdir"] == "acme"


def _organisation_packs_row(tmp_path: Path) -> None:
    project = build("organisation_packs", tmp_path)
    upgrade(project)
    data = config(project)
    assert "organisation_packs" not in data
    assert [p["name"] for p in data["charter_packs"]["org"]["packs"]] == ["acme"]


def _governance_config_row(tmp_path: Path) -> None:
    project = build("legacy_keys_only", tmp_path)
    upgrade(project)
    governance = config(project)["governance"]
    assert "doctrine" not in governance
    assert governance["charter"]["selected_directives"] == ["003-decision-documentation-requirement"]


def _governance_charter_yaml_row(tmp_path: Path) -> None:
    project = build("governance_doctrine_in_charter_yaml", tmp_path)
    upgrade(project)
    governance = charter_yaml(project)["governance"]
    assert "doctrine" not in governance and governance["charter"]["selected_directives"]


def _governance_standalone_row(tmp_path: Path) -> None:
    project = build("standalone_governance_yaml", tmp_path)
    upgrade(project)
    legacy = project / ".kittify" / "charter" / "governance.yaml"
    assert not legacy.exists() or "doctrine" not in (load_yaml(legacy) or {})
    texts = [p.read_text(encoding="utf-8") for p in (project / ".kittify").rglob("*.yaml")]
    assert any("003-decision-documentation-requirement" in t for t in texts), "the selection was lost"


def _tracker_row(tmp_path: Path) -> None:
    project = build("tracker_doctrine_key", tmp_path)
    upgrade(project)
    tracker = config(project)["tracker"]
    assert "doctrine" not in tracker and tracker["ownership"]["mode"] == "external_authoritative"


def _answers_row(tmp_path: Path) -> None:
    project = build("answers_doctrine_key", tmp_path)
    upgrade(project)
    answers = load_yaml(project / ".kittify" / "charter" / "interview" / "answers.yaml")
    assert "doctrine" not in answers and "DIRECTIVE_003" in json.dumps(answers)


def _both_present_row(tmp_path: Path) -> None:
    project = build("legacy_keys_only", tmp_path)
    data = config(project)
    data["charter_packs"] = {"org": {"packs": [{"name": "canonical", "local_path": ORG_PACK_DIR}]}}
    from .legacy_fixtures import finish

    finish(project, data)
    _, payload = upgrade(project)
    after = config(project)
    assert "doctrine" not in after and [p["name"] for p in after["charter_packs"]["org"]["packs"]] == ["canonical"]
    assert "doctrine.org.packs" in report_text(cutover_report(payload), "rewritten")


_KEY_ROWS = {
    "org_packs": _org_packs_row,
    "single_pack": _single_pack_row,
    "organisation_packs": _organisation_packs_row,
    "governance_config": _governance_config_row,
    "governance_charter_yaml": _governance_charter_yaml_row,
    "governance_standalone": _governance_standalone_row,
    "tracker": _tracker_row,
    "answers": _answers_row,
    "canonical_and_legacy_both_present": _both_present_row,
}


@covers(
    "FR-012",
    "OD-4",
    "INV:Org packs list",
    "INV:Single-pack legacy form",
    "INV:Flat org list",
    "INV:Governance selection",
    "INV:Tracker ownership",
    "INV:Interview answers",
    "EC:Canonical and legacy config keys both present",
)
@pytest.mark.parametrize("row", list(_KEY_ROWS))
def test_fr012_legacy_keys_rewritten(row: str, tmp_path: Path) -> None:
    _KEY_ROWS[row](tmp_path)


@covers("FR-012", "OD-1", "INV:Activation entry key")
def test_fr012_doctrine_pack_id_renamed(tmp_path: Path) -> None:
    project = build("doctrine_pack_id_activations", tmp_path)
    assert "doctrine_pack_id" in charter_yaml(project)["activations"][0]  # control
    upgrade(project)
    (entry,) = charter_yaml(project)["activations"]
    assert "doctrine_pack_id" not in entry and entry["charter_pack_id"] == "acme"


@covers("FR-012", "US2-1", "INV:Project layer", "EC:Uncommitted edits in moved or rewritten files")
def test_fr012_project_root_moved(tmp_path: Path) -> None:
    project = build("legacy_directory_only", tmp_path)
    legacy = project / ".kittify" / "doctrine"
    files = sorted(p.relative_to(legacy).as_posix() for p in legacy.rglob("*") if p.is_file())
    edited = legacy / "directive" / "001-mission-type-scope-directive.directive.yaml"
    edited.write_text(edited.read_text(encoding="utf-8") + "# uncommitted operator edit\n", encoding="utf-8")
    result, payload = upgrade(project)
    assert result.exit_code == 0, describe(result)
    new_root = project / ".kittify" / "charter-packs"
    assert not legacy.exists()
    assert sorted(p.relative_to(new_root).as_posix() for p in new_root.rglob("*") if p.is_file()) == files
    assert (new_root / "directive" / edited.name).read_text(encoding="utf-8").endswith("# uncommitted operator edit\n")
    assert len(cutover_report(payload)["moved"]) == len(files)


@covers("FR-012", "EC:Both project roots present")
def test_fr012_collision_refuses_and_moves_nothing(tmp_path: Path) -> None:
    project = build("both_roots_collision", tmp_path)
    before = tree_digest(project)
    result, payload = upgrade(project)
    assert result.exit_code != 0, describe(result)
    assert COLLISION_PATH in report_text(cutover_report(payload), "errors")
    assert tree_digest(project) == before
    # Control: disjoint roots move everything.
    disjoint = build("both_roots_disjoint", tmp_path)
    ok, _ = upgrade(disjoint)
    assert ok.exit_code == 0, describe(ok)
    assert not (disjoint / ".kittify" / "doctrine").exists()
    assert (disjoint / ".kittify" / "charter-packs" / "overlays" / "extra.yaml").is_file()
    assert (disjoint / ".kittify" / "charter-packs" / "graph.yaml").is_file()


_GITIGNORE_RULES = ".kittify/doctrine/**\n!.kittify/doctrine/graph.yaml\n"


@covers("FR-012", "INV:Synthesis manifest", "INV:Provenance sidecars", "INV:Pack-skill manifest", "INV:Ignore rules")
def test_fr012_path_references_rewritten(tmp_path: Path) -> None:
    project = build("synthesized_with_provenance", tmp_path)
    write_text(project / ".gitignore", _GITIGNORE_RULES)
    git_init_commit(project, "fixture: ignore rules")
    upgrade(project)
    manifest = (project / ".kittify" / "charter" / "synthesis-manifest.yaml").read_text(encoding="utf-8")
    assert ".kittify/charter-packs/" in manifest and ".kittify/doctrine" not in manifest
    provenance = "".join(p.read_text(encoding="utf-8") for p in (project / ".kittify" / "charter" / "provenance").glob("*.yaml"))
    assert ".kittify/doctrine" not in provenance
    ignore = (project / ".gitignore").read_text(encoding="utf-8")
    assert ".kittify/charter-packs/**" in ignore and "!.kittify/charter-packs/graph.yaml" in ignore and ".kittify/doctrine" not in ignore
    skills = build("project_pack_skills", tmp_path)
    upgrade(skills)
    entries = json.loads((skills / ".kittify" / "skills-manifest.json").read_text(encoding="utf-8"))["entries"]
    assert all(e["source_ref"].startswith(".kittify/charter-packs/") for e in entries if e.get("origin") == "pack")


@covers("FR-012", 'EC:User-chosen path values containing "doctrine"')
def test_fr012_user_path_values_untouched(tmp_path: Path) -> None:
    """Regression guard (passes at base): a user path value containing "doctrine" is never rewritten."""
    project = build("user_path_value_with_doctrine", tmp_path)
    result, _ = upgrade(project)
    assert result.exit_code == 0, describe(result)
    assert config(project)["charter_packs"]["org"]["packs"] == [{"name": "foo", "local_path": USER_PACK_DIR}]
    assert (project / USER_PACK_DIR).is_dir()


@covers("FR-012", "EC:Windows")
@pytest.mark.windows_ci
def test_fr012_windows_locked_file_refuses(tmp_path: Path) -> None:
    project = build("legacy_directory_only", tmp_path)
    locked = project / ".kittify" / "doctrine" / "graph.yaml"
    with locked.open("rb"):
        result, payload = upgrade(project)
        assert "graph.yaml" in report_text(cutover_report(payload), "errors"), describe(result)
    assert sys.platform == "win32"


# --------------------------------------------------------------------------------------
# Resets, kept lists and summary (WP12)
# --------------------------------------------------------------------------------------


def _stale_keys(project: Path, kept: tuple[str, ...]) -> list[str]:
    charter = active_charter(project)
    return sorted(
        k for k, v in charter.items() if k not in kept and k != "mission_type_activations" and isinstance(v, list) and sorted(v) in snapshot_lists("default", k)
    )


_STALE_PARAMS = [*STALE_FIXTURES, "stale_in_pointed_charter_yaml", "mixed_stale_and_custom"]


@covers("FR-012", "US2-2", "INV:Stale activation lists", "INV:Stale kind gate")
@pytest.mark.parametrize("name", [pytest.param(n, marks=pending_until("WP12", "stale snapshot lists reset")) for n in _STALE_PARAMS])
def test_fr012_stale_list_reset(name: str, tmp_path: Path) -> None:
    project, outcome, payload = first_upgrade(name, tmp_path)
    stale = _stale_keys(outcome.pristine, STALE_KEYS_KEPT.get(name, ()))
    assert stale, "control: the fixture carries snapshot lists"
    after = active_charter(project)
    assert not [k for k in stale if k in after], stale
    reset = report_text(cutover_report(payload), "reset")
    assert all(k in reset for k in stale), reset


@covers("FR-012", "US2-3", "INV:Customised lists, `minimal`-equal lists", "EC:Stale list plus one customisation", "EC:Lists mixing default ids with other ids")
@pending_until("WP12", "near-miss and customised lists kept and reported")
def test_fr012_near_miss_and_customised_kept_and_reported(tmp_path: Path) -> None:
    for name, key in (("near_miss_stale", "activated_tactics"), ("customised_lists", "activated_directives")):
        project, outcome, payload = first_upgrade(name, tmp_path)
        before = active_charter(outcome.pristine)[key]
        after = active_charter(project)
        assert after[key] == before, name
        assert key in report_text(cutover_report(payload), "kept_for_review"), name
        assert "activated_paradigms" not in after, f"{name}: control, the other snapshot keys were reset"


@covers("FR-012", "INV:Released `minimal` kind gate", "EC:List equal to the `minimal` preset", "DM-01M497F0NAQARAK3JZFVWF1SD0")
@pending_until("WP12", "the released minimal kind gate is removed and reported")
def test_fr012_minimal_kind_gate_removed_lists_reported(tmp_path: Path) -> None:
    project, outcome, payload = first_upgrade("minimal_equal", tmp_path)
    before = active_charter(outcome.pristine)
    after = active_charter(project)
    assert "activated_kinds" not in after
    assert after["activated_directives"] == before["activated_directives"] and after["activated_tactics"] == before["activated_tactics"]
    report = cutover_report(payload)
    assert "activated_kinds" in report_text(report, "reset")
    assert "minimal" in report_text(report, "matches_minimal")


@covers("FR-012", "INV:Normalizer empty lists", "EC:Deliberate `[]` for a kind", "DM-01M497EW60HNWWJQCXDFA99R0H")
@pending_until("WP12", "normalizer [] lists reset and reported with the key to restore")
def test_fr012_normalizer_empty_lists_reset_and_reported(tmp_path: Path) -> None:
    project, _, payload = first_upgrade("normalizer_empty_lists", tmp_path)
    after = active_charter(project)
    assert not [k for k in NORMALIZER_RESET_KEYS if k in after]
    reset = report_text(cutover_report(payload), "reset")
    for key in NORMALIZER_RESET_KEYS:
        assert key in reset and "config.yaml" in reset and "[]" in reset, reset


@covers("FR-012", "FR-008", "INV:Installed skills", "US4-1")
@pending_until("WP18", "installed copies of removed skills retired through spec-kitty upgrade")
def test_fr012_installed_removed_skills(tmp_path: Path) -> None:
    project = build("installed_removed_skills", tmp_path)
    _, payload = upgrade(project)
    assert not (project / MANIFESTED_SKILL).exists()
    assert not (project / UNMANIFESTED_EQUAL_SKILL).exists()
    assert (project / EDITED_SKILL).exists(), "an edited copy is kept"
    report = cutover_report(payload)
    assert "spk-doctrine-show-me" in report_text(report, "skills_kept")
    assert "spk-doctrine-charter" in report_text(report, "skills_removed")
    assert (project / ".claude" / "skills" / "spk-charter-governance").is_dir(), "control: the new name is installed"


@covers("FR-012")
@pending_until("WP12", "dry run reports the same lines and writes nothing")
def test_fr012_dry_run_parity(tmp_path: Path) -> None:
    dry_project = build("stale_d5_original", tmp_path / "dry")
    real_project = build("stale_d5_original", tmp_path / "real")
    before = tree_digest(dry_project)
    _, dry = upgrade(dry_project, "--dry-run")
    assert tree_digest(dry_project) == before
    _, real = upgrade(real_project)
    dry_report, real_report = cutover_report(dry), cutover_report(real)
    assert dry_report["reset"], "control: the fixture has something to reset"
    assert {k: len(v) for k, v in dry_report.items()} == {k: len(v) for k, v in real_report.items()}
    assert dry_report["reset"] == real_report["reset"]


# --------------------------------------------------------------------------------------
# NFR-001 / NFR-004 / US2-6 / US2-7
# --------------------------------------------------------------------------------------


def _golden(name: str) -> dict[str, Any]:
    data = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _all_builtin(record: dict[str, Any], kind: str, builtin_now: dict[str, list[str]]) -> frozenset[str]:
    return frozenset(builtin_now[kind]) | frozenset(record["kinds"][kind]["extra"])


def _kept_kinds(name: str, relation: str) -> set[str]:
    """Kinds whose 'before' set must survive unchanged; every other kind becomes ALL_BUILTIN."""
    if relation == "equal":
        return {"*"}
    if relation == "stale":
        return {k.removeprefix("activated_") for k in STALE_KEYS_KEPT.get(name, ())}
    if relation == "minimal_equal":
        return {"directives", "tactics"}
    return set()


def expected_after(name: str, record: dict[str, Any], builtin_now: dict[str, list[str]]) -> dict[str, frozenset[str]]:
    relation = EXPECTED_RELATION[name]
    before = expand(record, builtin_now)
    if relation == "equal":
        return before
    if relation == "normalizer_empty_lists":
        reset = {k.removeprefix("activated_") for k in NORMALIZER_RESET_KEYS}
        return {k: (_all_builtin(record, k, builtin_now) if k in reset else v) for k, v in before.items()}
    kept = _kept_kinds(name, relation)
    return {k: (v if k in kept else _all_builtin(record, k, builtin_now)) for k, v in before.items()}


def _default_preset_mission_types() -> list[str]:
    data = load_yaml(DEFAULT_PRESET)
    return sorted(data["mission_type_activations"])


def _nfr001_param(name: str) -> object:
    """``equal`` fixtures already hold at base (the legacy readers still work): unmarked regression guards."""
    if EXPECTED_RELATION[name] == "equal":
        return pytest.param(name, id=name)
    return pytest.param(name, id=name, marks=pending_until("WP12", "upgrade resets stale state and preserves the effective set"))


@covers("NFR-001", "SC-002", "US2-1")
@pytest.mark.parametrize("name", [_nfr001_param(n) for n in NFR001_FIXTURES])
def test_nfr001_effective_set_preserved(name: str, tmp_path: Path) -> None:
    record = _golden(name)["effective"]
    project, outcome, payload = first_upgrade(name, tmp_path)
    assert outcome.exit_code == 0 and not payload["errors"], outcome.output
    builtin_now = builtin_inventory()
    after_record = effective_set(project, builtin_now)
    after = expand(after_record, builtin_now)
    before = expand(record, builtin_now)
    lost = {k: sorted(before[k] - after[k]) for k in before if before[k] - after[k]}
    assert not lost, f"artifacts lost: {lost}"
    assert after == expected_after(name, record, builtin_now)
    if EXPECTED_RELATION[name] == "pre_rc35":
        assert after_record["mission_types"] == _default_preset_mission_types()
        assert all(entry["form"] == ALL_BUILTIN for entry in after_record["kinds"].values())
    else:
        assert after_record["mission_types"] == record["mission_types"]
    assert after_record["skills"] == record["skills"]
    _assert_charter_list_agrees(project, after_record)


def _assert_charter_list_agrees(project: Path, record: dict[str, Any]) -> None:
    from .test_presets import listed_activations, list_kind

    listed = listed_activations(project)
    for kind, entry in record["kinds"].items():
        token = list_kind(f"activated_{kind}")
        if entry["form"] == ALL_BUILTIN:
            assert listed.get(token) is None, (kind, listed.get(token))
    assert listed.get("mission-type") == sorted(record["mission_types"])


#: NFR-001 fixtures whose ``detect()`` is false by contract (no item of the FR-012 inventory:
#: canonical keys and layout, or a pre-rc35 project with no activation keys at all). The
#: cutover has nothing to migrate there, so only the digest control applies.
CUTOVER_NOT_APPLICABLE = frozenset({"two_org_packs", "pre_rc35"})


#: NFR-001 fixtures that carry no reset row (stale list, kind gate, ``[]``): their second upgrade is
#: a 0-byte no-op once WP11's keys, root and path rows land, so they are not pending WP12.
NFR004_GREEN_AT_WP11 = frozenset(
    {
        "legacy_keys_only",
        "single_pack_legacy_form",
        "organisation_packs",
        "legacy_directory_only",
        "governance_doctrine_in_charter_yaml",
        "two_org_packs",
        "pre_rc35",
        "synthesized_with_provenance",
        "project_pack_skills",
    }
)


@covers("NFR-004", "US2-4")
@pytest.mark.parametrize(
    "name",
    [pytest.param(n, marks=() if n in NFR004_GREEN_AT_WP11 else pending_until("WP12", "a second upgrade changes 0 bytes")) for n in NFR001_FIXTURES],
)
def test_nfr004_second_upgrade_changes_zero_bytes(name: str, tmp_path: Path) -> None:
    project, first, first_payload = first_upgrade(name, tmp_path)
    before = tree_digest(first.pristine)
    assert first.exit_code == 0, first.output
    after_first = tree_digest(project)
    assert after_first != before, "control: the first upgrade changed something"
    if name not in CUTOVER_NOT_APPLICABLE:
        # The version stamp alone would satisfy the digest control; the cutover itself must have run.
        assert CUTOVER_ID in first_payload["migrations_applied"], first_payload["migrations_applied"]
    second, _ = upgrade(project)
    assert second.exit_code == 0, describe(second)
    assert tree_digest(project) == after_first
    assert cutover_migration().detect(project) is False


@covers("US2-6", "NFR-001")
@pending_until("WP12", "a pre-rc35 project upgrades with zero errors to the default preset")
def test_us2_6_pre_rc35_upgrade_has_zero_errors(tmp_path: Path) -> None:
    project = build("pre_rc35", tmp_path)
    result, payload = upgrade(project)
    assert result.exit_code == 0, describe(result)
    assert payload["errors"] == [] and payload["failure_reasons"] == []
    record = effective_set(project)
    assert record["mission_types"] == _default_preset_mission_types()
    assert all(entry["form"] == ALL_BUILTIN for entry in record["kinds"].values())
    assert CUTOVER_ID in json.dumps(payload["migrations"])


@covers("US2-7", "EC:Lane worktrees created before the upgrade")
@pytest.mark.slow
def test_us2_7_lane_in_approved_consolidates_after_root_upgrade(tmp_path: Path) -> None:
    """Root upgrade (a cutover commit on the target), merge the target into the lane, then consolidate."""
    project = build_lane_project(tmp_path / "lanes")
    lane_id, worktree = next(iter(project.lane_worktrees.items()))
    assert (worktree / LANE_LEGACY_LAYER).is_dir(), "precondition: the lane carries the legacy project layer"
    pre_upgrade = git(project.repo, "rev-parse", "HEAD")
    upgraded = project.upgrade()
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    # Positive control: the root upgrade is a cutover (committed or not), not just a version stamp.
    changed = git(project.repo, "diff", "--name-only", pre_upgrade, "--", LANE_LEGACY_LAYER).splitlines()
    assert changed, "control: the root upgrade changed the legacy project layer"
    assert not (project.repo / LANE_LEGACY_LAYER).exists(), "control: the cutover moved the legacy project layer"
    assert (project.repo / ".kittify" / "charter-packs").is_dir(), "control: the project layer now lives in .kittify/charter-packs/"
    if git(project.repo, "status", "--porcelain"):
        git(project.repo, "add", "-A")
        git(project.repo, "commit", "-q", "--no-verify", "-m", "chore: commit the upgraded charter layout")
    git(worktree, "merge", "-q", "--no-edit", project.target_branch)
    assert not (worktree / LANE_LEGACY_LAYER).exists(), "control: the merge brought the cutover into the lane"
    result = project.run("consolidate", "--mission", project.slug)
    combined = (result.stdout or "") + (result.stderr or "")
    assert "LANE_MOVED_AFTER_APPROVAL" not in combined, combined
    assert result.returncode == 0, combined
    assert git(project.repo, "cat-file", "-t", f"{project.target_branch}:src/{lane_id.replace('-', '_')}/m.py") == "blob"
