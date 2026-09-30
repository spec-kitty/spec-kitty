#!/usr/bin/env python3
"""Validate a Spec Kitty pull-request body against the PR-body contract.

Internal maintainer asset (never shipped to consumers). The contract is the one
in ``docs/development/how-to/pr-landing.md`` ("PR-body contract"): exactly five
``## `` sections in order (Issue, Change, Tests run, Blast radius, Deferred).

Usage::

    python packs/internal/assets/validate-pr-body.py BODY.md
    gh pr view 123 --json body -q .body | python packs/internal/assets/validate-pr-body.py -
    python packs/internal/assets/validate-pr-body.py BODY.md --verify-discovery --expected-head <sha>

Exit codes: 0 valid, 1 violations (one ``section: problem`` line each), 2 usage error.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

SECTIONS = ("Issue", "Change", "Tests run", "Blast radius", "Deferred")
DOC_SCRIPT_HINT = "use `uv run python -m scripts.docs.<x>`, not the bare path"
_SHELL_OPERATORS = frozenset({"|", "||", "&&", ";", "&", ">", ">>", "<", "(", ")", "`"})
_NAME_ONLY_FLAGS = frozenset({"-l", "--files-with-matches", "--name-only"})
_CLOSES = re.compile(r"\bcloses\s+#\d+", re.IGNORECASE)
_BARE_DOC_SCRIPT = re.compile(r"(?<!\.)(?<![\w/])scripts/docs/[\w.]+\.py\b")
_FENCE = re.compile(r"^\s*(```|~~~)")
_PLACEHOLDER = re.compile(r"^<[^<>]+>")


def _prose_lines(body: str) -> list[tuple[str, bool]]:
    """Return ``(line, in_code_fence)`` for each line, dropping HTML comments."""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    out: list[tuple[str, bool]] = []
    fenced = False
    for line in body.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            out.append((line, True))
            continue
        out.append((line, fenced))
    return out


def split_sections(body: str) -> tuple[list[str], dict[str, list[tuple[str, bool]]]]:
    """Split into level-2 headings (in order) and each section's lines."""
    order: list[str] = []
    content: dict[str, list[tuple[str, bool]]] = {}
    current: str | None = None
    for line, fenced in _prose_lines(body):
        if not fenced and line.startswith("## "):
            current = line[3:].strip()
            order.append(current)
            content.setdefault(current, [])
        elif current is not None:
            content[current].append((line, fenced))
    return order, content


def check_structure(order: list[str]) -> list[str]:
    if tuple(order) == SECTIONS:
        return []
    problems: list[str] = []
    for name in SECTIONS:
        if name not in order:
            problems.append(f"structure: missing section `## {name}`")
    for name in order:
        if name not in SECTIONS:
            problems.append(f"structure: unexpected section `## {name}`")
    if not problems:
        problems.append(f"structure: sections out of order (got {', '.join(order)}; want {', '.join(SECTIONS)})")
    return problems


def check_change(lines: list[tuple[str, bool]]) -> list[str]:
    return [] if any(line.strip() for line, _ in lines) else ["Change: section is empty"]


def check_issue(lines: list[tuple[str, bool]]) -> list[str]:
    text = "\n".join(line for line, _ in lines)
    return [] if _CLOSES.search(text) else ["Issue: missing `closes #<n>` link"]


