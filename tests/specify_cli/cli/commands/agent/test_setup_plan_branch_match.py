"""WP06 (mission ``worktree-root-resolution-01M0B59R`` / FR-006 / #3124) —
``setup-plan``'s ``branch_matches_target`` must reflect the **invoking checkout's**
HEAD against the mission's ``meta.json`` target, NOT the **primary checkout's** HEAD.

The read-side false-green (#3124, the read-side analogue of #2613/#3051): ``setup_plan``
computes ``current_branch`` from ``get_current_branch(repo_root)`` where ``repo_root``
is the PRIMARY that ``locate_project_root()`` re-anchored to. Invoked from a lane
worktree parked on a divergent lane branch, the guard therefore reads the primary's
HEAD and reports ``branch_matches_target: true`` even though the lane sits on a
different branch than the mission targets.

Discipline (mirrors WP08 T025 + the standing red-first memory):

* Tests drive the **real** ``setup-plan`` command (``mission_mod.app``) from a
  **real** linked worktree (``git worktree add``) so the lane-vs-primary distinction
  is genuine, not simulated. ``get_current_branch`` is deliberately UNPATCHED so the
  production read of the invoking checkout runs for real.
* Both directions are asserted so a hardcoded ``false`` cannot pass:
  - a lane on a **divergent** branch → honest ``branch_matches_target: false``
    (RED on base: base reports ``true``);
  - a lane whose HEAD **matches** the ``meta.json`` target → ``true`` (the positive
    case — impossible to fake with a hardcoded ``false``).
* The owner invocation (run from the primary, on the mission target) is unchanged:
  ``branch_matches_target: true`` on base and after.
* Target-branch resolution stays primary-anchored (deliberate: ``_resolve_planning_branch``);
  only the *match* value is corrected.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import mission as mission_mod

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"
MID8 = MISSION_ID[:8]
SLUG = "setup-plan-branch-match"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"

# A substantive spec — the CONTENT clears the #846 substantive check; leaving it
# UNCOMMITTED trips the spec gate deterministically so the command emits the
# branch contract (which carries ``branch_matches_target``) via the blocked
# payload without needing plan templates or protected-branch commits.
SUBSTANTIVE_SPEC = """\
# Spec — setup-plan branch match

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-006 | Branch match honesty | branch_matches_target reflects the invoking checkout. | High | Open |
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _seed_primary(primary: Path, *, primary_branch: str, meta_target: str) -> Path:
    """Init a primary repo checked out on ``primary_branch`` with an uncommitted spec.

    ``meta.json`` records the canonical ``target_branch`` (``meta_target``). The
    spec.md is substantive but uncommitted, so the spec gate blocks and the command
    emits the branch contract deterministically. Returns the primary feature dir.
    """
    primary.mkdir(parents=True, exist_ok=True)
    (primary / ".kittify").mkdir(parents=True, exist_ok=True)
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "wp06@example.test")
    _git(primary, "config", "user.name", "WP06 Branch Match")
    _git(primary, "commit", "--allow-empty", "-qm", "init")
    if primary_branch != "main":
        _git(primary, "checkout", "-q", "-b", primary_branch)

    feature_dir = primary / "kitty-specs" / SLUG_WITH_MID8
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "target_branch": meta_target,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (feature_dir / "spec.md").write_text(SUBSTANTIVE_SPEC, encoding="utf-8")
    return feature_dir


def _add_lane_worktree(primary: Path, lane_path: Path, lane_branch: str) -> None:
    """Materialize a real linked worktree of ``primary`` on ``lane_branch``."""
    _git(primary, "worktree", "add", "-q", "-b", lane_branch, str(lane_path))


