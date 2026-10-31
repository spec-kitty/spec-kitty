"""Promote interview selections into present activation lists, never into an absent key (#6629).

Supersedes ``unify_charter_activation_promote_answers`` (3.2.6rc1, left
byte-identical per DIRECTIVE_044 and registered as a recorded no-op through
:data:`specify_cli.upgrade.supersession.SUPERSEDED_MIGRATIONS`). That migration
promoted every ``answers.selected_<kind>`` id the activation list lacked, and
seeded an *absent* ``activated_<kind>`` key with the kind's whole in-force set
first. Runtime governance did not change, but ``charter synthesize`` read the
seeded list as an operator's activation: it demanded one companion tactic per
directive (38 on the built-in pack) and skipped the fresh-project seed, so
``implement`` refused every work package (#6629). It also read only
``.kittify/config.yaml``, so on a project whose keys had moved it wrote a
second, stale list there (#6549).

Rules
-----
* **An absent key is never written.** While ``activated_<kind>`` is absent,
  every available artefact of that kind is in force, so a resolved interview
  id is already in force or names no available artefact; an allow-list entry
  for it would bring nothing into force and would only turn the "nothing
  chosen yet" state into an operator's activation. This is the zero-drop
  guarantee of the superseded migration, kept without materialising the key.
* **A present list gains the interview ids it lacks**, compared as stems so a
  list that spells an artefact by its declared id is not given a duplicate
  (#6423). The write goes through the one activation write target
  (:func:`charter.activation.pack_manager.resolve_activation_write_target`:
  the activation ledger once ``4.0.0rc8_activation_ledger`` has moved the
  keys) and the one promotion primitive, so the deny guard applies and a
  deactivated id stays deactivated.
* **Only where the superseded promotion never ran.** Since #2526 the
  interview record is not an activation source, so the promotion is a one-time
  backstop for a project crossing that change. When the Migration Ledger
  records ``unify_charter_activation_promote_answers`` as ``success`` (it ran,
  or the ledger-adoption backfill settled it for a project created after it)
  or as a ``skipped`` the shipped step recorded itself (the pre-ledger runner
  wrote "Not applicable" when the interview had already promoted, and the
  backfill copies it), an interview id a present list lacks was removed, or
  was never in force; it is not appended back (#6499). The superseded
  substitute's own ``skipped`` is marked ``superseded_by`` and does not count.
* **One run settles it.** :meth:`detect` is always True and :meth:`apply`
  succeeds even when nothing is left to promote, so the runner records
  ``success``. A ``skipped`` record would re-select the migration on every
  upgrade, and after an operator narrowed a list with ``charter activate
  --only`` it would append the interview ids back.
* **A list an earlier build seeded is reported, never narrowed** (#6499): when
  a present list holds every available artefact of its kind and the interview
  selected only some of them, the result warns and names the narrowing
  commands (#6408).

Resolution is not this step's own rule any more (#6686): every interview id is
resolved through :class:`charter.activation.selection.SelectionResolver`, the
layer-aware resolver ``charter interview`` uses, so the project pack, the org
packs and the built-in pack all answer. An id no layer resolves, or one no file
stem can represent, is reported, never dropped silently.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.api import (
    ActiveCharterConfigError,
    SelectionResolution,
    SelectionResolver,
    resolve_offering_root,
)
from charter.drg import ArtifactKind

from ..ledger import SETTLED_RESULT, LedgerRecord, MigrationLedger
from ..metadata import _LEGACY_MIGRATION_ID_MAP, ProjectMetadata
from ..registry import MigrationRegistry, migration_settled, pending_adoption_ids
from .base import BaseMigration, MigrationResult, MigrationStateUnreadableError

MIGRATION_ID = "4.0.0rc8_promote_interview_selections"

#: The kinds whose interview selections are promoted: the charter activation
#: kinds an interview can select (the superseded migration's set).
PROMOTED_KINDS: tuple[ArtifactKind, ...] = (
    ArtifactKind.DIRECTIVE,
    ArtifactKind.TACTIC,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TOOLGUIDE,
    ArtifactKind.PARADIGM,
    ArtifactKind.PROCEDURE,
    ArtifactKind.AGENT_PROFILE,
    ArtifactKind.MISSION_STEP_CONTRACT,
)

_ANSWERS_RELATIVE_PATH = Path(".kittify") / "charter" / "interview" / "answers.yaml"
_NOTHING_TO_PROMOTE = "No interview selections to promote: every selection is already in force"
_ALREADY_PROMOTED = "Interview selections were promoted by an earlier upgrade; nothing to promote"
_NO_SELECTIONS = "No interview selections to promote"
_NOTHING_PREVIEW = "dry-run: nothing would be promoted"
_SUPERSEDED_PROMOTION_ID = "unify_charter_activation_promote_answers"
_SKIPPED_RESULT = "skipped"
_SEEDED_LIST_HINT = (
    "{key} lists every available {token} ({listed}), as an upgrade before 4.0.0rc8 wrote it; the interview selected {selected}. "
    "To keep only those, run `spec-kitty charter interview --narrow-activation` or "
    "`spec-kitty charter activate {token} <id> --only`; `charter synthesize` then asks for companion tactics only for what you keep."
)


def _allow_key(kind: ArtifactKind) -> str:
    return f"activated_{kind.plural}"


def _selected_ids(answers: Mapping[str, Any], kind: ArtifactKind) -> list[str]:
    raw = answers.get(f"selected_{kind.plural}")
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _load_answers(project_path: Path) -> dict[str, Any]:
    """The interview answers mapping; ``{}`` when absent, empty, malformed or not a mapping."""
    path = project_path / _ANSWERS_RELATIVE_PATH
    if not path.is_file():
        return {}
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — an unreadable interview record holds no selection to promote
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_selections(answers: Mapping[str, Any], resolver: SelectionResolver) -> SelectionResolution:
    """The interview selections resolved through every doctrine layer (#6686).

    One rule, shared with ``charter interview`` (``charter.activation.selection``),
    so an org-pack or project-pack selection promotes here exactly as it does
    there. An id no layer knows, or one no file stem can represent, is reported.
    """
    return resolver.resolve({kind: _selected_ids(answers, kind) for kind in PROMOTED_KINDS})


def _present_lists(data: Mapping[str, Any], selections: SelectionResolution) -> dict[ArtifactKind, list[str]]:
    """The present allow list of every kind the interview selected; an absent key or a non-list value is left out."""
    present: dict[ArtifactKind, list[str]] = {}
    for kind in PROMOTED_KINDS:
        listed = data.get(_allow_key(kind))
        if _allow_key(kind) in selections.stems and isinstance(listed, list):
            present[kind] = [str(item) for item in listed]
    return present


def _promotions(present: Mapping[ArtifactKind, list[str]], selections: SelectionResolution, resolver: SelectionResolver) -> dict[str, list[str]]:
    """``{activated_<kind>: [stems]}``: each present list's missing interview stems, in answers order.

    A deactivated stem is not filtered here: the promotion primitive applies
    the effective deny (less the org required floor) and reports what it
    skipped, so one rule decides (FR-006).
    """
    promotions: dict[str, list[str]] = {}
    for kind, listed in present.items():
        listed_stems = resolver.stems(kind, listed)
        if missing := [stem for stem in selections.stems[_allow_key(kind)] if stem not in listed_stems]:
            promotions[_allow_key(kind)] = missing
    return promotions


def _discard(path: Path, data: dict[str, Any]) -> None:
    """The ``save`` of a dry run: the promotion primitive plans and reports, nothing is written."""
    del path, data


def _seeded_list_hints(project_path: Path, present: Mapping[ArtifactKind, list[str]], selections: SelectionResolution, resolver: SelectionResolver) -> list[str]:
    """A warning for each present list that holds every available artefact while the interview selected fewer.

    The in-force set is resolved once, only for the candidate kinds (a list
    longer than the selection). Nothing is written: narrowing is an operator
    decision (#6499, #6408).
    """
    candidates = {_allow_key(kind): kind for kind, listed in present.items() if len(listed) > len(selections.stems[_allow_key(kind)])}
    if not candidates:
        return []
    # Lazy: resolving the in-force set builds the doctrine service; registry discovery must not pay for that.
    from charter.activation.api import resolve_effective_sets

    hints: list[str] = []
    for key, entry in resolve_effective_sets(project_path, list(candidates)).items():
        kind = candidates[key]
        listed = resolver.stems(kind, present[kind])
        selected = set(selections.stems[key])
        if entry.resolved and entry.ids and listed == resolver.stems(kind, entry.ids) and selected < listed:
            hints.append(_SEEDED_LIST_HINT.format(key=key, token=kind.operator_token, listed=len(listed), selected=len(selected)))
    return hints


def _shipped_promotion_ran(record: LedgerRecord) -> bool:
    """Whether *record* says the shipped promotion itself ran: ``success``, or a ``skipped`` it recorded.

    The pre-ledger runner recorded ``skipped`` ("Not applicable") when the
    interview had already promoted, and the adoption backfill copies that
    record. The superseded substitute's own ``skipped`` carries
    ``superseded_by`` and means the shipped step never ran.
    """
    return record.result == SETTLED_RESULT or (record.result == _SKIPPED_RESULT and not record.superseded_by)


def _adoption_records_shipped_promotion(project_path: Path, ledger: MigrationLedger) -> bool:
    """Whether a pending ledger adoption will record that the superseded promotion ran.

    A dry run writes no ledger record, so on a project being adopted the
    preview asks what the adoption backfill will record, the way selection
    does (:func:`~specify_cli.upgrade.registry.pending_adoption_ids`): a
    ``success`` it settles, or the legacy ``skipped`` it copies from
    ``metadata.yaml`` (which predates the substitute, so it is the shipped
    step's own). After adoption nothing is pending and the ledger alone answers.
    """
    adopting = [migration for migration in MigrationRegistry.get_all() if migration.ledger_adoption and not migration_settled(ledger, migration)]
    if not adopting:
        return False
    if _SUPERSEDED_PROMOTION_ID in pending_adoption_ids(ledger, adopting, project_path):
        return True
    metadata = ProjectMetadata.load(project_path / ".kittify")
    legacy = metadata.applied_migrations if metadata is not None else []
    return any(_LEGACY_MIGRATION_ID_MAP.get(record.id, record.id) == _SUPERSEDED_PROMOTION_ID and record.result == _SKIPPED_RESULT for record in legacy)


def _shipped_promotion_settled(project_path: Path) -> bool:
    """Whether the Migration Ledger records, or its pending adoption will record, that the superseded promotion ran."""
    ledger = MigrationLedger(project_path)
    shipped = MigrationRegistry.get_by_id(_SUPERSEDED_PROMOTION_ID)
    records = ledger.applicable_records_for(shipped)
    if any(record.id == _SUPERSEDED_PROMOTION_ID and _shipped_promotion_ran(record) for record in records):
        return True
    return _adoption_records_shipped_promotion(project_path, ledger)


def _unresolved_warning(unresolved: list[str]) -> str:
    return f"Unresolved interview selections skipped (not promoted): {', '.join(unresolved)}"


@MigrationRegistry.register
class PromoteInterviewSelectionsMigration(BaseMigration):
    """Promote answers-only interview selections into present activation lists; never write an absent key."""

    migration_id = MIGRATION_ID
    description = (
        "Promote interview selections (answers.yaml selected_<kind>) that a present activation list lacks "
        "into it, through the activation ledger; an absent activated_<kind> key stays absent (#6629)."
    )
    target_version = "4.0.0rc8"
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """Always True, so one run records ``success`` and settles it (a ``skipped`` record re-selects it)."""
        del project_path
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable; a project with nothing to promote is a no-op."""
        del project_path
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Append each present list's missing interview selections; an absent key is never written.

        An unreadable or malformed activation surface is the runner's recorded
        failure (``MigrationStateUnreadableError``), as in ``4.0.0rc8_activation_ledger``,
        never an uncaught traceback.
        """
        try:
            return self._apply(project_path, dry_run)
        except ActiveCharterConfigError as exc:
            raise MigrationStateUnreadableError(exc.body) from exc

    def _apply(self, project_path: Path, dry_run: bool) -> MigrationResult:
        answers = _load_answers(project_path)
        if not any(_selected_ids(answers, kind) for kind in PROMOTED_KINDS):
            return MigrationResult(success=True, changes_made=[_NO_SELECTIONS])
        try:
            resolver = SelectionResolver.build(project_path, offering_root=resolve_offering_root())
        except Exception as exc:  # noqa: BLE001 — surfaced as a structured migration error
            return MigrationResult(success=False, errors=[f"Could not resolve doctrine root: {exc}"])
        selections = _resolve_selections(answers, resolver)

        # Lazy (registry discovery stays cheap): the write target loads the activation surface.
        from charter.activation.api import resolve_activation_write_target

        target_path, data, save = resolve_activation_write_target(project_path)
        present = _present_lists(data, selections)
        warnings = _seeded_list_hints(project_path, present, selections, resolver)
        if _shipped_promotion_settled(project_path):
            nothing = _NOTHING_PREVIEW if dry_run else _ALREADY_PROMOTED
            return MigrationResult(success=True, changes_made=[nothing], warnings=warnings)
        promotions = _promotions(present, selections, resolver)
        if selections.unresolved:
            warnings.append(_unresolved_warning([selection.urn for selection in selections.unresolved]))

        if not promotions:
            nothing = _NOTHING_PREVIEW if dry_run else _NOTHING_TO_PROMOTE
            return MigrationResult(success=True, changes_made=[nothing], warnings=warnings)
        return self._promote(project_path, promotions, target_path, data, save, warnings, dry_run=dry_run)

    @staticmethod
    def _promote(
        project_path: Path,
        promotions: dict[str, list[str]],
        target_path: Path,
        data: dict[str, Any],
        save: Callable[[Path, dict[str, Any]], None],
        warnings: list[str],
        *,
        dry_run: bool,
    ) -> MigrationResult:
        """Promote *promotions* (present keys only) through the one promotion primitive, then re-stamp the bundle.

        A dry run hands the primitive a copy of *data* and a discarding
        ``save``, so the preview is the primitive's own outcome (its deny guard
        included) and nothing is written.
        """
        from charter.activation.api import promote_activations, restamp_bundle_hash

        if dry_run:
            data, save = copy.deepcopy(data), _discard
        outcome = promote_activations(promotions, config_path=target_path, config_data=data, save=save, effective_sets={}, repo_root=project_path)
        promoted = {plan.yaml_key: plan.activated for plan in outcome.committed if plan.activated}
        notes = [warning for plan in outcome.committed for warning in plan.warnings]
        # Only present keys are promoted, so the primitive never leaves one absent.
        notes.extend(outcome.skipped_denied_messages())
        if dry_run:
            change = f"dry-run: would promote {promoted}" if promoted else _NOTHING_PREVIEW
            return MigrationResult(success=True, changes_made=[change], warnings=[*notes, *warnings])
        if promoted:
            # The activation ledger is in the bundle hash (FR-018): keep the manifest stamp in parity.
            restamp_bundle_hash(project_path)
        changes = [f"Promoted {ids} into {key}" for key, ids in promoted.items()]
        return MigrationResult(success=True, changes_made=changes or [_NOTHING_TO_PROMOTE], warnings=[*notes, *warnings])
