"""Compile and the consistency check resolve activation tokens through the identity index (#6433; FR-016, FR-017).

An activation token may be spelled as a file stem, a declared id or a
``<kind>:<id>`` URN, and may name an org-pack or a project-layer artifact. Each
surface resolves it through one :class:`~charter.activation.identity_index.IdentityIndex`
covering the built-in, org and project layers, so every surface accepts the same
tokens as the runtime gate (SC-006).

A token no layer knows has ONE pinned behaviour per surface (#6433 "pin one behaviour"):

* **runtime gate** (``resolver._gated``): warn and keep -- the token is logged and
  kept best-effort, never raised.
* **consistency check** (``run_consistency_check``): warn and keep -- the token is
  reported once, in ``unknown_references`` (never again in ``verification_errors``),
  and the stored list is left as it is.
* **compile** (``resolve_config_activated_roots``): refuse -- it raises
  :class:`~charter.activation.kind_vocabulary.UnknownArtifactIdError` naming the
  activation store (C-006: never silently drop).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
from charter.activation.compiler import _resolve_transitive_reference_graph, resolve_config_activated_roots
from charter.activation.consistency_check import (
    _check_reference_id_forward_parity,
    _check_reference_id_reverse_parity,
    run_consistency_check,
)
from charter.activation.drg_activation import _resolve_activated_urns_for_kind, filter_graph_by_activation
from charter.activation.catalog import resolve_offering_root
from charter.activation.identity_index import IdentityIndex
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import UnknownArtifactIdError, resolve_artifact_urn
from charter.activation.pack_context import PackContext
from charter.activation.pack_manager import ActiveCharterManager
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from kernel.charter_pack_paths import project_pack_root
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.integration]

ORG_TOOL_STEM, ORG_TOOL_ID = "acme-tool-file", "acme-tool-id"  # org-required
ORG_TAC_STEM, ORG_TAC_ID = "acme-tac-file", "acme-tac-id"
ORG_PARADIGM_STEM, ORG_PARADIGM_ID = "acme-paradigm-file", "acme-paradigm-id"
PROJ_TAC_STEM, PROJ_TAC_ID = "proj-tac", "proj-tac-id"
DIR_STEM, DIR_ID = "024-locality-of-change", "DIRECTIVE_024"
UNKNOWN = "ghost-token"

_TOOLGUIDE = 'schema_version: "1.0"\nid: {id}\ntool: acme\ntitle: Acme\nsummary: Acme.\nguide_path: acme.md\napplies_to_languages: []\n'
_TACTIC = "schema_version: '1.0'\nid: {id}\nname: T\npurpose: T.\nsteps:\n  - title: Do\n    description: Do it.\n"
_DIRECTIVE = 'schema_version: "1.0"\nid: {id}\ntitle: t\nintent: i\nenforcement: required\n'
_PARADIGM = 'schema_version: "1.0"\nid: {id}\nname: P\nsummary: P.\n'


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path, *, shadow_directive: bool = False) -> Path:
    """A git project with the org pack ``acme`` (stem != id artifacts) and a project-layer tactic."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    pack = tmp_path / "acme"
    _write(pack / "toolguides" / f"{ORG_TOOL_STEM}.toolguide.yaml", _TOOLGUIDE.format(id=ORG_TOOL_ID))
    _write(pack / "tactics" / f"{ORG_TAC_STEM}.tactic.yaml", _TACTIC.format(id=ORG_TAC_ID))
    _write(pack / "paradigms" / f"{ORG_PARADIGM_STEM}.paradigm.yaml", _PARADIGM.format(id=ORG_PARADIGM_ID))
    if shadow_directive:
        # The org file reuses the built-in stem for another id: DIRECTIVE_024 has no single stem.
        _write(pack / "directives" / f"{DIR_STEM}.directive.yaml", _DIRECTIVE.format(id="ACME_024"))
    _write(pack / "org-charter.yaml", f"org_name: acme\nrequired_toolguides:\n  - {ORG_TOOL_ID}\n")
    project_tactics = project_pack_root(tmp_path) / PROJECT_KIND_DIRS[ArtifactKind.TACTIC]
    _write(project_tactics / f"{PROJ_TAC_STEM}.tactic.yaml", _TACTIC.format(id=PROJ_TAC_ID))
    _write(tmp_path / ".kittify" / "config.yaml", f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {pack}\n")
    return tmp_path


def _flagged(entries: list[str], token: str) -> list[str]:
    return [entry for entry in entries if token in entry]


# --------------------------------------------------------------- compile ----


@pytest.mark.parametrize(
    ("ledger_key", "token", "field", "expected"),
    [
        pytest.param("activated_directives", f"directive:{DIR_ID}", "directives", DIR_ID, id="directive-urn"),
        pytest.param("activated_tactics", f"tactic:{ORG_TAC_ID}", "tactics", ORG_TAC_ID, id="org-tactic-urn"),
        pytest.param("activated_tactics", ORG_TAC_ID, "tactics", ORG_TAC_ID, id="org-tactic-declared-id"),
        pytest.param("activated_tactics", PROJ_TAC_STEM, "tactics", PROJ_TAC_ID, id="project-tactic-stem"),
        pytest.param("activated_tactics", PROJ_TAC_ID, "tactics", PROJ_TAC_ID, id="project-tactic-declared-id"),
        pytest.param("activated_tactics", f"tactic:{PROJ_TAC_ID}", "tactics", PROJ_TAC_ID, id="project-tactic-urn"),
    ],
)
def test_compile_resolves_every_spelling_of_a_known_token(tmp_path: Path, ledger_key: str, token: str, field: str, expected: str) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, **{ledger_key: [token]})

    roots = resolve_config_activated_roots(repo_root=root)

    assert getattr(roots, field) == [expected]


