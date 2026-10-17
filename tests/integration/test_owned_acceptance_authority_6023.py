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

import pytest

# Shared owned R/P/S fixtures + CLI driver (the same helpers the sibling
# owned-checkout integration suites build on). The ``<name> as <name>``
# redundant-alias form re-exports the pytest fixtures so using them as test
# parameters below is not read as an F811 redefinition.
from tests.integration.test_explicit_checkout_commands import invoke
from tests.integration.test_explicit_checkout_commands import checkouts as checkouts  # noqa: F401 -- pytest fixture
from tests.integration.test_owned_pr_bound_finalization import pr_bound_checkouts as pr_bound_checkouts  # noqa: F401 -- pytest fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _json(result) -> dict:
    return json.loads(result.output)


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
