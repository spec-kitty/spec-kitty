"""#6023 red-first reproduction: owned-mission acceptance authority.

A supported owned, PR-bound ``single_branch`` mission reaches acceptance with
its code work packages approved, but two acceptance surfaces lose the validated
ownership fact:

* GAP 1 -- ``agent mission acceptance-verdict`` resolves the repo root with
  ``find_repo_root()`` and the handle with ``resolve_mission_handle`` and has NO
  ``--owned-checkout`` option, so it searches the primary checkout, cannot find
  an owned-only mission, and the criterion verdict can never be recorded.
* GAP 2 -- ``accept``'s branch gate classifies the mission's WP kinds through the
  PRIMARY checkout (``_wp_kinds_for_manifest`` drops the owned fact), so
  ``mission_has_code`` is false, the minted ``kitty/mission-<slug>`` branch is
  excluded from ``allowed_branches``, and acceptance refuses with
  "Acceptance must run on mission or target branch (main), not kitty/mission-...",
  skipping the acceptance-matrix checks entirely.

Both are driven through the pre-existing CLI entry points against the
allocator-faithful owned R/P/S fixtures. RED at base, GREEN once the owned fact
is threaded through resolution, the matrix write dir, the shared locked writer
and the branch-gate WP-kind lookup.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from specify_cli.frontmatter import FrontmatterManager
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_events

# Shared owned R/P/S fixtures + CLI driver (the same helpers the sibling
# owned-checkout integration suites build on). The ``<name> as <name>``
# redundant-alias form re-exports the pytest fixtures so using them as test
# parameters below is not read as an F811 redefinition.
from tests.integration.test_explicit_checkout_commands import SLUG, invoke, snapshot
from tests.integration.test_explicit_checkout_commands import checkouts as checkouts  # noqa: F401 -- pytest fixture
from tests.integration.test_explicit_checkout_commands import git
from tests.integration.test_owned_pr_bound_finalization import pr_bound_checkouts as pr_bound_checkouts  # noqa: F401 -- pytest fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _json(result) -> dict:
    return json.loads(result.stdout)


def test_acceptance_verdict_owned_records_criterion(checkouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """GAP 1: record a criterion verdict for an owned-only mission.

    RED today: ``acceptance-verdict`` has no ``--owned-checkout`` option (the
    mission lives only in the owned checkout P, never in primary R), so the
    verdict cannot be recorded. GREEN once the owned fact is threaded through
    resolution + the matrix write seam.
    """
    _primary, owned, _sibling = checkouts

    # finalize-tasks scaffolds acceptance-matrix.json (one pending FR-001 row).
    fin = invoke("finalize-tasks", owned)
    assert fin.exit_code == 0, fin.output

    junit = owned / "junit.xml"
    junit.write_text("<testsuite tests='1' failures='0' errors='0'></testsuite>\n", encoding="utf-8")

    res = invoke(
        "acceptance-verdict",
        owned,
        "--criterion",
        "FR-001",
        "--result",
        "pass",
        "--verification-method",
        "automated_test",
        "--actor",
        "codex",
        "--evidence",
        str(junit),
    )
    assert res.exit_code == 0, (
        f"owned acceptance-verdict must resolve the owned mission and record the verdict, not fail because it searched primary (#6023 gap 1). output:\n{res.output}"
    )
    payload = _json(res)
    assert payload.get("success") is True, payload
    assert payload.get("criterion") == "FR-001"
    assert payload.get("result") == "pass"


def test_accept_owned_recognizes_minted_mission_branch(pr_bound_checkouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """GAP 2: the branch gate must recognise the minted mission branch under owned authority.

    The owned checkout sits on ``kitty/mission-<slug>`` (target ``main``), with a
    ``code_change`` WP. RED today: ``mission_has_code`` is computed through
    primary, so the branch gate rejects the mission branch and skips the matrix
    checks. GREEN once the owned fact reaches the WP-kind lookup.
    """
    _primary, owned, _sibling = pr_bound_checkouts

    fin = invoke("finalize-tasks", owned)
    assert fin.exit_code == 0, fin.output

    res = invoke("accept", owned, "--mode", "pr")
    # Assert on the RAW output (robust to any stderr the owned diagnose path mixes
    # in): the branch-gate rejection names the minted mission branch verbatim.
    assert "must run on mission or target branch" not in res.output, (
        "accept's branch gate rejected the minted mission branch for an owned mission "
        "because mission_has_code was computed through primary (#6023 gap 2). "
        f"exit={res.exit_code} output:\n{res.output}"
    )


# --------------------------------------------------------------------------- #7099

#: The ``--diagnose`` blocked-check name of the implementation-evidence gate.
_EVIDENCE_CHECK = "implementation_evidence"


def _commit_owned_change(owned: Path, relpath: str) -> None:
    """Commit one implementation change on the owned mission branch (real git evidence)."""
    target = owned / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 2\n", encoding="utf-8")
    git(owned, "add", "--", relpath)
    git(owned, "commit", "-qm", f"feat: implement {relpath}")


def _review_events(*, reviewer: str) -> list[StatusEvent]:
    """The claim -> review -> approval chain after finalize-tasks' ``planned`` event.

    Implementer ``alice`` claims and hands over; *reviewer* takes the review and the
    approval (a different actor => an independent review).
    """
    hops = (
        (Lane.PLANNED, Lane.CLAIMED, "alice"),
        (Lane.CLAIMED, Lane.IN_PROGRESS, "alice"),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW, "alice"),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW, reviewer),
        (Lane.IN_REVIEW, Lane.APPROVED, reviewer),
    )
    return [
        StatusEvent(
            event_id=f"01G709900000000000000000{n:02d}",
            mission_slug=SLUG,
            wp_id="WP01",
            from_lane=from_lane,
            to_lane=to_lane,
            at=f"2026-09-30T12:0{n}+00:00",
            actor=actor,
            force=False,
            execution_mode="worktree",
        )
        for n, (from_lane, to_lane, actor) in enumerate(hops, start=1)
    ]


def _commit_review_events(owned: Path, *, reviewer: str) -> None:
    """Seed the review chain through the atomic store primitive and commit the log."""
    mission = owned / "kitty-specs" / SLUG
    seed_status_events(mission, _review_events(reviewer=reviewer))
    git(owned, "add", "-A", "--", f"kitty-specs/{SLUG}")
    git(owned, "commit", "-qm", "status: review WP01")


def _install_stale_primary_copy(primary: Path, owned: Path) -> None:
    """Freeze the owned mission dir into the primary checkout (a stale R copy).

    The copy is taken BEFORE the owned-only work (implementation commits, review
    events, ownership edits) lands, so every read that wrongly consults primary
    sees the pre-work state. Ownership authority must never fall back to it.
    """
    stale = primary / "kitty-specs" / SLUG
    stale.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(owned / "kitty-specs" / SLUG, stale)


def _drop_owned_ownership(owned: Path) -> None:
    """Remove owned ownership while leaving the stale primary's claim intact."""
    wp_file = owned / "kitty-specs" / SLUG / "tasks" / "WP01-test.md"
    manager = FrontmatterManager()
    metadata, body = manager.read(wp_file)
    metadata["owned_files"] = []
    manager.write(wp_file, metadata, body)
    git(owned, "add", "--", f"kitty-specs/{SLUG}/tasks/WP01-test.md")
    git(owned, "commit", "-qm", "chore: WP01 owns nothing in the owned checkout")


