"""Tests for TrackerProjectConfig: project_slug, provider-aware is_configured, constants."""

from __future__ import annotations

import pytest

from specify_cli.tracker.config import (
    ALL_SUPPORTED_PROVIDERS,
    LOCAL_PROVIDERS,
    REMOVED_PROVIDERS,
    SAAS_PROVIDERS,
    TrackerProjectConfig,
    load_tracker_config,
    save_tracker_config,
)


# ---------------------------------------------------------------------------
# YAML roundtrip tests
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_project_slug_roundtrip(tmp_path: object) -> None:
    """SaaS binding: project_slug survives save + load cycle."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="linear", project_slug="my-proj")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.project_slug == "my-proj"
    assert loaded.provider == "linear"


def test_workspace_roundtrip(tmp_path: object) -> None:
    """Local binding: workspace survives save + load cycle."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="beads", workspace="my-ws")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.workspace == "my-ws"
    assert loaded.provider == "beads"


def test_project_slug_and_workspace_roundtrip(tmp_path: object) -> None:
    """Both fields can coexist in YAML (even if only one matters per provider type)."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="linear", project_slug="proj", workspace="ws")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.project_slug == "proj"
    assert loaded.workspace == "ws"


def test_project_slug_none_when_absent(tmp_path: object) -> None:
    """project_slug defaults to None when not present in YAML."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="beads", workspace="ws")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.project_slug is None


# ---------------------------------------------------------------------------
# is_configured tests — SaaS providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", sorted(SAAS_PROVIDERS))
def test_is_configured_saas_with_project_slug(provider: str) -> None:
    """SaaS provider with project_slug is configured."""
    assert TrackerProjectConfig(provider=provider, project_slug="p").is_configured


@pytest.mark.parametrize("provider", sorted(SAAS_PROVIDERS))
def test_is_configured_saas_without_project_slug(provider: str) -> None:
    """SaaS provider without project_slug is NOT configured."""
    assert not TrackerProjectConfig(provider=provider).is_configured


def test_is_configured_saas_workspace_alone_insufficient() -> None:
    """SaaS provider with only workspace (no project_slug) is NOT configured."""
    assert not TrackerProjectConfig(provider="linear", workspace="w").is_configured


# ---------------------------------------------------------------------------
# is_configured tests — local providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", sorted(LOCAL_PROVIDERS))
def test_is_configured_local_with_workspace(provider: str) -> None:
    """Local provider with workspace is configured."""
    assert TrackerProjectConfig(provider=provider, workspace="w").is_configured


@pytest.mark.parametrize("provider", sorted(LOCAL_PROVIDERS))
def test_is_configured_local_without_workspace(provider: str) -> None:
    """Local provider without workspace is NOT configured."""
    assert not TrackerProjectConfig(provider=provider).is_configured


def test_is_configured_local_project_slug_alone_insufficient() -> None:
    """Local provider with only project_slug (no workspace) is NOT configured."""
    assert not TrackerProjectConfig(provider="beads", project_slug="p").is_configured


# ---------------------------------------------------------------------------
# is_configured tests — edge cases
# ---------------------------------------------------------------------------


def test_is_configured_no_provider() -> None:
    """No provider at all is NOT configured."""
    assert not TrackerProjectConfig().is_configured


def test_is_configured_removed_provider() -> None:
    """Removed provider (azure_devops) is NOT configured regardless of fields."""
    assert not TrackerProjectConfig(provider="azure_devops", project_slug="p", workspace="w").is_configured


def test_is_configured_unknown_provider() -> None:
    """Unknown provider is NOT configured."""
    assert not TrackerProjectConfig(provider="some_unknown", project_slug="p", workspace="w").is_configured


# ---------------------------------------------------------------------------
# Provider classification constants
# ---------------------------------------------------------------------------


