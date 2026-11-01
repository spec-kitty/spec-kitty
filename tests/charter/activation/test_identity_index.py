"""Identity index: token <-> declared id <-> stem for every activatable kind (#6406, FR-006, NFR-003)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
from charter.activation.activation_engine import ActivationIdCollisionError
from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind

pytestmark = [pytest.mark.unit, pytest.mark.fast]

D, T = ArtifactKind.DIRECTIVE, ArtifactKind.TACTIC

#: kind -> (org stem, org declared id, project stem, project declared id)
_STEM_NE_ID = {
    ArtifactKind.DIRECTIVE: ("qa-003-no-fake-green", "QA_003", "proj-policy", "PROJ_POLICY"),
    ArtifactKind.TACTIC: ("qa-tactic-seven", "qa-seven", "proj-tactic", "proj-tac-id"),
    ArtifactKind.PARADIGM: ("qa-paradigm-file", "qa-paradigm-id", "proj-paradigm", "proj-par-id"),
    ArtifactKind.STYLEGUIDE: ("qa-style-file", "qa-style-id", "proj-style", "proj-sty-id"),
    ArtifactKind.TOOLGUIDE: ("qa-tool-file", "qa-tool-id", "proj-tool", "proj-tool-id"),
    ArtifactKind.PROCEDURE: ("qa-proc-file", "qa-proc-id", "proj-proc", "proj-proc-id"),
    ArtifactKind.AGENT_PROFILE: ("qa-profile-file", "qa-profile-id", "proj-profile", "proj-profile-id"),
    ArtifactKind.MISSION_STEP_CONTRACT: ("qa-step-file", "qa-step-id", "proj-step", "proj-step-id"),
    ArtifactKind.GLOSSARY_PACK: ("qa-glossary-file", "qa-glossary-id", "proj-glossary", "proj-glossary-id"),
    ArtifactKind.SKILL: ("qa-skill-file", "qa-skill-id", "proj-skill", "proj-skill-id"),
}
#: Activatable kinds deliberately not parametrised, with the reason.
_EXPLICIT_SKIPS = {
    ArtifactKind.ANTI_PATTERN: "re-kinded node inside another kind's graph fragment, never a standalone file; covered by test_anti_pattern_tokens_pass_through",
}
_ACTIVATABLE = [kind for kind in ArtifactKind if kind.activatable]
_KINDS = [kind for kind in _ACTIVATABLE if kind not in _EXPLICIT_SKIPS]


def test_parametrised_kinds_equal_activatable_minus_explicit_skips() -> None:
    assert set(_STEM_NE_ID) == set(_KINDS)
    assert set(_KINDS) | set(_EXPLICIT_SKIPS) == set(_ACTIVATABLE)
    assert all(reason for reason in _EXPLICIT_SKIPS.values())


def _write(directory: Path, kind: ArtifactKind, stem: str, declared: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    field = "profile-id" if kind is ArtifactKind.AGENT_PROFILE else "id"
    suffix = kind.glob_pattern[1:]
    (directory / f"{stem}{suffix}").write_text(f"schema_version: '1.0'\n{field}: {declared}\ntitle: {stem}\n", encoding="utf-8")


def _register_org(root: Path, *packs: Path) -> None:
    config = {"charter_packs": {"org": {"packs": [{"name": p.name, "local_path": str(p)} for p in packs]}}}
    with (root / ".kittify" / "config.yaml").open("w") as stream:
        YAML().dump(config, stream)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    org = tmp_path / "acme"
    for kind, (org_stem, org_id, proj_stem, proj_id) in ((k, _STEM_NE_ID[k]) for k in _KINDS):
        _write(org / kind.plural, kind, org_stem, org_id)
        _write(tmp_path / ".kittify" / "charter-packs" / PROJECT_KIND_DIRS[kind], kind, proj_stem, proj_id)
    _register_org(tmp_path, org)
    return tmp_path


@pytest.mark.parametrize("kind", _KINDS)
def test_every_kind_resolves_stem_and_declared_id_tokens_per_layer(project: Path, kind: ArtifactKind) -> None:
    org_stem, org_id, proj_stem, proj_id = _STEM_NE_ID[kind]
    index = IdentityIndex.build(project)
    for stem, declared, layer in ((org_stem, org_id, "org"), (proj_stem, proj_id, "project")):
        assert index.declared_id(kind, stem) == declared
        assert index.declared_id(kind, declared) == declared
        assert index.stem(kind, declared) == stem
        assert index.stem(kind, stem) == stem
        assert index.knows(kind, stem) and index.knows(kind, declared)
        assert index.source_layer(kind, declared) == layer
        assert index.source_layer(kind, stem) == layer
    # unknown token, with the known tokens above as positive control
    assert index.declared_id(kind, "no-such-artifact-anywhere") is None
    assert index.knows(kind, "no-such-artifact-anywhere") is False
    assert index.stem(kind, "no-such-artifact-anywhere") is None
    assert index.source_layer(kind, "no-such-artifact-anywhere") is None


def test_built_in_directive_stem_maps_to_declared_id() -> None:
    index = IdentityIndex.build(Path("/nonexistent-project-root"))
    assert index.declared_id(D, "001-architectural-integrity-standard") == "DIRECTIVE_001"
    assert index.stem(D, "DIRECTIVE_001") == "001-architectural-integrity-standard"
    assert index.source_layer(D, "DIRECTIVE_001") == "built-in"


def test_project_wins_over_org_for_same_declared_id(project: Path) -> None:
    _write(project / ".kittify" / "charter-packs" / PROJECT_KIND_DIRS[T], T, "project-copy", "qa-seven")
    index = IdentityIndex.build(project)
    assert index.source_layer(T, "qa-seven") == "project"
    assert index.stem(T, "qa-seven") == "project-copy"
    # control: the org file is still reachable by its own stem
    assert index.source_layer(T, "qa-tactic-seven") == "org"


def test_stem_wins_over_declared_id_collision(project: Path) -> None:
    org = project / "acme"
    # A's stem == B's declared id
    _write(org / "tactics", T, "clash", "a-id")
    _write(org / "tactics", T, "b-file", "clash")
    index = IdentityIndex.build(project)
    assert index.declared_id(T, "clash") == "a-id"
    assert index.declared_id(T, "b-file") == "clash"  # control: B stays reachable by its stem


def test_directive_selection_id_prefers_declared_id(project: Path) -> None:
    org = project / "acme"
    _write(org / "directives", D, "clash", "A_ID")
    _write(org / "directives", D, "b-file", "clash")
    index = IdentityIndex.build(project)
    assert index.declared_id(D, "clash") == "A_ID"
    assert index.selection_id(D, "clash") == "clash"  # declared id of b-file wins, mirrors resolve_selected_id_to_stem
    assert index.stem(D, index.selection_id(D, "clash") or "") == "b-file"


def test_directive_normaliser_fallback_only_when_normalised_id_known(project: Path) -> None:
    index = IdentityIndex.build(project)
    assert index.declared_id(D, "1") == "DIRECTIVE_001"
    assert index.declared_id(D, "24") == "DIRECTIVE_024"
    assert index.declared_id(D, "DIRECTIVE_9999") is None
    assert index.declared_id(D, "9999") is None


def test_anti_pattern_tokens_pass_through() -> None:
    index = IdentityIndex.build(Path("/nonexistent-project-root"))
    assert index.activation_id(ArtifactKind.ANTI_PATTERN, "some-anti-pattern", []) == "some-anti-pattern"


def test_activation_id_known_unknown_and_warning(project: Path) -> None:
    index = IdentityIndex.build(project)
    warnings: list[str] = []
    assert index.activation_id(T, "qa-tactic-seven", warnings) == "qa-seven"
    assert warnings == []
    assert index.activation_id(T, "ghost", warnings) == "ghost"
    assert len(warnings) == 1 and "ghost" in warnings[0]
    assert index.activation_id(D, "1", warnings) == "DIRECTIVE_001"
    assert len(warnings) == 1  # normalised and known: no new warning
    assert index.activation_id(D, "9999", warnings) == "DIRECTIVE_9999"
    assert len(warnings) == 2  # normalised but unknown: warns


def test_unconfigured_project_has_only_built_ins(tmp_path: Path) -> None:
    index = IdentityIndex.build(tmp_path)
    assert index.knows(D, "DIRECTIVE_001")
    assert index.knows(D, "QA_003") is False


# ---------------------------------------------------------------- NFR-003 ----


@pytest.fixture
def scan_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    calls: list[Path] = []
    original = kind_vocabulary._scan_dir_matches

    def _counted(scan_dir: Path, pattern: str, *, recursive: bool) -> list[Path]:
        calls.append(scan_dir)
        return original(scan_dir, pattern, recursive=recursive)

    monkeypatch.setattr(kind_vocabulary, "_scan_dir_matches", _counted)
    yield calls


def test_scan_count_is_one_per_root_per_kind(project: Path, scan_calls: list[Path]) -> None:
    index = IdentityIndex.build(project)
    assert scan_calls == []  # lazy: build alone does not scan
    stem, declared, p_stem, p_declared = _STEM_NE_ID[T]
    for _ in range(10):
        for token in (stem, declared, p_stem, p_declared, "ghost"):
            index.declared_id(T, token)
            index.knows(T, token)
            index.stem(T, token)
            index.source_layer(T, token)
    # project + org + built-in roots for the tactic kind, each walked once
    expected_roots = 3
    assert len(scan_calls) == expected_roots
    assert len(set(scan_calls)) == expected_roots
    index.declared_id(ArtifactKind.PARADIGM, _STEM_NE_ID[ArtifactKind.PARADIGM][1])
    assert len(scan_calls) == 2 * expected_roots


def test_build_adopts_shared_resolution_pass_and_org_roots(tmp_path: Path) -> None:
    shared = kind_vocabulary.ResolutionPass()
    index = IdentityIndex.build(tmp_path, org_roots=[], resolution_pass=shared)
    assert index._pass is shared
    assert index.org_roots == []
    assert IdentityIndex.build(tmp_path, org_roots=[])._pass is not shared


_EDGE_BODIES: dict[str, bytes] = {
    "plain": b"id: plain-one\ntitle: x\n",
    "dquoted": b'id: "quoted-one"\n',
    "squoted": b"id: 'single'\n",
    "trailing-comment": b"id: tagged # comment\n",
    "block": b"id: |\n  block\n",
    "no-id": b"title: no id here\n",
    "nested-then-top": b"nested:\n  id: inner\nid: outer\n",
    "zero": b"id: 0\n",
    "flow": b"id: [flow]\n",
    "spaced": b"id:   spaced-id   \n",
    "leading-zeros": b"id: 001\n",
    "true": b"id: true\n",
    "True-cap": b"id: True\n",
    "null": b"id: null\n",
    "Null": b"id: Null\n",
    "tilde": b"id: ~\n",
    "yes": b"id: yes\n",
    "float": b"id: 1.50\n",
    "exp": b"id: 1e3\n",
    "hex": b"id: 0x1F\n",
    "octal": b"id: 0o17\n",
    "multi-document": b"id: first\n---\nid: second\n",
    "leading-marker": b"---\nid: lead-marker\n",
    "doc-end": b"id: ended\n...\n",
    "duplicate-key": b"id: one\nid: two\n",
    "crlf": b"id: crlf-id\r\ntitle: x\r\n",
    "bom": b"\xef\xbb\xbfid: bom-id\ntitle: x\n",
    "sequence-after": b"id: seq-after\n- a\n",
    "broken-later-accepted": b"id: ok-id\nother: [unclosed\n",
    "continuation": b"id: first\n  second\ntitle: x\n",
    "continuation-tab": b"id: first\n\tsecond\ntitle: x\n",
    "tab-after-colon": b"id:\ttabbed-id\ntitle: x\n",
    "tab-trailing": b"id: tab-trail\t\ntitle: x\n",
    "no-continuation-next-key": b"id: solo\ntitle: x\n",
}
#: Documented limitation of the fast path: a syntax error elsewhere is not detected cheaply.
_ACCEPTED_DIVERGENCE = {"broken-later-accepted", "sequence-after"}


@pytest.mark.parametrize("name", sorted(set(_EDGE_BODIES) - _ACCEPTED_DIVERGENCE))
def test_declared_id_fast_path_equals_full_parse(tmp_path: Path, name: str) -> None:
    from charter.activation.identity_index import _declared_id_of

    path = tmp_path / "thing.tactic.yaml"
    path.write_bytes(_EDGE_BODIES[name])
    yaml = YAML(typ="safe")
    expected = kind_vocabulary._parse_id(path, "id", yaml)
    assert _declared_id_of(path, "id", yaml, kind_vocabulary.ResolutionPass()) == expected


def test_declared_id_fast_path_accepts_broken_yaml_elsewhere(tmp_path: Path) -> None:
    """Pinned limitation (see ``_declared_id_of``): the full parse says None, the fast path the id."""
    from charter.activation.identity_index import _declared_id_of

    path = tmp_path / "thing.tactic.yaml"
    yaml = YAML(typ="safe")
    for name, expected in (("broken-later-accepted", "ok-id"), ("sequence-after", "seq-after")):
        path.write_bytes(_EDGE_BODIES[name])
        assert kind_vocabulary._parse_id(path, "id", yaml) is None
        assert _declared_id_of(path, "id", yaml, kind_vocabulary.ResolutionPass()) == expected


def _built_in_artifacts() -> list[tuple[ArtifactKind, Path]]:
    root = Path(__file__).resolve().parents[3] / "packs" / "built-in"
    found: list[tuple[ArtifactKind, Path]] = []
    for kind in _ACTIVATABLE:
        if kind.glob_pattern:
            found.extend((kind, path) for path in sorted(root.rglob(kind.glob_pattern)))
    return found


_BUILT_IN = _built_in_artifacts()


def test_built_in_artifacts_are_found() -> None:
    assert _BUILT_IN


@pytest.mark.parametrize("kind,path", _BUILT_IN, ids=[f"{k.value}:{p.name}" for k, p in _BUILT_IN])
def test_declared_id_fast_path_equals_full_parse_on_built_in_packs(kind: ArtifactKind, path: Path) -> None:
    from charter.activation.identity_index import _declared_id_of

    yaml = YAML(typ="safe")
    for id_field in {"id", kind_vocabulary._id_field_for(kind)}:
        expected = kind_vocabulary._parse_id(path, id_field, yaml)
        assert _declared_id_of(path, id_field, yaml, kind_vocabulary.ResolutionPass()) == expected


@pytest.mark.parametrize("name", ["leading-zeros", "true", "null", "float", "exp", "hex", "octal", "multi-document", "duplicate-key", "crlf", "bom"])
def test_index_returns_full_parse_identity(tmp_path: Path, name: str) -> None:
    root = tmp_path / "org"
    (root / "tactics").mkdir(parents=True)
    path = root / "tactics" / "edge.tactic.yaml"
    path.write_bytes(_EDGE_BODIES[name])
    expected = kind_vocabulary._parse_id(path, "id", YAML(typ="safe"))
    index = IdentityIndex(org_roots=[root], offering_root=tmp_path / "none")
    assert index.declared_id(T, "edge") == expected


def test_fast_path_values_never_seed_the_shared_resolution_pass(tmp_path: Path) -> None:
    """Only canonical-reader results enter the shared pass; fast values stay in the index's private cache."""
    from charter.activation.identity_index import _declared_id_of

    path = tmp_path / "plain.tactic.yaml"
    path.write_bytes(b"id: plain-id\ntitle: x\n")
    quoted = tmp_path / "quoted.tactic.yaml"
    quoted.write_bytes(b"id: 'quoted-id'\ntitle: x\n")
    shared, fast = kind_vocabulary.ResolutionPass(), {}
    yaml = YAML(typ="safe")

    assert _declared_id_of(path, "id", yaml, shared, fast) == "plain-id"
    assert _declared_id_of(quoted, "id", yaml, shared, fast) == "quoted-id"

    assert (path, "id") not in shared.ids and fast == {(path, "id"): "plain-id"}
    assert shared.ids == {(quoted, "id"): "quoted-id"}  # the canonical reader did seed this one


