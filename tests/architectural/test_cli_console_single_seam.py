"""Architectural guardrail: one canonical CLI-output console (GitHub #2632).

All CLI-originated output must route through the single
``specify_cli.cli.console`` seam (``CliConsole`` / ``console`` / ``err_console``)
so that (a) ``--json`` output is plain by construction and (b) colour is a
property of the shared object, not the environment (ADR 2026-07-14-1).

No module under ``src/specify_cli/cli/`` — nor, since #2635, under
``src/specify_cli/retrospective/`` (whose standalone ``retrospect`` app and
``_render_rich`` helper emit CLI output, including a ``--json`` payload) — may
construct a raw ``rich.console.Console(...)``: only the seam module itself, and
only the seam class ``CliConsole(...)`` may be instantiated elsewhere (for the
few deliberately-special consoles, e.g. a fixed ``width=``). Type annotations
(``console: Console``) are fine — they are not constructions.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_ROOT = _REPO_ROOT / "src" / "specify_cli" / "cli"
_RETROSPECTIVE_ROOT = _REPO_ROOT / "src" / "specify_cli" / "retrospective"
_SEAM = _CLI_ROOT / "console.py"

# Rich style/colour tokens recognized as an *opening* markup tag, e.g.
# ``[red]``, ``[bold red]``, or the ``[i]``/``[b]``/``[u]``/``[s]`` shorthand
# Rich also renders. The OPENING regex is deliberately narrow — matching only
# these known tokens is what stops the detector from flagging legitimate
# literal brackets (``[QUERY ...]``, ``[{kind}]``, ``[]`` for an empty JSON
# array) that share the ``[...]`` shape but are not Rich markup.
_RICH_STYLE_TOKENS = (
    "red",
    "green",
    "yellow",
    "blue",
    "cyan",
    "magenta",
    "white",
    "black",
    "dim",
    "bold",
    "italic",
    "underline",
    # Short aliases Rich renders identically to the long forms above; an
    # opener-only ``[i]x`` leaks markup just as ``[italic]x`` would.
    "i",
    "b",
    "u",
    "s",
)
_STYLE_WORD = rf"(?:on\s+)?(?:bright_)?(?:{'|'.join(_RICH_STYLE_TOKENS)})"
_OPENING_MARKUP_RE = re.compile(rf"\[{_STYLE_WORD}(?:\s+{_STYLE_WORD})*\]")
# The CLOSING regex is deliberately BROAD (vocabulary-agnostic): it matches any
# ``[/]`` / ``[/tag]`` closer, so well-formed *paired* markup is caught even when
# the opener uses a token outside the allowlist above (``[blink]...[/blink]``).
# Trade-off: a builtin ``print()`` of a single-segment bracketed absolute path
# (``print("saved to [/tmp]")``) would false-positive here — there are none in
# the tree today; if one is ever added, rephrase or route it through the console
# seam. A second path segment (``[/usr/bin]``) already escapes.
_CLOSING_MARKUP_RE = re.compile(r"\[/\w*\]")


def _raw_console_constructions(path: Path) -> list[str]:
    """Return ``path`` sites that call the bare ``Console(...)`` constructor."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Bare ``Console(...)`` — ``CliConsole(...)`` and ``x.Console(...)`` attr
        # calls are not this exact name, so only the raw rich constructor trips.
        if isinstance(func, ast.Name) and func.id == "Console":
            try:
                where = path.relative_to(_REPO_ROOT)
            except ValueError:
                where = path  # planted/tmp file outside the repo (non-vacuity test)
            hits.append(f"{where}:{node.lineno}")
    return hits


