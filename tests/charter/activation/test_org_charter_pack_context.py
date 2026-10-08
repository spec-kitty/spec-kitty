"""Integration tests: PackContext wiring into OrgCharterPolicy loader (WP10).

T063 — Audit: no config.yaml reads in _resolve_chain() or _merge_chain()
-----------------------------------------------------------------------
``_resolve_chain()`` and ``_merge_chain()`` in
``charter.activation.org_charter`` operate entirely on the
``pack_set: dict[str, OrgCharterPolicy]`` argument.  The only path
that reads ``.kittify/config.yaml`` is ``PackContext.from_config()``
in ``charter.activation.pack_context``, which is in the *charter* layer (not the
doctrine layer).  When a ``PackContext`` is supplied to
``load_org_charter_policies()``, the function delegates immediately to
``_load_with_pack_context()`` which builds the pack set from
``PackContext.pack_roots`` via ``_build_pack_set()`` — no direct
``config.yaml`` read occurs there either.

T064 — Coordination note: caller updates are in owning WPs
-----------------------------------------------------------
This file (WP10) does NOT modify:
- ``src/charter/drg.py``     — owned by WP11 (T064-drg wires PackContext there)
- ``src/charter/activation/context.py`` — owned by WP01 (T006 adds the interim TODO comment)

WP10's value is this integration test suite (T065) that proves the full
``extends:`` chain works end-to-end when a ``PackContext`` is supplied.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.org_charter import (
    OrgCharterPolicy,
    load_org_charter_policies,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_pack_context(
    pack_roots: tuple[Path, ...],
    repo_root: Path | None = None,
) -> PackContext:
    """Construct a minimal ``PackContext`` pointing at the given roots.

    ``from_config()`` reads disk; here we build the dataclass directly so
    tests are hermetic (no config.yaml on disk required).
    """
    return PackContext(
        activated_kinds=frozenset(
            {
                "directives",
                "tactics",
                "paradigms",
                "styleguides",
                "toolguides",
                "procedures",
                "agent_profiles",
                "mission_step_contracts",
            }
        ),
        activated_mission_types=frozenset({"software-dev", "documentation", "research", "plan"}),
        pack_roots=pack_roots,
        org_pack_names=tuple(p.name for p in pack_roots),
        repo_root=repo_root or Path("/nonexistent"),
    )


def _write_org_charter(pack_dir: Path, body: str) -> None:
    """Write an ``org-charter.yaml`` inside *pack_dir*."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "org-charter.yaml").write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


# ---------------------------------------------------------------------------
# T065 — Integration tests
# ---------------------------------------------------------------------------


class TestFullChainResolution:
    """T065: Two org packs where B extends A; merged policy unions directives."""

    def test_full_chain_resolution_extends(self, tmp_path: Path) -> None:
        """B extends A; merged policy has directives from both A and B."""
        pack_a = tmp_path / "pack-a"
        pack_b = tmp_path / "pack-b"

        _write_org_charter(
            pack_a,
            """
            schema_version: 1
            org_name: "Corp Base"
            required_directives:
              - dir-from-a-1
              - dir-shared
            interview_defaults:
              human_in_command: true
              base_key: from-a
            """,
        )
        _write_org_charter(
            pack_b,
            """
            schema_version: 1
            extends: pack-a
            org_name: "Corp Overlay"
            required_directives:
              - dir-from-b-1
              - dir-shared
            interview_defaults:
              overlay_key: from-b
            """,
        )

        ctx = _make_pack_context((pack_a, pack_b))
        policy = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx)

        assert isinstance(policy, OrgCharterPolicy)
        # directives union: dir-from-a-1 + dir-shared + dir-from-b-1
        # (dir-shared deduped — appears once)
        assert "dir-from-a-1" in policy.required_directives
        assert "dir-from-b-1" in policy.required_directives
        assert policy.required_directives.count("dir-shared") == 1
        # interview_defaults: base_key from A survives; overlay_key from B added
        assert policy.interview_defaults["base_key"] == "from-a"
        assert policy.interview_defaults["overlay_key"] == "from-b"
        # human_in_command set in A, propagated through B chain
        assert policy.interview_defaults["human_in_command"] is True
        # org_name: last non-empty wins (B is resolved after A's chain base)
        assert policy.org_name in ("Corp Base", "Corp Overlay")