def test_lookup_is_stem_first_across_layers_then_declared_id(tmp_path: Path) -> None:
    """A lower layer's stem beats a higher layer's declared id (parity with resolve_artifact_urn)."""
    project = tmp_path / "proj"
    (project / ".kittify").mkdir(parents=True)
    org = tmp_path / "org-pack"
    _write(project / ".kittify" / "charter-packs" / PROJECT_KIND_DIRS[T], T, "high-layer", "shared-name")
    _write(org / "tactics", T, "shared-name", "low-layer-id")
    _register_org(project, org)
    index = IdentityIndex.build(project)

    assert index.declared_id(T, "shared-name") == "low-layer-id"
    assert index.source_layer(T, "shared-name") == "org"


def test_lookup_key_returns_declared_id_for_either_spelling(project: Path) -> None:
    index = IdentityIndex.build(project)
    assert index.lookup_key(T, "qa-tactic-seven") == "qa-seven"
    assert index.lookup_key(T, "qa-seven") == "qa-seven"


def test_lookup_key_unknown_token_falls_back_to_unindexed_key(project: Path) -> None:
    index = IdentityIndex.build(project)
    assert index.lookup_key(T, "ghost") == "ghost"
    assert index.lookup_key(D, "DIRECTIVE_9999") == IdentityIndex.unindexed_key(D, "DIRECTIVE_9999")
    assert index.lookup_key(None, "anything") == "anything"
    assert IdentityIndex.unindexed_key(D, "1") == "DIRECTIVE_001"
    assert IdentityIndex.unindexed_key(T, "1") == "1"