def test_provider_constants_membership() -> None:
    """Spot-check key providers are in the right sets."""
    assert "linear" in SAAS_PROVIDERS
    assert "jira" in SAAS_PROVIDERS
    assert "github" in SAAS_PROVIDERS
    assert "gitlab" in SAAS_PROVIDERS
    assert "beads" in LOCAL_PROVIDERS
    assert "fp" in LOCAL_PROVIDERS
    assert "azure_devops" in REMOVED_PROVIDERS


def test_provider_sets_disjoint() -> None:
    """SaaS, local, and removed sets must not overlap."""
    assert not SAAS_PROVIDERS & LOCAL_PROVIDERS
    assert not SAAS_PROVIDERS & REMOVED_PROVIDERS
    assert not LOCAL_PROVIDERS & REMOVED_PROVIDERS


def test_all_supported_is_union() -> None:
    """ALL_SUPPORTED_PROVIDERS == SAAS | LOCAL (removed excluded)."""
    assert ALL_SUPPORTED_PROVIDERS == SAAS_PROVIDERS | LOCAL_PROVIDERS
    assert not REMOVED_PROVIDERS & ALL_SUPPORTED_PROVIDERS


def test_provider_constants_are_frozensets() -> None:
    """Constants are immutable frozensets."""
    assert isinstance(SAAS_PROVIDERS, frozenset)
    assert isinstance(LOCAL_PROVIDERS, frozenset)
    assert isinstance(REMOVED_PROVIDERS, frozenset)
    assert isinstance(ALL_SUPPORTED_PROVIDERS, frozenset)


# ---------------------------------------------------------------------------
# from_dict / to_dict serialization
# ---------------------------------------------------------------------------


def test_to_dict_includes_project_slug() -> None:
    """to_dict emits project_slug key."""
    config = TrackerProjectConfig(provider="linear", project_slug="slug-1")
    d = config.to_dict()
    assert d["project_slug"] == "slug-1"


def test_from_dict_parses_project_slug() -> None:
    """from_dict reads project_slug from raw dict."""
    config = TrackerProjectConfig.from_dict({"provider": "github", "project_slug": "my-repo"})
    assert config.project_slug == "my-repo"
    assert config.provider == "github"


def test_from_dict_strips_whitespace() -> None:
    """from_dict strips surrounding whitespace from project_slug."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "project_slug": "  padded  "})
    assert config.project_slug == "padded"


def test_from_dict_empty_string_becomes_none() -> None:
    """from_dict treats empty/whitespace-only project_slug as None."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "project_slug": "   "})
    assert config.project_slug is None


# ---------------------------------------------------------------------------
# New fields: binding_ref, display_label, provider_context, _extra (T001/T003)
# ---------------------------------------------------------------------------


def test_new_fields_default_values() -> None:
    """New fields default to None / empty dict."""
    config = TrackerProjectConfig()
    assert config.binding_ref is None
    assert config.display_label is None
    assert config.provider_context is None
    assert config._extra == {}


def test_extra_field_not_in_repr() -> None:
    """_extra field is excluded from repr."""
    config = TrackerProjectConfig(provider="linear", _extra={"future_field": 42})
    r = repr(config)
    assert "_extra" not in r


# ---------------------------------------------------------------------------
# Roundtrip tests (T004)
# ---------------------------------------------------------------------------


def test_binding_ref_roundtrip(tmp_path: object) -> None:
    """binding_ref survives save + load cycle."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="linear", binding_ref="lin-proj-abc123")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.binding_ref == "lin-proj-abc123"
    assert loaded.provider == "linear"


def test_display_label_roundtrip(tmp_path: object) -> None:
    """display_label survives save + load cycle."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="jira", project_slug="PROJ", display_label="My Project Board")
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.display_label == "My Project Board"


def test_provider_context_roundtrip(tmp_path: object) -> None:
    """provider_context dict survives save + load cycle."""
    from pathlib import Path

    root = Path(str(tmp_path))
    ctx = {"org_id": "org-123", "team_id": "team-456"}
    config = TrackerProjectConfig(provider="linear", binding_ref="ref", provider_context=ctx)
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.provider_context == {"org_id": "org-123", "team_id": "team-456"}


