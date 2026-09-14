"""Migration m_unify_charter_activation: promote answers-only selections (FR-006/FR-007).

Mission ``unify-charter-activation-surfaces`` makes ``config.activated_<kind>``
the single activation authority; the compiled reference set + DRG graph now
derive from it, and ``answers.selected_<kind>`` (the charter interview record
at ``.kittify/charter/interview/answers.yaml``) is retired as an activation
*source*. A project upgrading into this model could have artefacts recorded
in ``answers.selected_<kind>`` that were never mirrored into
``config.activated_<kind>`` — under the new config-authority regime those
artefacts would silently drop out of the compiled reference set. This
migration is the zero-drop backstop: it promotes every answers-only selection
into config via :func:`charter.activation.activation_engine.promote_activations` (WP06),
for **every** charter kind (not roots-only — an org- or hand-authored project
can carry non-root selections such as ``selected_styleguides`` that no
activated directive reaches).

ID-form parity (WP01, C-006)
-----------------------------
``config.activated_<kind>`` stores config/file-stem IDs (e.g.
``"001-architectural-integrity-standard"``); ``answers.selected_<kind>``
values are free-form and may already be the stem OR the artefact's canonical
``id:`` field (e.g. ``"DIRECTIVE_001"`` for directives — the two forms this
repository's own answers/config pair actually differ by, per the squad
measurement in WP07's task doc). :func:`resolve_selected_id_to_stem` tries
both directions via :mod:`charter.activation.kind_vocabulary` (the WP01 resolver) before
concluding an id is unresolved, so a form-only difference is never mistaken
for an answers-only artefact.

Absent-key built-in safety (WP06 LAND-BLOCKER, reviewer caveat)
------------------------------------------------------------------
:func:`promote_activations` materializes the supplied ``default_ids`` for a
kind whose ``config.activated_<kind>`` key is *absent* before appending the
promoted ids — but only if the caller actually supplies the real built-in set.
This migration loads the shipped default pack via the shared
:func:`charter.activation.default_pack.load_default_pack_activation_ids` loader (the
same primitive :func:`specify_cli.doctrine.org_charter._promote_org_required_to_config`
uses — squad finding #2530 dedup) and passes it as ``default_ids`` so a
first-run/absent-key project keeps every built-in active rather than
collapsing to a bare, newly-promoted list.

Scope note
----------
Only the *built-in* doctrine layer is resolved here (``resolve_doctrine_root()``
with no ``org_roots``/``layer_roots``). An answers-only selection that names an
org-pack-only artefact is reported as unresolved (a warning, never a silent
drop) rather than crashing the migration — org-pack promotion is WP04's
``org_charter`` union, a separate consumer of the same WP06 primitive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.activation.activation_engine import promote_activations
from charter.activation.catalog import resolve_doctrine_root
from charter.activation.default_pack import load_default_pack_activation_ids
from charter.activation.kind_vocabulary import (
    UnrepresentableDirectiveIdError,
    resolve_selected_id_to_stem as resolve_selected_id_to_stem,
)
from charter.activation.kind_vocabulary import ArtifactKind

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: Kinds eligible for answers -> config promotion. Mirrors the 8-kind charter
#: activation universe (``charter.offering.artifact_kinds.CHARTER_KIND_TOKENS`` minus
#: the ``mission-type`` outlier, which has no ``selected_<kind>`` answers key
#: and no per-artefact config-stem/URN pair). ``TEMPLATE``/``ASSET`` are
#: excluded — they are not charter-activatable (see
#: ``charter.offering.artifact_kinds._NON_AUGMENTATION_ELIGIBLE_KINDS``).
_PROMOTABLE_KINDS: tuple[ArtifactKind, ...] = (
    ArtifactKind.DIRECTIVE,
    ArtifactKind.TACTIC,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TOOLGUIDE,
    ArtifactKind.PARADIGM,
    ArtifactKind.PROCEDURE,
    ArtifactKind.AGENT_PROFILE,
    ArtifactKind.MISSION_STEP_CONTRACT,
)

_CONFIG_RELATIVE_PATH = Path(".kittify") / "config.yaml"
_ANSWERS_RELATIVE_PATH = Path(".kittify") / "charter" / "interview" / "answers.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Safe-load a YAML mapping file; returns ``{}`` when absent/empty/non-mapping."""
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — malformed YAML degrades to empty, caller decides
        return {}
    return data if isinstance(data, dict) else {}


