"""Scoped agent-profile sentinel read (#6917).

The read-only work-package board needs one structural boolean per claimed row
(``profile.sentinel``, the 👤 human-in-charge marker). Before this mission that
boolean cost a whole ``AgentProfileRepository`` load — every shipped profile
document plus the lineage graph.

These tests pin the scoped replacement:

* the scope is *scoped* (it really filters), and it agrees with the full
  repository for every id it returns;
* the layer order, the field merge, the ``applies_to_languages`` gate and the
  default (unscoped) load are unchanged;
* the shipped lineage graph is built on first lineage use, not in the
  constructor, so a profile-map reader never parses it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import charter.offering.agent_profiles.repository as repository_module
from charter.activation.active_charter_service_builder import (
    build_active_charter_service,
    build_agent_profile_sentinels,
)
from charter.offering.agent_profiles.repository import AgentProfileRepository
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.unit, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).parents[2]
_SHIPPED_DIR = _REPO_ROOT / "packs" / "built-in" / "agent_profiles"

_HIC_ID = "human-in-charge"

_EMPTY_DRG = {
    "schema_version": "1.0",
    "generated_at": "1970-01-01T00:00:00Z",
    "generated_by": "tests/charter/test_agent_profile_scoped_load.py",
    "nodes": [],
    "edges": [],
}


def _shipped_profile_yaml(profile_id: str = _HIC_ID) -> str:
    return (_SHIPPED_DIR / f"{profile_id}.agent.yaml").read_text(encoding="utf-8")


def _with_sentinel(text: str, sentinel: bool) -> str:
    return text.replace("sentinel: true", f"sentinel: {'true' if sentinel else 'false'}")


def _write_profile(directory: Path, profile_id: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{profile_id}.agent.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _offering_service(
    *,
    org_dir: Path | None = None,
    overlay_dir: Path | None = None,
    active_languages: list[str] | None = None,
) -> CharterOfferingService:
    return CharterOfferingService(
        project_root=None,
        org_roots=[org_dir] if org_dir is not None else [],
        active_languages=active_languages,
        agent_profile_overlay_dir=overlay_dir,
    )


# --------------------------------------------------------------------------- #
# Scope really scopes, and agrees with the full repository
# --------------------------------------------------------------------------- #


def test_scoped_load_returns_only_the_requested_ids() -> None:
    """The scope filters (positive control: the full catalogue is much larger)."""
    full = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)
    requested = [_HIC_ID, "python-pedro"]

    scoped = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, only_ids=requested)

    assert len(full.list_all()) > len(requested), "fixture: the shipped catalogue must exceed the requested set"
    assert sorted(profile.profile_id for profile in scoped.list_all()) == sorted(requested)


def test_scoped_load_matches_the_full_repository_for_every_shipped_profile() -> None:
    """Every shipped id agrees with the unscoped load — the parity contract."""
    full = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)
    ids = sorted(profile.profile_id for profile in full.list_all())
    requested = [profile_id for profile_id in ids if profile_id != "human-in-charge"]
    requested.append(_HIC_ID)

    scoped = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, only_ids=requested)

    assert {profile.profile_id: profile.sentinel for profile in scoped.list_all()} == {
        profile_id: (full.get(profile_id).sentinel if full.get(profile_id) else False) for profile_id in requested
    }


def test_duplicate_blank_and_non_string_ids_are_tolerated() -> None:
    """The scope normalises its input instead of trusting it."""
    scoped = AgentProfileRepository(
        built_in_dir=_SHIPPED_DIR,
        only_ids=[_HIC_ID, _HIC_ID, "", "   ", None, 42],  # type: ignore[list-item]
    )

    assert [profile.profile_id for profile in scoped.list_all()] == [_HIC_ID]


def test_unknown_id_loads_nothing() -> None:
    """An id no layer ships yields an empty repository, not an exception."""
    scoped = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, only_ids=["no-such-profile"])

    assert scoped.list_all() == []


# --------------------------------------------------------------------------- #
# Layer parity: overlay field merge, project-over-org precedence
# --------------------------------------------------------------------------- #


def test_project_overlay_metadata_change_keeps_the_built_in_sentinel(tmp_path: Path) -> None:
    """A project overlay that only extends metadata inherits ``sentinel: true``."""
    overlay = tmp_path / "agent_profiles"
    _write_profile(overlay, _HIC_ID, _shipped_profile_yaml().replace("Human in Charge", "Human in Charge (project)"))

    sentinels = _offering_service(overlay_dir=overlay).agent_profile_sentinels([_HIC_ID])

    # Same fixture, full repository: the scoped answer must agree with it.
    full = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, project_dir=overlay)
    assert sentinels == {_HIC_ID: True}
    assert full.get(_HIC_ID) is not None and full.get(_HIC_ID).sentinel is True


def test_project_overlay_can_flip_the_sentinel(tmp_path: Path) -> None:
    """A higher layer that declares ``sentinel: false`` wins — same fixture as above."""
    overlay = tmp_path / "agent_profiles"
    _write_profile(overlay, _HIC_ID, _with_sentinel(_shipped_profile_yaml(), False))

    sentinels = _offering_service(overlay_dir=overlay).agent_profile_sentinels([_HIC_ID])

    full = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, project_dir=overlay)
    assert sentinels == {_HIC_ID: False}
    assert full.get(_HIC_ID) is not None and full.get(_HIC_ID).sentinel is False


def test_org_pack_override_flips_the_sentinel_and_project_restores_it(tmp_path: Path) -> None:
    """Layer order is built-in → org → project for the scoped read too."""
    org_dir = tmp_path / "org-pack" / "agent_profiles"
    overlay = tmp_path / "agent_profiles"
    _write_profile(org_dir, _HIC_ID, _with_sentinel(_shipped_profile_yaml(), False))

    org_only = _offering_service(org_dir=tmp_path / "org-pack").agent_profile_sentinels([_HIC_ID])
    assert org_only == {_HIC_ID: False}

    _write_profile(overlay, _HIC_ID, _shipped_profile_yaml())
    with_project = _offering_service(org_dir=tmp_path / "org-pack", overlay_dir=overlay).agent_profile_sentinels(
        [_HIC_ID]
    )
    assert with_project == {_HIC_ID: True}


# --------------------------------------------------------------------------- #
# Language scope parity
# --------------------------------------------------------------------------- #


def test_language_scoped_profile_answers_false_like_the_full_repository(tmp_path: Path) -> None:
    """``applies_to_languages`` excludes an id here exactly as ``get()`` excludes it."""
    overlay = tmp_path / "agent_profiles"
    custom = _shipped_profile_yaml().replace('profile-id: "human-in-charge"', 'profile-id: "custom-java-only"')
    custom = _with_sentinel(custom, True).replace(
        'schema-version: "1.0"', 'schema-version: "1.0"\napplies_to_languages:\n- java'
    )
    _write_profile(overlay, "custom-java-only", custom)

    python_only = _offering_service(overlay_dir=overlay, active_languages=["python"]).agent_profile_sentinels(
        ["custom-java-only"]
    )
    java = _offering_service(overlay_dir=overlay, active_languages=["java"]).agent_profile_sentinels(
        ["custom-java-only"]
    )

    full_python = AgentProfileRepository(
        built_in_dir=_SHIPPED_DIR, project_dir=overlay, active_languages=["python"]
    )
    assert python_only == {"custom-java-only": False}
    assert full_python.get("custom-java-only") is None
    # Positive control on the same fixture: admitted when the language matches.
    assert java == {"custom-java-only": True}


def test_non_string_and_blank_ids_yield_an_empty_mapping() -> None:
    assert _offering_service().agent_profile_sentinels(["", None, 7]) == {}  # type: ignore[list-item]


def test_unresolved_id_answers_false_rather_than_vanishing() -> None:
    """The mapping is total over the requested ids: no layer ships it ⇒ ``False``."""
    assert _offering_service().agent_profile_sentinels(["no-such-profile"]) == {"no-such-profile": False}


# --------------------------------------------------------------------------- #
# Lineage graph is built on first use, never by a profile-map reader
# --------------------------------------------------------------------------- #


def test_scoped_and_plain_reads_do_not_parse_the_lineage_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A profile-map reader must not pay for the 358-node shipped DRG (#6462, restored)."""
    calls: list[int] = []
    real_loader = repository_module.load_built_in_graph

    def _counting_loader():  # noqa: ANN202 - mirrors the seam's signature
        calls.append(1)
        return real_loader()

    monkeypatch.setattr(repository_module, "load_built_in_graph", _counting_loader)

    scoped = AgentProfileRepository(built_in_dir=_SHIPPED_DIR, only_ids=[_HIC_ID])
    assert scoped.get(_HIC_ID) is not None and scoped.get(_HIC_ID).sentinel is True
    assert [profile.profile_id for profile in scoped.list_all()] == [_HIC_ID]
    plain = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)
    assert len(plain.list_all()) > 1
    assert calls == [], "a profile-map reader parsed the shipped lineage graph"

    # Positive control on the same patch: a lineage answer does build the graph.
    assert isinstance(scoped.drg.nodes, list)
    assert calls == [1]

