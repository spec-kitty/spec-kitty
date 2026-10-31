"""Focused tests of ``4.0.0rc8_promote_interview_selections`` (#6629).

The migration is driven directly (``detect``/``apply`` on an instance) on
synthetic projects built from real built-in artefact ids, so each rule is
pinned on its own: an absent key is never written, a present list gains only
the interview ids it lacks (in identity space), a deactivation and an
unresolvable id are honoured, a re-apply is a no-op, a list an earlier build
seeded gets a hint and no write, and the shipped promotion it supersedes is a
recorded no-op.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.effective_set import resolve_effective_sets
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from kernel.charter_pack_paths import project_pack_root
from tests.charter.org_pack_identity_support import write_identity_org_pack
from specify_cli.upgrade.ledger import MigrationLedger, build_record, compute_content_hash
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations import m_4_0_0rc8_promote_interview_selections as module
from charter.activation.api import PromotionOutcome
from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError, SupersededMigration
from specify_cli.upgrade.migrations.m_4_0_0rc8_promote_interview_selections import MIGRATION_ID, PromoteInterviewSelectionsMigration
from specify_cli.upgrade.migrations.m_unify_charter_activation import UnifyCharterActivationMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.supersession import superseded_note
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.unit, pytest.mark.fast]

DIRECTIVES = "activated_directives"
LOCALITY_STEM = "024-locality-of-change"
LOCALITY_ID = "DIRECTIVE_024"
FIDELITY_STEM = "010-specification-fidelity-requirement"
FIDELITY_ID = "DIRECTIVE_010"
ARCHITECTURE_STEM = "001-architectural-integrity-standard"
DECISIONS_STEM = "003-decision-documentation-requirement"
DECISIONS_ID = "DIRECTIVE_003"
UNKNOWN_ID = "999-does-not-exist-anywhere"
CONFIG = Path(".kittify") / "config.yaml"
ANSWERS = Path(".kittify") / "charter" / "interview" / "answers.yaml"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path, *selected: str, paradigms: tuple[str, ...] = ()) -> Path:
    _write(tmp_path / CONFIG, "agents:\n  available: [claude]\n")
    lines = ["selected_directives:", *(f"- {item}" for item in selected)]
    if paradigms:
        lines += ["selected_paradigms:", *(f"- {item}" for item in paradigms)]
    _write(tmp_path / ANSWERS, "\n".join(lines) + "\n")
    return tmp_path


_TACTIC = 'schema_version: "1.0"\nid: {id}\nname: T\npurpose: T.\nsteps:\n  - title: Do\n    description: Do it.\n'


def _bytes(root: Path) -> dict[str, bytes]:
    paths = (CONFIG, Path(".kittify") / "charter" / "charter.yaml", Path(".kittify") / "charter" / "activation.yaml")
    return {str(rel): (root / rel).read_bytes() for rel in paths if (root / rel).is_file()}


# --------------------------------------------------------------------------- #
# apply: nothing to promote
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("answers", [None, "selected_directives: []\n", "mission: software-dev\n", "selected_directives: [unclosed\n", "- a list root\n"])
def test_no_selection_is_a_no_op_that_reads_no_doctrine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answers: str | None) -> None:
    def unexpected() -> Path:
        raise AssertionError("the doctrine root must not be resolved without a selection")

    monkeypatch.setattr(module, "resolve_offering_root", unexpected)
    _write(tmp_path / CONFIG, "{}\n")
    if answers is not None:
        _write(tmp_path / ANSWERS, answers)
    before = _bytes(tmp_path)

    result = PromoteInterviewSelectionsMigration().apply(tmp_path)

    assert result.success, result.errors
    assert result.changes_made == [module._NO_SELECTIONS]
    assert _bytes(tmp_path) == before


# --------------------------------------------------------------------------- #
# apply: absent keys
# --------------------------------------------------------------------------- #


def test_an_absent_key_is_never_written(tmp_path: Path) -> None:
    project = _project(tmp_path, LOCALITY_ID, FIDELITY_ID, paradigms=("domain-driven-design",))
    before = _bytes(project)

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert result.changes_made == [module._NOTHING_TO_PROMOTE]
    assert _bytes(project) == before
    assert read_activation_ledger(project) == {}


def test_an_absent_key_stays_absent_on_a_ledger_project(tmp_path: Path) -> None:
    project = _project(tmp_path, LOCALITY_ID)
    seed_activation_ledger(project, activated_paradigms=["domain-driven-design"])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert DIRECTIVES not in read_activation_ledger(project)
    assert "activated_" not in (project / CONFIG).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# apply: present lists
# --------------------------------------------------------------------------- #


def test_a_present_ledger_list_gains_exactly_the_missing_selection(tmp_path: Path) -> None:
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    config_before = (project / CONFIG).read_bytes()

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM, FIDELITY_STEM]
    assert (project / CONFIG).read_bytes() == config_before
    assert any(FIDELITY_STEM in change for change in result.changes_made)


# --------------------------------------------------------------------------- #
# apply: every layer resolves the selection (#6686)
# --------------------------------------------------------------------------- #

ORG_DIRECTIVE_STEM, ORG_DIRECTIVE_ID = "qa-003-no-fake-green", "QA_003"
PROJECT_TACTIC_STEM, PROJECT_TACTIC_ID = "proj-tac", "proj-tac-id"


def test_an_org_pack_selection_is_promoted_not_reported_unresolved(tmp_path: Path) -> None:
    """#6686: the upgrade resolves a selection through every layer, as `charter interview` does."""
    project = _project(tmp_path, ORG_DIRECTIVE_ID)
    write_identity_org_pack(project)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM, ORG_DIRECTIVE_STEM]
    assert not any("Unresolved" in warning for warning in result.warnings), result.warnings