def load_default_pack_ids() -> dict[str, list[str]]:
    """Load the shipped default-pack IDs, keyed by ``config.yaml`` activation key.

    Public (imported by ``interview.py``'s promotion wiring, T024, and by
    ``specify_cli.doctrine.org_charter``) so every consumer of the WP06
    ``promote_activations`` primitive supplies the same real built-in
    ``default_ids`` rather than each re-deriving it independently. Thin
    re-export of the canonical :func:`charter.activation.default_pack.load_default_pack_activation_ids`
    loader — kept under this name (rather than inlined at each call site)
    because this migration's own tests and ``interview.py`` import it from
    this module (squad finding #2530: the duplicate *implementations* are
    gone; the public name here is now a one-line delegation).
    """
    return load_default_pack_activation_ids()


def _answers_only_ids_for_kind(
    kind: ArtifactKind,
    *,
    answers_data: dict[str, Any],
    config_data: dict[str, Any],
    doctrine_root: Path,
) -> tuple[list[str], list[str]]:
    """Return ``(answers-only stems to promote, unresolved raw ids)`` for *kind*."""
    raw_answer_ids = answers_data.get(f"selected_{kind.plural}") or []
    existing_stems = set(config_data.get(f"activated_{kind.plural}") or [])

    promote_stems: list[str] = []
    unresolved: list[str] = []
    for raw_id in raw_answer_ids:
        try:
            stem = resolve_selected_id_to_stem(kind, str(raw_id), doctrine_root=doctrine_root)
        except UnrepresentableDirectiveIdError:
            # Preserve the migration's per-ID unresolved warning contract.
            unresolved.append(str(raw_id))
            continue
        if stem is None:
            unresolved.append(str(raw_id))
        elif stem not in existing_stems and stem not in promote_stems:
            promote_stems.append(stem)
    return promote_stems, unresolved


def _compute_promotions(
    answers_data: dict[str, Any],
    config_data: dict[str, Any],
    doctrine_root: Path,
) -> tuple[dict[str, list[str]], list[str]]:
    """Compute the full ``{activated_<kind>: [answers-only stems]}`` promotion set.

    Returns the promotions map (only kinds with at least one answers-only id)
    plus a flat list of ``"<operator_token>:<raw_id>"`` unresolved entries
    across all kinds.
    """
    promotions: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for kind in _PROMOTABLE_KINDS:
        promote_stems, kind_unresolved = _answers_only_ids_for_kind(
            kind,
            answers_data=answers_data,
            config_data=config_data,
            doctrine_root=doctrine_root,
        )
        unresolved.extend(f"{kind.operator_token}:{raw}" for raw in kind_unresolved)
        if promote_stems:
            promotions[f"activated_{kind.plural}"] = promote_stems
    return promotions, unresolved


def _unresolved_warning(unresolved: list[str]) -> str:
    return f"Unresolved answers-only ids skipped (not promoted): {', '.join(unresolved)}"


