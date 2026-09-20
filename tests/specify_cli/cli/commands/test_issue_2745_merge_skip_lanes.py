"""#2745 (WP05, FR-012, US5) — ``spec-kitty merge --skip-lanes``/``--no-lanes``
CLI-surface regression.

Mission ``terminus-safety-invariant-01M2XFT7`` / WP05, T015/T016. WP02 built
the executor-side ``skip_lanes`` capability (``_MergeRunState.skip_lanes``,
``_run_lane_based_merge(..., skip_lanes=...)``,
``_synthesize_no_lane_manifest``) that lets a merge-ready direct-on-target
mission (a WP committed directly on the target branch, no lane branch, no
``lanes.json``) complete transactionally instead of hard-failing with
``MissingLanesError``. This module is WP05's CLI half: it drives the real
``spec-kitty merge`` Typer command (never ``_run_lane_based_merge`` directly)
to prove the ``--skip-lanes``/``--no-lanes`` option is actually wired onto
that capability end-to-end.

Three ATDD cases (T015), all ``@pytest.mark.regression``, issue-pinned #2745:

1. ``test_skip_lanes_flag_is_what_enables_genuine_completion`` (US5-1) — a
   merge-ready direct-on-target mission GENUINELY completes via
   ``--skip-lanes`` (merge baseline recorded + target ref advances with the
   bookkeeping commit); the SAME mission, run without the flag, still
   hard-fails with the ``MissingLanesError`` translation and leaves the
   target ref untouched — proving the flag, not some other change, is what
   unlocks completion.
2. ``test_skip_lanes_does_not_bypass_merge_ready_precondition`` (US5-2) — a
   NOT-merge-ready direct-on-target mission run with ``--skip-lanes`` still
   refuses via the merge-ready precondition (naming the missing WP), not a
   ``MissingLanesError``, before any mutation; target ref unchanged.
3. ``test_skip_lanes_completion_rolls_back_on_post_mutation_failure`` — a
   ``--skip-lanes`` completion that fails after the target has mutated rolls
   back to the pre-command checkpoint (WP02's transactional primitive), so a
   subsequent plain ``--skip-lanes`` retry completes cleanly.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from kernel.clock import now_utc_iso

import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.cli.commands.merge import merge

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "terminus-skip-lanes-2745-01M2SK75"
WP_ID = "WP01"

#: The mission's target branch. Deliberately NOT ``main``/``master``: those
#: are protected by :mod:`specify_cli.git.protection_policy`'s default
#: ``{"main", "master"}`` set, and a legacy/flat-topology mission (no
#: coordination worktree) cannot redirect its bookkeeping write to one — a
#: genuinely completing direct-on-target fixture needs a non-protected
#: integration branch, matching how the sanctioned fallback is actually used.
TARGET_BRANCH = "delivery"


# ---------------------------------------------------------------------------
# Shared git/mission bootstrap helpers (mirrors WP02's
# tests/merge/test_merge_rollback_resume_coherence.py fixture shape)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _branch_tip(repo: Path, branch: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", branch], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def _committed_meta_json(repo: Path, branch: str, mission_slug: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{branch}:kitty-specs/{mission_slug}/meta.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"expected a committed meta.json on {branch}: {result.stderr}"
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


def _write_meta(feature_dir: Path, mission_slug: str, *, purpose: str) -> None:
    meta = {
        "mission_slug": mission_slug,
        "mission_id": "01M2SK75000000000000002745",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "purpose_tldr": "#2745 merge --skip-lanes CLI-surface regression",
        "purpose_context": purpose,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_wp_file(feature_dir: Path, wp_id: str) -> None:
    (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\nagent: implementer-bot\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _event(mission_slug: str, wp_id: str, event_id: str, *, from_lane: str, to_lane: str, actor: str) -> dict[str, object]:
    return {
        "actor": actor,
        "at": now_utc_iso(),
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission_slug,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": f"review-{wp_id}" if to_lane == "approved" else None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _bootstrap_direct_on_target_mission(
    repo: Path,
    mission_slug: str,
    *,
    merge_ready: bool,
    code_filename: str,
) -> Path:
    """A direct-on-target mission: WP code committed directly on
    :data:`TARGET_BRANCH` (the target branch), no lane branch, no
    ``lanes.json``, no coordination branch — the sanctioned fallback topology
    WP05's affordance targets.

    ``merge_ready`` controls whether WP01's terminal event reaches ``approved``
    (an acceptable ending) or stalls at ``in_progress`` (not merge-ready).
    """
    _git(repo, "checkout", "-b", TARGET_BRANCH)
    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir, mission_slug, purpose="direct-on-target skip-lanes fixture")
    _write_wp_file(feature_dir, WP_ID)
    events = [
        _event(mission_slug, WP_ID, "01HXYZSK750000000000000001", from_lane="claimed", to_lane="in_progress", actor="implementer-bot"),
    ]
    if merge_ready:
        events.append(_event(mission_slug, WP_ID, "01HXYZSK750000000000000002", from_lane="in_review", to_lane="approved", actor="reviewer-renata"))
    (feature_dir / "status.events.jsonl").write_text("\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n", encoding="utf-8")
    code_path = repo / "src" / code_filename
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text(f"def {code_path.stem}() -> int:\n    return 2745\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"feat({mission_slug}): {WP_ID} committed directly on target")
    return feature_dir


@contextlib.contextmanager
def _external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock only side effects outside git/status bookkeeping — same seam set
    WP02 uses in ``tests/merge/test_merge_rollback_resume_coherence.py``."""
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = MagicMock(mode="warn")
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _invoke_merge(repo: Path, args: list[str], monkeypatch: pytest.MonkeyPatch) -> Any:
    """Drive the real ``merge`` Typer command via ``CliRunner``.

    ``monkeypatch.chdir(repo)`` matters: several resolution seams downstream
    of the executor (primary-branch detection, placement resolution) fall
    back to the process CWD when a candidate lookup misses, so an in-process
    ``CliRunner`` invocation that leaves CWD at the real dev checkout can
    silently resolve against the WRONG repository. ``spec-kitty merge`` is
    always run from inside the target repo in practice; chdir'ing here
    matches that real invocation shape.
    """
    monkeypatch.chdir(repo)
    app = typer.Typer()
    app.command()(merge)
    runner = CliRunner()
    with _external_mocks(), patch("specify_cli.cli.commands.merge.find_repo_root", return_value=repo):
        return runner.invoke(app, args)