def test_a_project_layer_tactic_selection_is_promoted(tmp_path: Path) -> None:
    """The project pack is one of the layers the shared authority indexes."""
    project = _project(tmp_path, paradigms=())
    answers = project / ANSWERS
    answers.write_text("selected_tactics:\n- " + PROJECT_TACTIC_ID + "\n", encoding="utf-8")
    _write(project_pack_root(project) / PROJECT_KIND_DIRS[ArtifactKind.TACTIC] / f"{PROJECT_TACTIC_STEM}.tactic.yaml", _TACTIC.format(id=PROJECT_TACTIC_ID))
    seed_activation_ledger(project, activated_tactics=["acceptance-test-first"])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)["activated_tactics"] == ["acceptance-test-first", PROJECT_TACTIC_STEM]


def test_an_org_selection_promotes_while_an_unknown_one_is_still_reported(tmp_path: Path) -> None:
    """One fixture, both outcomes: the positive control for the unresolved report."""
    project = _project(tmp_path, ORG_DIRECTIVE_ID, UNKNOWN_ID)
    write_identity_org_pack(project)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM, ORG_DIRECTIVE_STEM]
    assert result.warnings == [module._unresolved_warning([f"directive:{UNKNOWN_ID}"])]


def test_a_mission_step_contract_selection_resolves_and_promotes(tmp_path: Path) -> None:
    """The shared resolver's free win (#6686 notes): step contracts used to resolve in neither writer.

    `kind_vocabulary` could not resolve the kind, so the upgrade reported the
    selection unresolved. Through the layer-aware index it resolves like every
    other promoted kind, and it is promoted here; the interview does not capture
    step contracts, so nothing changes on that side.
    """
    project = _project(tmp_path)
    (project / ANSWERS).write_text("selected_mission_step_contracts:\n- qa-contract\n", encoding="utf-8")
    write_identity_org_pack(project)
    seed_activation_ledger(project, activated_mission_step_contracts=["existing-contract"])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)["activated_mission_step_contracts"] == ["existing-contract", "qa-contract-file"]
    assert result.warnings == []


def test_a_settled_shipped_promotion_means_nothing_is_appended(tmp_path: Path) -> None:
    """#6499: once the superseded promotion ran (or was adopted), a missing interview id was removed or never in force."""
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    MigrationLedger(project).append(build_record(UnifyCharterActivationMigration(), "success"))
    before = _bytes(project)

    result = PromoteInterviewSelectionsMigration().apply(project)
    preview = PromoteInterviewSelectionsMigration().apply(project, dry_run=True)

    assert result.success, result.errors
    assert result.changes_made == [module._ALREADY_PROMOTED]
    assert preview.changes_made == [module._NOTHING_PREVIEW]
    assert _bytes(project) == before


