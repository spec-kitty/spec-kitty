"""Architectural gate: nothing we ship tells an agent to start another agent unsandboxed (#6477).

The implement-review skill and its dispatch matrix told the orchestrating agent to
launch Codex with ``--sandbox danger-full-access``, Gemini, Qwen, Copilot and
Kilocode with ``--yolo``, LLxprt with ``--approval-mode=yolo`` and Cursor with
``--force``: unrestricted write and network access the user never chose, and the
opposite of the orchestrator API's own ``BANNED_FLAGS``.

Shipped dispatch examples use each harness's workspace-scoped or approval-keeping
mode. Elevated dispatch is an operator decision documented outside the shipped
surface (``docs/guides/how-to/harnesses/agent-dispatch-permissions.md``), so this
gate scans everything that ships or generates shipped text (``src/`` and the
fetched ``packs/`` trees) and allows exactly one file: the ``BANNED_FLAGS``
definition itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specify_cli.orchestrator_api.envelope import BANNED_FLAGS

# ``corpus``: the scan reads the fetched ``packs/built-in`` tree.
pytestmark = [pytest.mark.architectural, pytest.mark.corpus, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCAN_ROOTS: tuple[str, ...] = ("src", "packs")
_TEXT_SUFFIXES: frozenset[str] = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".ps1", ".j2", ".jinja"})
_SKIPPED_DIR_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", "node_modules"})

#: The ban-list definition is the one place the flags may be spelled out.
_ALLOWED_FILES: frozenset[str] = frozenset({"src/specify_cli/orchestrator_api/envelope.py"})

# Flags that switch a harness's sandbox or approvals off wherever they appear.
_ANYWHERE: tuple[re.Pattern[str], ...] = (
    *(re.compile(rf"(?<![\w-]){re.escape(flag)}(?![\w-])") for flag in sorted(BANNED_FLAGS)),
    re.compile(r"danger-full-access"),
    re.compile(r"--approval-mode(?:=|\s+)['\"]?yolo\b", re.IGNORECASE),
    re.compile(r"(?<![\w-])--allow-all(?:-tools|-paths|-urls)?(?![\w-])"),
    re.compile(r"dangerously-skip-permissions|dangerously-bypass-approvals"),
    re.compile(r"\bbypassPermissions\b"),
)

# Short or generic flags that are unsafe only on one harness's command line.
_ON_HARNESS_LINE: tuple[re.Pattern[str], ...] = (
    # Cursor: --force/-f auto-approves every command not explicitly denied.
    re.compile(r"\bcursor(?:-agent| agent)\b[^\n]*\s(?:--force|-f)(?![\w-])"),
    # Kilo Code: --auto/-a disables every permission prompt.
    re.compile(r"\bkilo(?:code)?\b[^\n]*\s(?:--auto|-a)(?![\w-])"),
    # Gemini CLI family: -y is the short spelling of --yolo.
    re.compile(r"\b(?:gemini|qwen|llxprt)\b[^\n]*\s-y(?![\w-])"),
)


def dangerous_dispatch_spans(text: str) -> list[str]:
    """Every sandbox- or approval-disabling flag spelled in ``text``, in order.

    Shell line continuations are joined first, so a flag split onto the next
    line from its harness command is still on that command's line.
    """
    text = re.sub(r"\\\r?\n", " ", text)
    spans: list[tuple[int, str]] = []
    for pattern in (*_ANYWHERE, *_ON_HARNESS_LINE):
        spans.extend((match.start(), match.group(0)) for match in pattern.finditer(text))
    return [found for _, found in sorted(spans)]


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for root_name in _SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in _TEXT_SUFFIXES or not path.is_file():
                continue
            if _SKIPPED_DIR_NAMES.intersection(path.relative_to(REPO_ROOT).parts):
                continue
            files.append(path)
    return files


def test_scan_is_not_vacuous() -> None:
    """Concrete floor: the scan reads the real tree, the skill that motivated it included."""
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _scanned_files()}
    assert len(scanned) > 1000
    assert "src/charter/offering/skills/spec-kitty-implement-review/SKILL.md" in scanned
    assert "src/charter/offering/skills/spec-kitty-implement-review/references/agent-dispatch-matrix.md" in scanned


@pytest.mark.parametrize(
    "text",
    [
        'codex exec --sandbox danger-full-access -C "$W" -',
        "codex exec --dangerously-bypass-approvals-and-sandbox -",
        "codex exec --full-auto -",
        'gemini -p "x" --yolo',
        'gemini -p "x" -y',
        'qwen -p "x" --approval-mode yolo',
        'llxprt -p "x" --approval-mode=yolo',
        'copilot -p "x" --allow-all-tools',
        'copilot -p "x" --allow-all',
        "kilocode -a -j x",
        "kilo run --auto x",
        'timeout 600 cursor agent -p --force "x"',
        'cursor-agent -p -f "x"',
        "claude -p x --dangerously-skip-permissions",
        "claude -p x --permission-mode bypassPermissions",
        'qwen -p "x" --approval-mode\tYOLO',
        'cursor agent -p \\\n  --force "x"',
        "codex exec -s danger-full-access -",
    ],
)
def test_detector_flags_each_unsafe_spelling(text: str) -> None:
    """Self-mutation: every known unsafe spelling is caught."""
    assert dangerous_dispatch_spans(text)


@pytest.mark.parametrize(
    "text",
    [
        'codex exec --sandbox workspace-write --add-dir "$R" -C "$W" -',
        'gemini -p "x" --approval-mode auto_edit --output-format json',
        'qwen -p "x" --approval-mode auto-edit',
        "copilot -p x --allow-tool 'shell(git:*)'",
        "spec-kitty agent tasks move-task WP01 --to approved --force",
        'timeout 600 cursor agent -p --output-format json "x"',
        "git commit -a -m x",
    ],
)
def test_detector_passes_safe_commands(text: str) -> None:
    assert dangerous_dispatch_spans(text) == []


def test_no_shipped_text_dispatches_an_agent_unsandboxed() -> None:
    violations: dict[str, list[str]] = {}
    for path in _scanned_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in _ALLOWED_FILES:
            continue
        found = dangerous_dispatch_spans(path.read_text(encoding="utf-8", errors="replace"))
        if found:
            violations[rel] = found
    assert violations == {}, (
        "Shipped text turns a harness's sandbox or approvals off (#6477). Use the "
        "workspace-scoped mode; elevated dispatch is an operator opt-in documented in "
        f"docs/guides/how-to/harnesses/agent-dispatch-permissions.md: {violations}"
    )


def test_allowed_file_still_defines_the_ban_list() -> None:
    """The one allowlisted file keeps its reason to be allowlisted."""
    (allowed,) = _ALLOWED_FILES
    assert "BANNED_FLAGS" in (REPO_ROOT / allowed).read_text(encoding="utf-8")
