"""Cross-platform process liveness — the single canonical is-alive check (C-002).

Promoted from ``sync/daemon._is_process_alive`` so ``core`` and ``lanes`` can consult
process liveness without depending on the daemon's socket/HTTPServer machinery
(layering — do not import this from ``sync``). Never raises: NFR-004 requires a
conservative "not provably alive" (False) or "cannot prove dead" (True, AccessDenied)
result for every input, including absent, unparseable, or dead PIDs.

``is_process_alive`` trusts any live PID with no identity check, so on its own it
CANNOT distinguish a still-running claim from an unrelated process that later
reused a recycled PID (FR-004/#2575). PID-reuse-aware callers use the companion
:func:`is_claiming_process_alive`, which compares a persisted process
creation-time baseline before trusting the PID (additive degradation, C-007/D3a):
an absent baseline preserves this function's exact behavior, so no legacy claim
regresses.
"""

from __future__ import annotations

import psutil


def is_process_alive(pid: int) -> bool:
    """Return whether ``pid`` is a currently-running process.

    Conservative and NFR-004-safe: never raises.

    - ``psutil.NoSuchProcess`` (the PID does not exist / has exited) -> ``False``.
    - ``psutil.AccessDenied`` (the PID exists but permissions block inspection) ->
      ``True`` — we cannot prove the process is dead, so we conservatively treat it
      as alive.
    - Any other unexpected exception -> ``False``.
    """
    try:
        proc = psutil.Process(pid)
        return bool(proc.is_running())
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    except Exception:
        return False


def capture_creation_time_baseline(pid: int) -> str | None:
    """Best-effort capture of ``pid``'s process creation-time (C-007 baseline).

    Called at claim-write time (D3b) to co-write an identity baseline alongside
    ``shell_pid``. Returns the creation time as a string suitable for frontmatter
    storage, or ``None`` when it cannot be captured (e.g. the process has already
    exited, or permissions block inspection) — a ``None`` result means the claim
    is written WITHOUT a baseline, which degrades additively to today's live-PID
    trust (D3a) rather than failing the claim. Never raises (NFR-004).
    """
    try:
        return str(psutil.Process(pid).create_time())
    except Exception:
        return None


def is_claiming_process_alive(pid: int, baseline: str | None) -> bool:
    """PID-reuse-aware liveness for a claim (companion to :func:`is_process_alive`).

    Keeps :func:`is_process_alive`'s ``(pid) -> bool`` signature frozen (many
    consumers — review/lock, sync/owner, sync/daemon — depend on it staying
    stable); this companion is consumed only by
    ``stale_detection``'s claim-liveness check.

    Gated on ``baseline`` being present (D3a, additive degradation):

    - ``baseline`` falsy (``None``/empty — legacy claim written before this
      field existed) -> preserve today's exact :func:`is_process_alive`
      behavior. Zero regression for pre-fix claims.
    - ``baseline`` present and matches the live process's ``create_time()`` ->
      alive.
    - ``baseline`` present and does NOT match (the PID was recycled) -> not
      alive.

    Never raises (NFR-004): the same conservative ``AccessDenied`` -> alive
    posture as :func:`is_process_alive` is preserved when a baseline can't be
    verified because permissions block inspection.
    """
    if not baseline:
        return is_process_alive(pid)
    try:
        proc = psutil.Process(pid)
        return str(proc.create_time()) == baseline
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    except Exception:
        return False
