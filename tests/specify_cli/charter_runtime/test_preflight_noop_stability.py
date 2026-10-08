"""Preflight no-op-stability regression guard (#2373; charter-deadcode-noop-
campsite WP04).

**Scope reversed by the post-tasks squad**: the #2373 residual no-op churn
is already fixed at HEAD -- there is no behavioural change in this mission.
``synthesized_drg`` freshness is a content-hash of ``charter.yaml`` alone
(#2732, commit ``4c5fb725c``), so a genuine no-op (unchanged ``charter.yaml``)
hashes equal on recompute and reads ``fresh``; ``run_charter_preflight``
short-circuits to ``passed=True`` *before* it ever reaches the auto-refresh
sequence (``preflight/runner.py`` -- ``if passed: return ...`` precedes the
``if auto_refresh: return _attempt_auto_refresh(...)`` branch), so
``spec-kitty charter synthesize`` is never even considered, let alone
invoked, for an unchanged charter. ``write_pipeline.promote`` additionally
guards all four written surfaces with ``_substantively_equal`` (#1912), and
#2773 made ``charter.yaml`` the sole hash input.

This module pins that already-correct behaviour at the **preflight** level
(the surface operators and ``spec-kitty next`` / ``implement`` actually call)
so it cannot silently regress, plus a companion anti-over-suppression guard
(INV-2/LM-5): a *genuine* ``charter.yaml`` content edit must still be judged
stale and must still drive a real ``charter synthesize`` call through
``auto_refresh=True``. Do NOT "fix" a future red here by re-homing the
freshness signal onto derived-catalog equality -- that direction over-
suppresses genuine staleness (see the WP04 task prompt's Landmines section).

**LM-1 (fixture discipline)**: this checkout's own ``.git/info/exclude``
masks ``.kittify/charter-packs/`` and ``.kittify/charter/provenance/``, and the
checkout itself reads ``built_in_only`` -- so the checkout cannot reproduce
either scenario below. Both fixtures here fabricate a **real synthesized,
doctrine-tracked** repo (a real ``charter.yaml`` + a real ``graph.yaml`` +
a synthesis manifest whose ``bundle_content_hash`` genuinely matches a
fresh recompute -- ``charter_preflight._fixtures.make_fresh_repo``) and then
commit every seeded artifact so the tree starts clean -- the exact
precondition ``_attempt_auto_refresh``'s FR-008 dirty-check requires before
it will even attempt a refresh. A first-write ``??`` materialization of
those seeded-but-uncommitted files is not itself churn; it is only checked
*after* the deliberate commit, once genuine preflight runs follow.

Covers:

* ``test_repeated_preflight_on_fresh_repo_never_shells_out_and_stays_clean``
  (T012, G2/G3): two consecutive ``run_charter_preflight(auto_refresh=True)``
  calls on a real-synthesized, committed-clean repo each report
  ``synthesized_drg`` in ``_PASS_STATES``, leave ``git status --porcelain``
  empty, and never invoke a single non-git subprocess (in particular, never
  ``spec-kitty charter synthesize``).
* ``test_substantive_charter_yaml_edit_still_triggers_synthesize`` (T013,
  INV-2/G4/F3): starting from that same committed-clean baseline, a genuine
  (committed) ``charter.yaml`` content edit is read as ``synthesized_drg
  = stale`` and ``auto_refresh=True`` actually invokes ``spec-kitty charter
  synthesize`` -- proving the no-op guard above does not overreach into
  suppressing real staleness. ``tests/specify_cli/charter_freshness/
  test_computer.py::test_synthesized_drg_stale_when_bundle_content_
  genuinely_changed`` and ``tests/specify_cli/charter_runtime/
  test_preflight_one_pass.py::test_end_to_end_charter_yaml_edit_surfaces_
  in_report`` already pin the *detection* half of this (stale state +
  blocked_reason text) at the computer/preflight(``auto_refresh=False``)
  layers respectively; neither exercises ``auto_refresh=True`` end-to-end,
  so this test closes that gap by asserting the actual subprocess
  invocation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.charter_runtime.preflight import run_charter_preflight

pytestmark = [pytest.mark.git_repo]

from ..charter_preflight._fixtures import make_fresh_repo, seed_graph, seed_manifest

_GIT_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "t@x",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "t@x",
    "PATH": "/usr/bin:/bin",
}


def _git_commit_all(repo: Path, message: str) -> None:
    """Stage and commit every file in ``repo`` (test-local helper)."""
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=repo,
        check=True,
        env=_GIT_COMMIT_ENV,
    )


def _make_committed_fresh_repo(tmp_path: Path) -> Path:
    """Build a real-synthesized, doctrine-tracked repo, committed clean.

    ``make_fresh_repo`` materialises a genuinely-fresh ``charter.yaml`` +
    ``graph.yaml`` + ``synthesis-manifest.yaml`` (the manifest's
    ``bundle_content_hash`` is computed from the real ``charter.yaml``
    content, exactly as a real ``spec-kitty charter synthesize`` run would
    stamp it) but leaves those files uncommitted. Commit them here so the
    fixture starts from the clean, doctrine-tracked baseline the no-op
    claim requires (LM-1).
    """
    make_fresh_repo(tmp_path)
    _git_commit_all(tmp_path, "seed fresh synthesized state")
    return tmp_path


def _git_status_porcelain(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# T012 -- no-op-stability guard (G2/G3)
# ---------------------------------------------------------------------------


def test_repeated_preflight_on_fresh_repo_never_shells_out_and_stays_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two consecutive ``auto_refresh=True`` runs on a real-synthesized,
    committed-clean repo are both true no-ops: passing, git-clean, and
    they never shell out to ANY ``spec-kitty`` subcommand -- in particular
    never ``charter synthesize``.

    This is the strongest form of the #2373 pin: because
    ``synthesized_drg`` is genuinely ``fresh`` (whole-file hash match),
    ``run_charter_preflight`` returns at its early ``if passed: return``
    branch and never even reaches ``_attempt_auto_refresh`` -- so no
    refresh subprocess is a candidate to begin with. If a future change
    re-homes the freshness signal and makes an unchanged ``charter.yaml``
    read non-fresh, this test goes red the moment ANY subprocess call
    appears (not just ``synthesize``), which is the whole regression class
    #2373 named.
    """
    repo = _make_committed_fresh_repo(tmp_path)

    real_run = subprocess.run
    seen_calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    for iteration in range(2):
        result = run_charter_preflight(repo, auto_refresh=True)

        assert result.passed is True, f"iteration {iteration}: blocked_reason={result.blocked_reason!r}"
        assert result.auto_refresh_applied is False, (
            f"iteration {iteration}: a genuine no-op must never even attempt a refresh"
        )
        drg = next(c for c in result.checks if c.name == "synthesized_drg")
        assert drg.state == "fresh", f"iteration {iteration}: synthesized_drg={drg.state!r}"

        dirty = _git_status_porcelain(repo)
        assert dirty == "", f"iteration {iteration}: worktree is dirty after a no-op run:\n{dirty}"

    assert seen_calls == [], (
        "charter preflight shelled out on a genuine no-op (#2373 regression); "
        f"calls seen: {seen_calls}"
    )


