"""Charter-activation-aware org-profile resolver tests (WP02 — FR-003/FR-007).

The resolver under test, :func:`resolve_activated_org_profiles`, is the single
seam every org-honouring consumer (WP03 dispatch/context, WP04 projection)
calls.  It must return the **charter-activated** ∩ **org-provenance** subset of
agent profiles — composed through ``build_active_charter_service``
so the per-kind ``activated_agent_profiles`` gate is honoured (C-008) and never
re-implemented (C-006).

These tests pin the full three-regime activation contract over a real-format
org-pack fixture (C-007) plus the fail-closed regression (NFR-004):

* key absent → all org profiles admitted (backward-compat / #2156 install→visible);
* explicit list including an id → present;
* explicit list excluding an id → ABSENT;
* malformed pack member alongside an exclude list → de-activated id STILL absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.doctrine_service_factory import build_active_charter_service
from specify_cli.invocation.org_profiles import (
    ResolvedOrgProfile,
    resolve_activated_org_profiles,
)

pytestmark = pytest.mark.fast

# A real-format org pack: kebab pack name + an org-namespaced profile id.
_PACK_NAME = "orgzilla-governance-pack"
_ORG_ANALYST_ID = "orgzilla-org-analyst"
_ORG_CURATOR_ID = "orgzilla-org-curator"
# A real built-in profile id — used to prove built-in members never leak.
_BUILTIN_ID = "python-pedro"


def _org_profile_yaml(profile_id: str, *, name: str, role: str) -> str:
    """Render a minimal-but-valid ``.agent.yaml`` document body."""
    return (
        f"profile-id: {profile_id}\n"
        f"name: {name}\n"
        "description: Org-pack profile for activation-resolver fixtures\n"
        'schema-version: "1.0"\n'
        "roles:\n"
        f"  - {role}\n"
        "purpose: >\n"
        "  Organisation-provided profile contributed through an org doctrine\n"
        "  pack, used to verify charter-activation-aware resolution.\n"
        "specialization:\n"
        "  primary-focus: >\n"
        "    Organisation-specific tasks contributed through an org doctrine pack.\n"
    )


def _write_org_pack(repo_root: Path, *, extra_files: dict[str, str] | None = None) -> Path:
    """Create a real-format org pack and return its root directory.

    The pack root holds an ``agent_profiles/`` directory (the canonical
    org-doctrine layout) containing one analyst profile plus any
    ``extra_files`` (id → file body) the caller wants to add.
    """
    pack_root = repo_root / "org-packs" / _PACK_NAME
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{_ORG_ANALYST_ID}.agent.yaml").write_text(
        _org_profile_yaml(_ORG_ANALYST_ID, name="Orgzilla Org Analyst", role="researcher"),
        encoding="utf-8",
    )
    for filename, body in (extra_files or {}).items():
        (profiles_dir / filename).write_text(body, encoding="utf-8")
    return pack_root


def _write_config(repo_root: Path, pack_root: Path, *, activated: list[str] | None) -> None:
    """Write ``.kittify/config.yaml`` declaring the org pack and activation state.

    ``activated`` of ``None`` omits the ``activated_agent_profiles`` key entirely
    (the absent regime); a list writes it verbatim (include/exclude regimes).
    """
    data: dict[str, object] = {
        "charter_packs": {"org": {"packs": [{"name": _PACK_NAME, "local_path": str(pack_root)}]}},
    }
    if activated is not None:
        data["activated_agent_profiles"] = activated
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _ids(resolved: list[ResolvedOrgProfile]) -> list[str]:
    return [r.profile.profile_id for r in resolved]


# ---------------------------------------------------------------------------
# T004 — three-regime activation filter contract
# ---------------------------------------------------------------------------


class TestThreeRegimeActivation:
    def test_absent_key_admits_all_org_profiles(self, tmp_path: Path) -> None:
        """activated_agent_profiles absent → None filter → all org profiles admitted."""
        pack_root = _write_org_pack(tmp_path)
        _write_config(tmp_path, pack_root, activated=None)

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ORG_ANALYST_ID in _ids(resolved)
        # Org-provenance only: no built-in id leaks through.
        assert _BUILTIN_ID not in _ids(resolved)
        assert all(r.source_layer == "org" for r in resolved)

    def test_explicit_list_including_id_keeps_it_present(self, tmp_path: Path) -> None:
        """Explicit list that includes the org id → it survives the gate."""
        pack_root = _write_org_pack(tmp_path)
        _write_config(tmp_path, pack_root, activated=[_ORG_ANALYST_ID])

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ids(resolved) == [_ORG_ANALYST_ID]
        assert resolved[0].source_layer == "org"
        assert resolved[0].source_path is not None
        assert resolved[0].source_path.name == f"{_ORG_ANALYST_ID}.agent.yaml"

    def test_explicit_list_excluding_id_drops_it(self, tmp_path: Path) -> None:
        """Explicit list that excludes the org id → it is ABSENT (the gate bites).

        This is the regime a naive raw ``resolve_org_roots`` resolver would get
        wrong: it would surface the declared-but-de-activated org profile.
        """
        pack_root = _write_org_pack(tmp_path)
        _write_config(tmp_path, pack_root, activated=[_BUILTIN_ID])

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ORG_ANALYST_ID not in _ids(resolved)
        # The activated id is a built-in (not org-provenance) → org subset empty.
        assert resolved == []

    def test_results_are_deterministically_ordered_by_profile_id(self, tmp_path: Path) -> None:
        """Two activated org profiles come back sorted by profile_id."""
        curator_body = _org_profile_yaml(_ORG_CURATOR_ID, name="Orgzilla Org Curator", role="curator")
        pack_root = _write_org_pack(tmp_path, extra_files={f"{_ORG_CURATOR_ID}.agent.yaml": curator_body})
        _write_config(tmp_path, pack_root, activated=[_ORG_ANALYST_ID, _ORG_CURATOR_ID])

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ids(resolved) == sorted([_ORG_ANALYST_ID, _ORG_CURATOR_ID])


# ---------------------------------------------------------------------------
# T006 — fail-closed regression (NFR-004)
# ---------------------------------------------------------------------------


class TestFailClosed:
    @pytest.mark.parametrize("activated", [None, [_ORG_ANALYST_ID], [_BUILTIN_ID], []])
    def test_corrupt_sibling_diagnostics_survive_activation(self, tmp_path: Path, activated: list[str] | None) -> None:
        """The existing entrypoint must expose corruption even with no admission."""
        pack_root = _write_org_pack(
            tmp_path,
            extra_files={
                "orgzilla-broken.agent.yaml": "profile-id: orgzilla-broken\n: : : not valid yaml [\n",
            },
        )
        _write_config(tmp_path, pack_root, activated=activated)
        service = build_active_charter_service(tmp_path)
        _ = service.agent_profiles
        expected = tuple(item for item in service.agent_profile_repository.skipped_profiles() if item.layer == "org")
        assert len(expected) == 1
        assert expected[0].error_summary
        assert Path(expected[0].path) == pack_root / "agent_profiles/orgzilla-broken.agent.yaml"

        resolved = resolve_activated_org_profiles(tmp_path)

        assert isinstance(resolved, list)
        assert _ids(resolved) == ([_ORG_ANALYST_ID] if activated is None or _ORG_ANALYST_ID in activated else [])
        # Missing diagnostics is the observed bug, not a new-API import failure.
        assert getattr(resolved, "skipped_profiles", ()) == expected

    def test_malformed_pack_member_does_not_admit_excluded_profile(self, tmp_path: Path) -> None:
        """A corrupt sibling profile must NOT flip a de-activated id to admitted.

        The pack ships a valid analyst, a valid curator, and a corrupt file.
        Only the curator is activated. The resolver must fail CLOSED: the
        excluded analyst stays absent and the corrupt member never surfaces —
        the helper never silently returns the full org set.
        """
        curator_body = _org_profile_yaml(_ORG_CURATOR_ID, name="Orgzilla Org Curator", role="curator")
        pack_root = _write_org_pack(
            tmp_path,
            extra_files={
                f"{_ORG_CURATOR_ID}.agent.yaml": curator_body,
                "orgzilla-broken.agent.yaml": "profile-id: orgzilla-broken\n: : : not valid yaml [\n",
            },
        )
        _write_config(tmp_path, pack_root, activated=[_ORG_CURATOR_ID])

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ids(resolved) == [_ORG_CURATOR_ID]
        assert _ORG_ANALYST_ID not in _ids(resolved)
        assert "orgzilla-broken" not in _ids(resolved)

    def test_garbage_activation_entry_does_not_open_the_gate(self, tmp_path: Path) -> None:
        """A nonsense id in the activation list must not admit the excluded org id."""
        pack_root = _write_org_pack(tmp_path)
        _write_config(
            tmp_path,
            pack_root,
            activated=[_BUILTIN_ID, "this-profile-id-does-not-exist-anywhere"],
        )

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ORG_ANALYST_ID not in _ids(resolved)
        assert resolved == []


class TestDiagnosticControls:
    @pytest.mark.parametrize("activated", [None, [_ORG_ANALYST_ID], [_BUILTIN_ID], []])
    def test_healthy_pack_has_no_diagnostics(self, tmp_path: Path, activated: list[str] | None) -> None:
        pack_root = _write_org_pack(tmp_path)
        _write_config(tmp_path, pack_root, activated=activated)

        resolved = resolve_activated_org_profiles(tmp_path)

        assert resolved.skipped_profiles == ()
        assert _ids(resolved) == ([_ORG_ANALYST_ID] if activated is None or _ORG_ANALYST_ID in activated else [])

    def test_diagnostics_keep_canonical_provenance_and_order(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from charter.profiles import AgentProfileRepository

        pack_root = _write_org_pack(
            tmp_path,
            extra_files={
                "orgzilla-zulu.agent.yaml": "[",
                "orgzilla-alpha.agent.yaml": "[",
            },
        )
        _write_config(tmp_path, pack_root, activated=[])
        builtin_dir = tmp_path / "builtin-profiles"
        project_dir = tmp_path / ".kittify/charter-packs/agent_profiles"
        for directory in (builtin_dir, project_dir):
            directory.mkdir(parents=True)
            # Same filename as an org failure: layer, not ID/path heuristics,
            # owns attribution. Both layers really fail canonical loading.
            (directory / "orgzilla-alpha.agent.yaml").write_text("[", encoding="utf-8")
        monkeypatch.setattr(AgentProfileRepository, "_default_built_in_dir", staticmethod(lambda: builtin_dir))
        service = build_active_charter_service(tmp_path)
        _ = service.agent_profiles
        canonical = service.agent_profile_repository.skipped_profiles()
        assert {item.layer for item in canonical} == {"builtin", "org", "project"}
        expected = tuple(sorted((item for item in canonical if item.layer == "org"), key=lambda item: item.path))
        assert len(expected) == 2
        assert all(item.profile_id is None and item.error_summary for item in expected)

        resolved = resolve_activated_org_profiles(tmp_path)

        assert resolved == []
        assert resolved.skipped_profiles == expected
        assert [Path(item.path).name for item in resolved.skipped_profiles] == ["orgzilla-alpha.agent.yaml", "orgzilla-zulu.agent.yaml"]
        assert resolve_activated_org_profiles(tmp_path).skipped_profiles == expected

    def test_list_operations_do_not_change_diagnostics(self, tmp_path: Path) -> None:
        pack_root = _write_org_pack(tmp_path, extra_files={"orgzilla-broken.agent.yaml": "["})
        _write_config(tmp_path, pack_root, activated=None)
        resolved = resolve_activated_org_profiles(tmp_path)
        diagnostics = resolved.skipped_profiles

        assert [Path(item.path).name for item in diagnostics] == ["orgzilla-broken.agent.yaml"]
        assert list(resolved) == resolved[:]
        assert resolved[0].source_path == pack_root / "agent_profiles" / f"{_ORG_ANALYST_ID}.agent.yaml"
        resolved.clear()

        assert not resolved
        assert resolved.skipped_profiles == diagnostics


# ---------------------------------------------------------------------------
# R4 — no-org-packs short-circuit (perf): skip the activation-aware build
# ---------------------------------------------------------------------------


class TestNoOrgPacksShortCircuit:
    def test_no_org_packs_returns_empty(self, tmp_path: Path) -> None:
        """No declared org packs → empty result (nothing to resolve)."""
        # A config with no doctrine.org.packs at all.
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
            YAML().dump({"agents": {"available": ["claude"]}}, fh)

        resolved = resolve_activated_org_profiles(tmp_path)
        assert resolved == []
        assert resolved.skipped_profiles == ()

    def test_no_org_packs_does_not_build_the_service(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The short-circuit must avoid constructing the activation-aware service."""
        import specify_cli.invocation.org_profiles as org_profiles

        def _explode(_repo_root: Path) -> object:
            raise AssertionError("no-org-packs path must not build the activation-aware service")

        monkeypatch.setattr(org_profiles, "build_active_charter_service", _explode)

        # No .kittify/config.yaml at all → no org roots → fast path.
        resolved = resolve_activated_org_profiles(tmp_path)
        assert resolved == []
        assert resolved.skipped_profiles == ()

    def test_org_present_case_still_builds_and_resolves(self, tmp_path: Path) -> None:
        """Output unchanged for the org-present case (the build still happens)."""
        pack_root = _write_org_pack(tmp_path)
        _write_config(tmp_path, pack_root, activated=None)

        resolved = resolve_activated_org_profiles(tmp_path)

        assert _ORG_ANALYST_ID in _ids(resolved)


if __name__ == "__main__":  # pragma: no cover - manual red-first probe
    pytest.main([__file__, "-q"])
