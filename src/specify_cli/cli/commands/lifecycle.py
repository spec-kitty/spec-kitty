"""Top-level lifecycle command shims.

These commands provide CLI-visible entry points that delegate to the
agent lifecycle implementations.
"""

from __future__ import annotations

import contextlib
import io
import json
import re

import typer
from kernel.errors import GuardedReadError
from mission_runtime import MissionTopology
from specify_cli.cli.console import console as _console

from specify_cli.cli.selector_resolution import resolve_selector
from specify_cli.cli.commands.agent import mission as agent_feature
from specify_cli.core.paths import locate_project_root
from specify_cli.workspace.assert_initialized import (
    SPEC_KITTY_REPO_NOT_INITIALIZED,
    SpecKittyNotInitialized,
    assert_initialized,
)

#: Canonical question sets for the specify/plan widen-enabled interview loops.
#: Each entry is a ``(question_id, question_text)`` pair consumed by
#: ``run_specify_interview`` / ``run_plan_interview``.
SPECIFY_WIDEN_QUESTIONS: list[tuple[str, str]] = [
    ("problem_statement", "What problem does this feature solve?"),
    ("success_criteria", "How will we know this feature is successful?"),
    ("scope_boundaries", "What is explicitly out of scope for this feature?"),
]

PLAN_WIDEN_QUESTIONS: list[tuple[str, str]] = [
    ("approach", "What is the high-level implementation approach?"),
    ("risks", "What are the main risks or unknowns?"),
    ("dependencies", "What upstream dependencies does this plan rely on?"),
]



def _scaffold_next_action(mission_slug: str) -> str:
    return (
        "Open spec_file and replace the scaffold with a complete specification; "
        f"then run `spec-kitty plan --mission {mission_slug}`."
    )


def _with_specify_scaffold_state(payload: dict[str, object], mission_slug: str) -> dict[str, object]:
    """Expose that direct ``spec-kitty specify`` only creates a scaffold."""
    enriched = dict(payload)
    enriched["scaffold_only"] = True
    enriched["spec_state"] = "scaffold_only"
    enriched["next_action"] = _scaffold_next_action(str(enriched.get("mission_slug") or mission_slug))
    enriched["next_step"] = enriched["next_action"]
    return enriched


def _emit_scaffold_only_guidance(mission_slug: str) -> None:
    _console.print("[yellow]Scaffold-only:[/yellow] spec.md was created as a scaffold; no complete spec was authored.")
    _console.print(f"[cyan]Next:[/cyan] {_scaffold_next_action(mission_slug)}")


def _create_mission_for_specify_json(slug: str, mission_type: str | None, topology: MissionTopology | None) -> None:
    """Run mission creation and enrich its single JSON payload for direct specify."""
    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            agent_feature.create_mission(
                mission_slug=slug,
                mission_type=mission_type,
                topology=topology,
                json_output=True,
            )
    except typer.Exit:
        print(capture.getvalue(), end="")
        raise

    output = capture.getvalue()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        print(json.dumps(_with_specify_scaffold_state(payload, slug)))
        return
    print(output, end="")


def _enforce_initialized(*, require_specs: bool = True, json_output: bool = False) -> None:
    """Fail-loud if the cwd's canonical repo is not a Spec Kitty project (FR-032).

    Symmetric with FR-005's no-silent-fallback selector stance: if the
    operator runs ``specify`` / ``plan`` / ``tasks`` from a directory that
    is not an initialized Spec Kitty project, we exit non-zero with an
    actionable message instead of silently writing to a parent or
    sibling repo.
    """
    try:
        assert_initialized(require_specs=require_specs)
    except SpecKittyNotInitialized as exc:
        if json_output:
            print(
                json.dumps(
                    {
                        "error_code": SPEC_KITTY_REPO_NOT_INITIALIZED,
                        "error": str(exc),
                    }
                )
            )
            raise typer.Exit(code=1) from exc
        _console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