# ---------------------------------------------------------------------------
# T013 -- INV-2 anti-over-suppression guard (G4/F3)
# ---------------------------------------------------------------------------


def test_substantive_charter_yaml_edit_still_triggers_synthesize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine, committed ``charter.yaml`` content edit is read as
    ``synthesized_drg = stale`` and ``auto_refresh=True`` actually invokes
    ``spec-kitty charter synthesize`` -- guarding against a future no-op
    "fix" that over-suppresses real staleness (LM-5) by re-homing the
    freshness signal off the whole-file hash.
    """
    repo = _make_committed_fresh_repo(tmp_path)
    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"

    # A genuine, substantive content edit -- committed, so the worktree is
    # clean going into auto_refresh (an uncommitted edit would instead hit
    # the FR-008 dirty-worktree short-circuit and never reach synthesize,
    # which would prove nothing about THIS guard).
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# substantive edit\n",
        encoding="utf-8",
    )
    _git_commit_all(repo, "substantive charter.yaml edit")

    assert compute_freshness(repo).synthesized_drg.state == "stale"  # sanity: genuinely stale
    assert _git_status_porcelain(repo) == ""  # sanity: clean going into auto_refresh

    real_run = subprocess.run
    seen_calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            # Materialise what a real synthesize run would write, so the
            # post-refresh recompute observes a fresh DRG (mirrors
            # ``test_auto_refresh_clean_worktree_runs_sequence`` in
            # ``charter_preflight/test_runner.py``).
            seed_manifest(repo, built_in_only=False)
            seed_graph(repo)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_charter_preflight(repo, auto_refresh=True)

    assert result.auto_refresh_applied is True
    cmds_as_strs = [" ".join(c) for c in seen_calls]
    assert "spec-kitty charter synthesize" in cmds_as_strs, (
        "a genuine charter.yaml content edit must still drive `charter synthesize` "
        f"through auto_refresh (INV-2/LM-5); calls seen: {cmds_as_strs}"
    )