def test_compile_resolves_a_declared_id_with_no_single_stem(tmp_path: Path) -> None:
    """A hand-written colliding ``DIRECTIVE_024`` still compiles: writers refuse it (Decision ``file_name_collision``), compile is unchanged."""
    root = _project(tmp_path, shadow_directive=True)
    assert IdentityIndex.build(root).stem(ArtifactKind.DIRECTIVE, DIR_ID) is None, "fixture invalid: DIRECTIVE_024 must have no single stem"
    seed_activation_ledger(root, activated_directives=[DIR_ID])

    roots = resolve_config_activated_roots(repo_root=root)

    assert roots.directives == [DIR_ID]


def test_compile_still_refuses_an_unknown_token(tmp_path: Path) -> None:
    """Positive control: compile never drops an unknown token silently (C-006)."""
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_tactics=[PROJ_TAC_STEM, UNKNOWN])

    with pytest.raises(UnknownArtifactIdError) as excinfo:
        resolve_config_activated_roots(repo_root=root)

    assert UNKNOWN in str(excinfo.value)
    assert "Activation store:" in str(excinfo.value)


def test_compile_names_the_unknown_token_of_the_earliest_field_first(tmp_path: Path) -> None:
    """Kinds resolve in ``ConfigActivatedRoots`` field order (paradigms before tactics), as before #6433."""
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_paradigms=["ghost-paradigm"], activated_tactics=[UNKNOWN])

    with pytest.raises(UnknownArtifactIdError) as excinfo:
        resolve_config_activated_roots(repo_root=root)

    assert "ghost-paradigm" in str(excinfo.value)
    assert UNKNOWN not in str(excinfo.value)