def _split_command(command: str) -> list[str]:
    """Tokenise like a POSIX shell, keeping operators (`;`, `|`, `>` ...) as their own tokens."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _is_placeholder(text: str) -> bool:
    """True for template placeholders such as `<command>  # <N passed>` left unfilled."""
    return bool(_PLACEHOLDER.match(text.strip().strip("`").strip()))


def _pytest_target_problems(line: str) -> list[str]:
    tokens = _split_command(line.split("  #", 1)[0]) if line.strip() else []
    if "pytest" not in tokens:
        return []
    problems: list[str] = []
    for token in tokens[tokens.index("pytest") + 1 :]:
        if token.startswith("-") or not ("/" in token or "::" in token or token.endswith(".py")):
            continue
        if not token.startswith(("tests/", "docs/")):
            problems.append(f"Tests run: pytest target `{token}` must start with `tests/` or `docs/`")
    return problems


def _command_lines(lines: list[tuple[str, bool]]) -> list[str]:
    commands = [line for line, fenced in lines if fenced and not _FENCE.match(line)]
    for line, fenced in lines:
        if not fenced:
            commands.extend(re.findall(r"`([^`]+)`", line))
    return commands


def check_tests_run(lines: list[tuple[str, bool]]) -> list[str]:
    problems: list[str] = []
    marker = next((i for i, (line, fenced) in enumerate(lines) if not fenced and line.strip() == "Self-review:"), None)
    if marker is None:
        problems.append("Tests run: missing nested `Self-review:` block")
    else:
        entries = [m.group(1) for line, fenced in lines[marker + 1 :] if not fenced and (m := re.match(r"\s*[-*]\s+(\S.*)", line))]
        if not entries:
            problems.append("Tests run: `Self-review:` block has no entries")
        elif all(_is_placeholder(entry) for entry in entries):
            problems.append("Tests run: `Self-review:` block still holds the template placeholder")
    for command in _command_lines(lines):
        if _is_placeholder(command):
            problems.append(f"Tests run: template placeholder left in command `{command.strip()}`")
            continue
        without_comment = command.split("  #", 1)[0]
        if _BARE_DOC_SCRIPT.search(without_comment):
            problems.append(f"Tests run: bare doc-script path in `{command.strip()}` ({DOC_SCRIPT_HINT})")
        try:
            problems.extend(_pytest_target_problems(command))
        except ValueError:
            problems.append(f"Tests run: cannot parse command `{command.strip()}`")
    return problems


def parse_discovery(lines: list[tuple[str, bool]]) -> str | None:
    for line, fenced in lines:
        match = re.match(r"\s*Discovery:\s*(.+?)\s*$", line)
        if match and not fenced:
            return match.group(1).strip().strip("`").strip()
    return None


def parse_files(lines: list[tuple[str, bool]]) -> list[str] | None:
    files: list[str] = []
    seen = False
    for line, fenced in lines:
        if fenced:
            continue
        if re.match(r"\s*Files:\s*$", line):
            seen = True
            continue
        if seen:
            item = re.match(r"\s*[-*]\s+(.+?)\s*$", line)
            if item:
                files.append(item.group(1).strip("`").strip())
            elif line.strip():
                break
    return files if seen else None


def check_blast_radius(lines: list[tuple[str, bool]]) -> list[str]:
    problems: list[str] = []
    discovery = parse_discovery(lines)
    if discovery is None:
        problems.append("Blast radius: missing `Discovery:` line")
    elif _is_placeholder(discovery):
        problems.append(f"Blast radius: `Discovery:` still holds the template placeholder `{discovery}`")
    files = parse_files(lines)
    if files is not None and files and all(_is_placeholder(f) for f in files):
        problems.append("Blast radius: `Files:` still holds the template placeholder")
    elif files is None:
        problems.append("Blast radius: missing `Files:` list")
    elif not files:
        problems.append("Blast radius: `Files:` list is empty")
    return problems


def _run_git(args: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _grep_paths(tokens: list[str], output: str) -> set[str]:
    names_only = any(token in _NAME_ONLY_FLAGS for token in tokens)
    paths: set[str] = set()
    for line in output.splitlines():
        if line.strip():
            paths.add(line if names_only else line.split(":", 1)[0])
    return paths


def verify_discovery(lines: list[tuple[str, bool]], expected_head: str, repo: Path) -> list[str]:
    command = parse_discovery(lines)
    files = parse_files(lines)
    if command is None or files is None:
        return []  # already reported by check_blast_radius
    head = _run_git(["rev-parse", "HEAD"], repo)
    actual = head.stdout.strip()
    if head.returncode != 0 or not actual:
        return ["Blast radius: cannot read `git rev-parse HEAD` in the checkout"]
    if not actual.startswith(expected_head) and actual != expected_head:
        return [f"Blast radius: checkout HEAD {actual} != expected head {expected_head}"]
    try:
        tokens = _split_command(command)
    except ValueError:
        return [f"Blast radius: cannot parse Discovery command `{command}`"]
    if tokens[:2] != ["git", "grep"]:
        return [f"Blast radius: Discovery is not a `git grep` command, refusing to run `{command}`"]
    if any(token in _SHELL_OPERATORS or "$(" in token for token in tokens):
        return [f"Blast radius: Discovery contains shell operators, refusing to run `{command}`"]
    result = _run_git(tokens[1:], repo)
    if result.returncode not in (0, 1):
        return [f"Blast radius: Discovery command failed (exit {result.returncode}): {result.stderr.strip()}"]
    fresh = _grep_paths(tokens, result.stdout)
    recorded = set(files)
    problems = [f"Blast radius: Files lists `{p}` but Discovery does not find it" for p in sorted(recorded - fresh)]
    problems += [f"Blast radius: Discovery finds `{p}` missing from Files" for p in sorted(fresh - recorded)]
    return problems


def validate(body: str, *, expected_head: str | None = None, repo: Path = Path()) -> list[str]:
    order, content = split_sections(body)
    problems = check_structure(order)
    if "Issue" in content:
        problems += check_issue(content["Issue"])
    if "Change" in content:
        problems += check_change(content["Change"])
    if "Tests run" in content:
        problems += check_tests_run(content["Tests run"])
    if "Blast radius" in content:
        problems += check_blast_radius(content["Blast radius"])
        if expected_head is not None:
            problems += verify_discovery(content["Blast radius"], expected_head, repo)
    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a Spec Kitty PR body (five sections: " + ", ".join(SECTIONS) + ").",
        epilog="Exit 0 valid, 1 violations (one `section: problem` line each), 2 usage error.",
    )
    parser.add_argument("body", nargs="?", default="-", help="PR body file, or '-' for stdin (default)")
    parser.add_argument("--verify-discovery", action="store_true", help="re-run the Discovery `git grep` and compare with Files:")
    parser.add_argument("--expected-head", help="commit sha the checkout must be at (required with --verify-discovery)")
    parser.add_argument("--repo", default=".", help="checkout to run Discovery in (default: current directory)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify_discovery and not args.expected_head:
        parser.error("--verify-discovery requires --expected-head <sha>")
    if args.expected_head and not args.verify_discovery:
        parser.error("--expected-head is only meaningful with --verify-discovery")
    try:
        body = sys.stdin.read() if args.body == "-" else Path(args.body).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"validate-pr-body: cannot read body: {exc}", file=sys.stderr)
        return 2
    problems = validate(body, expected_head=args.expected_head if args.verify_discovery else None, repo=Path(args.repo))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
