"""Bytecode-cache doctor sibling: detect a corrupt ``.pyc`` before it bites (#4130).

#4124 shipped ``specify_cli.bytecode_heal``: a stale/corrupt ``__pycache__/*.pyc``
left by an interrupted install is purged and the failed operation retried once,
at CLI startup, at the compat-planner registry load, and at ``spec-kitty
upgrade`` discovery. That heals the failure *when it happens*, with a
full-package recompile penalty and a first-invocation warning.

This sibling adds the detection half: a ``spec-kitty doctor bytecode`` check
that finds a corrupt cache file *before* an ordinary import trips over it.

The dangerous shape is narrower than "any .pyc that looks off". Python's own
import machinery already re-validates a cache's header (magic number, plus
either an mtime+size pair or a source-hash) against the source file on every
import, and transparently recompiles when that check fails -- a bad magic
number or a stale timestamp never bites, because Python never trusts that
cache in the first place. The failure that actually bites (#4124) is the
opposite: the header looks valid -- Python decides to *trust* the cache -- but
the body was truncated by an interrupted write and does not unmarshal to a
code object. This check only flags that combination: header the header check
would pass, body that fails to unmarshal.

Read-only diagnostics. This module never deletes anything -- purging is
``specify_cli.bytecode_heal.purge_package_bytecode``'s job (invoked
automatically at runtime, or manually via the fix hint this check prints).

Auto-discovery seam (T015, see ``_provenance_doctor.py``): ``doctor.py``
imports every ``cli/commands/_*_doctor.py`` sibling and calls ``register(app)``
when the module exposes one. This module never requires an edit to
``doctor.py``.
"""

from __future__ import annotations

import importlib.util
import json
import marshal
import struct
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from specify_cli.bytecode_heal import package_root

from ._doctor_shared import console

__all__ = ["register", "run_bytecode_audit"]

_HEAL_HINT = "delete the flagged file(s) (or the whole __pycache__ dir); Python recompiles from source on next import"

_PYC_HEADER_SIZE = 16
_HASH_BASED_FLAG = 0x1


@dataclass(frozen=True)
class _BytecodeFinding:
    """One ``.pyc`` whose header Python would trust but whose body is corrupt."""

    pyc_path: str
    reason: str


def _cache_header_is_trusted(source_path: Path, header: bytes) -> bool:
    """True when Python's own import machinery would use this cache without recompiling.

    Mirrors ``importlib._bootstrap_external`` cache validation: the magic
    number must match this interpreter, and (for a timestamp-based cache) the
    recorded mtime/size must match the source file. A hash-based cache
    (``flags & 1``) is treated as trusted here -- recomputing the source hash
    duplicates work the import system already does -- and left to the body
    check below. Anything the header check would already reject (bad magic,
    stale timestamp/size, unreadable source) is not this check's concern:
    Python recompiles from source on the next import, so it never bites.
    """
    if len(header) < _PYC_HEADER_SIZE:
        return False
    if header[0:4] != importlib.util.MAGIC_NUMBER:
        return False
    flags = struct.unpack("<I", header[4:8])[0]
    if flags & _HASH_BASED_FLAG:
        return True
    try:
        source_stat = source_path.stat()
    except OSError:
        return False
    recorded_mtime: int = struct.unpack("<I", header[8:12])[0]
    recorded_size: int = struct.unpack("<I", header[12:16])[0]
    return bool(recorded_mtime == (int(source_stat.st_mtime) & 0xFFFFFFFF) and recorded_size == (source_stat.st_size & 0xFFFFFFFF))


