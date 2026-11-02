"""#6514: a forced status rewind out of review must be refused before it is appended.

The defect: `agent status emit WP01 --to in_progress --force --reason ...` on a WP in
``for_review`` appended a ``for_review -> in_progress`` event with ``review_ref: null`` and
reported success, while ``agent status validate`` refuses exactly that row. The log is
append-only, so the malformed row was permanent.

``for_review`` has no backward structural edge, so force is the only route into
``in_progress`` from it, and the force gate used to check nothing but actor + reason. The
requirement now lives in the work-package state machine (``status.wp_state``), which every
write door reaches before any append, so a refusal leaves the ledger byte-identical.

Every refusal assertion here is paired with a pointer-carrying request on the SAME fixture
that must append — without that positive control "nothing was written" cannot be
distinguished from "the probe cannot see a write".
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app

pytestmark = pytest.mark.fast

runner = CliRunner()

_MISSION_SLUG = "017-test-feature"


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests on local persistence: the fan-out is not under test here."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


_HOP_EXTRA: dict[str, list[str]] = {
    "claimed": [],
    "in_progress": [],
    "for_review": ["--subtasks-complete", "--implementation-evidence-present"],
    "in_review": [],
    "approved": ["--review-result-json", '{"reviewer": "reviewer-renata", "verdict": "approved", "reference": "review-cycle://WP01/1"}'],
}


def _advance_to(feature_dir: Path, target: str) -> None:
    """Seed ``planned`` then walk the WP to *target* through the real ``emit`` command."""
    from tests.status.conftest import seed_wp_to_planned

    seed_wp_to_planned(feature_dir, "WP01", slug=_MISSION_SLUG)
    lanes = ["claimed", "in_progress", "for_review", "in_review", "approved"]
    for to_lane in lanes[: lanes.index(target) + 1]:
        result = runner.invoke(
            app,
            ["emit", "WP01", "--to", to_lane, "--actor", "codex", "--mission", _MISSION_SLUG, "--json", *_HOP_EXTRA[to_lane]],
        )
        assert result.exit_code == 0, f"seed hop to {to_lane} failed: {result.stdout}"


def _advance_to_for_review(feature_dir: Path) -> None:
    _advance_to(feature_dir, "for_review")


@pytest.fixture
def repo_in_review(tmp_path: Path) -> Path:
    """A mission whose WP01 sits in ``for_review``, driven through ``agent status emit``."""
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (repo / ".kittify").mkdir()
    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.status._find_mission_slug", return_value=_MISSION_SLUG),
    ):
        _advance_to_for_review(feature_dir)
    return repo


def _invoke(repo: Path, argv: list[str]):
    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.status._find_mission_slug", return_value=_MISSION_SLUG),
    ):
        return runner.invoke(app, argv)


def _forced_rewind(repo: Path, *extra: str):
    return _invoke(
        repo,
        [
            "emit",
            "WP01",
            "--to",
            "in_progress",
            "--actor",
            "codex",
            "--mission",
            _MISSION_SLUG,
            "--force",
            "--reason",
            "source boundary changed",
            "--json",
            *extra,
        ],
    )


def _digest(path: Path) -> str:
    """Raw-byte digest: the whole point is that a refused command writes no bytes at all.

    ``charter.hasher.hash_content`` would normalise a BOM and line endings, which is
    exactly the difference a stray rewrite could hide, so this is a file-integrity
    check rather than a reuse of the charter hasher (TID251's sanctioned exception).
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- byte identity, not charter content


def _rows(feature_dir: Path) -> list[dict]:
    return [json.loads(line) for line in feature_dir.joinpath("status.events.jsonl").read_text().splitlines() if line.strip()]


def _lane_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if "from_lane" in row]


def _assert_validate_clean(repo: Path) -> None:
    result = _invoke(repo, ["validate", "--mission", _MISSION_SLUG, "--json"])
    payload = json.loads(result.stdout)
    assert payload["passed"] is True, payload["errors"]
    assert result.exit_code == 0, result.stdout


