"""``spec-kitty charter interview`` command (WP06 per-subcommand split).

The local Decision-Moment interview helpers live in
:mod:`specify_cli.cli.commands.charter._widen` so this module stays under the
500-line WP06 budget. Hosted Widen Mode was removed in issue #6164; only the
local interview loop remains.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.markup import escape

from specify_cli.core.env import is_interactive
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
    _prompt_one_question,
    _resolve_dm_terminal,
)

# Patch-compatibility shim: legacy tests patch
# ``specify_cli.cli.commands.charter.<name>`` for ``find_repo_root``,
# ``default_interview``, ``_charter_pkg._dm_service``, and
# ``_resolve_dm_terminal``. Looking them up on the package module at call time
# preserves that contract through the WP06 split.
import specify_cli.cli.commands.charter as _charter_pkg

if TYPE_CHECKING:
    from charter.activation.api import EffectiveSet
    from charter.activation.api import LanguageSettlement
    from charter.drg import ArtifactKind

__all__ = ["interview"]


def _narrow_bases(repo_root: Path, promotions: dict[str, list[str]], warnings: list[str]) -> dict[str, list[str]]:
    """Per promoted key, the narrow base: the selection stems plus the org-required ids (#6408)."""
    from charter.activation.api import org_required_stems

    bases: dict[str, list[str]] = {}
    for yaml_key, stems in promotions.items():
        plural = yaml_key.removeprefix("activated_")
        bases[yaml_key] = list(dict.fromkeys([*stems, *org_required_stems(repo_root, plural, warnings)]))
    return bases


def _stem_spelled_effective(repo_root: Path, effective: dict[str, EffectiveSet], kinds: dict[str, ArtifactKind]) -> dict[str, EffectiveSet]:
    """*effective* with every id spelled as an activation stem.

    The effective set lists org non-directive artifacts by declared id while
    activation lists hold stems, so a kept artifact whose stem differs from its id
    would otherwise be reported as no longer in force (#6408).
    """
    from charter.activation.api import IdentityIndex

    index = IdentityIndex.build(repo_root)
    mapped: dict[str, EffectiveSet] = {}
    for yaml_key, found in effective.items():
        kind = kinds.get(yaml_key)
        if kind is None or not found.resolved:
            mapped[yaml_key] = found
            continue
        mapped[yaml_key] = dataclasses.replace(found, ids=frozenset(index.stem(kind, item) or item for item in found.ids))
    return mapped


def _stem_spelled_config(repo_root: Path, config_data: dict[str, Any], kinds: dict[str, ArtifactKind], promotions: dict[str, list[str]]) -> dict[str, Any]:
    """*config_data* with each promoted key's PRESENT list spelled as activation stems.

    A list holding a declared id (``DIRECTIVE_003``) would otherwise be compared raw
    against the stem the interview selected and report the same artifact as dropped (#6408).
    """
    from charter.activation.api import IdentityIndex

    index = IdentityIndex.build(repo_root)
    mapped = dict(config_data)
    for yaml_key in promotions:
        kind = kinds.get(yaml_key)
        current = config_data.get(yaml_key)
        if kind is None or not isinstance(current, list):
            continue
        mapped[yaml_key] = [index.stem(kind, str(item)) or str(item) for item in current]
    return mapped


def _promote_interview_selections(repo_root: Path, interview_data: Any, *, narrow: bool = False) -> tuple[list[str], dict[str, list[str]]]:
    """Append-promote captured interview selections into ``config.activated_<kind>`` (FR-007).

    Only the three roots :class:`~charter.activation.interview.CharterInterview` actually
    captures (directives, tactics, paradigms) are promoted here — a project's
    ``answers.yaml`` may separately carry hand-authored non-root selections
    (e.g. ``selected_styleguides``); those are the config-seeded migration's
    job (``m_unify_charter_activation``, T023), not this per-interview-run
    wiring. Routes through the shared :func:`charter.activation.activation_engine.promote_activations`
    primitive — the same append-only seam the migration uses — with the WP01
    ID-form resolver (:func:`charter.activation.kind_vocabulary.resolve_selected_id_to_stem`).
    An absent key is seeded from the effective set
    (:func:`charter.activation.effective_set.resolve_effective_sets`, FR-015);
    when that set cannot be resolved the key stays absent and a warning names
    it (#4400).

    Best-effort / non-fatal by contract: the caller wraps this in a broad
    ``except`` so a promotion failure never blocks the interview answers
    already written to disk. Returns human-readable warning strings (empty
    when there is nothing to surface).

    Write target (consolidate-charter-bundle WP02): resolved via
    :func:`charter.activation.pack_manager.resolve_activation_write_target` — a
    migrated project (``config.yaml`` carries a ``charter:`` pointer)
    promotes into ``charter.yaml``; a legacy/un-migrated project promotes
    into ``config.yaml`` directly (unchanged pre-relocation behavior).

    With ``narrow=True`` (#6408) each promoted key is *replaced* by its selection
    plus the org-required ids instead of appended to; a kind with an empty
    selection is never narrowed. Returns ``(warnings, narrowed)`` where
    ``narrowed`` maps each key to the ids that stopped being in force (``{}``
    when narrowing is off).
    """
    from charter.activation.activation_engine import promote_activations
    from charter.activation.catalog import resolve_offering_root
    from charter.activation.effective_set import resolve_effective_sets
    from charter.activation.kind_vocabulary import UnrepresentableDirectiveIdError, resolve_selected_id_to_stem
    from charter.activation.pack_manager import resolve_activation_write_target
    from charter.drg import ArtifactKind

    kind_to_selection: dict[ArtifactKind, list[str]] = {
        ArtifactKind.DIRECTIVE: list(interview_data.selected_directives),
        ArtifactKind.TACTIC: list(interview_data.selected_tactics),
        ArtifactKind.PARADIGM: list(interview_data.selected_paradigms),
    }

    from charter.activation.layer_roots import (
        resolve_layer_roots,
        resolve_pack_chain,
    )

    offering_root = resolve_offering_root()
    org_roots = resolve_pack_chain(repo_root, strict=False)
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
                    offering_root=offering_root,
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
        return warnings, {}

    target_path, config_data, save = resolve_activation_write_target(repo_root)

    absent = [key for key in promotions if config_data.get(key) is None]
    effective_sets = resolve_effective_sets(repo_root, absent) if absent else {}
    if narrow:
        config_data = _stem_spelled_config(repo_root, config_data, {f"activated_{kind.plural}": kind for kind in kind_to_selection}, promotions)
        effective_sets = _stem_spelled_effective(repo_root, effective_sets, {f"activated_{kind.plural}": kind for kind in kind_to_selection})
    outcome = promote_activations(
        promotions,
        config_path=target_path,
        config_data=config_data,
        save=save,
        effective_sets=effective_sets,
        narrow_bases=_narrow_bases(repo_root, promotions, warnings) if narrow else None,
    )
    warnings.extend(warning for plan in outcome.committed for warning in plan.warnings)
    warnings.extend(outcome.left_absent_messages())
    narrowed = {plan.yaml_key: list(plan.deactivated) for plan in outcome.committed if narrow and plan.deactivated}
    return warnings, narrowed


_LANGUAGES_PROMPT = "Project languages (comma-separated catalog tokens, primary first; 'none' to leave unset)"


def _settle_languages(repo_root: Path, *, interactive: bool) -> LanguageSettlement:
    """Detect, propose and store the project language list in config.yaml (FR-020).

    Interactive runs show the stored list (else the detected one) as the default. A
    ``--defaults`` or non-interactive run never prompts, never overwrites a stored list, and
    stores the detected list (with a notice) only when the key is absent. An invalid answer
    is asked again (bounded), then fails without writing.
    """
    from charter.activation.api import settle_project_languages

    ask = (lambda default: typer.prompt(_LANGUAGES_PROMPT, default=default)) if interactive else None
    return settle_project_languages(repo_root, ask=ask, on_invalid=lambda message: typer.echo(message, err=True))


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
    narrow_activation: bool = typer.Option(
        False,
        "--narrow-activation",
        help="Replace (not append to) activated directives, tactics and paradigms with the selection plus org-required ids",
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
            from charter.activation.org_charter import apply_org_charter_to_interview

            org_prefill_messages = apply_org_charter_to_interview(interview_data, repo_root)
            if not json_output:
                for msg in org_prefill_messages:
                    console.print(f"[cyan]Org charter:[/cyan] {msg}")
        except Exception as exc:  # noqa: BLE001 — org-charter is best-effort, never blocks interview
            org_prefill_warning = str(exc)
            if not json_output:
                console.print(f"[yellow]Org charter pre-fill skipped:[/yellow] {exc}")

        # FR-020 -- detect the repository's languages, propose them, and store the confirmed
        # list in .kittify/config.yaml. When set it is the one list for evidence and scoping.
        language_settlement = _settle_languages(repo_root, interactive=not use_defaults and is_interactive())

        # Resolve actor for Decision Moment events (non-fatal fallback)
        actor = _resolve_actor()

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

                hint_line = "[enter]=accept default | [text]=type answer | [d]efer | [!cancel]"

                # Prompt the question (local Decision-Moment loop)
                actual_answer = _prompt_one_question(
                    question_id=question_id,
                    prompt_text=prompt_text,
                    default_value=default_value,
                    hint_line=hint_line,
                    console=console,
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

        answers_path = _interview_path(repo_root)
        write_interview_answers(answers_path, interview_data)

        # FR-007 — append-promote captured selections into config.activated_*
        # via the WP06 primitive. Best-effort / non-fatal: a promotion failure
        # must never block the interview answers already written to disk.
        promotion_warnings: list[str] = []
        narrowed: dict[str, list[str]] = {}
        try:
            promotion_warnings, narrowed = _promote_interview_selections(repo_root, interview_data, narrow=narrow_activation)
        except Exception as exc:  # noqa: BLE001 — promotion is best-effort, never blocks the interview
            if narrow_activation:
                # An explicit --narrow-activation that cannot be applied is a failure, not a warning (#6408).
                raise TaskCliError(f"--narrow-activation could not be applied: {exc}") from exc
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
                        "languages": list(language_settlement.languages),
                        "languages_source": language_settlement.source,
                        "languages_notice": language_settlement.notice,
                        "org_prefill_messages": org_prefill_messages,
                        "org_prefill_warning": org_prefill_warning,
                        "promotion_warnings": promotion_warnings,
                        "narrowed": narrowed,
                    },
                    indent=2,
                )
            )
            return

        console.print("[green]Charter interview answers saved[/green]")
        console.print(f"Interview file: {answers_path.relative_to(repo_root)}")
        console.print(f"Mission: {interview_data.mission}")
        console.print(f"Profile: {interview_data.profile}")
        if language_settlement.languages:
            console.print(f"Languages ({language_settlement.source}): {', '.join(language_settlement.languages)}")
        if language_settlement.notice:
            console.print(f"[yellow]Notice:[/yellow] {escape(language_settlement.notice)}")
        for msg in promotion_warnings:
            console.print(f"[yellow]Selection promotion:[/yellow] {msg}")
        for yaml_key, dropped in narrowed.items():
            console.print(f"[yellow]No longer in force ({len(dropped)}) for {yaml_key}:[/yellow] {escape(', '.join(dropped))}")

    except (TaskCliError, ValueError) as e:
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        _emit_error(console, json_output=json_output, message=str(e), unexpected=True)
        raise typer.Exit(code=1) from e