@pytest.mark.parametrize(
    ("superseded_by", "expected"),
    [("", [ARCHITECTURE_STEM]), (superseded_note(MIGRATION_ID), [ARCHITECTURE_STEM, FIDELITY_STEM])],
    ids=["a-legacy-skip-appends-nothing", "a-substitute-skip-still-promotes"],
)
def test_a_skipped_shipped_promotion_counts_only_when_the_shipped_step_recorded_it(tmp_path: Path, superseded_by: str, expected: list[str]) -> None:
    """The shipped step's own "Not applicable" skip means it ran; the substitute's marked no-op skip does not."""
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    MigrationLedger(project).append(build_record(UnifyCharterActivationMigration(), "skipped", superseded_by=superseded_by))

    PromoteInterviewSelectionsMigration().apply(project)

    assert read_activation_ledger(project)[DIRECTIVES] == expected


def test_a_declared_id_in_the_list_matches_the_stem_in_the_answers(tmp_path: Path) -> None:
    """#6423: an artefact spelled by its declared id in the list is not appended again by stem."""
    project = _project(tmp_path, LOCALITY_STEM)
    seed_activation_ledger(project, activated_directives=[LOCALITY_ID])
    before = _bytes(project)

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert _bytes(project) == before


def test_a_present_legacy_list_is_promoted_in_place(tmp_path: Path) -> None:
    """An unmigrated project (no activation ledger) keeps its keys where they are."""
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    _write(project / CONFIG, f"agents:\n  available: [claude]\nactivated_directives:\n- {ARCHITECTURE_STEM}\n")

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert FIDELITY_STEM in (project / CONFIG).read_text(encoding="utf-8")
    assert read_activation_ledger(project) == {}


def test_a_deactivated_selection_is_kept_deactivated(tmp_path: Path) -> None:
    project = _project(tmp_path, DECISIONS_ID, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM], deactivated_directives=[DECISIONS_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    ledger = read_activation_ledger(project)
    assert result.success, result.errors
    assert ledger[DIRECTIVES] == [ARCHITECTURE_STEM, FIDELITY_STEM]
    assert ledger["deactivated_directives"] == [DECISIONS_STEM]
    assert any(DECISIONS_STEM in warning and "deactivated" in warning for warning in result.warnings)


def test_a_deactivated_only_selection_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A deactivated-only selection: no write, no re-stamp, and the preview and real run report the primitive's skipped-denied warning.

    The org-required floor of the deny rule is guarded by
    ``test_a_deactivated_but_org_required_selection_is_promoted``.
    """
    calls: list[Path] = []
    monkeypatch.setattr("charter.activation.api.restamp_bundle_hash", lambda root: calls.append(root) or True)
    project = _project(tmp_path, DECISIONS_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM], deactivated_directives=[DECISIONS_STEM])
    before = _bytes(project)
    skipped = PromotionOutcome(skipped_denied={DIRECTIVES: [DECISIONS_STEM]}).skipped_denied_messages()

    preview = PromoteInterviewSelectionsMigration().apply(project, dry_run=True)
    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert (preview.changes_made, preview.warnings) == ([module._NOTHING_PREVIEW], skipped)
    assert (result.changes_made, result.warnings) == ([module._NOTHING_TO_PROMOTE], skipped)
    assert _bytes(project) == before
    assert calls == []


def test_a_deactivated_but_org_required_selection_is_promoted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale deny of an org-required id is inert (FR-006): the primitive's effective deny decides, not the raw deny list."""
    monkeypatch.setattr(
        "charter.activation.pack_context.read_org_required_tokens",
        lambda root, kind, *, strict: [DECISIONS_STEM] if kind.plural == "directives" else [],
    )
    monkeypatch.setattr("charter.activation.api.restamp_bundle_hash", lambda root: True)
    project = _project(tmp_path, DECISIONS_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM], deactivated_directives=[DECISIONS_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM, DECISIONS_STEM]


def test_an_unresolvable_selection_is_reported(tmp_path: Path) -> None:
    project = _project(tmp_path, UNKNOWN_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    before = _bytes(project)

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert _bytes(project) == before
    assert result.warnings == [module._unresolved_warning([f"directive:{UNKNOWN_ID}"])]


def test_a_reapply_changes_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    PromoteInterviewSelectionsMigration().apply(project)
    after_first = _bytes(project)

    again = PromoteInterviewSelectionsMigration().apply(project)

    assert again.success, again.errors
    assert again.changes_made == [module._NOTHING_TO_PROMOTE]
    assert _bytes(project) == after_first


def test_a_promotion_restamps_the_bundle_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    monkeypatch.setattr("charter.activation.api.restamp_bundle_hash", lambda root: calls.append(root) or True)
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])

    PromoteInterviewSelectionsMigration().apply(project)
    PromoteInterviewSelectionsMigration().apply(project)

    assert calls == [project]


