"""Fail-closed source reading and parsing for architectural scanners (#5139).

An AST scanner that swallows a read/decode/parse failure (``except SyntaxError:
continue`` / ``return []``) silently drops the file from its census: the gate
then passes over code it never read. The home-pin gate already bans that shape
locally (SC-013, ``_home_pin_scan.parse_module``); this module is the shared
form for every other scanner, and ``test_scanner_parse_fail_closed.py`` bans a
handler that can swallow a parse failure anywhere else under ``tests/``.

Every helper raises :class:`UnparseableSourceError` — an :class:`AssertionError`,
so a scan failure reads as a gate failure — naming the file and chaining the
underlying :class:`OSError` / :class:`UnicodeDecodeError` / :class:`SyntaxError`.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = [
    "UnparseableSourceError",
    "parse_file",
    "parse_source",
    "qualname_by_line",
    "read_and_parse",
    "read_source",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]


class UnparseableSourceError(AssertionError):
    """A scanner could not read, decode, or parse a source file it must cover."""


def _label(path: Path, display: str | None) -> str:
    if display is not None:
        return display
    try:
        return path.resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def read_source(path: Path, *, display: str | None = None) -> str:
    """Read ``path`` as UTF-8, failing closed on an I/O or decode error."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UnparseableSourceError(f"scanner cannot read {_label(path, display)}: {exc}") from exc


def parse_source(source: str, *, display: str) -> ast.Module:
    """Parse ``source`` (already read from ``display``), failing closed on a syntax error."""
    try:
        return ast.parse(source, filename=display)
    except (SyntaxError, ValueError) as exc:  # ValueError: a NUL byte in the source
        raise UnparseableSourceError(f"scanner cannot parse {display}: {exc}") from exc


def read_and_parse(path: Path, *, display: str | None = None) -> tuple[str, ast.Module]:
    """Read and parse ``path``; return ``(source, tree)``. Fails closed."""
    label = _label(path, display)
    source = read_source(path, display=label)
    return source, parse_source(source, display=label)


def parse_file(path: Path, *, display: str | None = None) -> ast.Module:
    """Read and parse ``path``; return the tree. Fails closed."""
    return read_and_parse(path, display=display)[1]


def qualname_by_line(tree: ast.Module) -> dict[int, str]:
    """Map each line number to its innermost enclosing ``def``/``class`` qualname.

    Scanner ledgers key on the enclosing function rather than a line number so
    unrelated edits above a site do not churn the gate. This is deliberately
    not :func:`specify_cli.contracts.anchoring.enclosing_qualname` (the
    ratchet key-builder): census ledgers such as ``_load_meta_census`` carry
    historical ``(path, qualname)`` rows keyed by exactly this line-span walk
    (``<module>`` for top-level lines), and changing the algorithm would
    silently re-key them.
    """
    out: dict[int, str] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = f"{prefix}.{child.name}" if prefix else child.name
                for lineno in range(child.lineno, (child.end_lineno or child.lineno) + 1):
                    out[lineno] = qual
                walk(child, qual)
            else:
                walk(child, prefix)

    walk(tree, "")
    return out
