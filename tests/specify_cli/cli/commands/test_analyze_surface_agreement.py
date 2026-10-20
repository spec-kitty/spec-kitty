"""Surface-agreement regression for the ``spec-kitty analyze`` reconciliation (FR-011, #3096).

Background: #3096 reported that the ``spec-kitty.analyze`` skill directed
agents/operators to run a bare top-level ``spec-kitty analyze`` CLI command
that does not exist — only ``spec-kitty agent mission record-analysis`` does.
Investigation for this WP (charter-pack-usage-journey-01KYWWTF WP06) found the
canonical doctrine source (``src/charter/offering/missions/mission-steps/software-dev/
analyze/prompt.md``, which ``command_renderer.py`` renders into every agent's
``SKILL.md``/command file) and the current doc corpus already redirect
exclusively to ``agent mission record-analysis`` — no textual fix was needed.
This test locks that state in as a regression guard, and pins the two-surface
distinction the fold called out explicitly:

* the **working** ``/spec-kitty.analyze`` skill / mission-step (invoked via
  the harness, backed by ``agent mission record-analysis``) — preserved;
* the **absent** top-level ``spec-kitty analyze`` CLI subcommand — must never
  be advertised as if it were real.

Do NOT extend this test to cover the ``analyze``-*expansion* issues
(#849/#851/#853 — readiness-review / product-coherence / full-corpus). Those
are separate scope.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Canonical, currently-instructive surfaces that must never advertise a bare
# ``spec-kitty analyze`` CLI invocation. Historical/planning prose is
# excluded below (it legitimately discusses the bug in retrospect).
_SCAN_ROOTS: tuple[str, ...] = ("src/doctrine", "docs", "README.md", "AGENTS.md")
_EXTENSIONS: tuple[str, ...] = ("*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.json")

# Historical/planning surfaces exempted for the same reason
# tests/architectural/test_no_legacy_terminology.py exempts docs/adr/:
# they are immutable or retrospective records that may legitimately *discuss*
# the now-fixed bug in prose, not live instructions a user would follow.
_EXCLUDED_PATH_FRAGMENTS: tuple[str, ...] = (
    "kitty-specs/",
    "docs/adr/",
    "docs/changelog/",
    "docs/plans/",
    ".worktrees/",
    ".venv/",
    "node_modules/",
    ".git/",
    # Self-exclusion: this test file's own docstring/prose discusses the bug.
    "tests/specify_cli/cli/commands/test_analyze_surface_agreement.py",
)

# A bare CLI invocation: "spec-kitty analyze" with a space (not the dotted
# skill form "spec-kitty.analyze", nor "$spec-kitty.analyze" / "/skill:...").
_BARE_ANALYZE_COMMAND_RE = re.compile(r"spec-kitty\s+analyze\b")

_CANONICAL_PROMPT = Path(
    "packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md"
)
_CANONICAL_COMMAND = "agent mission record-analysis"

# The generated ``analyze`` SKILL.md agents receive is rendered fresh via the
# production ``command_renderer.render`` path rather than read from a committed
# byte snapshot: mission modular-per-package-ci (#3447) retired the per-agent
# snapshot grid down to a single canonical (``codex/specify.SKILL.md``), so this
# #3096 guard renders the surface it checks instead of pinning a fixture that no
# longer exists. codex + vibe are the two skill-family render agents this guard
# historically covered.
_SKILL_RENDER_AGENTS: tuple[str, ...] = ("codex", "vibe")


def _repo_root() -> Path:
    """Resolve the repository root by walking up to a .kittify/ marker."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".kittify").is_dir():
            return parent
    raise RuntimeError("Could not locate repo root (no .kittify/ marker found).")


def _line_is_excluded(line: str) -> bool:
    """True when a ``git grep`` hit line falls under an excluded path fragment."""
    return any(fragment in line for fragment in _EXCLUDED_PATH_FRAGMENTS)