@pytest.mark.parametrize(
    ("legacy_skip", "preview", "applied"),
    [
        (False, f"dry-run: would promote {{'{DIRECTIVES}': ['{FIDELITY_STEM}']}}", [ARCHITECTURE_STEM, FIDELITY_STEM]),
        (True, module._NOTHING_PREVIEW, [ARCHITECTURE_STEM]),
        (None, module._NOTHING_PREVIEW, [ARCHITECTURE_STEM]),
    ],
    ids=["nothing-recorded", "adopting-a-legacy-skip", "adopting-a-version-stamp"],
)
def test_a_dry_run_previews_and_writes_nothing(tmp_path: Path, legacy_skip: bool | None, preview: str, applied: list[str]) -> None:
    """The preview writes nothing and agrees with the real run, also before ledger adoption has recorded anything."""
    MigrationRegistry.clear()
    auto_discover_migrations()
    project = _project(tmp_path, ARCHITECTURE_STEM, FIDELITY_ID)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    stamp = "'2026-10-01T00:00:00+00:00'"
    rc7 = f"spec_kitty:\n  version: 4.0.0rc7\n  initialized_at: {stamp}\n"
    if legacy_skip:
        # The pre-ledger runner's own record: an rc7 project where the interview had already promoted.
        entry = f"  - id: {UnifyCharterActivationMigration.migration_id}\n    applied_at: {stamp}\n    result: skipped\n"
        _write(project / ".kittify" / "metadata.yaml", f"{rc7}migrations:\n  applied:\n{entry}")
    elif legacy_skip is None:
        # No applied list: the adoption backfill settles the shipped step from the rc7 version stamp.
        _write(project / ".kittify" / "metadata.yaml", rc7)
    before = _bytes(project)
    ledger_before = MigrationLedger(project).read_all()

    result = PromoteInterviewSelectionsMigration().apply(project, dry_run=True)

    assert result.success, result.errors
    assert result.changes_made == [preview]
    assert _bytes(project) == before
    assert MigrationLedger(project).read_all() == ledger_before
    for migration in MigrationRegistry.get_applicable("4.0.0rc7", "4.0.0rc8", project):
        if migration.ledger_adoption:
            migration.apply(project)
    PromoteInterviewSelectionsMigration().apply(project)
    assert read_activation_ledger(project)[DIRECTIVES] == applied


def test_a_dry_run_with_nothing_to_promote_says_so(tmp_path: Path) -> None:
    project = _project(tmp_path, LOCALITY_ID)

    result = PromoteInterviewSelectionsMigration().apply(project, dry_run=True)

    assert result.changes_made == [module._NOTHING_PREVIEW]


def test_a_malformed_activation_ledger_fails_the_upgrade_without_a_traceback(tmp_path: Path) -> None:
    """The runner turns ``MigrationStateUnreadableError`` into a failed, stopped run; nothing is written."""
    project = _project(tmp_path, FIDELITY_ID)
    ledger = seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])
    ledger.write_text("activated_directives: [unclosed\n", encoding="utf-8")
    before = _bytes(project)

    with pytest.raises(MigrationStateUnreadableError):
        PromoteInterviewSelectionsMigration().apply(project)
    assert _bytes(project) == before


def test_an_unresolvable_doctrine_root_is_a_failed_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> Path:
        raise RuntimeError("no doctrine")

    monkeypatch.setattr(module, "resolve_offering_root", broken)

    result = PromoteInterviewSelectionsMigration().apply(_project(tmp_path, FIDELITY_ID))

    assert result.success is False
    assert result.errors == ["Could not resolve doctrine root: no doctrine"]


