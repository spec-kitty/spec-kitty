"""Red-first real-CLI reproductions of #5046 (mixed-lane-authorship-soundness-01M3M7Y0, WP02).

Mechanism (contract ``kitty-specs/mixed-lane-authorship-soundness-01M3M7Y0/
contracts/attribution-and-verdicts.md``, plan.md D-4/D-4b): a lane shared by an
APPROVED survivor WP and a CANCELED WP that already committed real content
(the C2 "mixed lane" shape) must never let the canceled WP's content ship on
the target -- today (this mission's base) it does, silently, because the
reconciliation gate does not yet run the canceled-content divergence axis
(D-4) and does not yet restore the target on REFUSE (D-4b).

Every test below is driven through the REAL ``spec-kitty consolidate`` CLI
(``tests.terminus.conftest.run_terminus`` -- no ``_run_git`` / subprocess
mocking) against a real on-disk coordination mission built by WP01's
``build_coord_mission_mixed_lane_canceled``. They are RED on this mission's
base: the observed behaviour today is exit 0 with the canceled content
present on the target. They go GREEN once WP05 (FAIL/REFUSE verdicts) and
WP07 (REFUSE restores the target) both land -- fine inside this mission; the
final PR contains all of them. Never ``xfail``, never skipped (charter
ATDD-first / ADR 2026-07-17-1).

Positive controls for every negative shape here live in
``test_repro_5046_controls.py`` (non-vacuity tactic).

**Review cycle 1 corrections (reviewer-renata):** T006's modify/delete
targets and T007 Shape B now use ``extra_base_files`` so the touched paths
are genuinely PRE-EXISTING at the mission base (not lane-authored via
``survivor_before``) -- the real US1/SC-007 shapes the spec describes, not a
survivor-undone variant of them. Assertions are now bound to the VERDICT
BLOCK (the text starting at the verdict header), not anywhere in stdout
(Issue 3), and each path/wording pair is bound to its own semicolon-delimited
clause within that block (Issue 5) so a gate that mislabels a path cannot
still pass. ``_collapse`` also strips backticks so the recovery-step
assertion survives the CLI's Markdown-styled console output (Issue 4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_WP02_NEW_PATH = "src/pkg/wp02_new.py"
_SHARED_PATH = "src/pkg/shared.py"
_LEGACY_PATH = "src/pkg/legacy.py"
_SURVIVOR_PATH = "src/pkg/survivor.py"
_WP01_OWN_PATH = "src/pkg/wp01_survivor.py"

_SHARED_BASE_CONTENT = "SHARED = 'base'\n"
_LEGACY_BASE_CONTENT = "LEGACY = 'base'\n"
_WP01_OWN_CONTENT = "def wp01_survivor() -> str:\n    return 'wp01 owns this'\n"

_FAIL_HEADER = "Reconciliation FAILED"
_FAIL_WHO = "canceled WP02"
_FAIL_ADD_MODIFY = "carries canceled WP02's change"
_FAIL_DELETE = "deleted by canceled WP02"
_REFUSE_HEADER = "Reconciliation refused (fail-closed)"
_REFUSE_NO_ATTRIBUTION = "no commit attribution"
_LANE_NAME = "lane-a"
_RECOVERY_STEP = "re-run spec-kitty consolidate"


def _collapse(text: str) -> str:
    """Collapse whitespace to single spaces AND strip backticks, so a
    rich-console line wrap or a Markdown-styled recovery step
    ("re-run `spec-kitty consolidate`") still matches a plain substring.

    Copies the normalisation :func:`tests.terminus.conftest.output_names_content_fail`
    uses, but WITHOUT lowercasing -- these assertions pin exact-case verdict
    text (``Reconciliation FAILED``), which that helper's generic squash
    wording does not match (WP02 prompt: "do NOT use that helper for these
    assertions -- it also matches the generic squash FAIL"). Backticks are
    stripped because contract C4's recovery step is written in backticks
    (``re-run `spec-kitty consolidate` ``) and the real CLI renders Markdown
    the same way (review cycle 1, Issue 4).
    """
    return " ".join(text.replace("`", "").split())


def _verdict_block(flat: str, header: str) -> str:
    """The suffix of *flat* starting at *header* -- the operator-facing
    verdict text, never the whole stdout+stderr blob (review cycle 1, Issue
    3: ``"lane-a"`` / ``"WP02"`` are already true on ANY successful or
    canceled-with-provenance run, so an assertion that only checks "appears
    somewhere in the output" is vacuous; binding it to the verdict block
    makes it check the VERDICT actually names the lane/WP).
    """
    idx = flat.find(header)
    assert idx != -1, f"expected the verdict text '{header}' in output:\n{flat}"
    return flat[idx:]


def _clause_for_path(block: str, path: str) -> str:
    """The semicolon-delimited clause of *block* that names ``'<path>'``.

    Contract C4's FAIL template is a semicolon-joined pair per divergence
    (situation clause; recovery clause), and multiple divergences render as
    multiple such pairs. Binding a path's expected wording to the SAME
    clause the path appears in (review cycle 1, Issue 5) proves the gate
    attached the right wording to the right path, not merely that both
    strings occur somewhere in the block.
    """
    needle = f"'{path}'"
    for clause in block.split(";"):
        if needle in clause:
            return clause
    raise AssertionError(f"no clause in the verdict block names '{path}':\n{block}")


def _t006_canceled_changes() -> list[PlantedChange]:
    return [
        PlantedChange(_WP02_NEW_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n"),
        PlantedChange(_SHARED_PATH, "SHARED = 'wp02 modified shared.py'\n"),
        PlantedChange(_LEGACY_PATH, None),
    ]


def _assert_t006_fail(flat: str) -> None:
    block = _verdict_block(flat, _FAIL_HEADER)
    assert _FAIL_WHO in block, f"expected the FAIL verdict block to name '{_FAIL_WHO}':\n{block}"
    assert _LANE_NAME in block, f"expected the FAIL verdict block to name the lane '{_LANE_NAME}':\n{block}"
    assert _RECOVERY_STEP in block, f"expected the FAIL verdict block to carry the recovery step '{_RECOVERY_STEP}':\n{block}"
    assert _FAIL_ADD_MODIFY in _clause_for_path(block, _WP02_NEW_PATH), f"expected '{_WP02_NEW_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_ADD_MODIFY in _clause_for_path(block, _SHARED_PATH), f"expected '{_SHARED_PATH}' clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert _FAIL_DELETE in _clause_for_path(block, _LEGACY_PATH), f"expected '{_LEGACY_PATH}' clause rendered as '{_FAIL_DELETE}':\n{block}"


def test_canceled_content_ships_under_default_squash_is_refused_as_fail(tmp_path: Path) -> None:
    """T006 -- default squash strategy, add+modify+delete in one build.

    ``shared.py`` and ``legacy.py`` are seeded via ``extra_base_files`` so
    they genuinely PRE-DATE the mission (US1's plain "canceled WP
    modifies/deletes a pre-existing file" shape, not a survivor-undone
    variant of it -- review cycle 1, Issue 2). WP01 (the survivor) still
    authors its own real commit (``wp01_survivor.py``, unrelated to the
    touched paths) so the lane carries genuine approved content, the
    canonical #5046 shape.

    RED on the mission base: the CLI exits 0 and ``src/pkg/wp02_new.py``'s
    canceled content ships on the target -- the exact #5046 defect.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: _SHARED_BASE_CONTENT, _LEGACY_PATH: _LEGACY_BASE_CONTENT},
        canceled_changes=_t006_canceled_changes(),
        survivor_before=[PlantedChange(_WP01_OWN_PATH, _WP01_OWN_CONTENT)],
        stamp_attribution=True,
        mid8="01M5046A",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, (
        f"canceled WP02 content (add+modify+delete) must be refused by the reconciliation "
        f"gate, got exit 0 (the #5046 defect: canceled content ships silently):\n{flat}"
    )
    _assert_t006_fail(flat)
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is False, "canceled WP02's new file must never land on the target"


def test_canceled_content_ships_under_merge_is_refused_as_fail(tmp_path: Path) -> None:
    """T006 -- ``--strategy merge``. Mirrors the default-squash case above."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: _SHARED_BASE_CONTENT, _LEGACY_PATH: _LEGACY_BASE_CONTENT},
        canceled_changes=_t006_canceled_changes(),
        survivor_before=[PlantedChange(_WP01_OWN_PATH, _WP01_OWN_CONTENT)],
        stamp_attribution=True,
        mid8="01M5046B",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, (
        f"canceled WP02 content (add+modify+delete) must be refused by the reconciliation gate under --strategy merge, got exit 0:\n{flat}"
    )
    _assert_t006_fail(flat)
    assert mission.rev(mission.target_branch) == pre_sha
    assert blob_present_at(mission.repo, mission.target_branch, _WP02_NEW_PATH) is False


def test_survivor_undone_content_is_refused_as_fail(tmp_path: Path) -> None:
    """T007 (SC-007, residual R1) -- two survivor-undone shapes in one build.

    Shape A: WP01 adds ``src/pkg/survivor.py``; canceled WP02 deletes it.
    Shape B: the MISSION BASE carries ``shared.py`` at v0 (``extra_base_files``);
    WP01 modifies it to v1 (``survivor_before``); canceled WP02 writes it back
    to EXACTLY the base v0 bytes (review cycle 1, Issue 1 -- the prior version
    wrote a brand-new "restored v0" string that matched no base state, so a
    naive mission-base check would already have flagged it; the real SC-007
    shape needs the canceled content to equal the mission base BYTE FOR BYTE
    so that check would wrongly drop the finding).

    A naive "compare with the mission base" check sees Shape A's final state
    (survivor.py absent) as equal to the mission base (never existed) and
    Shape B's final state (shared.py == base v0) as equal to the mission
    base too -- both look like "the canceled change did not land" and the
    finding is dropped, shipping the undo of WP01's approved work. The
    correct ``pre_state_by_survivor`` rule (plan.md D-3/D-4) must catch both
    by checking what a SURVIVING lane commit produced immediately before
    WP02's own change, not the mission base.
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        extra_base_files={_SHARED_PATH: _SHARED_BASE_CONTENT},
        canceled_changes=[
            PlantedChange(_SURVIVOR_PATH, None),
            PlantedChange(_SHARED_PATH, _SHARED_BASE_CONTENT),
        ],
        survivor_before=[
            PlantedChange(_SURVIVOR_PATH, "def survivor() -> str:\n    return 'wp01 survivor'\n"),
            PlantedChange(_SHARED_PATH, "SHARED = 'wp01 improvement v1'\n"),
        ],
        stamp_attribution=True,
        mid8="01M5046C",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"a canceled WP02 undoing WP01's approved work (deletion + revert-to-mission-base) must be refused, got exit 0:\n{flat}"
    block = _verdict_block(flat, _FAIL_HEADER)
    assert _FAIL_WHO in block, f"expected the FAIL verdict block to name '{_FAIL_WHO}':\n{block}"
    assert _LANE_NAME in block, f"expected the FAIL verdict block to name the lane '{_LANE_NAME}':\n{block}"
    assert _RECOVERY_STEP in block, f"expected the FAIL verdict block to carry the recovery step '{_RECOVERY_STEP}':\n{block}"
    assert _FAIL_DELETE in _clause_for_path(block, _SURVIVOR_PATH), f"expected the deleted survivor.py clause rendered as '{_FAIL_DELETE}':\n{block}"
    assert _FAIL_ADD_MODIFY in _clause_for_path(block, _SHARED_PATH), f"expected the reverted shared.py clause rendered as '{_FAIL_ADD_MODIFY}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on FAIL"


def test_no_commit_attribution_is_refused_as_refuse(tmp_path: Path) -> None:
    """T008 -- REFUSE (no attribution): WP02 committed real content but its
    lifecycle events carry no ``policy_metadata.lane_head`` stamp anywhere
    (C1/C3 "missing / open window" row) -- the gate cannot resolve a claim
    window and must fail closed rather than guess.

    RED on the mission base: exit 0 (canceled content ships, same as T006,
    but for the "no evidence to reason about" reason rather than "evidence
    was resolved and it says this content is canceled").
    """
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_WP02_NEW_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n")],
        stamp_attribution=False,
        mid8="01M5046D",
    )
    pre_sha = mission.rev(mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0, f"canceled WP02 content with no commit-attribution stamp must be REFUSEd (fail-closed), got exit 0:\n{flat}"
    block = _verdict_block(flat, _REFUSE_HEADER)
    assert "WP02" in block, f"expected the REFUSE verdict block to name WP02:\n{block}"
    assert _REFUSE_NO_ATTRIBUTION in block, f"expected the REFUSE verdict block to carry '{_REFUSE_NO_ATTRIBUTION}':\n{block}"
    assert _LANE_NAME in block, f"expected the REFUSE verdict block to name the lane '{_LANE_NAME}':\n{block}"
    assert _RECOVERY_STEP in block, f"expected the REFUSE verdict block to carry the recovery step '{_RECOVERY_STEP}':\n{block}"
    assert mission.rev(mission.target_branch) == pre_sha, "target must be restored to its pre-consolidation SHA on REFUSE"
