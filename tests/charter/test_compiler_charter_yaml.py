"""Tests for ``write_compiled_charter``'s charter.yaml partial/merge write.

consolidate-charter-bundle WP03 (T011/T012/T015): the compile pipeline no
longer overwrites ``charter.md`` (data-model.md Landmine 3 -- the #2772
clobber, one level down, on a now-tracked file) or emits
``references.yaml`` (retired). Instead it refreshes ONLY the DERIVED
``catalog``/``metadata`` sections of ``charter.yaml`` through the shared
INV-9 write helper, preserving AUTHORED ``governance``/``directives``/
activation/``overrides`` byte-for-byte via a ruamel round-trip.

Authoritative: ``kitty-specs/consolidate-charter-bundle-01KXSYB9/
data-model.md`` (Landmine 3, INV-9), ``contracts/charter-yaml-schema.md``
(G5).
"""

from __future__ import annotations

from pathlib import Path
import os

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import CompiledCharter, compile_charter, write_compiled_charter
from charter.activation.interview import default_interview
from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

pytestmark = pytest.mark.fast

_PRESET_HEADER = "name: default\ndescription: fixture\n"


def _seed_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str | None) -> Path:
    """Point the built-in pack root at a tmp pack whose ``default`` preset is *body* (absent when ``None``)."""
    packs_root = tmp_path / "packs-root"
    presets = packs_root / "built-in" / "presets"
    presets.mkdir(parents=True)
    seed = presets / "default.yaml"
    if body is not None:
        seed.write_text(body, encoding="utf-8")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return seed


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("body", [b"null\n", b"~ # keep\n", b"---\n...\n", b"42: user-value\n"])
def test_provision_supported_yaml_documents(tmp_path: Path, pointer: bool, body: bytes) -> None:
    from charter.activation.compiler import provision_mission_type_activations
    from charter.activation.compiler import default_preset_mission_types

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    if pointer:
        config.write_bytes(b"charter: policy.yaml\n")
    target.write_bytes(body)

    assert provision_mission_type_activations(tmp_path) is True
    persisted = YAML().load(target.read_bytes())
    assert isinstance(persisted, dict)
    assert persisted["mission_type_activations"] == default_preset_mission_types()
    if b"42:" in body:
        assert target.read_bytes().startswith(body)
        assert persisted[42] == "user-value"
    if b"# keep" in body:
        assert b"# keep\n" in target.read_bytes()
    if body.startswith(b"---"):
        assert target.read_bytes().startswith(b"---\n")
        assert target.read_bytes().endswith(b"...\n")
    before = snapshot({"project": tmp_path})
    assert provision_mission_type_activations(tmp_path) is False
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("pointer", [False, True])
def test_provision_preserves_complete_authored_bytes(tmp_path: Path, pointer: bool) -> None:
    from charter.activation.compiler import provision_mission_type_activations
    from charter.activation.compiler import default_preset_mission_types

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    authored = (
        b'# authored policy\nmetadata:\n  label: "keep quoted"\n'
        b"  choices:\n    - first\n    - second\n\n"
        b"overrides:\n  note: |\n    keep this text\n    and spacing\n"
        b"catalog:\n  languages:\n    - python\n"
        b"charter:\n  synthesis_inputs: [] # legacy namespace\n"
    )
    if pointer:
        config.write_bytes(b"charter: policy.yaml # non-default target\n")
    target.write_bytes(authored)
    config_before = config.read_bytes(), config.stat().st_mode, config.stat().st_mtime_ns

    assert provision_mission_type_activations(tmp_path) is True

    raw = target.read_bytes()
    assert YAML().load(raw)["mission_type_activations"] == default_preset_mission_types()
    assert raw.startswith(authored), "Provisioning reformatted unowned authored spans"
    if pointer:
        assert (config.read_bytes(), config.stat().st_mode, config.stat().st_mtime_ns) == config_before


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"# comment-only without newline",
        b"# heading\n--- # start\n# before null\nNULL # rationale\n... # end\n",
        b"--- ~ # rationale\n... # end\n",
        b"%YAML 1.2\n---\n# empty document\n... # end\n",
        b"!!null null # explicit tag\n",
        b"!custom key: user-value\n.nan: nan-key\n",
        b"42: user-value\n0x10: hexadecimal\ntrue: boolean\nnull: null-key\n2026-09-06: date\n? [one, two]\n: complex-key\n",
        b"? {left: right}\n: complex-map-key\n",
        b"--- # start\r\n~ # rationale\r\n... # end\r\n",
        b"defaults: &defaults {label: authored}\nmetadata: *defaults\n",
        b"defaults: &defaults {label: authored}\n<<: *defaults\n",
        b"{42: user-value, metadata: {label: authored}} # flow tail\n",
    ],
)
def test_provision_round_trip_input_classes(tmp_path: Path, pointer: bool, body: bytes) -> None:
    from charter.activation.compiler import prepare_mission_type_activations, provision_mission_type_activations
    from charter.activation.compiler import default_preset_mission_types

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "authored.yaml" if pointer else config
    if pointer:
        config.write_bytes(b"charter: authored.yaml # selected target\n")
    target.write_bytes(body)
    before = snapshot({"project": tmp_path})
    prepared = prepare_mission_type_activations(tmp_path)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert YAML().load(prepared.write.desired_bytes)["mission_type_activations"] == default_preset_mission_types()
    assert provision_mission_type_activations(tmp_path)
    assert target.read_bytes() == prepared.write.desired_bytes
    original = YAML().load(body)
    if isinstance(original, dict):
        if not body.startswith(b"{"):
            assert target.read_bytes().startswith(body)
        else:
            assert target.read_bytes().startswith(body.rsplit(b"}", 1)[0])
            assert target.read_bytes().endswith(b" # flow tail\n")
    else:
        for line in body.splitlines():
            if b"#" in line:
                comment = line[line.index(b"#") :]
                assert target.read_bytes().count(comment) == 1
        if b"..." in body:
            assert target.read_bytes().endswith(body[body.index(b"...") :])
        if body.startswith(b"%YAML"):
            assert target.read_bytes().startswith(b"%YAML 1.2\n---\n")
    effects = net_delta(before, snapshot({"project": tmp_path}))
    assert {(effect.root, effect.path, effect.action) for effect in effects} == {("project", "authored.yaml" if pointer else ".kittify/config.yaml", "update")}
    after = snapshot({"project": tmp_path})
    assert provision_mission_type_activations(tmp_path) is False
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("activation", [None, "[]", "[custom-mission, research]"])
def test_prepared_provisioning_exact_delta_and_repeats(tmp_path: Path, pointer: bool, activation: str | None) -> None:
    from charter.activation.compiler import prepare_mission_type_activations
    from charter.activation.compiler import default_preset_mission_types
    from charter.activation.pack_context import PackContext

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "authored.yaml" if pointer else config
    if pointer:
        config.write_text("charter: authored.yaml # keep pointer\n", encoding="utf-8")
    authored = b'# policy\nmetadata:\n  tags:\n    - "keep"\n\n'
    target.write_bytes(authored + (f"mission_type_activations: {activation}\n".encode() if activation else b""))
    target.chmod(0o640)
    os.utime(target, ns=(1_000_000_000, 1_000_000_000))
    before = snapshot({"project": tmp_path})

    prepared = prepare_mission_type_activations(tmp_path)

    assert_unchanged(before, snapshot({"project": tmp_path}))
    expected = default_preset_mission_types() if activation is None else YAML().load(activation)
    assert prepared.mission_type_activations == tuple(expected)
    assert prepared.write.target == target
    assert prepared.apply() is (activation is None)
    after = snapshot({"project": tmp_path})
    effects = net_delta(before, after)
    assert {(effect.root, effect.path, effect.action) for effect in effects} == (
        {("project", "authored.yaml" if pointer else ".kittify/config.yaml", "update")} if activation is None else set()
    )
    assert target.read_bytes() == prepared.write.desired_bytes
    assert target.read_bytes().startswith(authored)
    assert target.stat().st_mode & 0o777 == 0o640
    assert PackContext.from_config(tmp_path).activated_mission_types == frozenset(expected)
    for _ in range(2):
        assert prepare_mission_type_activations(tmp_path).apply() is False
        assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("pointer", [False, True])