# ---------------------------------------------------------------------------
# US5-1 / T015: genuine completion, contrasted with the flag-less hard-fail
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_skip_lanes_flag_is_what_enables_genuine_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A merge-ready direct-on-target mission GENUINELY completes via
    ``spec-kitty merge --skip-lanes`` — not merely exit-0 / no-hard-fail.

    Asserts:
    - the CLI exits 0
    - a merge baseline is recorded on target (``merged_at`` present)
    - the target ref has ADVANCED past the pre-run tip (the merge's
      bookkeeping commit lands on top of the WP's direct-on-target commit)

    Contrast (proves the FLAG is what unlocks completion, not some other
    difference): the identical mission, run WITHOUT ``--skip-lanes``, still
    hard-fails with the ``MissingLanesError`` translation and leaves the
    target ref completely unchanged.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_direct_on_target_mission(repo, MISSION_SLUG, merge_ready=True, code_filename="direct_on_target_complete.py")
    pre_run_tip = _branch_tip(repo, TARGET_BRANCH)

    # -- Without --skip-lanes: hard-fails, target untouched (the "safe but
    #    stuck" dead-end this WP's affordance fixes) --
    no_flag_result = _invoke_merge(repo, ["--mission", MISSION_SLUG, "--yes"], monkeypatch)
    assert no_flag_result.exit_code == 1, no_flag_result.output
    assert "lanes.json" in no_flag_result.output.lower() or "MissingLanesError" in no_flag_result.output.lower() or "required" in no_flag_result.output.lower(), (
        f"expected the missing-lanes translation, got: {no_flag_result.output!r}"
    )
    assert _branch_tip(repo, TARGET_BRANCH) == pre_run_tip, "no-flag run must leave the target ref untouched"

    # -- With --skip-lanes: genuinely completes --
    result = _invoke_merge(repo, ["--mission", MISSION_SLUG, "--skip-lanes", "--yes"], monkeypatch)
    assert result.exit_code == 0, result.output

    post_run_tip = _branch_tip(repo, TARGET_BRANCH)
    assert post_run_tip != pre_run_tip, "the target ref must ADVANCE (bookkeeping commit), not merely no-op"
    ancestry = _git(repo, "log", "--format=%H", post_run_tip).stdout.split()
    assert pre_run_tip in ancestry, "the pre-run tip (carrying the WP's direct-on-target commit) must remain in target ancestry"

    committed_meta = _committed_meta_json(repo, TARGET_BRANCH, MISSION_SLUG)
    assert committed_meta.get("merged_at"), f"expected a recorded merge baseline (merged_at) on target, got meta={committed_meta!r}"


# ---------------------------------------------------------------------------
# US5-2 / T015: no bypass of the merge-ready precondition
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_skip_lanes_does_not_bypass_merge_ready_precondition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--skip-lanes`` on a NOT-merge-ready direct-on-target mission still
    refuses BEFORE any mutation — the flag is not an escape from FR-001's
    terminal-readiness gate."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    not_ready_slug = f"{MISSION_SLUG}-notready"
    _bootstrap_direct_on_target_mission(repo, not_ready_slug, merge_ready=False, code_filename="direct_on_target_not_ready.py")
    pre_run_tip = _branch_tip(repo, TARGET_BRANCH)

    result = _invoke_merge(repo, ["--mission", not_ready_slug, "--skip-lanes", "--yes"], monkeypatch)

    assert result.exit_code == 1, result.output
    assert WP_ID in result.output, f"refusal must name the missing WP: {result.output!r}"
    assert "MissingLanesError" not in result.output
    assert "lanes.json" not in result.output.lower(), f"the refusal must come from the merge-ready precondition, not the manifest requirement: {result.output!r}"
    assert _branch_tip(repo, TARGET_BRANCH) == pre_run_tip, "a not-merge-ready mission must leave the target ref unchanged"


# ---------------------------------------------------------------------------
# Transactional rollback on the --skip-lanes completion path
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_skip_lanes_completion_rolls_back_on_post_mutation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``--skip-lanes`` completion that fails AFTER the target has mutated
    rolls back to the pre-command checkpoint (WP02's transactional primitive
    reused by the skip-lanes path) — no half-termination. A subsequent plain
    ``--skip-lanes`` retry then completes cleanly."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    rollback_slug = f"{MISSION_SLUG}-rollback"
    _bootstrap_direct_on_target_mission(repo, rollback_slug, merge_ready=True, code_filename="direct_on_target_rollback.py")
    pre_run_tip = _branch_tip(repo, TARGET_BRANCH)

    with patch(
        "specify_cli.merge.executor._project_status_bookkeeping_to_target",
        side_effect=RuntimeError("injected post-mutation failure (WP05 rollback regression)"),
    ):
        failing_result = _invoke_merge(repo, ["--mission", rollback_slug, "--skip-lanes", "--yes"], monkeypatch)

    assert failing_result.exit_code != 0, failing_result.output
    assert _branch_tip(repo, TARGET_BRANCH) == pre_run_tip, (
        "a post-mutation failure on the --skip-lanes path must roll the target ref back to its pre-command checkpoint"
    )

    # -- resume: a plain retry (now unobstructed) completes cleanly --
    retry_result = _invoke_merge(repo, ["--mission", rollback_slug, "--skip-lanes", "--yes"], monkeypatch)
    assert retry_result.exit_code == 0, retry_result.output
    post_retry_tip = _branch_tip(repo, TARGET_BRANCH)
    assert post_retry_tip != pre_run_tip, "the retry must genuinely complete and advance the target ref"
    committed_meta = _committed_meta_json(repo, TARGET_BRANCH, rollback_slug)
    assert committed_meta.get("merged_at"), "the retry must record the merge baseline"


# ---------------------------------------------------------------------------
# Pre-PR adversarial-squad FINDING 2 (LOW-MED) — ``--resume`` without
# re-passing ``--skip-lanes`` must auto-honor the persisted choice
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_resume_without_reflagging_skip_lanes_auto_honors_persisted_choice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_MergeRunState.skip_lanes`` was transient (never persisted to
    ``MergeState``), so ``merge --resume`` of a genuinely-lanes.json-absent
    mission defaulted ``skip_lanes=False`` and ``require_lanes_json`` raised
    ``MissingLanesError`` mid-resume — reading as a regression on a mission
    that was never going to have a lanes manifest.

    Reproduces via the SAME rollback fixture as the sibling
    ``test_skip_lanes_completion_rolls_back_on_post_mutation_failure``: a
    ``--skip-lanes`` run that fails after mutating leaves ``state.json`` with
    ``remaining_wps`` non-empty (an "interrupted merge"), then resumes via
    the real ``--resume`` flag WITHOUT re-passing ``--skip-lanes``. Must NOT
    raise ``MissingLanesError``; must complete cleanly."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    resume_slug = f"{MISSION_SLUG}-resume-no-reflag"
    _bootstrap_direct_on_target_mission(repo, resume_slug, merge_ready=True, code_filename="direct_on_target_resume.py")
    pre_run_tip = _branch_tip(repo, TARGET_BRANCH)

    with patch(
        "specify_cli.merge.executor._project_status_bookkeeping_to_target",
        side_effect=RuntimeError("injected post-mutation failure (FOLD-F2 resume regression)"),
    ):
        failing_result = _invoke_merge(repo, ["--mission", resume_slug, "--skip-lanes", "--yes"], monkeypatch)
    assert failing_result.exit_code != 0, failing_result.output
    assert _branch_tip(repo, TARGET_BRANCH) == pre_run_tip

    # -- --resume, WITHOUT --skip-lanes: must auto-honor the persisted choice --
    resume_result = _invoke_merge(repo, ["--mission", resume_slug, "--resume", "--yes"], monkeypatch)
    assert resume_result.exit_code == 0, resume_result.output
    assert "MissingLanesError" not in resume_result.output
    assert "lanes.json" not in resume_result.output.lower(), f"a resume must not re-derive skip_lanes=False from CLI defaults: {resume_result.output!r}"
    post_resume_tip = _branch_tip(repo, TARGET_BRANCH)
    assert post_resume_tip != pre_run_tip, "the resume must genuinely complete and advance the target ref"
    committed_meta = _committed_meta_json(repo, TARGET_BRANCH, resume_slug)
    assert committed_meta.get("merged_at"), "the resume must record the merge baseline"