# --------------------------------------------------------------------------- #
# The sole-door accessor and the light builder agree with the full service
# --------------------------------------------------------------------------- #


def test_light_builder_matches_the_charter_service_accessor() -> None:
    """``build_agent_profile_sentinels`` and the sole-door accessor answer identically.

    Same fixture (the repository's own pack layers plus the shipped catalogue):
    the light builder skips ``PackContext``, so this pins that skipping the
    governance machinery does not change the structural answer.
    """
    requested = [_HIC_ID, "generic-agent", "no-such-profile"]

    light = build_agent_profile_sentinels(_REPO_ROOT, requested)
    through_service = build_active_charter_service(_REPO_ROOT).agent_profile_sentinels(requested)

    assert light == through_service
    assert light[_HIC_ID] is True
    assert light["no-such-profile"] is False


# --------------------------------------------------------------------------- #
# Fail-closed: a config the activation-aware build rejects is rejected here too
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("config_text", "label"),
    [
        ("charter: [unclosed\n", "malformed-yaml"),
        ("activated_agent_profiles: 12\n", "invalid-activation-key"),
        ("charter: .kittify/does-not-exist.yaml\n", "dangling-charter-pointer"),
    ],
)
def test_light_builder_rejects_a_config_the_service_path_rejects(
    tmp_path: Path, config_text: str, label: str
) -> None:
    """The scoped read is lenient in *what it reads*, never in what it validates.

    The layer resolution logs and skips an unreadable config; that would turn a
    broken project into a successful markerless render, so the builder validates
    the file through ``PackContext.from_config`` first and raises the same error
    the activation-aware builder raises.
    """
    from charter.activation.active_charter_service_builder import (
        build_active_charter_service,
        build_agent_profile_sentinels,
    )
    from charter.activation.pack_context import ActiveCharterConfigError

    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(config_text, encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        build_agent_profile_sentinels(tmp_path, [_HIC_ID])
    with pytest.raises(ActiveCharterConfigError):
        build_active_charter_service(tmp_path)
    assert label
