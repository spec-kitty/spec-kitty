"""NFR-002 characterization net for the `spec-kitty upgrade` refactor.

Mission: upgrade-command-hardening-01M0N5N4 (WP02, T008-T010).

This module is the **golden behavior-preservation oracle** for the WP03/WP04
restructuring of ``src/specify_cli/cli/commands/upgrade.py`` into shared
seams (writer / commit-decision / consent / finalizer — see
``kitty-specs/upgrade-command-hardening-01M0N5N4/contracts/seam-contracts.md``,
contract C4). It freezes today's (pre-refactor) commit/outcome behavior on
the DEFAULT config path (``auto_commit`` unset/true, migrations pending, no
manual-review preservation) so WP03/WP04 can prove they did not change
observable behavior. **WP03/WP04 MUST keep this test green.**

It is a CALL-LEVEL oracle: rather than driving a real git repository through
``safe_commit``'s full protected-branch guard chain (HEAD-match assertion,
ref-exists check, staging-area backstop, etc. — a large fixture burden that
belongs to ``safe_commit``'s own test suite, not this net), it spies on the
seam boundaries — ``autocommit.safe_commit`` and
``autocommit.commit_touched_checkout`` — and asserts on what they were
*called with* and *how many times*. A regression that changes the commit
count, the message format, the churn-path set, or stops routing the
main-checkout commit through the shared ``commit_touched_checkout`` seam
will fail this test even though no real git history is inspected.

NFR-002 observables pinned (per spec.md's NFR-002 row):
  (a) a commit is created
  (b) exactly one commit
  (c) the commit-message format/text
  (d) the SET of churn paths committed (set-equality, not subset)
  (e) worktree commit behavior — pinned as: the main-checkout commit is
      performed via the SAME shared ``autocommit.commit_touched_checkout``
      seam that ``runner._upgrade_worktrees`` calls for each worktree
      post-refactor (contract C4). Driving an actual worktree upgrade is out
      of scope for this fast net (covered separately by contract C5); the
      call-level pin on the shared seam is the NFR-002-relevant observable.

Environment-derived values (commit SHAs, timestamps) are deliberately NOT
asserted byte-for-byte anywhere in this file — only structure/format is
checked for those. Everything asserted here (versions, message text, path
set, capability) is fully test-controlled, so exact-match assertions on
those are appropriate, not a bug-freeze.

Explicitly NOT pinned (by design): the #3392 divergence that once existed
between the JSON-output ``success`` variable and the raw ``result.success``
check in the human-readable branch that decided whether to raise
``typer.Exit(1)``. WP04 fixed it by deriving everything from one
``UpgradeOutcome``. This net only drives the fully-successful path (no
mission-type-activation errors, no unresolved tool-surface drift), where any
formula agrees — so it cannot accidentally freeze a divergence in place. Do not
extend this file to assert exit codes on a failure/drift scenario; that belongs
to ``test_upgrade_outcome_kind.py`` and ``test_upgrade_outcome_rendering.py``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from mission_runtime import CommitTarget

import specify_cli.cli.commands.upgrade as upgrade_cmd
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# Deliberately more than one path so set-equality (vs. subset) is a
# meaningful assertion below.
EXPECTED_CHURN_PATHS = {
    ".kittify/metadata.yaml",
    ".claude/commands/spec-kitty.tasks.md",
}


def _setup_upgrade_project(tmp_path: Path) -> Path:
    """Minimal `.kittify` project scaffold.

    Mirrors ``tests/upgrade/test_upgrade_auto_commit_unit.py::_setup_upgrade_project``
    (duplicated locally so this file stays self-contained — it is this WP's
    only owned file).
    """
    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  version: '1.0.0a1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )
    return tmp_path


def _run_upgrade(**kwargs: object) -> None:
    """Drive the real `upgrade()` entry point (mirrors the sibling harness)."""
    kwargs.setdefault("plan_json", False)
    kwargs.setdefault("yes", False)
    kwargs.setdefault("no_nag", False)
    kwargs.setdefault("agent_check", False)
    kwargs.setdefault("agent_choice", None)
    kwargs.setdefault("agent_latest", None)
    upgrade_cmd.upgrade(**kwargs)


def test_default_migrations_pending_commit_behavior_characterization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NFR-002 golden: DEFAULT auto_commit path, migrations pending.

    See module docstring for the full oracle rationale and the observable
    list (a)-(e). This is the char-net's single scenario: WP03/WP04 must
    keep it green across the finalizer refactor.
    """
    project_path = _setup_upgrade_project(tmp_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)

    # --- git_status_paths: call #1 is the pre-migration baseline (clean),
    # call #2 is the post-upgrade snapshot the commit seam diffs against.
    status_calls = {"count": 0}

    def _fake_status(_repo_path: Path) -> set[str]:
        status_calls["count"] += 1
        if status_calls["count"] == 1:
            return set()
        return set(EXPECTED_CHURN_PATHS)

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)

    # --- branch detection inside commit_touched_checkout: succeed with a
    # fixed branch name (NOT the CalledProcessError fallback path — that is
    # contract C7 / FR-013's own scenario, not this default-path net).
    monkeypatch.setattr(subprocess, "check_output", lambda *_a, **_kw: "main\n")

    # --- spy on the two commit-seam boundaries named in the WP prompt. Each
    # captured field is its own typed list (rather than a dict[str, object])
    # so downstream assertions get real static types, not `object`.
    safe_commit_messages: list[str] = []
    safe_commit_paths: list[tuple[Path, ...]] = []
    safe_commit_targets: list[CommitTarget] = []
    safe_commit_capabilities: list[GuardCapability] = []

    def _spy_safe_commit(
        *,
        repo_root: Path,
        worktree_root: Path,
        destination_ref: str | None = None,
        target: CommitTarget | None = None,
        message: str,
        paths: tuple[Path, ...],
        capability: GuardCapability = GuardCapability.STANDARD,
    ) -> object:
        del repo_root, worktree_root, destination_ref  # unused by the assertions below
        safe_commit_messages.append(message)
        safe_commit_paths.append(paths)
        if target is not None:
            safe_commit_targets.append(target)
        safe_commit_capabilities.append(capability)
        return MagicMock(name="CommitResult")

    monkeypatch.setattr(autocommit, "safe_commit", _spy_safe_commit)

    original_commit_touched_checkout: Callable[[Path, set[str] | None, str, str], tuple[bool, list[str], str | None]] = autocommit.commit_touched_checkout
    commit_touched_checkout_from_versions: list[str] = []
    commit_touched_checkout_to_versions: list[str] = []

    def _spy_commit_touched_checkout(
        checkout: Path,
        baseline_paths: set[str] | None,
        from_version: str,
        to_version: str,
    ) -> tuple[bool, list[str], str | None]:
        commit_touched_checkout_from_versions.append(from_version)
        commit_touched_checkout_to_versions.append(to_version)
        return original_commit_touched_checkout(checkout, baseline_paths, from_version, to_version)

    monkeypatch.setattr(autocommit, "commit_touched_checkout", _spy_commit_touched_checkout)

    # --- a single successful, no-manual-review migration (the default path).
    fake_migration = MagicMock(
        migration_id="3.2.0a4_safe_globalize_commands",
        description="Safely remove lingering per-project spec-kitty command files",
        target_version="3.2.0a4",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.registry.MigrationRegistry.get_applicable",
        lambda *_args, **_kwargs: [fake_migration],
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRunner.upgrade",
        lambda self, *args, **kwargs: UpgradeResult(
            success=True,
            from_version="1.0.0a1",
            to_version="3.2.0a4",
            migrations_applied=["3.2.0a4_safe_globalize_commands"],
            migration_results={"3.2.0a4_safe_globalize_commands": MigrationResult(success=True)},
        ),
    )

    _run_upgrade(
        dry_run=False,
        force=True,
        target="3.2.0a4",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
    )

    data = json.loads(capsys.readouterr().out.strip())

    # Outcome-level sanity: this scenario has no mission-type-activation
    # errors and no unresolved surface drift, so the outcome is a plain success
    # on every path — the #3392 divergence is simply not in play here.
    assert data["status"] == "success"
    assert data["success"] is True
    assert data["warnings"] == []

    # (a) a commit is created
    assert data["auto_committed"] is True
    assert len(safe_commit_messages) >= 1

    # (b) exactly one commit
    assert len(safe_commit_messages) == 1, "NFR-002(b): expected exactly one commit"
    [commit_message] = safe_commit_messages
    [commit_paths] = safe_commit_paths
    [commit_target] = safe_commit_targets
    [commit_capability] = safe_commit_capabilities

    # (c) the commit-message format/text (fully test-controlled inputs, so
    # an exact-match assertion is appropriate — not an env-derived value).
    assert commit_message == "chore: apply spec-kitty upgrade changes (1.0.0a1 -> 3.2.0a4)"

    # (d) the SET of churn paths committed — set-equality, not subset.
    committed_paths = {str(p) for p in commit_paths}
    assert committed_paths == EXPECTED_CHURN_PATHS
    assert set(data["auto_commit_paths"]) == EXPECTED_CHURN_PATHS

    # Structural (not byte-exact) check on the commit target/capability: the
    # ref is asserted as the fixed branch name we injected (structure), and
    # the capability is the fixed enum member the seam always uses for
    # upgrade bookkeeping — not environment-derived, so exact-match is fine.
    assert commit_target.ref == "main"
    assert commit_capability is GuardCapability.UPGRADE_BOOKKEEPING

    # (e) worktree commit behavior: the main-checkout commit is performed
    # through the SAME shared seam (`autocommit.commit_touched_checkout`)
    # that `runner._upgrade_worktrees` calls per-worktree post-refactor
    # (contract C4). This is a call-level pin on the seam being used, not an
    # execution of an actual worktree upgrade (out of scope here; see C5).
    assert len(commit_touched_checkout_from_versions) == 1
    assert commit_touched_checkout_from_versions[0] == "1.0.0a1"
    assert commit_touched_checkout_to_versions[0] == "3.2.0a4"
