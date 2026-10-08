"""Unit tests for the activation relocation onto ``charter.yaml`` (WP02, T010).

Covers the read seam (``charter.activation.pack_context.PackContext.from_config``)
after the activation state moves from ``.kittify/config.yaml`` into
``charter.yaml``, reached via the config's ``charter:`` pointer
(data-model.md INV-2/INV-4/INV-5/INV-8, contracts/active-doctrine-resolution.md).

Behavior-preserving two-branch design under test:

* ``charter:`` pointer ABSENT -> legacy/un-migrated project. Activation is
  read directly from ``config.yaml`` (pre-relocation behavior, byte-for-byte
  unchanged — pinned separately by ``tests/charter/test_pack_context.py``,
  which never sets a pointer and MUST stay green).
* ``charter:`` pointer PRESENT -> migrated project. Activation is read from
  the pointed-at ``charter.yaml``; ``config.yaml`` no longer needs
  ``activated_*`` keys. A dangling/unreadable pointer fails loud (INV-5,
  #2530) rather than silently falling back to config.yaml or to the
  default-pack.
* ``org_pack_names`` / ``pack_roots`` always come from ``config.yaml``
  regardless of which branch supplies activation (two-file read, G7).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.pack_context import ActiveCharterConfigError, PackContext


pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _write_charter_yaml(tmp_path: Path, content: str) -> Path:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.yaml"
    charter_path.write_text(content, encoding="utf-8")
    return charter_path


_POINTER_CONFIG = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
"""

_MIGRATED_CHARTER_YAML = """\
schema_version: "2.0.0"
governance:
  testing: {}
directives: []
catalog: {}
activated_kinds:
  - directives
  - tactics
mission_type_activations:
  - software-dev
activated_directives:
  - 001-architectural-integrity-standard
  - 010-specification-fidelity-requirement
activated_tactics:
  - acceptance-test-first
metadata:
  bundle_schema_version: 2
"""


# ---------------------------------------------------------------------------
# ATDD (red-first): from_config reads activated_directives from charter.yaml
# via the pointer, and config.yaml no longer needs activated_* directly.
# ---------------------------------------------------------------------------


def test_from_config_reads_activated_directives_from_charter_yaml_via_pointer(
    tmp_path: Path,
) -> None:
    """RED until T006: activation comes from charter.yaml, not config.yaml."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset(
        {"001-architectural-integrity-standard", "010-specification-fidelity-requirement"}
    )
    assert ctx.activated_tactics == frozenset({"acceptance-test-first"})
    assert ctx.activated_kinds == frozenset({"directives", "tactics"})
    assert ctx.activated_mission_types == frozenset({"software-dev"})


def test_config_yaml_has_no_activated_star_keys_when_migrated(tmp_path: Path) -> None:
    """A migrated project's config.yaml carries only the pointer — no
    activated_* keys — and from_config still resolves activation correctly
    entirely from charter.yaml."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)

    config_text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "activated_" not in config_text

    ctx = PackContext.from_config(tmp_path)
    assert ctx.activated_directives is not None
    assert "001-architectural-integrity-standard" in ctx.activated_directives


# ---------------------------------------------------------------------------
# Three-state fidelity, sourced from charter.yaml (T006)
# ---------------------------------------------------------------------------


