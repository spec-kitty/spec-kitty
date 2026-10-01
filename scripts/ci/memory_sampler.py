"""Whole-job peak-memory sampler for CI battery jobs (NFR-005).

Purpose
-------
NFR-005 requires the peak memory of each architectural battery job to stay
below 12 GB on the 16 GB hosted runner, *as recorded in the job log*. The
battery runs several xdist workers, so the figure that matters is the sum
across processes, not one process. This tool records it. It only measures: it
never wraps pytest and it never fails a job.

What is measured, and why (research.md D-07)
--------------------------------------------
A detached background sampler reads ``/proc/meminfo`` every few seconds and
tracks the peak of ``MemTotal - MemAvailable``: the system-wide,
non-reclaimable memory in use. That is the number that decides whether the
OOM killer fires on the VM. Page cache counts as *available*, so the
full-history checkout and the uv cache do not inflate it. The key is called
``peak_rss_bytes`` (the tasks.md contract name), but it is **not** per-process
RSS; it is the peak of ``MemTotal - MemAvailable``.

As a secondary figure, ``stop`` reads the job cgroup's ``memory.peak``
(cgroup v2) when it is readable. Its path comes from ``/proc/self/cgroup``
(``0::/<path>`` -> ``/sys/fs/cgroup/<path>/memory.peak``). ``na`` is a valid
value (cgroup v1, no permission, non-Linux).

Rejected: ``/usr/bin/time -v``. It reports the max RSS of the largest *single*
process, not the sum across xdist workers, and wrapping the pytest command
would break the gate model's command parse and trip the blind-runner guard in
``test_no_duplicate_suite_execution.py``. The sampler therefore runs in its
own workflow steps.

CLI
---
Run from the repository root as a module (stdlib only, so the runner's system
``python3`` is enough before ``uv sync``)::

    python3 -m scripts.ci.memory_sampler start --out PATH [--interval 2.0]
    python3 -m scripts.ci.memory_sampler stop  --out PATH [--warn-gb 10] [--error-gb 12]
    python3 -m scripts.ci.memory_sampler sample --out PATH [--interval 2.0] [--max-samples N]

``--proc-root`` (default ``/proc``) and ``--sys-root`` (default ``/``) exist so
tests can point the sampler at fake trees. ``sample`` is the foreground loop
that ``start`` spawns; it exits 0 on SIGTERM after writing a final state.
``start`` returns at once. ``stop`` always exits 0, even without a prior
``start``, an unreadable meminfo or a corrupt state file: it degrades to a
``::warning::`` annotation. (Only a malformed command line, a wiring typo,
exits 2 through ``argparse``.)

Output contract (WP12 and the evidence file parse this; C-011)
--------------------------------------------------------------
``stop`` prints exactly one report line, keys in this exact order::

    peak_rss_bytes=<int> source=<meminfo|unavailable> baseline_bytes=<int> \
delta_bytes=<int> samples=<int> elapsed_s=<float, 1 decimal> \
cgroup_peak_bytes=<int|na>

``baseline_bytes`` is the first sample (taken when ``start`` ran, before
``uv sync``), ``delta_bytes`` is peak minus baseline, ``elapsed_s`` is the
monotonic time of the last sample since the sampler started.
``source=unavailable`` means ``/proc/meminfo`` never yielded a sample. The key
order is the module constant ``REPORT_KEYS``. If this format changes, WP12's
wiring and the evidence file must change in the same commit.

It then prints, after the report line, zero or one annotation: ``::warning
title=memory sampler::`` at >= 10 GiB, ``::error title=memory sampler::`` at
>= 12 GiB (GiB = 1024**3 bytes; the thresholds are inclusive and the error
replaces the warning). The error is a visible signal, not a job failure. It
also appends one human-readable line to ``$GITHUB_STEP_SUMMARY`` when that
variable is set.

Lifetime model
--------------
``start`` spawns ``python -m scripts.ci.memory_sampler sample`` with
``start_new_session=True`` and stdio on ``DEVNULL``, so the step's shell does
not wait for it. On GitHub-hosted runners a process detached in one step
survives into later steps of the same job and the runner reaps orphans at job
end. ``stop`` also SIGTERMs it explicitly (pid kept in ``<out>.pid``). State is
written atomically (temporary file + ``os.replace``).

Workflow wiring (WP12)
----------------------
The ``start`` step goes after ``actions/checkout`` (the script lives in the
repository) and before ``setup-uv`` / ``uv sync``, so the baseline reflects the
idle runner::

    - name: Start memory sampler (NFR-005)
      run: python3 -m scripts.ci.memory_sampler start --out "$RUNNER_TEMP/memory-sampler.json"
    # ... uv sync + pytest ...
    - name: Report peak memory (NFR-005)
      if: always()
      run: python3 -m scripts.ci.memory_sampler stop --out "$RUNNER_TEMP/memory-sampler.json"

Only monotonic duration calls are used (the clock-ban gates scan ``scripts/``).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import FrameType
from typing import Any

GIB = 1024**3
_KIB = 1024

DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_WARN_GB = 10.0
DEFAULT_ERROR_GB = 12.0

SOURCE_MEMINFO = "meminfo"
SOURCE_UNAVAILABLE = "unavailable"

#: Exact key order of the ``stop`` report line (the output contract).
REPORT_KEYS: tuple[str, ...] = (
    "peak_rss_bytes",
    "source",
    "baseline_bytes",
    "delta_bytes",
    "samples",
    "elapsed_s",
    "cgroup_peak_bytes",
)

_ANNOTATION_TITLE = "memory sampler"
_CGROUP_UNIFIED_PREFIX = "0::"
_STOP_POLLS = 50
_STOP_POLL_SECONDS = 0.1
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SELF_MODULE = "scripts.ci.memory_sampler"


# ---------------------------------------------------------------------------
# Pure layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemInfo:
    """The two ``/proc/meminfo`` figures the sampler needs, in bytes."""

    total_bytes: int
    available_bytes: int


@dataclass(frozen=True)
class SamplerState:
    """Immutable running summary persisted between samples."""

    baseline_bytes: int
    peak_bytes: int
    samples: int
    elapsed_seconds: float
    source: str
    pid: int


def _meminfo_kib(line: str) -> tuple[str, int] | None:
    """Parse one ``Key:   123 kB`` line into ``(key, kibibytes)``."""
    key, sep, rest = line.partition(":")
    parts = rest.split()
    if not sep or not parts or not parts[0].isdigit():
        return None
    return key.strip(), int(parts[0])


def parse_meminfo(text: str) -> MemInfo | None:
    """Return ``MemTotal``/``MemAvailable`` in bytes, or ``None`` when either is missing.

    ``MemFree`` is never used as a stand-in: it ignores reclaimable cache and
    would overstate usage.
    """
    wanted: dict[str, int] = {}
    for line in text.splitlines():
        parsed = _meminfo_kib(line)
        if parsed is not None and parsed[0] in ("MemTotal", "MemAvailable"):
            wanted[parsed[0]] = parsed[1] * _KIB
    if "MemTotal" not in wanted or "MemAvailable" not in wanted:
        return None
    return MemInfo(total_bytes=wanted["MemTotal"], available_bytes=wanted["MemAvailable"])


def used_bytes(info: MemInfo) -> int:
    """System-wide non-reclaimable memory: ``MemTotal - MemAvailable``."""
    return info.total_bytes - info.available_bytes


def initial_state(pid: int) -> SamplerState:
    """A state with no samples yet (``source=unavailable``)."""
    return SamplerState(
        baseline_bytes=0,
        peak_bytes=0,
        samples=0,
        elapsed_seconds=0.0,
        source=SOURCE_UNAVAILABLE,
        pid=pid,
    )


def update(state: SamplerState, used: int, elapsed: float) -> SamplerState:
    """Fold one sample into ``state``; the first sample becomes the baseline."""
    first = state.samples == 0
    return replace(
        state,
        baseline_bytes=used if first else state.baseline_bytes,
        peak_bytes=used if first else max(state.peak_bytes, used),
        samples=state.samples + 1,
        elapsed_seconds=elapsed,
        source=SOURCE_MEMINFO,
    )


def to_json(state: SamplerState) -> str:
    return json.dumps(asdict(state), sort_keys=True)


def _int_field(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def from_json(text: str) -> SamplerState | None:
    """Parse a persisted state, validating its shape; ``None`` when invalid."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    elapsed = data.get("elapsed_seconds")
    source = data.get("source")
    ints = [_int_field(data, key) for key in ("baseline_bytes", "peak_bytes", "samples", "pid")]
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool):
        return None
    if source not in (SOURCE_MEMINFO, SOURCE_UNAVAILABLE) or any(v is None for v in ints):
        return None
    baseline, peak, samples, pid = (v for v in ints if v is not None)
    return SamplerState(
        baseline_bytes=baseline,
        peak_bytes=peak,
        samples=samples,
        elapsed_seconds=float(elapsed),
        source=source,
        pid=pid,
    )