class NonAsciiNameError(GuardedReadError):
    """Raised when a ``specify`` mission-name argument is empty or non-ASCII.

    Decision 01M2WJE53KMFBGEJX8JMFT71EE (#4720): a name that is not usable
    ASCII is rejected explicitly and named in the error -- never silently
    stripped/truncated. Covers three named regression scenarios: an
    all-non-Latin-script name (``日本語``, previously slugified to an empty
    string), an accented-Latin name whose diacritics used to be silently
    dropped (``Ünïcödé`` -> ``n-c-d``), and a mixed ASCII/non-Latin name
    whose ASCII fragment used to silently survive (``auth日本`` -> ``auth``).
    Raised directly (not via ``kernel.guarded_read.read_guarded`` -- this is
    operator-input validation, not a file read) so the WP01 global hook
    still renders it uniformly (JSON envelope under ``--json``, a clean
    ``Error: <reason>`` line otherwise), replacing a ``typer.BadParameter``
    that used to force a Typer usage-error exit (2) / stderr-only shape --
    see ``_require_mission_or_exit``'s docstring for the same lesson applied
    elsewhere in this module.
    """


def _reject_if_non_ascii(value: str) -> None:
    """Raise :class:`NonAsciiNameError` when *value* has a non-ASCII code point."""
    if not value.isascii():
        raise NonAsciiNameError(path=value, reason=f"name {value!r} has no usable ASCII characters")


def _slugify_feature_input(value: str) -> str:
    """Normalize a free-form feature name to kebab-case slug text.

    Raises :class:`NonAsciiNameError` for two distinct, deliberately
    differently worded failures (#4720): an empty/whitespace-only name
    ("no name given") versus a name containing non-ASCII characters ("no
    usable ASCII characters") -- never ``typer.BadParameter``, which
    bypasses the WP01 global error hook.
    """
    stripped = value.strip()
    if not stripped:
        raise NonAsciiNameError(path=value, reason="no name given")
    _reject_if_non_ascii(stripped)
    slug = re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")
    if not slug:
        raise NonAsciiNameError(path=value, reason=f"name {value!r} has no usable ASCII characters")
    return slug


