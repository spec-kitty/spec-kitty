"""``spec-kitty regen`` — regenerate the committed generated fixtures (#3447).

Generated assets drift silently: the twelve non-migrated agents' command
baselines and the codex/vibe skill snapshots are rendered from the source
prompt templates under ``packs/built-in/missions/mission-steps/**``. When a
contributor edits a source prompt, the ``twelve-agent-parity`` /
``command_renderer`` gates fail late with no self-service fix (issue #3379).

This command IS that self-service fix. It regenerates every committed generated
fixture from source — byte-identical to a ``PYTEST_UPDATE_SNAPSHOTS=1`` pytest
run, because it reuses the exact same render paths and the shared version pins
(:mod:`specify_cli.skills.render_versions`, FR-005) that the parity tests use.
After WP05 the byte-pinned surface is one canonical command baseline + one
canonical skill snapshot (the 12x12 / codex+vibe grids were retired for
structural invariants), so ``regen`` maintains those canonicals.

Modes (modeled on ``spec-kitty charter pack regenerate-graph``):

- default (write): rewrite every fixture, report how many changed;
- ``--check``: render into memory, byte-compare against the committed
  fixtures, print a unified diff + the exact remediation command, and exit
  non-zero when stale — the fork-PR-safe freshness gate.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

import typer

from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.skills.command_renderer import render as render_skill
from specify_cli.skills.render_versions import (
    FIXTURE_COMMAND_RENDER_VERSION,
    FIXTURE_SKILL_RENDER_VERSION,
)
from specify_cli.template.asset_generator import render_command_template

_REMEDIATION = "Run: spec-kitty regen"

# Source templates + fixture homes, repo-root-relative (resolved at call time).
_TEMPLATES_REL = Path("packs/built-in/missions/mission-steps/software-dev")
_BASELINE_REL = Path("tests/specify_cli/regression/_twelve_agent_baseline")
_SNAPSHOTS_REL = Path("tests/specify_cli/skills/__snapshots__")

# Post-WP05 (#3447, SC-005) the full 12x12 command grid + codex/vibe snapshot
# grid were retired in favour of structural invariants + canonical byte fixtures.
# One canonical per DISTINCT render branch is pinned (adversarial-review finding):
# the markdown branch (claude) AND the TOML branch (gemini) — they diverge in
# asset_generator's serialization — plus the skill branch (codex). `regen`
# maintains exactly those committed canonicals.
_CANONICAL_COMMANDS: tuple[tuple[str, str], ...] = (
    ("claude", "specify"),  # markdown render branch
    ("gemini", "specify"),  # TOML render branch
)
_CANONICAL_SKILL_AGENT = "codex"
_CANONICAL_SKILL_COMMAND = "specify"


@dataclass(frozen=True)
class _Fixture:
    """One rendered fixture: its committed path and freshly rendered content."""

    path: Path
    content: str
    label: str


def _repo_root() -> Path:
    """The repo checkout containing both the source templates and the fixtures.

    Walks up from this module (and falls back to the cwd) until a directory
    holds both the ``software-dev`` mission-step templates (``_TEMPLATES_REL``)
    and ``tests/specify_cli`` — the two trees ``regen`` reads and writes.
    ``regen`` only makes sense inside a dev checkout, so a clear error beats a
    silent wrong-directory write.
    """
    for anchor in (Path(__file__).resolve(), Path.cwd().resolve()):
        for candidate in (anchor, *anchor.parents):
            if (candidate / _TEMPLATES_REL).is_dir() and (
                candidate / "tests" / "specify_cli"
            ).is_dir():
                return candidate
    raise typer.BadParameter(
        "spec-kitty regen must run inside a spec-kitty source checkout "
        f"(could not locate {_TEMPLATES_REL} + tests/specify_cli)."
    )


def _command_fixtures(root: Path) -> list[_Fixture]:
    """The canonical command baselines (mirrors test_twelve_agent_parity WP05)."""
    fixtures: list[_Fixture] = []
    for agent, command in _CANONICAL_COMMANDS:
        template = root / _TEMPLATES_REL / command / "prompt.md"
        if not template.exists():
            continue
        config = AGENT_COMMAND_CONFIG[agent]
        content = render_command_template(
            template_path=template,
            script_type="sh",
            agent_key=agent,
            arg_format=config["arg_format"],
            extension=config["ext"],
            version=FIXTURE_COMMAND_RENDER_VERSION,
        )
        target = root / _BASELINE_REL / agent / f"{command}.{config['ext']}"
        fixtures.append(_Fixture(target, content, f"{agent}/{command}"))
    return fixtures


def _skill_fixtures(root: Path) -> list[_Fixture]:
    """The canonical skill snapshot (mirrors test_command_renderer WP05)."""
    template = root / _TEMPLATES_REL / _CANONICAL_SKILL_COMMAND / "prompt.md"
    if not template.exists():
        return []
    content = render_skill(
        template, _CANONICAL_SKILL_AGENT, FIXTURE_SKILL_RENDER_VERSION
    ).to_skill_md()
    target = (
        root / _SNAPSHOTS_REL / _CANONICAL_SKILL_AGENT
        / f"{_CANONICAL_SKILL_COMMAND}.SKILL.md"
    )
    return [
        _Fixture(target, content, f"{_CANONICAL_SKILL_AGENT}/{_CANONICAL_SKILL_COMMAND}")
    ]


def _all_fixtures(root: Path) -> list[_Fixture]:
    return _command_fixtures(root) + _skill_fixtures(root)


def _stale_diff(fixture: _Fixture) -> str | None:
    """A unified diff when the committed fixture differs from a fresh render.

    ``None`` when the committed file is byte-identical to the render.
    """
    committed = (
        fixture.path.read_text(encoding="utf-8") if fixture.path.exists() else ""
    )
    if committed == fixture.content:
        return None
    diff = difflib.unified_diff(
        committed.splitlines(keepends=True),
        fixture.content.splitlines(keepends=True),
        fromfile=f"a/{fixture.label}",
        tofile=f"b/{fixture.label}",
    )
    return "".join(diff)


def _write(fixtures: list[_Fixture]) -> list[str]:
    """Write every fixture, returning the labels whose content changed."""
    changed: list[str] = []
    for fixture in fixtures:
        if _stale_diff(fixture) is not None:
            changed.append(fixture.label)
        fixture.path.parent.mkdir(parents=True, exist_ok=True)
        fixture.path.write_text(fixture.content, encoding="utf-8")
    return changed


def regen(
    check: bool = typer.Option(
        False,
        "--check",
        help=(
            "Do not write; render into memory and byte-compare against the "
            "committed fixtures. Exit 1 when stale (prints the diff + the exact "
            "regen command), 0 when fresh. This is the fork-PR-safe freshness "
            "gate — a read-only token cannot commit back, so contributors run "
            "`spec-kitty regen` locally and push the result."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON result instead of text.",
    ),
) -> None:
    """Regenerate the committed generated agent-command + skill fixtures (#3447).

    Byte-identical to a ``PYTEST_UPDATE_SNAPSHOTS=1`` pytest run: same render
    paths, same shared version pins (FR-005).
    """
    root = _repo_root()
    fixtures = _all_fixtures(root)
    if not fixtures:
        # Fail closed: an empty render surface must never report "fresh" — that
        # would let a broken template tree pass the --check gate silently.
        raise typer.BadParameter(
            f"regen rendered no fixtures from {root / _TEMPLATES_REL}; the "
            "source template surface looks broken. Refusing to treat it as fresh."
        )

    if check:
        stale = [(f.label, diff) for f in fixtures if (diff := _stale_diff(f))]
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "fresh" if not stale else "stale",
                        "total": len(fixtures),
                        "stale": [label for label, _ in stale],
                        "remediation": _REMEDIATION,
                    }
                )
            )
        elif stale:
            for label, diff in stale:
                typer.echo(f"STALE: {label}")
                typer.echo(diff)
            typer.echo(
                f"\n{len(stale)} of {len(fixtures)} generated fixtures are stale. "
                f"{_REMEDIATION}"
            )
        else:
            typer.echo(f"All {len(fixtures)} generated fixtures are fresh.")
        raise typer.Exit(0 if not stale else 1)

    changed = _write(fixtures)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "status": "written",
                    "total": len(fixtures),
                    "changed": changed,
                }
            )
        )
    else:
        typer.echo(
            f"Regenerated {len(fixtures)} generated fixtures "
            f"({len(changed)} changed)."
        )
    raise typer.Exit(0)
