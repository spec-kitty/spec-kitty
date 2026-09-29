"""Unit tests for ``charter.activation.pack_context.PackContext`` (WP06, T040; WP04, T019/T022).

Covers:
- T040-1: ``PackContext.from_config()`` with a provisioned config.yaml (the
  ``mission_type_activations`` key explicitly present, as WP03 provisioning
  writes it) produces correct ``activated_mission_types`` (C-A6 parity).
- T040-2 (WP04 re-architecture): ``PackContext.from_config()`` with no
  config.yaml at all -- the ``mission_type_activations`` key is genuinely
  absent -- construction is TOTAL and returns ``frozenset()`` (never raises,
  never the all-four built-in backfill: absent != all-four). The fail-closed
  for an empty activation set moved to the mission-create / mission-type-use
  boundary (``create_mission_core``); construction must stay total because
  ``PackContext`` is built on dozens of read / compose hot paths.
- T040-3: ``PackContext`` is immutable (``FrozenInstanceError`` on mutation).
- T040-4: ``pack_roots`` is a ``tuple`` (not a list).
- T040-5: ``activated_kinds`` is a ``frozenset``.
- T040-6: ``PackContext`` can be used as a dict key (frozen dataclasses are
  hashable).
- T040-7: ``activated_kinds`` defaults to all built-in kinds (incl.
  ``templates``/``assets``, FR-001/FR-011) when key is absent.
- T040-8: ``activated_kinds`` is read from config when key is present.
- T040-9: ``mission_type_activations`` list is read from config when present.
- T040-10: ``org_pack_names`` and extra pack roots populated from config.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from charter.activation.pack_context import (
    CharterPackConfigError,
    PackContext,
    _BUILTIN_ARTIFACT_KINDS,
)
from charter.offering.missions.mission_type_repository import builtin_mission_type_id_set


pytestmark = [pytest.mark.fast]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: A minimal but PROVISIONED config: ``mission_type_activations`` is
#: explicitly present (as WP03 provisioning writes it for every real
#: project), listing all four built-ins. This is the fixture used by every
#: test in this module that exercises something OTHER than the
#: mission-type-activation fallback itself -- since WP04 removed the
#: config-absent backfill, an unprovisioned config now fails closed, and
#: these unrelated tests need a config that constructs successfully.
_MINIMAL_CONFIG = """\
vcs:
  type: git
agents:
  available:
    - claude
mission_type_activations:
  - software-dev
  - documentation
  - research
  - plan
"""

_CONFIG_WITH_ACTIVATIONS = """\
vcs:
  type: git
mission_type_activations:
  - software-dev
  - documentation
activated_kinds:
  - directives
  - tactics
"""

_CONFIG_WITH_ORG_PACKS = """\
vcs:
  type: git
mission_type_activations:
  - software-dev
  - documentation
  - research
  - plan
doctrine:
  org:
    packs:
      - name: acme-pack
        local_path: {pack_path}
