"""Migration m_4_0_0rc5_retire_single_owner_doctrine_ids: consumer retirement sweep.

Mission ``squad-doctrine-single-owner-01M3KBP7`` (FR-009) deletes, renames,
moves or re-kinds several activatable doctrine ids in the built-in pack, as
part of consolidating each rule onto a single canonical owner (the mission's
"epic rule", #5218: one owner states each rule, every other artifact
references it by id). The charter compiler is deliberately fail-closed —
``charter.activation.compiler`` raises
:class:`charter.activation.kind_vocabulary.UnknownArtifactIdError` for any
``activated_<kind>`` stem it cannot resolve, uncaught on the compile path —
and the rc35 default-pack migration
(``m_3_2_0rc35_default_charter_pack``) copied the *then*-current default
pack's activation lists verbatim into every consumer's
``.kittify/config.yaml``/``charter.yaml``, writing only absent keys. A later
upgrade therefore never drops a stale member from an already-present
activation list on its own. Every consumer that ever activated one of this
mission's retired ids would hard-fail at charter compile time on their next
upgrade without this migration — the same unmanaged-retirement shape
``m_3_2_6_retire_rtk_search_tooling`` (#3009) already fixed once, and this
migration reuses that fix's generic engine (``_retired_activation.py``,
T002) rather than hand-rolling a second near-copy.

Retirement table (research.md R-11, spec.md FR-009)
----------------------------------------------------
Exposed as :data:`RETIREMENTS`, a tuple of
``_retired_activation.Retirement`` records, because WP09's DRG-consistency
test imports this table directly rather than re-deriving it. Verified
against ``src/charter/activation/packs/default.yaml`` and this repo's own
``.kittify/charter/charter.yaml`` / ``.kittify/charter/interview/
answers.yaml`` (the activated_*/selected_* key names and catalog id:
prefixes cited in the WP prompt):

======================  ============================  ========  ==============================================
kind key                retired stem                   prefix    successor (kind key, stem)
======================  ============================  ========  ==============================================
activated_styleguides   adversarial-squad-cadence       STYLEGUIDE  none
activated_tactics       bug-fixing-checklist            TACTIC      (activated_procedures, test-first-bug-fixing)
activated_tactics       locality-of-change               TACTIC      (activated_tactics, avoid-gold-plating)
activated_tactics       common-docs-curation             TACTIC      (activated_tactics, common-docs-scaffold),
                                                                      (activated_tactics, common-docs-write),
                                                                      (activated_tactics, common-docs-find)
activated_tactics       boring-code-review               TACTIC      (activated_styleguides, boring-code-review)
activated_tactics       behavior-driven-development      TACTIC      (activated_tactics, bdd-scenario-formulation)
activated_tactics       iterative-deepening-review       TACTIC      none (moves to the in-house pack)
activated_procedures    tracker-organisation-workflow    PROCEDURE   none (moves to the in-house pack)
======================  ============================  ========  ==============================================

``024-locality-of-change`` (the directive) is a different stem, under
``activated_directives``, and is never touched here — the shared engine
matches strictly by ``kind_key``, so the directive list is never even
inspected while retiring the ``locality-of-change`` *tactic*.

An id moved to ``packs/internal`` under the same name
(``tracker-organisation-workflow``) still resolves for a project that loads
that org pack via ``.kittify/config.yaml``'s ``charter_packs.org.packs``
(as this very repository does) — the shared engine's org-pack-resolvable
skip (see ``_retired_activation.py``) leaves those consumers' activations
untouched rather than retiring an id they can still legitimately use.
``iterative-deepening-review`` was renamed on the move
(``tracker-backlog-iterative-deepening``), so the skip never applies to it
and the migration retires it everywhere.

Consumer ``graph.yml`` (Rule 6)
--------------------------------
``.kittify/charter/graph.yml`` is a per-project, interview-driven induced
subgraph snapshot. A full repository search (``grep -rn 'graph\\.yml' src/``)
found no reader anywhere in ``src/`` -- not the charter compiler
(``charter.activation.compiler.compile_charter``), not
``charter.activation.context.build_charter_context``, nor any other
runtime code path; it is write-once, orphaned residue (independently noted
in ``docs/archive/plans/doctrine/squad-reports/architect.md``: "five orphaned
residue files ... none has a src writer"). A module nothing reads cannot be
broken by a stale node/edge id inside it, so a stale
``iterative-deepening-review``/``tracker-organisation-workflow`` node in a
consumer's ``graph.yml`` cannot regress charter compilation, and this
migration deliberately does NOT add ``graph.yml`` to its surfaces.
``tests/specify_cli/upgrade/migrations/test_retired_activation.py`` pins
this as an executable regression guard (a future ``graph.yml`` reader
would fail that guard and force this decision to be revisited).

Why a NEW migration module/id (mirrors
``m_4_0_0rc5_hosted_endpoint_session_backfill``'s docstring rationale)
------------------------------------------------------------------------
The upgrade runner records a migration as applied per project, keyed by
``migration_id``, and unconditionally skips a migration once recorded
(``specify_cli.upgrade.runner._apply_migration``). Folding this retirement
sweep into an already-shipped migration's ``apply()`` would therefore be
silently inert for every project that already ran that earlier migration.
Minting a fresh ``migration_id``/``target_version`` here means every
project's next upgrade evaluates this sweep regardless of what it already
recorded for any other migration. Auto-discovered via
``pkgutil.iter_modules`` + ``@MigrationRegistry.register`` (see
``auto_discover_migrations()``); no manual import/registration needed.

Scope and idempotency
----------------------
Five project surfaces per retirement, each optional (never created):
``.kittify/config.yaml``, ``.kittify/charter/charter.yaml`` (its top-level
``activated_<kind>`` lists and ``catalog`` block), that same file's nested
legacy ``governance.charter.selected_<kind>`` block,
``.kittify/charter/references.yaml``, and
``.kittify/charter/interview/answers.yaml``. A surface file that exists but
cannot be parsed is skipped and reported as a ``MigrationResult`` warning. A successor stem is activated
in the same file the retired stem was removed from, only when that
successor's own ``activated_<kind>`` list already exists there (never
created — an absent key means "not narrowed",
``m_3_2_x_normalize_activation_absence``), and only when it does not
already contain the successor. Every removal/activation is conditional, so
a second run is a no-op (``success=True``), and a bare project (no
``.kittify`` at all) is left byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from ._retired_activation import Retirement, apply_retirements, detect_retirements
from .base import BaseMigration, MigrationResult

_TACTICS_KEY = "activated_tactics"
_TACTIC_PREFIX = "TACTIC"

#: The consumer retirement table (research.md R-11 / spec.md FR-009). Module-
#: level constant so WP09's DRG-consistency test can import it directly
#: rather than re-deriving the same data a second time.
RETIREMENTS: tuple[Retirement, ...] = (
    Retirement(
        kind_key="activated_styleguides",
        stem="adversarial-squad-cadence",
        reference_prefix="STYLEGUIDE",
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="bug-fixing-checklist",
        reference_prefix=_TACTIC_PREFIX,
        successors=(("activated_procedures", "test-first-bug-fixing"),),
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="locality-of-change",
        reference_prefix=_TACTIC_PREFIX,
        successors=((_TACTICS_KEY, "avoid-gold-plating"),),
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="common-docs-curation",
        reference_prefix=_TACTIC_PREFIX,
        successors=(
            (_TACTICS_KEY, "common-docs-scaffold"),
            (_TACTICS_KEY, "common-docs-write"),
            (_TACTICS_KEY, "common-docs-find"),
        ),
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="boring-code-review",
        reference_prefix=_TACTIC_PREFIX,
        successors=(("activated_styleguides", "boring-code-review"),),
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="behavior-driven-development",
        reference_prefix=_TACTIC_PREFIX,
        successors=((_TACTICS_KEY, "bdd-scenario-formulation"),),
    ),
    Retirement(
        kind_key=_TACTICS_KEY,
        stem="iterative-deepening-review",
        reference_prefix=_TACTIC_PREFIX,
    ),
    Retirement(
        kind_key="activated_procedures",
        stem="tracker-organisation-workflow",
        reference_prefix="PROCEDURE",
    ),
)

_NO_OP_MESSAGE = "no retired single-owner doctrine id is activated in this project; nothing to remove"


@MigrationRegistry.register
class RetireSingleOwnerDoctrineIdsMigration(BaseMigration):
    """Retire every single-owner-doctrine-consolidation id from project charter surfaces.

    Without this, charter compilation hard-fails with
    ``UnknownArtifactIdError`` on every project that activated one of this
    mission's retired/renamed/re-kinded ids before upgrading past it.
    """

    migration_id = "4.0.0rc5_retire_single_owner_doctrine_ids"
    description = (
        "Remove every retired doctrine id from config.yaml, charter.yaml, "
        "references.yaml and the interview answers, activating each "
        "successor where one exists, so the fail-closed charter compiler "
        "does not hard-fail on a stale activation."
    )
    target_version = "4.0.0rc5"

    def detect(self, project_path: Path) -> bool:
        """True when any surface still activates a retired id this project cannot still resolve."""
        return detect_retirements(project_path, RETIREMENTS, include_answers_surface=True)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Only applicable when at least one retirement has a removable presence."""
        if self.detect(project_path):
            return True, ""
        return False, "no retired single-owner doctrine id is activated in this project"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Strip every retired id (and activate its successor) across every project surface."""
        result = apply_retirements(
            project_path,
            RETIREMENTS,
            include_answers_surface=True,
            dry_run=dry_run,
        )
        if not result.changes_made and not result.errors:
            return MigrationResult(success=True, changes_made=[_NO_OP_MESSAGE], warnings=result.warnings)
        return result