@pytest.mark.regression
def test_invalid_forced_rewind_is_refused_before_append(repo_in_review: Path) -> None:
    """#6514: no ``review_ref`` ⇒ refused, and the ledger is byte-identical afterwards."""
    feature_dir = repo_in_review / "kitty-specs" / _MISSION_SLUG
    log_path = feature_dir / "status.events.jsonl"
    snapshot_path = feature_dir / "status.json"
    log_before, snapshot_before = _digest(log_path), _digest(snapshot_path)
    rows_before = len(_rows(feature_dir))

    result = _forced_rewind(repo_in_review)

    assert result.exit_code != 0, f"the pointerless rewind was accepted: {result.stdout}"
    assert _digest(log_path) == log_before, "the refused rewind appended to status.events.jsonl"
    assert _digest(snapshot_path) == snapshot_before, "the refused rewind rematerialized status.json"
    assert len(_rows(feature_dir)) == rows_before

    payload = json.loads(result.stdout)
    assert "error" in payload, payload
    assert "event_id" not in payload, "a refused transition must not claim an event id"
    assert "to_lane" not in payload, "a refused transition must not claim a target lane"
    assert "review_ref" in payload["error"], payload["error"]
    assert "--review-ref" in payload["error"], "the refusal must name the flag that supplies the pointer"


@pytest.mark.regression
def test_validation_still_passes_after_the_refusal(repo_in_review: Path) -> None:
    """#6514: because nothing was appended, the mission's own auditor stays green."""
    assert _forced_rewind(repo_in_review).exit_code != 0

    _assert_validate_clean(repo_in_review)


@pytest.mark.regression
def test_pointer_carrying_forced_rewind_still_appends(repo_in_review: Path) -> None:
    """Positive control on the same fixture: force + a real pointer is still a legal override."""
    feature_dir = repo_in_review / "kitty-specs" / _MISSION_SLUG
    before = len(_rows(feature_dir))

    result = _forced_rewind(repo_in_review, "--review-ref", "review-cycle://WP01/1")

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["to_lane"] == "in_progress"
    rows = _rows(feature_dir)
    assert len(rows) == before + 1
    appended = _lane_rows(rows)[-1]
    assert (appended["from_lane"], appended["to_lane"]) == ("for_review", "in_progress")
    assert appended["force"] is True
    assert appended["review_ref"] == "review-cycle://WP01/1"

    _assert_validate_clean(repo_in_review)


@pytest.mark.regression
def test_whitespace_only_review_ref_is_treated_as_absent(repo_in_review: Path) -> None:
    """A blank pointer is no pointer, matching the ``review_ref.strip()`` convention."""
    feature_dir = repo_in_review / "kitty-specs" / _MISSION_SLUG
    log_path = feature_dir / "status.events.jsonl"
    digest_before = _digest(log_path)

    result = _forced_rewind(repo_in_review, "--review-ref", "   ")

    assert result.exit_code != 0, f"a whitespace-only review_ref was accepted: {result.stdout}"
    assert _digest(log_path) == digest_before
    assert "review_ref" in json.loads(result.stdout)["error"]


# ---------------------------------------------------------------------------
# #6955: the gated family reaches past ``for_review``. A pointerless rewind from
# ``in_review`` or ``approved`` also produced a row the pinned wire contract
# rejects; every door refuses it now, and the pointer-carrying twin still lands.
# ---------------------------------------------------------------------------


@pytest.fixture(params=["approved"])
def repo_in_gated_lane(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, str]:
    """A mission whose WP01 sits in ``approved``, driven through ``emit``.

    ``in_review`` is the contract's third gated edge but needs its own fix first
    (#7080); its door behaviour is pinned by ``test_force_elsewhere_is_unchanged``.
    """
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (repo / ".kittify").mkdir()
    lane = str(request.param)
    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.status._find_mission_slug", return_value=_MISSION_SLUG),
    ):
        _advance_to(feature_dir, lane)
    return repo, lane