def test_existing_key_never_reads_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pointer: bool) -> None:
    from charter.activation import compiler

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    if pointer:
        config.write_text("charter: policy.yaml\n", encoding="utf-8")
    target.write_text("mission_type_activations: []\n", encoding="utf-8")

    def forbidden() -> list[str]:
        pytest.fail("Existing activation must not read the default preset")

    monkeypatch.setattr(compiler, "default_preset_mission_types", forbidden)
    before = snapshot({"project": tmp_path})
    assert compiler.prepare_mission_type_activations(tmp_path).apply() is False
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("race", ["config", "target", "same-bytes", "mode", "seed", "parent", "prepared-bytes"])
def test_provisioning_refuses_changed_inputs_before_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race: str) -> None:
    from dataclasses import replace
    from charter.activation import compiler

    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    parent = project / "policy"
    parent.mkdir()
    target = parent / "charter.yaml"
    target.write_text("metadata: {}\n", encoding="utf-8")
    config.write_text("charter: policy/charter.yaml\n", encoding="utf-8")
    seed = _seed_preset(tmp_path, monkeypatch, (Path(__file__).resolve().parents[2] / "packs/built-in/presets/default.yaml").read_text(encoding="utf-8"))
    prepared = compiler.prepare_mission_type_activations(project)
    if race == "config":
        config.write_text("charter: other.yaml\n", encoding="utf-8")
    elif race == "target":
        target.write_text("metadata: {user: changed}\n", encoding="utf-8")
    elif race == "same-bytes":
        target.write_bytes(target.read_bytes())
        os.utime(target, ns=(1_000_000_000, 1_000_000_000))
    elif race == "mode":
        target.chmod(0o600)
    elif race == "seed":
        seed.write_bytes(seed.read_bytes() + b"# changed\n")
    elif race == "parent":
        parent.rename(project / "sentinel")
        parent.symlink_to(project / "sentinel", target_is_directory=True)
    else:
        prepared = replace(prepared, write=replace(prepared.write, desired_bytes=b"forged: true\n"))
    before = snapshot({"sandbox": tmp_path})
    with pytest.raises(ValueError, match="precondition_changed|Unsafe YAML input"):
        prepared.apply()
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("body", ["null", "scalar", "{}"])
@pytest.mark.parametrize("pointer", [False, True])
def test_invalid_authored_activation_is_preserved(tmp_path: Path, body: str, pointer: bool) -> None:
    from charter.activation.compiler import prepare_mission_type_activations

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    if pointer:
        config.write_text("charter: policy.yaml\n", encoding="utf-8")
    target.write_text(f"mission_type_activations: {body}\n", encoding="utf-8")
    before = snapshot({"project": tmp_path})
    with pytest.raises(ValueError, match="must be a list"):
        prepare_mission_type_activations(tmp_path)
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize(
    "seed_body",
    [
        None,
        "[broken",
        "{}",
        _PRESET_HEADER,
        _PRESET_HEADER + "mission_type_activations: []\n",
        _PRESET_HEADER + "mission_type_activations: scalar\n",
    ],
)
def test_invalid_seed_is_not_empty_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed_body: str | None) -> None:
    from charter.activation import compiler

    config = tmp_path / "project/.kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("vcs: {type: git}\n", encoding="utf-8")
    seed = _seed_preset(tmp_path, monkeypatch, seed_body)
    before = snapshot({"sandbox": tmp_path})
    with pytest.raises(compiler.DefaultPresetMissingError) as caught:
        compiler.prepare_mission_type_activations(config.parent.parent)
    assert caught.value.code == "DEFAULT_PRESET_MISSING"
    assert str(seed) in caught.value.body
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("negative_control", [False, True])
def test_preparation_has_no_transient_write_attempts(tmp_path: Path, pointer: bool, negative_control: bool) -> None:
    import sys
    from tests.upgrade.preview_support.process import child_environment, run_process

    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("charter: policy.yaml\n" if pointer else "vcs: {type: git}\n", encoding="utf-8")
    if pointer:
        (project / "policy.yaml").write_text("metadata: {}\n", encoding="utf-8")
    env = child_environment(tmp_path / "child")
    env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "1"  # run_process must bind zero last.
    before = snapshot({"project": project})
    code = r"""
import json, os, sys
from pathlib import Path
from tests.upgrade.preview_support.write_observer import EVENTS
attempts = []
def deny(event, args):
    write_open = event == "open" and bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
    if event in EVENTS or write_open:
        attempts.append(event)
        raise PermissionError("owner write attempt")
sys.addaudithook(deny)
from charter.activation.compiler import prepare_mission_type_activations
assert os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] == "0"
try:
    prepared = prepare_mission_type_activations(Path(sys.argv[1]))
    assert prepared.write.changed and prepared.mission_type_activations
    if sys.argv[2] == "True":
        Path(sys.argv[1], "transient").write_bytes(b"forbidden")
except PermissionError:
    assert sys.argv[2] == "True"
print(json.dumps({"attempts": attempts, "sync": os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"]}))
"""
    result = run_process([sys.executable, "-c", code, str(project), str(negative_control)], Path(__file__).resolve().parents[2], env)
    result.require_success()
    assert result.json() == {"attempts": ["open"] if negative_control else [], "sync": "0"}
    assert_unchanged(before, snapshot({"project": project}))


