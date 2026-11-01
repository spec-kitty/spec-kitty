"""One stem<->id authority: the ``kind_vocabulary`` resolvers answer from ``IdentityIndex`` (#6433).

The three resolvers keep their public signatures, error types and messages, but the
*rule* they apply is the index's rule. These tests pin both halves of that claim:

* parity -- for every artifact the index indexes, the resolver and the index agree,
  in both directions, across the built-in, org and project layers;
* delegation -- the resolver actually consults the index (a monkeypatched
  ``IdentityIndex`` method is reached), so a second match rule cannot come back;
* the spellings the runtime gate already accepts (``<kind>:<id>`` URNs and
  normalised directive ids such as ``24``) resolve through the facade too, and a
  genuinely unknown token still fails closed with the layer-naming message.

Fixtures are built on disk and passed as data (no git needed): the resolvers take
``offering_root``, ``org_roots`` and ``layer_roots`` explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import kind_vocabulary
from charter.activation.catalog import resolve_offering_root
from charter.activation.identity_index import IdentityIndex
from charter.activation.kind_vocabulary import (
    ArtifactKind,
    UnknownArtifactIdError,
    UnrepresentableDirectiveIdError,
    resolve_artifact_urn,
    resolve_config_id,
    resolve_selected_id_to_stem,
)
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS
from kernel.charter_pack_paths import project_pack_root

pytestmark = [pytest.mark.fast]

#: A built-in directive whose stem and id differ: the round-trip case.
BUILT_IN_STEM, BUILT_IN_ID = "024-locality-of-change", "DIRECTIVE_024"
#: Org artifacts whose file stems differ from their declared ids.
ORG_TAC_STEM, ORG_TAC_ID = "acme-tac-file", "acme-tac-id"
ORG_TOOL_STEM, ORG_TOOL_ID = "acme-tool-file", "acme-tool-id"
ORG_DIR_STEM, ORG_DIR_ID = "acme-directive-file", "ACME_DIRECTIVE"
#: A project-layer tactic.
PROJ_TAC_STEM, PROJ_TAC_ID = "proj-tac", "proj-tac-id"
#: The org file that reuses a built-in directive stem for a *different* id.
SHADOW_ID = "ACME_024"
#: The directive id whose file name no single layer can represent once shadowed.
SHADOW_SHADOWED_ID = BUILT_IN_ID

_TACTIC = "schema_version: '1.0'\nid: {id}\nname: T\npurpose: T.\nsteps:\n  - title: Do\n    description: Do it.\n"
_TOOLGUIDE = 'schema_version: "1.0"\nid: {id}\ntool: acme\ntitle: Acme\nsummary: Acme.\nguide_path: acme.md\napplies_to_languages: []\n'
_DIRECTIVE = 'schema_version: "1.0"\nid: {id}\ntitle: t\nintent: i\nenforcement: optional\n'

_ResolverKwargs = dict[str, object]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _layers(root: Path, *, shadow_directive: bool = False) -> _ResolverKwargs:
    """An org pack plus a project layer, and the three resolver keyword arguments for them."""
    pack = root / "acme"
    _write(pack / "tactics" / f"{ORG_TAC_STEM}.tactic.yaml", _TACTIC.format(id=ORG_TAC_ID))
    _write(pack / "toolguides" / f"{ORG_TOOL_STEM}.toolguide.yaml", _TOOLGUIDE.format(id=ORG_TOOL_ID))
    _write(pack / "directives" / f"{ORG_DIR_STEM}.directive.yaml", _DIRECTIVE.format(id=ORG_DIR_ID))
    if shadow_directive:
        # Two layers bind one directive file name to two different identities.
        _write(pack / "directives" / f"{BUILT_IN_STEM}.directive.yaml", _DIRECTIVE.format(id=SHADOW_ID))
    project = project_pack_root(root)
    _write(project / PROJECT_KIND_DIRS[ArtifactKind.TACTIC] / f"{PROJ_TAC_STEM}.tactic.yaml", _TACTIC.format(id=PROJ_TAC_ID))
    return {"offering_root": resolve_offering_root(), "org_roots": [pack], "layer_roots": {"project": project}}


@pytest.fixture(scope="module")
def layers(tmp_path_factory: pytest.TempPathFactory) -> _ResolverKwargs:
    return _layers(tmp_path_factory.mktemp("identity-layers"))


@pytest.fixture(scope="module")
def shadow_layers(tmp_path_factory: pytest.TempPathFactory) -> _ResolverKwargs:
    return _layers(tmp_path_factory.mktemp("identity-shadow-layers"), shadow_directive=True)


def _index(kwargs: _ResolverKwargs) -> IdentityIndex:
    return IdentityIndex.from_roots(offering_root=kwargs["offering_root"], org_roots=kwargs["org_roots"], layer_roots=kwargs["layer_roots"])  # type: ignore[arg-type]


# ------------------------------------------------------- parity, both ways --


@pytest.mark.parametrize("kind", [ArtifactKind.DIRECTIVE, ArtifactKind.TACTIC, ArtifactKind.TOOLGUIDE], ids=lambda kind: kind.value)
def test_facade_agrees_with_the_index_for_every_indexed_entry(layers: _ResolverKwargs, kind: ArtifactKind) -> None:
    """Every stem and declared id the index holds resolves to the same URN through the facade."""
    index = _index(layers)
    entries = index._table(kind).entries
    assert entries, "fixture must index at least one artifact of this kind"
    # One pass for the whole matrix: the facade still answers from the index, but the
    # layer scans and id reads are memoised (the pattern a real multi-resolve caller uses).
    shared = kind_vocabulary.ResolutionPass()

    for entry in entries:
        expected = f"{kind.value}:{entry.declared_id}"
        assert resolve_artifact_urn(kind, entry.stem, resolution_pass=shared, **layers) == expected, entry.stem  # type: ignore[arg-type]
        assert resolve_artifact_urn(kind, entry.declared_id, resolution_pass=shared, **layers) == expected, entry.declared_id  # type: ignore[arg-type]


def test_urn_and_normalised_directive_id_resolve_like_their_stem(layers: _ResolverKwargs) -> None:
    """The spellings the runtime gate accepts resolve through the facade too (red before #6433)."""
    assert resolve_artifact_urn(ArtifactKind.TACTIC, ORG_TAC_STEM, **layers) == f"tactic:{ORG_TAC_ID}"  # type: ignore[arg-type]
    assert resolve_artifact_urn(ArtifactKind.TACTIC, f"tactic:{ORG_TAC_ID}", **layers) == f"tactic:{ORG_TAC_ID}"  # type: ignore[arg-type]
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, BUILT_IN_STEM, **layers) == f"directive:{BUILT_IN_ID}"  # type: ignore[arg-type]
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, "directive:DIRECTIVE_024", **layers) == f"directive:{BUILT_IN_ID}"  # type: ignore[arg-type]
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, "24", **layers) == f"directive:{BUILT_IN_ID}"  # type: ignore[arg-type]


