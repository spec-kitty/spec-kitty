"""#2861 causation repro — the PERSISTED proof that the "commit refused" block is closed.

**Landing note (2026-08, `tests/regression/` campsite clean).** #2861 is fixed;
this is a permanent regression guard, not a red-first reproduction, so it
carries no `regression` marker and lives with its sibling
`agent action review` / coordination-commit tests here rather than in
`tests/regression/`. The issue number is kept as history below.

coord-commit-integrity WP01 / T001 (NFR-002, red-first). FLIPPED by WP04 / T015.

Purpose
-------
#2861 reported that a manually-orchestrated coord-topology review was blocked by
a "commit refused". Two hypotheses were in play at planning time:

* FR-002 — the coord-commit path (misroute / empty-commit) refuses the commit.
* FR-006 — the ``--agent tool:model:profile:role`` actor payload is rejected as
  an "invalid value" and that rejection is what blocks the flow.

This module drives the REAL ``agent action review`` CLI against a materialized
coord mission seeded to ``for_review`` via REAL status events (the sanctioned
``coord_repo_for_review`` shape). It first PERSISTED the observed causation as
assertions (WP01), then — once WP04 eliminated the empty-second-commit — was
FLIPPED to assert the review now SUCCEEDS. WP02's US2 AC-3 gate reads this proof,
so it must go RED if the block ever regresses, not stay a prose note.

CAUSATION (WP01 verdict, now RESOLVED by WP04)
----------------------------------------------
The block was **FR-002 (coord-commit path), NOT FR-006 (actor)**. Concretely:

* The compact actor ``claude:opus:reviewer-renata:reviewer`` was ACCEPTED — it
  was never the blocker. Any dict-actor validator warning is a non-fatal
  SaaS-fanout warn-and-skip (Decision B), so FR-006 was excluded.
* The refusal was raised on the MODERN coordination-transaction path: the
  transactional status emit already committed the ``for_review -> in_review``
  transition to the coord worktree, so the follow-up workflow commit found
  "nothing to commit, working tree clean" → ``safe_commit: git commit failed``
  → refused. This is the **empty second commit** (distinct from the
  ``SafeCommitHeadMismatch`` *misroute* sub-mode exercised in
  ``test_coord_commit_integrity_e2e.py``).

RESOLUTION (WP04 / T015, FR-004 — single status write-authority)
----------------------------------------------------------------
WP04 made the coordination transaction's ``commit()`` idempotent: when the
staged paths already match HEAD (the transactional emit already committed the
transition), the follow-up commit is a clean no-op pinned at that HEAD instead
of an empty commit ``safe_commit`` rejects. ONE write authority = ONE commit.
The manual review claim therefore SUCCEEDS and this test now asserts
``exit_code == 0`` — the headline proof that #2861's block is closed.
"""

from __future__ import annotations

import enum
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from tests.characterization.test_trio_json_envelope import _build_mission_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_COMPACT_ACTOR = "claude:opus:reviewer-renata:reviewer"


def _materialize_lane_worktree(repo_root: Path, mission_dirname: str, wp_id: str) -> None:
    """Create the lane-a branch + worktree for ``wp_id``.

    The shared ``_build_mission_repo`` fixture deliberately never materializes a
    lane worktree, but a REAL ``agent action review`` runs against a mission
    whose implementation lane already exists — the post-commit auto-rebase-lane
    sync (``sync_lane_after_coordination_commit``) operates on it. Reproduce
    that reality here using the SAME canonical naming the sync itself uses so
    the success path completes end-to-end.
    """
    from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path
    from specify_cli.lanes.persistence import read_lanes_json

    feature_dir = repo_root / "kitty-specs" / mission_dirname
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None, "fixture must write lanes.json"
    lane = manifest.lane_for_wp(wp_id)
    assert lane is not None, f"{wp_id} must be lane-owned in the fixture manifest"

    coord_branch = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))["coordination_branch"]
    lane_branch = lane_branch_name(
        mission_dirname,
        lane.lane_id,
        planning_base_branch=manifest.target_branch,
    )
    # The sync resolves the worktree DIR through the same seam (no
    # identity parameter); match it exactly so the created path is the one the
    # sync will look for.
    lane_wt = worktree_path(repo_root, mission_dirname, lane_id=lane.lane_id)

    subprocess.run(
        ["git", "-C", str(repo_root), "branch", lane_branch, coord_branch],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add", str(lane_wt), lane_branch],
        check=True,
        capture_output=True,
        text=True,
    )


class Causation(enum.Enum):
    """The classified cause of the #2861 "commit refused" block."""

    COORD_COMMIT_PATH_REFUSED = "FR-002: coord-commit path refused the commit"
    ACTOR_REJECTED = "FR-006: actor payload rejected as invalid"
    NOT_BLOCKED = "no block observed"
    UNKNOWN = "unclassified"


def _classify(exit_code: int, output: str) -> Causation:
    if exit_code == 0:
        return Causation.NOT_BLOCKED
    lowered = output.lower()
    actor_rejected = "invalid" in lowered and "actor" in lowered and "[refused]" not in output
    commit_refused = "bookkeepingtransaction" in lowered or "safe_commit" in lowered
    if commit_refused and "[refused]" in output:
        return Causation.COORD_COMMIT_PATH_REFUSED
    if actor_rejected:
        return Causation.ACTOR_REJECTED
    return Causation.UNKNOWN


