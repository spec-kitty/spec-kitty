"""Red-first CLI acceptance for ``spec-kitty next`` under an owned checkout.

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, WP19 (T102).

Drives the REAL ``next`` command in-process (``typer.testing.CliRunner`` over
``next_cmd.next_step``, exactly as ``tests/specify_cli/cli/commands/`` does)
so every row is reproduced through the pre-existing entry point an operator
hits, before any ``next_cmd`` fix (C-007). Facts are never constructed here:
the CLI mints its own through the sole validator, and the WP11 helpers this
module reuses mint theirs through ``resolve_owned_mission``.

Observed on the WP11 result (the base of this WP), recorded per row:

* O9 / FR-002 (protected target): RED. The claim-only path accepts a protected
  target; no ``OWNED_BRANCH_REFUSED`` is emitted.
* FR-003 (validation count): RED. The CLI's claim-only check plus each runtime
  legacy arm (``_transitional_owned_from_legacy``) validate the claim more
  than once.
* FR-021 flagless adoption (positive): RED. Flagless ``next`` from inside a
  valid owned checkout does not adopt it; it resolves against the repository
  root and refuses with ``MISSION_NOT_FOUND``.
* FR-021 no-adoption controls (lane worktree, coordination worktree, rejected
  checkout): GREEN ratchets. The legacy guard / legacy resolution already
  refuses them; these rows keep the behaviour unchanged once ``next`` learns
  to adopt.
* FR-007 (stale copy key): RED. ``stale_repository_root_copy`` is not in the
  ``next`` payload. The non-owned control is a green ratchet (key absent).
* FR-023 pairing, FR-022 twin, O5 no-wedge, O8 CLI envelope and the US3-AS6
  branch-flip proof: GREEN ratchets on the WP11 result except where the
  FR-003 count assertion inside them is the red reason.
* US3-AS1 full row (``kind == "step"`` with a prompt file): was an expected
  failure owned by WP12 T068 (the prompt builder had no owned arm); green since WP12, and
  every decision assertion here now requires ``kind == "step"``.

Deviations from the WP prompt, all forced by what exists on this lane:
``agent tasks status --owned-checkout`` (WP09) is not on this lane, so the
lifecycle half of the FR-023 pairing uses ``agent mission finalize-tasks
--owned-checkout`` (which validates against ``LIFECYCLE_OWNED_TOPOLOGIES``); and
because the prompt builder was WP12's, the US3-AS6 row asserts the decision's
action/workspace rather than exit 0.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from specify_cli.cli.commands import next_cmd
from specify_cli.cli.commands.agent.mission import app as mission_app
from tests._factories import provision_test_charter
from tests._owned_fixtures import RSnapshotter
from tests.integration.conftest import OwnedCheckouts
from tests.integration.test_owned_lifecycle_acceptance_context import (
    _branch_worktree_holding_mission,
    _p_code_lane_id,
    _target_branch_worktree_holding_mission,
)
from tests.integration.test_owned_next_runtime import (
    _coord_owned_with_removed_worktree,
    _inject_git_worktree_failure,
    _provision_charter,
    _walk_to_tasks,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
next_app = typer.Typer()
next_app.command(name="next")(next_cmd.next_step)

_VOLATILE_KEYS = frozenset({"timestamp"})
_FLIP_BRANCH = "codex/flip-target"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _at(monkeypatch: pytest.MonkeyPatch, cwd: Path) -> None:
    """Run subsequent commands from ``cwd`` with no ambient repo-root override."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.chdir(cwd)


def _next(*args: str) -> Any:
    return runner.invoke(next_app, list(args))


def _payload(result: Any) -> dict[str, Any]:
    """The first JSON document in the combined output (stderr advisories may follow it)."""
    data, _end = json.JSONDecoder().raw_decode(result.output[result.output.index("{") :])
    assert isinstance(data, dict), result.output
    return data


def _assert_no_uncaught_exception(result: Any) -> None:
    assert result.exception is None or isinstance(result.exception, SystemExit), f"uncaught exception: {result.exception!r}\n{result.output}"
    assert "Traceback" not in result.output, result.output
    assert "ValueError" not in result.output, result.output