class TestPackRootsOrdering:
    """T065: org packs are processed in pack_roots order."""

    def test_pack_roots_ordering_interview_defaults(self, tmp_path: Path) -> None:
        """Later pack in pack_roots wins when keys collide in interview_defaults."""
        pack_first = tmp_path / "pack-first"
        pack_second = tmp_path / "pack-second"

        _write_org_charter(
            pack_first,
            """
            schema_version: 1
            interview_defaults:
              shared_key: "from-first"
              only_first: "yes"
            """,
        )
        _write_org_charter(
            pack_second,
            """
            schema_version: 1
            interview_defaults:
              shared_key: "from-second"
              only_second: "yes"
            """,
        )

        # pack_first is before pack_second
        ctx = _make_pack_context((pack_first, pack_second))
        policy = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx)

        # Later (second) pack wins for the shared key
        assert policy.interview_defaults["shared_key"] == "from-second"
        assert policy.interview_defaults["only_first"] == "yes"
        assert policy.interview_defaults["only_second"] == "yes"

    def test_pack_roots_ordering_reversed_wins_different_pack(self, tmp_path: Path) -> None:
        """Reversing pack_roots reverses who wins on collisions."""
        pack_alpha = tmp_path / "pack-alpha"
        pack_beta = tmp_path / "pack-beta"

        _write_org_charter(
            pack_alpha,
            """
            schema_version: 1
            interview_defaults:
              order_key: "from-alpha"
            """,
        )
        _write_org_charter(
            pack_beta,
            """
            schema_version: 1
            interview_defaults:
              order_key: "from-beta"
            """,
        )

        # alpha first: beta wins
        ctx_ab = _make_pack_context((pack_alpha, pack_beta))
        policy_ab = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx_ab)
        assert policy_ab.interview_defaults["order_key"] == "from-beta"

        # beta first: alpha wins
        ctx_ba = _make_pack_context((pack_beta, pack_alpha))
        policy_ba = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx_ba)
        assert policy_ba.interview_defaults["order_key"] == "from-alpha"


class TestBackwardCompatibility:
    """T065: load_org_charter_policies(repo_root, pack_context=None) still works."""

    def test_no_pack_context_no_config_returns_empty(self, tmp_path: Path) -> None:
        """No config.yaml and no PackContext -> empty policy, no error."""
        policy = load_org_charter_policies(tmp_path, pack_context=None)

        assert isinstance(policy, OrgCharterPolicy)
        assert policy.required_directives == []
        assert policy.interview_defaults == {}
        assert policy.governance_policies == []

    def test_no_pack_context_with_config_uses_registry(self, tmp_path: Path) -> None:
        """Without PackContext, the function reads config.yaml as before."""
        pack = tmp_path / "packs" / "legacy"
        _write_org_charter(
            pack,
            """
            schema_version: 1
            required_directives:
              - legacy-dir-001
            interview_defaults:
              legacy_key: "legacy-value"
            """,
        )
        # Write a .kittify/config.yaml pointing at the pack
        config_dir = tmp_path / ".kittify"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            f"charter_packs:\n  org:\n    packs:\n      - name: legacy\n        local_path: {pack!s}\n",
            encoding="utf-8",
        )

        # Explicitly pass pack_context=None (backward-compat form)
        policy = load_org_charter_policies(tmp_path, pack_context=None)

        assert "legacy-dir-001" in policy.required_directives
        assert policy.interview_defaults["legacy_key"] == "legacy-value"

    def test_default_argument_matches_explicit_none(self, tmp_path: Path) -> None:
        """``load_org_charter_policies(repo_root)`` equals
        ``load_org_charter_policies(repo_root, pack_context=None)``."""
        policy_default = load_org_charter_policies(tmp_path)
        policy_explicit_none = load_org_charter_policies(tmp_path, pack_context=None)

        assert policy_default.required_directives == policy_explicit_none.required_directives
        assert policy_default.interview_defaults == policy_explicit_none.interview_defaults