def test_legacy_config_loads_without_binding_ref(tmp_path: object) -> None:
    """Pre-062 config (no binding_ref, display_label, provider_context) loads without error."""
    from pathlib import Path

    from ruamel.yaml import YAML

    root = Path(str(tmp_path))
    config_path = root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write a pre-062 config (only provider + project_slug + ownership)
    yaml = YAML()
    payload = {
        "tracker": {
            "provider": "linear",
            "project_slug": "old-proj",
            "workspace": None,
            "ownership": {
                "mode": "external_authoritative",
                "field_owners": {},
            },
        }
    }
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(payload, f)

    loaded = load_tracker_config(root)
    assert loaded.provider == "linear"
    assert loaded.project_slug == "old-proj"
    assert loaded.binding_ref is None
    assert loaded.display_label is None
    assert loaded.provider_context is None
    assert loaded.is_configured is True


def test_unknown_field_passthrough(tmp_path: object) -> None:
    """Unknown keys in YAML survive load -> save round-trip."""
    from pathlib import Path

    from ruamel.yaml import YAML

    root = Path(str(tmp_path))
    config_path = root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write config with an unknown future field
    yaml = YAML()
    payload = {
        "tracker": {
            "provider": "linear",
            "project_slug": "proj",
            "future_field": 42,
            "another_unknown": "hello",
            "ownership": {"mode": "external_authoritative", "field_owners": {}},
        }
    }
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(payload, f)

    # Load, then save back
    loaded = load_tracker_config(root)
    assert loaded._extra == {"future_field": 42, "another_unknown": "hello"}

    save_tracker_config(root, loaded)

    # Reload and verify unknown fields survived
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.load(f)
    assert raw["tracker"]["future_field"] == 42
    assert raw["tracker"]["another_unknown"] == "hello"


def test_retired_doctrine_key_is_not_read_as_ownership() -> None:
    """The retired ``tracker.doctrine`` key is no ownership source (FR-011).

    It is kept as an unknown key (written back unchanged), which is safe only
    because the CLI-root ``LEGACY_CHARTER_STATE`` gate refuses such a project
    before any tracker command runs (``tests/specify_cli/migration/test_legacy_charter_gate.py``).
    """
    config = TrackerProjectConfig.from_dict({"provider": "beads", "doctrine": {"mode": "split_ownership", "field_owners": {"title": "spec_kitty"}}})

    assert config.ownership_mode == "external_authoritative"
    assert config.ownership_field_owners == {}
    assert config._extra == {"doctrine": {"mode": "split_ownership", "field_owners": {"title": "spec_kitty"}}}


def test_all_new_fields_together(tmp_path: object) -> None:
    """All new and old fields coexist correctly through save + load."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(
        provider="github",
        binding_ref="gh-repo-xyz",
        project_slug="my-repo",
        display_label="My GitHub Repo",
        provider_context={"org": "acme", "visibility": "private"},
        workspace="local-ws",
        ownership_mode="local_authoritative",
        ownership_field_owners={"title": "tracker", "status": "local"},
    )
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.provider == "github"
    assert loaded.binding_ref == "gh-repo-xyz"
    assert loaded.project_slug == "my-repo"
    assert loaded.display_label == "My GitHub Repo"
    assert loaded.provider_context == {"org": "acme", "visibility": "private"}
    assert loaded.workspace == "local-ws"
    assert loaded.ownership_mode == "local_authoritative"
    assert loaded.ownership_field_owners == {"title": "tracker", "status": "local"}


def test_provider_context_none_roundtrip(tmp_path: object) -> None:
    """provider_context=None serializes and deserializes correctly."""
    from pathlib import Path

    root = Path(str(tmp_path))
    config = TrackerProjectConfig(provider="linear", binding_ref="ref", provider_context=None)
    save_tracker_config(root, config)
    loaded = load_tracker_config(root)
    assert loaded.provider_context is None


def test_from_dict_binding_ref_strips_whitespace() -> None:
    """from_dict strips whitespace from binding_ref."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "binding_ref": "  ref-123  "})
    assert config.binding_ref == "ref-123"