"""


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


#: The provisioned ``mission_type_activations`` YAML block (WP03 shape).
#: Prepended to config fixtures below that test something OTHER than the
#: mission-type-activation fallback itself, so ``PackContext.from_config``
#: doesn't fail closed on an unrelated test's fixture (WP04 T020 removed
#: the config-absent backfill).
_PROVISIONED_MISSION_TYPES_YAML = (
    "mission_type_activations:\n  - software-dev\n  - documentation\n  - research\n  - plan\n"
)


# ---------------------------------------------------------------------------
# T040-1 / WP04 T019(a): from_config with a PROVISIONED config (key present,
# all four built-ins) → activated_mission_types returns exactly those four.
# This is the C-A6/NFR-003 authority parity case, measured at the activation
# authority (PackContext), not at list_available_missions.
# ---------------------------------------------------------------------------


def test_from_config_provisioned_with_all_builtins_returns_exactly_those_four(
    tmp_path: Path,
) -> None:
    """``mission_type_activations`` present (provisioned with the four
    built-ins) → ``activated_mission_types`` returns exactly those four --
    no more, no fewer -- read from the explicit list, never a fallback."""
    _write_config(tmp_path, _MINIMAL_CONFIG)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_mission_types == builtin_mission_type_id_set()
    assert "software-dev" in ctx.activated_mission_types
    assert "documentation" in ctx.activated_mission_types
    assert "research" in ctx.activated_mission_types
    assert "plan" in ctx.activated_mission_types


# ---------------------------------------------------------------------------
# T040-2 / WP04 (re-architecture): from_config with no config.yaml at all →
# the mission_type_activations key is genuinely absent → construction is
# TOTAL and returns ``frozenset()`` (never raises, never the all-four
# built-in backfill). ``PackContext`` is built on dozens of read / compose
# hot paths that must not crash on an unprovisioned project; the fail-closed
# for an empty set moved to the mission-create / mission-type-use boundary
# (``create_mission_core``), verified in
# ``tests/core/test_mission_create_activation_gate.py``.
# ---------------------------------------------------------------------------


def test_from_config_no_config_yaml_returns_empty_not_raise(tmp_path: Path) -> None:
    """No ``.kittify/config.yaml`` at all → ``mission_type_activations`` is
    genuinely absent → ``activated_mission_types`` is an empty frozenset,
    NOT a raise and NEVER the builtin roster (absent != all-four)."""
    # Don't write any config -- the key is genuinely absent.
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_mission_types == frozenset()
    assert isinstance(ctx.activated_mission_types, frozenset)


def test_from_config_explicit_empty_mission_type_list_returns_empty(
    tmp_path: Path,
) -> None:
    """An explicit empty list (``mission_type_activations: []``, C-008) reads
    as ``frozenset()`` -- the SAME total outcome as an absent key. Neither
    shape backfills the built-in roster, and neither raises at construction.
    """
    _write_config(tmp_path, "vcs:\n  type: git\nmission_type_activations: []\n")

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_mission_types == frozenset()


def test_from_config_provisioned_minimal_config_other_defaults_unchanged(
    tmp_path: Path,
) -> None:
    """Scope guard: a provisioned-but-otherwise-minimal config still defaults
    ``activated_kinds``/``org_pack_names``/``repo_root`` the same way as
    before -- only the ``mission_type_activations`` fallback changed."""
    _write_config(tmp_path, _MINIMAL_CONFIG)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_kinds == _BUILTIN_ARTIFACT_KINDS
    assert ctx.org_pack_names == ()
    assert ctx.repo_root == tmp_path


# ---------------------------------------------------------------------------
# T040-3: PackContext is immutable
# ---------------------------------------------------------------------------


def test_pack_context_is_immutable(tmp_path: Path) -> None:
    """Attempting to set a field raises FrozenInstanceError."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.activated_kinds = frozenset({"directives"})  # type: ignore[misc]


def test_pack_roots_contains_builtin_root(tmp_path: Path) -> None:
    """pack_roots[0] must point at the built-in offer catalogue root (src/charter/offering/, relocated from src/charter/offering/ in M2 charter-code-topology)."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    assert len(ctx.pack_roots) >= 1
    builtin = ctx.pack_roots[0]
    # The built-in offer catalogue root is src/charter/offering/ (relocated from
    # src/charter/offering/ in M2); the packaged pack root is its `built_in` data dir.
    assert builtin.exists()
    assert builtin.name == "offering"


# ---------------------------------------------------------------------------
# T040-6: PackContext is hashable (can be used as dict key)
# ---------------------------------------------------------------------------


def test_pack_context_is_hashable(tmp_path: Path) -> None:
    """Frozen dataclasses are hashable; PackContext can be used as a dict key."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    d: dict[PackContext, str] = {}
    d[ctx] = "value"
    assert d[ctx] == "value"


# ---------------------------------------------------------------------------
# T040-7: activated_kinds defaults to all built-in kinds when key absent
# ---------------------------------------------------------------------------