@pytest.mark.parametrize("mutation", ["omit", "wrong-target", "comment", "sequence", "empty-as-missing", "resave", "forged-bytes"])
def test_provisioning_oracle_rejects_faulty_application(tmp_path: Path, mutation: str) -> None:
    """Corrupt disposable outcomes to prove the positive assertions can fail."""
    from charter.activation.compiler import prepare_mission_type_activations

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("charter: policy.yaml\n", encoding="utf-8")
    target = tmp_path / "policy.yaml"
    authored = b"# authored\nmetadata:\n  choices:\n    - one\n"
    target.write_bytes(authored + (b"mission_type_activations: []\n" if mutation == "empty-as-missing" else b""))
    before = snapshot({"project": tmp_path})
    prepared = prepare_mission_type_activations(tmp_path)
    if mutation != "omit":
        prepared.apply()
    if mutation == "wrong-target":
        config.write_bytes(prepared.write.desired_bytes)
        target.write_bytes(authored)
    elif mutation == "comment":
        target.write_bytes(target.read_bytes().replace(b"# authored", b"# changed"))
    elif mutation == "sequence":
        target.write_bytes(target.read_bytes().replace(b"    - one", b"  - one"))
    elif mutation == "empty-as-missing":
        target.write_bytes(target.read_bytes().replace(b"[]", b"[research]"))
    elif mutation == "resave":
        before = snapshot({"project": tmp_path})
        os.utime(target, ns=(1_000_000_000, 1_000_000_000))
    elif mutation == "forged-bytes":
        target.write_bytes(b"mission_type_activations: [forged]\n")

    with pytest.raises(AssertionError):
        if mutation in {"empty-as-missing", "resave"}:
            assert_unchanged(before, snapshot({"project": tmp_path}))
        else:
            assert target.read_bytes() == prepared.write.desired_bytes
            assert {(e.path, e.action) for e in net_delta(before, snapshot({"project": tmp_path}))} == {("policy.yaml", "update")}


