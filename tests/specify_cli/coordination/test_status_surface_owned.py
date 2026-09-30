"""Owned-checkout status surface authority (WP06, T028-T031).

Pins the ONE classification predicate
(``surface_resolver.primary_read_targets_coord_worktree``), the six shape-guard
sites in ``status_service.py`` that route through it, and the FR-013/FR-014
same-path matrix that proves an owned read can never come from a weakened
coordination guard.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, TypeAlias

import pytest

from mission_runtime import OwnedCheckout
from mission_runtime.context import MissionTopology
from specify_cli.coordination import status_service, surface_resolver
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

# ``tests/integration/conftest.py`` is not on the fixture-discovery path for
# ``tests/specify_cli/coordination/`` (different subtree), so the WP02 factory
# fixture is imported explicitly and re-exported for pytest's own discovery
# (plan Test Layout: fixtures are never imported from *test* modules; this is
# a conftest, so the explicit import is the sanctioned route -- same pattern
# the carried commit 4ff6ff0c0 used for ``checkouts``).
from tests.integration.conftest import make_owned_checkouts  # noqa: F401

__all__ = ["make_owned_checkouts"]

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.integration.conftest import OwnedCheckouts

_MISSION_SLUG = "owned-01M2D900"


def _mint(
    *,
    repository_root: Path,
    owned_root: Path,
    mission_dir: Path,
    mission_slug: str = _MISSION_SLUG,
    target_branch: str = "codex/owned",
) -> OwnedCheckout:
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=mission_slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch=target_branch,
    )


def _forbid_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: assert the pure predicate never shells out to git."""

    def _boom(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("NFR-002: primary_read_targets_coord_worktree must not call subprocess")

    monkeypatch.setattr(surface_resolver.subprocess, "run", _boom)


def _status_event(event_id: str, *, to_lane: str = "claimed") -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane(to_lane),
        at="2026-09-28T00:00:00+00:00",
        actor="wp06-test",
        force=False,
        execution_mode="worktree",
    )


# ---------------------------------------------------------------------------
# T028 -- primary_read_targets_coord_worktree: the one classification predicate
# ---------------------------------------------------------------------------


def _owned_layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    owned_root = repo / ".worktrees" / "owned-a"
    mission_dir = owned_root / "kitty-specs" / _MISSION_SLUG
    mission_dir.mkdir(parents=True)
    return repo, owned_root, mission_dir


@pytest.mark.unit
@pytest.mark.fast
def test_no_fact_under_worktrees_segment_is_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo, _owned_root, mission_dir = _owned_layout(tmp_path)
    _forbid_subprocess(monkeypatch)

    assert surface_resolver.primary_read_targets_coord_worktree(mission_dir, owned=None) is True


@pytest.mark.unit
@pytest.mark.fast
def test_no_fact_outside_worktrees_segment_is_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "repo" / "kitty-specs" / _MISSION_SLUG
    outside.mkdir(parents=True)
    _forbid_subprocess(monkeypatch)

    assert surface_resolver.primary_read_targets_coord_worktree(outside, owned=None) is False


@pytest.mark.unit
@pytest.mark.fast
def test_fact_inside_owned_root_is_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, owned_root, mission_dir = _owned_layout(tmp_path)
    fact = _mint(repository_root=repo, owned_root=owned_root, mission_dir=mission_dir)
    _forbid_subprocess(monkeypatch)

    # Same-fixture positive control: identical path to the ``owned=None`` row
    # above -- the only variable is the fact.
    assert surface_resolver.primary_read_targets_coord_worktree(mission_dir, owned=fact) is False


@pytest.mark.unit
@pytest.mark.fast
def test_fact_outside_owned_root_under_worktrees_is_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, owned_root, mission_dir = _owned_layout(tmp_path)
    fact = _mint(repository_root=repo, owned_root=owned_root, mission_dir=mission_dir)
    coord_dir = repo / ".worktrees" / f"{_MISSION_SLUG}-coord" / "kitty-specs" / _MISSION_SLUG
    coord_dir.mkdir(parents=True)
    _forbid_subprocess(monkeypatch)

    # The fact exempts only its OWN subtree -- a different worktree under the
    # same repo is still shape-classified as coordination.
    assert surface_resolver.primary_read_targets_coord_worktree(coord_dir, owned=fact) is True


@pytest.mark.unit
@pytest.mark.fast
def test_sibling_prefix_path_is_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, owned_root, mission_dir = _owned_layout(tmp_path)
    fact = _mint(repository_root=repo, owned_root=owned_root, mission_dir=mission_dir)
    evil = repo / ".worktrees" / "owned-a-evil" / "kitty-specs" / _MISSION_SLUG
    evil.mkdir(parents=True)
    _forbid_subprocess(monkeypatch)

    # Containment is by path components, not string prefix: "owned-a-evil" is
    # not nested under "owned-a".
    assert surface_resolver.primary_read_targets_coord_worktree(evil, owned=fact) is True


