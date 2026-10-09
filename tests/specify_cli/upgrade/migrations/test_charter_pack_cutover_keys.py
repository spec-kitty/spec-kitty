"""Charter-pack cutover migration: config keys and ``doctrine_pack_id`` rows (#3732, T056/T057/T060).

Each test builds one FR-012 inventory row under ``tmp_path``, applies the
migration, asserts the rewrite and its report line, then asserts a second
``apply()`` changes 0 bytes and ``detect()`` is False (NFR-004 for the row).
"""

from __future__ import annotations

import json
from kernel.clock import datetime
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.base import MigrationResult, MigrationStateUnreadableError
from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration

pytestmark = [pytest.mark.unit]

CHARTER_POINTER = "charter: .kittify/charter/charter.yaml\n"


def _write(project: Path, rel: str, text: str) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _config(project: Path, text: str) -> Path:
    return _write(project, ".kittify/config.yaml", text)


def _load(path: Path) -> Any:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _digest(project: Path) -> dict[str, bytes]:
    """Every file under *project* and its bytes (a tree snapshot to compare)."""
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


def _report(result: MigrationResult) -> dict[str, list[str]]:
    report: dict[str, list[str]] = json.loads(result.changes_made[0])
    return report


def _apply_twice(project: Path) -> dict[str, list[str]]:
    """Apply, then prove the second application is a byte no-op and detect() is False."""
    migration = CharterPackCutoverMigration()
    assert migration.detect(project) is True, "control: the fixture carries legacy state"
    first = migration.apply(project)
    assert first.success, first.errors
    after_first = _digest(project)
    second = migration.apply(project)
    assert second.success
    assert _digest(project) == after_first
    assert _report(second)["rewritten"] == []
    assert migration.detect(project) is False
    return _report(first)


def test_org_packs_list_renamed(tmp_path: Path) -> None:
    config = _config(tmp_path, "# org packs\ndoctrine:\n  org:\n    packs:\n    - name: acme\n      local_path: org-packs/acme  # keep\nvcs:\n  type: git\n")
    report = _apply_twice(tmp_path)
    data = _load(config)
    assert "doctrine" not in data
    assert data["charter_packs"]["org"]["packs"] == [{"name": "acme", "local_path": "org-packs/acme"}]
    assert list(data) == ["charter_packs", "vcs"], "the canonical block takes the legacy block's place"
    text = config.read_text(encoding="utf-8")
    assert "# org packs" in text and "# keep" in text, "comments survive the round trip"
    assert report["rewritten"] == [".kittify/config.yaml: doctrine.org.packs -> charter_packs.org.packs"]


@pytest.mark.parametrize(("local_path", "expected"), [("org-packs", "org-packs"), ("vendor/Acme Packs", "acme-packs"), ("packs/default", "org"), ("", "org")])
def test_single_pack_legacy_form_gets_an_explicit_name(tmp_path: Path, local_path: str, expected: str) -> None:
    legacy = f"doctrine:\n  org:\n    local_path: '{local_path}'\n    subdir: acme\n    source_type: git\n"
    config = _config(tmp_path, legacy + "    url: https://x.invalid/p.git\n    ref: main\n")
    report = _apply_twice(tmp_path)
    data = _load(config)
    assert "doctrine" not in data
    (pack,) = data["charter_packs"]["org"]["packs"]
    assert pack == {"name": expected, "local_path": local_path, "subdir": "acme", "source_type": "git", "url": "https://x.invalid/p.git", "ref": "main"}
    assert report["rewritten"] == [f".kittify/config.yaml: doctrine.org (single-pack form) -> charter_packs.org.packs entry named {expected!r}"]


def test_single_pack_form_extra_keys_are_kept_for_review(tmp_path: Path) -> None:
    config = _config(tmp_path, "doctrine:\n  org:\n    local_path: org-packs\n    note: hand-written\n")
    report = _apply_twice(tmp_path)
    data = _load(config)
    assert data["doctrine"] == {"org": {"note": "hand-written"}}
    assert data["charter_packs"]["org"]["packs"] == [{"name": "org-packs", "local_path": "org-packs"}]
    assert report["kept_for_review"] == [".kittify/config.yaml: doctrine: keeps org (not a charter-pack key)"]


