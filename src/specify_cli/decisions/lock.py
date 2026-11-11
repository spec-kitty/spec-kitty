"""The decisions lock: one owner for its path, its waits and its refusal (#6763).

Every holder of the decisions lock goes through this module: the decision
write path (``decisions/service.py``: open, resolve, defer, cancel), the
reconciler (``doctor decisions --repair`` and its coordination-only ledger
copy), an owned ``next``'s ordered commit and ``agent decision
repair-runtime-lock``. None of them takes ``kernel.locks.machine_file_lock`` on
the sidecar itself, and none of them builds its own timeout message.

The refusal contract
--------------------
A wait that runs out raises :class:`~specify_cli.decisions.models.DecisionError`
built by :func:`lock_timeout_error`, and only that:

* **code** -- ``DECISION_LOCK_TIMEOUT`` (:attr:`DecisionErrorCode.LOCK_TIMEOUT`,
  orchestrator-api contract 1.19.0);
* **message** -- names the wait and the lock file, says another decision
  command holds it, that nothing was written under this lock, and to retry
  ("under this lock" keeps it true for an owned ``next``, whose advancement is
  already recorded before the commit takes the lock);
* **details** -- ``decision_id``, ``mission_slug``, ``lock_path`` and
  ``timeout_seconds`` (the orchestrator-api ``data`` keys, unchanged);
* **retryability** -- always retryable: the critical section never ran, so the
  same call can be made again. The code itself is the retryability signal;
  no envelope carries a separate ``retryable`` flag (adding one would change
  the orchestrator-api contract). :func:`is_lock_timeout` is the one predicate a
  caller uses to recognise it; a caller renders it in its own envelope and lets
  every other :class:`DecisionError` propagate unchanged.

Only the ACQUIRE is translated. An exception raised inside the held section
propagates as it is.

Lock order
----------
One global order, and no path inverts it::

    anchor lock (event log)     <- cross-checkout serialization (#6765)
      ledger-dir sidecar lock   <- in-ledger repair exclusion (#4848, #5925, #6628)
        Mission status lock     <- taken by ``emit`` inside the critical section

Writers take both locks (:func:`decisions_write_locks`); the reconciler, the
owned ``next`` commit and ``repair-runtime-lock`` take only the sidecar
(:func:`decisions_lock`), so nothing can hold the sidecar and then wait for the
anchor.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from kernel.event_log_append import EventLogLockTimeoutError, event_log_lock, event_log_lock_path
from kernel.locks import LockAcquireTimeout, machine_file_lock
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import DecisionError, DecisionErrorCode

#: ``lock_timeout_error`` and ``anchor_lock_path`` are this module's own building
#: blocks (every refusal is raised from here), so they stay out of the export list;
#: the tests import them to pin the contract.
__all__ = [
    "ACQUIRE_TIMEOUT_S",
    "LOCK_FILENAME",
    "OPEN_WAIT_S",
    "RETRY_REMEDY",
    "decisions_lock",
    "decisions_write_locks",
    "is_lock_timeout",
    "lock_path",
]

#: The sidecar lock-only file guarding the decisions index RMW. Never the
#: payload path (``index.json`` itself): ``kernel.locks`` G1 wants a DEDICATED
#: lock-only path.
LOCK_FILENAME = "index.json.lock"

#: #7498: the clone-local exclusion that keeps the lock out of ``git status`` in
#: every checkout role. It lives in the COMMON-dir ``info/exclude`` (git honours
#: it for the repository root checkout and every linked worktree, and it is never
#: committed); ``**/`` matches any monorepo depth, like
#: ``coordination.coherence.is_decisions_runtime_lock``'s ``(?:^|/)`` anchor.
_EXCLUDE_PATTERN = f"**/kitty-specs/*/decisions/{LOCK_FILENAME}"

#: Bounded wait matching the NFR-002 10 s hold ceiling, used by every holder
#: except an open: a stuck holder fails loudly with :func:`lock_timeout_error`
#: rather than hanging the caller. Read at call time (``_lock.ACQUIRE_TIMEOUT_S``)
#: so a test can pin it for every holder at once.
ACQUIRE_TIMEOUT_S: float | None = 10.0

#: The refusal's closing remedy. A caller whose retry is unsafe (an owned
#: ``next`` whose advancement is already recorded) strips it and states its own.
RETRY_REMEDY = "; retry the command."

#: #4848 (operator ruling): an open waits WITHOUT a bound -- the same unbounded
#: wait the Mission status lock uses. The holder of the decisions lock may itself
#: be waiting, without a bound, on the status lock inside its opening append, so
#: a bounded wait would fail an unrelated open of a different decision.
#: Deadlock-free because every path takes the decisions lock before the status
#: lock, never the reverse.
OPEN_WAIT_S: float | None = None


def lock_path(ledger_dir: Path) -> Path:
    """Return the sidecar lock path guarding ``decisions/index.json``.

    ``ledger_dir`` is the PRIMARY-partition dir ``service._ledger_dir`` resolves
    (#4966 AC-D2); every holder passes that same dir, so they all lock the same
    file.
    """
    return Path(_store.decisions_dir(ledger_dir) / LOCK_FILENAME)


def anchor_lock_path(events_path: Path) -> Path:
    """Return the log-anchor lock path that every decision writer of *events_path* takes.

    The sidecar is keyed on the per-checkout LEDGER directory, but the row the
    critical section protects is appended to the Mission EVENT LOG, which on a
    coordination topology lives on another partition. The identity every
    writer shares is the log (#6765). Delegated verbatim to
    :func:`kernel.event_log_append.event_log_lock_path`, the one anchor to
    lock-path contract (#6606 rule 1).
    """
    return event_log_lock_path(events_path)


def lock_timeout_error(
    held_lock: Path,
    *,
    timeout_s: float | None,
    mission_slug: str | None,
    decision_id: str | None,
) -> DecisionError:
    """Build THE decisions-lock refusal (see the module docstring's contract).

    ``mission_slug`` and ``decision_id`` are carried into ``details`` verbatim
    and may be ``None`` (``doctor decisions --repair`` and an owned ``next``
    have no decision id). ``timeout_s`` is ``None`` only for an unbounded wait,
    which cannot time out; the message still renders.
    """
    waited = "an unbounded wait" if timeout_s is None else f"{timeout_s:g}s"
    return DecisionError(
        code=DecisionErrorCode.LOCK_TIMEOUT,
        details={
            "decision_id": decision_id,
            "mission_slug": mission_slug,
            "lock_path": str(held_lock),
            "timeout_seconds": timeout_s,
        },
        message=(
            f"Timed out after {waited} waiting for the decisions lock {str(held_lock)!r}; "
            f"another decision command is holding it. Nothing was written under this lock{RETRY_REMEDY}"
        ),
    )


def is_lock_timeout(exc: BaseException) -> bool:
    """True when *exc* is the retryable decisions-lock refusal, and nothing else."""
    return isinstance(exc, DecisionError) and exc.code is DecisionErrorCode.LOCK_TIMEOUT


def _ensure_runtime_lock_excluded(held_lock: Path) -> None:
    """Make sure git never lists the runtime lock as an untracked change (#7498, FR-008).

    Best effort, and never a refusal: the lock exists BY DESIGN (release truncates,
    never unlinks: kernel ``locks`` G3), and the commit helper's refusal to stage it
    (``git.commit_helpers.safe_commit``) is the guarantee that no branch tracks it.
    An exclude cannot hide a lock some branch already tracks; that one is repaired by
    ``agent decision repair-runtime-lock``.
    """
    from kernel.git_topology import GitTopologyError
    from specify_cli.core.git_ops import exclude_from_git_index

    anchor = next((parent for parent in held_lock.parents if parent.is_dir()), None)
    if anchor is None:
        return
    try:
        # Outside a git repository the helper finds no exclude file and does nothing.
        # One read of ``info/exclude`` per acquire; only a missing line is appended,
        # so a clone is written once (NFR-002).
        exclude_from_git_index(anchor, [_EXCLUDE_PATTERN])
    except (GitTopologyError, OSError):
        return


@contextmanager
def decisions_lock(
    held_lock: Path,
    *,
    timeout_s: float | None,
    mission_slug: str | None,
    decision_id: str | None,
) -> Iterator[None]:
    """Hold the ledger-dir sidecar lock; a timed-out wait raises :func:`lock_timeout_error`.

    ``timeout_s=None`` waits without a bound. A timeout leaves nothing written,
    since the caller's critical section never ran.

    Before the first acquire in a clone, the lock is excluded from git (#7498).
    """
    _ensure_runtime_lock_excluded(held_lock)
    with ExitStack() as stack:
        try:
            stack.enter_context(machine_file_lock(held_lock, blocking=True, timeout_s=timeout_s))
        except LockAcquireTimeout as exc:
            raise lock_timeout_error(held_lock, timeout_s=timeout_s, mission_slug=mission_slug, decision_id=decision_id) from exc
        yield


@contextmanager
def _anchor_lock(events_path: Path, *, timeout_s: float | None, mission_slug: str, decision_id: str | None) -> Iterator[None]:
    """Hold the event-log anchor lock; a timed-out wait raises :func:`lock_timeout_error`.

    Taken through :func:`kernel.event_log_append.event_log_lock`, not a raw file
    lock, so its per-thread re-entrancy applies: a nested ``event_log_lock`` on
    the same log inside the critical section (a status-store append, #6193)
    yields the held lock instead of self-deadlocking.
    """
    with ExitStack() as stack:
        try:
            stack.enter_context(event_log_lock(events_path, timeout_s=timeout_s))
        except EventLogLockTimeoutError as exc:
            raise lock_timeout_error(
                anchor_lock_path(events_path),
                timeout_s=timeout_s,
                mission_slug=mission_slug,
                decision_id=decision_id,
            ) from exc
        yield


@contextmanager
def decisions_write_locks(
    *,
    events_path: Path,
    ledger_dir: Path,
    timeout_s: float | None,
    mission_slug: str,
    decision_id: str | None,
) -> Iterator[None]:
    """Hold both decision-write locks: the log anchor, then the ledger sidecar.

    The caller passes paths it has ALREADY resolved: resolving the log may
    materialize the coordination surface, and a placement refusal must fail
    before any lock is taken and before any write (#5113). ``timeout_s=None``
    waits without a bound on both takes, which is what an open needs.
    """
    with ExitStack() as stack:
        stack.enter_context(_anchor_lock(events_path, timeout_s=timeout_s, mission_slug=mission_slug, decision_id=decision_id))
        stack.enter_context(decisions_lock(lock_path(ledger_dir), timeout_s=timeout_s, mission_slug=mission_slug, decision_id=decision_id))
        yield