def test_activated_kinds_defaults_to_all_builtin_when_key_absent(tmp_path: Path) -> None:
    """When activated_kinds key is absent -> all built-in kinds (incl. templates/assets)."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_kinds == _BUILTIN_ARTIFACT_KINDS
    # FR-001/FR-011 (asset-kind mission): templates + assets are node-declarable
    # org-pack DRG kinds added to the default set in lockstep with
    # ``charter.activation.activations._ALLOWED_KINDS`` and
    # ``charter.offering.drg.org_pack_loader._ORG_DRG_CANONICAL_KINDS``.
    assert {"templates", "assets"} <= ctx.activated_kinds


# ---------------------------------------------------------------------------
# T040-8: activated_kinds read from config when key present
# ---------------------------------------------------------------------------


def test_activated_kinds_read_from_config_when_present(tmp_path: Path) -> None:
    """When activated_kinds is in config, use that list."""
    _write_config(tmp_path, _CONFIG_WITH_ACTIVATIONS)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_kinds == frozenset({"directives", "tactics"})


# ---------------------------------------------------------------------------
# T040-9: mission_type_activations read from config when present
# ---------------------------------------------------------------------------


def test_activated_mission_types_read_from_config(tmp_path: Path) -> None:
    """When mission_type_activations is in config, use that list."""
    _write_config(tmp_path, _CONFIG_WITH_ACTIVATIONS)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_mission_types == frozenset({"software-dev", "documentation"})


# ---------------------------------------------------------------------------
# T040-10: org_pack_names populated from config
# ---------------------------------------------------------------------------


def test_org_pack_names_and_roots_populated(tmp_path: Path) -> None:
    """When doctrine.org.packs is present, org_pack_names and pack_roots are populated."""
    # Create a fake pack directory
    pack_dir = tmp_path / "acme-pack"
    pack_dir.mkdir()
    content = _CONFIG_WITH_ORG_PACKS.format(pack_path=pack_dir)
    _write_config(tmp_path, content)

    ctx = PackContext.from_config(tmp_path)

    assert "acme-pack" in ctx.org_pack_names
    # pack_roots has the built-in root first, then the org pack root
    assert [p.name for p in ctx.pack_roots] == ["offering", pack_dir.name]
    assert ctx.pack_roots[0].name == "offering"  # built-in
    assert ctx.pack_roots[1] == pack_dir


# ---------------------------------------------------------------------------
# Additional: repo_root is stored
# ---------------------------------------------------------------------------


def test_repo_root_is_stored(tmp_path: Path) -> None:
    """repo_root field is set to the provided repo_root."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.repo_root == tmp_path


# ---------------------------------------------------------------------------
# Additional: PackContext exported from charter namespace
# ---------------------------------------------------------------------------


def test_pack_context_exported_from_charter_namespace() -> None:
    """PackContext must be importable from the top-level charter namespace."""
    from charter import PackContext as PackContextFromCharter  # noqa: PLC0415

    assert PackContextFromCharter is PackContext


# ---------------------------------------------------------------------------
# FR-039: empty list must produce frozenset(), not built-in fallback
# ---------------------------------------------------------------------------


def test_activated_kinds_empty_list_returns_frozenset_not_builtin_fallback(
    tmp_path: Path,
) -> None:
    """FR-039 regression: [] must produce frozenset(), not built-in fallback."""
    content = f"""\
vcs:
  type: git
activated_kinds: []
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_kinds == frozenset()
    assert ctx.activated_kinds is not None  # extra clarity: frozenset() != None


# ---------------------------------------------------------------------------
# Three-state tests: activated_directives (T010)
# ---------------------------------------------------------------------------


def test_activated_directives_absent_returns_none(tmp_path: Path) -> None:
    """Absent key → None (all built-ins available)."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives is None


def test_activated_directives_empty_list_returns_empty_frozenset(tmp_path: Path) -> None:
    """[] → frozenset() (explicitly nothing activated)."""
    content = f"""\
vcs:
  type: git
activated_directives: []
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset()


def test_activated_directives_populated_returns_frozenset(tmp_path: Path) -> None:
    """Non-empty list → frozenset of IDs."""
    content = f"""\
vcs:
  type: git
activated_directives:
  - dir-001
  - dir-002
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset({"dir-001", "dir-002"})


# ---------------------------------------------------------------------------
# Three-state tests: activated_agent_profiles (T010)
# ---------------------------------------------------------------------------


def test_activated_agent_profiles_absent_returns_none(tmp_path: Path) -> None:
    """Absent key → None (all built-ins available)."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_agent_profiles is None


def test_activated_agent_profiles_empty_list_returns_empty_frozenset(
    tmp_path: Path,
) -> None:
    """[] → frozenset() (explicitly nothing activated)."""
    content = f"""\
vcs:
  type: git
activated_agent_profiles: []
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_agent_profiles == frozenset()


