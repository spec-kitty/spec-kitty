"""Identity index: token <-> declared id <-> stem for every activatable kind (#6406, FR-006, NFR-003)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
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
    index = IdentityIndex(org_roots=[root], _offering_root=tmp_path / "none")
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