@pytest.mark.regression
def test_pointerless_gated_rewind_is_refused_before_append(repo_in_gated_lane: tuple[Path, str]) -> None:
    """#6955: no ``review_ref`` on ``approved -> in_progress`` ⇒ refused, no bytes written."""
    repo, lane = repo_in_gated_lane
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    log_path = feature_dir / "status.events.jsonl"
    snapshot_path = feature_dir / "status.json"
    log_before, snapshot_before = _digest(log_path), _digest(snapshot_path)
    rows_before = len(_rows(feature_dir))

    result = _forced_rewind(repo)

    assert result.exit_code != 0, f"the pointerless {lane} rewind was accepted: {result.stdout}"
    assert _digest(log_path) == log_before, "the refused rewind appended to status.events.jsonl"
    assert _digest(snapshot_path) == snapshot_before, "the refused rewind rematerialized status.json"
    assert len(_rows(feature_dir)) == rows_before
    payload = json.loads(result.stdout)
    assert "error" in payload, payload
    assert "event_id" not in payload, "a refused transition must not claim an event id"
    assert "review_ref" in payload["error"], payload["error"]
    assert "--review-ref" in payload["error"], "the refusal must name the flag that supplies the pointer"


@pytest.mark.regression
def test_pointer_carrying_gated_rewind_still_appends(repo_in_gated_lane: tuple[Path, str]) -> None:
    """Positive control on the same fixture: the identical request plus a pointer appends."""
    repo, lane = repo_in_gated_lane
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    before = len(_rows(feature_dir))

    result = _forced_rewind(repo, "--review-ref", "force-override")

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["to_lane"] == "in_progress"
    rows = _rows(feature_dir)
    assert len(rows) == before + 1
    appended = _lane_rows(rows)[-1]
    assert (appended["from_lane"], appended["to_lane"]) == (lane, "in_progress")
    assert appended["force"] is True
    assert appended["review_ref"] == "force-override"
    _assert_validate_clean(repo)


@pytest.mark.regression
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_review_ref_is_refused_on_the_gated_family(repo_in_gated_lane: tuple[Path, str], blank: str) -> None:
    """A blank pointer is no pointer on the whole family, not just ``for_review``."""
    repo, _lane = repo_in_gated_lane
    log_path = repo / "kitty-specs" / _MISSION_SLUG / "status.events.jsonl"
    digest_before = _digest(log_path)

    result = _forced_rewind(repo, "--review-ref", blank)

    assert result.exit_code != 0, f"a blank review_ref was accepted: {result.stdout}"
    assert _digest(log_path) == digest_before
    assert "review_ref" in json.loads(result.stdout)["error"]


# ---------------------------------------------------------------------------
# Unit pins: the requirement lives on the FSM edge, and only on that edge
# ---------------------------------------------------------------------------


def _ctx(**overrides: object):
    from specify_cli.status.models import GuardContext

    base: dict[str, object] = {"force": True, "actor": "codex", "reason": "source boundary changed"}
    base.update(overrides)
    return GuardContext(**base)  # type: ignore[arg-type]


def _in_progress():
    from specify_cli.status.models import Lane

    return Lane.IN_PROGRESS


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("for_review", "in_progress"),
        # #6955: a pointerless forced rewind from `approved` also recorded a row
        # hosted sync rejects. `in_review` is the contract's third gated edge but
        # carries its evidence as a structured `review_result` on the emit path, so
        # it needs its own fix first (follow-up: #7080).
        ("approved", "in_progress"),
    ],
)
def test_requires_review_ref_covers_the_gated_family(from_lane: str, to_lane: str) -> None:
    from specify_cli.status.wp_state import requires_review_ref

    assert requires_review_ref(from_lane, to_lane) is True


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("for_review", "planned"),
        ("for_review", "in_review"),
        ("in_review", "planned"),
        ("in_review", "approved"),
        ("approved", "planned"),
        ("approved", "done"),
        ("done", "in_progress"),
        ("canceled", "planned"),
        ("planned", "in_progress"),
        ("nonsense-lane", "in_progress"),
    ],
)
def test_requires_review_ref_excludes_every_other_edge(from_lane: str, to_lane: str) -> None:
    """The requirement is scoped to the gated family; a malformed lane is not a member, never a raise."""
    from specify_cli.status.wp_state import requires_review_ref

    assert requires_review_ref(from_lane, to_lane) is False


