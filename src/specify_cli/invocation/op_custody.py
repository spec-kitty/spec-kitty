"""Where an Op record belongs, and whether it may be written there (#6564).

``find_repo_root`` maps a linked worktree back to the repository root checkout
on purpose: governance (the charter, profiles, glossaries) is discovered
there. An Op record is different: it is the trail of work done in the checkout
the command runs in, and it is committed on that checkout's branch. Writing it
into the repository root checkout from a feature worktree strands untracked
files on its protected branch, where the guard then refuses to commit them.

* :func:`resolve_op_record_root` keeps the two apart: it returns the invoking
  checkout when that checkout belongs to the project's repository, and the
  project root otherwise.
* :func:`locate_op_record_root` finds the checkout that already holds a given
  Op's record, so an Op opened in one checkout can be closed or claimed from
  another one of the same repository.
* :class:`OpWriteRefusal` and :class:`OpWriteRefused` carry the answer to
  "may a record be written there at all": the executor decides, this module
  owns the vocabulary and the operator-facing message.
"""

from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Iterator
from pathlib import Path

from kernel.git_topology import GitTopologyError, git_toplevel
from specify_cli.git.commit_helpers import is_worktree_of
from specify_cli.invocation.errors import InvocationError
from specify_cli.invocation.writer import InvocationWriter

__all__ = [
    "OP_WRITE_PROTECTED_BRANCH",
    "OP_WRITE_PROTECTION_CONFIG_INVALID",
    "OpWriteRefusal",
    "OpWriteRefused",
    "locate_op_record_root",
    "resolve_op_record_root",
]

#: Error codes of the pre-write admission refusal (#6564).
OP_WRITE_PROTECTED_BRANCH = "OP_WRITE_PROTECTED_BRANCH"
OP_WRITE_PROTECTION_CONFIG_INVALID = "OP_WRITE_PROTECTION_CONFIG_INVALID"

_GIT_TIMEOUT_SECONDS = 30
_WORKTREE_LINE_PREFIX = "worktree "


def _git_lines(cwd: Path, *args: str) -> list[str] | None:
    """Stripped stdout lines of a git command in ``cwd``; ``None`` when it fails."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0 or not lines:
        return None
    return lines


def resolve_op_record_root(project_root: Path, start: Path | None = None) -> Path:
    """Return the checkout whose ``kitty-ops/`` holds the Op records of this command.

    That is the git checkout containing ``start`` (default: the working
    directory) when it belongs to the project's repository: the repository
    root checkout or one of its linked worktrees. Anything else (no git checkout,
    or a checkout of a different repository) falls back to ``project_root``,
    which is what every Op command used before #6564.

    Both checks are the git-topology ones ``safe_commit`` itself applies
    (``git_toplevel``, then ``is_worktree_of``, which compares git common
    dirs and so holds whatever form a worktree's ``gitdir:`` pointer takes).
    """
    try:
        toplevel = git_toplevel(start if start is not None else Path.cwd())
    except GitTopologyError:
        return project_root
    if not is_worktree_of(project_root, toplevel):
        return project_root
    return toplevel


def _repository_checkouts(project_root: Path) -> Iterator[Path]:
    """Every checkout ``git worktree list`` reports for the project's repository."""
    for line in _git_lines(project_root, "worktree", "list", "--porcelain") or []:
        if line.startswith(_WORKTREE_LINE_PREFIX):
            yield Path(line[len(_WORKTREE_LINE_PREFIX) :]).resolve()


def _holds_record(checkout: Path, invocation_id: str) -> bool:
    try:
        record: Path = InvocationWriter(checkout).invocation_path(invocation_id)
    except ValueError:
        return False
    return record.is_file()


def locate_op_record_root(project_root: Path, invocation_id: str, *, preferred: Path | None = None) -> Path | None:
    """Return the checkout holding ``kitty-ops/<invocation_id>.jsonl``, or ``None``.

    Looks in ``preferred`` (the invoking checkout) first, then the project
    root, then every other checkout of the repository, so an Op opened in a
    linked worktree, or by an older CLI in the repository root checkout, is found from
    either side. An invalid id is never found.
    """
    seen: set[Path] = set()
    candidates = [path for path in (preferred, project_root) if path is not None]
    for checkout in [*candidates, *_repository_checkouts(project_root)]:
        key = checkout.resolve()
        if key in seen:
            continue
        seen.add(key)
        if _holds_record(checkout, invocation_id):
            return checkout
    return None


@dataclasses.dataclass(frozen=True)
class OpWriteRefusal:
    """Why an Op record may not be written in its checkout (#6564).

    ``reason`` is the guard's answer (``protected branch 'main'``, or why the
    protection configuration could not be read); it never names the
    protected-branch override.
    """

    code: str
    reason: str


def _op_write_refusal_message(refusal: OpWriteRefusal, record_root: Path, *, action: str) -> str:
    """The operator-facing refusal; ``action`` is ``open the Op`` or ``close the Op``.

    It never suggests overriding the protected-branch guard.
    """
    if refusal.code == OP_WRITE_PROTECTED_BRANCH:
        problem = f"its Op record would be written in {record_root} on {refusal.reason}, where the record cannot be committed"
        remedy = "Run the command from a topic branch, or from a worktree whose branch is not protected."
    else:
        problem = f"the branch protection settings for {record_root} cannot be read ({refusal.reason})"
        remedy = "Fix the protection: block in .kittify/config.yaml, then run the command again."
    return f"Refusing to {action}: {problem}. Nothing was written. {remedy}"


class OpWriteRefused(InvocationError):
    """The executor refused to write an Op record before writing anything (#6564)."""

    def __init__(self, refusal: OpWriteRefusal, record_root: Path, *, action: str) -> None:
        self.refusal = refusal
        self.record_root = record_root
        super().__init__(_op_write_refusal_message(refusal, record_root, action=action))
