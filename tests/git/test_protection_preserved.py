"""Protection-preserved suite — the mission's C-003 ratchet (ATDD-first).

Mission ``tooling-stability-guard-coherence-01KTRC04`` (WP01, FR-008, NFR-005,
contracts C-GUARD-2 / C-GUARD-4).

This suite is authored BEFORE any guard conversion. It pins two things:

* **Invariants that hold TODAY and must stay green through every later WP**
  (T001): a plain-message commit to a protected branch with no capability is
  refused, both through the helper and the public CLI surface; and the guard
  never performs a push (direct-push-to-origin/main protection is policy + CI,
  encoded here as a structural "no push subprocess in commit_helpers" check).

* **The FIVE privilege channels as they exist today** (T002): each is a
  ``xfail(strict=True)`` repro of the CURRENT bypass, written inverted — it
  asserts the bypass is REFUSED, so it xfails while the channel is live and
  *flips to a failure* (forcing marker removal) when WP03 deletes the channel.
  This strict-xfail convergence is the designed coupling between WP01 and WP03.

The five privilege channels (``src/specify_cli/git/commit_helpers.py``):
  1. ``_is_protected_branch_exception`` — the message-prefix allowlist
     (``_PROTECTED_BRANCH_COMMIT_EXCEPTIONS``, ``release: ``/``chore: …`` etc.;
     the #1334 live repro).
  2. ``allow_protected_branch_in_test_mode`` — the test-mode bool parameter
     (gated by ``_test_mode_allows_protected_branch``).
  3. ``allow_completed_op_on_protected_branch`` — the completed-op bool param.
  4. ``_is_completed_op_record_exception`` — the op-record FILE-CONTENT
     exception.
  5. Env hatches — ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` /
     ``SPEC_KITTY_TEST_MODE`` consumed by ``assert_not_protected_branch`` (the
     public-CLI pre-check) and ``_test_mode_allows_protected_branch``.

Channels 1-5 all FLIP in WP03 (channel deletion); the strict xfail markers MUST
be removed there.

Tests use REAL git repos under ``tmp_path`` — no mocks (01KTPKST precedent) —
and leak no ``test-feature-*`` mission state.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import specify_cli.git.commit_helpers as commit_helpers
from specify_cli.cli.commands.safe_commit_cmd import safe_commit_command
from specify_cli.git.commit_helpers import (
    ProtectedBranchCommitError,
    ProtectedBranchRefused,
    safe_commit,
)

from tests.git.protected_target_fixtures import (  # noqa: F401 — pytest fixture re-export
    ProtectedTargetRepo,
    protected_target_repo,
)

pytestmark = pytest.mark.git_repo


@pytest.fixture(autouse=True)
def _clear_env_hatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient env hatch leaks privilege into the invariant tests.

    The suite controls the env hatch explicitly in the channel-5 repro; every
    other test must run with the hatches cleared so the guard's default
    fail-closed behavior is what is exercised.
    """
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)


# ---------------------------------------------------------------------------
# T001 — Protection-preserved invariants (green today, stay green)
# ---------------------------------------------------------------------------


