"""Tests for the consumer retirement migration (mission
``squad-doctrine-single-owner-01M3KBP7``, WP01/T004).

Covers the production :data:`RETIREMENTS` table (research.md R-11 / spec.md
FR-009) and the migration class built on the shared engine tested in
``test_retired_activation.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations._retired_activation import Retirement
from specify_cli.upgrade.migrations.m_4_0_0rc5_retire_single_owner_doctrine_ids import (
    RETIREMENTS,
    RetireSingleOwnerDoctrineIdsMigration,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CHARTER_RELATIVE_PATH = Path(".kittify") / "charter" / "charter.yaml"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load(path: Path) -> dict:
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The table itself
# --------------------------------------------------------------------------- #


def test_retirements_table_matches_the_spec_table() -> None:
    """Pins research.md R-11 / spec.md FR-009's eight rows, verbatim."""
    by_stem = {r.stem: r for r in RETIREMENTS}
    assert len(RETIREMENTS) == 8
    assert set(by_stem) == {
        "adversarial-squad-cadence",
        "bug-fixing-checklist",
        "locality-of-change",
        "common-docs-curation",
        "boring-code-review",
        "behavior-driven-development",
        "iterative-deepening-review",
        "tracker-organisation-workflow",
    }

    assert by_stem["adversarial-squad-cadence"].kind_key == "activated_styleguides"
    assert by_stem["adversarial-squad-cadence"].reference_prefix == "STYLEGUIDE"
    assert by_stem["adversarial-squad-cadence"].successors == ()

    assert by_stem["bug-fixing-checklist"].kind_key == "activated_tactics"
    assert by_stem["bug-fixing-checklist"].successors == (("activated_procedures", "test-first-bug-fixing"),)

    assert by_stem["locality-of-change"].successors == (("activated_tactics", "avoid-gold-plating"),)

    assert by_stem["common-docs-curation"].successors == (
        ("activated_tactics", "common-docs-scaffold"),
        ("activated_tactics", "common-docs-write"),
        ("activated_tactics", "common-docs-find"),
    )

    assert by_stem["boring-code-review"].successors == (("activated_styleguides", "boring-code-review"),)
    assert by_stem["behavior-driven-development"].successors == (("activated_tactics", "bdd-scenario-formulation"),)

    assert by_stem["iterative-deepening-review"].kind_key == "activated_tactics"
    assert by_stem["iterative-deepening-review"].successors == ()

    assert by_stem["tracker-organisation-workflow"].kind_key == "activated_procedures"
    assert by_stem["tracker-organisation-workflow"].reference_prefix == "PROCEDURE"
    assert by_stem["tracker-organisation-workflow"].successors == ()


# --------------------------------------------------------------------------- #
# detect(): parametrized over every table row
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("retirement", RETIREMENTS, ids=[r.stem for r in RETIREMENTS])
def test_detect_true_for_every_table_row(tmp_path: Path, retirement: Retirement) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        f"{retirement.kind_key}:\n- {retirement.stem}\n",
    )

    migration = RetireSingleOwnerDoctrineIdsMigration()

    assert migration.detect(tmp_path) is True
    assert migration.can_apply(tmp_path) == (True, "")


@pytest.mark.parametrize("retirement", RETIREMENTS, ids=[r.stem for r in RETIREMENTS])
def test_apply_removes_every_table_row_from_charter_yaml(tmp_path: Path, retirement: Retirement) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        f"{retirement.kind_key}:\n- {retirement.stem}\n- sibling-kept\n",
    )

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    # A successor whose target key coincides with the retired id's own
    # kind_key (e.g. locality-of-change -> activated_tactics) may append an
    # extra sibling into this same list, so only the exact removal and the
    # ORIGINAL sibling's survival are pinned here -- exact-table successor
    # behaviour has its own dedicated tests below.
    assert retirement.stem not in charter[retirement.kind_key]
    assert "sibling-kept" in charter[retirement.kind_key]


def test_detect_false_on_a_bare_project(tmp_path: Path) -> None:
    migration = RetireSingleOwnerDoctrineIdsMigration()

    assert migration.detect(tmp_path) is False
    assert migration.can_apply(tmp_path) == (
        False,
        "no retired single-owner doctrine id is activated in this project",
    )


# --------------------------------------------------------------------------- #
# Successor activation, multi-successor row
# --------------------------------------------------------------------------- #


def test_common_docs_curation_activates_all_three_successors(tmp_path: Path) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "activated_tactics:\n- common-docs-curation\n- other-tactic\n",
    )

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["activated_tactics"] == [
        "other-tactic",
        "common-docs-scaffold",
        "common-docs-write",
        "common-docs-find",
    ]