@pytest.mark.unit
@pytest.mark.fast
def test_symlinked_alias_of_owned_root_is_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, owned_root, mission_dir = _owned_layout(tmp_path)
    fact = _mint(repository_root=repo, owned_root=owned_root, mission_dir=mission_dir)
    alias_root = tmp_path / "owned-alias"
    alias_root.symlink_to(owned_root, target_is_directory=True)
    alias_mission_dir = alias_root / "kitty-specs" / _MISSION_SLUG
    _forbid_subprocess(monkeypatch)

    assert surface_resolver.primary_read_targets_coord_worktree(alias_mission_dir, owned=fact) is False


# ---------------------------------------------------------------------------
# T029 -- all six status_service shape-guard sites accept the owned fact
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_fact_accepts_read_and_append(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")
    fact = resolve_owned_mission(checkouts.repository_root, checkouts.owned_root, checkouts.mission_slug)

    assert read_event_log(EventLogReadContract.primary_checkout(checkouts.mission_dir, owned=fact)) == []
    stream = read_event_stream_log(EventLogReadContract.primary_checkout(checkouts.mission_dir, owned=fact))
    assert stream.transitions == []

    event = _status_event("wp06-t029-append")
    append_event_log(
        EventLogWriteContract.primary_checkout_append(checkouts.mission_dir, owned=fact),
        event,
    )
    events_after = read_event_log(EventLogReadContract.primary_checkout(checkouts.mission_dir, owned=fact))
    assert [written.event_id for written in events_after] == ["wp06-t029-append"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_same_calls_without_owned_fact_still_refused(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")

    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_log(EventLogReadContract.primary_checkout(checkouts.mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_stream_log(EventLogReadContract.primary_checkout(checkouts.mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout_append must not target coordination worktree paths"):
        append_event_log(
            EventLogWriteContract.primary_checkout_append(checkouts.mission_dir),
            _status_event("wp06-t029-refused"),
        )


@pytest.mark.integration
@pytest.mark.git_repo
def test_coordination_label_on_owned_path_still_accepted_by_shape(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
) -> None:
    """A coordination-labelled contract has no ``owned`` field, so P's own
    ``.worktrees``-shaped path is (unchanged) accepted by shape -- FR-014
    does not touch the coordination factories."""
    checkouts = make_owned_checkouts(placement="under_worktrees")

    assert read_event_log(EventLogReadContract.coordination_worktree(checkouts.mission_dir)) == []


# ---------------------------------------------------------------------------
# Shared helper: register a REAL, git-registered coordination worktree.
# T027's own same-path control (test_registered_coordination_worktree_same_path_still_refused)
# lives in test_owned_status_read_contract.py, paired with the carried
# finalize test's owned-accepted read on the SAME fixture; this helper is
# reused here by T029's regression pin and the T031 matrix.
# ---------------------------------------------------------------------------


def _register_coordination_worktree(checkouts: OwnedCheckouts) -> Path:
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
    return coord_mission_dir


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_fact_never_exempts_a_different_registered_coord_worktree(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
) -> None:
    """T029 regression pin (FR-014): a registered coordination worktree
    stays refused for a primary_checkout-labelled read/append."""
    checkouts = make_owned_checkouts(placement="under_worktrees")
    coord_mission_dir = _register_coordination_worktree(checkouts)

    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_log(EventLogReadContract.primary_checkout(coord_mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout reads must not target coordination worktree paths"):
        read_event_stream_log(EventLogReadContract.primary_checkout(coord_mission_dir))
    with pytest.raises(StatusContractError, match="primary_checkout_append must not target coordination worktree paths"):
        append_event_log(
            EventLogWriteContract.primary_checkout_append(coord_mission_dir),
            _status_event("wp06-t029-coord-refused"),
        )


# ---------------------------------------------------------------------------
# T031 -- FR-013 / FR-014 same-path matrix, plus NFR-002 subprocess counting
# ---------------------------------------------------------------------------

_OWNED_READ_REFUSED_MESSAGE = "primary_checkout reads must not target coordination worktree paths"
_OWNED_APPEND_REFUSED_MESSAGE = "primary_checkout_append must not target coordination worktree paths"

EventLogContract: TypeAlias = EventLogReadContract | EventLogWriteContract


def _message_for(op: str) -> str:
    return _OWNED_APPEND_REFUSED_MESSAGE if op == "append" else _OWNED_READ_REFUSED_MESSAGE


def _run(op: str, contract: EventLogContract) -> None:
    # N2 (review cycle 1): union type + isinstance narrowing, no suppressions.
    # _contract_for below is the only producer and always returns the shape
    # matching ``op``, so each assert is a real invariant, not a workaround.
    if op == "read":
        assert isinstance(contract, EventLogReadContract)
        read_event_log(contract)
    elif op == "stream":
        assert isinstance(contract, EventLogReadContract)
        read_event_stream_log(contract)
    else:
        assert isinstance(contract, EventLogWriteContract)
        append_event_log(contract, _status_event(f"wp06-t031-append-{op}"))


def _contract_for(op: str, *, feature_dir: Path, owned: OwnedCheckout | None, label: str = "primary") -> EventLogContract:
    if label == "coordination":
        if op == "append":
            return EventLogWriteContract.coordination_transaction_append(feature_dir)
        return EventLogReadContract.coordination_worktree(feature_dir)
    if op == "append":
        return EventLogWriteContract.primary_checkout_append(feature_dir, owned=owned)
    return EventLogReadContract.primary_checkout(feature_dir, owned=owned)


# Each row id names: which path (owned P / registered coord worktree), which
# fact is threaded (P's own fact / none / a DIFFERENT checkout's fact), and
# which label the contract carries (primary, unless noted).
_MATRIX_ROW_IDS = [
    "owned-p-with-own-fact",
    "owned-p-without-fact",
    "coord-worktree-without-fact",
    "coord-worktree-with-other-fact",
    # N3 (review cycle 1): the missing row -- a COORDINATION label on the
    # coordination worktree's own path is (unchanged) accepted by shape,
    # regardless of any fact. Pairs with
    # test_coordination_label_on_owned_path_still_accepted_by_shape (P's
    # own path) to cover both sides of the "coordination label is shape-only"
    # claim.
    "coord-worktree-coordination-label",
]


def _row_target_and_fact(row_id: str, *, p_mission_dir: Path, coord_mission_dir: Path, p_fact: OwnedCheckout) -> tuple[Path, OwnedCheckout | None, bool, str]:
    """Return (feature_dir, owned, expected_ok, label) for one matrix row."""
    if row_id == "owned-p-with-own-fact":
        return p_mission_dir, p_fact, True, "primary"
    if row_id == "owned-p-without-fact":
        return p_mission_dir, None, False, "primary"
    if row_id == "coord-worktree-without-fact":
        return coord_mission_dir, None, False, "primary"
    if row_id == "coord-worktree-with-other-fact":
        # A fact for a DIFFERENT checkout (P) exempts only P's own subtree --
        # it must not exempt the coordination worktree too.
        return coord_mission_dir, p_fact, False, "primary"
    if row_id == "coord-worktree-coordination-label":
        return coord_mission_dir, None, True, "coordination"
    raise AssertionError(f"unknown matrix row id: {row_id}")


def _wrap_subprocess_counters(monkeypatch: pytest.MonkeyPatch, *modules: ModuleType) -> list[object]:
    """N1 (review cycle 1): count both ``subprocess.run`` AND ``Popen`` calls,
    in BOTH ``status_service`` and ``surface_resolver`` -- makes the "0 git
    calls" NFR-002 claim literal rather than partial (the branch-ref arm's
    ``status_service.subprocess.run`` was previously unwrapped; every row in
    this matrix is shape-guard-only or fact-carrying, so none of them should
    ever reach it, but the counter must actually be able to see it)."""
    calls: list[object] = []
    for module in modules:
        real_run: Callable[..., object] = module.subprocess.run
        real_popen: Callable[..., object] = module.subprocess.Popen

        def _counting_run(*args: object, __real: Callable[..., object] = real_run, **kwargs: object) -> object:
            calls.append(args)
            return __real(*args, **kwargs)

        def _counting_popen(*args: object, __real: Callable[..., object] = real_popen, **kwargs: object) -> object:
            calls.append(args)
            return __real(*args, **kwargs)

        monkeypatch.setattr(module.subprocess, "run", _counting_run)
        monkeypatch.setattr(module.subprocess, "Popen", _counting_popen)
    return calls


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("op", ["read", "stream", "append"])
@pytest.mark.parametrize("row_id", _MATRIX_ROW_IDS)
def test_same_path_matrix(
    row_id: str,
    op: str,
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")
    p_fact = resolve_owned_mission(checkouts.repository_root, checkouts.owned_root, checkouts.mission_slug)
    coord_mission_dir = _register_coordination_worktree(checkouts)
    feature_dir, owned, expected_ok, label = _row_target_and_fact(
        row_id,
        p_mission_dir=checkouts.mission_dir,
        coord_mission_dir=coord_mission_dir,
        p_fact=p_fact,
    )

    subprocess_calls = _wrap_subprocess_counters(monkeypatch, surface_resolver, status_service)

    contract = _contract_for(op, feature_dir=feature_dir, owned=owned, label=label)
    if expected_ok:
        _run(op, contract)
    else:
        with pytest.raises(StatusContractError, match=_message_for(op)):
            _run(op, contract)

    # NFR-002: the owned-accepted rows make 0 git calls; the shape-guard-only
    # refused rows make 0 as well.
    assert subprocess_calls == []


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_p_outside_worktrees_still_accepted(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> None:
    """FR-022 guard: an owned P outside ``.worktrees`` also takes the owned
    contract -- hunk (c) in ``_read_contract_from_transaction_target`` is
    unconditional on PATH SHAPE (not gated on ``.worktrees`` membership).
    It IS gated on topology (see
    ``test_hunk_c_skips_owned_shortcut_for_a_coordination_routing_topology``
    below, review-cycle-1 fix): this fixture's fact is single_branch, which
    never routes through coordination, so the owned shortcut still applies
    here."""
    checkouts = make_owned_checkouts(placement="sibling")
    fact = resolve_owned_mission(checkouts.repository_root, checkouts.owned_root, checkouts.mission_slug)

    assert read_event_log(EventLogReadContract.primary_checkout(checkouts.mission_dir, owned=fact)) == []


@pytest.mark.unit
@pytest.mark.git_repo
def test_hunk_c_skips_owned_shortcut_for_a_coordination_routing_topology(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
) -> None:
    """Review-cycle-1 fix (forward note): an owned identity whose FACT's
    topology routes through coordination (``LANES_WITH_COORD`` / ``COORD``)
    must NOT take the unconditional owned ``primary_checkout`` shortcut in
    ``_read_contract_from_transaction_target`` -- P's own local partition
    never carries the coordination log for such a mission. An owned identity
    is single_branch by construction today (``LIFECYCLE_OWNED_TOPOLOGIES``),
    so this is tested by constructing the fact and ``_TransactionIdentity``
    directly (the transition pipeline itself refuses a non-single_branch
    owned identity with ``OWNED_TOPOLOGY_UNSUPPORTED`` before reaching this
    helper -- reviewer-renata verified that refusal in review cycle 1)."""
    from mission_runtime import OwnedCheckout
    from mission_runtime.context import MissionTopology
    from specify_cli.coordination import status_transition as st
    from specify_cli.coordination.status_service import StatusReadSource

    checkouts = make_owned_checkouts(topology="lanes_with_coord")
    fact = OwnedCheckout._mint(
        repository_root=checkouts.repository_root,
        owned_root=checkouts.owned_root,
        mission_dir=checkouts.mission_dir,
        mission_slug=checkouts.mission_slug,
        topology=MissionTopology.LANES_WITH_COORD,
        write_branch=checkouts.target_branch,
    )
    identity = st._TransactionIdentity(
        repo_root=checkouts.owned_root,
        feature_dir=checkouts.mission_dir,
        mission_id=checkouts.mission_id,
        mid8=checkouts.mid8,
        destination_ref=f"kitty/mission-{checkouts.mission_slug}",
        meta_exists=True,
        coordination_branch=f"kitty/mission-{checkouts.mission_slug}",
        transaction_meta_exists=False,
        owned=fact,
    )

    contract = st._read_contract_from_transaction_target(identity, checkouts.mission_slug)

    # The bug hunk (c) used to have: EVERY owned identity took
    # primary_checkout(feature_dir, owned=fact), regardless of topology.
    assert not (contract.source == StatusReadSource.PRIMARY_CHECKOUT and contract.owned is fact)


@pytest.mark.integration
@pytest.mark.git_repo
def test_same_path_matrix_non_vacuity(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation check (T031 step 4): forcing the predicate to always return
    False must turn the FR-014 refusal rows green-washed (accepted) --
    proving the real predicate is load-bearing for the refusal above. This
    test performs the mutation transiently via monkeypatch; nothing is
    committed for it as production behaviour."""
    checkouts = make_owned_checkouts(placement="under_worktrees")
    coord_mission_dir = _register_coordination_worktree(checkouts)

    monkeypatch.setattr(surface_resolver, "primary_read_targets_coord_worktree", lambda *a, **k: False)  # noqa: ARG005

    # With the predicate mutated to always answer "not coordination", the
    # refusal for a registered coordination worktree disappears.
    read_event_log(EventLogReadContract.primary_checkout(coord_mission_dir))