def test_an_unrepresentable_directive_id_is_reported_as_unresolved(tmp_path: Path) -> None:
    """A directive identity no file stem can represent is reported, never promoted as another artifact.

    The fixture shadows the built-in ``024-locality-of-change`` file with an org
    directive of another id (Decision ``file_name_collision``), so ``DIRECTIVE_024``
    is known but has no single stem.
    """
    project = _project(tmp_path, "DIRECTIVE_024")
    pack = write_identity_org_pack(project)
    (pack / "directives" / "024-locality-of-change.directive.yaml").write_text(
        'schema_version: "1.0"\nid: ACME_024\ntitle: t\nintent: i\nenforcement: required\n', encoding="utf-8"
    )
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert result.warnings == [module._unresolved_warning(["directive:DIRECTIVE_024"])]
    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM]


def test_a_selection_named_twice_is_promoted_once(tmp_path: Path) -> None:
    project = _project(tmp_path, FIDELITY_ID, FIDELITY_STEM)
    seed_activation_ledger(project, activated_directives=[ARCHITECTURE_STEM])

    PromoteInterviewSelectionsMigration().apply(project)

    assert read_activation_ledger(project)[DIRECTIVES] == [ARCHITECTURE_STEM, FIDELITY_STEM]


# --------------------------------------------------------------------------- #
# A list an earlier build seeded
# --------------------------------------------------------------------------- #


def _every_directive(project: Path) -> list[str]:
    entry = resolve_effective_sets(project, [DIRECTIVES])[DIRECTIVES]
    assert entry.resolved and entry.ids
    return sorted(entry.ids)


def test_a_seeded_list_gets_a_hint_and_is_left_unchanged(tmp_path: Path) -> None:
    project = _project(tmp_path, LOCALITY_ID, FIDELITY_ID)
    seeded = _every_directive(project)
    seed_activation_ledger(project, activated_directives=seeded)
    before = _bytes(project)

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert _bytes(project) == before
    hint = module._SEEDED_LIST_HINT.format(key=DIRECTIVES, token="directive", listed=len(seeded), selected=2)
    assert result.warnings == [hint]
    assert "--narrow-activation" in hint and "--only" in hint


def test_an_operator_chosen_list_gets_no_hint(tmp_path: Path) -> None:
    project = _project(tmp_path, LOCALITY_ID)
    seed_activation_ledger(project, activated_directives=[LOCALITY_STEM, FIDELITY_STEM])

    result = PromoteInterviewSelectionsMigration().apply(project)

    assert result.success, result.errors
    assert result.warnings == []


def test_the_in_force_set_is_resolved_at_most_once_and_only_for_a_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: no list longer than the selection means no resolution; a candidate means one."""
    import charter.activation.api as seam

    calls: list[list[str]] = []
    original = seam.resolve_effective_sets

    def counting(root: Path, keys: list[str]) -> object:
        calls.append(list(keys))
        return original(root, keys)

    monkeypatch.setattr(seam, "resolve_effective_sets", counting)
    project = _project(tmp_path, LOCALITY_ID, paradigms=("domain-driven-design",))
    PromoteInterviewSelectionsMigration().apply(project)
    assert calls == []

    seed_activation_ledger(project, activated_directives=[LOCALITY_STEM, FIDELITY_STEM], activated_paradigms=["domain-driven-design", "deep-module-design"])
    PromoteInterviewSelectionsMigration().apply(project)
    assert calls == [[DIRECTIVES, "activated_paradigms"]]


def test_the_effect_is_tracked() -> None:
    """Its record routes to the tracked partition, which travels with the activation ledger it writes."""
    assert PromoteInterviewSelectionsMigration().clone_local_effect is False


# --------------------------------------------------------------------------- #
# Supersession of the shipped promotion
# --------------------------------------------------------------------------- #


def test_the_shipped_promotion_is_a_recorded_no_op_superseded_by_this_migration(tmp_path: Path) -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()
    registered = MigrationRegistry.get_by_id(UnifyCharterActivationMigration.migration_id)

    assert isinstance(registered, SupersededMigration)
    assert MIGRATION_ID in registered.superseded_by
    assert compute_content_hash(registered) == compute_content_hash(UnifyCharterActivationMigration())
    assert registered.detect(_project(tmp_path, FIDELITY_ID)) is False
    successor = MigrationRegistry.get_by_id(MIGRATION_ID)
    # Re-discovery re-imports the module, so compare by name rather than class identity.
    assert type(successor).__name__ == PromoteInterviewSelectionsMigration.__name__
    assert not isinstance(successor, SupersededMigration)
