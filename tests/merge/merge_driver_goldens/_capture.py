"""Capture helper for the merge-driver golden cases.

Produces (and reproduces, deterministically) ``expected_A`` + ``case.json``
for every case under ``tests/merge/merge_driver_goldens/<command>/<case>/``
by running the REGISTERED subprocess entrypoint (``python -m specify_cli
<command> O A B``) exactly as git would invoke a merge driver, against
whatever driver implementation is currently installed.

Never runs on import -- guarded behind ``if __name__ == "__main__":`` at the
bottom of this module; pytest collects everything under ``tests/merge/**``,
and this module has no ``test_*`` functions and a leading underscore, so it
is never collected as a test module.

Usage::

    .venv/bin/python tests/merge/merge_driver_goldens/_capture.py
    git status --porcelain tests/merge/merge_driver_goldens   # expect empty on 2nd run
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_GOLDENS_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _GOLDENS_ROOT.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

_DEFAULT_ARGV_NAMES: tuple[str, str, str] = ("O", "A", "B")
_TMP_PLACEHOLDER = "<TMP>"
_SUBPROCESS_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class GoldenCase:
    """One discovered golden case: its command, case id, and directory."""

    command: str
    case_id: str
    case_dir: Path

    @property
    def full_id(self) -> str:
        return f"{self.command}/{self.case_id}"


@dataclass(frozen=True)
class _Seed:
    """The author-written seed fields of one case's ``case.json``."""

    argv: tuple[str, ...] | None
    absent: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class CaseResult:
    """The captured outcome of replaying one :class:`GoldenCase`."""

    case: GoldenCase
    expected_a: bytes
    exit_code: int
    stdout: str
    stderr: str
    argv_names: tuple[str, str, str]
    absent: tuple[str, ...]
    note: str


def iter_cases() -> list[GoldenCase]:
    """Discover every ``<command>/<case>/`` directory under this package.

    Sorted for deterministic ordering (stable parametrize ids / capture runs).
    """
    cases: list[GoldenCase] = []
    for command_dir in sorted(p for p in _GOLDENS_ROOT.iterdir() if p.is_dir()):
        for case_dir in sorted(p for p in command_dir.iterdir() if p.is_dir()):
            cases.append(GoldenCase(command=command_dir.name, case_id=case_dir.name, case_dir=case_dir))
    return cases


def _read_seed(case_dir: Path) -> _Seed:
    """Read the author-written seed ``case.json`` (``argv``/``absent``/``note`` only).

    Tolerant of a case.json that already carries captured fields (a
    re-capture run) -- only the three seed keys are consulted.
    """
    seed_path = case_dir / "case.json"
    if not seed_path.exists():
        return _Seed(argv=None, absent=(), note="")
    data: dict[str, Any] = json.loads(seed_path.read_text(encoding="utf-8"))
    raw_argv = data.get("argv")
    argv = tuple(str(item) for item in raw_argv) if raw_argv is not None else None
    absent = tuple(str(item) for item in data.get("absent", []))
    note = str(data.get("note", ""))
    return _Seed(argv=argv, absent=absent, note=note)


def _argv_names(seed: _Seed) -> tuple[str, str, str]:
    if seed.argv is None:
        return _DEFAULT_ARGV_NAMES
    if len(seed.argv) != 3:  # pragma: no cover - defensive; every authored case uses 3
        raise ValueError(f"argv override must name exactly 3 paths, got {seed.argv!r}")
    return (seed.argv[0], seed.argv[1], seed.argv[2])


def _materialize_inputs(case_dir: Path, tmp_dir: Path, argv_names: tuple[str, str, str]) -> None:
    """Copy each argv-named input file from *case_dir* into *tmp_dir*, preserving
    any nested relative structure (e.g. ``sub/B``). A name with no source file
    in *case_dir* is left absent in *tmp_dir* (the "absent" case shape)."""
    for name in argv_names:
        source = case_dir / name
        if not source.exists():
            continue
        target = tmp_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def _capture_env(home_dir: Path) -> dict[str, str]:
    """An explicit minimal subprocess environment -- never a copy of ``os.environ``.

    Reading ``PATH`` from the ambient environment is not a mutation; every
    other variable is a fixed, fresh value so the captured golden is
    machine-independent.
    """
    return {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(_SRC_ROOT),
        "HOME": str(home_dir),
        "SPEC_KITTY_HOME": str(home_dir / ".spec-kitty"),
        "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
        "LC_ALL": "C.UTF-8",
    }