def test_boring_code_review_activates_the_styleguide_successor_only_when_present(tmp_path: Path) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "activated_tactics:\n- boring-code-review\nactivated_styleguides: []\n",
    )

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert "boring-code-review" not in charter["activated_tactics"]
    assert charter["activated_styleguides"] == ["boring-code-review"]


def test_successor_never_invented_when_target_list_absent(tmp_path: Path) -> None:
    """bug-fixing-checklist's successor list (activated_procedures) is entirely absent."""
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "activated_tactics:\n- bug-fixing-checklist\n")

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["activated_tactics"] == []
    assert "activated_procedures" not in charter


# --------------------------------------------------------------------------- #
# Directive/tactic slug collision, using the real locality-of-change row
# --------------------------------------------------------------------------- #


def test_directive_024_locality_of_change_is_untouched(tmp_path: Path) -> None:
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "activated_directives:\n- 024-locality-of-change\nactivated_tactics:\n- locality-of-change\n- avoid-gold-plating\n",
    )

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    assert charter["activated_directives"] == ["024-locality-of-change"]
    assert charter["activated_tactics"] == ["avoid-gold-plating"]


# --------------------------------------------------------------------------- #
# Whole-table idempotency and no-op message
# --------------------------------------------------------------------------- #


def test_apply_over_the_whole_table_is_idempotent(tmp_path: Path) -> None:
    stems_by_kind_key: dict[str, list[str]] = {}
    for retirement in RETIREMENTS:
        stems_by_kind_key.setdefault(retirement.kind_key, []).append(retirement.stem)
    text = "".join(f"{kind_key}:\n" + "".join(f"- {stem}\n" for stem in stems) for kind_key, stems in stems_by_kind_key.items())
    _write(tmp_path / _CHARTER_RELATIVE_PATH, text)
    migration = RetireSingleOwnerDoctrineIdsMigration()

    first = migration.apply(tmp_path)
    second = migration.apply(tmp_path)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == ["no retired single-owner doctrine id is activated in this project; nothing to remove"]
    assert migration.detect(tmp_path) is False


def test_apply_on_bare_project_reports_the_no_op_message(tmp_path: Path) -> None:
    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    assert result.changes_made == ["no retired single-owner doctrine id is activated in this project; nothing to remove"]
    assert not (tmp_path / ".kittify").exists()


def test_dry_run_leaves_the_project_untouched(tmp_path: Path) -> None:
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "activated_tactics:\n- locality-of-change\n")
    before = (tmp_path / _CHARTER_RELATIVE_PATH).read_text(encoding="utf-8")

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert result.changes_made
    assert (tmp_path / _CHARTER_RELATIVE_PATH).read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------- #
# Migration identity + registration
# --------------------------------------------------------------------------- #


def test_migration_identity() -> None:
    migration = RetireSingleOwnerDoctrineIdsMigration()
    assert migration.migration_id == "4.0.0rc5_retire_single_owner_doctrine_ids"
    assert migration.target_version == "4.0.0rc5"


# --------------------------------------------------------------------------- #
# The legacy governance.charter.selected_<kind> block (WP10-discovered gap,
# spec.md FR-009 amendment)
# --------------------------------------------------------------------------- #


def test_apply_removes_every_table_row_from_governance_charter_selected_block(tmp_path: Path) -> None:
    """Mirrors WP10's real charter.yaml shape: retired ids nested under governance.charter."""
    _write(
        tmp_path / _CHARTER_RELATIVE_PATH,
        "governance:\n"
        "  charter:\n"
        "    selected_tactics:\n"
        "    - bug-fixing-checklist\n"
        "    - locality-of-change\n"
        "    - common-docs-curation\n"
        "    - boring-code-review\n"
        "    - behavior-driven-development\n"
        "    - other-tactic\n"
        "    selected_styleguides:\n"
        "    - adversarial-squad-cadence\n"
        "    - other-styleguide\n"
        "    selected_procedures:\n"
        "    - other-procedure\n"
        "    selected_agent_profiles:\n"
        "    - implementer-ivan\n",
    )

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)

    assert result.success is True
    charter = _load(tmp_path / _CHARTER_RELATIVE_PATH)
    selected = charter["governance"]["charter"]
    assert selected["selected_tactics"] == [
        "other-tactic",
        "avoid-gold-plating",
        "common-docs-scaffold",
        "common-docs-write",
        "common-docs-find",
        "bdd-scenario-formulation",
    ]
    assert selected["selected_styleguides"] == ["other-styleguide", "boring-code-review"]
    assert selected["selected_procedures"] == ["other-procedure", "test-first-bug-fixing"]
    # common-docs-curation's successors are never invented -- charter.yaml's
    # governance.charter block above never declared its own selected_tactics
    # entries for common-docs-{scaffold,write,find}, but selected_tactics DOES
    # exist as a list, so they ARE activated there (same rule as the top-level
    # activated_tactics surface): confirm all three landed.
    assert "common-docs-scaffold" in selected["selected_tactics"]
    assert "common-docs-write" in selected["selected_tactics"]
    assert "common-docs-find" in selected["selected_tactics"]
    # A retirement with no successor (adversarial-squad-cadence) leaves the
    # untouched sibling profile list alone.
    assert selected["selected_agent_profiles"] == ["implementer-ivan"]