def _run_setup_plan_from(
    invocation_cwd: Path,
    primary: Path,
    feature_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """Invoke the REAL ``setup-plan`` command with ``invocation_cwd`` as cwd.

    ``locate_project_root`` is pinned to the primary (the real re-anchor a lane
    invocation sees). ``get_current_branch`` is left UNPATCHED so the production
    read of the invoking checkout is exercised for real. Git preflight and the
    coord-aware feature-dir lookup are neutralized; the dossier sync is stubbed.
    """
    runner = CliRunner()
    monkeypatch.chdir(invocation_cwd)

    prev_allow = os.environ.get("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")
    os.environ["SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"] = "1"
    prev_saas = os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC")
    os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    try:
        with (
            patch.object(mission_mod, "locate_project_root", return_value=primary),
            patch.object(mission_mod, "_enforce_git_preflight"),
            patch.object(mission_mod, "_find_feature_directory", return_value=feature_dir),
        ):
            result = runner.invoke(
                mission_mod.app,
                ["setup-plan", "--json", "--mission", SLUG_WITH_MID8],
                catch_exceptions=False,
            )
    finally:
        if prev_allow is None:
            os.environ.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
        else:
            os.environ["SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"] = prev_allow
        if prev_saas is not None:
            os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = prev_saas

    output = result.output.strip()
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {output!r}"
    payload: dict[str, object] = json.loads(output[start : end + 1])
    return payload


# --------------------------------------------------------------------------- #
# T018 — red-first: divergent lane falsely reports matches_target on base.
# --------------------------------------------------------------------------- #
def test_divergent_lane_reports_honest_branch_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lane on a DIVERGENT branch must report ``branch_matches_target: false``.

    Base (bug): ``setup_plan`` reads the primary's HEAD (== the mission target), so
    the guard reports ``true`` — this assertion is RED on ``upstream/main``.
    After the fix: the match reflects the invoking lane checkout (``lane/divergent``)
    vs the ``meta.json`` target (``fix/target``) — an honest ``false``.

    Regression pin: #3124.
    """
    primary = tmp_path / "primary"
    _seed_primary(primary, primary_branch="fix/target", meta_target="fix/target")
    lane_path = tmp_path / "lane-f"
    _add_lane_worktree(primary, lane_path, "lane/divergent")
    feature_dir = primary / "kitty-specs" / SLUG_WITH_MID8

    payload = _run_setup_plan_from(lane_path, primary, feature_dir, monkeypatch)

    assert payload.get("branch_matches_target") is False, payload


# --------------------------------------------------------------------------- #
# T019 — positive: a lane whose HEAD matches the meta target reports true.
# --------------------------------------------------------------------------- #
def test_matching_lane_reports_branch_match_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lane on the mission's ``meta.json`` target reports ``branch_matches_target: true``.

    The positive direction that a hardcoded ``false`` cannot satisfy: the primary is
    parked on ``main`` while the mission targets ``fix/target`` and the lane worktree
    is checked out on ``fix/target``. The honest match (invoking HEAD == meta target)
    is ``true`` — proving the fix reads the invoking checkout, not the primary.
    """
    primary = tmp_path / "primary"
    _seed_primary(primary, primary_branch="main", meta_target="fix/target")
    lane_path = tmp_path / "lane-f"
    _add_lane_worktree(primary, lane_path, "fix/target")
    feature_dir = primary / "kitty-specs" / SLUG_WITH_MID8

    payload = _run_setup_plan_from(lane_path, primary, feature_dir, monkeypatch)

    assert payload.get("branch_matches_target") is True, payload


# --------------------------------------------------------------------------- #
# Owner invocation unchanged — run from the primary, on the mission target.
# --------------------------------------------------------------------------- #
def test_owner_invocation_from_primary_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From the primary checkout (on the mission target) the result is unchanged: true.

    Guards the deliberate primary-anchored behavior — an owner invocation resolves
    its own checkout, so ``branch_matches_target`` is ``true`` both before and after
    the fix.
    """
    primary = tmp_path / "primary"
    _seed_primary(primary, primary_branch="fix/target", meta_target="fix/target")
    feature_dir = primary / "kitty-specs" / SLUG_WITH_MID8

    payload = _run_setup_plan_from(primary, primary, feature_dir, monkeypatch)

    assert payload.get("branch_matches_target") is True, payload


# --------------------------------------------------------------------------- #
# Coord-husk fallback — meta.json unreadable ⇒ operands collapse to invoking HEAD.
# --------------------------------------------------------------------------- #
def test_coord_husk_meta_unreadable_degrades_to_silent_match(tmp_path: Path) -> None:
    """FR-006 fallback: when ``meta.json`` cannot be read (a coord husk), the match
    operands both collapse to the invoking HEAD so the guard degrades to a silent
    match (``branch_matches_target: true``) rather than a spurious disagreement.

    Exercises ``_resolve_branch_match_operands``'s ``PlanningBranchResolutionFailed``
    branch directly: ``plan_read_dir`` has no ``meta.json``, so the canonical target
    read raises and ``match_target`` falls back to ``invoking_branch``.

    #3786: the identity is now an injected :class:`CheckoutIdentity` value object
    (resolved once at the ``setup_plan`` entrypoint) — no ``chdir`` and no
    internal-symbol patch needed to make this deterministic.
    """
    from specify_cli.cli.commands.agent.mission_setup_plan import (
        _resolve_branch_match_operands,
    )
    from specify_cli.core.checkout_identity import CheckoutIdentity, Intent

    plan_read_dir = tmp_path / "coord-husk"  # no meta.json here
    plan_read_dir.mkdir()

    invocation_identity = CheckoutIdentity(
        invoking_root=tmp_path,
        canonical_target=tmp_path,
        is_owner=True,
        intent=Intent.WRITE,
    )
    invoking_branch, match_target = _resolve_branch_match_operands(
        invocation_identity,
        plan_read_dir,
        fallback_branch="kitty/mission-x-lane-a",
        get_current_branch=lambda _root: "kitty/mission-x-lane-a",
    )

    # Both operands are the invoking HEAD ⇒ the honest match is a silent True.
    assert invoking_branch == "kitty/mission-x-lane-a"
    assert match_target == invoking_branch