def cgroup_peak_path(proc_self_cgroup: str, sys_root: Path) -> Path | None:
    """Locate ``memory.peak`` from a ``/proc/self/cgroup`` body (unified ``0::`` line only)."""
    for line in proc_self_cgroup.splitlines():
        if not line.startswith(_CGROUP_UNIFIED_PREFIX):
            continue
        parts = [p for p in line[len(_CGROUP_UNIFIED_PREFIX) :].split("/") if p]
        if ".." in parts:
            return None
        return sys_root.joinpath("sys", "fs", "cgroup", *parts, "memory.peak")
    return None


def read_int_file(path: Path) -> int | None:
    """Read a single integer from ``path``; ``None`` when absent, unreadable or not an integer."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def render_report(state: SamplerState, cgroup_peak: int | None, *, warn_bytes: int, error_bytes: int) -> list[str]:
    """The report line first, then at most one threshold annotation."""
    values = {
        "peak_rss_bytes": str(state.peak_bytes),
        "source": state.source,
        "baseline_bytes": str(state.baseline_bytes),
        "delta_bytes": str(state.peak_bytes - state.baseline_bytes),
        "samples": str(state.samples),
        "elapsed_s": f"{state.elapsed_seconds:.1f}",
        "cgroup_peak_bytes": "na" if cgroup_peak is None else str(cgroup_peak),
    }
    lines = [" ".join(f"{key}={values[key]}" for key in REPORT_KEYS)]
    annotation = _threshold_annotation(state.peak_bytes, warn_bytes, error_bytes)
    return [*lines, annotation] if annotation else lines


def _threshold_annotation(peak: int, warn_bytes: int, error_bytes: int) -> str | None:
    gib = peak / GIB
    if peak >= error_bytes:
        return f"::error title={_ANNOTATION_TITLE}::peak memory {gib:.2f} GiB reached the {error_bytes / GIB:g} GiB NFR-005 limit"
    if peak >= warn_bytes:
        return f"::warning title={_ANNOTATION_TITLE}::peak memory {gib:.2f} GiB is above {warn_bytes / GIB:g} GiB (NFR-005 limit {error_bytes / GIB:g} GiB)"
    return None


def summary_line(state: SamplerState, cgroup_peak: int | None) -> str:
    """One human-readable line for ``$GITHUB_STEP_SUMMARY``."""
    cgroup = "n/a" if cgroup_peak is None else f"{cgroup_peak / GIB:.2f} GiB"
    return (
        f"Memory sampler (NFR-005): peak {state.peak_bytes / GIB:.2f} GiB "
        f"(MemTotal - MemAvailable), baseline {state.baseline_bytes / GIB:.2f} GiB, "
        f"{state.samples} samples over {state.elapsed_seconds:.1f}s, cgroup peak {cgroup}"
    )


# ---------------------------------------------------------------------------
# Edge layer
# ---------------------------------------------------------------------------


def _warning(message: str) -> str:
    return f"::warning title={_ANNOTATION_TITLE}::{message}"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _pid_path(out: Path) -> Path:
    return out.with_name(out.name + ".pid")


def _write_atomic(path: Path, text: str) -> None:
    """Write ``text`` so readers never see a partial file (tmp file + ``os.replace``)."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _take_sample(state: SamplerState, proc_root: Path, elapsed: float) -> SamplerState:
    text = _read_text(proc_root / "meminfo")
    info = parse_meminfo(text) if text is not None else None
    return state if info is None else update(state, used_bytes(info), elapsed)