def test_lookup_key_selection_flag_switches_directive_precedence(tmp_path: Path) -> None:
    """selection=True: a declared id beats a coincidentally equal stem; the default is stem first."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    org = tmp_path / "org"
    _write(org / "directives", D, "clash", "A_ID")
    _write(org / "directives", D, "b-file", "clash")
    (tmp_path / ".kittify").mkdir()
    _register_org(tmp_path, org)
    index = IdentityIndex.build(tmp_path)

    assert index.lookup_key(D, "clash") == "A_ID"
    assert index.lookup_key(D, "clash", selection=True) == "clash"


# ------------------------------------------------- #6527: URNs, step contracts --


@pytest.mark.parametrize("kind", _KINDS)
def test_urn_resolves_like_its_bare_token_and_never_comes_back_as_the_stem(project: Path, kind: ArtifactKind) -> None:
    """FR-011: ``<kind>:<id>`` / ``<kind>:<stem>`` name the same artifact; the stem is returned, never the URN."""
    org_stem, org_id, proj_stem, proj_id = _STEM_NE_ID[kind]
    index = IdentityIndex.build(project)
    for stem, declared in ((org_stem, org_id), (proj_stem, proj_id)):
        for urn in (f"{kind.value}:{declared}", f"{kind.value}:{stem}"):
            assert index.stem(kind, urn) == stem
            assert index.declared_id(kind, urn) == declared
            assert index.knows(kind, urn)
            assert index.lookup_key(kind, urn) == declared


def test_urn_of_another_kind_is_not_stripped(project: Path) -> None:
    index = IdentityIndex.build(project)
    assert index.knows(T, "tactic:qa-seven")  # positive control
    assert index.knows(T, "directive:qa-seven") is False
    assert index.stem(T, "directive:qa-seven") is None


def test_directive_urn_uses_the_id_first_rule(project: Path) -> None:
    index = IdentityIndex.build(project)
    assert index.stem(D, "directive:DIRECTIVE_024") == "024-locality-of-change"
    assert index.selection_id(D, "directive:DIRECTIVE_024") == "DIRECTIVE_024"


def test_built_in_step_contracts_are_indexed() -> None:
    """FR-015: the one identity authority covers the built-in ``missions/built_in_step_contracts`` files."""
    kind = ArtifactKind.MISSION_STEP_CONTRACT
    directory = kind_vocabulary._built_in_scan_dir(kind)
    assert directory is not None and directory[1] is False
    stems = sorted(kind_vocabulary._config_stem(path) for path in directory[0].glob(kind.glob_pattern))
    assert stems, "fixture invalid: the built-in pack ships step contracts"
    index = IdentityIndex.build(Path("/nonexistent-project-root"))
    for stem in stems:
        assert index.knows(kind, stem), stem
        assert index.source_layer(kind, stem) == "built-in"
        assert index.stem(kind, f"{kind.value}:{stem}") == stem


def test_step_contract_scan_dir_is_none_when_the_missions_root_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.missions.repository import MissionsRootNotFound
    from charter.offering.missions.step_contracts import MissionStepContractRepository

    def _missing() -> Path:
        raise MissionsRootNotFound("gone")

    monkeypatch.setattr(MissionStepContractRepository, "built_in_dir", staticmethod(_missing))
    assert kind_vocabulary._built_in_scan_dir(ArtifactKind.MISSION_STEP_CONTRACT) is None


def test_step_contract_scan_dir_is_none_when_the_directory_is_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from charter.offering.missions.step_contracts import MissionStepContractRepository

    monkeypatch.setattr(MissionStepContractRepository, "built_in_dir", staticmethod(lambda: tmp_path / "absent"))
    assert kind_vocabulary._built_in_scan_dir(ArtifactKind.MISSION_STEP_CONTRACT) is None


def test_stored_spelling_is_the_stem_for_every_known_spelling(project: Path) -> None:
    index = IdentityIndex.build(project)
    for token in ("qa-tactic-seven", "qa-seven", "tactic:qa-seven"):
        assert index.stored_spelling(T, token) == "qa-tactic-seven"
    assert index.stored_spelling(D, "DIRECTIVE_024") == "024-locality-of-change"
    assert index.stored_spelling(T, "ghost") == "ghost"  # unknown: kept, the caller validates


def test_stored_spelling_refuses_a_declared_id_whose_file_name_another_layer_uses(project: Path) -> None:
    """Decision ``file_name_collision``: an org file reuses the built-in file name for another id."""
    org_file = project / "acme" / "directives" / "024-locality-of-change.directive.yaml"
    _write(org_file.parent, D, "024-locality-of-change", "ACME_024")
    index = IdentityIndex.build(project)
    assert index.knows(D, "DIRECTIVE_024") and index.stem(D, "DIRECTIVE_024") is None
    built_in_scan = kind_vocabulary._built_in_scan_dir(D)
    assert built_in_scan is not None
    built_in_file = next(built_in_scan[0].rglob("024-locality-of-change.directive.yaml"))

    for token in ("DIRECTIVE_024", "directive:DIRECTIVE_024"):
        with pytest.raises(ActivationIdCollisionError) as excinfo:
            index.stored_spelling(D, token)

        assert str(excinfo.value) == (
            "Cannot store directive 'DIRECTIVE_024': its file name '024-locality-of-change' is used by files in more than one layer "
            f"that declare different IDs (the org file {org_file} declares 'ACME_024'; the built-in file {built_in_file} declares 'DIRECTIVE_024'), "
            f"so the file name cannot stand for 'DIRECTIVE_024'. Rename the org file {org_file} so each ID has its own file name."
        )
        assert excinfo.value.kind == "directive" and excinfo.value.artifact_id == "DIRECTIVE_024"
    assert index.stored_spelling(D, "024-locality-of-change") == "024-locality-of-change"  # the file name itself is a stem


def test_file_name_collisions_reports_the_org_file_that_takes_a_built_in_file_name(project: Path) -> None:
    """#6743: one file name, two layers, different declared ids is one collision record."""
    org_file = project / "acme" / "directives" / "024-locality-of-change.directive.yaml"
    _write(org_file.parent, D, "024-locality-of-change", "ACME_024")
    built_in_scan = kind_vocabulary._built_in_scan_dir(D)
    assert built_in_scan is not None
    built_in_file = next(built_in_scan[0].rglob("024-locality-of-change.directive.yaml"))

    index = IdentityIndex.build(project)
    collisions = index.file_name_collisions(kinds=[D])

    assert [c.file_name for c in collisions] == ["024-locality-of-change"]
    collision = collisions[0]
    assert collision.kind is D
    assert [(layer, declared) for layer, declared, _path in collision.declarations] == [("org", "ACME_024"), ("built-in", "DIRECTIVE_024")]
    assert [path for _layer, _declared, path in collision.declarations] == [org_file, built_in_file]
    assert collision.sort_key == ("directive", "024-locality-of-change")