def _corrupt_body_reason(body: bytes) -> str | None:
    """Return a finding reason when *body* does not unmarshal to a code object, else None.

    ``marshal.loads`` on arbitrary input is unsafe in general, but this call
    only ever sees the body of a ``.pyc`` under the *locally installed*
    ``specify_cli`` package tree (``_scan_bytecode_cache`` never reads a
    caller-supplied path) -- exactly the file the Python interpreter itself
    would unmarshal on the next ordinary ``import`` of that module. This
    check does not expose new attack surface; it runs the identical operation
    proactively, read-only, to report the failure instead of letting it crash
    an import.
    """
    try:
        # noqa justification: this unmarshals only the body of a .pyc already
        # located under the locally installed specify_cli package tree (see
        # the docstring above) -- the same operation Python's own import
        # machinery performs on this exact file on the next ordinary import.
        payload = marshal.loads(body)  # noqa: S302
    except Exception as exc:  # noqa: BLE001 - marshal raises whatever the garbage bytes provoke
        return f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, types.CodeType):
        return "unmarshalled to a non-code object"
    return None


def _scan_bytecode_cache(root: Path) -> list[_BytecodeFinding]:
    """Read-only scan of every ``*.pyc`` under *root*.

    Flags only a cache file whose header Python's import machinery would
    trust (so it would be used as-is, no recompile) but whose body fails to
    unmarshal into a code object -- the truncated-write shape from #4124.
    Never deletes or mutates anything.
    """
    findings: list[_BytecodeFinding] = []
    if not root.is_dir():
        return findings
    for pyc_path in sorted(root.rglob("*.pyc")):
        try:
            data = pyc_path.read_bytes()
        except OSError:
            continue
        try:
            source_path = Path(importlib.util.source_from_cache(str(pyc_path)))
        except ValueError:
            continue
        if not _cache_header_is_trusted(source_path, data[:_PYC_HEADER_SIZE]):
            continue
        reason = _corrupt_body_reason(data[_PYC_HEADER_SIZE:])
        if reason is not None:
            findings.append(_BytecodeFinding(str(pyc_path.relative_to(root)), reason))
    return findings


def run_bytecode_audit(*, json_output: bool) -> None:
    """Entry point for ``doctor bytecode``.

    Advisory (matches ``doctor provenance``'s informational shape): exits 1
    when a finding is present so CI can gate on it if desired, but this
    command never mutates anything.
    """
    root = package_root()
    if root is None:
        console.print("[red]Error:[/red] could not resolve the installed specify_cli package root")
        raise typer.Exit(1)

    findings = _scan_bytecode_cache(root)

    if json_output:
        payload = {
            "root": str(root),
            "findings": [{"path": f.pyc_path, "reason": f.reason} for f in findings],
            "finding_count": len(findings),
            "heal_hint": _HEAL_HINT,
        }
        console.print_json(json.dumps(payload, indent=2))
        raise typer.Exit(1 if findings else 0)

    if not findings:
        console.print("[green]Bytecode cache[/green]: no corrupt .pyc files found under the installed package.")
        raise typer.Exit(0)

    console.print(f"\n[bold yellow]Corrupt bytecode cache file(s)[/bold yellow] -- {len(findings)} under {root}\n")
    for finding in findings:
        console.print(f"  • [yellow]{finding.pyc_path}[/yellow]: {finding.reason}")
    console.print(f"\n  [dim]Fix:[/dim] {_HEAL_HINT}\n")
    raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Register the ``bytecode`` subcommand onto *app* (doctor.py auto-discovery seam)."""

    @app.command(name="bytecode")
    def bytecode(
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Machine-readable JSON output"),
        ] = False,
    ) -> None:
        """Flag a corrupt installed-package .pyc before it bites (#4124, #4130).

        Reads each .pyc under the installed specify_cli package and flags one
        whose header Python's import machinery would trust (so it would be
        used as-is) but whose body fails to unmarshal into a code object --
        the truncated-write shape that crashed a training machine in #4124.
        A cache Python would already recompile from source (bad magic, stale
        timestamp/size) is not flagged; it never bites. Read-only -- never
        deletes anything.

        Examples:
            spec-kitty doctor bytecode
            spec-kitty doctor bytecode --json
        """
        run_bytecode_audit(json_output=json_output)
