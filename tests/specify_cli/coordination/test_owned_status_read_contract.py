"""Owned status authority must survive an in-repository worktree location.

Carried from #5009 commit 4ff6ff0c0 (author Samuel Goff) via
``git cherry-pick -x``, then adapted (WP06 T027): the parallel
``owned_checkout`` status source this file originally pinned
(``test_owned_contract_validates_root_and_mission``) never lands -- an owned
repository-root-labelled read is a ``primary_checkout`` contract carrying the
validated :class:`~mission_runtime.OwnedCheckout` fact (C-002), not a second
status source -- so that test is dropped entirely. The genuine O6 red
(``test_finalize_and_read_owned_mission_below_worktrees``) is kept and
re-pointed at the WP02 fixtures and this WP's own contract surface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    EventLogWriteContract,
    StatusContractError,
    append_event_log,
    read_event_log,
    read_event_stream_log,
)
from specify_cli.core.owned_mission import resolve_owned_mission
from specify_cli.status.models import Lane, StatusEvent

# ``tests/integration/conftest.py`` is not visible to
# ``tests/specify_cli/coordination/`` (different subtree), so the WP02
# fixtures are imported explicitly and re-exported for pytest discovery
# (plan Test Layout: fixtures are never imported from *test* modules -- this
# replaces the carried commit's import from the test module
# ``tests.integration.test_explicit_checkout_commands``).
from tests.integration.conftest import make_owned_checkouts, make_r_snapshot  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests._owned_fixtures import RSnapshotter
    from tests.integration.conftest import OwnedCheckouts

__all__ = ["make_owned_checkouts", "make_r_snapshot"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "owned-01M1A900"

runner = CliRunner()


def test_finalize_and_read_owned_mission_below_worktrees(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Default mission_slug/mission_id (embeds the mid8 as a suffix,
    # "owned-fixture-01M2D900" / mid8 "01M2D900") so the legacy per-mission
    # transaction-meta check (status_transition._transaction_topology_available)
    # resolves to the SAME meta.json this fixture already wrote -- the
    # verbatim "<slug>-<mid8>" transaction-dir composer is idempotent when the
    # slug already embeds the mid8 (lanes/branch_naming.coord_mission_dir_name).
    checkouts = make_owned_checkouts(placement="under_worktrees", wp_ids=("WP01",))
    inside = checkouts.owned_root
    # finalize-tasks requires every WP file to match a tasks.md section
    # heading, and an owning_files-declaring code_change WP; the shared WP02
    # fixture's tasks.md/WP files are read-only-contract placeholders, so
    # amend them before finalizing.
    (checkouts.mission_dir / "tasks.md").write_text("# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n", encoding="utf-8")
    (checkouts.mission_dir / "tasks" / "WP01-owned.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Owned fixture task\ndependencies: []\n"
        "requirement_refs: [FR-001]\nsubtasks: []\nowned_files: [app.py]\n"
        "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n# Task\n",
        encoding="utf-8",
    )
    (checkouts.owned_root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."],
        cwd=checkouts.owned_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "commit", "-qm", "amend tasks.md section header"],
        cwd=checkouts.owned_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    snapshotter = make_r_snapshot(checkouts)
    monkeypatch.chdir(inside)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(inside))
    before = snapshotter.take()

    result = runner.invoke(
        mission_app,
        [
            "finalize-tasks",
            "--mission",
            checkouts.mission_slug,
            "--owned-checkout",
            str(inside),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    owned = resolve_owned_mission(checkouts.repository_root, inside, checkouts.mission_slug)
    events = read_event_log(EventLogReadContract.primary_checkout(owned.mission_dir, owned=owned))
    assert [(event.wp_id, str(event.to_lane)) for event in events] == [("WP01", "planned")]
    after = snapshotter.take()
    # NFR-001 (orchestrator-ruled wording amendment, review-cycle-1 Issue 1):
    # the transactional status write legitimately acquires R-anchored file
    # lock (checkout_file_lock persists an empty lock file on disk after
    # release, by design -- it is infrastructure, not a content leak). The
    # ONE named, canonical tolerance lives in tests/_owned_fixtures.py
    # (WP02's file): it accepts only that single empty, canonically-named
    # lock key and still compares files/head/index/home_files byte-for-byte.
    snapshotter.assert_unchanged(before, after, tolerate_status_mutex_for=checkouts.mission_slug)
    assert not (checkouts.repository_root / "kitty-specs" / checkouts.mission_slug).exists()


def test_registered_coordination_worktree_same_path_still_refused(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
) -> None:
    """FR-014 / US4-AS2: a REGISTERED coordination worktree stays refused for
    a primary_checkout-labelled read/append -- the same-path control paired
    with the finalize test's owned-accepted read above."""
    checkouts = make_owned_checkouts(placement="under_worktrees")
    coord_branch = f"kitty/mission-{checkouts.mission_slug}-coord"
    coord_root = checkouts.repository_root / ".worktrees" / f"{checkouts.mission_slug}-coord"
    subprocess.run(
        ["git", "-C", str(checkouts.repository_root), "worktree", "add", "-qb", coord_branch, str(coord_root)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    coord_mission_dir = coord_root / "kitty-specs" / checkouts.mission_slug
    coord_mission_dir.mkdir(parents=True)
    (coord_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_log(EventLogReadContract.primary_checkout(coord_mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_stream_log(EventLogReadContract.primary_checkout(coord_mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout_append must not target coordination worktree paths"):
        append_event_log(
            EventLogWriteContract.primary_checkout_append(coord_mission_dir),
            StatusEvent(
                event_id="wp06-t027-registered-coord-refused",
                mission_slug=checkouts.mission_slug,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-09-28T00:00:00+00:00",
                actor="wp06-test",
                force=False,
                execution_mode="worktree",
            ),
        )


@pytest.mark.parametrize("reader", [read_event_log, read_event_stream_log])
def test_primary_contract_still_rejects_coordination_shaped_path(tmp_path: Path, reader: object) -> None:
    with pytest.raises(StatusContractError, match="primary_checkout"):
        reader(EventLogReadContract.primary_checkout(tmp_path / ".worktrees" / "coord" / "kitty-specs" / _SLUG))  # type: ignore[operator]