def test_force_cannot_override_the_review_ref_requirement() -> None:
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for("for_review").check_transition(_in_progress(), _ctx())

    assert ok is False
    assert error is not None
    assert "review_ref" in error
    assert "--review-ref" in error
    assert "for_review -> in_progress" in error


@pytest.mark.parametrize("review_ref", ["force-override", "review-cycle://WP01/1"])
def test_a_forced_rewind_with_a_pointer_is_admitted(review_ref: str) -> None:
    from specify_cli.status.wp_state import wp_state_for

    assert wp_state_for("for_review").check_transition(_in_progress(), _ctx(review_ref=review_ref)) == (True, None)


@pytest.mark.parametrize("review_ref", ["", "   ", None])
def test_a_blank_pointer_does_not_satisfy_the_requirement(review_ref: str | None) -> None:
    from specify_cli.status.wp_state import wp_state_for

    ok, _ = wp_state_for("for_review").check_transition(_in_progress(), _ctx(review_ref=review_ref))

    assert ok is False


def test_unforced_attempt_keeps_the_historical_refusal_text() -> None:
    """Contract C-5: the new message only appears on the force path."""
    from specify_cli.status.models import GuardContext
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for("for_review").check_transition(_in_progress(), GuardContext(actor="codex", reason="why"))

    assert ok is False
    assert error == "Illegal transition: for_review -> in_progress"


def test_validator_reads_the_same_requirement() -> None:
    """The auditor's finding appears exactly when the writer's rule refuses."""
    from specify_cli.status.validate import validate_event_schema

    base = {
        "event_id": "01M68J63NCYKK6X90EG8HYNE6K",
        "mission_slug": _MISSION_SLUG,
        "wp_id": "WP01",
        "from_lane": "for_review",
        "to_lane": "in_progress",
        "at": "2026-10-31T08:00:00+00:00",
        "actor": "codex",
        "force": True,
        "reason": "source boundary changed",
        "execution_mode": "worktree",
    }

    blank = validate_event_schema(dict(base, review_ref=None))
    spaced = validate_event_schema(dict(base, review_ref="   "))
    cited = validate_event_schema(dict(base, review_ref="review-cycle://WP01/1"))

    assert blank == ["Event 01M68J63NCYKK6X90EG8HYNE6K: for_review->in_progress without review_ref"]
    assert spaced == blank, "a whitespace-only pointer must not satisfy the auditor either"
    assert cited == []


def test_move_task_plan_supplies_the_sentinel_on_the_auto_promoted_rewind() -> None:
    """#6514: the backward move is promoted to a forced rewind, so it must cite one.

    Before this, ``move-task`` set the ``force-override`` sentinel only for an explicit
    ``--force``. An unforced ``for_review -> in_progress`` was auto-promoted to
    ``emit_force=True`` with ``review_ref=None`` -- the same row ``status validate``
    refuses. Both force routes now carry the one sentinel.
    """
    from specify_cli.cli.commands.agent.tasks_transition_core import build_transition_plan

    for explicit_force in (False, True):
        plan = build_transition_plan(
            old_lane="for_review",
            target_lane="in_progress",
            force=explicit_force,
            review_feedback_pointer=None,
            arb_review_ref=None,
            note_text=None,
        )
        assert plan.emit_force is True, f"force={explicit_force}: the rewind is no longer forced"
        assert plan.emit_review_ref == "force-override", f"force={explicit_force}: no pointer on a forced rewind"