class TestNoConfigYamlReadInResolver:
    """T065: resolution works entirely from PackContext; config.yaml is NOT read.

    Architectural invariant (C-005 / T063): when a PackContext is provided,
    _resolve_chain() and _merge_chain() operate only on the pre-built
    pack_set dict.  No Path.read_text() calls for config.yaml exist inside
    those functions.

    We verify this behaviorally: supply a PackContext whose pack_roots
    point at temp directories populated with org-charter.yaml files, then
    assert that:
    1. The resolved policy is correct even though no .kittify/config.yaml
       exists on disk.
    2. A deliberately wrong config.yaml (if present) does not affect the
       result — the PackContext is the sole authority.
    """

    def test_resolution_works_without_config_yaml(self, tmp_path: Path) -> None:
        """PackContext resolves packs when no .kittify/config.yaml exists."""
        pack_a = tmp_path / "org-pack-a"
        _write_org_charter(
            pack_a,
            """
            schema_version: 1
            required_directives:
              - packcontext-dir-001
            """,
        )

        # No .kittify/config.yaml written to tmp_path at all
        assert not (tmp_path / ".kittify" / "config.yaml").exists()

        ctx = _make_pack_context((pack_a,), repo_root=tmp_path)
        policy = load_org_charter_policies(tmp_path, pack_context=ctx)

        assert "packcontext-dir-001" in policy.required_directives

    def test_misleading_config_yaml_is_ignored_when_pack_context_provided(self, tmp_path: Path) -> None:
        """A config.yaml pointing at a *different* pack does not influence
        the result when a PackContext is explicitly supplied."""
        # Real pack (what the test wants)
        real_pack = tmp_path / "real-pack"
        _write_org_charter(
            real_pack,
            """
            schema_version: 1
            required_directives:
              - real-dir-001
            """,
        )

        # Decoy pack (what config.yaml references)
        decoy_pack = tmp_path / "decoy-pack"
        _write_org_charter(
            decoy_pack,
            """
            schema_version: 1
            required_directives:
              - decoy-dir-999
            """,
        )

        # Write a config.yaml pointing only at the decoy
        config_dir = tmp_path / ".kittify"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            f"charter_packs:\n  org:\n    packs:\n      - name: decoy-pack\n        local_path: {decoy_pack!s}\n",
            encoding="utf-8",
        )

        # PackContext points only at the real pack — config.yaml must be ignored
        ctx = _make_pack_context((real_pack,), repo_root=tmp_path)
        policy = load_org_charter_policies(tmp_path, pack_context=ctx)

        assert "real-dir-001" in policy.required_directives
        assert "decoy-dir-999" not in policy.required_directives

    def test_empty_pack_roots_returns_empty_policy(self, tmp_path: Path) -> None:
        """PackContext with no pack_roots -> empty OrgCharterPolicy, no disk reads."""
        ctx = _make_pack_context((), repo_root=tmp_path)
        policy = load_org_charter_policies(tmp_path, pack_context=ctx)

        assert isinstance(policy, OrgCharterPolicy)
        assert policy.required_directives == []
        assert policy.interview_defaults == {}


class TestExtendsChainViaPackContext:
    """T065: full extends: chain resolver works through PackContext.pack_roots."""

    def test_chain_directives_are_unioned(self, tmp_path: Path) -> None:
        """Base + overlay directives union; overlay's extends is resolved."""
        base = tmp_path / "base-pack"
        overlay = tmp_path / "overlay-pack"

        _write_org_charter(
            base,
            """
            schema_version: 1
            required_directives:
              - base-dir-1
              - base-dir-2
            """,
        )
        _write_org_charter(
            overlay,
            """
            schema_version: 1
            extends: base-pack
            required_directives:
              - overlay-dir-1
            """,
        )

        # Both packs must be reachable via pack_roots for extends: to resolve
        ctx = _make_pack_context((base, overlay))
        policy = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx)

        assert "base-dir-1" in policy.required_directives
        assert "base-dir-2" in policy.required_directives
        assert "overlay-dir-1" in policy.required_directives

    def test_chain_interview_defaults_overlay_wins(self, tmp_path: Path) -> None:
        """Overlay's interview_defaults overwrite base when keys collide."""
        base = tmp_path / "base-pack"
        overlay = tmp_path / "overlay-pack"

        _write_org_charter(
            base,
            """
            schema_version: 1
            interview_defaults:
              shared: "base-value"
              base_only: "keep-me"
            """,
        )
        _write_org_charter(
            overlay,
            """
            schema_version: 1
            extends: base-pack
            interview_defaults:
              shared: "overlay-value"
              overlay_only: "added"
            """,
        )

        ctx = _make_pack_context((base, overlay))
        policy = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx)

        # Overlay wins on collision
        assert policy.interview_defaults["shared"] == "overlay-value"
        # Base-only key survives
        assert policy.interview_defaults["base_only"] == "keep-me"
        # Overlay-only key present
        assert policy.interview_defaults["overlay_only"] == "added"

    def test_chain_single_pack_no_extends(self, tmp_path: Path) -> None:
        """Single pack without extends: behaves identically to legacy path."""
        solo = tmp_path / "solo-pack"
        _write_org_charter(
            solo,
            """
            schema_version: 1
            org_name: "Solo Corp"
            required_directives:
              - solo-dir-001
            interview_defaults:
              solo_key: "value"
            """,
        )

        ctx = _make_pack_context((solo,))
        policy = load_org_charter_policies(Path("/nonexistent"), pack_context=ctx)

        assert policy.org_name == "Solo Corp"
        assert "solo-dir-001" in policy.required_directives
        assert policy.interview_defaults["solo_key"] == "value"