def test_unknown_token_still_fails_closed_naming_the_searched_layers(layers: _ResolverKwargs) -> None:
    """A token no layer knows refuses with the same message; there is no best-effort widening."""
    with pytest.raises(UnknownArtifactIdError) as caught:
        resolve_artifact_urn(ArtifactKind.TACTIC, "ghost-token", **layers)  # type: ignore[arg-type]

    message = str(caught.value)
    assert "ghost-token" in message
    assert "Searched layers:" in message
    assert "project" in message and "org" in message


def test_anti_pattern_has_no_files_and_still_refuses(layers: _ResolverKwargs) -> None:
    """``anti_pattern`` is an activatable kind with no artifact files: the facade keeps refusing."""
    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(ArtifactKind.ANTI_PATTERN, "any-token", **layers)  # type: ignore[arg-type]


class _IndexStub:
    """An ``IdentityIndex`` stand-in proving the facade's answer comes from the index."""

    def __init__(self, *, declared: str | None = None, stem: str | None = None, has_id: bool = True) -> None:
        self._declared = declared
        self._stem = stem
        self._has_id = has_id

    def declared_id(self, kind: ArtifactKind, token: str) -> str | None:
        return self._declared

    def stem_for_declared_id(self, kind: ArtifactKind, declared_id: str) -> str | None:
        return self._stem

    def has_declared_id(self, kind: ArtifactKind, token: str) -> bool:
        return self._has_id

    def stem(self, kind: ArtifactKind, token: str) -> str | None:
        return self._stem

    def names_a_file(self, kind: ArtifactKind, token: str) -> bool:
        return self._has_id