_AUTHORED_FIXTURE = """\
schema_version: "2.0.0"
governance:
  testing:
    min_coverage: 87  # AUTHORED-GOVERNANCE-SENTINEL
  quality: {}
  commits: {}
  performance: {}
  branch_strategy: {}
  doctrine: {}
  activations: []
  enforcement: {}
directives:
  directives:
  - id: DIRECTIVE_001
    title: AUTHORED-DIRECTIVE-SENTINEL
    description: ''
    severity: warn
    references: []
catalog:
  mission: stale-mission
  template_set: stale-template-set
  languages: []
  references: []
activated_kinds:
- directives
activated_directives:
- 001-architectural-integrity-standard  # AUTHORED-ACTIVATION-SENTINEL
overrides:
  some-future-key: authored-override-sentinel
metadata:
  generated_at: '2020-01-01T00:00:00Z'
  bundle_schema_version: 2
"""


def _compiled() -> CompiledCharter:
    interview = default_interview(mission="software-dev", profile="minimal")
    return compile_charter(mission="software-dev", interview=interview)


class TestBootstrapCreate:
    """charter.yaml absent -- a bootstrap create, NOT the Landmine 3 clobber."""

    def test_creates_charter_yaml_not_charter_md(self, tmp_path: Path) -> None:
        compiled = _compiled()

        result = write_compiled_charter(tmp_path, compiled, force=True)

        assert result.files_written == ["charter.yaml"]
        assert (tmp_path / "charter.yaml").exists()
        assert not (tmp_path / "charter.md").exists()
        assert not (tmp_path / "references.yaml").exists()

    def test_bootstrapped_catalog_matches_compiled_references(self, tmp_path: Path) -> None:
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        catalog = document["catalog"]
        assert catalog["mission"] == compiled.mission
        assert catalog["template_set"] == compiled.template_set
        assert len(catalog["references"]) == len(compiled.references)

    def test_bootstrapped_activation_keys_absent_without_config(self, tmp_path: Path) -> None:
        """No repo_root -> no config.yaml to read -> activation stays absent
        (three-state None == default-pack fallback, contract G3)."""
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        assert "activated_directives" not in document

    def test_bootstrapped_governance_and_directives_are_empty_defaults(self, tmp_path: Path) -> None:
        """No repo_root -> no legacy triad to seed from -> empty AUTHORED
        defaults (nothing has been authored yet)."""
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        assert document["directives"]["directives"] == []