def test_governance_charter_block_is_idempotent_over_the_whole_table(tmp_path: Path) -> None:
    stems_by_kind_key: dict[str, list[str]] = {}
    for retirement in RETIREMENTS:
        stems_by_kind_key.setdefault(retirement.kind_key, []).append(retirement.stem)
    selected_lines = "".join(
        f"    {kind_key.replace('activated_', 'selected_')}:\n" + "".join(f"    - {stem}\n" for stem in stems) for kind_key, stems in stems_by_kind_key.items()
    )
    _write(tmp_path / _CHARTER_RELATIVE_PATH, "governance:\n  charter:\n" + selected_lines)
    migration = RetireSingleOwnerDoctrineIdsMigration()

    first = migration.apply(tmp_path)
    second = migration.apply(tmp_path)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == ["no retired single-owner doctrine id is activated in this project; nothing to remove"]
    assert migration.detect(tmp_path) is False


def test_dogfood_repo_governance_charter_block_matches_wp10_hand_fix() -> None:
    """End-to-end: applying the migration to this repo's own PRE-migration
    charter.yaml (as it stood at commit a8e0984b, before WP10's dogfooding
    commit d5aa133c) reproduces the same governance.charter.selected_* block
    WP10's hand-edit committed at HEAD -- for the six retirements this
    project actually had activated (the other two retired ids in the table
    were never present in this project's charter.yaml at all, at any commit).
    """
    import subprocess
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve()
    for parent in (repo_root, *repo_root.parents):
        if (parent / ".git").exists() and (parent / "src").is_dir():
            repo_root = parent
            break
    else:  # pragma: no cover -- defensive; the repo root always exists in CI/dev
        pytest.skip("could not locate repo root")

    pre_migration_charter = subprocess.run(
        ["git", "show", "a8e0984b:.kittify/charter/charter.yaml"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        _write(project / _CHARTER_RELATIVE_PATH, pre_migration_charter)

        result = RetireSingleOwnerDoctrineIdsMigration().apply(project)

        assert result.success is True
        migrated = _load(project / _CHARTER_RELATIVE_PATH)
        migrated_block = migrated["governance"]["charter"]

    head_charter_yaml = (repo_root / ".kittify" / "charter" / "charter.yaml").read_text(encoding="utf-8")
    head_block = YAML(typ="safe").load(head_charter_yaml)["governance"]["charter"]

    # Retired stems, scoped by the SELECTED_<KIND> list they were retired
    # from -- a retired stem can collide by name with an unrelated
    # successor of a *different* kind (e.g. the tactic "boring-code-review"
    # is retired, but "boring-code-review" the STYLEGUIDE is its very
    # successor, legitimately present in selected_styleguides afterwards).
    retired_by_selected_kind: dict[str, set[str]] = {}
    for retirement in RETIREMENTS:
        selected_kind = retirement.kind_key.replace("activated_", "selected_", 1)
        retired_by_selected_kind.setdefault(selected_kind, set()).add(retirement.stem)

    for kind_key in ("selected_tactics", "selected_styleguides", "selected_procedures"):
        migrated_kind = set(migrated_block.get(kind_key, []))
        head_kind = set(head_block.get(kind_key, []))
        retired_for_kind = retired_by_selected_kind.get(kind_key, set())
        # No retired stem survives the migration, for THIS kind's own list.
        assert not (migrated_kind & retired_for_kind), f"{kind_key}: retired stems survived migration: {migrated_kind & retired_for_kind}"
        # The migrated set equals HEAD's hand-fixed set for this kind, modulo
        # ids WP10's hand-edit touched for unrelated reasons (none observed in
        # practice -- this assertion is the executable proof of that).
        assert migrated_kind == head_kind, f"{kind_key}: migration result {migrated_kind} != WP10 hand-fix {head_kind}"


def test_migration_is_registered_by_auto_discovery() -> None:
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    MigrationRegistry.clear()
    auto_discover_migrations()

    assert "4.0.0rc5_retire_single_owner_doctrine_ids" in MigrationRegistry._migrations