@pytest.mark.git_repo
def test_2861_block_is_closed_manual_coord_review_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PROOF (WP04/T015): the #2861 empty-second-commit block is closed.

    The same sanctioned coord fixture that WP01 recorded as ``exit_code == 1``
    (empty-second-commit refusal) now SUCCEEDS: a single write authority commits
    the ``for_review -> in_review`` transition exactly once, the follow-up
    workflow commit is an idempotent no-op, and the manual review claim returns
    ``exit_code == 0``.
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="trio-coord-review",
        wp_lane="for_review",
        materialize_coord=True,
    )
    # A real review runs against an existing implementation lane; the fixture
    # omits it, so materialize lane-a for the post-commit auto-rebase sync.
    _materialize_lane_worktree(repo_root, mission_slug, "WP01")

    result = runner.invoke(
        root_app,
        [
            "agent",
            "action",
            "review",
            "WP01",
            "--mission",
            mission_slug,
            "--agent",
            _COMPACT_ACTOR,
        ],
    )
    output = result.output

    # HEADLINE PROOF: the manual coord-topology review claim now SUCCEEDS
    # (the empty-second-commit no longer refuses the write).
    assert result.exit_code == 0, output

    # The causation classifier agrees: no block is observed.
    verdict = _classify(result.exit_code, output)
    assert verdict is Causation.NOT_BLOCKED, f"#2861 regressed: expected {Causation.NOT_BLOCKED} but classified {verdict}.\n--- output ---\n{output}"

    # The empty-second-commit refusal is GONE: neither the BookkeepingTransaction
    # refusal nor the "git commit failed" sub-mode may appear on the success path.
    assert "[refused]" not in output, output
    assert "git commit failed" not in output, output
    assert "SafeCommitHeadMismatch" not in output, output

    # The compact actor is still accepted (FR-006 was never the blocker) and the
    # review claim is confirmed in the output.
    assert _COMPACT_ACTOR in output, output
    assert "Claimed WP01 for review" in output, output


def _git_show(repo: Path, ref: str, path: str) -> str | None:
    """Return ``git show <ref>:<path>`` content, or ``None`` if absent on ref.

    Reads COMMITTED tree state (not the filesystem) so the assertion pins what
    the review claim actually persisted onto the coord branch.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _last_in_review_actor(events_text: str, wp_id: str) -> dict[str, object]:
    """Return the ``actor`` of the last ``* -> in_review`` transition for ``wp_id``.

    Parses the committed ``status.events.jsonl`` and selects the terminal
    review-claim transition — skipping any trailing ``InnerStateChanged``
    annotation (whose actor is a plain string), so the assertion targets the
    lane transition the FR-005 seam stamps with the structured actor.
    """
    selected: dict[str, object] | None = None
    for line in events_text.splitlines():
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        if event.get("wp_id") == wp_id and event.get("to_lane") == "in_review":
            selected = event
    assert selected is not None, f"no in_review transition for {wp_id} in:\n{events_text}"
    actor = selected["actor"]
    assert isinstance(actor, dict), f"in_review actor is not a structured dict: {actor!r}"
    return actor


@pytest.mark.git_repo
def test_2861_review_seam_persists_parsed_bare_tool_not_whole_agent_string(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-005 seam-wiring: the LIVE compact-``--agent`` review claim persists the
    PARSED bare tool + self-asserted profile into the committed coord event.

    The unit tests pin ``parse_agent_boundary_string`` + ``build_resolved_actor``
    in isolation, but nothing pinned the 3 live seams actually threading the
    PARSED bare token into the PERSISTED event. This drives the REAL
    ``agent action review`` end-to-end against the sanctioned coord fixture and
    reads the committed coord ``status.events.jsonl``: the last ``in_review``
    transition's ``actor["tool"]`` MUST be the bare ``"claude"`` (NOT the whole
    ``claude:opus:reviewer-renata:reviewer`` compact string — the #2861 leak),
    and ``actor["profile"]`` MUST be the self-asserted ``"reviewer-renata"``.

    Goes RED if any live seam reverts to ``tool=agent`` (the whole compact
    string lands in ``actor.tool``) or drops the self-asserted profile parse.
    """
    monkeypatch.setenv("SPEC_KITTY_SYNC_MINIMAL_IMPORT", "1")
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="trio-coord-review",
        wp_lane="for_review",
        materialize_coord=True,
    )
    _materialize_lane_worktree(repo_root, mission_slug, "WP01")

    result = runner.invoke(
        root_app,
        [
            "agent",
            "action",
            "review",
            "WP01",
            "--mission",
            mission_slug,
            "--agent",
            _COMPACT_ACTOR,
        ],
    )
    assert result.exit_code == 0, result.output

    mid8 = mission_slug.rsplit("-", 1)[1]
    coord_branch = f"kitty/mission-trio-coord-review-{mid8}"
    events_rel = f"kitty-specs/{mission_slug}/status.events.jsonl"
    coord_events = _git_show(repo_root, coord_branch, events_rel)
    assert coord_events is not None, "status.events.jsonl must exist on the coord branch"

    actor = _last_in_review_actor(coord_events, "WP01")
    # The PARSED bare tool — NOT the whole compact --agent string (the #2861 leak).
    assert actor["tool"] == "claude", f"the review seam must persist the PARSED bare tool, not the whole --agent string; got actor.tool={actor['tool']!r}"
    # The self-asserted profile parsed from the --agent boundary string.
    assert actor["profile"] == "reviewer-renata", (
        f"the review seam must persist the self-asserted profile from the --agent value; got actor.profile={actor['profile']!r}"
    )