def test_compile_builds_one_identity_index_per_compile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: the roots of one compile are resolved through a single index, not one per kind."""
    import charter.activation.compiler as compiler

    root = _project(tmp_path)
    seed_activation_ledger(root, activated_tactics=[PROJ_TAC_STEM], activated_directives=[DIR_STEM], activated_toolguides=[ORG_TOOL_STEM])
    built: list[IdentityIndex] = []
    real_from_roots = IdentityIndex.from_roots

    def spy(**kwargs: Any) -> IdentityIndex:
        index = real_from_roots(**kwargs)
        built.append(index)
        return index

    monkeypatch.setattr(compiler.IdentityIndex, "from_roots", staticmethod(spy))

    resolve_config_activated_roots(repo_root=root)

    assert len(built) == 1


# ----------------------------------------------------- consistency check ----


def test_check_reports_no_unknown_for_a_w2_written_list(tmp_path: Path) -> None:
    """An absent-key activate (W2) writes the effective set; the check finds nothing unknown in it."""
    root = _project(tmp_path)
    ActiveCharterManager().activate(ProjectContext.from_repo(root), "toolguide", "gherkin")
    stored = read_activation_ledger(root)["activated_toolguides"]
    assert "gherkin" in stored and len(stored) > 1, stored

    report = run_consistency_check(ProjectContext.from_repo(root))

    assert [entry for entry in report.unknown_references if entry.startswith("toolguide/")] == []
    assert [entry for entry in report.verification_errors if entry.startswith("toolguide/")] == []


@pytest.mark.parametrize(
    ("ledger_key", "token"),
    [
        pytest.param("activated_toolguides", ORG_TOOL_ID, id="stored-org-declared-id"),
        pytest.param("activated_tactics", PROJ_TAC_STEM, id="project-layer-stem"),
        pytest.param("activated_tactics", PROJ_TAC_ID, id="project-layer-declared-id"),
        pytest.param("activated_directives", DIR_ID, id="built-in-declared-id"),
    ],
)
def test_check_does_not_report_a_known_token_as_unknown(tmp_path: Path, ledger_key: str, token: str) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, **{ledger_key: [token]})

    report = run_consistency_check(ProjectContext.from_repo(root))

    assert _flagged(report.unknown_references, token) == []
    assert _flagged(report.verification_errors, token) == []


def test_check_reports_an_unknown_token_once_and_keeps_it(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_tactics=[PROJ_TAC_STEM, UNKNOWN])

    report = run_consistency_check(ProjectContext.from_repo(root))

    assert report.unknown_references == [f"tactic/{UNKNOWN}"]
    assert _flagged(report.verification_errors, UNKNOWN) == []
    assert report.coherent is False
    assert read_activation_ledger(root)["activated_tactics"] == [PROJ_TAC_STEM, UNKNOWN]


def test_forward_parity_resolves_a_project_layer_artifact(tmp_path: Path) -> None:
    """A project-layer stem absent from the compiled references is a divergence, not a silent skip."""
    root = _project(tmp_path)
    divergences: list[str] = []

    _check_reference_id_forward_parity(
        {"tactic": [PROJ_TAC_STEM, f"tactic:{ORG_TAC_ID}", UNKNOWN]},
        {"tactic": frozenset({ORG_TAC_ID})},
        identity=IdentityIndex.build(root),
        reference_id_divergences=divergences,
        suggestions=[],
    )

    assert divergences == [f"tactic/{PROJ_TAC_STEM}"]


def test_reverse_paradigm_parity_compares_stems_with_stems(tmp_path: Path) -> None:
    """A compiled org paradigm (declared id) activated by its stem is not stale."""
    root = _project(tmp_path)
    divergences: list[str] = []

    _check_reference_id_reverse_parity(
        {"paradigm": [ORG_PARADIGM_STEM]},
        {"paradigm": frozenset({ORG_PARADIGM_ID})},
        identity=IdentityIndex.build(root),
        reference_id_divergences=divergences,
        suggestions=[],
    )

    assert divergences == []


def test_reverse_paradigm_parity_still_flags_a_stale_paradigm(tmp_path: Path) -> None:
    root = _project(tmp_path)
    divergences: list[str] = []

    _check_reference_id_reverse_parity(
        {"paradigm": []},
        {"paradigm": frozenset({ORG_PARADIGM_ID})},
        identity=IdentityIndex.build(root),
        reference_id_divergences=divergences,
        suggestions=[],
    )

    assert divergences == [f"paradigm/{ORG_PARADIGM_ID}"]


# ------------------------------------------ drg_activation fallback (T023) --


_FALLBACK_KINDS = (
    ArtifactKind.DIRECTIVE,
    ArtifactKind.TACTIC,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TOOLGUIDE,
    ArtifactKind.PARADIGM,
    ArtifactKind.PROCEDURE,
    ArtifactKind.AGENT_PROFILE,
    ArtifactKind.MISSION_STEP_CONTRACT,
    ArtifactKind.GLOSSARY_PACK,
    ArtifactKind.SKILL,
)


@pytest.mark.parametrize("kind", _FALLBACK_KINDS, ids=lambda kind: kind.value)
def test_index_resolves_every_token_the_filesystem_resolver_resolves(tmp_path: Path, kind: ArtifactKind) -> None:
    """T023 evidence: for every stem and declared id ``resolve_artifact_urn`` resolves, the index gives the same URN."""
    root = _project(tmp_path, shadow_directive=kind is ArtifactKind.DIRECTIVE)
    index = IdentityIndex.build(root)
    org_roots = list(index.org_roots)
    layer_roots = {"project": project_pack_root(root)}
    # Both directions: tokens the index scanned, and tokens drawn from the filesystem resolver's own scan.
    tokens = {token for entry in index._table(kind).entries for token in (entry.stem, entry.declared_id)}
    yaml = YAML(typ="safe")
    for path in kind_vocabulary._iter_artifact_paths(kind, offering_root=resolve_offering_root(), org_roots=org_roots, layer_roots=layer_roots):
        tokens.add(kind_vocabulary._config_stem(path))
        declared = kind_vocabulary._read_id(path, kind_vocabulary._id_field_for(kind), yaml)
        if declared:
            tokens.add(declared)
    for token in sorted(tokens):
        try:
            expected = resolve_artifact_urn(kind, token, offering_root=resolve_offering_root(), org_roots=org_roots, layer_roots=layer_roots)
        except UnknownArtifactIdError:
            continue
        assert f"{kind.value}:{index.declared_id(kind, token)}" == expected, token


def test_drg_gate_resolves_through_the_index_alone(tmp_path: Path) -> None:
    """With an index, the gate needs no filesystem fallback: known tokens resolve, unknown ones are skipped."""
    root = _project(tmp_path)

    urns = _resolve_activated_urns_for_kind(
        "tactic",
        frozenset({PROJ_TAC_STEM, f"tactic:{ORG_TAC_ID}", UNKNOWN}),
        offering_root=resolve_offering_root(),
        org_roots=[],  # The index alone carries the org and project layers: no filesystem resolver could find these.
        identity=IdentityIndex.build(root),
    )

    assert urns == frozenset({f"tactic:{PROJ_TAC_ID}", f"tactic:{ORG_TAC_ID}"})


# ---------------------------------- one identity authority for the filter --
#
# Decision ``urn_split``: every ``filter_graph_by_activation`` caller resolves
# activation tokens through the identity index (built once per call when the
# caller passes none), so an activated URN or org declared id survives into the
# filtered graph -- the transitive closure and the ``references.yaml`` input --
# not only into ``ConfigActivatedRoots``.

_URN_TOKENS = (f"tactic:{PROJ_TAC_ID}", f"tactic:{ORG_TAC_ID}")
_CONTROL = "tactic:not-activated-control"


def _graph_with_layer_tactics() -> Any:
    """The built-in graph plus the project and org tactic nodes and a not-activated control."""
    from charter.offering.drg.loader import load_built_in_graph
    from charter.offering.drg.models import DRGNode, NodeKind

    base = load_built_in_graph()
    extra = [DRGNode(urn=urn, kind=NodeKind.TACTIC, label=urn) for urn in (f"tactic:{PROJ_TAC_ID}", f"tactic:{ORG_TAC_ID}", _CONTROL)]
    return base.model_copy(update={"nodes": [*base.nodes, *extra]})


def test_filter_without_an_index_keeps_activated_urn_and_declared_id_tokens(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_tactics=[*_URN_TOKENS, ORG_TAC_ID])

    survivors = {node.urn for node in filter_graph_by_activation(_graph_with_layer_tactics(), PackContext.from_config(root)).nodes}

    assert {f"tactic:{PROJ_TAC_ID}", f"tactic:{ORG_TAC_ID}"} <= survivors
    assert _CONTROL not in survivors


def test_activated_urn_tokens_reach_the_transitive_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``references.yaml`` input: the closure walks the filtered graph, so a filtered-out root never resolves."""
    import charter.activation._drg_helpers as drg_helpers

    root = _project(tmp_path)
    seed_activation_ledger(root, activated_tactics=list(_URN_TOKENS))
    ctx = PackContext.from_config(root)
    assert set(resolve_config_activated_roots(repo_root=root).tactics) == {PROJ_TAC_ID, ORG_TAC_ID}  # the roots already resolve
    monkeypatch.setattr(drg_helpers, "load_validated_graph", lambda *_a, **_k: _graph_with_layer_tactics())

    result = _resolve_transitive_reference_graph(
        offering_root=resolve_offering_root(),
        directives=[],
        direct_root_urns=frozenset({f"tactic:{PROJ_TAC_ID}", f"tactic:{ORG_TAC_ID}"}),
        repo_root=root,
        pack_context=ctx,
    )

    assert {PROJ_TAC_ID, ORG_TAC_ID} <= set(result.tactics), result


def test_check_knows_an_artifact_token_only_through_the_index(tmp_path: Path) -> None:
    """For an artifact kind the index alone decides; ``list_available`` ids count only for mission types."""
    from charter.activation.consistency_check import _is_known

    index = IdentityIndex.build(_project(tmp_path))
    listed = {"tactic": frozenset({UNKNOWN}), "mission-type": frozenset({"software-dev"})}

    assert _is_known("tactic", UNKNOWN, index, listed) is False
    assert _is_known("tactic", f"tactic:{PROJ_TAC_ID}", index, listed) is True
    assert _is_known("mission-type", "software-dev", index, listed) is True
    assert _is_known("mission-type", UNKNOWN, index, listed) is False