def _grep_bare_analyze_command() -> list[str]:
    """Return every ``<file>:<line>:<content>`` hit for a bare CLI invocation.

    Uses ``git grep`` so ``.gitignore`` exclusions apply automatically. If no
    hits exist, ``git grep`` exits 1 (not an error).
    """
    root = _repo_root()
    cmd = [
        "git",
        "-C",
        str(root),
        "grep",
        "--line-number",
        "--extended-regexp",
        "--ignore-case",
        r"spec-kitty[[:space:]]+analyze\b",
        "--",
        *_SCAN_ROOTS,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise RuntimeError(
            f"git grep failed: exit={result.returncode} stderr={result.stderr!r}"
        )
    return [line for line in result.stdout.splitlines() if not _line_is_excluded(line)]


def test_no_bare_spec_kitty_analyze_cli_reference_in_canonical_surfaces() -> None:
    """No canonical doc/skill/prompt advertises the absent top-level command.

    ``spec-kitty analyze`` (bare, space-separated) is not a real CLI command
    (see ``test_top_level_analyze_command_does_not_exist_on_real_cli`` below).
    The dotted skill-invocation form ``/spec-kitty.analyze`` or
    ``$spec-kitty.analyze`` is fine — that is the working, harness-invoked
    skill surface, which internally calls ``agent mission record-analysis``.
    """
    hits = _grep_bare_analyze_command()
    if hits:
        formatted = "\n  ".join(hits)
        pytest.fail(
            "Found a documented-but-absent bare `spec-kitty analyze` CLI "
            "invocation (#3096). Redirect it to "
            f"`spec-kitty {_CANONICAL_COMMAND}` instead.\n"
            f"Hits ({len(hits)}):\n  {formatted}"
        )


def test_canonical_analyze_prompt_source_names_record_analysis() -> None:
    """The doctrine source (rendered into every agent's skill/command file)

    must positively name the canonical ``agent mission record-analysis``
    command as the persistence step, not merely avoid the bad pattern.
    """
    root = _repo_root()
    text = (root / _CANONICAL_PROMPT).read_text(encoding="utf-8")
    assert _CANONICAL_COMMAND in text, (
        f"{_CANONICAL_PROMPT} must direct users to `spec-kitty {_CANONICAL_COMMAND}` "
        "(the supported, staleness-gated persistence flow)."
    )
    assert not _BARE_ANALYZE_COMMAND_RE.search(text), (
        f"{_CANONICAL_PROMPT} must not advertise a bare `spec-kitty analyze` "
        "CLI invocation — only the dotted skill form or "
        f"`spec-kitty {_CANONICAL_COMMAND}`."
    )


@pytest.mark.parametrize("agent_key", _SKILL_RENDER_AGENTS)
def test_rendered_skill_snapshot_names_record_analysis(agent_key: str) -> None:
    """The actual generated SKILL.md agents receive agrees with the source.

    Rendered fresh through the production ``command_renderer.render`` path —
    the same output ``command_renderer.py`` produces at
    ``.agents/skills/spec-kitty-analyze/SKILL.md`` in a consumer project, the
    surface #3096 was filed against. (Previously read from a committed byte
    snapshot; #3447 retired that snapshot grid, so the guard renders the
    surface it checks rather than pinning a fixture that no longer exists.)
    """
    from specify_cli.skills.command_renderer import render
    from specify_cli.skills.render_versions import FIXTURE_SKILL_RENDER_VERSION

    root = _repo_root()
    template = root / _CANONICAL_PROMPT
    assert template.exists(), f"canonical analyze prompt missing: {template}"
    text = render(template, agent_key, FIXTURE_SKILL_RENDER_VERSION).to_skill_md()
    assert _CANONICAL_COMMAND in text, (
        f"rendered {agent_key} analyze SKILL.md must direct users to "
        f"`spec-kitty {_CANONICAL_COMMAND}`."
    )
    assert not _BARE_ANALYZE_COMMAND_RE.search(text), (
        f"rendered {agent_key} analyze SKILL.md must not advertise a bare "
        "`spec-kitty analyze` CLI invocation."
    )


def test_top_level_analyze_command_does_not_exist_on_real_cli() -> None:
    """Pin the actual (still-absent) CLI surface #3096 was filed against.

    If a future WP mints the fallback alias (research.md Decision 2
    fallback), this test must be updated alongside it — it is not meant to
    forbid the alias forever, only to keep docs and CLI in agreement with
    whatever the real surface is at any given time.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_record_analysis_command_resolves_on_real_cli() -> None:
    """The canonical replacement command is real and reachable from the top-level app."""
    runner = CliRunner()
    result = runner.invoke(app, ["agent", "mission", "record-analysis", "--help"])
    assert result.exit_code == 0
    assert "record-analysis" in result.output