class _Scenario(NamedTuple):
    """One owned-evidence scenario: every field the parametrized test consumes."""

    param_id: str
    commit_relpath: str
    reviewer: str
    stale_primary: bool
    drop_owned_ownership: bool
    expected_code: str | None


#: One table drives collection and the test body alike: each scenario carries
#: its pytest id, its fixture flags and its expected error code in the same row,
#: so a name can never reach the test body without its row (the retired
#: hand-copied parametrize list raised ``KeyError`` inside the body instead of
#: failing collection when the two tables drifted).
_SCENARIOS: dict[str, _Scenario] = {
    "genuine": _Scenario(
        param_id="genuine-owned-implementation-passes",
        commit_relpath="app.py",
        reviewer="bob",
        stale_primary=False,
        drop_owned_ownership=False,
        expected_code=None,
    ),
    "missing_implementation": _Scenario(
        param_id="missing-implementation-fails-closed",
        commit_relpath="other.py",
        reviewer="bob",
        stale_primary=False,
        drop_owned_ownership=False,
        expected_code="IMPLEMENTATION_MISSING",
    ),
    "self_review": _Scenario(
        param_id="self-review-fails-closed",
        commit_relpath="app.py",
        reviewer="alice",
        stale_primary=False,
        drop_owned_ownership=False,
        expected_code="REVIEW_NOT_INDEPENDENT",
    ),
    "missing_owned_ownership": _Scenario(
        param_id="missing-owned-ownership-fails-closed-even-stale-primary",
        commit_relpath="app.py",
        reviewer="bob",
        stale_primary=True,
        drop_owned_ownership=True,
        expected_code="IMPLEMENTATION_MISSING",
    ),
}


