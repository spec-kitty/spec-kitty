"""Behavioural loader↔resolver recursion-parity gate (WP05 / T026, T027, T028).

Binds the two authorities that #3490/#3426 let drift: the loader
(``doctrine.base``/``doctrine.agent_profiles``) and the charter-activation
resolver (``charter.activation.kind_vocabulary``) must discover the *same* nested overlay
artifacts, for every kind, because both derive recursion from the single
``doctrine.discovery_recursion`` authority (C-001, FR-002). The gate:

* asserts the resolver discovers a nested org artifact for EVERY kind (T026);
* cross-checks loader↔resolver agreement on representative kinds (T026);
* proves kind-specific globs keep ``.provenance/*.yaml`` / ``.md`` out (C-002, T027);
* is falsifiable: reintroducing a per-kind ``recursive=False`` divergence makes
  the resolver stop discovering the nested artifact -- the parity assertion would
  redden and name the kind (NFR-003, T028).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation import kind_vocabulary
from charter.activation.kind_vocabulary import _iter_artifact_paths
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.discovery_recursion import overlay_scan_is_recursive

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

#: Kinds that address a real artifact file on disk (non-empty glob). ``template``
#: has an empty glob (mission-tier, resolved specially); ``anti_pattern`` declares
#: a glob for consumer-loop consistency but ships no files -- it still recurses
#: identically (both sides discover the same, possibly empty, set).
_GLOBBED_KINDS = [kind for kind in ArtifactKind if kind.glob_pattern]


def _write_id(path: Path, artifact_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump({"id": artifact_id}, path.open("w", encoding="utf-8"))


def _nested_probe(pack: Path, kind: ArtifactKind, artifact_id: str) -> Path:
    """Author a nested ``<pack>/<plural>/deep/probe<suffix>`` artifact; return its path."""
    suffix = kind.glob_pattern[1:]  # "*.tactic.yaml" -> ".tactic.yaml"
    path = pack / kind.plural / "deep" / f"probe{suffix}"
    _write_id(path, artifact_id)
    return path


def _resolver_paths(pack: Path, kind: ArtifactKind, tmp: Path) -> list[Path]:
    return _iter_artifact_paths(
        kind,
        offering_root=tmp / "offering_root",
        org_roots=[pack],
        layer_roots=None,
    )


# ── T026: resolver discovers nested for every kind ────────────────────────────


@pytest.mark.parametrize("kind", _GLOBBED_KINDS, ids=lambda k: k.value)
def test_resolver_discovers_nested_overlay_artifact_for_every_kind(kind: ArtifactKind, tmp_path: Path) -> None:
    pack = tmp_path / "orgpack"
    probe = _nested_probe(pack, kind, f"{kind.value}-probe")
    assert probe in _resolver_paths(pack, kind, tmp_path), f"resolver did not discover nested {kind.value} artifact -> recursion divergence for this kind"


def test_authority_is_recursive_for_every_kind() -> None:
    """Both loader and resolver consult this single function (parity by construction)."""
    assert all(overlay_scan_is_recursive(kind) for kind in ArtifactKind)


# ── T026: direct loader↔resolver agreement on representative kinds ────────────


def test_loader_and_resolver_agree_for_nested_tactic(tmp_path: Path) -> None:
    from charter.offering.tactics.repository import TacticRepository

    pack = tmp_path / "orgpack"
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    (pack / "tactics" / "deep").mkdir(parents=True)
    YAML().dump(
        {"schema_version": "1.0", "id": "agree-tactic", "name": "A", "steps": [{"title": "s"}]},
        (pack / "tactics" / "deep" / "agree.tactic.yaml").open("w", encoding="utf-8"),
    )

    loader_found = TacticRepository(built_in_dir=built_in, org_dirs=[pack / "tactics"]).get("agree-tactic") is not None
    resolver_found = any(
        p.name == "agree.tactic.yaml"
        for p in _iter_artifact_paths(
            ArtifactKind.TACTIC,
            offering_root=tmp_path / "dr",
            org_roots=[pack],
            layer_roots=None,
        )
    )
    assert loader_found is True
    assert resolver_found is True
    assert loader_found == resolver_found  # parity


def test_loader_and_resolver_agree_for_nested_agent_profile(tmp_path: Path) -> None:
    from charter.offering.agent_profiles.repository import AgentProfileRepository

    pack = tmp_path / "orgpack"
    _write_id(pack / "agent_profiles" / "team" / "x.agent.yaml", "unused")  # placeholder path
    # A valid profile for the loader:
    YAML().dump(
        {
            "profile-id": "agree-profile",
            "name": "Agree",
            "description": "parity probe",
            "schema-version": "1.0",
            "roles": ["implementer"],
            "purpose": "parity",
            "specialization": {"primary-focus": "parity"},
        },
        (pack / "agent_profiles" / "team" / "agree.agent.yaml").open("w", encoding="utf-8"),
    )

    loader_found = AgentProfileRepository(org_dirs=[pack / "agent_profiles"]).get("agree-profile") is not None
    resolver_found = any(
        p.name == "agree.agent.yaml"
        for p in _iter_artifact_paths(
            ArtifactKind.AGENT_PROFILE,
            offering_root=tmp_path / "dr",
            org_roots=[pack],
            layer_roots=None,
        )
    )
    assert loader_found is True
    assert resolver_found is True


# ── T027: C-002 negative -- kind-specific globs exclude non-artifacts ─────────


def test_provenance_and_markdown_never_captured(tmp_path: Path) -> None:
    """C-002: kind-specific globs exclude generic ``.provenance/*.yaml`` + ``.md``.

    Non-vacuous: asserts the discovered set is *exactly* the real artifact. A
    generic ``sidecar.provenance.yaml`` and a ``notes.md`` sit beside the real
    nested tactic; if the scan used a broad ``*.yaml`` glob (or captured markdown)
    they would appear and this exact-set assertion would fail. Proves the
    guarantee comes from glob-specificity, not incidental id/extension checks.
    """
    pack = tmp_path / "orgpack"
    probe = _nested_probe(pack, ArtifactKind.TACTIC, "real-probe")
    _write_id(pack / "tactics" / "deep" / ".provenance" / "sidecar.provenance.yaml", "prov")
    (pack / "tactics" / "deep" / "notes.md").write_text("# note\n", encoding="utf-8")

    # Scope to the org pack subtree (the resolver also scans the real built-in
    # corpus). Within the pack, the discovered set must be exactly the probe.
    org_resolved = [p for p in _resolver_paths(pack, ArtifactKind.TACTIC, tmp_path) if pack in p.parents]
    assert org_resolved == [probe], (
        "kind-specific glob must discover exactly the *.tactic.yaml artifact in "
        "the org pack -- the .provenance/*.yaml sidecar and .md note must be "
        f"excluded; got {org_resolved}"
    )


# ── FOLD A regression: nested `built-in` is NOT the reserved child ────────────


def test_nested_builtin_component_stays_in_parity(tmp_path: Path) -> None:
    """A ``built-in`` dir BELOW a category is a user dir, not the reserved child.

    Regression for the over-exclusion defect: excluding a ``built-in`` component
    at any depth dropped ``<plural>/<category>/built-in/x`` from the resolver
    while the loader still loaded it. The immediate-child scoping keeps deep
    ``built-in`` components discoverable, so loader and resolver agree.
    """
    from charter.offering.tactics.repository import TacticRepository

    pack = tmp_path / "orgpack"
    built_in = tmp_path / "built-in"
    built_in.mkdir()
    nested = pack / "tactics" / "writing" / "built-in" / "deep.tactic.yaml"
    nested.parent.mkdir(parents=True)
    YAML().dump(
        {"schema_version": "1.0", "id": "deep-builtin-tactic", "name": "D", "steps": [{"title": "s"}]},
        nested.open("w", encoding="utf-8"),
    )

    loader_found = TacticRepository(built_in_dir=built_in, org_dirs=[pack / "tactics"]).get("deep-builtin-tactic") is not None
    resolver_found = any(
        p.name == "deep.tactic.yaml"
        for p in _iter_artifact_paths(
            ArtifactKind.TACTIC,
            offering_root=tmp_path / "dr",
            org_roots=[pack],
            layer_roots=None,
        )
    )
    assert loader_found is True
    assert resolver_found is True, "nested <category>/built-in/ artifact must resolve (immediate-child exclusion only) -- else loader<->resolver divergence returns"


def test_top_level_builtin_still_reserved_flat_wins(tmp_path: Path) -> None:
    """The immediate ``<plural>/built-in`` child is still the reserved legacy dir.

    A same-config-stem file in flat ``<plural>`` must still win over one in the
    top-level ``<plural>/built-in`` legacy dir (the exclusion of the immediate
    child, compensated by the dedicated legacy entry, preserves flat-wins).
    """
    from charter.activation.kind_vocabulary import resolve_artifact_urn

    pack = tmp_path / "orgpack"
    (pack / "tactics" / "built-in").mkdir(parents=True)
    (pack / "tactics" / "flatwin.tactic.yaml").write_text("id: FLAT_WIN\n", encoding="utf-8")
    (pack / "tactics" / "built-in" / "flatwin.tactic.yaml").write_text("id: LEGACY_LOSE\n", encoding="utf-8")
    urn = resolve_artifact_urn(
        ArtifactKind.TACTIC,
        "flatwin",
        offering_root=tmp_path / "dr",
        org_roots=[pack],
    )
    assert urn == "tactic:FLAT_WIN"


# ── FOLD C: reintroduced non-recursive override guard (finding 4) ─────────────


def test_no_base_repository_reoverrides_project_scan_non_recursively() -> None:
    """No ``BaseArtifactRepository`` subclass may re-declare ``_project_scan``.

    Directly guards the reintroduced-override regression the falsifiability probe
    cannot reach (a per-repo ``.glob`` override bypasses the shared authority the
    resolver reds against). WP01 deleted the styleguide + asset overrides in
    favour of the recursive base; a subclass that re-adds one -- recursive or not
    -- must fail here so the loader cannot silently diverge from the resolver.
    """
    from charter.offering.base import BaseArtifactRepository

    offenders = [cls.__name__ for cls in BaseArtifactRepository.__subclasses__() if "_project_scan" in cls.__dict__]
    assert not offenders, f"these repositories re-declare _project_scan instead of inheriting the authority-driven recursive base: {offenders}"


# ── T028: falsifiability -- reintroduced divergence reddens the parity check ──


def test_reintroduced_divergence_breaks_resolver_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both directions on one commit: with the authority intact the nested probe
    resolves; monkeypatching the authority to non-recursive for TACTIC makes the
    resolver stop discovering it -- exactly the divergence the parity gate above
    would catch and name.
    """
    pack = tmp_path / "orgpack"
    probe = _nested_probe(pack, ArtifactKind.TACTIC, "falsify-probe")

    # Direction 1: intact authority -> discovered (parity holds).
    assert probe in _resolver_paths(pack, ArtifactKind.TACTIC, tmp_path)

    # Direction 2: reintroduce a per-kind non-recursive divergence -> dropped.
    def _diverged(kind: ArtifactKind) -> bool:
        return kind is not ArtifactKind.TACTIC and overlay_scan_is_recursive(kind)

    monkeypatch.setattr(kind_vocabulary, "overlay_scan_is_recursive", _diverged)
    assert probe not in _resolver_paths(pack, ArtifactKind.TACTIC, tmp_path)