class TestPartialMergeRefresh:
    """charter.yaml already exists -- the Landmine 3 regression guard."""

    def _seed(self, tmp_path: Path) -> Path:
        charter_yaml_path = tmp_path / "charter.yaml"
        charter_yaml_path.write_text(_AUTHORED_FIXTURE, encoding="utf-8")
        return charter_yaml_path

    def test_authored_governance_survives_refresh(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        surviving = (tmp_path / "charter.yaml").read_text(encoding="utf-8")
        assert "AUTHORED-GOVERNANCE-SENTINEL" in surviving
        assert "min_coverage: 87" in surviving

    def test_authored_directives_survive_refresh(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        surviving = (tmp_path / "charter.yaml").read_text(encoding="utf-8")
        assert "AUTHORED-DIRECTIVE-SENTINEL" in surviving

    def test_authored_activation_survives_refresh(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        surviving = (tmp_path / "charter.yaml").read_text(encoding="utf-8")
        assert "AUTHORED-ACTIVATION-SENTINEL" in surviving
        assert "001-architectural-integrity-standard" in surviving

    def test_authored_overrides_survive_refresh(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        surviving = (tmp_path / "charter.yaml").read_text(encoding="utf-8")
        assert "authored-override-sentinel" in surviving

    def test_catalog_is_refreshed_from_compiled_state(self, tmp_path: Path) -> None:
        """The DERIVED section is the one thing that IS expected to change."""
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        assert document["catalog"]["mission"] == compiled.mission
        assert document["catalog"]["mission"] != "stale-mission"

    def test_metadata_generated_at_is_refreshed(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        assert document["metadata"]["generated_at"] != "2020-01-01T00:00:00Z"
        assert document["metadata"]["bundle_schema_version"] == 2

    def test_metadata_generated_at_matches_pre_migration_golden_bytes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SC-004 persisted-artifact golden (kernel-clock-single-door WP07).

        Captured from the PRE-migration tree (before ``compiler.py`` routed
        onto the door): under a frozen instant of
        ``2026-11-02T14:15:16.654321+00:00``, the raw
        ``datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`` call
        ``_build_metadata_dict`` used to make persisted the literal
        timestamp ``2026-11-02T14:15:16Z`` into ``charter.yaml``'s
        ``metadata.generated_at``. This test freezes the door's
        ``DEFAULT_CLOCK`` (the seam the migrated call now reads through via
        ``now_utc_stamp()``) to that exact instant and asserts the persisted
        bytes this WP's migrated code writes are byte-identical to that
        pre-migration golden.
        """
        import kernel.clock as clock_module
        from kernel.clock import UTC, FrozenClock, datetime as door_datetime

        fixed = door_datetime(2026, 11, 2, 14, 15, 16, 654321, tzinfo=UTC)
        monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=fixed))

        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        yaml = YAML()
        document = yaml.load((tmp_path / "charter.yaml").read_text(encoding="utf-8"))
        assert document["metadata"]["generated_at"] == "2026-11-02T14:15:16Z"

    def test_refresh_never_writes_charter_md_or_references_yaml(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=True)

        assert not (tmp_path / "charter.md").exists()
        assert not (tmp_path / "references.yaml").exists()

    def test_survives_refresh_without_force(self, tmp_path: Path) -> None:
        """force no longer gates anything destructive -- a merge refresh is
        always safe, force=False or not."""
        self._seed(tmp_path)
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled, force=False)

        surviving = (tmp_path / "charter.yaml").read_text(encoding="utf-8")
        assert "AUTHORED-GOVERNANCE-SENTINEL" in surviving


class TestConfigPointerMinting:
    """WP02-review gap (T014): bootstrap must ALSO mint config.yaml's
    ``charter:`` pointer, or a project that never runs the WP07 migration
    falls to the config-activation branch permanently (split-brain)."""

    def test_bootstrap_mints_pointer_into_absent_config(self, tmp_path: Path) -> None:
        """No config.yaml at all -> bootstrap creates one containing just
        the pointer (does not depend on ``spec-kitty init`` ordering)."""
        output_dir = tmp_path / ".kittify" / "charter"
        compiled = _compiled()

        write_compiled_charter(output_dir, compiled, repo_root=tmp_path)

        config_path = tmp_path / ".kittify" / "config.yaml"
        assert config_path.exists()
        yaml = YAML()
        config = yaml.load(config_path.read_text(encoding="utf-8"))
        assert config["charter"] == ".kittify/charter/charter.yaml"

    def test_bootstrap_mints_pointer_preserving_other_config_keys(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "vcs:\n  type: git\n# a comment that must survive\nproject:\n  slug: my-project\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / ".kittify" / "charter"
        compiled = _compiled()

        write_compiled_charter(output_dir, compiled, repo_root=tmp_path)

        surviving = config_path.read_text(encoding="utf-8")
        assert "# a comment that must survive" in surviving
        assert "slug: my-project" in surviving
        yaml = YAML()
        config = yaml.load(surviving)
        assert config["vcs"]["type"] == "git"
        assert config["charter"] == ".kittify/charter/charter.yaml"

    def test_no_repo_root_does_not_touch_config(self, tmp_path: Path) -> None:
        """No repo_root -> no config.yaml resolution context -> pointer is
        never minted (mirrors the existing 'activation stays absent'
        contract for the no-repo_root bootstrap path)."""
        compiled = _compiled()

        write_compiled_charter(tmp_path, compiled)

        assert not (tmp_path / "config.yaml").exists()
        assert not (tmp_path / ".kittify" / "config.yaml").exists()

    def test_pointer_not_reminted_on_refresh_of_existing_charter_yaml(self, tmp_path: Path) -> None:
        """Once charter.yaml exists, writes are a partial-merge refresh (not
        bootstrap) -- the config.yaml pointer path is not touched again."""
        charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        charter_yaml_path.write_text(_AUTHORED_FIXTURE, encoding="utf-8")
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("vcs:\n  type: git\n", encoding="utf-8")
        compiled = _compiled()

        write_compiled_charter(charter_yaml_path.parent, compiled, repo_root=tmp_path)

        surviving = config_path.read_text(encoding="utf-8")
        assert "charter:" not in surviving