def _stable(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in _VOLATILE_KEYS}


def _is_under(path: str | Path, root: Path) -> bool:
    return Path(path).resolve().is_relative_to(root.resolve())


def _assert_implement_wp01_in_p(payload: dict[str, Any], checkouts: OwnedCheckouts) -> None:
    """The contract of the CLI at tasks->implement: ``implement WP01`` issued with workspace P.

    The step's PROMPT is built from P by ``prompt_builder`` (WP12), so the
    decision is a real ``step`` and never a ``prompt resolution failed`` block.
    """
    assert payload["kind"] == "step", (payload["kind"], payload["reason"])
    assert payload.get("error_code") is None
    assert payload["action"] == "implement"
    assert payload["wp_id"] == "WP01"
    assert payload["workspace_path"] is not None
    assert Path(payload["workspace_path"]).resolve() == checkouts.owned_root.resolve()
    assert not _is_under(payload["workspace_path"], checkouts.repository_root) or _is_under(checkouts.owned_root, checkouts.repository_root)


@pytest.fixture
def validation_count(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """Count every ``resolve_ownership_claim`` call (FR-003), with cold workspace caches."""
    import specify_cli.core.checkout_ownership as checkout_ownership
    from specify_cli.workspace import clear_workspace_resolution_caches

    real = checkout_ownership.resolve_ownership_claim
    calls: list[tuple[Any, ...]] = []

    def _counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)
    clear_workspace_resolution_caches()
    return calls


def _r_snapshotter(checkouts: OwnedCheckouts) -> RSnapshotter:
    """Snapshot R (and P's git state) without the global home: ``next`` legitimately writes the prompt file there."""
    return RSnapshotter(checkouts.repository_root, checkouts.owned_root, None)


