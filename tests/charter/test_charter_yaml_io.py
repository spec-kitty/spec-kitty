"""Tests for the shared charter.yaml write helper (WP01 / T003 / INV-9).

Three independent writers (activation_engine.commit_plan, pack_manager.
merge_defaults, compiler.write_compiled_charter) must route through this ONE
``load -> mutate-owned-section -> round-trip-save`` helper so section
preservation is structural, not conventional (Landmine 3 / alphonso
MAJOR-3). These tests prove the byte-preservation guarantee: mutating one
named section leaves every other section's formatting (including comments)
untouched.
"""

from __future__ import annotations

from pathlib import Path
import types

import pytest

from charter.activation.charter_yaml_io import (
    OWNED_SECTIONS,
    UnknownCharterYamlSectionError,
    catalog_field_from_document,
    load_charter_yaml,
    save_charter_yaml,
    update_charter_yaml_section,
)


pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("reload_document", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        "metadata: {}\nactivated_directives: # keep-rationale\n  - old\n",
        "? activated_directives # keep-rationale\n: [old]\nmetadata: {}\n",
    ],
)
def test_reused_document_preserves_key_comments(tmp_path: Path, newline: str, reload_document: bool, body: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    tail = '# outside\noverrides: {keep: "raw"}\n'.replace("\n", newline).encode()
    path.write_bytes(body.replace("\n", newline).encode() + tail)
    document = load_charter_yaml(path)
    document["metadata"] = {"long-entry": "x" * 100}
    save_charter_yaml(path, document)
    for value in ([], ["new"], [], ["final"]):
        if reload_document:
            document = load_charter_yaml(path)
        document["activated_directives"] = value
        save_charter_yaml(path, document)
        assert load_charter_yaml(path)["activated_directives"] == value
        assert path.read_bytes().count(b"# keep-rationale") == 1
        assert path.read_bytes().endswith(tail)
    before = snapshot({"project": tmp_path})
    save_charter_yaml(path, document)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("body", ["null\n", "metadata: {}\n"])
def test_version_directive_saver_preserves_document_frame(tmp_path: Path, newline: str, pointer: bool, body: str) -> None:
    from charter.activation.pack_manager import resolve_activation_write_target
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    if pointer:
        config.write_bytes(b"charter: policy.yaml\n")
    prefix = "%YAML 1.2\n---\n".replace("\n", newline).encode()
    suffix = "... # end\n".replace("\n", newline).encode()
    target.write_bytes(prefix + body.replace("\n", newline).encode() + suffix)
    path, document, save = resolve_activation_write_target(tmp_path)
    assert path == target
    document["activated_directives"] = ["new"]
    save(path, document)
    assert load_charter_yaml(path)["activated_directives"] == ["new"]
    assert path.read_bytes().startswith(prefix)
    assert path.read_bytes().endswith(suffix)
    if body.startswith("metadata"):
        assert body.replace("\n", newline).encode() in path.read_bytes()
    if pointer:
        assert config.read_bytes() == b"charter: policy.yaml\n"
    before = snapshot({"project": tmp_path})
    save(path, document)
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_update_block_collection_retains_key_comment(tmp_path: Path) -> None:
    path = tmp_path / "charter.yaml"
    path.write_bytes(b"activated_directives: # keep this rationale\n  - old\nmetadata: {}\n")

    update_charter_yaml_section(path, "activation", {"activated_directives": ["new"]})

    assert load_charter_yaml(path)["activated_directives"] == ["new"]
    assert path.read_bytes().startswith(b"activated_directives: # keep this rationale\n")
    assert path.read_bytes().endswith(b"metadata: {}\n")


@pytest.mark.parametrize(
    "section,key,old,new",
    [
        ("activation", "activated_directives", "\n  - old", ["new"]),
        ("activation", "activated_directives", " [old]", ["new"]),
        ("metadata", "metadata", "\n  label: old", {"label": "new"}),
        ("metadata", "metadata", " {label: old}", {"label": "new"}),
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_section_replacement_preserves_comment_framing(
    tmp_path: Path,
    section: str,
    key: str,
    old: str,
    new: object,
    newline: str,
) -> None:
    from charter.activation.charter_yaml_io import prepare_charter_yaml_section, apply_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    prefix = "--- # document\n# before key\n"
    tail = '\n# separator\noverrides:\n  choices:\n    - "keep"\n... # end\n'
    value = " # key rationale" + old if old.startswith("\n") else old + " # key rationale"
    path.write_bytes((prefix + key + ":" + value + "\n" + tail).replace("\n", newline).encode())
    values = {key: new} if section == "activation" else new
    assert isinstance(values, dict)
    before = snapshot({"project": tmp_path})
    prepared = prepare_charter_yaml_section(path, section, values)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert apply_yaml_write(prepared)
    raw = path.read_text()
    assert raw.startswith(prefix) and raw.endswith(tail)
    assert path.read_bytes().startswith(prefix.replace("\n", newline).encode())
    assert path.read_bytes().endswith(tail.replace("\n", newline).encode())
    assert raw.count("# key rationale") == 1
    assert raw.count("# separator") == 1
    assert raw.count("# before key") == 1
    assert load_charter_yaml(path)[key] == new
    after = snapshot({"project": tmp_path})
    update_charter_yaml_section(path, section, values)
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("body", [b"", b"# only\n", b"null\n", b"~ # reason\n", b"---\n...\n"])
def test_save_null_convention_and_mapping_readback(tmp_path: Path, body: bytes) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    path.write_bytes(body)
    before = snapshot({"project": tmp_path})
    document = load_charter_yaml(path)
    save_charter_yaml(path, document)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    document["metadata"] = {"label": "new"}
    save_charter_yaml(path, document)
    assert load_charter_yaml(path) == {"metadata": {"label": "new"}}


@pytest.mark.parametrize("body", [b"null\n", b"~\n", b"---\n...\n", b"[]\n", b"false\n", b"broken: [\n", b"{}\n---\n{}\n"])
def test_prepared_bytes_refuse_nonmapping_before_any_write(tmp_path: Path, body: bytes) -> None:
    from ruamel.yaml.error import YAMLError
    from charter.activation.charter_yaml_io import prepare_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    before = snapshot({"project": tmp_path})
    with pytest.raises((ValueError, YAMLError)):
        prepare_yaml_write(tmp_path / "absent/charter.yaml", body, section="document")
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("document", [None, [], "scalar", False])
def test_save_refuses_nonmapping_document(tmp_path: Path, present: bool, document: object) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    if present:
        path.write_bytes(b"metadata: {}\n")
    before = snapshot({"project": tmp_path})
    with pytest.raises(ValueError, match="YAML root must be a mapping"):
        save_charter_yaml(path, document)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize(
    "section,key,old,new",
    [
        ("activation", "activated_directives", "\n  - old", []),
        ("activation", "activated_directives", " [old]", []),
        ("metadata", "metadata", "\n  label: old", {}),
        ("metadata", "metadata", " {label: old}", {}),
    ],
)
def test_empty_collection_keeps_following_key_boundary(tmp_path: Path, newline: str, section: str, key: str, old: str, new: object) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    tail = 'overrides: {label: "keep"}' + newline
    path.write_bytes((key + ":" + old + "\n").replace("\n", newline).encode() + tail.encode())
    values = {key: new} if section == "activation" else new
    assert isinstance(values, dict)
    update_charter_yaml_section(path, section, values)
    assert load_charter_yaml(path)[key] == new
    assert path.read_bytes().endswith(tail.encode())
    after = snapshot({"project": tmp_path})
    update_charter_yaml_section(path, section, values)
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "section,key,body",
    [
        ("activation", "activated_directives", "activated_directives: # rationale\n# key detail\n  - old\n"),
        ("metadata", "metadata", "metadata: # rationale\n# key detail\n  label: old\n"),
        ("activation", "activated_directives", "? activated_directives\n: [old]\n"),
        ("metadata", "metadata", "? metadata\n: {label: old}\n"),
        ("activation", "activated_directives", "activated_directives:\n# key detail\n  - old\n"),
        ("metadata", "metadata", "metadata:\n# key detail\n  label: old\n"),
        ("activation", "activated_directives", "activated_directives: # rationale\n\n  # key detail\n  # continuation\n  - old\n"),
        ("activation", "activated_directives", "? # indicator\n  activated_directives # key detail\n: # rationale\n  - old\n"),
        ("metadata", "metadata", "? # indicator\n  metadata # key detail\n: # rationale\n  label: old\n"),
        ("activation", "activated_directives", "? 'activated_directives'\n: [old]\n"),
        ("activation", "activated_directives", "? >-\n  activated_directives\n: [old]\n"),
        ("activation", "activated_directives", "?\n  activated_directives\n: [old]\n"),
        ("activation", "activated_directives", "? activated_directives\n: # rationale\n# key detail\n  - old\n"),
        ("activation", "activated_directives", "activated_directives: # rationale\n# key detail\n"),
    ],
)
def test_section_entry_source_boundaries(tmp_path: Path, newline: str, empty: bool, section: str, key: str, body: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    prefix = "--- # document\n# before entry\n".replace("\n", newline).encode()
    tail = '\n# separator\noverrides: {label: "keep"}\n... # end\n'.replace("\n", newline).encode()
    path.write_bytes(prefix + body.replace("\n", newline).encode() + tail)
    value = ([] if empty else ["new"]) if section == "activation" else ({} if empty else {"label": "new"})
    values = {key: value} if section == "activation" else value
    assert isinstance(values, dict)
    update_charter_yaml_section(path, section, values)
    assert load_charter_yaml(path)[key] == value
    raw = path.read_bytes()
    assert raw.startswith(prefix) and raw.endswith(tail)
    for comment in (b"# rationale", b"# key detail", b"# indicator", b"# continuation"):
        if comment in body.encode():
            assert raw.count(comment) == 1
    after = snapshot({"project": tmp_path})
    update_charter_yaml_section(path, section, values)
    assert_unchanged(after, snapshot({"project": tmp_path}))


def test_inherited_activation_override_preserves_merge_source(tmp_path: Path) -> None:
    path = tmp_path / "charter.yaml"
    prefix = b"defaults: &defaults {activated_directives: [old]}\n<<: *defaults\n"
    path.write_bytes(prefix)
    update_charter_yaml_section(path, "activation", {"activated_directives": ["new"]})
    assert path.read_bytes().startswith(prefix)
    document = load_charter_yaml(path)
    assert document["activated_directives"] == ["new"]
    assert document["defaults"]["activated_directives"] == ["old"]


def test_alias_replacement_preserves_unowned_anchor(tmp_path: Path) -> None:
    path = tmp_path / "charter.yaml"
    prefix = b"overrides: &authored {label: old}\n"
    path.write_bytes(prefix + b"metadata: *authored\n")
    update_charter_yaml_section(path, "metadata", {"label": "new"})
    assert path.read_bytes().startswith(prefix)
    assert load_charter_yaml(path)["overrides"] == {"label": "old"}
    assert load_charter_yaml(path)["metadata"] == {"label": "new"}


def test_flow_mapping_update_preserves_unowned_entry_and_tail(tmp_path: Path) -> None:
    path = tmp_path / "charter.yaml"
    path.write_bytes(b'{metadata: {label: old}, 42: ["keep", spacing]} # tail\n')
    update_charter_yaml_section(path, "metadata", {"label": "new"})
    assert load_charter_yaml(path)["metadata"] == {"label": "new"}
    assert path.read_bytes().endswith(b', 42: ["keep", spacing]} # tail\n')


def test_save_added_key_retains_round_trip_comment(tmp_path: Path) -> None:
    path = tmp_path / "charter.yaml"
    prefix = b'overrides:\n  choices:\n    - "keep"\n'
    path.write_bytes(prefix)
    document = load_charter_yaml(path)
    document["activated_directives"] = ["new"]
    document.yaml_add_eol_comment("new rationale", key="activated_directives")
    save_charter_yaml(path, document)
    assert path.read_bytes().startswith(prefix)
    assert path.read_bytes().count(b"# new rationale") == 1
    assert load_charter_yaml(path)["activated_directives"] == ["new"]


def test_owned_anchor_change_refuses_unowned_alias_drift(tmp_path: Path) -> None:
    from ruamel.yaml.error import YAMLError
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    path.write_bytes(b"metadata: &owned {label: old}\noverrides: *owned\n")
    before = snapshot({"project": tmp_path})
    with pytest.raises((ValueError, YAMLError)):
        update_charter_yaml_section(path, "metadata", {"label": "new"})
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_flow_root_deletion_refuses_before_writing(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    path.write_bytes(b"{metadata: {}, overrides: {label: keep}} # tail\n")
    document = load_charter_yaml(path)
    del document["metadata"]
    before = snapshot({"project": tmp_path})
    with pytest.raises(ValueError, match="deletion from flow-style"):
        save_charter_yaml(path, document)
    assert_unchanged(before, snapshot({"project": tmp_path}))


def test_update_existing_activation_does_not_open_for_write(tmp_path: Path) -> None:
    import os

    path = tmp_path / "charter.yaml"
    path.write_bytes(b"# authored\nmission_type_activations: [software-dev]\n")
    path.chmod(0o640)
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    before = path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns

    update_charter_yaml_section(path, "activation", {"mission_type_activations": ["software-dev"]})

    assert (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("suffix", ["", "...\n"])
def test_section_change_preserves_unowned_spans(tmp_path: Path, suffix: str) -> None:
    from charter.activation.charter_yaml_io import prepare_charter_yaml_section, apply_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    prefix = '# top\nmetadata:\n  labels:\n    - "quoted"\n\n'
    tail = "# owned by user\noverrides:\n  text: |\n    first\n    second\n" + suffix
    path.write_text(prefix + "mission_type_activations: [research] # selection\n" + tail, encoding="utf-8")
    before = snapshot({"project": tmp_path})
    prepared = prepare_charter_yaml_section(path, "activation", {"mission_type_activations": ["software-dev"]})
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert apply_yaml_write(prepared)
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith(prefix) and raw.endswith(tail)
    assert "# selection" in raw
    after = snapshot({"project": tmp_path})
    save_charter_yaml(path, load_charter_yaml(path))
    assert_unchanged(after, snapshot({"project": tmp_path}))


def test_prepared_writer_reports_absent_parents_and_actual_delta(tmp_path: Path) -> None:
    from charter.activation.charter_yaml_io import prepare_yaml_write, apply_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    path = tmp_path / "new/nested/charter.yaml"
    before = snapshot({"project": tmp_path})
    prepared = prepare_yaml_write(path, b"mission_type_activations: []\n", section="activation")
    assert prepared.absent_parents == (tmp_path / "new", tmp_path / "new/nested")
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert apply_yaml_write(prepared)
    effects = net_delta(before, snapshot({"project": tmp_path}))
    assert {(e.path, e.action, e.after.kind, e.after.mode) for e in effects} == {
        ("new", "create", "directory", 0o755),
        ("new/nested", "create", "directory", 0o755),
        ("new/nested/charter.yaml", "create", "file", 0o644),
    }


def test_prepared_writer_propagates_io_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from charter.activation.charter_yaml_io import prepare_charter_yaml_section, apply_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    path = tmp_path / "charter.yaml"
    path.write_bytes(b"metadata: {}\n")
    prepared = prepare_charter_yaml_section(path, "activation", {"mission_type_activations": ["research"]})

    def fail_open(*_args: object, **_kwargs: object) -> int:
        raise OSError("injected destination failure")

    monkeypatch.setattr(os, "open", fail_open)
    before = snapshot({"project": tmp_path})
    with pytest.raises(OSError, match="injected destination failure"):
        apply_yaml_write(prepared)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("body", [b"{}\n", b'{metadata: {tags: ["keep"]}} # tail\n'])
def test_flow_root_provisioning_retains_unowned_text(tmp_path: Path, body: bytes) -> None:
    path = tmp_path / "charter.yaml"
    path.write_bytes(body)
    update_charter_yaml_section(path, "activation", {"mission_type_activations": ["research"]})
    assert load_charter_yaml(path)["mission_type_activations"] == ["research"]
    if b"metadata" in body:
        assert b'metadata: {tags: ["keep"]}' in path.read_bytes()
        assert path.read_bytes().endswith(b" # tail\n")


def test_new_file_writer_does_not_require_unix_fchmod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from charter.activation.charter_yaml_io import prepare_yaml_write, apply_yaml_write

    prepared = prepare_yaml_write(tmp_path / "charter.yaml", b"metadata: {}\n", section="document")
    monkeypatch.delattr(os, "fchmod", raising=False)
    assert apply_yaml_write(prepared)
    assert (tmp_path / "charter.yaml").read_bytes() == prepared.desired_bytes


_FIXTURE = """\
schema_version: "2.0.0"
governance:
  testing:
    min_coverage: 80  # GOV-COMMENT-MARKER preserved
  quality: {}
  commits: {}
  performance: {}
  branch_strategy: {}
  doctrine: {}
  activations: []
  enforcement: {}
directives:
  directives: []
catalog:
  mission: software-dev
  template_set: software-dev-default  # CATALOG-COMMENT-MARKER preserved
  languages:
  - python
  references: []
activated_kinds:
- directives
mission_type_activations:
- software-dev
activated_directives: []
activated_tactics:
activated_styleguides:
activated_toolguides:
activated_paradigms:
activated_procedures:
activated_agent_profiles:
activated_mission_step_contracts:
overrides: {}
metadata:
  generated_at: '2026-07-18T00:00:00Z'
  bundle_schema_version: 2
"""


def _write_fixture(path: Path) -> None:
    path.write_text(_FIXTURE, encoding="utf-8")


class TestOwnedSections:
    def test_owned_sections_cover_the_six_named_sections(self) -> None:
        expected = {
            "governance",
            "directives",
            "catalog",
            "activation",
            "metadata",
            "overrides",
        }
        assert expected == OWNED_SECTIONS

    def test_unknown_section_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)
        with pytest.raises(UnknownCharterYamlSectionError):
            update_charter_yaml_section(path, "not-a-real-section", {"x": 1})


class TestLoadSaveRoundTrip:
    def test_load_then_save_is_byte_identical_when_unmutated(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        document = load_charter_yaml(path)
        save_charter_yaml(path, document)

        assert path.read_text(encoding="utf-8") == _FIXTURE


class TestMutateActivationPreservesGovernanceAndCatalog:
    def test_mutating_activation_preserves_governance_comment_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "activation",
            {"activated_directives": ["001-architectural-integrity-standard"]},
        )

        text = path.read_text(encoding="utf-8")
        assert "# GOV-COMMENT-MARKER preserved" in text
        assert "min_coverage: 80" in text

    def test_mutating_activation_preserves_catalog_comment_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "activation",
            {"activated_directives": ["001-architectural-integrity-standard"]},
        )

        text = path.read_text(encoding="utf-8")
        assert "# CATALOG-COMMENT-MARKER preserved" in text
        assert "template_set: software-dev-default" in text

    def test_mutating_activation_actually_updates_the_target_key(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "activation",
            {"activated_directives": ["001-architectural-integrity-standard"]},
        )

        document = load_charter_yaml(path)
        assert document["activated_directives"] == ["001-architectural-integrity-standard"]

    def test_mutating_activation_leaves_other_activation_keys_untouched(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "activation",
            {"activated_directives": ["001-architectural-integrity-standard"]},
        )

        document = load_charter_yaml(path)
        assert document["activated_kinds"] == ["directives"]
        assert document["mission_type_activations"] == ["software-dev"]

    def test_mutating_activation_rejects_unknown_activation_key(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        with pytest.raises(ValueError, match="Unknown activation key"):
            update_charter_yaml_section(path, "activation", {"not_a_real_activation_key": []})


class TestMutateCatalogPreservesGovernanceAndActivation:
    def test_mutating_catalog_preserves_governance_comment_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "catalog",
            {
                "mission": "software-dev",
                "template_set": "software-dev-default",
                "languages": ["python", "rust"],
                "references": [],
            },
        )

        text = path.read_text(encoding="utf-8")
        assert "# GOV-COMMENT-MARKER preserved" in text

    def test_mutating_catalog_preserves_activation_flat_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "catalog",
            {
                "mission": "software-dev",
                "template_set": "software-dev-default",
                "languages": ["python", "rust"],
                "references": [],
            },
        )

        document = load_charter_yaml(path)
        assert document["activated_kinds"] == ["directives"]
        assert document["activated_directives"] == []

    def test_mutating_catalog_updates_the_target_section(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "catalog",
            {
                "mission": "software-dev",
                "template_set": "software-dev-default",
                "languages": ["python", "rust"],
                "references": [],
            },
        )

        document = load_charter_yaml(path)
        assert document["catalog"]["languages"] == ["python", "rust"]


class TestMutateGovernancePreservesCatalogAndMetadata:
    def test_mutating_governance_preserves_catalog_comment_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "governance",
            {
                "testing": {"min_coverage": 90},
                "quality": {},
                "commits": {},
                "performance": {},
                "branch_strategy": {},
                "doctrine": {},
                "activations": [],
                "enforcement": {},
            },
        )

        text = path.read_text(encoding="utf-8")
        assert "# CATALOG-COMMENT-MARKER preserved" in text

    def test_mutating_governance_preserves_metadata(self, tmp_path: Path) -> None:
        path = tmp_path / "charter.yaml"
        _write_fixture(path)

        update_charter_yaml_section(
            path,
            "governance",
            {
                "testing": {"min_coverage": 90},
                "quality": {},
                "commits": {},
                "performance": {},
                "branch_strategy": {},
                "doctrine": {},
                "activations": [],
                "enforcement": {},
            },
        )

        document = load_charter_yaml(path)
        assert document["metadata"]["bundle_schema_version"] == 2


@pytest.mark.parametrize("parents", [False, True])
def test_yaml_creation_receipt_requires_exact_writer_and_unchanged_nodes(tmp_path: Path, parents: bool) -> None:
    import copy
    from dataclasses import replace
    from charter.activation.charter_yaml_io import apply_yaml_write, prepare_yaml_write

    target = tmp_path / "nested/config.yaml" if parents else tmp_path / "config.yaml"
    prepared = prepare_yaml_write(target, b"mission_type_activations: []\n", section="activation")
    assert not target.exists()
    with pytest.raises(ValueError, match="no completion receipt"):
        prepared.recheck_applied()
    assert apply_yaml_write(prepared)
    assert set(prepared.recheck_applied()) == {target, *prepared.absent_parents}
    for clone in (copy.copy(prepared), copy.deepcopy(prepared), replace(prepared)):
        with pytest.raises(ValueError, match="no completion receipt"):
            clone.recheck_applied()
    with pytest.raises(ValueError, match="precondition_changed"):
        apply_yaml_write(prepared)
    assert prepared.recheck_applied()  # Failed repeat did not erase the original receipt.


@pytest.mark.parametrize("damage", ["replace", "hardlink", "symlink", "parent", "input"])
def test_yaml_creation_receipt_refuses_post_write_interference(tmp_path: Path, damage: str) -> None:
    import os
    from charter.activation.charter_yaml_io import apply_yaml_write, observe_yaml_input, prepare_yaml_write

    source = tmp_path / "source.yaml"
    source.write_text("source: true\n")
    target = tmp_path / "new/config.yaml"
    prepared = prepare_yaml_write(target, b"mission_type_activations: []\n", section="activation", inputs=(observe_yaml_input(source),))
    assert apply_yaml_write(prepared)
    if damage == "replace":
        replacement = tmp_path / "replacement"
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
    elif damage == "hardlink":
        os.link(target, tmp_path / "alias")
    elif damage == "symlink":
        target.rename(tmp_path / "other")
        target.symlink_to(tmp_path / "other")
    elif damage == "parent":
        target.parent.rename(tmp_path / "old")
        target.parent.mkdir()
        (tmp_path / "old/config.yaml").rename(target)
    else:
        source.write_text("source: false\n")
    with pytest.raises(ValueError):
        prepared.recheck_applied()


def test_failed_yaml_creation_does_not_mint_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    from charter.activation.charter_yaml_io import apply_yaml_write, prepare_yaml_write

    prepared = prepare_yaml_write(tmp_path / "config.yaml", b"mission_type_activations: []\n", section="activation")

    def fail(*args: object, **kwargs: object) -> int:
        raise OSError("injected open failure")

    monkeypatch.setattr(os, "open", fail)
    with pytest.raises(OSError, match="injected"):
        apply_yaml_write(prepared)
    with pytest.raises(ValueError, match="no completion receipt"):
        prepared.recheck_applied()


def test_catalog_field_from_document_accepts_a_mappingproxytype_document() -> None:
    """PR-FRESH2-002 (#5257, HALT round-3 operator ruling):
    ``catalog_field_from_document`` must gate on ``collections.abc.Mapping``,
    not the narrower ``dict``.

    RED pre-fix: a ``types.MappingProxyType`` document -- Mapping-like but
    not a ``dict`` subclass -- failed ``isinstance(document, dict)`` and
    ``catalog_field_from_document`` returned ``None`` even though
    ``catalog.mission`` was genuinely present and valid. GREEN post-fix:
    the same document's mission is read through.
    """
    document = types.MappingProxyType(
        {
            "catalog": types.MappingProxyType(
                {
                    "mission": "software-dev",
                    "template_set": "software-dev-default",
                }
            )
        }
    )

    assert catalog_field_from_document(document, "mission") == "software-dev"
    assert catalog_field_from_document(document, "template_set") == "software-dev-default"


def test_catalog_field_from_document_rejects_a_plain_get_only_object() -> None:
    """A plain object exposing only a ``.get`` method (not a real
    ``collections.abc.Mapping``) is NOT treated as a document -- the fix
    widens the predicate from ``dict`` to ``Mapping``, it does not widen it
    to "anything duck-typed with ``.get``". This pins that the tightened
    predicate is still a real ``isinstance`` check, not a ``hasattr``
    duck-type check in disguise.
    """

    class GetOnly:
        def get(self, key: str, default: object = None) -> object:
            return {"mission": "software-dev"}.get(key, default)

    assert catalog_field_from_document(GetOnly(), "mission") is None
