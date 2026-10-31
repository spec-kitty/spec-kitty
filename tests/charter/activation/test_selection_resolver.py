"""The one selection resolver both activation writers use (#6686).

Before it existed, ``charter interview`` resolved a selection through the
layer-aware identity index while the ``4.0.0rc8_promote_interview_selections``
upgrade step resolved against the built-in pack alone, so a valid org-pack
selection was reported unresolved. These tests pin the shared rule itself: layer
lookup (built-in, org, project), dedupe, unknown ids, and the one ambiguity the two
writers treat differently (report vs refuse).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.activation_engine import ActivationIdCollisionError
from charter.activation.api import IdentityIndex, SelectionResolution, SelectionResolver, UnresolvedSelection
from charter.activation.identity_index import IdentityIndex as InternalIdentityIndex
from charter.activation.selection import (
    SelectionResolution as InternalSelectionResolution,
    SelectionResolver as InternalSelectionResolver,
    UnresolvedSelection as InternalUnresolvedSelection,
)
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from kernel.charter_pack_paths import project_pack_root
from tests.charter.org_pack_identity_support import IDENTITY_ARTIFACTS, write_identity_org_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast]

BUILT_IN_DIRECTIVE_ID = "DIRECTIVE_024"
BUILT_IN_DIRECTIVE_STEM = "024-locality-of-change"
ORG_DIRECTIVE_STEM, ORG_DIRECTIVE_ID = "qa-003-no-fake-green", "QA_003"
ORG_TACTIC_STEM, ORG_TACTIC_ID = "qa-tactic-seven", "qa-seven"
PROJECT_TACTIC_STEM, PROJECT_TACTIC_ID = "proj-tac", "proj-tac-id"
UNKNOWN_ID = "999-does-not-exist-anywhere"

_TACTIC = 'schema_version: "1.0"\nid: {id}\nname: T\npurpose: T.\nsteps:\n  - title: Do\n    description: Do it.\n'
_DIRECTIVE = 'schema_version: "1.0"\nid: {id}\ntitle: t\nintent: i\nenforcement: required\n'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _org_pack_project(tmp_path: Path) -> Path:
    """A project registering the identity org pack (declared ids differ from every stem)."""
    write_identity_org_pack(tmp_path)
    return tmp_path


def _with_project_tactic(tmp_path: Path) -> Path:
    """*tmp_path* plus one project-layer tactic whose declared id differs from its stem."""
    _write(project_pack_root(tmp_path) / PROJECT_KIND_DIRS[ArtifactKind.TACTIC] / f"{PROJECT_TACTIC_STEM}.tactic.yaml", _TACTIC.format(id=PROJECT_TACTIC_ID))
    return tmp_path


def _collision_project(tmp_path: Path) -> Path:
    """An org pack that reuses a built-in directive's file name for another id (Decision file_name_collision)."""
    project = _org_pack_project(tmp_path)
    pack = tmp_path / "identity-org"
    _write(pack / "directives" / f"{BUILT_IN_DIRECTIVE_STEM}.directive.yaml", _DIRECTIVE.format(id="ACME_024"))
    return project