def specify(
    mission: str = typer.Argument(..., help="Mission name or slug (e.g., user-authentication)"),
    mission_type: str | None = typer.Option(None, "--mission-type", help="Mission type (e.g., software-dev, research)"),
    mission_type_alias: str | None = typer.Option(None, "--mission", hidden=True, help="(deprecated) Use --mission-type"),
    topology: MissionTopology | None = typer.Option(
        None,
        "--topology",
        help=(
            "Create-time mission shape: single_branch | lanes | coord | "
            "lanes_with_coord. Coordination-bearing shapes (coord, "
            "lanes_with_coord) mint a coordination branch; branch-flat shapes "
            "(single_branch, lanes) do not. Default: context-derived (#2581) — "
            "coord on the primary branch or with --pr-bound, single_branch on a "
            "non-primary feature branch."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON result"),
) -> None:
    """Create a feature scaffold in kitty-specs/."""
    _enforce_initialized(require_specs=False, json_output=json_output)
    slug = _slugify_feature_input(mission)
    resolved_mission_type = mission_type
    if mission_type is not None or mission_type_alias is not None:
        resolved = resolve_selector(
            canonical_value=mission_type,
            canonical_flag="--mission-type",
            alias_value=mission_type_alias,
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
            command_hint="--mission-type <name>",
        )
        resolved_mission_type = resolved.canonical_value
    if json_output:
        _create_mission_for_specify_json(slug, resolved_mission_type, topology)
    else:
        agent_feature.create_mission(
            mission_slug=slug,
            mission_type=resolved_mission_type,
            topology=topology,
            json_output=False,
        )
        _emit_scaffold_only_guidance(slug)

    # FR-002: Wire widen-enabled interview for the specify flow.
    # Only run in interactive (non-JSON) mode so agent/script callers are unaffected.
    if not json_output:
        from specify_cli.missions.plan.specify_interview import run_specify_interview

        repo_root = locate_project_root()
        if repo_root is not None:
            with contextlib.suppress(Exception):
                run_specify_interview(
                    questions=SPECIFY_WIDEN_QUESTIONS,
                    repo_root=repo_root,
                    mission_slug=slug,
                    console=_console,
                )


_MISSION_REQUIRED_MSG = "--mission <slug> is required"


def _require_mission_or_exit(mission: str | None, *, json_output: bool) -> str:
    """Return the normalized mission slug, or emit the no-selector error and Exit(2).

    Mirrors the sibling commands' (accept/next/research) no-selector contract: a
    direct console/JSON message plus ``typer.Exit(2)``. We deliberately avoid
    ``typer.BadParameter`` here — its Rich error-panel rendering is dropped by
    some Typer versions when raised from a command body, so the ``--mission``
    hint never reaches captured output (an FR-008 regression that surfaced once
    the no-selector guard tests were gated into CI). A direct print to the same
    stdout console the sibling commands use is version-robust.
    """
    mission_norm = mission.strip() if isinstance(mission, str) else None
    if not mission_norm:
        if json_output:
            print(json.dumps({"error": _MISSION_REQUIRED_MSG}))
        else:
            _console.print(f"[red]Error:[/red] {_MISSION_REQUIRED_MSG}")
        raise typer.Exit(2)
    return mission_norm


def plan(
    mission: str | None = typer.Option(None, "--mission", help="Mission slug (e.g., 001-user-authentication)"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON result"),
) -> None:
    """Scaffold plan.md for a feature."""
    _enforce_initialized(json_output=json_output)
    mission_slug = _require_mission_or_exit(mission, json_output=json_output)
    agent_feature.setup_plan(feature=mission_slug, json_output=json_output)

    # FR-002: Wire widen-enabled interview for the plan flow.
    # Only run in interactive (non-JSON) mode so agent/script callers are unaffected.
    if not json_output:
        import pathlib

        from specify_cli.missions.plan.plan_interview import run_plan_interview

        repo_root = locate_project_root()
        if repo_root is not None:
            # Resolve the mission slug for the interview seam. BOTH the
            # explicit --mission path and the no-flag autodetect route through
            # the read-path-backed resolver (context._find_feature_directory)
            # and key by the resolved directory name (F-001): the explicit
            # value is an operator HANDLE (full slug, bare mid8, numeric
            # prefix) and passing it through raw persists a raw mission_slug
            # into decisions/index.json via run_plan_interview ->
            # _dm_service.open_decision. An unresolvable/ambiguous handle
            # raises a structured error (C-CTX-4) which the surrounding
            # suppress turns into "skip the interview" — never a
            # wrong-but-plausible slug (setup_plan above has already surfaced
            # the structured error for explicit handles).
            _mission_slug: str | None = None
            with contextlib.suppress(Exception):
                from specify_cli.cli.commands.agent.context import (
                    _find_feature_directory,
                )

                _fd = _find_feature_directory(
                    repo_root,
                    pathlib.Path.cwd(),
                    explicit_mission=mission_slug,
                )
                _mission_slug = _fd.name

            if _mission_slug is not None:
                with contextlib.suppress(Exception):
                    run_plan_interview(
                        questions=PLAN_WIDEN_QUESTIONS,
                        repo_root=repo_root,
                        mission_slug=_mission_slug,
                        console=_console,
                    )



def tasks(
    mission: str | None = typer.Option(None, "--mission", help="Mission slug (e.g., 001-user-authentication)"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON result"),
) -> None:
    """Finalize tasks metadata after task generation."""
    _enforce_initialized(json_output=json_output)
    mission_slug = _require_mission_or_exit(mission, json_output=json_output)
    agent_feature.finalize_tasks(feature=mission_slug, json_output=json_output)


__all__ = ["specify", "plan", "tasks"]
