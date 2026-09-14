"""``spec-kitty charter interview`` command (WP06 per-subcommand split).

Widen Mode helpers live in :mod:`specify_cli.cli.commands.charter._widen` so
this module stays under the 500-line WP06 budget.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import typer

from specify_cli.decisions.models import OriginFlow as _DmOriginFlow
from specify_cli.decisions.service import DecisionError as _DecisionError
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import charter_app, console
from specify_cli.cli.commands.charter._common import (
    _emit_error,
    _interview_path,
    _parse_csv_option,
    _resolve_actor,
)
from specify_cli.cli.commands.charter._widen import (
    _is_already_widened,
    _prompt_one_question,
    _resolve_dm_terminal,
)

# Patch-compatibility shim: legacy tests patch
# ``specify_cli.cli.commands.charter.<name>`` for ``find_repo_root``,
# ``default_interview``, ``_charter_pkg._dm_service``, ``_get_widen_prereqs_absent``, and
# ``_resolve_dm_terminal``. Looking them up on the package module at call time
# preserves that contract through the WP06 split.
import specify_cli.cli.commands.charter as _charter_pkg

__all__ = ["interview"]


def _promote_interview_selections(repo_root: Path, interview_data: Any) -> list[str]:
    """Append-promote captured interview selections into ``config.activated_<kind>`` (FR-007).

    Only the three roots :class:`~charter.activation.interview.CharterInterview` actually
    captures (directives, tactics, paradigms) are promoted here — a project's
    ``answers.yaml`` may separately carry hand-authored non-root selections
    (e.g. ``selected_styleguides``); those are the config-seeded migration's
    job (``m_unify_charter_activation``, T023), not this per-interview-run
    wiring. Routes through the shared :func:`charter.activation.activation_engine.promote_activations`
    primitive (WP06) — the same append-only, absent-key-built-in-safe seam the
    migration uses — reusing (not duplicating) the WP01 ID-form resolver and
    the default-pack loader via ``m_unify_charter_activation`` (T023's sibling
    consumer).

    Best-effort / non-fatal by contract: the caller wraps this in a broad
    ``except`` so a promotion failure never blocks the interview answers
    already written to disk. Returns human-readable warning strings (empty
    when there is nothing to surface).

    Write target (consolidate-charter-bundle WP02): resolved via
    :func:`charter.activation.pack_manager.resolve_activation_write_target` — a
    migrated project (``config.yaml`` carries a ``charter:`` pointer)
    promotes into ``charter.yaml``; a legacy/un-migrated project promotes
    into ``config.yaml`` directly (unchanged pre-relocation behavior).
    """
    from charter.activation.activation_engine import promote_activations
    from charter.activation.catalog import resolve_doctrine_root
    from charter.activation.kind_vocabulary import UnrepresentableDirectiveIdError
    from charter.activation.pack_manager import resolve_activation_write_target
    from charter.drg import ArtifactKind

    from specify_cli.upgrade.migrations.m_unify_charter_activation import (
        load_default_pack_ids,
        resolve_selected_id_to_stem,
    )

    kind_to_selection: dict[ArtifactKind, list[str]] = {
        ArtifactKind.DIRECTIVE: list(interview_data.selected_directives),
        ArtifactKind.TACTIC: list(interview_data.selected_tactics),
        ArtifactKind.PARADIGM: list(interview_data.selected_paradigms),
    }

    from specify_cli.cli.commands.charter._layer_roots import (
        resolve_layer_roots,
        resolve_org_root_chain,
    )

    doctrine_root = resolve_doctrine_root()
    org_roots = resolve_org_root_chain(repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    promotions: dict[str, list[str]] = {}
    warnings: list[str] = []
    for kind, raw_ids in kind_to_selection.items():
        stems: list[str] = []
        for raw_id in raw_ids:
            try:
                stem = resolve_selected_id_to_stem(
                    kind,
                    raw_id,
                    doctrine_root=doctrine_root,
                    org_roots=org_roots,
                    layer_roots=layer_roots,
                )
            except UnrepresentableDirectiveIdError as exc:
                warnings.append(f"Could not promote selected directive id {raw_id!r}; skipped. {exc}")
                continue
            if stem is None:
                warnings.append(f"Could not resolve selected {kind.operator_token} id {raw_id!r}; skipped.")
            elif stem not in stems:
                stems.append(stem)
        if stems:
            promotions[f"activated_{kind.plural}"] = stems

    if not promotions:
        return warnings

    target_path, config_data, save = resolve_activation_write_target(repo_root)

    plans = promote_activations(
        promotions,
        config_path=target_path,
        config_data=config_data,
        save=save,
        default_ids=load_default_pack_ids(),
    )
    warnings.extend(warning for plan in plans for warning in plan.warnings)
    return warnings


@charter_app.command()
def interview(  # noqa: C901
    mission_type: str | None = typer.Option(
        None,
        "--mission-type",
        help="Mission type for charter defaults (default: software-dev)",
    ),
    mission: str | None = typer.Option(None, "--mission", hidden=True, help="(deprecated) Use --mission-type"),
    profile: str = typer.Option("minimal", "--profile", help="Interview profile: minimal or comprehensive"),
    use_defaults: bool = typer.Option(False, "--defaults", help="Use deterministic defaults without prompts"),
    selected_paradigms: str | None = typer.Option(
        None,
        "--selected-paradigms",
        help="Comma-separated paradigm IDs override",
    ),
    selected_directives: str | None = typer.Option(
        None,
        "--selected-directives",
        help="Comma-separated directive IDs override",
    ),
    available_tools: str | None = typer.Option(
        None,
        "--available-tools",
        help="Comma-separated tool IDs override",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    mission_slug: str | None = typer.Option(
        None,
        "--mission-slug",
        help="Mission slug for Decision Moment paper trail (optional)",
    ),
) -> None:
    """Capture charter interview answers for later generation."""
    from charter.activation.interview import (
        MINIMAL_QUESTION_ORDER,
        QUESTION_ORDER,
        QUESTION_PROMPTS,
        apply_answer_overrides,
        write_interview_answers,
    )

    try:
        repo_root = _charter_pkg.find_repo_root()
        normalized_profile = profile.strip().lower()
        if normalized_profile not in {"minimal", "comprehensive"}:
            raise ValueError("--profile must be 'minimal' or 'comprehensive'")

        resolved_mission_type = "software-dev"
        if mission_type is not None or mission is not None:
            from specify_cli.cli.selector_resolution import resolve_selector

            resolved = resolve_selector(
                canonical_value=mission_type,
                canonical_flag="--mission-type",
                alias_value=mission,
                alias_flag="--mission",
                suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
                command_hint="--mission-type <name>",
            )
            resolved_mission_type = resolved.canonical_value

        interview_data = _charter_pkg.default_interview(mission=resolved_mission_type, profile=normalized_profile)

        # ------------------------------------------------------------------
        # FR-026 — Pre-fill interview from org charter packs (non-destructive).
        # Missing answers receive the org default so the interactive prompt
        # surfaces it; existing answers are preserved. Required directives are
        # pre-selected. Failure here is non-fatal (org packs are optional).
        # ------------------------------------------------------------------
        org_prefill_messages: list[str] = []
        org_prefill_warning: str | None = None
        try:
            from specify_cli.doctrine.org_charter import apply_org_charter_to_interview

            org_prefill_messages = apply_org_charter_to_interview(interview_data, repo_root)
            if not json_output:
                for msg in org_prefill_messages:
                    console.print(f"[cyan]Org charter:[/cyan] {msg}")
        except Exception as exc:  # noqa: BLE001 — org-charter is best-effort, never blocks interview
            org_prefill_warning = str(exc)
            if not json_output:
                console.print(f"[yellow]Org charter pre-fill skipped:[/yellow] {exc}")

        # Resolve actor for Decision Moment events (non-fatal fallback)
        actor = _resolve_actor()

        # ------------------------------------------------------------------
        # T026 — Widen Mode prereq check at startup (non-fatal, ≤300ms)
        # ------------------------------------------------------------------
        prereq_state: Any = _charter_pkg._get_widen_prereqs_absent()
        widen_flow: Any = None
        widen_store: Any = None
        _saas_client: Any = None

        if mission_slug is not None:
            try:
                from specify_cli.saas_client import SaasClient
                from specify_cli.widen import check_prereqs
                from specify_cli.widen.flow import WidenFlow
                from specify_cli.widen.state import WidenPendingStore

                _saas_client = SaasClient.from_env(repo_root)
                # Resolve team_slug from the auth context
                _team_slug: str = ""
                with contextlib.suppress(Exception):
                    from specify_cli.saas_client.auth import load_auth_context

                    _auth_ctx = load_auth_context(repo_root)
                    _team_slug = _auth_ctx.team_slug or ""

                prereq_state = check_prereqs(_saas_client, team_slug=_team_slug)
                if prereq_state.all_satisfied:
                    widen_flow = WidenFlow(_saas_client, repo_root, console)
                    widen_store = WidenPendingStore(repo_root, mission_slug)
            except Exception:  # noqa: BLE001 — SaaS prereq check is optional; failure keeps prereq_state ABSENT (non-fatal)
                pass  # non-fatal; prereq_state stays ABSENT

        # Resolve mission_id for widen endpoint (ULID from meta.json)
        _mission_id: str | None = None
        if mission_slug is not None:
            _mission_id = _charter_pkg._get_mission_id(repo_root, mission_slug)

        if not use_defaults:
            question_order = MINIMAL_QUESTION_ORDER if normalized_profile == "minimal" else QUESTION_ORDER
            answers_override: dict[str, str] = {}
            for question_id in question_order:
                prompt_text = QUESTION_PROMPTS.get(question_id, question_id.replace("_", " ").title())
                default_value = interview_data.answers.get(question_id, "")

                # Open a Decision Moment before presenting the question (non-fatal)
                current_decision_id: str | None = None
                if mission_slug is not None:
                    with contextlib.suppress(_DecisionError):
                        dm_response = _charter_pkg._dm_service.open_decision(
                            repo_root=repo_root,
                            mission_slug=mission_slug,
                            origin_flow=_DmOriginFlow.CHARTER,
                            step_id=f"charter.{question_id}",
                            input_key=question_id,
                            question=prompt_text,
                            options=(),
                            actor=actor,
                        )
                        current_decision_id = dm_response.decision_id

                # T045 — Already-widened question prompt (§1.3 contract)
                _already_widened = widen_store is not None and current_decision_id is not None and _is_already_widened(widen_store, current_decision_id)
                if _already_widened and _saas_client is not None and mission_slug is not None and current_decision_id is not None:
                    from specify_cli.widen.interview_helpers import render_already_widened_prompt

                    render_already_widened_prompt(
                        question_text=prompt_text,
                        decision_id=current_decision_id,
                        mission_slug=mission_slug,
                        repo_root=repo_root,
                        saas_client=_saas_client,
                        widen_store=widen_store,
                        dm_service=_charter_pkg._dm_service,
                        actor=actor,
                        console=console,
                    )
                    answers_override[question_id] = ""
                    continue  # next question — decision already handled

                # T027 — Build hint line; append [w]iden when prereqs met
                widen_suffix = ""
                if prereq_state is not None and prereq_state.all_satisfied and widen_store is not None and current_decision_id is not None and not _already_widened:
                    widen_suffix = " | [w]iden"
                hint_line = f"[enter]=accept default | [text]=type answer{widen_suffix} | [d]efer | [!cancel]"

                # Prompt the question (handles widen dispatch internally)
                actual_answer = _prompt_one_question(
                    question_id=question_id,
                    prompt_text=prompt_text,
                    default_value=default_value,
                    hint_line=hint_line,
                    widen_flow=widen_flow,
                    widen_store=widen_store,
                    current_decision_id=current_decision_id,
                    mission_id=_mission_id,
                    mission_slug=mission_slug,
                    repo_root=repo_root,
                    console=console,
                    saas_client=_saas_client,
                    actor=actor,
                    answers_override=answers_override,
                )

                # Terminal DM event (non-fatal)
                if current_decision_id is not None and mission_slug is not None:
                    _resolve_dm_terminal(
                        repo_root=repo_root,
                        mission_slug=mission_slug,
                        decision_id=current_decision_id,
                        actual_answer=actual_answer,
                        actor=actor,
                    )

            paradigms_default = ", ".join(interview_data.selected_paradigms)
            directives_default = ", ".join(interview_data.selected_directives)
            tools_default = ", ".join(interview_data.available_tools)

            selected_paradigms = typer.prompt(
                "Selected paradigms (comma-separated)",
                default=selected_paradigms or paradigms_default,
            )
            selected_directives = typer.prompt(
                "Selected directives (comma-separated)",
                default=selected_directives or directives_default,
            )
            available_tools = typer.prompt(
                "Available tools (comma-separated)",
                default=available_tools or tools_default,
            )

            interview_data = apply_answer_overrides(
                interview_data,
                answers=answers_override,
                selected_paradigms=_parse_csv_option(selected_paradigms),
                selected_directives=_parse_csv_option(selected_directives),
                available_tools=_parse_csv_option(available_tools),
            )
        else:
            # --defaults path: no interactive prompt, but we still record a
            # Decision Moment per question so the paper trail matches the
            # interactive flow.  Each defaulted answer becomes a resolved
            # decision (or deferred when the default is empty).
            if mission_slug is not None:
                question_order = MINIMAL_QUESTION_ORDER if normalized_profile == "minimal" else QUESTION_ORDER
                for question_id in question_order:
                    prompt_text = QUESTION_PROMPTS.get(question_id, question_id.replace("_", " ").title())
                    default_answer = interview_data.answers.get(question_id, "")
                    with contextlib.suppress(_DecisionError):
                        dm_response = _charter_pkg._dm_service.open_decision(
                            repo_root=repo_root,
                            mission_slug=mission_slug,
                            origin_flow=_DmOriginFlow.CHARTER,
                            step_id=f"charter.{question_id}",
                            input_key=question_id,
                            question=prompt_text,
                            options=(),
                            actor=actor,
                        )
                        _resolve_dm_terminal(
                            repo_root=repo_root,
                            mission_slug=mission_slug,
                            decision_id=dm_response.decision_id,
                            actual_answer=default_answer,
                            actor=actor,
                        )

            interview_data = apply_answer_overrides(
                interview_data,
                selected_paradigms=_parse_csv_option(selected_paradigms),
                selected_directives=_parse_csv_option(selected_directives),
                available_tools=_parse_csv_option(available_tools),
            )

        # ------------------------------------------------------------------
        # T040 — End-of-interview pending pass (FR-010)
        # ------------------------------------------------------------------
        if widen_store is not None and _saas_client is not None and mission_slug is not None:
            from specify_cli.widen.interview_helpers import run_end_of_interview_pending_pass

            run_end_of_interview_pending_pass(
                widen_store=widen_store,
                saas_client=_saas_client,
                mission_slug=mission_slug,
                repo_root=repo_root,
                console=console,
                dm_service=_charter_pkg._dm_service,
                actor=actor,
            )

        answers_path = _interview_path(repo_root)
        write_interview_answers(answers_path, interview_data)

        # FR-007 — append-promote captured selections into config.activated_*
        # via the WP06 primitive. Best-effort / non-fatal: a promotion failure
        # must never block the interview answers already written to disk.
        promotion_warnings: list[str] = []
        try:
            promotion_warnings = _promote_interview_selections(repo_root, interview_data)
        except Exception as exc:  # noqa: BLE001 — promotion is best-effort, never blocks the interview
            promotion_warnings = [f"Selection promotion skipped: {exc}"]
            if not json_output:
                console.print(f"[yellow]Selection promotion skipped:[/yellow] {exc}")

        if json_output:
            print(
                json.dumps(
                    {
                        "result": "success",
                        "success": True,
                        "interview_path": str(answers_path.relative_to(repo_root)),
                        "mission": interview_data.mission,
                        "profile": interview_data.profile,
                        "selected_paradigms": interview_data.selected_paradigms,
                        "selected_directives": interview_data.selected_directives,
                        "available_tools": interview_data.available_tools,
                        "org_prefill_messages": org_prefill_messages,
                        "org_prefill_warning": org_prefill_warning,
                        "promotion_warnings": promotion_warnings,
                    },
                    indent=2,
                )
            )
            return

        console.print("[green]Charter interview answers saved[/green]")
        console.print(f"Interview file: {answers_path.relative_to(repo_root)}")
        console.print(f"Mission: {interview_data.mission}")
        console.print(f"Profile: {interview_data.profile}")
        for msg in promotion_warnings:
            console.print(f"[yellow]Selection promotion:[/yellow] {msg}")

    except (TaskCliError, ValueError) as e:
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        _emit_error(console, json_output=json_output, message=str(e), unexpected=True)
        raise typer.Exit(code=1) from e
