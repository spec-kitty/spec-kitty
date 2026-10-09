"""Regression tests for software-dev action index doctrine wiring."""

import pytest

from charter.offering.missions import MissionTemplateRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

def test_review_action_index_includes_living_documentation_sync() -> None:
    repo = MissionTemplateRepository.default()
    index = repo.get_action_index("software-dev", "review")

    assert index is not None
    assert "037-living-documentation-sync" in index.parsed["directives"]
    assert index.parsed["tactics"][0] == "usage-examples-sync"


@pytest.mark.parametrize("action", ["plan", "implement", "review"])
def test_action_index_includes_supply_chain_install_safety(action: str) -> None:
    """Each software-dev action wired for supply-chain checks must reference
    the specific directive and tactic ids, not just some new edge count.

    A bug that wired a different directive/tactic pair to these actions
    (while preserving the total edge count) would slip past DRG golden-count
    assertions but must fail this content-level check.
    """
    repo = MissionTemplateRepository.default()
    index = repo.get_action_index("software-dev", action)

    assert index is not None
    assert "051-supply-chain-install-safety" in index.parsed["directives"]
    assert "supply-chain-install-safety" in index.parsed["tactics"]