def test_resolvers_answer_from_the_index(layers: _ResolverKwargs, monkeypatch: pytest.MonkeyPatch) -> None:
    """Delegation proof: each resolver returns the index's answer, not a second match rule's."""
    monkeypatch.setattr(IdentityIndex, "from_roots", classmethod(lambda cls, **kwargs: _IndexStub(declared="FROM-INDEX", stem="STEM-FROM-INDEX")))

    assert resolve_artifact_urn(ArtifactKind.TACTIC, ORG_TAC_STEM, **layers) == "tactic:FROM-INDEX"  # type: ignore[arg-type]
    assert resolve_config_id(f"tactic:{ORG_TAC_ID}", **layers) == "STEM-FROM-INDEX"  # type: ignore[arg-type]
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, ORG_DIR_ID, **layers) == "STEM-FROM-INDEX"  # type: ignore[arg-type]


def test_resolvers_fail_closed_when_the_index_knows_nothing(layers: _ResolverKwargs, monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal is still the facade's, built from the index's negative answer."""
    monkeypatch.setattr(IdentityIndex, "from_roots", classmethod(lambda cls, **kwargs: _IndexStub(declared=None, stem=None, has_id=False)))

    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(ArtifactKind.TACTIC, ORG_TAC_STEM, **layers)  # type: ignore[arg-type]
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_id(f"tactic:{ORG_TAC_ID}", **layers)  # type: ignore[arg-type]
    assert resolve_selected_id_to_stem(ArtifactKind.TACTIC, ORG_TAC_STEM, **layers) is None  # type: ignore[arg-type]


# ------------------------------------------------------- inverse direction --


def test_a_normalised_directive_id_resolves_in_the_id_first_direction(layers: _ResolverKwargs) -> None:
    """``directive:24`` is the spelling the gate and the index accept; the inverse resolves it too (review finding 1)."""
    assert resolve_config_id("directive:24", **layers) == BUILT_IN_STEM  # type: ignore[arg-type]
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, "24", **layers) == BUILT_IN_STEM  # type: ignore[arg-type]


def test_resolve_config_id_returns_the_stem_for_every_layer(layers: _ResolverKwargs) -> None:
    assert resolve_config_id(f"tactic:{ORG_TAC_ID}", **layers) == ORG_TAC_STEM  # type: ignore[arg-type]
    assert resolve_config_id(f"tactic:{PROJ_TAC_ID}", **layers) == PROJ_TAC_STEM  # type: ignore[arg-type]
    assert resolve_config_id(f"directive:{BUILT_IN_ID}", **layers) == BUILT_IN_STEM  # type: ignore[arg-type]
    assert resolve_config_id(f"directive:{ORG_DIR_ID}", **layers) == ORG_DIR_STEM  # type: ignore[arg-type]


def test_a_shared_directive_stem_still_resolves_through_the_stem(shadow_layers: _ResolverKwargs) -> None:
    """A stem input keeps first-match precedence: the file the reader names wins, no round-trip check."""
    assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, BUILT_IN_STEM, **shadow_layers) == f"directive:{SHADOW_ID}"  # type: ignore[arg-type]


def test_resolve_config_id_still_refuses_a_directive_id_no_filename_represents(shadow_layers: _ResolverKwargs) -> None:
    """Positive control: a uniquely named org directive resolves; both ids bound to the shadowed file name do not."""
    assert resolve_config_id(f"directive:{ORG_DIR_ID}", **shadow_layers) == ORG_DIR_STEM  # type: ignore[arg-type]
    for unrepresentable in (SHADOW_ID, SHADOW_SHADOWED_ID):
        with pytest.raises(UnrepresentableDirectiveIdError):
            resolve_config_id(f"directive:{unrepresentable}", **shadow_layers)  # type: ignore[arg-type]


def test_resolve_artifact_urn_keeps_its_single_refusal_type_for_an_unrepresentable_id(shadow_layers: _ResolverKwargs) -> None:
    """The stem/id direction has always reported the unrepresentable directive case as unknown (C-002)."""
    with pytest.raises(UnknownArtifactIdError) as caught:
        resolve_artifact_urn(ArtifactKind.DIRECTIVE, SHADOW_ID, **shadow_layers)  # type: ignore[arg-type]

    assert type(caught.value) is UnknownArtifactIdError  # not the UnrepresentableDirectiveIdError subclass


def test_resolve_config_id_keeps_its_malformed_urn_refusals(layers: _ResolverKwargs) -> None:
    for urn in ("no-colon", ":missing-kind", "tactic:"):
        with pytest.raises(ValueError, match="Malformed URN"):
            resolve_config_id(urn, **layers)  # type: ignore[arg-type]


def test_resolve_selected_id_to_stem_stays_stem_valued(layers: _ResolverKwargs) -> None:
    assert resolve_selected_id_to_stem(ArtifactKind.TACTIC, ORG_TAC_STEM, **layers) == ORG_TAC_STEM  # type: ignore[arg-type]
    assert resolve_selected_id_to_stem(ArtifactKind.TACTIC, ORG_TAC_ID, **layers) == ORG_TAC_STEM  # type: ignore[arg-type]
    assert resolve_selected_id_to_stem(ArtifactKind.TACTIC, "ghost-token", **layers) is None  # type: ignore[arg-type]


def test_resolve_selected_id_to_stem_still_refuses_the_shadowed_built_in_id(shadow_layers: _ResolverKwargs) -> None:
    assert resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, ORG_DIR_ID, **shadow_layers) == ORG_DIR_STEM  # type: ignore[arg-type]
    for unrepresentable in (SHADOW_ID, SHADOW_SHADOWED_ID):
        with pytest.raises(UnrepresentableDirectiveIdError):
            resolve_selected_id_to_stem(ArtifactKind.DIRECTIVE, unrepresentable, **shadow_layers)  # type: ignore[arg-type]


# ------------------------------------------------------- scan cost (NFR-004) --


def test_a_threaded_resolution_pass_scans_once_per_kind(layers: _ResolverKwargs, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pass that resolves the same kind twice re-walks no directory: the index reads through the pass."""
    globs: list[Path] = []
    original = kind_vocabulary._scan_dir_matches

    def counting(scan_dir: Path, pattern: str, *, recursive: bool) -> list[Path]:
        globs.append(scan_dir)
        return original(scan_dir, pattern, recursive=recursive)

    monkeypatch.setattr(kind_vocabulary, "_scan_dir_matches", counting)
    urn = f"tactic:{ORG_TAC_ID}"

    resolve_config_id(urn, resolution_pass=kind_vocabulary.ResolutionPass(), **layers)  # type: ignore[arg-type]
    assert globs, "a first resolution must scan"

    # Positive control: without a pass every call re-walks, so the counter observes the difference.
    without_pass = len(globs)
    resolve_config_id(urn, **layers)  # type: ignore[arg-type]
    assert len(globs) > without_pass

    shared = kind_vocabulary.ResolutionPass()
    resolve_config_id(urn, resolution_pass=shared, **layers)  # type: ignore[arg-type]
    after_first = len(globs)
    resolve_config_id(urn, resolution_pass=shared, **layers)  # type: ignore[arg-type]
    assert len(globs) == after_first, "the pass must answer the second resolution without a new scan"