def test_cli_layer_constructs_no_raw_console(tmp_path: Path) -> None:
    offenders: list[str] = []
    for root in (_CLI_ROOT, _RETROSPECTIVE_ROOT):
        for path in sorted(root.rglob("*.py")):
            if path == _SEAM:
                continue  # the seam owns the one CliConsole(Console) definition
            offenders.extend(_raw_console_constructions(path))

    assert not offenders, (
        "CLI modules must route output through the canonical "
        "specify_cli.cli.console seam (console/err_console/CliConsole), not a "
        "raw rich Console(). Offending constructions:\n" + "\n".join(offenders)
    )

    # Controlled incompatible change: the same scanner must reject a raw
    # constructor while accepting the supported seam and annotation forms.
    planted = tmp_path / "planted.py"
    planted.write_text("console = Console()\n", encoding="utf-8")
    assert _raw_console_constructions(planted)

    clean = tmp_path / "clean.py"
    clean.write_text(
        "from specify_cli.cli.console import console\nspecial = CliConsole(width=200)\ndef f(c: Console) -> None: ...\n",
        encoding="utf-8",
    )
    assert not _raw_console_constructions(clean)


def _contains_rich_markup(text: str) -> bool:
    """Return True if ``text`` contains a Rich opening or closing markup tag."""
    return bool(_CLOSING_MARKUP_RE.search(text) or _OPENING_MARKUP_RE.search(text))


def _is_builtin_print_call(node: ast.AST) -> bool:
    """Return True for a bare ``print(...)`` call — not ``console.print(...)``."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"


def _string_literal_parts(call: ast.Call) -> list[str]:
    """Collect literal string text from ``call``'s args: plain strings and the
    literal (non-interpolated) segments of any f-string arguments."""
    parts: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            parts.append(arg.value)
        elif isinstance(arg, ast.JoinedStr):
            for value in arg.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
    return parts


def _markup_print_offenses(path: Path) -> list[str]:
    """Return ``path`` sites where a builtin ``print()`` carries Rich markup."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not _is_builtin_print_call(node):
            continue
        assert isinstance(node, ast.Call)
        for part in _string_literal_parts(node):
            if not _contains_rich_markup(part):
                continue
            try:
                where = path.relative_to(_REPO_ROOT)
            except ValueError:
                where = path  # planted/tmp file outside the repo (unit tests)
            hits.append(f"{where}:{node.lineno}: {part!r}")
            break
    return hits


def test_cli_layer_builtin_print_carries_no_rich_markup() -> None:
    offenders: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        offenders.extend(_markup_print_offenses(path))

    assert not offenders, (
        "Builtin print() must not render Rich markup under src/specify_cli/cli/ "
        "— route this output through the canonical specify_cli.cli.console.console "
        "seam instead (escape any dynamic text with rich.markup.escape). "
        "Offending print() calls:\n" + "\n".join(offenders)
    )


# Sample sources for the detector's own unit tests — exercised directly against
# _markup_print_offenses, independent of the repo scan above.
_FLAGGED_PRINT_SOURCES = (
    'print("[red]x[/red]")\n',
    'print(f"[dim]{value}[/dim]")\n',
    'print("[/]")\n',
    'print("prefix [bold red]warn[/bold red] suffix")\n',
    'print("[i]x")\n',  # opener-only short alias — leaks without the i/b/u/s allowlist
)
_CLEAN_PRINT_SOURCES = (
    "import json\nprint(json.dumps({'a': 1}))\n",
    'print("[spec-kitty guard] applied")\n',
    'print("[c] choose an option")\n',
    'print("plain text")\n',
    'console.print("[red]x[/red]")\n',
    'print(f"[{command_name}] Commits recorded:")\n',
)


def test_markup_print_detector_flags_known_bad_samples(tmp_path: Path) -> None:
    for index, source in enumerate(_FLAGGED_PRINT_SOURCES):
        sample = tmp_path / f"flagged_{index}.py"
        sample.write_text(source, encoding="utf-8")
        assert _markup_print_offenses(sample), source


def test_markup_print_detector_ignores_known_good_samples(tmp_path: Path) -> None:
    for index, source in enumerate(_CLEAN_PRINT_SOURCES):
        sample = tmp_path / f"clean_{index}.py"
        sample.write_text(source, encoding="utf-8")
        assert not _markup_print_offenses(sample), source
