"""FR-006 (#7149): ``accept --owned-checkout`` reads the operator-canceled work packages from the owned checkout.

``acceptably_canceled_wp_ids`` resolved the status surface from the repository root, so a Mission that
exists only in the owned checkout yielded an empty set (fail-open) and canceled work packages were not
excluded. ``accept`` passes ``run.owned`` to the reader; the reader must follow the owned placement.

The ``accept`` verdict itself cannot show the difference today (its evidence reader admits only
approved/done work packages), so the contract is pinned at the reader the two ``accept`` call sites use.
"""

from __future__ import annotations

import shutil

import pytest

from specify_cli.consolidation.done_bookkeeping import acceptably_canceled_wp_ids
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_events
from tests.integration.test_explicit_checkout_commands import SLUG, git, mint_fact
from tests.integration.test_explicit_checkout_commands import checkouts as checkouts  # noqa: F401 -- pytest fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _operator_cancellation() -> StatusEvent:
    return StatusEvent(
        event_id="01G71490000000000000000001",
        mission_slug=SLUG,
        wp_id="WP02",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CANCELED,
        at="2026-11-03T12:00+00:00",
        actor="operator",
        force=True,
        execution_mode="worktree",
        reason="descoped by the operator",
        reason_source="operator",
    )


def test_owned_checkout_canceled_work_packages_are_read_from_the_owned_checkout(checkouts) -> None:  # noqa: F811 -- pytest fixture
    primary, owned, _sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    seed_status_events(mission, [_operator_cancellation()])
    git(owned, "add", "-A", "--", f"kitty-specs/{SLUG}")
    git(owned, "commit", "-qm", "status: operator cancels WP02")
    assert not (primary / "kitty-specs" / SLUG).exists()

    assert acceptably_canceled_wp_ids(primary, SLUG, owned=mint_fact(primary, owned)) == {"WP02"}

    # Control: the same Mission checked out in the repository root keeps its un-owned route.
    shutil.copytree(mission, primary / "kitty-specs" / SLUG)
    assert acceptably_canceled_wp_ids(primary, SLUG) == {"WP02"}