@MigrationRegistry.register
class UnifyCharterActivationMigration(BaseMigration):
    """Promote answers-only ``selected_<kind>`` ids into ``config.activated_<kind>``.

    Config-seeded reconcile (FR-006): a project whose interview record
    (``answers.yaml``) carries a selection never mirrored into
    ``config.yaml`` would otherwise silently lose that artefact once the
    compiled reference set / DRG graph derive from config alone. This
    migration promotes any such answers-only artefact, for every charter
    kind, with zero drop.
    """

    migration_id = "unify_charter_activation_promote_answers"
    description = (
        "Promote answers-only selected_<kind> ids into config.activated_<kind> "
        "so config-authority derivation never silently drops an artefact "
        "recorded only in the charter interview (FR-006)."
    )
    target_version = "3.2.6rc1"

    def detect(self, project_path: Path) -> bool:
        """Return True when at least one answers-only selection is promotable."""
        config_path = project_path / _CONFIG_RELATIVE_PATH
        answers_path = project_path / _ANSWERS_RELATIVE_PATH
        if not config_path.exists() or not answers_path.exists():
            return False

        config_data = _load_yaml(config_path)
        answers_data = _load_yaml(answers_path)
        if not config_data or not answers_data:
            return False

        try:
            doctrine_root = resolve_doctrine_root()
        except Exception:  # noqa: BLE001 — unresolved doctrine root means nothing to detect
            return False

        promotions, _unresolved = _compute_promotions(answers_data, config_data, doctrine_root)
        return bool(promotions)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that there is at least one answers-only selection to promote."""
        if self.detect(project_path):
            return True, ""
        return False, "no answers-only selections to promote"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Promote every answers-only ``selected_<kind>`` id into config.yaml.

        Uses ``ruamel.yaml`` round-trip mode so existing ``config.yaml``
        comments/formatting survive the write, and routes the single write
        through :func:`charter.activation.activation_engine.promote_activations` (one
        ``commit_plan`` call per affected kind) — there is no other write
        path in this migration.
        """
        config_path = project_path / _CONFIG_RELATIVE_PATH
        answers_path = project_path / _ANSWERS_RELATIVE_PATH

        if not config_path.exists():
            return MigrationResult(
                success=True,
                changes_made=["No .kittify/config.yaml found; nothing to promote"],
            )
        if not answers_path.exists():
            return MigrationResult(
                success=True,
                changes_made=["No answers.yaml found; nothing to promote"],
            )

        yaml = YAML()
        yaml.preserve_quotes = True
        try:
            config_data = yaml.load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001 — surfaced as a structured migration error
            return MigrationResult(success=False, errors=[f"Invalid .kittify/config.yaml: {exc}"])
        if not isinstance(config_data, dict):
            return MigrationResult(success=False, errors=[".kittify/config.yaml root must be a mapping"])

        answers_data = _load_yaml(answers_path)
        if not answers_data:
            return MigrationResult(
                success=True,
                changes_made=["answers.yaml is empty or has no selections; nothing to promote"],
            )

        try:
            doctrine_root = resolve_doctrine_root()
        except Exception as exc:  # noqa: BLE001 — surfaced as a structured migration error
            return MigrationResult(success=False, errors=[f"Could not resolve doctrine root: {exc}"])

        promotions, unresolved = _compute_promotions(answers_data, config_data, doctrine_root)

        if not promotions:
            result = MigrationResult(success=True, changes_made=["No answers-only selections to promote"])
            if unresolved:
                result.warnings = [_unresolved_warning(unresolved)]
            return result

        if dry_run:
            summary = [f"{key}: +{ids}" for key, ids in promotions.items()]
            result = MigrationResult(success=True, changes_made=[f"dry-run: would promote {summary}"])
            if unresolved:
                result.warnings = [_unresolved_warning(unresolved)]
            return result

        default_ids = load_default_pack_ids()

        def _save(path: Path, data: dict[str, Any]) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as fh:
                yaml.dump(data, fh)

        plans = promote_activations(
            promotions,
            config_path=config_path,
            config_data=config_data,
            save=_save,
            default_ids=default_ids,
        )

        changes_made = [f"Promoted {plan.activated} into {plan.yaml_key}" for plan in plans if plan.activated]
        warnings = [warning for plan in plans for warning in plan.warnings]
        if unresolved:
            warnings.append(_unresolved_warning(unresolved))

        return MigrationResult(
            success=True,
            changes_made=changes_made or ["No changes (all promotions already present)"],
            warnings=warnings,
        )