@pytest.mark.parametrize("review_ref", [0, 5, ["ref"], {"ref": 1}, 3.5])
def test_a_non_string_pointer_is_not_a_pointer(review_ref: object) -> None:
    """A corrupt log must produce a finding, never a crash, in both authorities."""
    from specify_cli.status.validate import validate_event_schema
    from specify_cli.status.wp_state import has_review_ref, wp_state_for

    assert has_review_ref(review_ref) is False
    ok, _ = wp_state_for("for_review").check_transition(_in_progress(), _ctx(review_ref=review_ref))
    assert ok is False

    findings = validate_event_schema(
        {
            "event_id": "01M68J63NCYKK6X90EG8HYNE6K",
            "mission_slug": _MISSION_SLUG,
            "wp_id": "WP01",
            "from_lane": "for_review",
            "to_lane": "in_progress",
            "at": "2026-10-31T08:00:00+00:00",
            "actor": "codex",
            "force": True,
            "reason": "source boundary changed",
            "execution_mode": "worktree",
            "review_ref": review_ref,
        }
    )
    assert findings == ["Event 01M68J63NCYKK6X90EG8HYNE6K: for_review->in_progress without review_ref"]


@pytest.mark.parametrize(
    ("from_lane", "to_lane"),
    [
        ("done", "in_progress"),
        ("canceled", "planned"),
        ("planned", "in_progress"),
        ("for_review", "planned"),
        ("in_review", "planned"),
        ("approved", "planned"),
        ("in_progress", "planned"),
        ("blocked", "in_progress"),
        # The pinned contract's third gated edge, deliberately deferred by #6955: its
        # evidence is a structured review_result the emit path never turns into a
        # review_ref, so the local writer still admits a pointerless rewind here. This
        # row is the carve-out's pin -- #7080 must flip it, and nothing else may.
        ("in_review", "in_progress"),
    ],
)
def test_force_elsewhere_is_unchanged(from_lane: str, to_lane: str) -> None:
    """Every forced edge outside the gated set still admits actor + reason (`NFR-003`)."""
    from specify_cli.status.models import GuardContext, Lane
    from specify_cli.status.wp_state import requires_review_ref, wp_state_for

    target = Lane(to_lane)
    assert requires_review_ref(from_lane, to_lane) is False
    ctx = GuardContext(force=True, actor="admin", reason="operator override")

    ok, error = wp_state_for(from_lane).check_transition(target, ctx)

    assert (ok, error) == (True, None), f"{from_lane} -> {to_lane} changed: {error}"


@pytest.mark.parametrize("target", ["planned", "blocked", "canceled"])
def test_forced_exits_from_done_still_work(target: str) -> None:
    """The terminal-exit ratchet: ``done`` stays force-only and force still admits it."""
    from specify_cli.status.models import GuardContext, Lane
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for("done").check_transition(Lane(target), GuardContext(force=True, actor="admin", reason="reopen"))

    assert (ok, error) == (True, None), error
    # ... and still refuses without force, as before.
    assert wp_state_for("done").check_transition(Lane(target), GuardContext(actor="admin", reason="reopen"))[0] is False


def test_migration_actor_is_exempt_from_the_requirement() -> None:
    """A ``migration:`` actor reconstructs state; it follows the #5446 exemption, an operator does not."""
    from specify_cli.status.wp_state import wp_state_for

    state = wp_state_for("for_review")

    assert state.check_transition(_in_progress(), _ctx(actor="migration:backfill")) == (True, None)
    assert state.check_transition(_in_progress(), _ctx(actor="codex"))[0] is False


def test_move_task_for_review_to_planned_is_not_given_the_sentinel_by_the_edge_rule() -> None:
    """The #6514 sentinel fill follows the owning edge set, not a wider copy of it.

    ``for_review -> planned`` is not in ``REVIEW_REF_REQUIRED_EDGES`` (the validator does not
    flag it). An explicit ``--force`` still gets ``force-override`` from the command's
    long-standing rule; an auto-promoted move gets none from the new rule.
    """
    from specify_cli.cli.commands.agent.tasks_transition_core import build_transition_plan

    def plan(force: bool):
        return build_transition_plan(
            old_lane="for_review",
            target_lane="planned",
            force=force,
            review_feedback_pointer=None,
            arb_review_ref=None,
            note_text="reset",
        )

    assert plan(True).emit_review_ref == "force-override"
    auto = plan(False)
    assert auto.emit_force is True
    assert auto.emit_review_ref is None