def test_activated_agent_profiles_populated_returns_frozenset(tmp_path: Path) -> None:
    """Non-empty list → frozenset of IDs."""
    content = f"""\
vcs:
  type: git
activated_agent_profiles:
  - python-pedro
  - reviewer-renata
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_agent_profiles == frozenset({"python-pedro", "reviewer-renata"})


# ---------------------------------------------------------------------------
# Structural test: all 11 activated_* fields exist (T010, extended WP04 T021)
# ---------------------------------------------------------------------------


def test_packcontext_has_all_eleven_activated_fields(tmp_path: Path) -> None:
    """Structural guard: all 11 activated_* fields exist with correct defaults."""
    _write_config(tmp_path, _MINIMAL_CONFIG)
    ctx = PackContext.from_config(tmp_path)

    # Existing fields: activated_kinds still defaults when its key is absent
    # (a different, out-of-scope contract); activated_mission_types is read
    # from the explicit provisioned list in _MINIMAL_CONFIG (WP04: no
    # implicit backfill any more when the key is genuinely absent).
    assert ctx.activated_kinds is not None
    assert ctx.activated_mission_types is not None

    # New fields (all default to None when key is absent)
    assert ctx.activated_directives is None
    assert ctx.activated_tactics is None
    assert ctx.activated_styleguides is None
    assert ctx.activated_toolguides is None
    assert ctx.activated_paradigms is None
    assert ctx.activated_procedures is None
    assert ctx.activated_agent_profiles is None
    assert ctx.activated_mission_step_contracts is None
    assert ctx.activated_glossary_packs is None


# ---------------------------------------------------------------------------
# Malformed values must not fail open.
# ---------------------------------------------------------------------------


def test_activated_directives_malformed_value_raises(tmp_path: Path) -> None:
    """A non-list value for activated_directives must not fail open."""
    content = f"""\
vcs:
  type: git
activated_directives: not-a-list
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)

    with pytest.raises(CharterPackConfigError, match="CHARTER_PACK_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


def test_activated_tactics_malformed_value_raises(tmp_path: Path) -> None:
    """A non-list value for activated_tactics must not fail open."""
    content = f"""\
vcs:
  type: git
activated_tactics: 42
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)

    with pytest.raises(CharterPackConfigError, match="CHARTER_PACK_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


def test_invalid_config_yaml_raises_instead_of_using_defaults(tmp_path: Path) -> None:
    """Malformed config.yaml must not restore default-all activation."""
    _write_config(tmp_path, "activated_directives: [unterminated\n")

    with pytest.raises(CharterPackConfigError, match="CHARTER_PACK_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


# ---------------------------------------------------------------------------
# charter.mission_steps re-export surface (FR-011 facade)
# ---------------------------------------------------------------------------


def test_charter_mission_steps_exports_repository_and_model() -> None:
    """charter.mission_steps must re-export MissionStepRepository and MissionStep."""
    from charter.mission_steps import MissionStep, MissionStepRepository  # noqa: PLC0415

    assert MissionStepRepository is not None
    assert MissionStep is not None


# ---------------------------------------------------------------------------
# Fail-closed: pack-config resolution errors propagate (must not disable org packs)
# ---------------------------------------------------------------------------


def test_from_config_unset_pack_env_var_propagates_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An org pack ``local_path`` referencing an unset env var must fail closed.

    ``_read_org_packs`` resolves ``effective_root`` inside its try so a
    resolution-time ``OrgPackEnvVarUnsetError`` re-raises (never swallowed into
    a silent empty registry that would drop the pack's governance).
    """
    from charter.offering.drg.org_pack_config import OrgPackEnvVarUnsetError  # noqa: PLC0415

    monkeypatch.delenv("SPEC_KITTY_PACK_HOME_FIXTURE_UNSET", raising=False)
    content = f"""\
vcs:
  type: git
doctrine:
  org:
    packs:
      - name: acme-pack
        local_path: ${{SPEC_KITTY_PACK_HOME_FIXTURE_UNSET}}/acme-pack
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)

    with pytest.raises(OrgPackEnvVarUnsetError):
        PackContext.from_config(tmp_path)


def test_from_config_subdir_escape_propagates_fail_closed(tmp_path: Path) -> None:
    """An org pack ``subdir`` that escapes outside ``local_path`` must fail closed.

    A symlink-escape is an operator-actionable config error, not a missing-pack
    condition — ``PackContext.from_config`` must propagate ``OrgPackSubdirEscapeError``
    instead of silently returning a context with the escaping pack dropped.
    """
    from charter.offering.drg.org_pack_config import OrgPackSubdirEscapeError  # noqa: PLC0415

    # Create a pack root and an outside directory, then a symlink inside
    # the pack root pointing outside (the same pattern as TestSymlinkEscape).
    pack_root = tmp_path / "acme-pack"
    pack_root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    escape_link = pack_root / "escape"
    escape_link.symlink_to(outside_dir)

    content = f"""\
vcs:
  type: git
doctrine:
  org:
    packs:
      - name: acme-pack
        local_path: {pack_root}
        subdir: escape
{_PROVISIONED_MISSION_TYPES_YAML}"""
    _write_config(tmp_path, content)

    with pytest.raises(OrgPackSubdirEscapeError):
        PackContext.from_config(tmp_path)