@pytest.fixture(scope="module")
def org_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One org-pack project per module: building the index reads the whole doctrine corpus."""
    return _org_pack_project(tmp_path_factory.mktemp("org-pack"))


@pytest.fixture(scope="module")
def resolver(org_project: Path) -> SelectionResolver:
    return SelectionResolver.build(org_project)


@pytest.fixture(scope="module")
def project_layer_resolver(tmp_path_factory: pytest.TempPathFactory) -> SelectionResolver:
    return SelectionResolver.build(_with_project_tactic(_org_pack_project(tmp_path_factory.mktemp("project-layer"))))


@pytest.fixture(scope="module")
def collision_resolver(tmp_path_factory: pytest.TempPathFactory) -> SelectionResolver:
    return SelectionResolver.build(_collision_project(tmp_path_factory.mktemp("collision")))


def test_the_seam_reexports_the_real_resolver() -> None:
    """The seam is an identity re-export, not a copy or a wrapper (#6099)."""
    assert SelectionResolver is InternalSelectionResolver
    assert SelectionResolution is InternalSelectionResolution
    assert UnresolvedSelection is InternalUnresolvedSelection
    assert IdentityIndex is InternalIdentityIndex


def test_an_org_pack_id_resolves_to_its_stem(resolver: SelectionResolver) -> None:
    """#6686: the org layer resolves, not only the built-in pack."""
    assert resolver.stem(ArtifactKind.DIRECTIVE, ORG_DIRECTIVE_ID) == ORG_DIRECTIVE_STEM
    assert resolver.stem(ArtifactKind.DIRECTIVE, ORG_DIRECTIVE_STEM) == ORG_DIRECTIVE_STEM
    assert resolver.stem(ArtifactKind.TACTIC, ORG_TACTIC_ID) == ORG_TACTIC_STEM


def test_a_project_layer_id_resolves_to_its_stem(project_layer_resolver: SelectionResolver) -> None:
    resolver = project_layer_resolver

    assert resolver.stem(ArtifactKind.TACTIC, PROJECT_TACTIC_ID) == PROJECT_TACTIC_STEM


def test_a_built_in_id_still_resolves(resolver: SelectionResolver) -> None:
    """The layer the old upgrade path did resolve must keep resolving (no regression)."""
    assert resolver.stem(ArtifactKind.DIRECTIVE, BUILT_IN_DIRECTIVE_ID) == BUILT_IN_DIRECTIVE_STEM


def test_an_unknown_id_resolves_to_none(resolver: SelectionResolver) -> None:
    assert resolver.stem(ArtifactKind.DIRECTIVE, UNKNOWN_ID) is None


def test_resolve_groups_stems_by_activation_key_in_selection_order(resolver: SelectionResolver) -> None:
    resolution = resolver.resolve(
        {
            ArtifactKind.DIRECTIVE: [ORG_DIRECTIVE_ID, BUILT_IN_DIRECTIVE_ID],
            ArtifactKind.TACTIC: [ORG_TACTIC_ID],
        }
    )

    assert resolution.stems == {
        "activated_directives": [ORG_DIRECTIVE_STEM, BUILT_IN_DIRECTIVE_STEM],
        "activated_tactics": [ORG_TACTIC_STEM],
    }
    assert resolution.unresolved == []


def test_a_selection_named_twice_is_resolved_once(resolver: SelectionResolver) -> None:
    resolution = resolver.resolve({ArtifactKind.DIRECTIVE: [ORG_DIRECTIVE_ID, ORG_DIRECTIVE_STEM]})

    assert resolution.stems == {"activated_directives": [ORG_DIRECTIVE_STEM]}


def test_an_unknown_id_is_reported_and_contributes_no_stem(resolver: SelectionResolver) -> None:
    """The positive control is the same fixture's known id: it promotes while the unknown one is reported."""
    resolution = resolver.resolve({ArtifactKind.DIRECTIVE: [ORG_DIRECTIVE_ID, UNKNOWN_ID]})

    assert resolution.stems == {"activated_directives": [ORG_DIRECTIVE_STEM]}
    assert resolution.unresolved == [UnresolvedSelection(ArtifactKind.DIRECTIVE, UNKNOWN_ID, ambiguous=False)]
    assert resolution.unresolved[0].urn == f"directive:{UNKNOWN_ID}"


def test_an_empty_selection_resolves_to_nothing(resolver: SelectionResolver) -> None:
    assert resolver.resolve({ArtifactKind.DIRECTIVE: []}) == SelectionResolution()


def test_an_unrepresentable_identity_is_reported_by_default(collision_resolver: SelectionResolver) -> None:
    """The upgrade reports a collision, never drops or reinterprets it."""
    resolver = collision_resolver

    resolution = resolver.resolve({ArtifactKind.DIRECTIVE: [BUILT_IN_DIRECTIVE_ID]})

    assert resolution.stems == {}
    assert resolution.unresolved == [UnresolvedSelection(ArtifactKind.DIRECTIVE, BUILT_IN_DIRECTIVE_ID, ambiguous=True)]


def test_an_unrepresentable_identity_is_refused_when_asked(collision_resolver: SelectionResolver) -> None:
    """Same fixture, other policy: the interview refuses before writing anything."""
    resolver = collision_resolver

    with pytest.raises(ActivationIdCollisionError):
        resolver.resolve({ArtifactKind.DIRECTIVE: [BUILT_IN_DIRECTIVE_ID]}, refuse_ambiguous=True)


def test_stems_matches_a_stored_list_by_stem_and_keeps_unknown_entries_literal(resolver: SelectionResolver) -> None:
    assert resolver.stems(ArtifactKind.DIRECTIVE, [ORG_DIRECTIVE_ID, UNKNOWN_ID]) == {ORG_DIRECTIVE_STEM, UNKNOWN_ID}


def test_stems_keeps_an_unrepresentable_entry_as_written(collision_resolver: SelectionResolver) -> None:
    """The present-list comparison must not crash on a colliding id: it compares by the spelling stored."""
    assert collision_resolver.stems(ArtifactKind.DIRECTIVE, [BUILT_IN_DIRECTIVE_ID]) == {BUILT_IN_DIRECTIVE_ID}


def test_one_index_build_serves_a_whole_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: a writer resolves its layers once, not once per selection."""
    builds = 0
    original = InternalIdentityIndex.build

    def counting(cls: type[InternalIdentityIndex], repo_root: Path, **kwargs: object) -> InternalIdentityIndex:
        nonlocal builds
        builds += 1
        return original(repo_root, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(InternalIdentityIndex, "build", classmethod(counting))
    resolver = SelectionResolver.build(_org_pack_project(tmp_path))

    resolver.resolve({ArtifactKind.DIRECTIVE: [ORG_DIRECTIVE_ID, BUILT_IN_DIRECTIVE_ID], ArtifactKind.TACTIC: [ORG_TACTIC_ID]})
    resolver.stems(ArtifactKind.DIRECTIVE, [ORG_DIRECTIVE_ID])

    assert builds == 1


def test_every_identity_org_pack_kind_resolves_its_declared_id(resolver: SelectionResolver) -> None:
    """The fixture pack covers each promoted kind; each kind's declared id maps to its stem."""
    for plural, stem, declared in IDENTITY_ARTIFACTS:
        kind = ArtifactKind.from_plural(plural)
        assert resolver.stem(kind, declared) == stem, plural