def test_file_name_collisions_are_ordered_by_kind_then_file_name(project: Path) -> None:
    """NFR-002: the record order is stable, so two runs on one tree are byte-identical."""
    _write(project / "acme" / "directives", D, "024-locality-of-change", "ACME_024")
    _write(project / "acme" / "tactics", T, "acceptance-test-first", "acme-atf")

    collisions = IdentityIndex.build(project).file_name_collisions()

    keys = [c.sort_key for c in collisions]
    assert keys == sorted(keys)
    assert ("directive", "024-locality-of-change") in keys
    assert ("tactic", "acceptance-test-first") in keys


def test_file_name_collisions_ignores_a_same_id_override_and_a_disjoint_pack(project: Path) -> None:
    """FR-006 positive/negative control: only a *different* declared id is a collision."""
    org_file = project / "acme" / "directives" / "024-locality-of-change.directive.yaml"
    _write(org_file.parent, D, "024-locality-of-change", "DIRECTIVE_024")  # deliberate same-id override
    assert IdentityIndex.build(project).file_name_collisions(kinds=[D]) == ()

    _write(org_file.parent, D, "acme-024-local", "ACME_024")  # its own file name
    assert IdentityIndex.build(project).file_name_collisions(kinds=[D]) == ()


def test_file_name_collisions_does_not_rescan_the_index_it_reuses(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: the query reads the memoised tables; a second call re-walks nothing."""
    _write(project / "acme" / "directives", D, "024-locality-of-change", "ACME_024")
    index = IdentityIndex.build(project)
    index.file_name_collisions(kinds=[D])  # first call builds the table (one scan)

    def _fail(_kind: ArtifactKind) -> list:  # pragma: no cover - only runs on a regression
        raise AssertionError("file_name_collisions re-scanned an already-built table")

    monkeypatch.setattr(IdentityIndex, "_scan", _fail)
    assert index.file_name_collisions(kinds=[D])[0].file_name == "024-locality-of-change"


# --------------------------------------------------------------------------------------
# The diagnostic and the writer refusal are one computation (#6743, FR-005)
#
# Decision ``file_name_collision``: a file name that files in more than one layer bind to
# different declared ids is a pack-content error. The runtime refuses such an id in every
# writer (#6527) and the authoring diagnostics report it before anyone hits that refusal.
# Both read ``IdentityIndex``, so these tests pin that they name the same file, the same
# layers and the same declared ids for one fixture.
# --------------------------------------------------------------------------------------

FILE_NAME = "024-locality-of-change"
ORG_ID, BUILT_IN_ID = "ACME_024", "DIRECTIVE_024"
_DIRECTIVE = 'schema_version: "1.0"\nid: {id}\ntitle: t\nintent: i\nenforcement: required\n'


def _write_org_directive(project: Path, stem: str, declared: str) -> Path:
    """Write one org-layer directive file and register the pack; return the file."""
    path = project / "acme" / "directives" / f"{stem}.directive.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DIRECTIVE.format(id=declared), encoding="utf-8")
    config = {"charter_packs": {"org": {"packs": [{"name": "acme", "local_path": str(project / "acme")}]}}}
    with (project / ".kittify" / "config.yaml").open("w") as stream:
        YAML().dump(config, stream)
    return path


def _collision_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    return tmp_path


def _built_in_directive_file() -> Path:
    scan_dir = kind_vocabulary._built_in_scan_dir(D)
    assert scan_dir is not None
    return next(scan_dir[0].rglob(f"{FILE_NAME}.directive.yaml"))


def test_diagnostic_declarations_equal_the_writer_refusal_declarations(tmp_path: Path) -> None:
    """One fixture: the collision record and ``ActivationIdCollisionError`` describe the same files."""
    project = _collision_project(tmp_path)
    org_file = _write_org_directive(project, FILE_NAME, ORG_ID)
    built_in_file = _built_in_directive_file()

    index = IdentityIndex.build(project)
    (collision,) = index.file_name_collisions(kinds=[D])

    with pytest.raises(ActivationIdCollisionError) as excinfo:
        index.stored_spelling(D, BUILT_IN_ID)

    assert collision.file_name == excinfo.value.file_name == FILE_NAME
    assert [(layer, declared) for layer, declared, _path in collision.declarations] == [("org", ORG_ID), ("built-in", BUILT_IN_ID)]
    assert list(excinfo.value.declarations) == [(f"{layer} file {path}", declared) for layer, declared, path in collision.declarations]
    assert [org_file, built_in_file] == [path for _layer, _declared, path in collision.declarations]


def test_the_diagnostic_message_offers_the_renamable_file_and_names_both_ids(tmp_path: Path) -> None:
    """FR-004: the message names the file name, the layers, both ids and what to rename."""
    project = _collision_project(tmp_path)
    org_file = _write_org_directive(project, FILE_NAME, ORG_ID)

    (collision,) = IdentityIndex.build(project).file_name_collisions(kinds=[D])
    message = collision.message()

    assert FILE_NAME in message
    assert ORG_ID in message and BUILT_IN_ID in message
    assert "org file" in message and "built-in file" in message
    assert f"Rename the org file {org_file}" in message, "a built-in file cannot be renamed, so the org file is named"


def test_a_same_id_override_is_not_a_collision_and_is_not_refused(tmp_path: Path) -> None:
    """The control: reusing a built-in file name *for the built-in id* stays legal (FR-006)."""
    project = _collision_project(tmp_path)
    _write_org_directive(project, FILE_NAME, BUILT_IN_ID)

    index = IdentityIndex.build(project)

    assert index.file_name_collisions(kinds=[D]) == ()
    assert index.stored_spelling(D, BUILT_IN_ID) == FILE_NAME
