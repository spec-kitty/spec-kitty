"""Guard: every ``spec-kitty`` command path named in shipped doctrine resolves.

Shipped doctrine (``packs/built-in/**``) tells agents which CLI commands to
run. When a command is renamed or retired and the doctrine is not updated,
agents are sent to ``No such command`` (#5204). This test extracts every
``spec-kitty <group> <sub> ...`` path that appears in a code context
(fenced block, inline code span, or a YAML ``examples`` list item) and walks
it through the real Typer/Click command tree.

Only the command path is checked; option names and argument values are
left to each command's own tests.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import click
import pytest
from typer.main import get_command

from tests.doctrine.conftest import REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

BUILT_IN_PACK = REPO_ROOT / "packs" / "built-in"
_SCANNED_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".toml"})

# ``spec-kitty`` followed by one or more lowercase command-like tokens.
_COMMAND_PATTERN = re.compile(r"(?<![\w./-])spec-kitty((?:[ \t]+[a-z][a-z0-9_-]*)+)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"^\s*(```|~~~)")
_YAML_EXAMPLE_ITEM = re.compile(r"""^\s*-\s*["']?spec-kitty\b""")

# Deliberate references to commands that do NOT exist (the doctrine warns
# agents off them). Keyed by (pack-relative path, command path).
_INTENTIONAL_NEGATIVE_REFERENCES: frozenset[tuple[str, str]] = frozenset(
    {
        # "Do not hunt for ... imaginary `spec-kitty agent context update` commands."
        ("missions/mission-steps/software-dev/plan/prompt.md", "agent context update"),
    }
)


def _code_segments(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line_number, segment)`` for every code-context segment."""
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or _YAML_EXAMPLE_ITEM.match(line):
            yield line_number, line
            continue
        for match in _INLINE_CODE.finditer(line):
            yield line_number, match.group(1)


def _unresolved_prefix(root: click.Group, tokens: list[str]) -> str | None:
    """Return the first unresolvable command path, or ``None`` if it resolves."""
    command: click.Command = root
    walked: list[str] = []
    for token in tokens:
        if not isinstance(command, click.Group):
            return None  # reached a leaf command; remaining tokens are arguments
        sub = command.get_command(click.Context(command), token)
        if sub is None:
            return " ".join([*walked, token])
        walked.append(token)
        command = sub
    return None


def _collect_unresolved(root: click.Group) -> list[str]:
    violations: list[str] = []
    for path in sorted(BUILT_IN_PACK.rglob("*")):
        if path.suffix not in _SCANNED_SUFFIXES or not path.is_file():
            continue
        relative = path.relative_to(BUILT_IN_PACK).as_posix()
        for line_number, segment in _code_segments(path.read_text(encoding="utf-8")):
            for match in _COMMAND_PATTERN.finditer(segment):
                unresolved = _unresolved_prefix(root, match.group(1).split())
                if unresolved is None or (relative, unresolved) in _INTENTIONAL_NEGATIVE_REFERENCES:
                    continue
                violations.append(f"{relative}:{line_number}: spec-kitty {unresolved}")
    return violations


@pytest.fixture(scope="module")
def cli_root() -> click.Group:
    from specify_cli import _get_app

    root = get_command(_get_app())
    assert isinstance(root, click.Group)
    return root


def test_builtin_doctrine_names_only_real_cli_commands(cli_root: click.Group) -> None:
    violations = _collect_unresolved(cli_root)
    assert violations == [], "Shipped doctrine names CLI commands that do not exist:\n" + "\n".join(violations)


def test_intentional_negative_references_are_still_present() -> None:
    """Keep the allowlist honest: drop an entry once its text is gone."""
    for relative, command in _INTENTIONAL_NEGATIVE_REFERENCES:
        text = (BUILT_IN_PACK / relative).read_text(encoding="utf-8")
        assert f"spec-kitty {command}" in text, (relative, command)


def test_extractor_flags_a_retired_command(cli_root: click.Group) -> None:
    """The walker reports the first unresolvable token, not the whole line."""
    assert _unresolved_prefix(cli_root, ["agent", "tasks", "transition", "wp01"]) == "agent tasks transition"
    assert _unresolved_prefix(cli_root, ["agent", "tasks", "move-task", "wp01"]) is None


def test_code_segments_cover_fences_inline_spans_and_yaml_examples() -> None:
    text = "\n".join(
        [
            "Prose mentioning spec-kitty workflows is ignored.",
            "Run `spec-kitty agent tasks status` inline.",
            "```bash",
            "spec-kitty merge",
            "```",
            '  - "spec-kitty agent mission create demo"',
        ]
    )
    segments = [segment for _, segment in _code_segments(text)]
    assert segments == [
        "spec-kitty agent tasks status",
        "spec-kitty merge",
        '  - "spec-kitty agent mission create demo"',
    ]