@pytest.mark.parametrize(
    ("scenario", "row"),
    [pytest.param(name, row, id=row.param_id) for name, row in _SCENARIOS.items()],
)
def test_accept_evidence_judges_ownership_through_owned_authority(
    pr_bound_checkouts,
    scenario: str,
    row: _Scenario,
) -> None:
    """Owned evidence must pass for real work and fail closed without borrowing primary ownership.

    Exercise the existing CLI with real Git changes and independent/self-review events.
    Diagnose isolates the evidence verdict from unrelated acceptance prerequisites;
    the approved-WP assertion ensures that the gate is not vacuously bypassed.
    """
    primary, owned, sibling = pr_bound_checkouts
    expected_code = row.expected_code

    fin = invoke("finalize-tasks", owned)
    assert fin.exit_code == 0, fin.output
    if row.stale_primary:
        _install_stale_primary_copy(primary, owned)
    if row.drop_owned_ownership:
        _drop_owned_ownership(owned)
    _commit_owned_change(owned, row.commit_relpath)
    _commit_review_events(owned, reviewer=row.reviewer)

    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    res = invoke("accept", owned, "--mode", "pr")
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before
    output = res.output
    payload = _json(res)
    assert payload.get("lanes", {}).get("approved") == ["WP01"], payload
    if expected_code is None:
        assert res.exit_code == 0, f"a genuine owned implementation must pass the evidence gate; output:\n{output}"
        assert payload.get("error_code") is None, payload
        assert "error" not in payload, payload
        assert "IMPLEMENTATION_MISSING" not in output and "REVIEW_NOT_INDEPENDENT" not in output, output
        assert all(check.get("check") != _EVIDENCE_CHECK for check in payload.get("blocked_checks", [])), payload
        return
    assert res.exit_code == 1, f"{scenario} must fail closed; output:\n{output}"
    # The axis keeps the single_branch voice for a single_branch mission (#5939); the canonical
    # code it aliases to is pinned by tests/consolidation/test_wp_evidence.py.
    expected_voices = {expected_code, f"SINGLE_BRANCH_{expected_code}"}
    assert payload.get("error_code") in expected_voices, payload
    assert expected_voices.intersection(payload.get("error_codes", [])), payload
    # The ownership failure must not mask the review verdict, or vice versa.
    wrong = "REVIEW_NOT_INDEPENDENT" if expected_code == "IMPLEMENTATION_MISSING" else "IMPLEMENTATION_MISSING"
    wrong_voices = {wrong, f"SINGLE_BRANCH_{wrong}"}
    assert wrong_voices.isdisjoint(payload.get("error_codes", [])), payload
    assert any(check.get("check") == _EVIDENCE_CHECK for check in payload.get("blocked_checks", [])), payload


def test_owned_self_review_refusal_uses_owned_topology(pr_bound_checkouts) -> None:
    """A stale primary topology must not change the owned self-review refusal code."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.tasks import app as tasks_app

    primary, owned, sibling = pr_bound_checkouts
    finalized = invoke("finalize-tasks", owned)
    assert finalized.exit_code == 0, finalized.output
    _install_stale_primary_copy(primary, owned)
    stale_meta_path = primary / "kitty-specs" / SLUG / "meta.json"
    stale_meta = json.loads(stale_meta_path.read_text(encoding="utf-8"))
    stale_meta["topology"] = "lanes"
    stale_meta_path.write_text(json.dumps(stale_meta), encoding="utf-8")
    _commit_owned_change(owned, "app.py")
    mission = owned / "kitty-specs" / SLUG
    seed_status_events(mission, _review_events(reviewer="alice")[:-1])
    git(owned, "add", "--", f"kitty-specs/{SLUG}")
    git(owned, "commit", "-qm", "status: implementation handed to review")
    before = tuple(snapshot(root) for root in (primary, owned, sibling))

    result = CliRunner().invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "approved", "--mission", SLUG, "--owned-checkout", str(owned), "--agent", "alice", "--json"],
    )

    assert result.exit_code == 1, result.output
    assert _json(result)["error"]["code"] == "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT", result.output
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before