def test_from_dict_binding_ref_empty_becomes_none() -> None:
    """from_dict treats empty/whitespace binding_ref as None."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "binding_ref": "   "})
    assert config.binding_ref is None


def test_from_dict_display_label_strips_whitespace() -> None:
    """from_dict strips whitespace from display_label."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "display_label": "  My Board  "})
    assert config.display_label == "My Board"


def test_from_dict_display_label_empty_becomes_none() -> None:
    """from_dict treats empty/whitespace display_label as None."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "display_label": ""})
    assert config.display_label is None


def test_from_dict_provider_context_non_dict_ignored() -> None:
    """from_dict ignores provider_context if not a dict."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "provider_context": "not-a-dict"})
    assert config.provider_context is None


def test_from_dict_provider_context_values_stringified() -> None:
    """from_dict converts provider_context values to strings."""
    config = TrackerProjectConfig.from_dict({"provider": "linear", "provider_context": {"num": 42, "flag": True}})
    assert config.provider_context == {"num": "42", "flag": "True"}


def test_to_dict_includes_new_fields() -> None:
    """to_dict emits binding_ref, display_label, provider_context."""
    config = TrackerProjectConfig(
        provider="linear",
        binding_ref="ref-1",
        display_label="Board",
        provider_context={"k": "v"},
    )
    d = config.to_dict()
    assert d["binding_ref"] == "ref-1"
    assert d["display_label"] == "Board"
    assert d["provider_context"] == {"k": "v"}


def test_to_dict_extra_does_not_override_known_fields() -> None:
    """_extra keys with the same name as known fields are overridden by known values."""
    config = TrackerProjectConfig(
        provider="linear",
        binding_ref="real-ref",
        _extra={"binding_ref": "fake-ref", "future": 99},
    )
    d = config.to_dict()
    assert d["binding_ref"] == "real-ref"  # Known field wins
    assert d["future"] == 99  # Unknown field preserved


# ---------------------------------------------------------------------------
# is_configured tests — SaaS dual-read (T005)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "binding_ref,project_slug,expected",
    [
        ("ref", None, True),  # binding_ref only
        (None, "slug", True),  # project_slug only (legacy)
        ("ref", "slug", True),  # both
        (None, None, False),  # neither
    ],
)
def test_is_configured_saas_dual_read(binding_ref: str | None, project_slug: str | None, expected: bool) -> None:
    """SaaS provider is configured when binding_ref OR project_slug is set."""
    config = TrackerProjectConfig(provider="linear", binding_ref=binding_ref, project_slug=project_slug)
    assert config.is_configured == expected


@pytest.mark.parametrize("provider", sorted(SAAS_PROVIDERS))
def test_is_configured_saas_with_binding_ref_only(provider: str) -> None:
    """SaaS provider with only binding_ref (no project_slug) is configured."""
    assert TrackerProjectConfig(provider=provider, binding_ref="ref").is_configured


def test_is_configured_saas_workspace_and_binding_ref() -> None:
    """SaaS provider with workspace + binding_ref is configured (binding_ref counts)."""
    config = TrackerProjectConfig(provider="linear", binding_ref="ref", workspace="ws")
    assert config.is_configured


@pytest.mark.parametrize("provider", sorted(LOCAL_PROVIDERS))
def test_is_configured_local_unaffected_by_binding_ref(provider: str) -> None:
    """Local provider ignores binding_ref; still needs workspace."""
    assert not TrackerProjectConfig(provider=provider, binding_ref="ref").is_configured
    assert TrackerProjectConfig(provider=provider, binding_ref="ref", workspace="ws").is_configured