def test_activated_paradigms_absent_from_charter_yaml_returns_none(tmp_path: Path) -> None:
    """Absent key in charter.yaml -> None (all built-ins available) — SC-008:
    absent must NEVER be silently converted to an empty list."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)  # no activated_paradigms key

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_paradigms is None


def test_activated_paradigms_empty_list_in_charter_yaml_returns_empty_frozenset(
    tmp_path: Path,
) -> None:
    """Explicit [] in charter.yaml -> frozenset() (fail-closed, nothing active)."""
    _write_config(tmp_path, _POINTER_CONFIG)
    content = _MIGRATED_CHARTER_YAML + "activated_paradigms: []\n"
    _write_charter_yaml(tmp_path, content)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_paradigms == frozenset()


def test_activated_agent_profiles_populated_in_charter_yaml_returns_exact_set(
    tmp_path: Path,
) -> None:
    """Non-empty list in charter.yaml -> exact frozenset of ids."""
    _write_config(tmp_path, _POINTER_CONFIG)
    content = (
        _MIGRATED_CHARTER_YAML
        + "activated_agent_profiles:\n  - python-pedro\n  - reviewer-renata\n"
    )
    _write_charter_yaml(tmp_path, content)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_agent_profiles == frozenset({"python-pedro", "reviewer-renata"})


# ---------------------------------------------------------------------------
# Two-file read (G7): org_pack_names / pack_roots always from config.yaml
# ---------------------------------------------------------------------------


def test_org_pack_names_read_from_config_yaml_even_when_migrated(tmp_path: Path) -> None:
    """org_packs stay in config.yaml regardless of the activation source
    (data-model.md 'Entity: .kittify/config.yaml (after relocation)')."""
    pack_dir = tmp_path / "acme-pack"
    pack_dir.mkdir()
    config_content = f"""\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
charter_packs:
  org:
    packs:
      - name: acme-pack
        local_path: {pack_dir}
