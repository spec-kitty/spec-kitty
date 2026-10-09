"""Tests for ``resolve_generic_fallback`` — the WP02/#3064 empty-charter routing seam.

NOTE (WP01/#3104, #3064 reversal): the composite predicate this module's
truth table originally pinned (ALL of directives/tactics/toolguides/
procedures/paradigms/styleguides/glossary-packs/mission-step-contracts/
agent_profiles/org_roots empty) has been REPLACED by the bundle-presence +
org-pack-safe predicate in ``specify_cli.invocation.empty_charter``. That
predicate treats "empty" as "no compiled charter bundle
(``.kittify/charter/charter.yaml``) AND no org pack AND no explicit
agent-profile activation" — it deliberately drops the non-routing dimensions
(directives, tactics, glossary-packs, mission-step-contracts, toolguides,
procedures, paradigms, styleguides) because none of them make
``ActionRouter.route()`` able to resolve a profile it otherwise couldn't;
keeping them produced the #3104 defect (``charter pack apply`` activating a
URN with no bundle and no profile used to flip the net off and hand back a
bare ``ROUTER_NO_MATCH``). See ``src/specify_cli/invocation/empty_charter.py``
module docstring for the full rationale.

The routing dimensions (``activated_agent_profiles`` and org packs) are
unchanged and remain covered below.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.invocation.empty_charter import GENERIC_AGENT_ID, resolve_generic_fallback
from specify_cli.invocation.router import RouterDecision

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(repo_root: Path, data: dict[str, object]) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


# ---------------------------------------------------------------------------
# Truth table — fallback fires
# ---------------------------------------------------------------------------


def test_no_config_at_all_returns_fallback_decision(tmp_path: Path) -> None:
    """No ``.kittify/config.yaml`` at all is the maximally-empty case."""
    decision = resolve_generic_fallback(tmp_path, "implement the payment module")

    assert decision is not None
    assert isinstance(decision, RouterDecision)
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_empty_config_file_returns_fallback_decision(tmp_path: Path) -> None:
    """An explicit-but-empty config.yaml (no activation keys at all) is empty."""
    _write_config(tmp_path, {})

    decision = resolve_generic_fallback(tmp_path, "review the diff")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID
    assert decision.confidence == "generic_fallback"
    assert decision.action == "review"


def test_action_falls_back_to_implementer_default_when_no_verb_matches(tmp_path: Path) -> None:
    """No canonical-verb token present -> derive from the IMPLEMENTER role default."""
    decision = resolve_generic_fallback(tmp_path, "please help me with this")

    assert decision is not None
    # DEFAULT_ROLE_CAPABILITIES[Role.IMPLEMENTER].canonical_verbs[0] == "generate"
    assert decision.action == "generate"


# ---------------------------------------------------------------------------
# Truth table — fallback does NOT fire (bundle-presence + org-pack-safe predicate)
# ---------------------------------------------------------------------------


def test_directive_only_no_bundle_fires_net(tmp_path: Path) -> None:
    """NFR-004/#3104: a lone activated directive, with no compiled bundle and no
    profile/org activation, is a NON-routing dimension under the new predicate —
    the net now FIRES (returns generic-agent) instead of deferring to the router.
    """
    _write_config(tmp_path, {"activated_directives": ["028-efficient-local-tooling"]})

    decision = resolve_generic_fallback(tmp_path, "implement the feature")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_agent_profiles_activated_with_entries_returns_none(tmp_path: Path) -> None:
    _write_config(tmp_path, {"activated_agent_profiles": ["architect-alphonso"]})

    assert resolve_generic_fallback(tmp_path, "implement the feature") is None


def test_agent_profiles_activated_with_empty_list_returns_none(tmp_path: Path) -> None:
    """Three-state semantics: an explicit empty list is still 'key present' (not empty-charter)."""
    _write_config(tmp_path, {"activated_agent_profiles": []})

    assert resolve_generic_fallback(tmp_path, "implement the feature") is None


def test_glossary_packs_only_no_bundle_fires_net(tmp_path: Path) -> None:
    """NFR-004/#3064 reversal: a glossary-pack activation, with no compiled
    bundle and no profile/org activation, is a NON-routing dimension — the net
    now FIRES.
    """
    _write_config(tmp_path, {"activated_glossary_packs": ["core-glossary"]})

    decision = resolve_generic_fallback(tmp_path, "implement the feature")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_glossary_packs_activated_with_empty_list_fires_net(tmp_path: Path) -> None:
    """An explicit empty glossary-pack list is likewise a non-routing dimension —
    the net still FIRES (glossary packs never gate the router)."""
    _write_config(tmp_path, {"activated_glossary_packs": []})

    decision = resolve_generic_fallback(tmp_path, "implement the feature")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_mission_step_contracts_only_no_bundle_fires_net(tmp_path: Path) -> None:
    """NFR-004/#3104: a mission-step-contract activation, with no compiled
    bundle and no profile/org activation, is a NON-routing dimension — the net
    now FIRES.
    """
    _write_config(tmp_path, {"activated_mission_step_contracts": ["software-dev-implement"]})

    decision = resolve_generic_fallback(tmp_path, "implement the feature")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_mission_step_contracts_activated_with_empty_list_fires_net(tmp_path: Path) -> None:
    """An explicit empty mission-step-contract list is likewise a non-routing
    dimension — the net still FIRES."""
    _write_config(tmp_path, {"activated_mission_step_contracts": []})

    decision = resolve_generic_fallback(tmp_path, "implement the feature")

    assert decision is not None
    assert decision.profile_id == GENERIC_AGENT_ID == "generic-agent"
    assert decision.confidence == "generic_fallback"
    assert decision.action == "implement"


def test_org_pack_present_returns_none(tmp_path: Path) -> None:
    """An org/project pack registered in config.yaml is a configured repo, even
    with zero activation keys set — org_roots != () alone must block the fallback.
    """
    pack_root = tmp_path / "org-packs" / "orgzilla-governance-pack"
    pack_root.mkdir(parents=True)
    _write_config(
        tmp_path,
        {"charter_packs": {"org": {"packs": [{"name": "orgzilla-governance-pack", "local_path": str(pack_root)}]}}},
    )

    assert resolve_generic_fallback(tmp_path, "implement the feature") is None
