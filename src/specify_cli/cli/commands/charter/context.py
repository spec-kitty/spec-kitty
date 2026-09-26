"""``spec-kitty charter context`` command (WP06 per-subcommand split)."""

from __future__ import annotations

import json

import typer

from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError

from specify_cli.cli.helpers import git_resolution_failure_message
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import charter_app, console
from specify_cli.cli.commands.charter._common import _emit_error

# Test-patch shim — see ``synthesize.py``.
import specify_cli.cli.commands.charter as _charter_pkg

__all__ = ["context"]


@charter_app.command()
def context(
    action: str | None = typer.Option(
        None,
        "--action",
        help="Workflow action (specify|plan|implement|review)",
    ),
    include: str | None = typer.Option(
        None,
        "--include",
        help=("Fetch selector, e.g. agent-profile:<id>, template:<mission>/<name>, directive:<id>, section:<slug>."),
    ),
    mark_loaded: bool = typer.Option(True, "--mark-loaded/--no-mark-loaded", help="Persist first-load state"),
    mission_type: str | None = typer.Option(
        None,
        "--mission-type",
        help=(
            "Canonical mission type (e.g. documentation|research|plan|software-dev) "
            "for the action doctrine grain. Required when rendering action context "
            "from the repo root — without it, and without a mission's meta.json, "
            "the action grain is typeless and never inherits software-dev (#883)."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "Output JSON. `context_schema_version` stamps the top-level payload "
            "shape (#2787, tracking contract -- not yet frozen). `directives` is "
            "action-scoped; `all_directives` and `project_charter` describe the "
            "project-local charter, while `org_charter` describes imported org "
            "packs."
        ),
    ),
    include_all: bool = typer.Option(
        False,
        "--include-all",
        help=(
            "Escape hatch: materialise the entire reachable closure inline in the "
            "structured (--json) payload instead of the default progressive "
            "disclosure (requires eager, suggests linked). Output is a superset of "
            "the progressive render for the same grain."
        ),
    ),
) -> None:
    """Render charter context for a specific workflow action."""
    from charter.activation.context import (
        build_charter_context,
        build_charter_context_include,
        build_charter_context_json,
    )
    from charter.activation.context_contract import CONTEXT_SCHEMA_VERSION

    from charter.drg import resolve_org_roots
    from specify_cli.doctrine.org_charter_loader import load_org_charter_json_block

    try:
        repo_root = _charter_pkg.find_repo_root()
        # WP07 T034: resolve the configured org doctrine snapshot in the
        # specify_cli layer and pass it as data into the charter layer.
        # ``charter`` must not import ``specify_cli`` (ADR 2026-03-27-1).
        org_roots = [p for p in resolve_org_roots(repo_root) if p.exists()]
        # SPEC-ARCH-002 / T017: the single-path ``org_root`` below stays
        # truncated to ``org_roots[0]`` ONLY for the ``--include`` path
        # (unaffected by this mission's FR-002 fix). ``build_charter_context``
        # / ``build_charter_context_json`` must NOT receive this truncated
        # value — an explicit (already-truncated) ``org_root`` is honoured
        # verbatim by ``_resolve_action_bundle`` and never widens into the
        # full chain (``charter.activation.action_doctrine_bundle._resolve_action_bundle``
        # docstring). Passing ``org_root=None`` through to those two calls
        # instead lets the charter-layer self-resolution walk the FULL
        # declaration-ordered org-pack chain via ``resolve_existing_org_roots``.
        # The separately-computed full ``org_roots`` list below is unchanged
        # and still passed to ``load_org_charter_json_block(org_roots)``.
        org_root = org_roots[0] if org_roots else None
        if include:
            included_text = build_charter_context_include(
                repo_root,
                include,
                action=action,
                org_root=org_root,
            )
            if json_output:
                print(
                    json.dumps(
                        {
                            "result": "success",
                            "success": True,
                            "include": include,
                            "context": included_text,
                            "text": included_text,
                        },
                        indent=2,
                    )
                )
                return
            # Doctrine prose can legitimately carry literal
            # "[build]"/"[ratchet]"/"[folded]" bracket text (e.g. the
            # acceptance-criteria-non-vacuity tactic's own legend). Rich's
            # default markup parser treats "[...]" as a style tag and
            # silently drops it, stripping exactly that legend from the one
            # prescribed fetch command (``--include tactic:<id>``) that
            # renders it. Pass ``markup=False`` so bracketed doctrine text
            # prints verbatim instead of being consumed as a tag.
            console.print(included_text, markup=False)
            return

        if action is None:
            raise TaskCliError("--action is required unless --include is provided.")

        result = build_charter_context(
            repo_root,
            action=action,
            mark_loaded=mark_loaded,
            # T017: pass None, not the truncated single-pack ``org_root`` —
            # see the comment above where ``org_root`` is computed.
            org_root=None,
            mission_type=mission_type,
        )

        if json_output:
            # WP07 T033 + T046: structured JSON payload includes per-artifact
            # provenance and the additive ``org_charter`` block.  The block
            # is loaded in the specify_cli layer (where ``org_charter_loader``
            # may import the optional WP09 module) and passed as data into the
            # charter layer.
            org_charter_block = load_org_charter_json_block(org_roots)
            structured = build_charter_context_json(
                repo_root,
                action=action,
                depth=result.depth,
                # T017: pass None, not the truncated single-pack ``org_root``
                # — see the comment above where ``org_root`` is computed.
                org_root=None,
                org_charter_block=org_charter_block,
                mission_type=mission_type,
                include_all=include_all,
            )
            print(
                json.dumps(
                    {
                        "result": "success",
                        "success": True,
                        "context_schema_version": structured.get("context_schema_version", CONTEXT_SCHEMA_VERSION),
                        "action": result.action,
                        "mode": result.mode,
                        "first_load": result.first_load,
                        "references_count": result.references_count,
                        "context": result.text,
                        "text": result.text,
                        "directives": structured.get("directives", []),
                        "all_directives": structured.get("all_directives", []),
                        "tactics": structured.get("tactics", []),
                        "styleguides": structured.get("styleguides", []),
                        "toolguides": structured.get("toolguides", []),
                        "references": structured.get("references", []),
                        "governance_references": structured.get("governance_references", []),
                        "project_charter": structured.get(
                            "project_charter",
                            # FR-006: kept consistent with the producer
                            # (``charter.activation.context_json._project_charter_json_block``) --
                            # ``present``/``path`` key on the authoritative
                            # ``charter.yaml`` bundle, not the display-only
                            # ``charter.md``.
                            {
                                "present": False,
                                "path": ".kittify/charter/charter.yaml",
                                "charter_md_present": False,
                                "charter_md_path": ".kittify/charter/charter.md",
                            },
                        ),
                        "org_charter": structured.get("org_charter", {"present": False, "packs": []}),
                    },
                    indent=2,
                )
            )
            return

        # FR-007 (#3596, WP02): gate the display header on the resolved mode,
        # not set-membership -- a declared non-fast-path action (e.g.
        # "tasks", "retrospect") now resolves bootstrap too and must get its
        # header, which a static BOOTSTRAP_ACTIONS check would still deny.
        if result.mode == "bootstrap":
            console.print(f"Action: {result.action} ({result.mode})")
        # Same rationale as the ``--include`` path above: the action-scoped
        # context body is also doctrine prose that can carry literal bracket
        # text, so it must not be parsed as Rich markup either.
        console.print(result.text, markup=False)

    except TaskCliError as e:
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except ValueError as e:
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except (NotInsideRepositoryError, GitCommonDirUnavailableError) as e:
        # #4123: a never-`git init`-ed project used to fall into the generic
        # "Unexpected error" branch below with a non-actionable message.
        # Same escape route as dispatch (build_charter_context ->
        # ensure_charter_bundle_fresh), same actionable git-init advice;
        # ``--json`` keeps its parseable envelope via _emit_error.
        _emit_error(
            console,
            json_output=json_output,
            message=git_resolution_failure_message(e, e.path),
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        _emit_error(console, json_output=json_output, message=str(e), unexpected=True)
        raise typer.Exit(code=1) from e