def test_organisation_packs_rewritten_and_unconvertible_entry_kept(tmp_path: Path) -> None:
    config = _config(tmp_path, "organisation_packs:\n- name: acme\n  path: org-packs/acme\n  source: local_path\n- name: remote\n  path: r\n  source: git\n")
    report = _apply_twice(tmp_path)
    data = _load(config)
    assert data["charter_packs"]["org"]["packs"] == [{"name": "acme", "local_path": "org-packs/acme"}]
    assert data["organisation_packs"] == [{"name": "remote", "path": "r", "source": "git"}]
    assert report["rewritten"] == [".kittify/config.yaml: organisation_packs -> charter_packs.org.packs (acme)"]
    assert report["kept_for_review"] == [".kittify/config.yaml: organisation_packs keeps 1 entry with a source other than local_path"]


def test_organisation_packs_fully_converted_is_removed(tmp_path: Path) -> None:
    config = _config(tmp_path, "organisation_packs:\n- name: a\n  path: pa\n- name: b\n  path: pb\n")
    _apply_twice(tmp_path)
    data = _load(config)
    assert "organisation_packs" not in data
    assert [p["name"] for p in data["charter_packs"]["org"]["packs"]] == ["a", "b"]


@pytest.mark.parametrize(
    ("legacy", "label"),
    [
        ("doctrine:\n  org:\n    packs:\n    - name: old\n      local_path: o\n", "doctrine.org.packs"),
        ("organisation_packs:\n- name: old\n  path: o\n", "organisation_packs"),
    ],
)
def test_canonical_org_block_wins_over_a_legacy_one(tmp_path: Path, legacy: str, label: str) -> None:
    config = _config(tmp_path, "charter_packs:\n  org:\n    packs:\n    - name: canonical\n      local_path: c\n" + legacy)
    report = _apply_twice(tmp_path)
    data = _load(config)
    assert set(data) == {"charter_packs"}
    assert [p["name"] for p in data["charter_packs"]["org"]["packs"]] == ["canonical"]
    assert report["rewritten"] == [f".kittify/config.yaml: dropped {label} (charter_packs.org is already present; the canonical value wins)"]


def test_charter_packs_without_org_receives_the_org_block(tmp_path: Path) -> None:
    config = _config(tmp_path, "charter_packs:\n  project:\n    skill_namespace: acme\ndoctrine:\n  org:\n    packs: []\n")
    _apply_twice(tmp_path)
    assert _load(config)["charter_packs"] == {"project": {"skill_namespace": "acme"}, "org": {"packs": []}}


def test_charter_packs_not_a_mapping_keeps_the_legacy_block_for_review(tmp_path: Path) -> None:
    config = _config(tmp_path, "charter_packs: oops\ndoctrine:\n  org:\n    packs: []\n")
    before = config.read_bytes()
    result = CharterPackCutoverMigration().apply(tmp_path)
    assert result.success
    assert config.read_bytes() == before
    assert _report(result)["kept_for_review"] == [
        ".kittify/config.yaml: doctrine.org.packs kept (charter_packs is not a mapping; make it one by hand, then run `spec-kitty upgrade` again)"
    ]


@pytest.mark.parametrize(
    ("section", "legacy_value", "new_key"),
    [("governance", "{selected_directives: [X]}", "charter"), ("tracker", "{mode: external_authoritative}", "ownership")],
)
def test_governance_and_tracker_keys_renamed_line_level(tmp_path: Path, section: str, legacy_value: str, new_key: str) -> None:
    text = f"vcs:\n  type: git  # c\n{section}:\n  doctrine: {legacy_value}\n  other: 1\n"
    config = _config(tmp_path, text)
    report = _apply_twice(tmp_path)
    assert config.read_text(encoding="utf-8") == text.replace("  doctrine:", f"  {new_key}:"), "only the key line changes"
    assert report["rewritten"] == [f".kittify/config.yaml: {section}.doctrine -> {section}.{new_key}"]


@pytest.mark.parametrize(("section", "new_key"), [("governance", "charter"), ("tracker", "ownership")])
def test_governance_and_tracker_canonical_wins(tmp_path: Path, section: str, new_key: str) -> None:
    config = _config(tmp_path, f"{section}:\n  {new_key}: {{keep: 1}}\n  doctrine: {{drop: 1}}\n")
    report = _apply_twice(tmp_path)
    assert _load(config) == {section: {new_key: {"keep": 1}}}
    assert report["rewritten"] == [f".kittify/config.yaml: dropped {section}.doctrine ({section}.{new_key} is already present; the canonical value wins)"]


def test_config_structural_and_key_rewrites_together(tmp_path: Path) -> None:
    config = _config(tmp_path, "doctrine:\n  org:\n    packs: []\ngovernance:\n  doctrine: {a: 1}\ntracker:\n  doctrine: {mode: m}\n")
    report = _apply_twice(tmp_path)
    assert _load(config) == {"charter_packs": {"org": {"packs": []}}, "governance": {"charter": {"a": 1}}, "tracker": {"ownership": {"mode": "m"}}}
    assert len(report["rewritten"]) == 3


