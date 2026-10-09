"""Architectural parity test: live Typer surface vs CLI reference docs.

Asserts the set of non-hidden command paths discovered by the
``scripts.docs._typer_walker`` matches exactly the set named in
``docs/api/cli-commands.md`` and ``docs/api/agent-subcommands.md``.

If the reference files are not yet present (e.g., a branch where WP07
hasn't run), the test :func:`pytest.skip` s with an explicit reason so
the architectural gate stays green during the documentation refresh.

Mirrors the discovery pattern in
``tests/architectural/test_safety_registry_completeness.py``.

The :func:`test_skill_docs_profile_subcommands_are_registered` guard (FR-018)
additionally scans shipped skill docs for ``spec-kitty agent profile <sub>``
tokens and asserts every ``<sub>`` is a registered command on the ``profile``
Typer app. This locks the ``spk-charter-profile-load`` skill against re-introducing
references to non-existent profile subcommands (FR-017).

The :func:`test_offering_source_snippets_are_registered` guard (FR-011/FR-012)
scans all ``spec-kitty …`` command snippets inside bash fences in the doctrine
SOURCE (``src/charter/offering/skills/**/*.md``,
``src/charter/offering/missions/mission-steps/**/*.md``) and asserts every extracted
command path is a registered Typer surface.  Catches ``HARD`` drift (nonexistent
command/group) introduced by skills and mission-step prompts; does NOT catch
behavioral drift (e.g. a missing required flag whose absence triggers a resolver
error) — those require prompt-level fixes such as T026.

Allow-list: ``_SNIPPET_DRIFT_ALLOWLIST`` (module-level frozenset, starts empty
after the 15 SOURCE fixes landed in WP07).  Any intentional pseudo-command in
docs must be added explicitly with a comment.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from collections.abc import Iterator

import pytest
import typer

# CRITICAL: env flags MUST be set before importing specify_cli so that
# the tracker / issue-search subtree is registered.
# SPEC_KITTY_ENABLE_SAAS_SYNC is now set collection-wide in tests/conftest.py
# pytest_configure (#3213), before any module import, so the gate decision is
# selection-invariant; only the non-gate NO_UPGRADE flag remains per-module.
os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK", "1")

# Ensure scripts/docs is importable (matches tests/docs/conftest.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs._typer_walker import walk  # noqa: E402
from scripts.docs.check_cli_reference_freshness import (  # noqa: E402
    extract_referenced_paths,
)

# ``docs_scoped``: reads the ``docs/api/*.md`` CLI-reference files and
# shipped skill docs, so a docs-only PR could newly-red it — it MUST run on the
# arch pole's docs-only trim.
pytestmark = [pytest.mark.architectural, pytest.mark.docs_scoped]


REFERENCE_PATH = _REPO_ROOT / "docs" / "api" / "cli-commands.md"
AGENT_REFERENCE_PATH = _REPO_ROOT / "docs" / "api" / "agent-subcommands.md"


def _build_live_app() -> typer.Typer:
    """Mirror the discovery pattern used by ``test_safety_registry_completeness``."""
    import specify_cli

    # This reference covers every command, including feature-gated tracker
    # commands. Build a fresh tree so an earlier sync-off import cannot narrow
    # the documented surface. Construction performs no live sync operation.
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
        saved = sys.argv[:]
        sys.argv = ["spec-kitty", "--help"]
        try:
            app = specify_cli._build_app()
        finally:
            sys.argv = saved
    assert isinstance(app, typer.Typer), "specify_cli.app must be a Typer instance"
    return app


# Sentinel marker emitted by ``scripts/docs/build_cli_reference.py``.
# A reference file that does not carry this marker has not yet been
# rebuilt by WP07's generator pass; the parity assertion is meaningless
# in that case, so we skip with an explicit reason.
_WP07_GENERATOR_MARKER = "<!-- BEGIN GENERATED -->"


def _read_or_skip(path: Path, *, wp_label: str) -> str:
    if not path.exists():
        pytest.skip(
            f"{wp_label} not yet run: {path} is missing. "
            "Re-run after the rebuilt CLI reference lands."
        )
    text = path.read_text(encoding="utf-8")
    if _WP07_GENERATOR_MARKER not in text:
        pytest.skip(
            f"{wp_label} not yet run: {path} does not carry the generator "
            "marker. Re-run after the rebuilt CLI reference lands."
        )
    return text


@pytest.fixture(scope="module")
def reference_text() -> str:
    return _read_or_skip(REFERENCE_PATH, wp_label="WP07")


@pytest.fixture(scope="module")
def agent_reference_text() -> str:
    return _read_or_skip(AGENT_REFERENCE_PATH, wp_label="WP07")


def test_reference_paths_are_present_and_generated() -> None:
    """Mechanical not-skipped guard (FR-013 / WP14).

    ``_read_or_skip`` lets ``test_visible_paths_match_reference`` SKIP
    silently if either reference file is missing or ungenerated — a
    half-fix (repointing only one of the two fixtures) reintroduces exactly
    that silent skip. This test fails LOUDLY instead of skipping, so a
    regression in either path is a red, not a quiet green-via-skip.
    """
    missing = [
        str(path)
        for path in (REFERENCE_PATH, AGENT_REFERENCE_PATH)
        if not path.exists()
    ]
    assert not missing, (
        "CLI reference doc(s) missing — the parity gate would silently "
        f"SKIP instead of running: {missing}"
    )
    ungenerated = [
        str(path)
        for path in (REFERENCE_PATH, AGENT_REFERENCE_PATH)
        if _WP07_GENERATOR_MARKER not in path.read_text(encoding="utf-8")
    ]
    assert not ungenerated, (
        "CLI reference doc(s) missing the generator marker "
        f"({_WP07_GENERATOR_MARKER!r}) — regenerate via "
        f"scripts/docs/build_cli_reference.py: {ungenerated}"
    )


@pytest.mark.parametrize("sync_flag", ["0", "1"])
def test_visible_paths_match_reference(
    reference_text: str, agent_reference_text: str, sync_flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every visible (non-hidden) command path must appear in one of the references."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", sync_flag)
    app = _build_live_app()
    assert os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] == sync_flag
    entries = walk(app)
    live_visible = {e.path for e in entries if not e.hidden}

    main_paths = set(extract_referenced_paths(reference_text).keys())
    agent_paths = set(extract_referenced_paths(agent_reference_text).keys())
    referenced = main_paths | agent_paths

    missing = live_visible - referenced
    extra = referenced - {e.path for e in entries}

    assert not missing, (
        "Visible command paths missing from the reference docs:\n"
        + "\n".join(f"  - spec-kitty {' '.join(p)}" for p in sorted(missing))
    )
    assert not extra, (
        "Reference docs name command paths that are not in the live tree:\n"
        + "\n".join(f"  - spec-kitty {' '.join(p)}" for p in sorted(extra))
    )


def test_deprecated_paths_classified(reference_text: str, agent_reference_text: str) -> None:
    """Deprecated visible commands must carry a Deprecated banner in the reference."""
    app = _build_live_app()
    entries = walk(app)
    deprecated = [e for e in entries if e.deprecated and not e.hidden]
    if not deprecated:
        pytest.skip("No deprecated visible commands found in the live tree.")

    main_paths = extract_referenced_paths(reference_text)
    agent_paths = extract_referenced_paths(agent_reference_text)
    combined = {**main_paths, **agent_paths}

    unclassified = [
        e.path
        for e in deprecated
        if combined.get(e.path)
        and not combined[e.path].get("classified_deprecated")
    ]
    assert not unclassified, (
        "Deprecated paths missing Deprecated banner in the reference:\n"
        + "\n".join(f"  - spec-kitty {' '.join(p)}" for p in sorted(unclassified))
    )


def test_retired_check_residual_option_is_absent(reference_text: str) -> None:
    """The unreachable residual flag must not survive in help or docs."""
    from typer.testing import CliRunner

    result = CliRunner().invoke(_build_live_app(), ["review", "--help"])

    assert result.exit_code == 0, result.output
    assert "--check-residual" not in result.output
    assert "--check-residual" not in reference_text


# ---------------------------------------------------------------------------
# FR-018: skill-doc / CLI parity guard for ``agent profile`` subcommands.
# ---------------------------------------------------------------------------

#: Shipped skill docs that name ``spec-kitty agent profile <sub>`` commands.
#: At minimum the spk-charter-profile-load SKILL.md and its mechanics reference (the source template — generated
#: agent copies under ``.claude/`` etc. propagate from it on upgrade, so they
#: are intentionally out of scope here per C-006).
_SKILL_DOCS = (
    _REPO_ROOT / "src" / "charter" / "offering" / "skills" / "spk-charter-profile-load" / "SKILL.md",
    _REPO_ROOT / "src" / "charter" / "offering" / "skills" / "spk-charter-profile-load" / "references" / "profile-load-mechanics.md",
)

#: Match ``spec-kitty agent profile <sub>`` where ``<sub>`` is a command token
#: (lower-case word, optionally hyphenated). The ``spec-kitty`` prefix anchors
#: the match to genuine command invocations, so prose like "load an agent
#: profile on demand" (which lacks the prefix) is never captured.
_PROFILE_CMD_RE = re.compile(
    r"spec-kitty\s+agent\s+profile\s+([a-z][a-z-]*)(?=\s|$|`)"
)


def _registered_profile_commands() -> set[str]:
    """Return the set of command names registered on the ``profile`` Typer app."""
    from specify_cli.cli.commands import profiles_cmd

    return {
        cmd.name
        for cmd in profiles_cmd.app.registered_commands
        if cmd.name is not None
    }


def test_skill_docs_profile_subcommands_are_registered() -> None:
    """Every ``agent profile <sub>`` named in skill docs must be a real command.

    FR-018: fail on any orphan reference to a profile subcommand that is not
    registered on the ``profile`` Typer app. This is the regression lock for
    the FR-017 SKILL.md reconciliation.
    """
    registered = _registered_profile_commands()
    assert registered, "Expected at least one registered profile command."

    orphans: list[tuple[str, str]] = []
    scanned_any = False
    for doc in _SKILL_DOCS:
        assert doc.is_file(), f"skill doc missing: {doc.relative_to(_REPO_ROOT)}"
        scanned_any = True
        text = doc.read_text(encoding="utf-8")
        for match in _PROFILE_CMD_RE.finditer(text):
            sub = match.group(1)
            if sub not in registered:
                rel = doc.relative_to(_REPO_ROOT)
                orphans.append((str(rel), sub))

    assert scanned_any, (
        "No skill docs were scanned — expected at least "
        f"{_SKILL_DOCS[0].relative_to(_REPO_ROOT)} to exist."
    )
    assert not orphans, (
        "Skill docs reference 'spec-kitty agent profile <sub>' commands that "
        "are not registered on the profile Typer app "
        f"(registered: {sorted(registered)}):\n"
        + "\n".join(f"  - {doc}: 'agent profile {sub}'" for doc, sub in sorted(orphans))
    )


# ---------------------------------------------------------------------------
# FR-011/FR-012: doctrine SOURCE command-snippet guard (WP07 / #2007 Focus A).
# ---------------------------------------------------------------------------

#: Source globs for the doctrine SOURCE only.  Generated agent copies under
#: ``.claude/``, ``.amazonq/``, etc. are intentionally excluded — they
#: propagate from SOURCE on ``spec-kitty upgrade`` and must not be separately
#: maintained.
_OFFERING_SOURCE_GLOBS: tuple[str, ...] = (
    "src/charter/offering/skills/**/*.md",
    "src/charter/offering/missions/mission-steps/**/*.md",
)

#: Ratchet allow-list.  Start empty after WP07 lands all 15 SOURCE fixes.
#: Key: ``(relative_path_str, command_path_tuple)``.
#: Add an entry here only when a snippet intentionally uses a pseudo-command
#: (e.g. a tutorial placeholder) and must survive the guard.  Include an
#: inline comment explaining why the bypass is safe.
_SNIPPET_DRIFT_ALLOWLIST: frozenset[tuple[str, tuple[str, ...]]] = frozenset()

#: Regex that captures bash-fenced blocks.
_BASH_FENCE_RE: re.Pattern[str] = re.compile(r"```bash(.*?)```", re.DOTALL)

#: Characters that mark the end of a command path and the start of an
#: argument, placeholder, or flag section.
_PATH_STOP_RE: re.Pattern[str] = re.compile(
    r"^(?:-|<|\[|\{|\$|\.\.\.)|[A-Z\"\']"
)

#: A valid command-path token: lower-case ASCII letter followed by
#: lower-case letters, digits, or hyphens.
_PATH_TOKEN_RE: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9-]*$")

#: Shell metacharacters that terminate the command we are analysing.
_CMD_STOP_CHARS = ("|", "&&", ";", ">")


def _chop_at_shell_stop(line: str) -> str:
    """Return *line* up to but not including the first shell metacharacter."""
    for stop in _CMD_STOP_CHARS:
        idx = line.find(stop)
        if idx != -1:
            line = line[:idx]
    return line


def _extract_command_path(line: str) -> tuple[str, ...] | None:
    """Extract the command-path tuple from a ``spec-kitty …`` invocation line.

    Returns ``None`` when the line does not start with ``spec-kitty`` (after
    stripping common shell prefixes such as ``$ `` or ``uv run ``).

    The path is the maximal prefix of lower-case/hyphen tokens that precede
    the first flag (``-``), placeholder (``<``, ``[``, ``{``, ``$``,
    ``...``), upper-case token, or quoted string.  This is path-level
    validation only — flag correctness is a follow-on tier.
    """
    stripped = line.strip()
    # Strip common shell prefixes that are not part of the command.
    for prefix in ("uv run ", "$ ", "  "):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
    # Skip comment lines (the whole line is a shell comment).
    if stripped.startswith("#"):
        return None
    if not stripped.startswith("spec-kitty"):
        return None
    chopped = _chop_at_shell_stop(stripped)
    tokens = chopped.split()
    if not tokens or tokens[0] != "spec-kitty":
        return None
    path: list[str] = []
    for tok in tokens[1:]:
        if _PATH_STOP_RE.search(tok):
            break
        if _PATH_TOKEN_RE.match(tok):
            path.append(tok)
        else:
            break
    return tuple(path)


def _offering_source_snippets(
    repo_root: Path,
) -> Iterator[tuple[str, tuple[str, ...], str]]:
    """Yield ``(relative_path, command_path, original_line)`` for every
    ``spec-kitty …`` invocation found inside a bash fence in the doctrine
    SOURCE files.
    """
    for glob_pat in _OFFERING_SOURCE_GLOBS:
        for filepath in sorted(repo_root.glob(glob_pat)):
            text = filepath.read_text(encoding="utf-8")
            rel = str(filepath.relative_to(repo_root))
            for fence_match in _BASH_FENCE_RE.finditer(text):
                block = fence_match.group(1)
                for line_match in re.finditer(
                    r"^[ \t]*(spec-kitty[ \t]+[^\n]+)", block, re.MULTILINE
                ):
                    raw = line_match.group(1)
                    path = _extract_command_path(raw)
                    if path is not None:
                        yield rel, path, raw.strip()


def _is_registered_path(
    path: tuple[str, ...],
    registered: set[tuple[str, ...]],
    registered_commands: set[tuple[str, ...]] | None = None,
) -> bool:
    """Return ``True`` when *path* is an exact registered path, or when the
    path starts with a registered leaf command (positional-argument case).

    An empty path (extracted from ``spec-kitty --flag`` with no subcommand
    tokens) is treated as valid since ``--help`` / ``--version`` are valid
    top-level options, not missing commands.

    A group path such as ``('agent', 'context')`` is registered as a group
    entry; a leaf such as ``('agent', 'context', 'resolve')`` as a command.
    Both are valid when matched exactly.

    Positional-argument case: ``spec-kitty agent profile show architect`` →
    extracted path ``('agent', 'profile', 'show', 'architect')``.  The prefix
    ``('agent', 'profile', 'show')`` is a registered leaf command that accepts a
    positional argument; ``architect`` is that argument, not a subcommand.  The
    guard accepts this by checking every strict prefix of *path* against
    *registered_commands*.

    Partial group matches (e.g. ``('doctrine',)`` matching when the snippet says
    ``('doctrine', 'list')``) are NOT accepted — if the prefix is a group, the
    remaining tokens must resolve to a registered subcommand.
    """
    if not path:
        # Empty path → no subcommand tokens, e.g. "spec-kitty --version".
        return True
    if path in registered:
        return True
    # Check positional-argument case: any strict prefix is a leaf command.
    if registered_commands:
        for length in range(len(path) - 1, 0, -1):
            if path[:length] in registered_commands:
                return True
    return False


def test_offering_source_snippets_are_registered() -> None:
    """Every ``spec-kitty …`` snippet in doctrine SOURCE bash fences must name
    a registered Typer command path.

    Finding code: ``unregistered-path`` — the extracted command path is not
    present in the live Typer surface (neither as a leaf command nor as a
    group).

    Limit: this guard detects HARD snippet drift (nonexistent command/group).
    It does NOT detect behavioral drift such as a missing required ``--action``
    flag — those require prompt-level fixes (T026).

    Allow-list: ``_SNIPPET_DRIFT_ALLOWLIST`` (starts empty; add entries with a
    rationale comment when an intentional pseudo-command must survive).
    """
    app = _build_live_app()
    entries = walk(app)
    registered: set[tuple[str, ...]] = {e.path for e in entries}
    # Registered leaf commands (kind="command") that accept positional arguments.
    # A snippet like "spec-kitty agent profile show architect" is valid because
    # "architect" is a positional argument to the "agent profile show" command,
    # not a subcommand token.  We detect this by checking whether any strict
    # prefix of the extracted path is a registered leaf command.
    registered_commands: set[tuple[str, ...]] = {e.path for e in entries if e.kind == "command"}

    failures: list[tuple[str, tuple[str, ...], str]] = []
    for rel, path, raw_line in _offering_source_snippets(_REPO_ROOT):
        if (rel, path) in _SNIPPET_DRIFT_ALLOWLIST:
            continue
        if not _is_registered_path(path, registered, registered_commands):
            failures.append((rel, path, raw_line))

    assert not failures, (
        "Doctrine SOURCE bash fences reference unregistered 'spec-kitty' command paths "
        f"(finding: unregistered-path). {len(failures)} violation(s):\n"
        + "\n".join(
            f"  {rel}  spec-kitty {' '.join(path)!r}  ← {raw_line[:72]}"
            for rel, path, raw_line in sorted(failures)
        )
        + "\n\nFix the SOURCE snippet to point at a real registered surface, or add "
        "an allow-list entry in _SNIPPET_DRIFT_ALLOWLIST with a rationale comment."
    )


# ---------------------------------------------------------------------------
# FR-011 self-test: guard must fail on a planted nonexistent-command snippet.
# ---------------------------------------------------------------------------


def test_guard_rejects_planted_nonexistent_command() -> None:
    """Self-test: ``_extract_command_path`` + ``_is_registered_path`` correctly
    flag a nonexistent command path that would be a HARD drift if present in a
    skill doc.

    This test does NOT scan the file system — it exercises the guard helpers
    in isolation so the self-test is fast and deterministic.
    """
    app = _build_live_app()
    entries = walk(app)
    registered: set[tuple[str, ...]] = {e.path for e in entries}
    registered_commands: set[tuple[str, ...]] = {e.path for e in entries if e.kind == "command"}

    # Plant a nonexistent command path — ``doctrine list`` never exists.
    planted_line = "spec-kitty doctrine list --kind directive"
    path = _extract_command_path(planted_line)
    assert path == ("doctrine", "list"), (
        f"Expected path extraction to yield ('doctrine', 'list'), got {path!r}"
    )
    assert not _is_registered_path(path, registered, registered_commands), (
        "Expected ('doctrine', 'list') to be UNREGISTERED — the guard would "
        "not catch it if this assertion fails.  ('doctrine',) is a group, so "
        "its presence must not cause the guard to accept ('doctrine', 'list')."
    )


def test_guard_accepts_valid_bool_auto_negation() -> None:
    """Self-test: ``--no-mark-loaded`` (Typer auto-negation of ``--mark-loaded``)
    must NOT be misidentified as a path token; the guard must not flag it.

    The path extraction stops at the first ``-`` token, so ``--no-mark-loaded``
    is treated as a flag and excluded from the path.
    """
    line = "spec-kitty charter context --action specify --no-mark-loaded --json"
    path = _extract_command_path(line)
    # Path must be ("charter", "context") — stops before the first "--" flag.
    assert path == ("charter", "context"), (
        f"Expected ('charter', 'context'), got {path!r}.  "
        "The guard must stop tokenising at the first flag."
    )

    app = _build_live_app()
    entries = walk(app)
    registered: set[tuple[str, ...]] = {e.path for e in entries}
    assert _is_registered_path(path, registered), (
        "('charter', 'context') must be registered — guard would false-positive otherwise."
    )