def _as1(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """The AS-1 fixture: finalized owned mission whose run sits on the ``tasks`` step, cwd = R."""
    _walk_to_tasks(checkouts, monkeypatch)
    _at(monkeypatch, checkouts.repository_root)


def _next_success(checkouts: OwnedCheckouts, *extra: str) -> Any:
    return _next("--agent", "claude", "--owned-checkout", str(checkouts.owned_root), "--mission", checkouts.mission_slug, "--result", "success", "--json", *extra)


def _next_query(checkouts: OwnedCheckouts, handle: str | None = None) -> Any:
    return _next("--owned-checkout", str(checkouts.owned_root), "--mission", handle or checkouts.mission_slug, "--json")


# ---------------------------------------------------------------------------
# FR-002 / O9: branch and protection checks
# ---------------------------------------------------------------------------


class TestO9BranchAndProtection:
    def test_protected_target_is_refused_with_typed_code(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        checkouts = make_owned_checkouts(protected_target=True)
        _at(monkeypatch, checkouts.repository_root)

        result = _next_query(checkouts)

        _assert_no_uncaught_exception(result)
        assert result.exit_code == 1, result.output
        payload = _payload(result)
        assert payload["success"] is False
        assert payload["error_code"] == OwnedRefusalCode.OWNED_BRANCH_REFUSED

    def test_unprotected_control_is_accepted(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        checkouts = make_owned_checkouts()
        _at(monkeypatch, checkouts.repository_root)

        result = _next_query(checkouts)

        _assert_no_uncaught_exception(result)
        assert result.exit_code == 0, result.output
        assert _payload(result)["kind"] == "query"


# ---------------------------------------------------------------------------
# FR-023: `next` accepts every topology it accepts today; lifecycle refuses
# ---------------------------------------------------------------------------


class TestFr023TopologyPairing:
    @pytest.mark.parametrize("topology", ["lanes_with_coord", "lanes"])
    def test_next_accepts_and_lifecycle_command_refuses(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch, topology: str) -> None:
        checkouts = make_owned_checkouts(topology=topology)
        _provision_charter(checkouts)
        _at(monkeypatch, checkouts.repository_root)

        accepted = _next_query(checkouts)

        _assert_no_uncaught_exception(accepted)
        assert accepted.exit_code == 0, accepted.output
        accepted_payload = _payload(accepted)
        assert accepted_payload["kind"] == "query"
        assert accepted_payload.get("error_code") is None

        _at(monkeypatch, checkouts.owned_root)
        monkeypatch.setenv("SPECIFY_REPO_ROOT", str(checkouts.owned_root))
        refused = runner.invoke(
            mission_app,
            ["finalize-tasks", "--mission", checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root), "--json"],
        )
        assert refused.exit_code != 0, refused.output
        assert _payload(refused)["error_code"] == OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED


# ---------------------------------------------------------------------------
# FR-008 / O5: tasks -> implement is not wedged
# ---------------------------------------------------------------------------


class TestO5NoWedge:
    def test_result_success_at_tasks_advances_into_p(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _as1(owned_checkouts, monkeypatch)
        snap = _r_snapshotter(owned_checkouts)
        before = snap.take()

        advanced = _next_success(owned_checkouts)

        _assert_no_uncaught_exception(advanced)
        _assert_implement_wp01_in_p(_payload(advanced), owned_checkouts)

        follow_up = _payload(_next_query(owned_checkouts))
        assert follow_up["kind"] == "query"
        assert follow_up["mission_state"] == "implement", "a following query must not return the same unadvanced decision"
        assert follow_up["preview_step"] == "implement"
        snap.assert_unchanged(before, snap.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)

    def test_us3_as1_full_row_step_with_prompt_file_in_p(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _as1(owned_checkouts, monkeypatch)

        result = _next_success(owned_checkouts)

        assert result.exit_code == 0, result.output
        payload = _payload(result)
        assert payload["kind"] == "step"
        assert payload["prompt_file"] is not None and Path(payload["prompt_file"]).is_file()
        assert Path(payload["workspace_path"]).resolve() == owned_checkouts.owned_root.resolve()


# ---------------------------------------------------------------------------
# FR-012 (CLI envelope) / O8
# ---------------------------------------------------------------------------


class TestO8CliEnvelope:
    def test_injected_worktree_list_failure_reaches_the_json_envelope(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """One subprocess-seam injection through the real command.

        The injection is ARMED from inside ``next_cmd.decide_next`` -- i.e. only after the
        command's ownership validation has finished -- because ``subprocess.run`` is the one
        global module object: an injection live from the start would also break the claim
        check's own ``git worktree list`` and refuse the checkout before the runtime is
        reached. ``_print_decision`` serialises ``Decision.error_code`` (WP11).
        """
        checkouts, _fact = _coord_owned_with_removed_worktree(make_owned_checkouts)
        _at(monkeypatch, checkouts.repository_root)
        real_decide_next = next_cmd.decide_next

        def _arming_decide_next(*args: Any, **kwargs: Any) -> Any:
            _inject_git_worktree_failure(monkeypatch, "list")
            return real_decide_next(*args, **kwargs)

        monkeypatch.setattr(next_cmd, "decide_next", _arming_decide_next)

        result = _next_success(checkouts)

        _assert_no_uncaught_exception(result)
        payload = _payload(result)
        assert payload["kind"] == "blocked"
        assert payload["error_code"] == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE


# ---------------------------------------------------------------------------
# FR-022: in-process CLI twin (create -> next on a lanes_with_coord mission)
# ---------------------------------------------------------------------------


class TestFr022CoordinationTwin:
    """FR-022 ratchet: in-process CLI twin of ``tests/e2e/test_worktree_owned_root_concurrency.py``.

    Owned ``agent mission create --topology lanes_with_coord`` then ``next`` must be a
    non-error decision. It is green on origin/main and the mission merge-base; WP11's
    988990eb9 (owned arm builds the WHOLE mission context, which fails closed on a
    declared-but-unmaterialised coordination worktree) regressed it, and WP19 review
    cycle 1 requires the runtime fix rather than an accepted failure.
    """

    @staticmethod
    def _create(make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> tuple[OwnedCheckouts, str]:
        checkouts = make_owned_checkouts()
        agent_checkout = checkouts.sibling
        provision_test_charter(checkouts.repository_root)
        provision_test_charter(agent_checkout)
        subprocess.run(["git", "add", "-A"], cwd=agent_checkout, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "provision charter"], cwd=agent_checkout, check=True, capture_output=True)
        _at(monkeypatch, agent_checkout)
        created = runner.invoke(
            mission_app,
            [
                "create",
                "twin-coord-mission",
                "--start-branch",
                "codex/sibling",
                "--topology",
                "lanes_with_coord",
                "--pr-bound",
                "--branch-strategy",
                "already-confirmed",
                "--owned-checkout",
                str(agent_checkout),
                "--json",
            ],
        )
        assert created.exit_code == 0, created.output
        payload = _payload(created)
        assert payload["topology"] == "lanes_with_coord"
        assert payload["coordination_branch_created"] is True
        assert Path(str(payload["owned_checkout"])).resolve() == agent_checkout.resolve()
        assert not (checkouts.repository_root / "kitty-specs" / str(payload["mission_slug"])).exists()
        return checkouts, str(payload["mission_slug"])

    def test_next_after_create_is_a_typed_json_outcome_never_a_traceback(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        checkouts, slug = self._create(make_owned_checkouts, monkeypatch)
        _at(monkeypatch, checkouts.repository_root)

        result = _next("--owned-checkout", str(checkouts.sibling), "--mission", slug, "--json")

        _assert_no_uncaught_exception(result)
        payload = _payload(result)
        assert payload.get("error_code") or payload.get("kind"), payload
        assert not (checkouts.repository_root / "kitty-specs" / slug).exists(), "next must never materialise the mission in the repository root"

    def test_next_after_create_is_a_non_error_decision(self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        checkouts, slug = self._create(make_owned_checkouts, monkeypatch)
        _at(monkeypatch, checkouts.repository_root)

        result = _next("--owned-checkout", str(checkouts.sibling), "--mission", slug, "--json")

        assert result.exit_code == 0, result.output
        payload = _payload(result)
        assert payload.get("error_code") is None
        assert payload["kind"] != "blocked", payload

    def test_advance_after_create_materialises_the_coordination_worktree_and_is_not_an_error(
        self, make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        checkouts, slug = self._create(make_owned_checkouts, monkeypatch)
        _at(monkeypatch, checkouts.repository_root)

        result = _next("--agent", "claude", "--owned-checkout", str(checkouts.sibling), "--mission", slug, "--result", "success", "--json")

        _assert_no_uncaught_exception(result)
        payload = _payload(result)
        assert payload.get("error_code") is None, payload
        assert not (checkouts.repository_root / "kitty-specs" / slug).exists()


# ---------------------------------------------------------------------------
# T103 step 3: handle-less `next --owned-checkout P`
# ---------------------------------------------------------------------------


class TestHandlelessOwnedNext:
    """Sole-mission discovery runs inside the CLAIMED checkout, after the claim check."""

    def test_sole_mission_is_discovered_in_p_and_never_in_r(
        self,
        owned_checkouts: OwnedCheckouts,
        stale_root_copy: Any,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stale_dir = stale_root_copy()
        _at(monkeypatch, owned_checkouts.repository_root)

        result = _next("--owned-checkout", str(owned_checkouts.owned_root), "--json")

        _assert_no_uncaught_exception(result)
        assert result.exit_code == 0, result.output
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"
        payload = _payload(result)
        assert payload["mission_slug"] == owned_checkouts.mission_slug
        assert payload["stale_repository_root_copy"]["path"] == str(stale_dir)

    def test_a_refused_claim_is_refused_before_any_listing(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        listed: list[Path] = []
        real_list = __import__("specify_cli.context.mission_resolver", fromlist=["x"]).list_missions_for_selection
        monkeypatch.setattr(
            "specify_cli.context.mission_resolver.list_missions_for_selection",
            lambda root: (listed.append(root), real_list(root))[1],
        )
        _at(monkeypatch, owned_checkouts.repository_root)

        result = _next("--owned-checkout", str(owned_checkouts.repository_root), "--json")

        assert result.exit_code == 1, result.output
        assert _payload(result)["error_code"] == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT
        assert listed == []
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"

    def test_ambiguous_missions_are_listed_after_one_validation(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        second = owned_checkouts.mission_dir.parent / "second-mission-01M2D999"
        second.mkdir()
        (second / "meta.json").write_text(json.dumps({"mission_id": "01M2D999000000000000000002", "slug": second.name}), encoding="utf-8")
        _at(monkeypatch, owned_checkouts.repository_root)

        result = _next("--owned-checkout", str(owned_checkouts.owned_root), "--json")

        assert result.exit_code == 1, result.output
        payload = _payload(result)
        assert payload["error_code"] == "MISSION_SELECTION_REQUIRED"
        assert {m["mission_slug"] for m in payload["available_missions"]} == {owned_checkouts.mission_slug, second.name}
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"


# ---------------------------------------------------------------------------
# FR-007 / R-12: stale repository-root copy
# ---------------------------------------------------------------------------


class TestFr007StaleCopy:
    def test_owned_payload_reports_the_stale_copy_and_never_uses_r(
        self,
        owned_checkouts: OwnedCheckouts,
        stale_root_copy: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _as1(owned_checkouts, monkeypatch)
        stale_dir = stale_root_copy()

        result = _next_success(owned_checkouts)

        _assert_no_uncaught_exception(result)
        payload = _payload(result)
        _assert_implement_wp01_in_p(payload, owned_checkouts)
        assert payload["stale_repository_root_copy"]["path"] == str(stale_dir)
        assert payload["stale_repository_root_copy"]["mission_id"] == owned_checkouts.mission_id
        assert not _is_under(payload["workspace_path"], owned_checkouts.repository_root)

    def test_owned_payload_field_is_null_when_r_holds_no_copy(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _at(monkeypatch, owned_checkouts.repository_root)

        payload = _payload(_next_query(owned_checkouts))

        assert "stale_repository_root_copy" in payload
        assert payload["stale_repository_root_copy"] is None

    def test_non_owned_control_never_carries_the_key(
        self,
        owned_checkouts: OwnedCheckouts,
        stale_root_copy: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Green ratchet: a non-owned run on the same repository (R holds M) emits no ``stale_repository_root_copy``."""
        stale_root_copy()
        _provision_charter(owned_checkouts)
        _at(monkeypatch, owned_checkouts.repository_root)

        result = _next("--mission", owned_checkouts.mission_slug, "--json")

        _assert_no_uncaught_exception(result)
        assert result.exit_code == 0, result.output
        assert "stale_repository_root_copy" not in _payload(result)


# ---------------------------------------------------------------------------
# FR-003 / NFR-001: one validation, R untouched, independent of cwd and handle
# ---------------------------------------------------------------------------


class TestFr003ExactlyOneValidation:
    def test_query_validates_exactly_once(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _at(monkeypatch, owned_checkouts.repository_root)

        result = _next_query(owned_checkouts)

        assert result.exit_code == 0, result.output
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"

    def test_advance_validates_exactly_once(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _as1(owned_checkouts, monkeypatch)
        validation_count.clear()

        result = _next_success(owned_checkouts)

        _assert_no_uncaught_exception(result)
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"


class TestNfr001CwdMatrix:
    def test_query_leaves_r_unchanged_for_every_cwd_and_handle(
        self,
        owned_checkouts: OwnedCheckouts,
        owned_handle: str,
        owned_cwd: Path,
        r_snapshot: RSnapshotter,
    ) -> None:
        before = r_snapshot.take()

        result = _next_query(owned_checkouts, handle=owned_handle)

        _assert_no_uncaught_exception(result)
        assert result.exit_code == 0, result.output
        payload = _payload(result)
        assert payload["mission_slug"] == owned_checkouts.mission_slug
        r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


# ---------------------------------------------------------------------------
# US3-AS6: the fact from the start of the command is never re-derived
# ---------------------------------------------------------------------------


@dataclass
class _As6Outcome:
    branch_before_flip: str
    branch_after_flip: str
    flips: int
    validations: int
    result: Any
    payload: dict[str, Any]


def _git_out(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _run_as6(
    checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
    validation_count: list[tuple[Any, ...]],
    *,
    rederive: bool,
) -> _As6Outcome:
    """Run the AS-1 advance with R's branch flipped between validation and the runtime.

    The hook wraps ``next_cmd.decide_next``: ``next_cmd`` calls it after
    ``resolve_owned_or_adopt`` returned (the fact is in hand) and before the
    prompt is built (inside ``decide_next``), so the wrapper provably runs after
    validation. ``rederive=True`` is the deliberately reintroduced bug: the
    wrapper validates a second time after the flip.

    NFR-001 baseline (analysis I5): the ``r_snapshot`` baseline is taken AFTER the
    flip, inside the wrapper, so "0 differences" holds without an unstated HEAD
    exemption; R's branch is restored in ``finally`` and a final snapshot
    (including HEAD) confirms R is back to its pre-test state.
    """
    from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission

    r_root = checkouts.repository_root
    original_branch = _git_out(r_root, "branch", "--show-current")
    _git_out(r_root, "branch", _FLIP_BRANCH, original_branch)
    pristine = _r_snapshotter(checkouts).take()
    snap = _r_snapshotter(checkouts)
    seen: dict[str, Any] = {"flips": 0}
    real_decide_next = next_cmd.decide_next

    def _flipping_decide_next(*args: Any, **kwargs: Any) -> Any:
        seen["before"] = _git_out(r_root, "branch", "--show-current")
        _git_out(r_root, "checkout", "-q", _FLIP_BRANCH)
        seen["after"] = _git_out(r_root, "branch", "--show-current")
        seen["flips"] += 1
        seen["baseline"] = snap.take()
        if rederive:
            resolve_owned_mission(r_root, checkouts.owned_root, checkouts.mission_slug, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
        return real_decide_next(*args, **kwargs)

    monkeypatch.setattr(next_cmd, "decide_next", _flipping_decide_next)
    validation_count.clear()
    try:
        result = _next_success(checkouts)
        if seen["flips"]:
            snap.assert_unchanged(seen["baseline"], snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)
    finally:
        _git_out(r_root, "checkout", "-q", original_branch)
    _r_snapshotter(checkouts).assert_unchanged(pristine, _r_snapshotter(checkouts).take(), tolerate_status_mutex_for=checkouts.mission_slug)
    return _As6Outcome(
        branch_before_flip=seen.get("before", ""),
        branch_after_flip=seen.get("after", ""),
        flips=seen["flips"],
        validations=len(validation_count),
        result=result,
        payload=_payload(result),
    )


def _assert_as6_contract(outcome: _As6Outcome, checkouts: OwnedCheckouts) -> None:
    assert outcome.flips == 1, "the branch-flip hook never fired: the row would pass vacuously"
    assert outcome.branch_before_flip != outcome.branch_after_flip
    assert outcome.branch_after_flip == _FLIP_BRANCH
    assert outcome.validations == 1, f"observed {outcome.validations} validations"
    _assert_no_uncaught_exception(outcome.result)
    _assert_implement_wp01_in_p(outcome.payload, checkouts)
    assert not _is_under(outcome.payload["workspace_path"], checkouts.repository_root)


class TestUs3As6FactNotReDerived:
    def test_branch_flip_after_validation_changes_nothing(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _as1(owned_checkouts, monkeypatch)

        outcome = _run_as6(owned_checkouts, monkeypatch, validation_count, rederive=False)

        _assert_as6_contract(outcome, owned_checkouts)

    def test_mutation_a_reintroduced_rederivation_is_detected(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-vacuity (analysis U3): the contract above FAILS against a re-derivation bug."""
        _as1(owned_checkouts, monkeypatch)

        outcome = _run_as6(owned_checkouts, monkeypatch, validation_count, rederive=True)

        assert outcome.flips == 1
        assert outcome.validations >= 2
        with pytest.raises(AssertionError, match="validations"):
            _assert_as6_contract(outcome, owned_checkouts)


# ---------------------------------------------------------------------------
# FR-021 / US7-AS2/AS3: flagless adoption of a valid owned P, and only of that
# ---------------------------------------------------------------------------


@pytest.mark.real_worktree_detection
class TestFr021FlaglessAdoption:
    @pytest.mark.parametrize("placement", ["sibling", "under_worktrees"])
    def test_flagless_query_from_p_resolves_exactly_as_the_explicit_flag(
        self,
        make_owned_checkouts: Any,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
        placement: str,
    ) -> None:
        checkouts = make_owned_checkouts(placement=placement)
        _provision_charter(checkouts)
        _at(monkeypatch, checkouts.sibling)
        explicit = _next_query(checkouts)
        assert explicit.exit_code == 0, explicit.output
        validation_count.clear()

        _at(monkeypatch, checkouts.owned_root)
        flagless = _next("--mission", checkouts.mission_slug, "--json")

        _assert_no_uncaught_exception(flagless)
        assert flagless.exit_code == 0, flagless.output
        assert _stable(_payload(flagless)) == _stable(_payload(explicit))
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"

    def test_flagless_advance_from_p_issues_implement_in_p(
        self,
        owned_checkouts: OwnedCheckouts,
        validation_count: list[tuple[Any, ...]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _walk_to_tasks(owned_checkouts, monkeypatch)
        _at(monkeypatch, owned_checkouts.owned_root)
        validation_count.clear()

        result = _next("--agent", "claude", "--mission", owned_checkouts.mission_slug, "--result", "success", "--json")

        _assert_no_uncaught_exception(result)
        _assert_implement_wp01_in_p(_payload(result), owned_checkouts)
        assert len(validation_count) == 1, f"observed {len(validation_count)} validations"

    @staticmethod
    def _body_entered(monkeypatch: pytest.MonkeyPatch) -> list[str]:
        entered: list[str] = []
        for name in ("_run_query_mode", "_dispatch_query_mode", "_dispatch_advancing_mode"):
            real = getattr(next_cmd, name)

            def _record(*args: Any, _real: Any = real, _name: str = name, **kwargs: Any) -> Any:
                entered.append(_name)
                return _real(*args, **kwargs)

            monkeypatch.setattr(next_cmd, name, _record)
        return entered

    def test_lane_worktree_is_not_adopted(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        """Green ratchet: the legacy ``.worktrees`` guard still refuses, before any body runs."""
        from specify_cli.lanes.worktree_allocator import predict_lane_worktree

        lane_dir, _branch = predict_lane_worktree(owned_checkouts.repository_root, owned_checkouts.mission_slug, _p_code_lane_id(owned_checkouts))
        _target_branch_worktree_holding_mission(owned_checkouts, lane_dir)
        entered = self._body_entered(monkeypatch)
        _at(monkeypatch, lane_dir)

        result = _next("--mission", owned_checkouts.mission_slug, "--json")

        assert result.exit_code == 1, result.output
        assert entered == []

    def test_coordination_worktree_is_not_adopted(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        coord_dir = owned_checkouts.repository_root / ".worktrees" / f"{owned_checkouts.mission_slug}-coord"
        _target_branch_worktree_holding_mission(owned_checkouts, coord_dir)
        entered = self._body_entered(monkeypatch)
        _at(monkeypatch, coord_dir)

        result = _next("--mission", owned_checkouts.mission_slug, "--json")

        assert result.exit_code == 1, result.output
        assert entered == []

    def test_rejected_checkout_behaves_exactly_like_the_repository_root(
        self,
        owned_checkouts: OwnedCheckouts,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A registered linked checkout holding M on a mismatched branch is not adopted (US7-AS3 / O10)."""
        mismatched = tmp_path / "mismatched-branch-checkout"
        _branch_worktree_holding_mission(owned_checkouts, mismatched, "codex/mismatched-branch")
        _at(monkeypatch, owned_checkouts.repository_root)
        baseline = _next("--mission", owned_checkouts.mission_slug, "--json")
        assert baseline.exit_code == 1, baseline.output

        _at(monkeypatch, mismatched)
        result = _next("--mission", owned_checkouts.mission_slug, "--json")

        _assert_no_uncaught_exception(result)
        assert result.exit_code == baseline.exit_code
        assert _payload(result) == _payload(baseline)