"""
    _write_config(tmp_path, config_content)
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)

    ctx = PackContext.from_config(tmp_path)

    assert "acme-pack" in ctx.org_pack_names
    assert ctx.pack_roots[1] == pack_dir
    # Activation still resolved from charter.yaml, not affected by org_packs.
    assert ctx.activated_directives is not None


# ---------------------------------------------------------------------------
# Fail-loud: dangling / unreadable pointer (INV-5, re-homed #2530)
# ---------------------------------------------------------------------------


def test_dangling_charter_pointer_raises(tmp_path: Path) -> None:
    """A pointer naming a charter.yaml that does not exist must fail loud —
    never silently fall back to config.yaml or the default pack."""
    _write_config(tmp_path, _POINTER_CONFIG)
    # Deliberately do NOT create .kittify/charter/charter.yaml.

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


def test_malformed_charter_yaml_raises(tmp_path: Path) -> None:
    """Invalid YAML in the pointed-at charter.yaml fails loud (fails closed,
    never falls back to defaults)."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, "activated_directives: [unterminated\n")

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


def test_non_mapping_charter_yaml_root_raises(tmp_path: Path) -> None:
    """A charter.yaml whose root is not a mapping (e.g. a bare list) fails
    loud instead of being silently treated as empty."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, "- not\n- a\n- mapping\n")

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


def test_malformed_activation_value_in_charter_yaml_raises(tmp_path: Path) -> None:
    """A non-list activation value in charter.yaml must not fail open."""
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, "activated_directives: not-a-list\n")

    with pytest.raises(ActiveCharterConfigError, match="ACTIVE_CHARTER_CONFIG_INVALID"):
        PackContext.from_config(tmp_path)


# ---------------------------------------------------------------------------
# Absent-config default-pack fallback (distinguished from a dangling
# pointer — T009): no project config at all -> default fallback, unchanged.
# ---------------------------------------------------------------------------


def test_no_config_yaml_at_all_returns_empty_mission_types(tmp_path: Path) -> None:
    """No .kittify/config.yaml whatsoever -> ``activated_mission_types`` is an
    empty frozenset (construction is total; no raise).

    Historically (pre-WP04) this scenario fell back to the built-in default
    pack for ``activated_mission_types``; an intermediate WP04 iteration made
    it a construction ``ActiveCharterConfigError``. The final WP04
    re-architecture made construction TOTAL: an absent ``mission_type_
    activations`` reads as ``frozenset()`` (never the all-four backfill,
    never a raise), because ``PackContext`` sits on dozens of read / compose
    hot paths that must not crash. The fail-closed for an empty set moved to
    the mission-create boundary. The identical scenario is pinned by this
    WP's own ``tests/charter/test_pack_context.py::
    test_from_config_no_config_yaml_returns_empty_not_raise``.
    """
    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_mission_types == frozenset()


def test_config_yaml_present_without_pointer_uses_legacy_read(tmp_path: Path) -> None:
    """config.yaml present but with no 'charter:' key -> legacy/un-migrated
    project: activation is read directly from config.yaml (unchanged), even
    though this WP's relocation has landed in code."""
    content = """\
vcs:
  type: git
mission_type_activations:
  - software-dev
activated_directives:
  - 099-legacy-only-directive
"""
    _write_config(tmp_path, content)
    # No charter.yaml anywhere — must NOT be required when there's no pointer.

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset({"099-legacy-only-directive"})


# ---------------------------------------------------------------------------
# Migrated charter.yaml activation takes precedence over stale config keys
# ---------------------------------------------------------------------------


def test_migrated_project_ignores_stale_activated_keys_left_in_config(
    tmp_path: Path,
) -> None:
    """Once a project carries a 'charter:' pointer, any (stale) activated_*
    keys still lingering in config.yaml are ignored — charter.yaml is the
    sole activation authority post-migration."""
    content = _POINTER_CONFIG + "activated_directives:\n  - stale-config-directive\n"
    _write_config(tmp_path, content)
    _write_charter_yaml(tmp_path, _MIGRATED_CHARTER_YAML)

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset(
        {"001-architectural-integrity-standard", "010-specification-fidelity-requirement"}
    )
    assert "stale-config-directive" not in ctx.activated_directives


# ---------------------------------------------------------------------------
# resolve_charter_yaml_pointer — the shared helper, exercised directly
# ---------------------------------------------------------------------------


def test_resolve_charter_yaml_pointer_absent_returns_none(tmp_path: Path) -> None:
    from charter.activation.pack_context import resolve_charter_yaml_pointer

    assert resolve_charter_yaml_pointer(tmp_path, {}) is None


def test_resolve_charter_yaml_pointer_resolves_relative_to_repo_root(
    tmp_path: Path,
) -> None:
    from charter.activation.pack_context import resolve_charter_yaml_pointer

    resolved = resolve_charter_yaml_pointer(
        tmp_path, {"charter": ".kittify/charter/charter.yaml"}
    )

    assert resolved == tmp_path / ".kittify" / "charter" / "charter.yaml"


def test_resolve_charter_yaml_pointer_mapping_value_is_not_a_pointer(
    tmp_path: Path,
) -> None:
    """A mapping-valued ``charter:`` key (the pre-#2773 inline namespace
    holding e.g. ``synthesis_inputs``) is NOT a charter.yaml pointer: it must
    resolve to ``None`` (legacy inline read) rather than being stringified into
    a bogus ``.../{'synthesis_inputs': ...}`` path that then "does not exist".
    Mirrors ``load_url_list_from_config``'s tolerance for the same shape."""
    from charter.activation.pack_context import resolve_charter_yaml_pointer

    inline = {"charter": {"synthesis_inputs": {"url_list": ["https://example.com/g"]}}}

    assert resolve_charter_yaml_pointer(tmp_path, inline) is None


def test_from_config_with_inline_charter_mapping_uses_legacy_read(
    tmp_path: Path,
) -> None:
    """``charter:`` present as an inline mapping (not a string pointer) must be
    treated as the legacy/un-migrated state: activation is read from the
    top-level config.yaml keys, and no ACTIVE_CHARTER_CONFIG_INVALID is raised
    for the mapping value (regression guard for #2850)."""
    content = """\
vcs:
  type: git
mission_type_activations:
  - software-dev
charter:
  synthesis_inputs:
    url_list:
      - https://example.com/governance
activated_directives:
  - 099-legacy-only-directive
"""
    _write_config(tmp_path, content)
    # No charter.yaml file — the mapping value must NOT be read as a pointer.

    ctx = PackContext.from_config(tmp_path)

    assert ctx.activated_directives == frozenset({"099-legacy-only-directive"})