def _run_sample(args: argparse.Namespace) -> int:
    out = Path(args.out)
    proc_root = Path(args.proc_root)
    stop_event = threading.Event()

    def _on_term(_signum: int, _frame: FrameType | None) -> None:
        stop_event.set()

    previous = signal.signal(signal.SIGTERM, _on_term)
    try:
        return _sample_loop(args, out, proc_root, stop_event)
    finally:
        # Restore the caller's handler: in-process callers (tests) must not keep ours.
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def _sample_loop(args: argparse.Namespace, out: Path, proc_root: Path, stop_event: threading.Event) -> int:
    origin = time.monotonic()
    state = initial_state(os.getpid())
    taken = 0
    while True:
        state = _take_sample(state, proc_root, time.monotonic() - origin)
        _write_atomic(out, to_json(state))
        taken += 1
        if stop_event.is_set() or (args.max_samples and taken >= args.max_samples):
            return 0
        stop_event.wait(args.interval)


def _run_start(args: argparse.Namespace) -> int:
    out = Path(args.out)
    command = [
        sys.executable,
        "-m",
        _SELF_MODULE,
        "sample",
        "--out",
        str(out),
        "--interval",
        str(args.interval),
        "--proc-root",
        args.proc_root,
    ]
    try:
        child = subprocess.Popen(
            command,
            cwd=_REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _pid_path(out).write_text(str(child.pid), encoding="utf-8")
    except OSError as exc:
        print(_warning(f"could not start the sampler: {exc}"))
        return 0
    print(f"memory_sampler started pid={child.pid} out={out}")
    return 0


def _pid_running(pid: int) -> bool:
    """True while ``pid`` runs; a zombie awaiting its reaper counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    stat = _read_text(Path(f"/proc/{pid}/stat"))
    return stat is None or stat.rsplit(")", 1)[-1].split()[:1] != ["Z"]


def _pid_is_sampler(pid: int) -> bool:
    """False only when ``/proc/<pid>/cmdline`` is readable and is not this sampler.

    Guards against a stale pid file whose pid was reused by an unrelated process. Where
    ``/proc`` offers no answer (non-Linux, vanished pid) the identity cannot be disproved,
    so the caller proceeds as before.
    """
    raw = _read_text(Path(f"/proc/{pid}/cmdline"))
    return raw is None or _SELF_MODULE in raw


def _terminate_sampler(out: Path) -> None:
    """SIGTERM the recorded sampler and wait a bounded number of polls for it to exit."""
    raw = _read_text(_pid_path(out))
    if raw is None or not raw.strip().isdigit():
        return
    pid = int(raw.strip())
    if not _pid_is_sampler(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(_STOP_POLLS):
        if not _pid_running(pid):
            return
        time.sleep(_STOP_POLL_SECONDS)


def _load_state(out: Path) -> SamplerState | None:
    text = _read_text(out)
    return from_json(text) if text is not None else None


def _append_step_summary(line: str) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        print(_warning(f"could not write the step summary: {exc}"))


def _run_stop(args: argparse.Namespace) -> int:
    out = Path(args.out)
    proc_root = Path(args.proc_root)
    _terminate_sampler(out)
    state = _load_state(out)
    if state is None:
        print(_warning(f"no usable sampler state at {out}; was `start` run?"))
        state = initial_state(0)
    else:
        state = _take_sample(state, proc_root, state.elapsed_seconds)
        if state.source == SOURCE_UNAVAILABLE:
            print(_warning("no /proc/meminfo sample was recorded; peak memory is unavailable"))
    cgroup_text = _read_text(proc_root / "self" / "cgroup")
    cgroup_file = cgroup_peak_path(cgroup_text, Path(args.sys_root)) if cgroup_text else None
    cgroup_peak = read_int_file(cgroup_file) if cgroup_file else None
    for line in render_report(
        state,
        cgroup_peak,
        warn_bytes=int(args.warn_gb * GIB),
        error_bytes=int(args.error_gb * GIB),
    ):
        print(line)
    _append_step_summary(summary_line(state, cgroup_peak))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=_SELF_MODULE, description="CI job peak-memory sampler (NFR-005).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sample", "start", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--out", required=True, help="state file path")
        cmd.add_argument("--proc-root", default="/proc")
        cmd.add_argument("--sys-root", default="/")
        if name != "stop":
            cmd.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
        if name == "sample":
            cmd.add_argument("--max-samples", type=int, default=0, help="0 = until SIGTERM")
        if name == "stop":
            cmd.add_argument("--warn-gb", type=float, default=DEFAULT_WARN_GB)
            cmd.add_argument("--error-gb", type=float, default=DEFAULT_ERROR_GB)
    return parser


_COMMANDS = {"sample": _run_sample, "start": _run_start, "stop": _run_stop}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Measurement never fails a job: every runtime failure becomes a warning, exit 0."""
    args = _build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except Exception as exc:  # measurement must never turn a green job red
        print(_warning(f"{args.command} failed: {exc!r}"))
        return 0


if __name__ == "__main__":
    sys.exit(main())