# ---------------------------------------------------------------------------
# #6955: the emitter, the local set and the pinned contract must agree
# ---------------------------------------------------------------------------


def _plan(old_lane: str, target_lane: str = "in_progress", *, pointer: str | None = None, force: bool = False):
    from specify_cli.cli.commands.agent.tasks_transition_core import build_transition_plan

    return build_transition_plan(
        old_lane=old_lane,
        target_lane=target_lane,
        force=force,
        review_feedback_pointer=pointer,
        arb_review_ref=None,
        note_text=None,
    )


@pytest.mark.parametrize("old_lane", ["for_review", "approved"])
def test_emitted_forced_family_rewind_cites_the_sentinel(old_lane: str) -> None:
    """#6955: a forced rewind with no pointer still emits a wire-valid row."""
    plan = _plan(old_lane)

    assert plan.emit_force is True
    assert plan.emit_review_ref == "force-override"


def test_approved_reopen_with_a_pointer_stays_force_free_and_cites_it() -> None:
    """The #6845 arm, unchanged: usable evidence wins over the sentinel."""
    plan = _plan("approved", pointer="/tmp/review-feedback.md")

    assert plan.emit_force is False
    assert plan.emit_review_ref == "/tmp/review-feedback.md"


def _wire_payload(from_lane: str, to_lane: str, *, force: bool, review_ref: str | None, reason: str = "rewind"):
    from spec_kitty_events.status import ExecutionMode, Lane, StatusTransitionPayload

    return StatusTransitionPayload(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        actor="codex",
        force=force,
        reason=reason,
        execution_mode=ExecutionMode("direct_repo"),
        review_ref=review_ref,
        evidence=None,
    )


def test_local_edge_set_equals_the_contract_members_it_claims() -> None:
    """`SC-003`/`FR-009`: one local set, holding exactly the edges this mission claims.

    The per-member half is the non-vacuity control: each member is proven to be a
    real requirement of the *pinned dependency* (a pointerless payload is rejected,
    its sentinel-carrying twin accepted), so the local set cannot be narrowed
    without this failing -- and a member added beyond the contract fails here too.

    The contract's third gated edge, ``in_review -> in_progress``, is deliberately
    absent: its evidence is a structured ``review_result`` the emit path does not
    turn into a ``review_ref`` yet (follow-up issue #7080). It is not silently
    dropped -- this docstring and ``wp_state.REVIEW_REF_REQUIRED_EDGES`` name it.
    """
    from spec_kitty_events.status import validate_transition
    from specify_cli.status.wp_state import REVIEW_REF_REQUIRED_EDGES

    expected = {
        ("for_review", "in_progress"),
        ("approved", "in_progress"),
    }
    assert {(from_lane.value, to_lane.value) for from_lane, to_lane in REVIEW_REF_REQUIRED_EDGES} == expected

    for from_lane, to_lane in sorted(expected):
        assert validate_transition(_wire_payload(from_lane, to_lane, force=True, review_ref=None)).valid is False, (
            f"{from_lane} -> {to_lane}: the pinned contract no longer requires a review_ref, so the local set is now wider than the contract"
        )
        assert validate_transition(_wire_payload(from_lane, to_lane, force=True, review_ref="force-override")).valid is True

    # The carve-out is real, not a typo: the contract still gates this edge (#7080).
    assert validate_transition(_wire_payload("in_review", "in_progress", force=True, review_ref=None)).valid is False


def test_the_contract_is_the_released_pin_not_a_local_patch() -> None:
    """`FR-009`: the fix conforms the payload; it never edits or re-pins the dependency."""
    from importlib.metadata import version
    from pathlib import Path

    import spec_kitty_events
    from packaging.requirements import Requirement
    from packaging.version import Version

    installed = version("spec-kitty-events")
    package_path = Path(spec_kitty_events.__file__).resolve()
    assert "site-packages" in package_path.parts, f"spec_kitty_events is not the installed package: {package_path}"

    declared = [
        Requirement(line.strip().strip(",").strip('"'))
        for line in (Path("pyproject.toml").read_text(encoding="utf-8").splitlines())
        if "spec-kitty-events" in line and line.strip().startswith('"')
    ]
    assert declared, "pyproject.toml no longer declares spec-kitty-events"
    assert any(Version(installed) in req.specifier for req in declared), (
        f"installed spec-kitty-events {installed} is outside the declared range {[str(r.specifier) for r in declared]}"
    )


