"""The Python side of the #6193 lock-interop spike (Mission Write API step 3).

The Java harness (``services/mission-status-api/event-log``, ``LockInteropSpikeTest``) drives this peer as a child process to
prove, or refute, that the interim event-log lock of :mod:`kernel.event_log_append` and a Java writer exclude each other, and that
appends from both sides land as whole lines that both readers accept. Every lock and every append here goes through the production
kernel code, never a reimplementation: :func:`kernel.event_log_append.event_log_lock_path`, :func:`~kernel.event_log_append.event_log_lock`,
:func:`~kernel.event_log_append.append_event_log_lines` and :func:`kernel.locks.machine_file_lock`.

Commands (each prints one JSON object on stdout):

- ``lock-path ANCHOR``: the lock file every writer of ANCHOR takes.
- ``try ANCHOR``: one non-blocking attempt on that lock; ``{"acquired": bool}``.
- ``hold ANCHOR --ready R --release S``: take the lock, create R, wait until S exists, release.
- ``contend ANCHOR --sentinel F --rounds N``: N times, take the lock and create F exclusively inside it; a create that finds F
  already present means another holder is inside the critical section at the same time (an overlap).
- ``append LOG --writer W --count N``: N locked appends of one status-event row each; the indexes of refused appends and their
  error codes are reported, not raised.

``contend`` and ``append`` take ``--ready R --start S``: the peer creates R once it is loaded and starts only when S exists, so the
harness can start every writer at the same moment.
- ``render-row --writer W --index I``: the row bytes writer W appends as its I-th row (the byte-identity reference).
- ``read LOG``: read LOG with the Python status reader; the number of lane events and the SHA-256 of the bytes read.

The spike report is ``docs/development/spikes/2026-10-27-lock-interop-spike.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from kernel.event_log_append import EventLogAppendError, append_event_log_lines, event_log_lock, event_log_lock_path
from kernel.locks import LockNotAcquired, machine_file_lock

#: The ULID alphabet (Crockford base32), so every event id passes both readers' ULID checks.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
#: Event ids of different writers never collide while a writer appends fewer rows than this.
_WRITER_STRIDE = 1_000_000
_HOLD_POLL_S = 0.01
_HOLD_TIMEOUT_S = 120.0
#: Long enough that a fair contender never times out under the spike's load; a timeout is a harness error, not evidence.
_CONTEND_TIMEOUT_S = 60.0
_INSIDE_S = 0.002
_JITTER_S = 0.005
_MISSION_ID = "01M5Z69W0NVCDP2P7BXS5TV391"
_MISSION_SLUG = "lock-interop-spike-01M5Z69W"


def event_id(writer: int, index: int) -> str:
    """Return a deterministic ULID-shaped event id, unique per ``(writer, index)``."""
    value = writer * _WRITER_STRIDE + index
    digits = []
    while value:
        value, digit = divmod(value, 32)
        digits.append(_CROCKFORD[digit])
    return "".join(reversed(digits)).rjust(_ULID_LENGTH, "0")


def render_row(writer: int, index: int) -> str:
    """Return writer ``writer``'s ``index``-th row: one lane transition in today's status row shape, no terminator.

    Serialised as ``status.store`` serialises a row (``json.dumps(row, sort_keys=True)``).

    The Java harness renders the same row with the same bytes (``SpikeRows``); the harness compares the two before it trusts either.
    """
    row = {
        "actor": f"lock-interop-{writer}",
        "at": f"2026-10-27T12:00:00.{index:06d}+00:00",
        "event_id": event_id(writer, index),
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "planned",
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "reason": None,
        "review_ref": None,
        "to_lane": "claimed",
        "wp_id": f"WP{writer:02d}",
    }
    return json.dumps(row, sort_keys=True)


def _emit(payload: dict[str, object]) -> int:
    print(json.dumps(payload, sort_keys=True), flush=True)
    return 0


def cmd_lock_path(anchor: Path) -> int:
    return _emit({"lock_path": str(event_log_lock_path(anchor))})


def cmd_try(anchor: Path) -> int:
    try:
        with machine_file_lock(event_log_lock_path(anchor), blocking=False):
            return _emit({"acquired": True})
    except LockNotAcquired:
        return _emit({"acquired": False})


def _wait_for(path: Path, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"{path} did not appear within {timeout_s}s")
        time.sleep(_HOLD_POLL_S)


def cmd_hold(anchor: Path, ready: Path, release: Path) -> int:
    with event_log_lock(anchor):
        ready.touch()
        _wait_for(release, _HOLD_TIMEOUT_S)
    return _emit({"held": True})


def enter_critical_section(sentinel: Path) -> bool:
    """Create ``sentinel`` exclusively and remove it after a short stay; ``False`` when it already existed (an overlap)."""
    try:
        fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    time.sleep(_INSIDE_S)
    os.unlink(sentinel)
    return True


def _barrier(ready: Path | None, start: Path | None) -> None:
    if ready is not None:
        ready.touch()
    if start is not None:
        _wait_for(start, _HOLD_TIMEOUT_S)


def cmd_contend(anchor: Path, sentinel: Path, rounds: int, ready: Path | None = None, start: Path | None = None) -> int:
    _barrier(ready, start)
    overlaps = 0
    for _ in range(rounds):
        with event_log_lock(anchor, timeout_s=_CONTEND_TIMEOUT_S):
            if not enter_critical_section(sentinel):
                overlaps += 1
        time.sleep(random.uniform(0, _JITTER_S))  # noqa: S311 - scheduling jitter, not a secret
    return _emit({"overlaps": overlaps, "rounds": rounds})


def cmd_append(log: Path, writer: int, count: int, ready: Path | None = None, start: Path | None = None) -> int:
    _barrier(ready, start)
    refused: list[int] = []
    codes: set[str] = set()
    for index in range(count):
        try:
            append_event_log_lines(log, [render_row(writer, index)], timeout_s=_CONTEND_TIMEOUT_S)
        except EventLogAppendError as exc:
            # A refusal is an observation (for example a torn tail seen while an unexcluded writer was mid-write), not a harness error.
            refused.append(index)
            codes.add(exc.code)
        time.sleep(random.uniform(0, _JITTER_S))  # noqa: S311 - scheduling jitter, not a secret
    return _emit({"appended": count - len(refused), "codes": sorted(codes), "refused": refused, "writer": writer})


def cmd_read(log: Path) -> int:
    # Imported here: the status reader pulls in the CLI package, which the lock commands do not need.
    from specify_cli.status.store import read_events

    events = read_events(log.parent)
    return _emit({"events": len(events), "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})


def _barrier_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ready", type=Path)
    parser.add_argument("--start", type=Path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lock-path").add_argument("anchor", type=Path)
    sub.add_parser("try").add_argument("anchor", type=Path)
    hold = sub.add_parser("hold")
    hold.add_argument("anchor", type=Path)
    hold.add_argument("--ready", type=Path, required=True)
    hold.add_argument("--release", type=Path, required=True)
    contend = sub.add_parser("contend")
    contend.add_argument("anchor", type=Path)
    contend.add_argument("--sentinel", type=Path, required=True)
    contend.add_argument("--rounds", type=int, required=True)
    _barrier_arguments(contend)
    append = sub.add_parser("append")
    append.add_argument("log", type=Path)
    append.add_argument("--writer", type=int, required=True)
    append.add_argument("--count", type=int, required=True)
    _barrier_arguments(append)
    render = sub.add_parser("render-row")
    render.add_argument("--writer", type=int, required=True)
    render.add_argument("--index", type=int, required=True)
    sub.add_parser("read").add_argument("log", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command: str = args.command
    if command == "lock-path":
        return cmd_lock_path(args.anchor)
    if command == "try":
        return cmd_try(args.anchor)
    if command == "hold":
        return cmd_hold(args.anchor, args.ready, args.release)
    if command == "contend":
        return cmd_contend(args.anchor, args.sentinel, args.rounds, args.ready, args.start)
    if command == "append":
        return cmd_append(args.log, args.writer, args.count, args.ready, args.start)
    if command == "render-row":
        print(render_row(args.writer, args.index), flush=True)
        return 0
    return cmd_read(args.log)


if __name__ == "__main__":
    sys.exit(main())
