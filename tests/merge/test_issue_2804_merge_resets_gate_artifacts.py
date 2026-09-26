"""Scope: #2804 (P0) -- ``spec-kitty merge`` clobbers filled coordination gate
artifacts (``acceptance-matrix.json`` / ``issue-matrix.json``) back to their
empty placeholder scaffold, on the integration branch, AFTER the done-gate has
already consumed their filled contents.

**WP11 (FR-008) campsite note:** originally fixtured with the retired
``issue-matrix.md`` shape. WP05 migrated ``issue-matrix`` to the structured
``.json`` artifact (C-008; no ``.md`` is written by any canonical path any
more) and WP11 repointed the merge-driver registration to match
(``kitty-specs/**/issue-matrix.json``) -- the ``.md`` fixture below would
silently stop exercising ANY reconcile driver (falling through to git's
default ``-X theirs`` text merge), so it is updated to the real ``.json``
row schema here. This file is not WP11-owned, but no other work package
references it (checked); the update is a direct, necessary consequence of
the T041 registration repoint, not unrelated scope creep. WP11 also
replaces the acceptance/issue-matrix drivers' whole-file "more-filled-side"
heuristic with a row-aware, base-aware (3-way) reconciler (FR-008) -- the
assertions below were updated to require that the real, accepted evidence
is never silently discarded (the #2804 invariant), matching the new
driver's behavior verified against this exact fixture.

Permanent guard: this exact scenario is fixed and this module is stably
green. Formerly a red-first ``@pytest.mark.regression`` reproduction under
``tests/regression/``; relocated here (2026-08 landing fold: make
``@pytest.mark.regression`` mean exactly one thing) once the defect stopped
reproducing.

Tracking issue: https://github.com/Priivacy-ai/spec-kitty/issues/2804 --
**#2804 itself remained OPEN at relocation time.** Only the specific
divergence this fixture reproduces (the mission->target squash merge's
``-X theirs`` conflict resolution silently discarding an already-accepted
``acceptance-matrix.json``/``issue-matrix.json`` fill) is confirmed fixed by
this test going green; broader scope the issue may still cover is
unverified by this module and must not be inferred as closed from this
relocation alone.

Root-cause mechanism (confirmed by replaying the real incident's git history --
mission ``charter-deadcode-noop-campsite-01KXW0NY``, reflog entries
``aa9126844`` "Record acceptance commit for ..." -> ``2be339a0c`` "squash merge
of mission" -> the operator's manual recovery commit "restore terminal
issue-matrix + acceptance-matrix (merge reset them to placeholders)"):

``acceptance-matrix.json`` / ``issue-matrix.json`` are COORD-partition kinds
(``mission_runtime.artifacts._PLACEMENT_ARTIFACT_KINDS``). ``finalize-tasks``
scaffolds their placeholder INSIDE the mission-branch checkout (the
finalize-tasks / lane-provisioning step runs there), while ``spec-kitty
accept``'s residual-artifact commit lands them on the PRIMARY checkout
(target_branch) -- a *different* branch, per the sibling, already-open #2404
("accept reads/writes acceptance-matrix.json via the primary checkout, not the
coordination surface"). Because the file is introduced FOR THE FIRST TIME
independently on each side (an add/add divergence -- the mission branch never
carries the accept-authored fill, and the target branch never carried the
placeholder), ``spec-kitty merge``'s mission->target squash step
(``specify_cli.lanes.merge._merge_branch_into``, ``git merge --squash -X
theirs <mission_branch>``) resolves the add/add conflict by taking "theirs"
(the mission branch's stale placeholder) -- silently discarding the target's
already-filled, already-accepted content. This is orthogonal to the
``finalize-tasks`` scaffolder itself, which is idempotent and never touches an
existing file (``scaffold_acceptance_matrix``/``scaffold_issue_matrix``: "if
path.exists(): return path") -- the reset happens purely through ``-X theirs``
conflict resolution during the REAL merge branch-integration step, not through
any scaffold call.

This module reproduces the clobber through the real, pre-existing merge entry
point (``specify_cli.cli.commands.merge._run_lane_based_merge`` ->
``specify_cli.merge.executor`` -> ``specify_cli.lanes.merge.
integrate_mission_into_target`` -> the real ``git merge --squash -X theirs``
subprocess), never a hand-rolled reimplementation of the merge or of git's
conflict resolution. The harness mirrors the proven coord-topology
lane-based-merge fixture in ``tests/merge/
test_issue_2711_merge_rollback_resume_coherence.py`` (mocking only side
effects that are irrelevant to git content -- dossier sync, stale-assertion
scan, merge-gate policy, baseline-commit bookkeeping, done-transition
recording) while leaving the git plumbing (branch creation, lane merge,
mission->target squash merge) entirely real.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import ExitStack
from kernel.clock import now_utc_iso
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the status package before any coordination submodule -- mirrors the
# production CLI entrypoint's import order (see test_issue_2711's identical
# guard) so this module stays importable under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.acceptance.matrix import SCAFFOLD_TODO_MARKER
from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MID8 = "01KXW0NY"
MISSION_ID = f"01KXW0NY0000000000000000{MID8[-2:]}"
MISSION_SLUG = f"charter-deadcode-noop-campsite-{MID8}"
MISSION_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LANE_ID = "lane-a"
LANE_CODE = "src/charter/generator.py"
WP_ID = "WP01"

# --- Realistic, production-shaped acceptance-matrix.json ------------------
# Mirrors the real (pre-clobber) evidence recorded for the incident mission
# that surfaced #2804 -- multiple genuinely-verified FR criteria, real
# reviewer/evidence text, ``overall_verdict: pass`` -- not a toy placeholder.
FILLED_ACCEPTANCE_MATRIX: dict[str, object] = {
    "mission_slug": MISSION_SLUG,
    "mission_number": "",
    "mission_type": "software-dev",
    "overall_verdict": "pass",
    "criteria": [
        {
            "criterion_id": "FR-001",
            "description": (
                "Delete charter.generator module (CharterDraft/"
                "build_charter_draft/write_charter) + its __init__ import "
                "and __all__ entries."
            ),
            "proof_type": "automated_test",
            "evidence": (
                "WP01 (commit d5b8324f9): src/charter/generator.py deleted; "
                "src/charter/__init__.py import (was line 31) + 3 __all__ "
                "entries removed. git grep finds zero live src refs. "
                "uv run pytest tests/charter/test_generator.py "
                "tests/architectural/test_no_dead_modules.py -> 6 passed. "
                "Net -156 LOC."
            ),
            "pass_fail": "pass",
            "verified_by": "reviewer-renata/opus (per-WP) + orchestrator synthesis",
            "verified_at": "2026-07-19T03:20:00+00:00",
            "notes": "LM-4 clear: no charter.md scaffold path dropped.",
        },
        {
            "criterion_id": "FR-003",
            "description": (
                "Delete charter.extractor module + its test-only references "
                "(dedicated tests retired; incidental fixtures reconstructed)."
            ),
            "proof_type": "automated_test",
            "evidence": (
                "WP02 (commit 8a0a1fcf2): src/charter/extractor.py (577 LOC) "
                "+ 5 dedicated test files deleted. 2 incidental fixtures "
                "reconstructed inline so live assertions survive (31 passed)."
            ),
            "pass_fail": "pass",
            "verified_by": "reviewer-renata/opus (per-WP) + orchestrator synthesis",
            "verified_at": "2026-07-19T03:20:00+00:00",
            "notes": "Net -1685/+55 LOC.",
        },
    ],
    "negative_invariants": [],
}

FILLED_ISSUE_MATRIX: dict[str, object] = {
    "schema_version": 1,
    "rows": {
        "#2373": {
            "verdict": "verified-already-fixed",
            "evidence_ref": "commit d5b8324f9 (WP01)",
            "title": "dead-code baseline noop-stability",
            "scope": None,
            "wp": None,
            "fr": None,
            "nfr": None,
            "sc": None,
            "repo": None,
        }
    },
}

# --- The empty scaffold placeholder produced by ``scaffold_acceptance_matrix``
# / ``scaffold_issue_matrix`` at finalize-tasks time (byte-identical shape to
# the real product scaffolder -- this is what the mission branch still
# carries, since it never sees the later accept-authored fill). ---
PLACEHOLDER_ACCEPTANCE_MATRIX: dict[str, object] = {
    "mission_slug": MISSION_SLUG,
    "criteria": [
        {
            "criterion_id": "AC-001",
            "description": SCAFFOLD_TODO_MARKER,
            "proof_type": "automated_test",
            "pass_fail": "pending",
            "evidence": None,
            "notes": SCAFFOLD_TODO_MARKER,
        }
    ],
    "negative_invariants": [],
}
PLACEHOLDER_ISSUE_MATRIX: dict[str, object] = {
    "schema_version": 1,
    "rows": {
        "#2373": {
            "verdict": "unknown",
            "evidence_ref": "<link or commit>",
            "title": "<fill at WP-implementation time>",
            "scope": None,
            "wp": None,
            "fr": None,
            "nfr": None,
            "sc": None,
            "repo": None,
        }
    },
}


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "dead-code burndown + #2373/#1914 no-op-stability",
        "purpose_context": "regression fixture for #2804",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_manifest(feature_dir: Path) -> LanesManifest:
    # ``mission_id`` MUST be the ULID ``MISSION_ID`` (never the slug -- see
    # ``LanesManifest.mission_id``'s docstring, "ULID or None; never a slug").
    # Epic #5001 landing remediation: passing the slug here made
    # ``lane_branch_name`` derive a lane branch that never matched the real
    # one this fixture creates, so the reconciliation claim builder silently
    # resolved empty authorship for every run -- invisible before FIX C's new
    # fail-closed squash-vacuous-authorship guard, which correctly surfaces it.
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=MISSION_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=(LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{WP_ID}-work.md").write_text(
        "---\n"
        f"work_package_id: {WP_ID}\n"
        f"title: {WP_ID} retire charter.generator\n"
        "agent: implementer-bot\n"
        "review_status: approved\n"
        "reviewed_by: reviewer-renata\n"
        "---\n"
        f"# {WP_ID}\n",
        encoding="utf-8",
    )


def _approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZAPPR000000000000002804A",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{WP_ID}",
        "to_lane": "approved",
        "wp_id": WP_ID,
    }


def _bootstrap_mission(repo: Path) -> Path:
    """Build the real #2804 divergence: mission branch and target each
    introduce ``acceptance-matrix.json`` / ``issue-matrix.json`` INDEPENDENTLY
    (an add/add divergence), matching the real incident's history:

    1. Shared ancestor WITHOUT either gate artifact (meta/lanes/WP/status only).
    2. Mission branch (+ lane) fork here, then the mission branch commits its
       OWN ``finalize-tasks``-style placeholder scaffold (mirrors finalize-
       tasks running against the mission-branch checkout).
    3. The PRIMARY checkout (still on target_branch ``main`` -- never switched
       to the mission branch) commits the FILLED, accept-authored matrix
       DIRECTLY onto ``main`` -- the first time main ever sees these files at
       all (mirrors #2404: accept's residual-artifact commit lands on the
       primary checkout, a branch distinct from the mission integration
       branch).
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_approved_event(), sort_keys=True) + "\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap (no gate artifacts yet)")

    # --- mission branch + lane fork BEFORE the gate artifacts exist anywhere ---
    _git(repo, "branch", MISSION_BRANCH)
    _git(repo, "checkout", MISSION_BRANCH)
    (feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(PLACEHOLDER_ACCEPTANCE_MATRIX, indent=2) + "\n", encoding="utf-8"
    )
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(PLACEHOLDER_ISSUE_MATRIX, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "kitty-specs")
    _git(
        repo,
        "commit",
        "-m",
        f"tasks({MISSION_SLUG}): finalize -- scaffold acceptance/issue matrix",
    )

    lane_branch = f"{MISSION_BRANCH}-{LANE_ID}"
    _git(repo, "branch", lane_branch, MISSION_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("# generator module removed by WP01\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): {WP_ID} retire charter.generator")
    _git(repo, "checkout", "main")

    # --- primary checkout (still on target_branch) authors + accepts the
    # FILLED matrix directly onto main; the mission branch never sees this. ---
    (feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(FILLED_ACCEPTANCE_MATRIX, indent=2) + "\n", encoding="utf-8"
    )
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(FILLED_ISSUE_MATRIX, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-m", f"Finalize acceptance artifacts for {MISSION_SLUG}")

    return feature_dir


def _merge_external_mocks() -> ExitStack:
    """Mock ONLY side effects that are irrelevant to git tree content: merge
    gates/policy (no policy config in this minimal fixture), the stale-
    assertion advisory scan, dossier sync (external SaaS I/O), diff-summary /
    mission-closed emission (cosmetic), baseline-commit bookkeeping, and
    done-transition recording (a legacy-topology status-write concern
    unrelated to the #2804 file-content clobber under test). The git
    plumbing under test -- lane consolidation and the mission->target squash
    merge with ``-X theirs`` -- is left completely real.
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch(
            "specify_cli.merge.executor._enforce_review_artifact_consistency"
        ),
        "status_history": patch(
            "specify_cli.merge.executor._enforce_canonical_status_history"
        ),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "baseline_record": patch(
            "specify_cli.merge.executor._record_baseline_merge_commit", return_value=None
        ),
        "baseline_assert": patch(
            "specify_cli.merge.executor._assert_baseline_merge_commit_on_target"
        ),
        "done_on_target": patch(
            "specify_cli.merge.executor._assert_merged_wps_done_on_target"
        ),
        "record_done": patch(
            "specify_cli.merge.executor._record_merged_wps_done_for_merge"
        ),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    stack = ExitStack()
    mocks = {name: stack.enter_context(p) for name, p in patches.items()}
    gate_eval = MagicMock()
    gate_eval.overall_pass = True
    gate_eval.gates = []
    mocks["gates"].return_value = gate_eval
    policy = MagicMock()
    policy.merge_gates = []
    policy.risk = MagicMock()
    mocks["policy"].return_value = policy
    stale_report = MagicMock()
    stale_report.findings = []
    mocks["run_check"].return_value = stale_report
    return stack


def test_merge_resets_filled_gate_artifacts_to_placeholder(tmp_path: Path) -> None:
    """Permanent guard for #2804's squash-merge clobber, now fixed.

    ``spec-kitty merge`` must NEVER clobber an already-filled,
    already-accepted ``acceptance-matrix.json`` / ``issue-matrix.json`` back
    to the empty scaffold placeholder. Un-marked from
    ``@pytest.mark.regression`` and relocated out of ``tests/regression/``
    in the 2026-08 landing fold once this scenario went stably green (the
    filled coord gate artifacts survive the mission->target squash merge).
    #2804 tracking issue: #2804 -- the issue itself was still OPEN at
    relocation time; only this exact scenario is confirmed fixed here.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_mission(repo)

    # --- Precondition witnesses (BEFORE the act): the primary checkout
    # genuinely carries the FILLED, non-placeholder artifacts pre-merge --
    # so any post-merge placeholder can only be the merge's own doing, never
    # a fixture that started out empty. ---
    pre_matrix = json.loads((feature_dir / "acceptance-matrix.json").read_text(encoding="utf-8"))
    assert pre_matrix["overall_verdict"] == "pass", "precondition: fixture must start FILLED"
    assert SCAFFOLD_TODO_MARKER not in json.dumps(pre_matrix), (
        "precondition: fixture must start FILLED, not the scaffold placeholder"
    )
    pre_issue_matrix = json.loads((feature_dir / "issue-matrix.json").read_text(encoding="utf-8"))
    assert pre_issue_matrix["rows"]["#2373"]["verdict"] == "verified-already-fixed", (
        "precondition: fixture must start with a real terminal verdict row"
    )

    with _merge_external_mocks():
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=True,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )

    # --- Non-vacuity witness: the merge genuinely ran to completion and
    # advanced main with a real squash-merge commit (mission_number assigned,
    # the code file landed) -- so a placeholder result below is the merge's
    # own reset, not a merge that silently no-op'd or failed. ---
    code_landed = (repo / LANE_CODE).exists()
    assert code_landed, (
        "precondition: the merge must have genuinely integrated the mission "
        "branch into main (lane code file missing -- merge did not run)"
    )
    meta_after = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta_after.get("mission_number") == 1, (
        "precondition: merge must have assigned a mission_number on target "
        f"(merge did not complete the mission->target integration); got {meta_after.get('mission_number')!r}"
    )

    # --- CONTRACT (RED on base): the permanent record left on the
    # integration branch must still be the FILLED content, not the reset
    # scaffold placeholder. On buggy main, the ``-X theirs`` squash-merge
    # conflict resolution takes the mission branch's stale placeholder over
    # target's already-accepted fill. ---
    post_matrix = json.loads((feature_dir / "acceptance-matrix.json").read_text(encoding="utf-8"))
    assert post_matrix.get("overall_verdict") == "pass", (
        "#2804: spec-kitty merge reset acceptance-matrix.json's overall_verdict "
        f"to {post_matrix.get('overall_verdict')!r} -- the filled, accepted "
        "evidence was clobbered by the mission->target squash merge's "
        "'-X theirs' conflict resolution (mission branch's stale placeholder "
        "won over target's already-accepted fill)."
    )
    assert SCAFFOLD_TODO_MARKER not in json.dumps(post_matrix), (
        "#2804: spec-kitty merge reset acceptance-matrix.json's criteria back "
        f"to the scaffold placeholder ({SCAFFOLD_TODO_MARKER!r}), discarding "
        f"the real accepted evidence. Post-merge content: {post_matrix!r}"
    )

    post_issue_matrix = json.loads((feature_dir / "issue-matrix.json").read_text(encoding="utf-8"))
    merged_row = post_issue_matrix["rows"]["#2373"]
    # WP11 (FR-008): the row-aware driver reconciles the SAME row key (#2373)
    # present with genuinely differing content on both sides (an add/add, no
    # common base -- exactly this fixture's shape). Per the algorithm contract
    # (contracts/merge-driver-algorithm.md), a genuine same-key divergence with
    # no base to arbitrate is a structured conflict, NEVER a silent pick either
    # way -- so the assertion is deliberately narrower than "byte-identical to
    # FILLED": the scaffold's placeholder verdict must never win OUTRIGHT, and
    # the real, accepted evidence must never be silently discarded (both are
    # satisfied whether the merge cleanly resolves to the real verdict or
    # surfaces it inside a structured conflict marker).
    assert merged_row["verdict"] != "unknown", (
        "#2804 (row-aware, FR-008): spec-kitty merge let the mission branch's "
        f"scaffold verdict ('unknown') win outright over the target's real, "
        f"accepted verdict. Post-merge row: {merged_row!r}"
    )
    assert "verified-already-fixed" in json.dumps(merged_row), (
        "#2804 (row-aware, FR-008): spec-kitty merge discarded the target's "
        "real, accepted verdict ('verified-already-fixed') without leaving any "
        f"trace of it (not even in a structured conflict marker). Post-merge "
        f"row: {merged_row!r}"
    )