@pytest.mark.parametrize("old_lane", ["for_review", "approved"])
def test_the_planner_reads_no_io_on_the_gated_family(old_lane: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """`NFR-002`: the widened predicate is a membership test, not a new read.

    The probe patches the production planner's would-be I/O seams to fail, then
    calls the real entry point -- so a future edit that starts resolving a
    pointer, a pin or a file here turns red instead of silently adding a read.
    """
    import subprocess

    def _no_io(*args: object, **kwargs: object):
        raise AssertionError("build_transition_plan performed I/O on the gated family")

    monkeypatch.setattr(Path, "read_text", _no_io)
    monkeypatch.setattr(Path, "open", _no_io)
    monkeypatch.setattr(subprocess, "run", _no_io)

    plan = _plan(old_lane, pointer="/tmp/review-feedback.md")

    # ``approved`` reads the supplied pointer; ``for_review``/``in_review`` take the
    # sentinel (their pointer arms are the rejection writer's). Either way, the plan
    # is produced with a wire-valid pointer and no I/O.
    assert plan.emit_review_ref in ("/tmp/review-feedback.md", "force-override")


# ---------------------------------------------------------------------------
# #6955: the writer's verdicts (unit) and the auditor's finding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("from_lane", ["approved"])
def test_force_cannot_override_the_requirement_on_the_added_edges(from_lane: str) -> None:
    """The family's requirement is force-insurmountable on the two added edges."""
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for(from_lane).check_transition(_in_progress(), _ctx())

    assert ok is False
    assert error is not None
    assert "review_ref" in error
    assert "--review-ref" in error


@pytest.mark.parametrize("from_lane", ["approved"])
@pytest.mark.parametrize(
    ("review_ref", "accepted"),
    [("force-override", True), ("review-cycle://WP01/1", True), ("   ", False), (None, False)],
)
def test_the_added_edges_follow_the_same_pointer_rule(from_lane: str, review_ref: str | None, accepted: bool) -> None:
    from specify_cli.status.wp_state import wp_state_for

    ok, error = wp_state_for(from_lane).check_transition(_in_progress(), _ctx(review_ref=review_ref))

    assert ok is accepted, f"{from_lane} with review_ref={review_ref!r}: {error}"


@pytest.mark.parametrize("from_lane", ["approved"])
def test_migration_actor_is_exempt_on_the_added_edges(from_lane: str) -> None:
    """A reconstruction actor restates history; the writer admits it (#5446 precedent)."""
    from specify_cli.status.wp_state import wp_state_for

    assert wp_state_for(from_lane).check_transition(_in_progress(), _ctx(actor="migration:backfill")) == (True, None)


@pytest.mark.parametrize("from_lane", ["approved"])
def test_auditor_reports_a_pointerless_family_row(from_lane: str) -> None:
    """`FR-002`: the auditor reads the same set, so the stored row is reported."""
    from specify_cli.status.validate import validate_event_schema

    event = {
        "event_id": "01M68J63NCYKK6X90EG8HYNE6K",
        "mission_slug": _MISSION_SLUG,
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": "in_progress",
        "at": "2026-10-31T08:00:00+00:00",
        "actor": "codex",
        "force": True,
        "reason": "operator rewind",
        "execution_mode": "worktree",
        "review_ref": None,
    }

    assert validate_event_schema(event) == [f"Event 01M68J63NCYKK6X90EG8HYNE6K: {from_lane}->in_progress without review_ref"]
    # Positive control on the same row: the sentinel-carrying twin is clean.
    assert validate_event_schema({**event, "review_ref": "force-override"}) == []