def test_plain_commit_to_protected_branch_is_refused(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """(a) safe_commit to a protected branch with a plain message + no capability is refused."""
    repo = protected_target_repo
    repo.assert_is_spec_kitty_project()
    repo.assert_target_is_protected()

    changed = repo.write("docs/note.md", "a legitimate doc change\n")

    with pytest.raises(ProtectedBranchRefused) as excinfo:
        safe_commit(
            repo_root=repo.repo_root,
            worktree_root=repo.repo_root,
            destination_ref=repo.target_branch,
            message="docs: add a note",
            paths=(changed,),
        )
    assert excinfo.value.destination_ref == repo.target_branch


def test_guard_is_not_vacuous_without_kittify(tmp_path: Path) -> None:
    """Spot-check the guard is real: without .kittify/ the public pre-check does NOT refuse.

    This is the inverse of RISK-5 — it proves the invariant test above passes
    *because the guard fired*, not because the test never reaches it. A repo
    without ``.kittify/`` makes ``_is_spec_kitty_project`` false, so
    ``assert_not_protected_branch`` short-circuits and returns without raising.
    """
    import subprocess

    bare = tmp_path / "no_kittify_repo"
    bare.mkdir()
    subprocess.run(["git", "init", "--initial-branch", "main"], cwd=bare, check=True, capture_output=True)

    # No .kittify/ → guard skipped → no raise. If this ever raises, the
    # _is_spec_kitty_project precondition has changed and the invariant tests
    # may have become vacuous.
    commit_helpers.assert_not_protected_branch(bare, operation="commit")


def test_public_cli_path_refuses_plain_commit_to_protected_branch(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(b) the public CLI path (safe_commit_command) refuses likewise.

    The CLI command exits non-zero (``typer.Exit(1)``) when the destination is
    protected. It runs ``assert_not_protected_branch`` and ``safe_commit``; with
    the env hatches cleared, both refuse a plain commit to ``main``.
    """
    repo = protected_target_repo
    monkeypatch.chdir(repo.repo_root)
    repo.write("docs/cli-note.md", "a legitimate doc change via the CLI\n")

    import typer

    with pytest.raises(typer.Exit) as excinfo:
        safe_commit_command(
            files=[Path("docs/cli-note.md")],
            message=["docs: add a cli note"],
            to_branch=repo.target_branch,
            json_output=False,
        )
    assert excinfo.value.exit_code == 1


def test_commit_helpers_module_performs_no_push() -> None:
    """(c) direct-push protection: NO code path in commit_helpers performs a git push.

    Direct-push-to-origin/main protection is policy + CI; structurally, the
    commit helper module must never invoke ``git push``. This encodes that
    invariant as a source-level check so a future edit that introduces a push
    fails this test.
    """
    source = inspect.getsource(commit_helpers)
    # No `git push` argv anywhere in the module — the guard commits locally only.
    # (``git stash push`` is a local index operation and is intentionally allowed;
    # a remote push is spelled ``git push`` — i.e. a ``"push"`` token immediately
    # after the ``git`` argv literal — which must never appear.)
    normalized = " ".join(source.split())
    assert '"git", "push"' not in normalized and "'git', 'push'" not in normalized, (
        "commit_helpers must not invoke `git push`; direct-push protection is "
        "structural — the guard only ever commits locally"
    )


# ---------------------------------------------------------------------------
# T002 — Per-channel refusal tests (DELETED in WP03 — markers removed)
#
# Each test is written INVERTED: it asserts the bypass is REFUSED. While the
# channel was live (WP01/WP02) the bypass SUCCEEDED, so these were
# ``xfail(strict=True)``. WP03 DELETED every channel, so each refusal now holds
# and the strict markers are removed — the designed WP01↔WP03 convergence. These
# are the acceptance evidence for FR-008 / C-GUARD-2.
# ---------------------------------------------------------------------------


def test_channel1_message_prefix_exception_grants_no_privilege(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """Channel 1 — the message-prefix allowlist (#1334) is DELETED.

    A prefix-crafted message (``release: …``) used to land on a protected
    branch via ``_is_protected_branch_exception``. That channel is gone: the
    prefix grants nothing and the commit is refused.
    """
    repo = protected_target_repo
    changed = repo.write("docs/release-note.md", "crafted-prefix bypass\n")

    with pytest.raises(ProtectedBranchRefused):
        safe_commit(
            repo_root=repo.repo_root,
            worktree_root=repo.repo_root,
            destination_ref=repo.target_branch,
            message="release: 9.9.9 (prefix-crafted #1334 repro)",
            paths=(changed,),
        )


def test_channel2_test_mode_grants_no_privilege(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Channel 2 — the ``allow_protected_branch_in_test_mode`` bool is DELETED.

    The bool (gated on ``SPEC_KITTY_TEST_MODE``) used to let a plain commit land
    on a protected branch. Both the bool parameter and the env gate are gone:
    even with ``SPEC_KITTY_TEST_MODE=1`` set, a plain commit (no capability) is
    refused. Privilege is asserted-at-the-surface via ``capability=``, never the
    deleted bool or ambient env.
    """
    repo = protected_target_repo
    # The deleted env gate must grant nothing even when set.
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    changed = repo.write("docs/test-mode-note.md", "test-mode bool bypass\n")

    with pytest.raises(ProtectedBranchRefused):
        safe_commit(
            repo_root=repo.repo_root,
            worktree_root=repo.repo_root,
            destination_ref=repo.target_branch,
            message="docs: plain message, no capability asserted",
            paths=(changed,),
        )


def test_channel3_completed_op_bool_grants_no_privilege(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """Channel 3 — the ``allow_completed_op_on_protected_branch`` bool is DELETED.

    An op-record file plus the bool used to land the commit on a protected
    branch. The bool parameter no longer exists: a plain op-record commit (no
    capability) is refused.
    """
    repo = protected_target_repo
    op_id = "01HZZZZZZZZZZZZZZZZZZZZZZ0"  # 26-char Crockford ULID
    op_rel = f"kitty-ops/{op_id}.jsonl"
    changed = repo.write(
        op_rel,
        '{"event": "completed", "invocation_id": "' + op_id + '"}\n',
    )

    with pytest.raises(ProtectedBranchRefused):
        safe_commit(
            repo_root=repo.repo_root,
            worktree_root=repo.repo_root,
            destination_ref=repo.target_branch,
            message=f"op({op_id}): record completion",
            paths=(changed,),
        )


def test_channel4_op_record_file_content_grants_no_privilege(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
) -> None:
    """Channel 4 — the op-record FILE-CONTENT exception is DELETED.

    Privilege used to be derived from the *content* of the committed file (a
    JSONL ``event=completed`` line). The predicate
    ``_is_completed_op_record_exception`` no longer exists, so file content
    derives nothing. The symbol's absence IS the deletion evidence.
    """
    repo = protected_target_repo
    op_id = "01HYYYYYYYYYYYYYYYYYYYYYY0"  # 26-char Crockford ULID
    op_rel = f"kitty-ops/{op_id}.jsonl"
    repo.write(
        op_rel,
        '{"event": "completed", "invocation_id": "' + op_id + '"}\n',
    )

    # The file-content privilege predicate is DELETED: the symbol is gone, so
    # file content can no longer be a privilege source on a protected branch.
    grants_privilege = getattr(
        commit_helpers, "_is_completed_op_record_exception", None
    )
    assert grants_privilege is None, (
        "the op-record file-content privilege predicate must be deleted (WP03)"
    )


def test_channel5_env_hatch_grants_no_privilege(
    protected_target_repo: ProtectedTargetRepo,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Channel 5 — the ``SPEC_KITTY_TEST_MODE`` env privilege hatch is DELETED.

    ``SPEC_KITTY_TEST_MODE=1`` used to make ``assert_not_protected_branch``
    return without raising on a protected branch (ambient privilege). That env
    hatch is gone: with it set, the public pre-check still refuses.

    Note: the ONE retained operator escape hatch is
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` (documented in commit_guard);
    it is intentionally NOT exercised here because it is *kept* by design.
    """
    repo = protected_target_repo
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")

    with pytest.raises(ProtectedBranchCommitError):
        commit_helpers.assert_not_protected_branch(repo.repo_root, operation="commit")