def _normalize(text: str, tmp_dir: Path) -> str:
    """Replace every occurrence of *tmp_dir* (and its realpath) with ``<TMP>``.

    Longest-candidate-first, deterministically: on macOS ``tmp_dir.resolve()``
    (``/private/var/...``) is a strict superstring of the unresolved
    ``tmp_dir`` (``/var/...``), and a set's iteration order is not guaranteed
    -- replacing the shorter candidate first would leave a dangling
    ``/private`` + ``<TMP>`` fragment instead of a single clean placeholder.
    """
    normalized = text
    candidates = sorted({str(tmp_dir), str(tmp_dir.resolve())}, key=len, reverse=True)
    for candidate in candidates:
        normalized = normalized.replace(candidate, _TMP_PLACEHOLDER)
    return normalized


def capture_case(case_dir: Path, *, home_dir: Path | None = None) -> CaseResult:
    """Replay one case dir's inputs through the real subprocess entrypoint.

    Returns the :class:`CaseResult` (bytes + exit code + normalized
    stdout/stderr) without writing anything -- callers (this module's
    ``main`` and the golden test's subprocess leg) decide what to do with it.

    *home_dir*, when given, is a caller-owned ``HOME``/``SPEC_KITTY_HOME``
    root REUSED across many calls (perf: a fresh ``HOME`` pays a one-time
    ~12s cold-install bootstrap that seeds every agent's command/skill
    directories; a shared, pre-existing ``HOME`` skips it after the first
    call, dropping each subsequent case to ~1s). When omitted, a private,
    single-use ``HOME`` is created under this case's own temp dir (used by
    ``main()`` for a single ad-hoc case and by any other caller that wants
    full isolation).
    The case's own ``O``/``A``/``B`` working directory is ALWAYS a fresh,
    private temp dir regardless -- only the ``HOME`` root is ever shared.
    """
    case = next(c for c in iter_cases() if c.case_dir == case_dir)
    seed = _read_seed(case_dir)
    argv_names = _argv_names(seed)

    with tempfile.TemporaryDirectory(prefix="merge-driver-golden-") as raw_tmp:
        tmp_dir = Path(raw_tmp)
        _materialize_inputs(case_dir, tmp_dir, argv_names)
        if home_dir is None:
            home_dir = tmp_dir / "_home"
        home_dir.mkdir(parents=True, exist_ok=True)

        argv = [sys.executable, "-m", "specify_cli", case.command, *argv_names]
        result = subprocess.run(
            argv,
            cwd=str(tmp_dir),
            env=_capture_env(home_dir),
            capture_output=True,
            text=False,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

        ours_path = tmp_dir / argv_names[1]
        expected_a = ours_path.read_bytes() if ours_path.exists() else b""

        return CaseResult(
            case=case,
            expected_a=expected_a,
            exit_code=result.returncode,
            stdout=_normalize(result.stdout.decode("utf-8"), tmp_dir),
            stderr=_normalize(result.stderr.decode("utf-8"), tmp_dir),
            argv_names=argv_names,
            absent=seed.absent,
            note=seed.note,
        )


def _write_result(result: CaseResult) -> None:
    case_dir = result.case.case_dir
    (case_dir / "expected_A").write_bytes(result.expected_a)
    payload: dict[str, object] = {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "absent": list(result.absent),
        "note": result.note,
    }
    if result.argv_names != _DEFAULT_ARGV_NAMES:
        payload["argv"] = list(result.argv_names)
    (case_dir / "case.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    cases = iter_cases()
    if not cases:
        raise SystemExit(f"no golden cases discovered under {_GOLDENS_ROOT}")
    # A single shared HOME for the whole run (perf: only the FIRST subprocess
    # call pays the ~12s cold-install bootstrap; every later case reuses the
    # already-seeded HOME at ~1s). Never reused across process invocations of
    # this script -- a fresh run gets a fresh HOME, so the golden output is
    # unaffected by anything an earlier run may have left behind.
    with tempfile.TemporaryDirectory(prefix="merge-driver-golden-home-") as raw_home:
        shared_home = Path(raw_home)
        for case in cases:
            result = capture_case(case.case_dir, home_dir=shared_home)
            _write_result(result)
            print(f"captured {case.full_id}: exit={result.exit_code}")


if __name__ == "__main__":
    main()