def test_charter_yaml_governance_renamed_byte_minimal(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    body = "".join(f'# filler {i}: doctrine prose, keep me\nkey_{i}: "value {i}"\n' for i in range(200))
    original = f"schema_version: '2.0.0'\n{body}governance:\n  doctrine:\n    selected_directives:\n    - 003-x\n  template_set: t\n"
    charter = _write(tmp_path, ".kittify/charter/charter.yaml", original)
    report = _apply_twice(tmp_path)
    after = charter.read_text(encoding="utf-8").splitlines()
    before = original.splitlines()
    assert len(after) == len(before)
    changed = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
    assert changed == [("  doctrine:", "  charter:")]
    assert report["rewritten"] == [".kittify/charter/charter.yaml: governance.doctrine -> governance.charter"]


def test_charter_yaml_resolved_through_the_pointer(tmp_path: Path) -> None:
    _config(tmp_path, "charter: custom/place.yaml\n")
    pointed = _write(tmp_path, "custom/place.yaml", "governance:\n  doctrine: {a: 1}\n")
    default = _write(tmp_path, ".kittify/charter/charter.yaml", "governance:\n  doctrine: {untouched: 1}\n")
    result = CharterPackCutoverMigration().apply(tmp_path)
    assert result.success
    assert _load(pointed) == {"governance": {"charter": {"a": 1}}}
    assert _load(default) == {"governance": {"doctrine": {"untouched": 1}}}


def test_charter_yaml_without_pointer_uses_the_bundle_path(tmp_path: Path) -> None:
    _config(tmp_path, "vcs: {type: git}\n")
    charter = _write(tmp_path, ".kittify/charter/charter.yaml", "governance:\n  doctrine: {a: 1}\n")
    _apply_twice(tmp_path)
    assert _load(charter) == {"governance": {"charter": {"a": 1}}}


def test_charter_yaml_both_keys_canonical_wins(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    charter = _write(tmp_path, ".kittify/charter/charter.yaml", "governance:\n  charter: {keep: 1}\n  doctrine: {drop: 1}\n")
    report = _apply_twice(tmp_path)
    assert _load(charter) == {"governance": {"charter": {"keep": 1}}}
    assert report["rewritten"][0].startswith(".kittify/charter/charter.yaml: dropped governance.doctrine")


def test_standalone_governance_yaml_renamed(tmp_path: Path) -> None:
    governance = _write(tmp_path, ".kittify/charter/governance.yaml", "doctrine:\n  selected_directives: [X]\n")
    report = _apply_twice(tmp_path)
    assert governance.read_text(encoding="utf-8") == "charter:\n  selected_directives: [X]\n"
    assert report["rewritten"] == [".kittify/charter/governance.yaml: doctrine -> charter"]


def test_answers_top_level_key_renamed_prose_untouched(tmp_path: Path) -> None:
    original = (
        "schema_version: '1'\n# doctrine: a comment, never a key\n"
        "doctrine:\n  selected_directives: [DIRECTIVE_003]\nanswers:\n  q: 'the doctrine-catfooding mission'\n"
    )
    answers = _write(tmp_path, ".kittify/charter/interview/answers.yaml", original)
    report = _apply_twice(tmp_path)
    assert answers.read_text(encoding="utf-8") == original.replace("\ndoctrine:\n", "\ncharter:\n")
    assert report["rewritten"] == [".kittify/charter/interview/answers.yaml: doctrine -> charter"]


def test_answers_both_keys_canonical_wins(tmp_path: Path) -> None:
    answers = _write(tmp_path, ".kittify/charter/interview/answers.yaml", "charter: {keep: 1}\ndoctrine: {drop: 1}\n")
    _apply_twice(tmp_path)
    assert _load(answers) == {"charter": {"keep": 1}}


def test_doctrine_pack_id_renamed_in_activation_entries(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    original = (
        "governance:\n  activations:\n  - doctrine_pack_id: acme\n    artifact_id: t\n  - {'doctrine_pack_id': acme, artifact_id: u}\n"
        'activations:\n- artifact_id: v\n  doctrine_pack_id: "acme"\n'
    )
    charter = _write(tmp_path, ".kittify/charter/charter.yaml", original)
    report = _apply_twice(tmp_path)
    assert charter.read_text(encoding="utf-8") == original.replace("doctrine_pack_id", "charter_pack_id")
    assert report["rewritten"] == [".kittify/charter/charter.yaml: activations[].doctrine_pack_id -> activations[].charter_pack_id"] * 3


def test_doctrine_pack_id_both_keys_canonical_wins(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    charter = _write(tmp_path, ".kittify/charter/charter.yaml", "activations:\n- charter_pack_id: keep\n  doctrine_pack_id: drop\n")
    _apply_twice(tmp_path)
    assert _load(charter) == {"activations": [{"charter_pack_id": "keep"}]}


def test_doctrine_pack_id_in_standalone_governance_yaml(tmp_path: Path) -> None:
    governance = _write(tmp_path, ".kittify/charter/governance.yaml", "charter: {}\nactivations:\n- doctrine_pack_id: acme\n")
    _apply_twice(tmp_path)
    assert _load(governance) == {"charter": {}, "activations": [{"charter_pack_id": "acme"}]}


def test_doctrine_pack_id_is_structural(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    _write(tmp_path, ".kittify/charter/charter.yaml", "activations:\n- doctrine_pack_id: acme\n")
    migration = CharterPackCutoverMigration()
    assert migration.structural_detect(tmp_path) is True
    migration.apply(tmp_path)
    assert migration.structural_detect(tmp_path) is False


def test_user_path_values_containing_doctrine_never_rewritten(tmp_path: Path) -> None:
    text = "charter_packs:\n  org:\n    packs:\n    - name: foo\n      local_path: packs/doctrine-foo\ngovernance:\n  charter:\n    template_set: doctrine-set\n"
    config = _config(tmp_path, text)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)
    assert config.read_text(encoding="utf-8") == text
    assert not any(_report(result).values())


def test_dry_run_writes_nothing_and_reports_would_lines(tmp_path: Path) -> None:
    _config(tmp_path, "doctrine:\n  org:\n    packs: []\ngovernance:\n  doctrine: {}\n")
    before = _digest(tmp_path)
    result = CharterPackCutoverMigration().apply(tmp_path, dry_run=True)
    assert _digest(tmp_path) == before
    assert len(_report(result)["rewritten"]) == 2
    assert [line.split(" ", 2)[:2] for line in result.changes_made[1:]] == [["Would", "rewrite"]] * 2


def test_malformed_config_selects_and_apply_names_the_file(tmp_path: Path) -> None:
    _config(tmp_path, "doctrine: [unclosed\n")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    assert migration.structural_detect(tmp_path) is True
    with pytest.raises(MigrationStateUnreadableError, match=r"\.kittify/config\.yaml is not readable YAML"):
        migration.apply(tmp_path)


def test_malformed_governance_file_names_the_file(tmp_path: Path) -> None:
    _write(tmp_path, ".kittify/charter/governance.yaml", "doctrine: [unclosed\n")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    with pytest.raises(MigrationStateUnreadableError, match=r"governance\.yaml is not readable YAML"):
        migration.apply(tmp_path)


def test_malformed_charter_yaml_selects_and_apply_names_it(tmp_path: Path) -> None:
    _config(tmp_path, CHARTER_POINTER)
    _write(tmp_path, ".kittify/charter/charter.yaml", "governance:\n  doctrine: [unclosed\n")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    assert migration.structural_detect(tmp_path) is True
    with pytest.raises(MigrationStateUnreadableError, match=r"charter\.yaml could not be read"):
        migration.apply(tmp_path)


def test_detect_is_total_even_when_a_step_crashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.upgrade.migrations import m_4_0_0rc6_charter_pack_cutover as module

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(module, "_run_steps", boom)
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    assert migration.structural_detect(tmp_path) is True


def test_is_first_application_reads_the_recorded_result(tmp_path: Path) -> None:
    from specify_cli.upgrade.metadata import ProjectMetadata

    migration = CharterPackCutoverMigration()
    assert migration.is_first_application(tmp_path) is True
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    metadata = ProjectMetadata(version="4.0.0rc6", initialized_at=datetime(2026, 1, 1), python_version="3.11", platform="t", platform_version="t")
    metadata.record_migration(migration.migration_id, "failed")
    metadata.save(kittify)
    assert migration.is_first_application(tmp_path) is True, "a failed record does not settle the cutover"
    metadata.record_migration(migration.migration_id, "success")
    metadata.save(kittify)
    assert migration.is_first_application(tmp_path) is False
    (kittify / "metadata.yaml").write_text(": [", encoding="utf-8")
    assert migration.is_first_application(tmp_path) is True
